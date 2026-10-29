"""Tiny Gemma 4: on-policy healing data. Gemma 4 E2B-it answers questions itself; the heal then distills on
those conversations, so the student learns what E2B actually does (its tool calls, its thinking, how it stops).

Questions only (never the datasets' own answers):
  - NousResearch/hermes-function-calling-v1 (Apache-2.0): the tools + the user's first request, rendered with
    Gemma's native tool declarations. E2B decides whether and how to call a tool. Single step only (the dataset's
    later tool results were written for someone else's calls).
  - HuggingFaceTB/smoltalk (Apache-2.0) problem-solving sources: numina-cot (maths), metamathqa, self-oss-instruct
    (code), smol-magpie-ultra (general): the first user turn.
Every word of every answer is Gemma's (Apache-2.0). Thinking is on for a share of prompts (THINK_SHARE).

    python gen.py OUT_DIR        env: MODEL, N_SMOL, MAX_TOKENS, THINK_SHARE, MINUTES
Writes OUT_DIR/gen.jsonl.gz: {"source", "thinking", "text"} where text is the full conversation in Gemma's
chat format (tools, user turn, E2B's answer, end of turn), without the leading <bos>.
"""
import gzip, json, os, random, sys, time

OUT = sys.argv[1] if len(sys.argv) > 1 else "out"
os.makedirs(OUT, exist_ok=True)
MODEL = os.environ.get("MODEL", "google/gemma-4-E2B-it")
N_SMOL = json.loads(os.environ.get("N_SMOL", '{"numina-cot-100k": 2500, "metamathqa-50k": 1500, "self-oss-instruct": 2000, "smol-magpie-ultra": 1500}'))
MAX_TOKENS = int(os.environ.get("MAX_TOKENS", 1024))
THINK_SHARE = float(os.environ.get("THINK_SHARE", 0.35))
MINUTES = float(os.environ.get("MINUTES", 25))
T0 = time.time()


def log(*a):
    print(f"[{(time.time() - T0) / 60:5.1f} min]", *a, flush=True)


def prompts(tok):
    from datasets import load_dataset
    rng = random.Random(0)
    out, seen = [], set()
    for cfg in ("func_calling_singleturn", "glaive_func_calling"):
        for r in load_dataset("NousResearch/hermes-function-calling-v1", cfg, split="train"):
            user = next((m["value"] for m in r["conversations"] if m["from"] == "human"), None)
            if not user or user in seen:
                continue
            seen.add(user)
            try:
                tools = json.loads(r["tools"]) if isinstance(r["tools"], str) else r["tools"]
            except Exception:
                continue
            out.append({"source": "hermes", "messages": [{"role": "user", "content": user}], "tools": tools or None})
    need = dict(N_SMOL)
    for r in load_dataset("HuggingFaceTB/smoltalk", "all", split="train", streaming=True).shuffle(seed=0, buffer_size=5000):
        src = r.get("source")
        if need.get(src, 0) <= 0:
            if not any(v > 0 for v in need.values()):
                break
            continue
        user = next((m["content"] for m in r["messages"] if m.get("role") == "user"), None)
        if not user or len(user) > 4000:
            continue
        need[src] -= 1
        out.append({"source": src, "messages": [{"role": "user", "content": user}], "tools": None})
    rng.shuffle(out)
    for p in out:
        p["thinking"] = rng.random() < THINK_SHARE
    log(f"{len(out)} prompts", {s: sum(1 for p in out if p['source'] == s) for s in {p['source'] for p in out}})
    return out


def main():
    from transformers import AutoTokenizer
    from vllm import LLM, SamplingParams
    tok = AutoTokenizer.from_pretrained(MODEL)
    ps = prompts(tok)
    texts, keep = [], []
    for p in ps:
        kw = {"tools": p["tools"]} if p["tools"] else {}
        t = tok.apply_chat_template(p["messages"], tokenize=False, add_generation_prompt=True, enable_thinking=p["thinking"], **kw)
        if len(tok(t)["input_ids"]) <= 3000:                    # leaves room for the answer
            texts.append(t); keep.append(p)
    ps = keep
    log(f"{len(ps)} prompts after the length filter")
    llm = LLM(model=MODEL, max_model_len=MAX_TOKENS + 3072, gpu_memory_utilization=0.9,
              limit_mm_per_prompt={"image": 0, "audio": 0, "video": 0})
    sp = SamplingParams(temperature=1.0, top_p=0.95, top_k=64, max_tokens=MAX_TOKENS, skip_special_tokens=False)
    path = os.path.join(OUT, "gen.jsonl.gz")
    kept = cut_off = 0
    with gzip.open(path, "wt") as f:
        for i in range(0, len(texts), 1500):
            if time.time() - T0 > MINUTES * 60:
                log("time budget reached"); break
            outs = llm.generate(texts[i:i + 1500], sp)
            for p, t, o in zip(ps[i:i + 1500], texts[i:i + 1500], outs):
                c = o.outputs[0]
                if c.finish_reason != "stop":
                    cut_off += 1; continue
                full = (t + c.text + "<turn|>\n").removeprefix(tok.bos_token)
                f.write(json.dumps({"source": p["source"], "thinking": p["thinking"], "text": full}) + "\n")
                kept += 1
            f.flush()
            log(f"{i + len(outs)} done, kept {kept}, cut off at {MAX_TOKENS} tokens {cut_off}")
    json.dump({"kept": kept, "cut_off": cut_off, "prompts": len(ps)}, open(os.path.join(OUT, "gen_summary.json"), "w"))
    log("done", kept)


if __name__ == "__main__":
    code = 0
    try:
        main()
    except BaseException:
        import traceback
        traceback.print_exc(); code = 1
    sys.stdout.flush(); sys.stderr.flush()
    os._exit(code)
