"""Findout pilot: does LFM2.5-350M learn to put plans together, without losing its English?

  python pilot.py --arms untouched,gold                   # untouched (two worked examples) and trained on template episodes
  python pilot.py --arms teacher --teacher teacher_episodes.jsonl
  python pilot.py --smoke ...                             # tiny everything, to check the pipeline end to end

Each trained arm: a full fine-tune on ~2,000 world-v2 episodes plus 20% replay of the base model's own everyday answers.
Tests: the 10 trained task types (fresh worlds) and 5 held-out combinations of trained parts, half the requests in a
messy style; WikiText-2 perplexity; plain chat with and without tools. Everything lands in out/.
"""
import argparse, collections, json, math, os, random, re, sys, time, zlib
import torch
import torch.nn.functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer
from world2 import *  # noqa: F401,F403

ap = argparse.ArgumentParser()
ap.add_argument("--arms", default="untouched,gold")
ap.add_argument("--teacher", default="teacher_episodes.jsonl")
ap.add_argument("--n_train", type=int, default=2000)
ap.add_argument("--per_type", type=int, default=24)          # test episodes per task type
ap.add_argument("--epochs", type=float, default=2)
ap.add_argument("--lr", type=float, default=2e-5)
ap.add_argument("--export", action="store_true")
ap.add_argument("--smoke", action="store_true")
A = ap.parse_args()
if A.smoke:
    A.n_train, A.per_type, A.epochs = 48, 2, 1

MODEL = "LiquidAI/LFM2.5-350M"
OUT = "out"
os.makedirs(OUT, exist_ok=True)
DEV = "cuda"
T0 = time.time()
torch.manual_seed(0)
LOG = open(f"{OUT}/log.txt", "a")


def log(*a):
    s = f"[{(time.time() - T0) / 60:5.1f} min] " + " ".join(str(x) for x in a)
    print(s, flush=True); LOG.write(s + "\n"); LOG.flush()


tok = AutoTokenizer.from_pretrained(MODEL)
tok.padding_side = "left"
EOS = tok.convert_tokens_to_ids("<|im_end|>")
PAD = tok.pad_token_id if tok.pad_token_id is not None else 0


def load():
    return AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32).to(DEV)


def to_hf(msgs):
    out = []
    for m in msgs:
        if m["role"] == "assistant":
            d = {"role": "assistant", "content": m.get("content") or ""}
            if m.get("tool_calls"):
                d["tool_calls"] = [{"type": "function", "function": {"name": c["name"], "arguments": c["arguments"]}} for c in m["tool_calls"]]
            out.append(d)
        else:
            out.append({"role": "tool", "content": m["content"]})
    return out


def check_render():
    """Our renderer must match the model's own chat template, or we'd train on a format it never saw."""
    r = random.Random(1)
    bad = 0
    for fn in (t_total, t_ask, h_bridge_compare):
        t = make_task(r, fn, 0)
        msgs, _ = gold_episode(t, r)
        ours = "".join(p for p, _ in render_lfm(msgs, user=t["request"]))
        theirs = tok.apply_chat_template([{"role": "system", "content": SYSTEM}, {"role": "user", "content": t["request"]}] + to_hf(msgs),
                                         tools=TOOLS, tokenize=False)
        if ours != theirs:
            bad += 1
            i = next((k for k in range(min(len(ours), len(theirs))) if ours[k] != theirs[k]), min(len(ours), len(theirs)))
            log(f"RENDER MISMATCH at char {i}:\n ours  : {ours[max(0, i - 80):i + 120]!r}\n theirs: {theirs[max(0, i - 80):i + 120]!r}")
    log("renderer matches the chat template" if not bad else f"renderer differs from the template in {bad}/3 samples")
    return bad == 0


def encode(pieces, max_len=2048):
    ids, lab = [], []
    for text, train in pieces:
        t = tok(text, add_special_tokens=False)["input_ids"]
        ids += t; lab += t if train else [-100] * len(t)
    return ids[:max_len], lab[:max_len]


def user_part(req, msgs):
    return render_lfm(msgs, user=req)[1:]


def prompt(req, msgs, shots=()):
    pieces = render_lfm([], user=None)
    for sreq, smsgs in shots:
        pieces += user_part(sreq, smsgs)
    pieces += user_part(req, msgs)
    return "".join(p for p, _ in pieces) + "<|im_start|>assistant\n"


def plain_prompt(p, tools=False):
    sys_part = ("<|im_start|>system\n" + SYSTEM + "\nList of tools: [" + ", ".join(json.dumps(t) for t in TOOLS) + "]<|im_end|>\n") if tools else ""
    return f"<|startoftext|>{sys_part}<|im_start|>user\n{p}<|im_end|>\n<|im_start|>assistant\n"


@torch.no_grad()
def generate(model, prompts, max_new=320, bs=48):
    model.eval()
    order = sorted(range(len(prompts)), key=lambda i: len(prompts[i]))
    outs = [None] * len(prompts)
    for k in range(0, len(order), bs):
        idx = order[k:k + bs]
        enc = tok([prompts[i] for i in idx], return_tensors="pt", padding=True, add_special_tokens=False).to(DEV)
        with torch.autocast("cuda", dtype=torch.bfloat16):
            g = model.generate(**enc, max_new_tokens=max_new, do_sample=False, eos_token_id=EOS, pad_token_id=PAD)
        for i, row in zip(idx, g[:, enc["input_ids"].shape[1]:]):
            outs[i] = tok.decode(row, skip_special_tokens=False).split("<|im_end|>")[0].replace("<|pad|>", "")
    return outs


def run_eval(model, tasks, shots=(), max_turns=12):
    S = [{"t": t, "msgs": [], "H": Harness(t), "turns": 0, "final": None} for t in tasks]
    live = list(range(len(S)))
    while live:
        texts = generate(model, [prompt(S[i]["t"]["request"], S[i]["msgs"], shots) for i in live])
        nxt = []
        for i, text in zip(live, texts):
            s = S[i]; content, calls = parse_lfm(text)
            s["turns"] += 1
            if calls and s["turns"] < max_turns:
                s["msgs"].append({"role": "assistant", "content": content, "tool_calls": calls})
                for c in calls:
                    s["msgs"].append({"role": "tool", "name": c["name"], "content": s["H"].run(c["name"], c.get("arguments", {}))})
                nxt.append(i)
            else:
                s["msgs"].append({"role": "assistant", "content": content})
                s["final"] = content if not calls else ""
        live = nxt
    rows = []
    for s in S:
        first = next((m.get("content", "") for m in s["msgs"] if m["role"] == "assistant"), "")
        sc = score(s["t"], s["final"], s["H"], first)
        sc["turns"] = s["turns"]
        rows.append((sc, s))
    return rows


def summarise(rows):
    by = collections.defaultdict(list)
    for sc, _ in rows:
        by[sc["type"]].append(sc)
    def frac(xs, k):
        return sum(1 for x in xs if x[k]) / len(xs) if xs else float("nan")
    out = {}
    for ty, xs in by.items():
        out[ty] = {"n": len(xs), "ok": frac(xs, "ok"), "strict": frac(xs, "strict"), "strict": frac(xs, "strict"), "ok_clean": frac([x for x in xs if x["style"] == "clean"], "ok"),
                   "ok_messy": frac([x for x in xs if x["style"] == "messy"], "ok"), "coverage": sum(x["coverage"] for x in xs) / len(xs),
                   "needs_list": frac(xs, "needs_list"), "answer_line": frac(xs, "answer_line"),
                   "calc_when_needed": frac([x for x in xs if x["needs_calc"]], "calc"),
                   "asked_when_needed": frac([x for x in xs if x["needs_ask"]], "asked"),
                   "asked_when_not": frac([x for x in xs if not x["needs_ask"]], "asked"),
                   "searched_given": frac([x for x in xs if ty == "given"], "searched_given") if ty == "given" else float("nan"),
                   "searches": sum(x["searches"] for x in xs) / len(xs), "needed_searches": sum(x["needed_searches"] for x in xs) / len(xs)}
    return out


def transcript(s):
    L = [f"user: {s['t']['request']}"]
    for m in s["msgs"]:
        if m["role"] == "assistant":
            calls = "".join(f"\n  -> {c['name']}({json.dumps(c.get('arguments', {}))})" for c in m.get("tool_calls", []))
            L.append(f"assistant: {m.get('content', '')}{calls}")
        else:
            L.append(f"  <- {m['content']}")
    return "\n".join(L)


def english(model, max_tokens):
    """English kept, three ways on WikiText-2 test: raw text (as before), raw text with an explicit mask and no cache,
    and the same text as an assistant reply (the form this model actually writes in). Each window starts with BOS."""
    from datasets import load_dataset
    text = "\n\n".join(load_dataset("Salesforce/wikitext", "wikitext-2-raw-v1", split="test")["text"])
    ids = tok(text, add_special_tokens=False, return_tensors="pt")["input_ids"][0][:max_tokens]
    head = tok("<|startoftext|><|im_start|>user\nWrite a passage of encyclopedia text.<|im_end|>\n<|im_start|>assistant\n",
               add_special_tokens=False, return_tensors="pt")["input_ids"][0]
    bos = head[:1]
    model.eval(); out = {}
    for mode in ("raw", "raw_masked", "as_reply"):
        nll, n = 0.0, 0
        with torch.no_grad():
            for k in range(0, len(ids), 1024):
                w = ids[k:k + 1024]
                pre = head if mode == "as_reply" else bos
                x = torch.cat([pre, w]).unsqueeze(0).to(DEV)
                kw = {} if mode == "raw" else {"attention_mask": torch.ones_like(x[:, :-1]), "use_cache": False}
                with torch.autocast("cuda", dtype=torch.bfloat16):
                    logits = model(x[:, :-1], **kw).logits.float()
                tgt = x[0, 1:].clone(); tgt[:len(pre) - 1] = -100        # score only the passage
                nll += F.cross_entropy(logits[0], tgt, reduction="sum", ignore_index=-100).item(); n += int((tgt != -100).sum())
        out[mode] = math.exp(nll / n)
    return out


CHAT = ["Write a two-line poem about rain.", "What's a good way to start learning guitar?", "Explain what a black hole is in two sentences.",
        "Give me three dinner ideas with chicken.", "How do I politely decline a meeting invite?", "hey whats up lol",
        "Why is the sky blue?", "Tell me a short joke about computers.", "Summarize in one sentence: The cat sat on the warm mat all afternoon because the sun was shining on it.",
        "What should I pack for a weekend camping trip?", "Translate 'good morning, how are you?' into Spanish.", "Is it better to rent or buy a house? Keep it short."]


def chat_check(model, n):
    ps = CHAT[:n]
    rows = []
    for tools in (False, True):
        for p, a in zip(ps, generate(model, [plain_prompt(p, tools) for p in ps], max_new=200)):
            w = a.split()
            grams = collections.Counter(tuple(w[i:i + 4]) for i in range(len(w) - 3))
            rows.append({"prompt": p, "tools_offered": tools, "reply": a, "tool_call": "<|tool_call_start|>" in a,
                         "answer_line": bool(re.search(r"answer\s*:", a, re.I)), "needs_list": bool(re.search(r"^\s*(needs|plan)\s*:", a, re.I | re.M)),
                         "repeats": bool(grams) and grams.most_common(1)[0][1] >= 3})
    return rows


# ---------------------------------------------------------------- training data
def replay_examples(base, n):
    prompts = []
    try:
        from datasets import load_dataset
        ds = load_dataset("yahma/alpaca-cleaned", split="train")
        r = random.Random(4)
        cand = [x["instruction"] for x in ds if not x["input"] and 10 < len(x["instruction"]) < 200]
        prompts = r.sample(cand, min(n, len(cand)))
    except Exception as e:
        log("alpaca prompts unavailable, using the chat list:", repr(e)[:200])
    while len(prompts) < n:
        prompts += CHAT
    prompts = prompts[:n]
    r = random.Random(5)
    with_tools = [r.random() < 0.5 for _ in prompts]
    answers = generate(base, [plain_prompt(p, t) for p, t in zip(prompts, with_tools)], max_new=256, bs=64)
    ex = []
    for p, t, a in zip(prompts, with_tools, answers):
        if "<|tool_call_start|>" in a or len(a.split()) < 3:
            continue
        head = plain_prompt(p, t)
        ex.append(encode([(head, False), (a.strip() + "<|im_end|>", True), ("\n", False)]))
    return ex


def gold_examples(n):
    r = random.Random(11)
    out = []
    for t in make_set(1, n, TRAIN_TASKS):
        msgs, _ = gold_episode(t, r)
        out.append(encode(render_lfm(msgs, user=t["request"])))
    return out


def teacher_examples(path, n):
    recs = [json.loads(l) for f in path.split(",") for l in open(f)]
    kept = [x for x in recs if x["kept"]]
    log(f"teacher file: {len(recs)} episodes, {len(kept)} kept; using {min(n, len(kept))}")
    random.Random(12).shuffle(kept)
    return [encode(render_lfm(x["messages"], user=x["request"])) for x in kept[:n]]


def micro_batches(batch, micro=8, budget=2048):
    """Split a batch into pieces of at most `micro` examples whose padded size stays under `budget` tokens.
    Same gradient as one big batch (the loss is normalised over the whole batch); only the peak memory changes.
    The logits over the ~65k-word vocabulary are what overflow a 22 GB card when examples are long."""
    out, cur = [], []
    for ex in sorted(batch, key=lambda e: len(e[0])):
        if cur and (len(cur) + 1 > micro or (len(cur) + 1) * len(ex[0]) > budget):
            out.append(cur); cur = []
        cur.append(ex)
    if cur:
        out.append(cur)
    return out


def train(model, examples, epochs, lr, bs=16, micro=8):
    random.Random(0).shuffle(examples)
    steps = max(1, int(len(examples) * epochs / bs))
    opt = torch.optim.AdamW(model.parameters(), lr=lr, betas=(0.9, 0.95), weight_decay=0.01)
    warm = max(1, steps // 20)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1, (s + 1) / warm) * (0.1 + 0.9 * 0.5 * (1 + math.cos(math.pi * min(1, s / steps)))))
    model.train()
    order = []
    while len(order) < steps * bs:
        o = list(range(len(examples))); random.Random(len(order)).shuffle(o); order += o
    losses = []
    for s in range(steps):
        opt.zero_grad(set_to_none=True)
        batch = [examples[i] for i in order[s * bs:(s + 1) * bs]]
        ntok = sum(sum(1 for l in lab if l != -100) for _, lab in batch)
        tot = 0.0
        for mb in micro_batches(batch, micro):
            L = max(len(x) for x, _ in mb)
            ids = torch.tensor([x + [PAD] * (L - len(x)) for x, _ in mb], device=DEV)
            lab = torch.tensor([y + [-100] * (L - len(y)) for _, y in mb], device=DEV)
            att = torch.tensor([[1] * len(x) + [0] * (L - len(x)) for x, _ in mb], device=DEV)
            with torch.autocast("cuda", dtype=torch.bfloat16):
                logits = model(input_ids=ids, attention_mask=att).logits
            loss = F.cross_entropy(logits[:, :-1].float().reshape(-1, logits.shape[-1]), lab[:, 1:].reshape(-1), ignore_index=-100, reduction="sum") / max(1, ntok)
            loss.backward(); tot += loss.item()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step(); sched.step(); losses.append(tot)
        if s % 20 == 0 or s == steps - 1:
            log(f"step {s + 1}/{steps} loss {sum(losses[-20:]) / len(losses[-20:]):.3f} lr {sched.get_last_lr()[0]:.2e}")
    model.eval()
    return losses


# ---------------------------------------------------------------- export
def export(model, name):
    """Best effort: a Q8_0 GGUF plus Modelfile, uploaded to a private model repo (too big for the git repo)."""
    import subprocess, urllib.request, zipfile
    from huggingface_hub import HfApi
    d = f"/tmp/{name}"
    model.to(torch.bfloat16).save_pretrained(d); tok.save_pretrained(d)
    if not os.path.exists("/tmp/llama.cpp-master"):
        urllib.request.urlretrieve("https://github.com/ggml-org/llama.cpp/archive/refs/heads/master.zip", "/tmp/lc.zip")
        zipfile.ZipFile("/tmp/lc.zip").extractall("/tmp")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "/tmp/llama.cpp-master/gguf-py"], check=True)
    r = subprocess.run([sys.executable, "/tmp/llama.cpp-master/convert_hf_to_gguf.py", d, "--outtype", "q8_0", "--outfile", f"/tmp/{name}.gguf"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-1500:])
    api = HfApi(token=os.environ["HF_TOKEN"])
    repo = f"{api.whoami()['name']}/findout-pilot"
    api.create_repo(repo, private=True, exist_ok=True)
    api.upload_file(path_or_fileobj=f"/tmp/{name}.gguf", path_in_repo=f"{name}.gguf", repo_id=repo)
    mf = f"FROM ./{name}.gguf\nPARAMETER temperature 0\nPARAMETER num_ctx 4096\n"
    api.upload_file(path_or_fileobj=mf.encode(), path_in_repo=f"Modelfile.{name}", repo_id=repo)
    return f"https://huggingface.co/{repo}"


# ---------------------------------------------------------------- main
def main():
    arms = [a for a in A.arms.split(",") if a]
    log(f"arms {arms}, GPU {torch.cuda.get_device_name(0)}, smoke={A.smoke}")
    R = {"args": vars(A), "arms": {}}
    R["render_ok"] = check_render()
    test = []
    for fn in TRAIN_TASKS + HELD_OUT:
        test += make_set(zlib.crc32(fn.__name__.encode()) % 1000 + 300, A.per_type, [fn])
    log(f"{len(test)} test episodes ({sum(t['style'] == 'messy' for t in test)} messy)")
    r = random.Random(2)
    shots = []
    for fn in (t_total, t_compare2):
        t = make_task(random.Random(fn.__name__ + "shot"), fn, 0)
        shots.append((t["request"], gold_episode(t, r)[0]))
    ppl_tokens = 8000 if A.smoke else 120000
    base = load()
    R["eng_base"] = english(base, ppl_tokens)
    R["ppl_base"] = R["eng_base"]["as_reply"]
    log(f"base English perplexity {R['eng_base']}")
    replay = None
    for arm in arms:
        t_arm = time.time()
        if arm == "untouched":
            m = base
        else:
            if replay is None:
                replay = replay_examples(base, max(8, A.n_train // 4))
                log(f"{len(replay)} replay examples from the base model")
            ex = gold_examples(A.n_train) if arm == "gold" else teacher_examples(A.teacher, A.n_train)
            ntrain = len(ex)
            m = load()
            losses = train(m, ex + replay, A.epochs, A.lr)
        rows = run_eval(m, test, shots=shots if arm == "untouched" else ())
        eng = R["eng_base"] if arm == "untouched" else english(m, ppl_tokens)
        res = {"summary": summarise(rows), "eng": eng, "ppl": eng["as_reply"],
               "chat": chat_check(m, 3 if A.smoke else len(CHAT)), "minutes": (time.time() - t_arm) / 60}
        if arm != "untouched":
            res["n_train"], res["final_loss"] = ntrain, sum(losses[-10:]) / len(losses[-10:])
        ex_by = collections.defaultdict(list)
        for sc, s in rows:
            ex_by[(sc["type"], sc["ok"])].append(transcript(s))
        res["examples"] = {f"{ty} {'right' if ok else 'wrong'}": v[:2] for (ty, ok), v in ex_by.items()}
        R["arms"][arm] = res
        log(f"{arm}: " + ", ".join(f"{ty} {v['ok']:.0%}" for ty, v in sorted(res["summary"].items())) + f"; ppl {res['ppl']:.2f}")
        json.dump(R, open(f"{OUT}/results.json", "w"), indent=1)
        if A.export and arm != "untouched":
            try:
                res["export"] = export(m, f"findout-pilot-{arm}")
                log("exported:", res["export"])
            except Exception as e:
                log("export failed:", repr(e)[-800:])
        if m is not base:
            del m; torch.cuda.empty_cache()
    json.dump(R, open(f"{OUT}/results.json", "w"), indent=1)
    open(f"{OUT}/PILOT_RESULTS.md", "w").write(report(R))
    log("done")


def pct(x):
    return "–" if x != x else f"{x:.0%}"


def report(R):
    arms = list(R["arms"])
    trained = sorted({t for a in arms for t in R["arms"][a]["summary"] if not t.startswith("H:")})
    held = sorted({t for a in arms for t in R["arms"][a]["summary"] if t.startswith("H:")})
    L = ["# Findout pilot", "", f"LFM2.5-350M. Arms: {', '.join(arms)}. Renderer matches the chat template: {R['render_ok']}.", "",
         "## Success by task type", "", "Strict = right answer and every needed step done (searched each fact, used the calculator, asked when needed). Right answer alone can be luck on which-questions. Brackets: right answer on clean / messy requests.", "", "| type | " + " | ".join(arms) + " |", "| --- |" + " --- |" * len(arms)]
    for ty in trained + held:
        cells = []
        for a in arms:
            v = R["arms"][a]["summary"].get(ty)
            cells.append(f"**{pct(v['strict'])}** strict, {pct(v['ok'])} right answer ({pct(v['ok_clean'])} / {pct(v['ok_messy'])})" if v else "")
        L.append(f"| {ty} | " + " | ".join(cells) + " |")
    def mean(a, tys, k="ok"):
        xs = [R["arms"][a]["summary"][t][k] for t in tys if t in R["arms"][a]["summary"]]
        xs = [x for x in xs if x == x]
        return sum(xs) / len(xs) if xs else float("nan")
    L += ["| **trained types, mean (strict)** | " + " | ".join(pct(mean(a, trained, "strict")) for a in arms) + " |",
          "| **held-out, mean (strict)** | " + " | ".join(pct(mean(a, held, "strict")) for a in arms) + " |",
          "| held-out, mean (right answer) | " + " | ".join(pct(mean(a, held)) for a in arms) + " |", "",
          "## Habits", "", "| | " + " | ".join(arms) + " |", "| --- |" + " --- |" * len(arms)]
    for k, label in (("coverage", "searched every needed thing (held-out)"), ("needs_list", "needs list first (held-out)"),
                     ("calc_when_needed", "calculator when arithmetic was needed (held-out)"), ("answer_line", "ended with an Answer: line (held-out)")):
        L.append(f"| {label} | " + " | ".join(pct(mean(a, held, k)) for a in arms) + " |")
    for k, label, tys in (("asked_when_needed", "asked when only the person knew (trained)", ["ask"]),
                          ("asked_when_not", "asked when it didn't need to (trained, lower is better)", [t for t in trained if t != "ask"]),
                          ("searched_given", "searched for what the message gave (lower is better)", ["given"])):
        L.append(f"| {label} | " + " | ".join(pct(mean(a, tys, k)) for a in arms) + " |")
    L += ["", "## English and plain chat", "", "| | " + " | ".join(arms) + " |", "| --- |" + " --- |" * len(arms),
          "| WikiText-2 perplexity, as an assistant reply | " + " | ".join(f"{R['arms'][a]['eng']['as_reply']:.2f}" for a in arms) + " |",
          "| WikiText-2 perplexity, raw text, masked | " + " | ".join(f"{R['arms'][a]['eng']['raw_masked']:.2f}" for a in arms) + " |",
          "| WikiText-2 perplexity, raw text (first method) | " + " | ".join(f"{R['arms'][a]['eng']['raw']:.2f}" for a in arms) + " |"]
    for k, label in (("tool_call", "plain chat replies with a tool call"), ("answer_line", "plain chat replies with an Answer: line"),
                     ("repeats", "plain chat replies that loop")):
        L.append(f"| {label} | " + " | ".join(f"{sum(c[k] for c in R['arms'][a]['chat'])}/{len(R['arms'][a]['chat'])}" for a in arms) + " |")
    L += ["", "## Verdict", ""]
    for a in [x for x in arms if x != "untouched"]:
        h = mean(a, held, "strict"); worst = min((R["arms"][a]["summary"][t]["strict"] for t in held), default=float("nan"))
        ppl_up = R["arms"][a]["ppl"] / R["ppl_base"] - 1
        chat_bad = sum(c["tool_call"] or c["repeats"] for c in R["arms"][a]["chat"] if not c["tools_offered"])
        gap = mean(a, trained, "ok_clean") - mean(a, trained, "ok_messy")
        checks = [(h >= 0.5 and worst >= 0.2, f"held-out strict mean {pct(h)} (need 50%), worst held-out type {pct(worst)} (need 20%)"),
                  (ppl_up <= 0.15, f"English perplexity as an assistant reply {ppl_up:+.0%} (need at most +15%)"),
                  (chat_bad <= 1, f"{chat_bad} broken plain-chat replies without tools (need at most 1)"),
                  (gap <= 0.10, f"clean minus messy on trained types {gap * 100:+.0f} points (need at most 10)")]
        L.append(f"**{a}:** " + ("GO" if all(c for c, _ in checks) else "NOT YET"))
        L += [f"- {'pass' if c else 'fail'}: {s}" for c, s in checks] + [""]
    L += ["## Plain chat replies", ""]
    for a in arms:
        L.append(f"**{a}**"); L.append("")
        for c in R["arms"][a]["chat"]:
            L.append(f"- ({'tools offered' if c['tools_offered'] else 'no tools'}) *{c['prompt']}* → {c['reply'][:300]!r}")
        L.append("")
    L += ["## Example episodes", ""]
    for a in arms:
        for k, v in sorted(R["arms"][a]["examples"].items()):
            if k.startswith("H:") or k.endswith("wrong"):
                L += [f"**{a}, {k}**", "```", v[0][:2500], "```", ""]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
