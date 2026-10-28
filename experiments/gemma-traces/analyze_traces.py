"""Count how Gemma-style thinking traces are structured.

Reads a JSONL file where each line has either:
  - "raw": decoded model text containing <|channel>thought ... <channel|>, or
  - "thinking": the thought text on its own (the Squiggle session format).
plus optional "id", "category", "prompt", "model", and the token counts run_traces.py
saves ("thought_tokens", "answer_tokens", "finished").

Prints a per-category summary (per model when the files hold more than one) and
writes a per-trace CSV. "phone s" is the thinking alone at 15 tokens/s.

numbered_steps counts only the first numbered list in a thought. The tool,
unknown-word and ask flags are crude keyword hints, not judgments, so read the
actual traces for any prompt you care about.

    python analyze_traces.py out/traces_*.jsonl --csv trace_stats.csv
"""
import argparse
import csv
import json
import re
from collections import Counter, defaultdict

THOUGHT = re.compile(r"<\|channel>thought\s*(.*?)(?:<channel\|>|$)", re.DOTALL)
# One numbered line: "1.  **Analyze the User Request:** details" or "2. Locate the code"
NUMBERED = re.compile(r"^\s*(\d+)\.\s+(.*)$", re.MULTILINE)


def first_plan(thought):
    """Return [(number, title)] for the first numbered list only (1, 2, 3, ...).

    Thoughts often contain a second numbered list later (e.g. a "Plan:" after a
    tool call); counting only the first run avoids double counting.
    """
    steps = []
    for m in NUMBERED.finditer(thought):
        n, rest = int(m.group(1)), m.group(2).strip()
        if not steps:
            if n != 1:
                continue
        elif n != steps[-1][0] + 1:
            break
        bold = re.match(r"\*\*(.+?)\*\*", rest)
        if bold:
            title = bold.group(1)
        else:
            title = re.split(r"[:\-—]", rest, maxsplit=1)[0]
        title = title.strip(" *:").strip()[:60]
        steps.append((n, title))
    return steps
OPENER = re.compile(r"^\s*(here'?s a thinking process|thinking process)", re.IGNORECASE)
SQUIGGLE_TOOLS = ("list_files read_file grep note write_file delete_file github_list_repos git_clone git_status git_branch "
                  "git_commit git_push git_pull git_log github_open_pr fetch_url web_search remember recall forget "
                  "search_history run_js").split()
TOOL_WORDS = re.compile(r"\b(tool|" + "|".join(SQUIGGLE_TOOLS) + r"|search|look(?:ing)? up)\b", re.IGNORECASE)
UNKNOWN_WORDS = re.compile(
    r"(don'?t know|not familiar|unfamiliar|made[- ]up|not a (?:standard|real|recognized|known)|"
    r"doesn'?t (?:appear|seem) to be|no (?:known|standard|clear) (?:meaning|definition)|"
    r"not sure what|can'?t find|neologism|typo)",
    re.IGNORECASE,
)
ASK_WORDS = re.compile(r"(clarif|ask the user|ask for|what (?:they|the user) mean)", re.IGNORECASE)


def get_thought(rec):
    if rec.get("thinking"):
        return rec["thinking"]
    m = THOUGHT.search(rec.get("raw", ""))
    return m.group(1).strip() if m else ""


def stats(thought):
    steps = first_plan(thought)
    top_level = [t for n, t in steps if t]
    first_line = thought.strip().splitlines()[0] if thought.strip() else ""
    return {
        "thought_chars": len(thought),
        "numbered_steps": len(steps),
        "step_titles": " | ".join(top_level[:12]),
        "template_opener": bool(OPENER.match(thought)),
        "first_line": first_line[:100],
        "mentions_tool": bool(TOOL_WORDS.search(thought)),
        "flags_unknown": bool(UNKNOWN_WORDS.search(thought)),
        "plans_to_ask": bool(ASK_WORDS.search(thought)),
        "has_thought": bool(thought),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--csv", default="trace_stats.csv")
    args = ap.parse_args()

    recs = [json.loads(line) for path in args.paths for line in open(path) if line.strip()]
    models = {(r.get("model") or "").split("/")[-1] for r in recs}
    rows = []
    for r in recs:
        s = stats(get_thought(r))
        s.update({"id": r.get("id"), "category": r.get("category", "all"), "prompt": (r.get("prompt") or "")[:80],
                  "model": (r.get("model") or "").split("/")[-1], "run": r.get("run"),
                  "thought_tokens": r.get("thought_tokens"), "answer_tokens": r.get("answer_tokens"),
                  "finished": r.get("finished")})
        rows.append(s)

    fields = ["model", "id", "run", "category", "prompt", "has_thought", "thought_chars", "thought_tokens", "answer_tokens",
              "finished", "numbered_steps",
              "template_opener", "mentions_tool", "flags_unknown", "plans_to_ask", "first_line", "step_titles"]
    with open(args.csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for s in rows:
            w.writerow({k: s[k] for k in fields})

    by_cat = defaultdict(list)
    for s in rows:
        by_cat[(s["model"] + " " if len(models) > 1 else "") + s["category"]].append(s)

    print(f"{len(rows)} traces\n")
    w = max(14, max(len(c) for c in by_cat) + 2)
    print(f"{'category':{w}}{'n':>4}{'has thought':>13}{'avg chars':>11}{'avg tok':>9}{'max tok':>9}{'phone s':>9}{'avg steps':>11}"
          f"{'% list':>8}{'% opener':>10}{'% tool':>8}{'% unknown':>11}{'% ask':>7}{'capped':>8}")
    for cat, items in by_cat.items():
        n = len(items)
        thoughts = [i for i in items if i["has_thought"]]
        pct = lambda f: 100 * sum(1 for i in items if i[f]) / n
        avg = lambda f: (sum(i[f] for i in thoughts) / len(thoughts)) if thoughts else 0
        listed = 100 * sum(1 for i in items if i["numbered_steps"] >= 2) / n
        toks = [i["thought_tokens"] for i in thoughts if i["thought_tokens"] is not None]
        avg_tok = sum(toks) / len(toks) if toks else 0
        capped = sum(1 for i in items if i["finished"] is False)
        print(f"{cat:{w}}{n:>4}{len(thoughts):>13}{avg('thought_chars'):>11.0f}{avg_tok:>9.0f}{max(toks or [0]):>9}"
              f"{avg_tok / 15:>9.0f}{avg('numbered_steps'):>11.1f}"
              f"{listed:>7.0f}%{pct('template_opener'):>9.0f}%{pct('mentions_tool'):>7.0f}%{pct('flags_unknown'):>10.0f}%"
              f"{pct('plans_to_ask'):>6.0f}%{capped:>8}")

    titles = Counter()
    for s in rows:
        for t in s["step_titles"].split(" | "):
            t = re.sub(r"[^a-z ]", "", t.lower()).strip()
            if t:
                titles[t] += 1
    print("\nMost common step titles (does a shared skeleton show up?):")
    for t, c in titles.most_common(12):
        print(f"  {c:3}  {t}")
    print(f"\nPer-trace CSV: {args.csv}")


if __name__ == "__main__":
    main()
