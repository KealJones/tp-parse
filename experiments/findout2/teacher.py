# %% [markdown]
# # Findout pilot: teacher traces
#
# A 4B teacher (Qwen3-4B-Instruct-2507) works through world-v2 tasks with the real harness (search, calculator,
# ask the person). It never sees the answer key. Only episodes it gets fully right are kept: right answer, every
# needed fact actually searched, nothing searched that the message already gave, the calculator used for
# arithmetic, the person asked when only they know, a needs list first and an "Answer:" line last.
#
# Why a teacher at all: the askfirst run showed that episodes written from templates teach the model to recite.
# A teacher writes each episode in its own words.
#
# **On Kaggle**: GPU T4 x2, Internet on. Each GPU runs its own copy of the model on half the tasks.
# Output: `teacher_episodes.jsonl` (every episode, with `kept` and its score) and `TEACHER_RESULTS.md`.

# %%
import json, os, random, re, subprocess, sys, threading, time, collections
QUICK = "--quick" in sys.argv or os.environ.get("TEACHER_QUICK") == "1"
ARGS = dict(a.split("=", 1) for a in sys.argv[1:] if a.startswith("--") and "=" in a)
SHARD, NSHARD = (int(x) for x in ARGS.get("--shard", "0/1").split("/"))   # e.g. --shard=1/2 runs every second task
OUTDIR = ARGS.get("--out", ".")
import transformers
if tuple(int(x) for x in transformers.__version__.split(".")[:2]) < (4, 51):
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "transformers>=4.51,<5", "accelerate"], check=False)
    print("upgraded transformers; if imports fail, restart and rerun")
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

# (world2.py is inlined here by make_notebook.py)
from world2 import *  # noqa: E402,F401  -- replaced in the notebook

MODEL = "Qwen/Qwen3-4B-Instruct-2507"
N_TASKS = 40 if QUICK else 3000
BATCH = int(ARGS.get("--batch", 12))
MAX_TURNS = 12
TIME_LIMIT_H = float(ARGS.get("--hours", 0.4 if QUICK else 4.5))
ABORT = []
T0 = time.time()

TEACHER_SYSTEM = SYSTEM + (
    "\n\nHow to work:\n"
    "- Your first message starts with 'Needs:' and a numbered list of every piece you need, each marked (search), "
    "(calculator) or (ask them). If the message already gives a fact, list it as 'Given: ...' instead of searching for it. "
    "Then make the tool call for item 1.\n"
    "- Make exactly one tool call per message. Before each later call, say in a few words what you just learned and which item is next.\n"
    "- Search for one thing at a time, using the exact name from the request. If a person, town or item is linked to another one "
    "(for example the town someone lives in), find the link first.\n"
    "- Search results can include facts about other things; use only the ones about what you asked for.\n"
    "- Do every calculation and comparison with the calculator, even easy ones.\n"
    "- Never write 'Answer:' before you have the tool results for every item on your list.\n"
    "- When you have everything, reply in one or two plain sentences and end with a last line 'Answer: ' followed by the short answer. "
    "For 'which' questions the short answer is just the winner's name.\n\n"
    "Example first message for 'How much do 4 lanterns cost?':\nNeeds:\n1. the price of a lantern (search)\n2. 4 x that price (calculator)\n"
    "Starting with 1.\n(then the search tool call)")


def log(*a):
    print(f"[{(time.time() - T0) / 60:5.1f} min]", *a, flush=True)


def to_qwen(msgs):
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


TOOL_MARK = re.compile(r"\((search|calculator|ask them|ask)\)", re.I)


def advance(a, text, results):
    """Apply one teacher reply to an episode. Returns True if the episode goes on.
    A reply that plans tools but stops (often with a made-up answer) is cut before 'Answer:' and continued
    from its own words, so the stored message reads as one natural turn."""
    full = a.pop("prefix", "") + text
    content, calls = parse_qwen(full)
    a["turns"] += 1
    if calls and a["turns"] < MAX_TURNS:
        c = calls[0]                                 # one call per turn
        a["msgs"].append({"role": "assistant", "content": content, "tool_calls": [c]})
        a["msgs"].append({"role": "tool", "name": c["name"], "content": a["H"].run(c["name"], c["arguments"])})
        return True
    first = not any(m["role"] == "tool" for m in a["msgs"])
    head = re.split(r"answer\s*:", content, flags=re.I)[0].rstrip()
    has_answer = head != content.rstrip()
    if not calls and a.get("cont", 0) < 3 and a["turns"] < MAX_TURNS and (not has_answer or (first and TOOL_MARK.search(head))):
        a["cont"] = a.get("cont", 0) + 1
        a["prefix"] = head + ("\nStarting with 1.\n" if first and "starting with" not in head.lower()[-40:] else "\n")
        return True
    a["msgs"].append({"role": "assistant", "content": content})
    t = a["task"]
    sc = score(t, content if not calls else "", a["H"], a["msgs"][0].get("content", ""))
    errs = sum(1 for m in a["msgs"] if m["role"] == "tool" and m["content"].startswith("error"))
    kept = (sc["ok"] and sc["answer_line"] and sc["coverage"] == 1 and not sc["searched_given"] and (sc["needs_list"] or not t["needs"])
            and (sc["calc"] or not sc["needs_calc"]) and (sc["asked"] or not sc["needs_ask"]) and errs == 0
            and all(m["tool_calls"][0]["name"] in ("search", "calculator", "ask_person") for m in a["msgs"] if m.get("tool_calls")))
    results.append({"idx": a["idx"], "type": t["type"], "style": t["style"], "request": t["request"], "clean": t["clean"],
                    "messages": a["msgs"], "score": sc, "tool_errors": errs, "kept": bool(kept), "turns": a["turns"]})
    return False


DTYPE = torch.bfloat16 if torch.cuda.is_available() and torch.cuda.is_bf16_supported() else torch.float16


def load_model(gpu):
    tok = AutoTokenizer.from_pretrained(MODEL)
    tok.padding_side = "left"
    try:                                            # loaded straight onto its GPU, in the main thread (loading isn't thread-safe)
        model = AutoModelForCausalLM.from_pretrained(MODEL, dtype=DTYPE, device_map={"": gpu})
    except TypeError:
        model = AutoModelForCausalLM.from_pretrained(MODEL, torch_dtype=DTYPE, device_map={"": gpu})
    return tok, model.eval()


def worker(gpu, tok, model, tasks, results, stats):
    dev = f"cuda:{gpu}"
    eos = [tok.convert_tokens_to_ids("<|im_end|>"), tok.eos_token_id]
    queue = list(tasks)
    if gpu == 0:                                    # show one raw reply, so a broken fp16 model is obvious in the log
        p = tok.apply_chat_template([{"role": "system", "content": TEACHER_SYSTEM}, {"role": "user", "content": queue[0][1]["request"]}],
                                    tools=TOOLS, add_generation_prompt=True, tokenize=False)
        with torch.no_grad():
            o = model.generate(**tok([p], return_tensors="pt").to(dev), max_new_tokens=200, do_sample=False)
        log("sanity reply:", repr(tok.decode(o[0][len(tok(p)["input_ids"]):], skip_special_tokens=False)[:600]))
    last = t_start = time.time()
    active = []                                     # dicts: task, idx, msgs, H, turns
    gen_tokens = 0
    while queue or active:
        if len(results) >= 400 and sum(x["kept"] for x in results) < 0.05 * len(results):
            if not ABORT:
                ABORT.append(f"stopped early: only {sum(x['kept'] for x in results)} of {len(results)} episodes kept")
                log(ABORT[0])
            queue.clear()
        while queue and len(active) < BATCH and time.time() - T0 < TIME_LIMIT_H * 3600:
            idx, t = queue.pop(0)
            active.append({"task": t, "idx": idx, "msgs": [], "H": Harness(t), "turns": 0})
        if not active:
            break
        prompts = [tok.apply_chat_template([{"role": "system", "content": TEACHER_SYSTEM}, {"role": "user", "content": a["task"]["request"]}]
                                           + to_qwen(a["msgs"]), tools=TOOLS, add_generation_prompt=True, tokenize=False) + a.get("prefix", "")
                   for a in active]
        enc = tok(prompts, return_tensors="pt", padding=True).to(dev)
        with torch.no_grad():
            out = model.generate(**enc, max_new_tokens=320, do_sample=True, temperature=0.7, top_p=0.8, top_k=20,
                                 eos_token_id=eos, pad_token_id=tok.pad_token_id or eos[0])
        new = out[:, enc["input_ids"].shape[1]:]
        gen_tokens += int((new != (tok.pad_token_id or eos[0])).sum())
        still = []
        for a, ids in zip(active, new):
            if advance(a, tok.decode(ids, skip_special_tokens=False), results):
                still.append(a)
        active = still
        stats[gpu] = {"gen_tokens": gen_tokens}
        if time.time() - last > 120:
            last = time.time()
            k = sum(r["kept"] for r in results)
            log(f"gpu{gpu}: {len(results)} finished (both GPUs), {k} kept, {len(queue)} left here, ~{gen_tokens / max(1, last - t_start):.0f} new tok/s on this GPU")


def main():
    from huggingface_hub import snapshot_download
    snapshot_download(MODEL)                        # once, before the two GPU threads start
    tasks = list(enumerate(make_set(2, N_TASKS, TRAIN_TASKS)))[SHARD::NSHARD]
    os.makedirs(OUTDIR, exist_ok=True)
    ngpu = max(1, torch.cuda.device_count())
    log(f"{len(tasks)} tasks, {ngpu} GPU(s): {[torch.cuda.get_device_name(i) for i in range(ngpu)]}")
    results, stats, threads = [], {}, []
    models = [load_model(g) for g in range(ngpu)]
    log("models loaded")
    for g in range(ngpu):
        th = threading.Thread(target=worker, args=(g, *models[g], tasks[g::ngpu], results, stats))
        th.start(); threads.append(th)
    for th in threads:
        th.join()
    results.sort(key=lambda x: x["idx"])
    with open(os.path.join(OUTDIR, f"teacher_episodes{'' if NSHARD == 1 else f'_{SHARD}'}.jsonl"), "w") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    mins = (time.time() - T0) / 60
    by = collections.defaultdict(lambda: [0, 0, 0])
    for r in results:
        b = by[r["type"]]; b[0] += 1; b[1] += r["score"]["ok"]; b[2] += r["kept"]
    tok_total = sum(s["gen_tokens"] for s in stats.values())
    L = ["# Teacher traces (findout pilot)", "",
         f"{MODEL} ({str(DTYPE).split('.')[-1]}, batch {BATCH}, shard {SHARD + 1} of {NSHARD}) on {ngpu} GPU(s), {len(results)} of {len(tasks)} tasks finished in {mins:.0f} min. "
         f"Generated about {tok_total:,} tokens, {tok_total / max(1, mins * 60):.0f} tokens/s across GPUs (prompts re-read every turn).", "",
         f"Kept: **{sum(r['kept'] for r in results)}** ({sum(r['kept'] for r in results) / max(1, len(results)):.0%}). {' '.join(ABORT)}", "",
         "| type | episodes | right answer | kept |", "| --- | --- | --- | --- |"]
    for ty in sorted(by):
        n, ok, k = by[ty]
        L.append(f"| {ty} | {n} | {ok / n:.0%} | {k / n:.0%} |")
    fails = collections.Counter()
    for r in results:
        if not r["kept"]:
            s = r["score"]
            why = ("wrong answer" if not s["ok"] else "no Answer: line" if not s["answer_line"] else "missed a search" if s["coverage"] < 1
                   else "searched what was given" if s["searched_given"] else "no needs list" if not s["needs_list"]
                   else "no calculator" if s["needs_calc"] and not s["calc"] else "didn't ask" if s["needs_ask"] and not s["asked"] else "tool error")
            fails[why] += 1
    L += ["", "Why episodes were dropped: " + ", ".join(f"{k} {v}" for k, v in fails.most_common()), ""]
    for r in [x for x in results if x["kept"]][:3]:
        L += ["```", f"user: {r['request']}"]
        for m in r["messages"]:
            L.append(f"{m['role']}: {m.get('content', '')}" + (f"  -> {m['tool_calls'][0]['name']}({m['tool_calls'][0]['arguments']})" if m.get("tool_calls") else ""))
        L += ["```", ""]
    open(os.path.join(OUTDIR, f"TEACHER_RESULTS{'' if NSHARD == 1 else f'_{SHARD}'}.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


# %%
if __name__ == "__main__" or "ipykernel" in sys.modules:
    main()
