"""Self-test: every episode renders and parses with Squiggle's own functions.

  python selftest.py samples/samples.jsonl                 # episode results (samples, teacher_results with calls)
  python selftest.py out/train_examples.jsonl.gz --tokenizers unsloth/gemma-3-270m-it,LiquidAI/LFM2.5-350M

For every model call it checks, with the app's code (sq/format.mjs -> engine-wllama.js, agent.js):
  - the prompt is what gemmaMessages produces (folding it again changes nothing), starts with LITE_SYSTEM, and its
    turns go system, user, then alternate, ending on a user turn
  - the output parses: thinking opens and closes, at most one tool call, valid JSON, a tool Squiggle has; a final
    reply has no tool call; nothing loops (isLooping)
  - the Python checker's parser (families.parse_out) reads the same call the app reads
With --tokenizers, it also renders each example with each chat template and checks the prompt is a prefix of
prompt+output (so the loss mask is exact), the prompt fits the phone's 4096 tokens and the output 1024.
For episode results it re-runs the family checker and reports kept / not kept.
"""
import argparse, collections, gzip, json, os, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import families as F
from sqrun import AppFormat

TOOLS = {"plan", "done", "need", "find", "find_tools", "list_files", "read_file", "grep", "note", "write_file", "delete_file",
         "github_list_repos", "git_clone", "git_status", "git_branch", "git_commit", "git_push", "git_pull", "git_log",
         "github_open_pr", "fetch_url", "web_search", "remember", "recall", "forget", "search_history", "run_js"}


def read(path):
    op = gzip.open if str(path).endswith(".gz") else open
    with op(path, "rt") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def as_calls(rec):
    """(episode id, family, kind, messages, output) from an episode result or a training example."""
    if "messages" in rec and "output" in rec:
        yield rec.get("episode"), rec.get("family"), rec.get("kind"), rec["messages"], rec["output"]
        return
    for c in rec.get("calls", []):
        if c.get("kind") in ("chat", "step", "final") and c.get("output") is not None and not c.get("error"):
            yield rec.get("id"), rec.get("family"), c["kind"], c["messages"], c["output"]


def check_call(app, system, kind, messages, output):
    p = []
    if not messages or messages[0]["role"] != "system" or not messages[0]["content"].startswith(system):
        p.append("prompt doesn't start with LITE_SYSTEM")
    roles = [m["role"] for m in messages[1:]]
    if not roles or roles[0] != "user" or roles[-1] != "user" or any(a == b for a, b in zip(roles, roles[1:])):
        p.append(f"turn order {roles}")
    again = app("messages", messages=messages)
    if again != messages:
        p.append("gemmaMessages changes the prompt")
    a = app("parse", text=output)
    if not output.lstrip().startswith("<think>"):
        p.append("no thinking")
    if a["open"]:
        p.append("thinking never closes")
    if not a["thinking"].strip():
        p.append("empty thinking")
    if len(a["calls"]) > 1:
        p.append("several tool calls")
    for c in a["calls"]:
        if c["name"] not in TOOLS:
            p.append(f"unknown tool {c['name']}")
    if "```tool" in a["text"] and not a["calls"]:
        p.append("unparseable tool call")
    if kind == "final" and a["calls"]:
        p.append("tool call in a final reply")
    if not a["calls"] and not a["text"].strip():
        p.append("no call and no reply")
    if a["looping"]:
        p.append("loops")
    py = F.parse_out(output)
    if [(c["name"], c["arguments"]) for c in py["calls"][:1]] != [(c["name"], c["arguments"]) for c in a["calls"][:1]]:
        p.append("python parser disagrees with the app")
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--tokenizers", default="")
    ap.add_argument("--squiggle", default=os.environ.get("SQUIGGLE_DIR", str(HERE / "squiggle")))
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    app = AppFormat(args.squiggle)
    system = app("system")
    toks = []
    for name in [t for t in args.tokenizers.split(",") if t]:
        from transformers import AutoTokenizer
        toks.append((name, AutoTokenizer.from_pretrained(name)))
    n = bad = 0
    why = collections.Counter()
    lengths = collections.defaultdict(list)
    episodes = kept = 0
    for path in args.files:
        for rec in read(path):
            if "calls" in rec and "family" in rec and "turns" in rec:
                episodes += 1
                c = F.check(rec)
                kept += c["strict"]
                if not c["strict"]:
                    print(f"  episode {rec['id']}: not kept ({'; '.join(c['reasons'])[:200]})")
            for eid, fam, kind, msgs, out in as_calls(rec):
                n += 1
                p = check_call(app, system, kind, msgs, out)
                for name, tok in toks:
                    prompt = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
                    full = tok.apply_chat_template(msgs + [{"role": "assistant", "content": out}], tokenize=False)
                    if not full.startswith(prompt):
                        p.append(f"{name}: prompt is not a prefix of prompt+output")
                    pl = len(tok(prompt, add_special_tokens=False).input_ids)
                    ol = len(tok(full[len(prompt):], add_special_tokens=False).input_ids)
                    lengths[name].append((pl, ol))
                    if pl > 4096:
                        p.append(f"{name}: prompt {pl} tokens > 4096")
                    if ol > 1024:
                        p.append(f"{name}: output {ol} tokens > 1024")
                if p:
                    bad += 1
                    for x in p:
                        why[x] += 1
                    if bad <= 15:
                        print(f"  {eid} ({fam}, {kind}): {'; '.join(p)}")
                if args.limit and n >= args.limit:
                    break
    app.close()
    print(f"\n{n} model calls checked, {bad} with problems." + (f" {episodes} episodes, {kept} pass their checker." if episodes else ""))
    for k, v in why.most_common():
        print(f"  {v} × {k}")
    for name, ls in lengths.items():
        ps = sorted(x for x, _ in ls)
        os_ = sorted(y for _, y in ls)
        print(f"  {name}: prompt tokens median {ps[len(ps) // 2]}, max {ps[-1]}; output tokens median {os_[len(os_) // 2]}, max {os_[-1]}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
