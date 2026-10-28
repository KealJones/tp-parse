"""Run the prompt set through Gemma 4 with thinking on and save the raw output.

    python run_traces.py --models google/gemma-4-E4B-it,google/gemma-4-E2B-it --runs 3 --out out
    python run_traces.py --dry          # render the prompts with the real chat template, no model

Loading and sampling follow the Gemma 4 model card (AutoModelForMultimodalLM, bf16,
enable_thinking=True, temperature 1.0, top_p 0.95, top_k 64). Generation is batched with
left padding; each batch is one run over every prompt (or several runs when --bs is larger).
Prompts marked needs_image are skipped (they need photos).

Each model writes out/traces_<model>.jsonl after every batch, one line per sample:
raw decoded text (with <|channel>thought ... <channel|>), the thinking and answer split out,
token counts (thought, answer, total) and whether the sample ended on its own or hit the cap.
out/run_info.json has timings, throughput and versions.
"""
import argparse
import json
import os
import re
import sys
import time

# Squiggle's real agent tools: names, arguments (? = optional) and the first sentence of each
# description, from squiggle app/src/tools.js (2026-10-28). The harness's own plan/done/need/find
# are left out so they don't steer the planning this experiment looks at.
TOOLS = """\
- list_files(path?): List files in the workspace.
- read_file(path, start_line?, end_line?): Read lines of a text file from the workspace, with line numbers.
- grep(pattern, path?, ignore_case?, skip?): Search files for a word or regular expression.
- note(action, id?, text?): Your notepad for this chat.
- write_file(path, content): Create or overwrite a text file in the workspace.
- delete_file(path): Delete a file (or folder) in the workspace.
- github_list_repos(): List the GitHub repos the user has given Squiggle access to.
- git_clone(repo, branch?): Clone a GitHub repo into /repos/<name>.
- git_status(repo): Show the current branch and changed files of a cloned repo.
- git_branch(repo, name, from?): Switch to a branch, or start a new one.
- git_commit(repo, message): Commit all changes in a repo on the current branch.
- git_push(repo): Push the current branch to GitHub (never forced).
- git_pull(repo): Fetch and fast-forward the current branch from GitHub.
- git_log(repo, count?): Recent commits on the current branch.
- github_open_pr(repo, title, body?, base?): Open a pull request from the current (pushed) branch.
- fetch_url(url): Read a web page by its full URL.
- web_search(query, count?): Search the web (DuckDuckGo).
- remember(subject, relation, object, note?): Save a lasting fact about the user or their projects (preferences, decisions, names, how things work).
- recall(query): Search saved memory facts.
- forget(id): Delete a saved memory fact by id (when the user says it is wrong or outdated).
- search_history(query): Search the user's past conversations (all sessions) for something discussed before.
- run_js(code): Run JavaScript in an isolated sandbox (no access to the user's data or files)."""

SYSTEM = (
    "You are a helpful assistant. You can use these tools:\n" + TOOLS + "\n"
    "If a tool would help, say which tool you would call and with what arguments."
)

THOUGHT = re.compile(r"<\|channel>thought\s*(.*?)(?:<channel\|>|$)", re.DOTALL)
T0 = time.time()


def log(*a):
    print(f"[{(time.time() - T0) / 60:5.1f} min] " + " ".join(str(x) for x in a), flush=True)


def load_prompts(path):
    rows = [json.loads(line) for line in open(path) if line.strip()]
    skipped = [r["id"] for r in rows if r.get("needs_image")]
    if skipped:
        log(f"skipping prompts that need an image: {skipped}")
    return [r for r in rows if not r.get("needs_image")]


def render(tok, rows, runs):
    """One item per (run, prompt), run-major, so each batch of len(rows) is one full run."""
    items = []
    for run in range(runs):
        for r in rows:
            messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": r["prompt"]}]
            text = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=True)
            items.append({"row": r, "run": run, "text": text})
    return items


def split_output(ids, tok, stop_ids):
    """Generated ids (left-padded batch, so they start right after the prompt) -> record fields."""
    ids = list(ids)
    end = next((i for i, t in enumerate(ids) if t in stop_ids), None)
    finished = end is not None
    ids = ids[: end + 1] if finished else [t for t in ids if t != tok.pad_token_id]
    raw = tok.decode(ids, skip_special_tokens=False)
    open_id, close_id = tok.convert_tokens_to_ids("<|channel>"), tok.convert_tokens_to_ids("<channel|>")
    o = ids.index(open_id) if open_id in ids else None
    c = ids.index(close_id) if close_id in ids else None
    gen = len(ids) - (1 if finished else 0)
    if o is None:
        thought_tokens, answer_tokens = 0, gen
    elif c is None:
        thought_tokens, answer_tokens = gen - o - 1, 0
    else:
        thought_tokens, answer_tokens = c - o - 1, gen - c - 1
    m = THOUGHT.search(raw)
    thinking = m.group(1).strip() if m else ""
    answer = raw.split("<channel|>", 1)[1] if "<channel|>" in raw else ("" if o is not None else raw)
    for t in ("<turn|>", "<eos>", "<pad>"):
        answer = answer.replace(t, "")
    return {"raw": raw, "thinking": thinking, "answer": answer.strip(), "gen_tokens": gen,
            "thought_tokens": thought_tokens, "answer_tokens": answer_tokens, "finished": finished,
            "thought_closed": c is not None}


def generate(model, tok, texts, max_new, stop_ids):
    """One padded batch. On CUDA OOM, split it in half and try again."""
    import torch
    try:
        enc = tok(texts, return_tensors="pt", padding=True, add_special_tokens=False).to(model.device)
        with torch.no_grad():
            out = model.generate(**enc, max_new_tokens=max_new, do_sample=True, temperature=1.0, top_p=0.95, top_k=64,
                                 eos_token_id=sorted(stop_ids), pad_token_id=tok.pad_token_id)
        return [row.tolist() for row in out[:, enc["input_ids"].shape[1]:]]
    except torch.cuda.OutOfMemoryError:
        if len(texts) == 1:
            raise
        torch.cuda.empty_cache()
        log(f"out of memory at batch {len(texts)}; splitting")
        h = len(texts) // 2
        return generate(model, tok, texts[:h], max_new, stop_ids) + generate(model, tok, texts[h:], max_new, stop_ids)


def run_model(name, rows, args, info):
    from transformers import AutoTokenizer
    short = name.split("/")[-1]
    tok = AutoTokenizer.from_pretrained(name)
    tok.padding_side = "left"
    items = render(tok, rows, args.runs)
    lens = [len(tok(i["text"], add_special_tokens=False)["input_ids"]) for i in items[: len(rows)]]
    log(f"{short}: {len(items)} samples, prompt tokens {min(lens)}-{max(lens)}; example prompt:\n{items[0]['text']}")
    stop_ids = {i for i in (tok.convert_tokens_to_ids(t) for t in ("<eos>", "<turn|>")) if isinstance(i, int) and i >= 0}
    mi = {"model": name, "samples": 0, "batches": []}
    info["models"].append(mi)
    if args.dry:
        return
    import torch
    from transformers import AutoModelForMultimodalLM
    torch.manual_seed(args.seed)
    t = time.time()
    model = AutoModelForMultimodalLM.from_pretrained(name, dtype=torch.bfloat16, device_map="cuda").eval()
    mi["load_s"] = round(time.time() - t)
    log(f"{short}: loaded in {mi['load_s']} s, {torch.cuda.memory_allocated() / 1e9:.1f} GB on the GPU")
    bs = args.bs.get(short, args.bs.get("*", 38))
    path = os.path.join(args.out, f"traces_{short}.jsonl")
    with open(path, "w") as f:
        for k in range(0, len(items), bs):
            if (time.time() - T0) / 60 > args.stop_after:
                log(f"{short}: past {args.stop_after} min, stopping before batch {k // bs + 1}")
                mi["stopped_early"] = True
                break
            chunk = items[k:k + bs]
            torch.cuda.reset_peak_memory_stats()
            t = time.time()
            outs = generate(model, tok, [i["text"] for i in chunk], args.max_new_tokens, stop_ids)
            secs = time.time() - t
            recs = []
            for item, ids in zip(chunk, outs):
                r = item["row"]
                rec = {"id": r["id"], "category": r["category"], "prompt": r["prompt"], "look_for": r.get("look_for"),
                       "run": item["run"], "model": name, **split_output(ids, tok, stop_ids)}
                recs.append(rec)
                f.write(json.dumps(rec) + "\n")
            f.flush()
            steps = max(len(o) for o in outs)
            b = {"size": len(chunk), "seconds": round(secs, 1), "steps": steps, "ms_per_step": round(1000 * secs / max(1, steps), 1),
                 "tokens": sum(x["gen_tokens"] for x in recs), "capped": sum(not x["finished"] for x in recs),
                 "peak_gb": round(torch.cuda.max_memory_allocated() / 1e9, 1)}
            mi["batches"].append(b)
            mi["samples"] += len(recs)
            log(f"{short}: batch {k // bs + 1} {b}")
            json.dump(info, open(os.path.join(args.out, "run_info.json"), "w"), indent=1)
    del model
    import gc
    gc.collect()
    torch.cuda.empty_cache()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="google/gemma-4-E4B-it")
    ap.add_argument("--prompts", default="prompts.jsonl")
    ap.add_argument("--out", default="out")
    ap.add_argument("--runs", type=int, default=3, help="samples per prompt")
    ap.add_argument("--max-new-tokens", type=int, default=6144)
    ap.add_argument("--bs", default="gemma-4-E4B-it=38,gemma-4-E2B-it=114",
                    help="batch size per model short name, '*' for the rest")
    ap.add_argument("--skip-after", type=float, default=40, help="don't start another model after this many minutes")
    ap.add_argument("--stop-after", type=float, default=70, help="don't start another batch after this many minutes")
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--dry", action="store_true", help="render prompts only, no model")
    args = ap.parse_args()
    args.bs = {k: int(v) for k, v in (p.split("=") for p in args.bs.split(","))}
    os.makedirs(args.out, exist_ok=True)
    rows = load_prompts(args.prompts)
    info = {"system": SYSTEM, "runs": args.runs, "max_new_tokens": args.max_new_tokens, "prompts": len(rows),
            "sampling": {"temperature": 1.0, "top_p": 0.95, "top_k": 64}, "models": []}
    try:
        import torch, transformers
        info.update(torch=torch.__version__, transformers=transformers.__version__,
                    gpu=torch.cuda.get_device_name(0) if torch.cuda.is_available() else None)
    except Exception as e:
        info["versions_error"] = repr(e)
    for i, name in enumerate(args.models.split(",")):
        if i and (time.time() - T0) / 60 > args.skip_after:
            log(f"skipping {name}: past {args.skip_after} min")
            info["models"].append({"model": name, "skipped": True})
            continue
        run_model(name, rows, args, info)
        json.dump(info, open(os.path.join(args.out, "run_info.json"), "w"), indent=1)
    info["total_min"] = round((time.time() - T0) / 60, 1)
    json.dump(info, open(os.path.join(args.out, "run_info.json"), "w"), indent=1)
    log("done")


if __name__ == "__main__":
    main()
