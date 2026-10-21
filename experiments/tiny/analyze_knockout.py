"""Summarise knockout_results.json."""
import json, statistics as st
from knockout import CONCEPTS, ENGLISH

import sys
DICT_RUN = "--dict" in sys.argv
R = json.load(open("knockout_dict_results.json" if DICT_RUN else "knockout_results.json"))
conds = ["routed+dict", "routed+dict+ewc", "unrouted+dict", "english"] if DICT_RUN else ["routed", "routed+ewc", "unrouted", "english"]
IN_DICT = {"telo", "moku", "tomo", "kala", "pan", "soweli", "jan"}  # waso (bird) and kili (fruit) are not in the dictionary


def summary(key):
    print("condition".ljust(14) + "own concept".rjust(14) + "other concepts".rjust(16) + "random block".rjust(14) + "own wins".rjust(10))
    for c in conds:
        rows = [r[key] for r in R if r["cond"] == c and key in r]
        if not rows:
            continue
        own = st.mean(m[k][k] for m in rows for k in CONCEPTS)
        other = st.mean(m[k][t] for m in rows for k in CONCEPTS for t in CONCEPTS if t != k)
        rnd = st.mean(v for m in rows for v in m["random"].values())
        # how often a block's knockout hurts its own concept more than any other concept
        wins = sum(max(m[k], key=lambda t: m[k][t]) == k for m in rows for k in CONCEPTS) / (len(rows) * len(CONCEPTS))
        print(c.ljust(14) + f"{own:+.3f}".rjust(14) + f"{other:+.3f}".rjust(16) + f"{rnd:+.3f}".rjust(14) + f"{wins*100:.0f}%".rjust(10))
    print(f"  values: how much worse the model gets (loss increase) at predicting each concept's words; 'own wins' chance = {100/len(CONCEPTS):.0f}%")


print("== Right after toki pona (stage 1): knock out a block, predict toki pona words")
summary("tp_after_stage1")
if DICT_RUN:
    print("\n== After the dictionary, before the English sweep: knock out a block, predict English words")
    summary("en_after_dict")
print("\n== After the English sweep: knock out a block, predict English words")
summary("en_knockout")

for cond in conds[:2]:
    print(f"\nPer concept, '{cond}', after English: loss increase on own words vs average on others")
    for k in CONCEPTS:
        own = st.mean(r["en_knockout"][k][k] for r in R if r["cond"] == cond)
        oth = st.mean(r["en_knockout"][k][t] for r in R if r["cond"] == cond for t in CONCEPTS if t != k)
        tag = "" if not DICT_RUN else ("  (in dictionary)" if k in IN_DICT else "  (NOT in dictionary)")
        print(f"  {k:7s} ({'/'.join(ENGLISH[k])}): own {own:+.3f}  others {oth:+.3f}{tag}")
