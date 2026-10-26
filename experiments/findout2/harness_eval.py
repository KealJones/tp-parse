"""Same model, two harnesses: does a smarter harness make the pair better than the model alone?

  plain harness: what multi_eval.py does (tool results passed back verbatim, first answer accepted)
  smart harness: three changes that use NO answer key, only what a real harness can see
    1. cleaner results: search output keeps only facts about what was asked, as short "- fact" lines
    2. follow-up nudge: a new name that appears in a result ("Dana lives in Ashford") is pointed out once:
       "New name: Ashford. If your question depends on it, look it up."
    3. answer gate (at most twice): an answer is sent back if the model looked nothing up, if its answer uses a
       number that never appeared in the question or any tool result, if it did fewer lookups than its own plan
       has steps (plan restated at the end of the context), or if it has no 'Answer:' line

  python harness_eval.py --models LiquidAI/LFM2.5-350M --device cpu --limit 0 --out out
"""
import argparse, json, os, re, sys, time, zlib
import world2 as w

ap = argparse.ArgumentParser()
ap.add_argument("--models", default="LiquidAI/LFM2.5-350M")
ap.add_argument("--per_type", type=int, default=24)
ap.add_argument("--take", type=int, default=0, help="use only the first N episodes of each type (0 = all)")
ap.add_argument("--max_turns", type=int, default=10)
ap.add_argument("--max_new", type=int, default=320)
ap.add_argument("--bs", type=int, default=24)
ap.add_argument("--device", default="cpu")
ap.add_argument("--harness", default="plain,smart")
ap.add_argument("--out", default="out")
A = ap.parse_args()
os.makedirs(A.out, exist_ok=True)
MINE = A
sys.argv = [sys.argv[0], "--device", A.device, "--bs", str(A.bs), "--out", A.out]   # reuse multi_eval's helpers
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "multi_eval.py")).read()
exec(src.split("# ------------------------------------------------------------------ test 1")[0])   # parse_any, chat, Runner, log
A = MINE        # multi_eval's code re-parses its own arguments; keep ours

NAME = re.compile(r"\b[A-Z][a-z]{2,}\b")


def clean_search(query, raw):
    """Keep facts whose subject is something named in the query; fall back to the raw text if that drops everything."""
    facts = [f.strip() for f in re.split(r"(?<=\.)\s+", raw) if f.strip()]
    q = query.lower()

    def subject(f):
        ws = f.split()
        return (ws[1] if ws[0] in ("A", "An", "The") and len(ws) > 1 else ws[0]).strip(".,").lower()
    keep = [f for f in facts if re.search(r"\b" + re.escape(subject(f)) + r"(s|'s)?\b", q)] or facts
    return "\n".join("- " + f for f in keep)


def plan_steps(first_text):
    """Number of numbered steps in the model's own opening plan (0 if it wrote none)."""
    return len(re.findall(r"^\s*\d+[.)]\s", first_text or "", re.M))


def run(R, tasks, smart):
    S = [{"t": t, "msgs": [{"role": "system", "content": w.SYSTEM}, {"role": "user", "content": t["request"]}],
          "H": w.Harness(t), "final": None, "first": "", "outputs": [], "raw": [], "seen": set(), "gates": 0, "nudges": 0}
         for t in tasks]
    for s in S:
        s["seen"] = {"the", "new"} | {x.strip("?.,!'").lower() for x in s["t"]["request"].split()}
    live, turn = list(range(len(S))), 0
    while live:
        turn += 1
        outs = R.generate([chat(R.tok, S[i]["msgs"], w.TOOLS) for i in live], A.max_new)
        nxt = []
        for i, text in zip(live, outs):
            s = S[i]; s["raw"].append(text)
            vis, calls = parse_any(text)
            if turn == 1:
                s["first"] = vis
            if calls and turn < A.max_turns:
                res, shown = [], []
                for c in calls:
                    r = s["H"].run(c["name"], c["arguments"])
                    res.append(r)
                    if smart and c["name"] == "search" and r != "No results.":
                        r = clean_search(str(c["arguments"].get("query", "")), r)
                        new = [n for n in dict.fromkeys(NAME.findall(r)) if n.lower() not in s["seen"]]
                        if new:
                            r += "\nNew name: " + ", ".join(new) + ". If your question depends on it, look it up."
                            s["nudges"] += 1
                    for n in NAME.findall(r) + re.findall(r"[A-Za-z]+", str(c["arguments"])):
                        s["seen"].add(n.lower())
                    shown.append(r)
                s["outputs"] += res
                s["msgs"].append({"role": "assistant", "content": vis, "tool_calls": [
                    {"id": f"c{turn}_{j}", "type": "function", "function": {"name": c["name"], "arguments": c["arguments"]}} for j, c in enumerate(calls)]})
                for j, (c, r) in enumerate(zip(calls, shown)):
                    s["msgs"].append({"role": "tool", "tool_call_id": f"c{turn}_{j}", "name": c["name"], "content": r})
                nxt.append(i)
                continue
            steps, done = plan_steps(s["first"]), len(s["H"].log)
            short_missing = not re.search(r"answer\s*:", vis, re.I)
            seen_nums = set(w.numbers_in(s["t"]["request"] + " " + " ".join(s["outputs"])))
            ans = w.short_answer(vis)[0]
            made_up = [n for n in w.numbers_in(ans) if n not in seen_nums]
            why = None
            if done == 0:
                why = "You have not looked anything up. Facts must come from search, and arithmetic from the calculator."
            elif made_up:
                why = f"Your answer uses {made_up[0]}, which no tool gave you. Look it up or calculate it."
            elif done < steps:
                why = f"Your plan has {steps} steps but you have only done {done} tool calls. Finish the plan first."
            elif short_missing:
                why = "End with a line 'Answer: <short answer>'."
            if smart and why and s["gates"] < 2 and turn < A.max_turns:
                s["gates"] += 1
                plan = f"\nYour plan was:\n{s['first'][:600]}" if steps else ""
                s["msgs"].append({"role": "assistant", "content": vis})
                s["msgs"].append({"role": "user", "content": f"Not yet. {why}{plan}"})
                nxt.append(i)
                continue
            s["final"] = vis
        live = nxt
        log(f"{R.name} {'smart' if smart else 'plain'}: turn {turn}, {len(live)} still going")
    rows = []
    for s in S:
        fs = w.fair_score(s["t"], s["final"], s["H"], s["outputs"])
        rows.append({"type": s["t"]["type"], "style": s["t"]["style"], "request": s["t"]["request"], "gold": str(s["t"]["short"]),
                     "final": s["final"], **fs, "gates": s["gates"], "nudges": s["nudges"],
                     "calls": [[n, a] for n, a in s["H"].log], "outputs": s["outputs"], "raw": s["raw"]})
    return rows


def pct(xs):
    return f"{100 * sum(xs) / max(1, len(xs)):.0f}%"


TEST = []
for fn in w.HELD_OUT:
    ts = w.make_set(zlib.crc32(fn.__name__.encode()) % 1000 + 300, A.per_type, [fn])
    TEST += ts[:A.take] if A.take else ts
summary, by_type = [], {}
for name in A.models.split(","):
    short = name.split("/")[-1]
    R = Runner(name)
    for h in A.harness.split(","):
        t1 = time.time()
        rows = run(R, TEST, h == "smart")
        with open(os.path.join(A.out, f"harness_{h}_{short}.jsonl"), "w") as f:
            f.writelines(json.dumps(r) + "\n" for r in rows)
        cl = [r for r in rows if r["style"] == "clean"]; ms = [r for r in rows if r["style"] == "messy"]
        summary.append([short, h, str(len(rows)), pct([r["fair_ok"] for r in rows]), pct([r["fair_strict"] for r in rows]),
                        f"{pct([r['fair_ok'] for r in cl])} / {pct([r['fair_ok'] for r in ms])}",
                        str(sum(r["gates"] for r in rows)), str(sum(r["nudges"] for r in rows)), f"{(time.time() - t1) / 60:.1f}"])
        for ty in sorted({r["type"] for r in rows}):
            by_type.setdefault(ty, {})[f"{short} {h}"] = pct([r["fair_ok"] for r in rows if r["type"] == ty])
        log(" | ".join(summary[-1]))
        head = ["model", "harness", "episodes", "right (fair)", "fair strict", "clean / messy", "answers sent back", "new-name nudges", "minutes"]
        cols = list(next(iter(by_type.values())).keys())
        md = ["# Plain vs smart harness, same model, no training", "",
              "Held-out figure-it-out test (world2 v3, `fair_score`). The smart harness uses no answer key: it filters search results to "
              "the asked-about entities, points out new names once, and sends an answer back once if the model did fewer lookups than its "
              "own plan had steps, used a number no tool gave it, looked nothing up, or gave no 'Answer:' line (at most twice). CPU run, greedy, thinking off.", "",
              "| " + " | ".join(head) + " |", "|" + " --- |" * len(head)] + ["| " + " | ".join(r) + " |" for r in summary]
        md += ["", "## By held-out type (right, fair)", "", "| type | " + " | ".join(cols) + " |", "|" + " --- |" * (len(cols) + 1)]
        md += ["| " + ty + " | " + " | ".join(v.get(c, "") for c in cols) + " |" for ty, v in by_type.items()]
        open(os.path.join(A.out, "HARNESS_RESULTS.md"), "w").write("\n".join(md) + "\n")
    R.close()
log("done")
