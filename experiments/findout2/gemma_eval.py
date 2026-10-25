"""Run off-the-shelf Gemma 4 models on the pilot's held-out test set, with the same system prompt, tools and request text
the pilot model saw, and world2's real tools. No fine-tuning. Thinking off, greedy, like the pilot.

  python gemma_eval.py --models google/gemma-4-E2B-it,google/gemma-4-E4B-it --out out
Writes out/GEMMA_RESULTS.md and out/gemma_<name>.jsonl (every transcript)."""
import argparse, json, os, re, time, zlib, gc
import world2 as w

ap = argparse.ArgumentParser()
ap.add_argument("--models", default="google/gemma-4-E2B-it")
ap.add_argument("--per_type", type=int, default=24)
ap.add_argument("--max_turns", type=int, default=12)
ap.add_argument("--max_new", type=int, default=512)
ap.add_argument("--bs", type=int, default=40)
ap.add_argument("--out", default="out")
ap.add_argument("--dry", action="store_true", help="render and parse only, no model")
A = ap.parse_args()
os.makedirs(A.out, exist_ok=True)
T0 = time.time()
LOG = open(os.path.join(A.out, "log.txt"), "a")


def log(*a):
    s = f"[{(time.time() - T0) / 60:5.1f} min] " + " ".join(str(x) for x in a)
    print(s, flush=True); LOG.write(s + "\n"); LOG.flush()


# the same held-out episodes as pilot.py (same seeds)
TEST = []
for fn in w.HELD_OUT:
    TEST += w.make_set(zlib.crc32(fn.__name__.encode()) % 1000 + 300, A.per_type, [fn])
SUBSET = {("H:bridge-compare", i) for i in (1, 2, 3, 0, 6, 7)} | {("H:ask-diff", i) for i in (0, 1, 3, 4, 5, 8)} | {("H:argmax4", i) for i in (0, 1, 4, 10)}

CALL = re.compile(r"<\|tool_call>call:(\w+)\{(.*?)\}<tool_call\|>", re.S)
ARG = re.compile(r'(\w+):(?:<\|"\|>(.*?)<\|"\|>|([^,}]*))', re.S)


def parse(text):
    """Gemma 4 output -> (visible text, [(name, args)])."""
    t = re.sub(r"<\|channel>.*?<channel\|>", "", text, flags=re.S)
    calls = []
    for m in CALL.finditer(t):
        args = {k: (s if s is not None else v.strip()) for k, s, v in ARG.findall(m.group(2))}
        calls.append((m.group(1), args))
    vis = CALL.sub("", t)
    for tok in ("<turn|>", "<|tool_response>", "<eos>", "<pad>"):
        vis = vis.replace(tok, "")
    return vis.strip(), calls


def fair(task, final, H, outputs):
    """Fixes for the three scorer problems: yes/no answers, facts already seen in a tool result, non-answers."""
    short, _ = w.short_answer(final or "")
    ok = bool(final) and bool(task["check"](short))
    if re.search(r"can'?t|cannot|unable|not sure|don'?t know|no (size|population|data)", short, re.I):
        ok = False
    if task["type"] == "H:bridge-compare" and task["request"].lower().replace("'", "").find("is the town") >= 0:
        need = [s for s in task["needs"] if s[0] == "search" and s[1] == "town"]
        t_home, t_other = need[0][2], need[1][2]
        yes = task["world"]["town"][t_home]["population"] > task["world"]["town"][t_other]["population"]
        m = re.match(r"\W*(yes|no)\b", short, re.I)
        if m:
            ok = (m.group(1).lower() == "yes") == yes
    seen = " ".join(outputs)
    got = all(w.fact_sentence(k, e, a, task["world"][k][e][a]) in seen for s in task["needs"] if s[0] == "search" for _, k, e, a in [s])
    names = [n for n, _ in H.log]
    calc_ok = "calculator" in names or not any(s[0] == "calc" for s in task["needs"])
    ask_ok = "ask_person" in names or not any(s[0] == "ask" for s in task["needs"])
    return ok, ok and got and calc_ok and ask_ok


def to_msgs(task, turns):
    msgs = [{"role": "system", "content": w.SYSTEM}, {"role": "user", "content": task["request"]}]
    for k, (content, calls, results) in enumerate(turns):
        m = {"role": "assistant", "content": content}
        if calls:
            m["tool_calls"] = [{"id": f"c{k}_{j}", "type": "function", "function": {"name": n, "arguments": a}} for j, (n, a) in enumerate(calls)]
        msgs.append(m)
        for j, ((n, _), r) in enumerate(zip(calls, results)):
            msgs.append({"role": "tool", "tool_call_id": f"c{k}_{j}", "name": n, "content": r})
    return msgs


def run_model(name):
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(name)
    tok.padding_side = "left"
    if A.dry:
        model = None
    else:
        import torch, transformers
        cls = getattr(transformers, "AutoModelForMultimodalLM", None) or transformers.AutoModelForImageTextToText
        model = cls.from_pretrained(name, dtype=torch.bfloat16, device_map="cuda").eval()
    stop = [i for i in (tok.convert_tokens_to_ids(t) for t in ("<turn|>", "<|tool_response>", "<eos>")) if isinstance(i, int) and i >= 0]
    S = [{"t": t, "turns": [], "H": w.Harness(t), "final": None, "first": "", "outputs": [], "raw": [],
          "prompt": tok.apply_chat_template(to_msgs(t, []), tools=w.TOOLS, tokenize=False, add_generation_prompt=True, enable_thinking=False)}
         for t in TEST]
    live = list(range(len(S)))
    turn = 0
    while live:
        turn += 1
        prompts = [S[i]["prompt"] for i in live]
        if turn == 1:
            log("example prompt:\n" + prompts[0][-1500:])
        outs = []
        for k in range(0, len(prompts), A.bs):
            chunk = prompts[k:k + A.bs]
            if model is None:
                outs += ['Needs:\n1. x (search)<|tool_call>call:search{query:<|"|>Kobripel town<|"|>}<tool_call|>' if turn == 1 else "Answer: Drasor<turn|>"] * len(chunk)
                continue
            enc = tok(chunk, return_tensors="pt", padding=True, add_special_tokens=False).to("cuda")
            with torch.no_grad():
                g = model.generate(**enc, max_new_tokens=A.max_new, do_sample=False, eos_token_id=stop, pad_token_id=tok.pad_token_id)
            outs += tok.batch_decode(g[:, enc["input_ids"].shape[1]:], skip_special_tokens=False)
        nxt = []
        for i, text in zip(live, outs):
            text = text.replace("<pad>", "")
            s = S[i]; s["raw"].append(text)
            vis, calls = parse(text)
            if turn == 1:
                s["first"] = vis
            if calls and turn < A.max_turns:
                res = [s["H"].run(n, a) for n, a in calls]
                s["outputs"] += res
                s["turns"].append((vis, calls, res))
                # Gemma 4's native continuation: its own output up to the last call, then the responses, same model turn
                body = text[:text.rfind("<tool_call|>") + len("<tool_call|>")]
                s["prompt"] += body + "".join(f'<|tool_response>response:{n}{{value:<|"|>{r}<|"|>}}<tool_response|>' for (n, _), r in zip(calls, res))
                nxt.append(i)
            else:
                s["final"] = vis
        live = nxt
        log(f"{name}: turn {turn}, {len(live)} still going")
    del model; gc.collect()
    try:
        import torch, shutil; torch.cuda.empty_cache()
        if not A.dry:   # five models are ~160 GB; free the disk before the next one
            from huggingface_hub.constants import HF_HUB_CACHE
            shutil.rmtree(os.path.join(HF_HUB_CACHE, "models--" + name.replace("/", "--")), ignore_errors=True)
    except Exception:
        pass
    rows = []
    for s in S:
        sc = w.score(s["t"], s["final"] or "", s["H"], s["first"])
        f_ok, f_strict = fair(s["t"], s["final"], s["H"], s["outputs"])
        idx = TEST.index(s["t"]) % A.per_type
        rows.append({"type": s["t"]["type"], "idx": idx, "style": s["t"]["style"], "request": s["t"]["request"], "gold": str(s["t"]["short"]),
                     "final": s["final"], "ok": sc["ok"], "strict": sc["strict"], "fair_ok": f_ok, "fair_strict": f_strict,
                     "subset": (s["t"]["type"], idx) in SUBSET, "calls": [[n, a] for n, a in s["H"].log], "outputs": s["outputs"], "raw": s["raw"]})
    with open(os.path.join(A.out, f"gemma_{name.split('/')[-1]}.jsonl"), "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return rows


def pct(xs):
    return f"{100 * sum(xs) / max(1, len(xs)):.0f}%"


report = ["# Gemma 4 on the pilot's held-out test set", "",
          "Off the shelf, no fine-tuning. Same system prompt, tools and request text as the pilot; thinking off, greedy. "
          "`ok`/`strict` = world2's scorer (same as PILOT_RESULTS.md). `fair` = with the three scorer fixes "
          "(yes/no accepted, facts already seen in a tool result count, non-answers fail). Subset = the 16 episodes Haiku and Sonnet ran.", ""]
summary = [["model", "held-out ok", "held-out strict", "fair ok", "fair strict", "16-subset fair ok", "minutes"]]
by_type = {}
for name in A.models.split(","):
    t1 = time.time()
    try:
        rows = run_model(name)
    except Exception as e:
        log(f"{name} failed: {e!r}"[:2000]); summary.append([name, "failed", repr(e)[:80], "", "", "", ""]); continue
    sub = [r for r in rows if r["subset"]]
    summary.append([name.split("/")[-1], pct([r["ok"] for r in rows]), pct([r["strict"] for r in rows]), pct([r["fair_ok"] for r in rows]),
                    pct([r["fair_strict"] for r in rows]), f"{sum(r['fair_ok'] for r in sub)}/{len(sub)}", f"{(time.time() - t1) / 60:.1f}"])
    for ty in sorted({r["type"] for r in rows}):
        rr = [r for r in rows if r["type"] == ty]
        by_type.setdefault(ty, {})[name.split("/")[-1]] = f"{pct([r['strict'] for r in rr])} strict / {pct([r['fair_ok'] for r in rr])} fair"
    log(" | ".join(summary[-1]))
    md = report + ["| " + " | ".join(summary[0]) + " |", "|" + " --- |" * len(summary[0])] + ["| " + " | ".join(r) + " |" for r in summary[1:]]
    ms = list(next(iter(by_type.values())).keys()) if by_type else []
    md += ["", "## By held-out type (world2 strict / fair right answer)", "", "| type | " + " | ".join(ms) + " |", "|" + " --- |" * (len(ms) + 1)]
    md += ["| " + ty + " | " + " | ".join(v.get(m, "") for m in ms) + " |" for ty, v in by_type.items()]
    open(os.path.join(A.out, "GEMMA_RESULTS.md"), "w").write("\n".join(md) + "\n")
log("done")
