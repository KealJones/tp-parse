"""One table: every base untouched (as released) next to its fine-tuned version, on the same eval episodes.

  python combine_results.py hf-train/metrics.json hf-baselines/metrics.json --out hf-baselines/RESULTS_COMBINED.md
"""
import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import families as F

ORDER = [("untouched-gemma3", "gemma3"), ("untouched-lfm25", "lfm25"), ("untouched-functiongemma", "functiongemma")]
HABITS = [("trained_strict", "trained types, strict mean"), ("trained_ok", "trained types, right answer"),
          ("held_strict", "held-out types, strict mean"), ("format", "well-formed calls"),
          ("loops", "episodes looping / call-capped"), ("plans", "plans multi-step requests"),
          ("asks", "asks (need) when info is missing"), ("chat", "plain chat stays plain"),
          ("done_facts", "done results carry the answer"), ("clean", "clean requests, strict"), ("messy", "messy requests, strict")]


def pct(v):
    return "-" if v is None else f"{v:.0%}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("metrics", nargs="+")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    arms = {}
    for p in a.metrics:
        arms.update(json.loads(Path(p).read_text()))
    cols = [x for pair in ORDER for x in pair if x in arms]
    L = ["# Untouched vs fine-tuned, every base", "",
         "Same 293 eval episodes for every column (squiggle-ft-train's set: EVAL_PLAN_V1, seed 123). *untouched* = the "
         "base as released, no training and no embedding changes; *tuned* = trained on teach-v1 (3 epochs).", "",
         "## Habits", "", "| measure | " + " | ".join(cols) + " |", "| --- |" + " --- |" * len(cols)]
    for k, label in HABITS:
        L.append(f"| {label} | " + " | ".join(pct(arms[c].get(k)) for c in cols) + " |")
    L.append("| tokens per call | " + " | ".join(f"{arms[c]['gen']['per_call']:.0f}" if arms[c].get("gen") else "-" for c in cols) + " |")
    L.append("| episodes evaluated | " + " | ".join(str(sum(v["n"] for v in arms[c]["families"].values())) for c in cols) + " |")
    fams = sorted({f for c in cols for f in arms[c]["families"]}, key=lambda f: (f in F.HELD_OUT, f))
    L += ["", "## Strict score per task type (right answer only in brackets)", "", "| type | " + " | ".join(cols) + " |",
          "| --- |" + " --- |" * len(cols)]
    for f in fams:
        L.append(f"| {f}{' (held out)' if f in F.HELD_OUT else ''} | " + " | ".join(
            f"{arms[c]['families'][f]['strict']:.0%} ({arms[c]['families'][f]['ok']:.0%})" if f in arms[c]["families"] else "-" for c in cols) + " |")
    Path(a.out).write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
