"""Summarise neurons_results.json."""
import json, statistics as st
from collections import defaultdict

R = json.load(open("neurons_results.json"))
conds = ["full", "no-dict", "full-replay", "control-other-seed"]
chance = 1 / 18

for where, label in [("mlp", "MLP neurons (96)"), ("hidden", "hidden state after the layer (48 numbers)")]:
    print(f"\n== {label}")
    print("English word after the sweep vs toki pona word BEFORE the sweep (old spot)")
    print("condition".ljust(22) + "picks own concept".rjust(20) + "corr own".rjust(12) + "corr others".rjust(14))
    for c in conds:
        xs = [r["old_tp_vs_new_en"] for r in R if r["cond"] == c and r["where"] == where]
        if not xs:
            continue
        acc = st.mean(x["accuracy"] for x in xs)
        cs = st.mean(x["corr_same"] for x in xs)
        co = st.mean(x["corr_other"] for x in xs)
        print(c.ljust(22) + f"{acc*100:.0f}%".rjust(20) + f"{cs:+.2f}".rjust(12) + f"{co:+.2f}".rjust(14))
    print(f"(chance for 'picks own concept' ≈ {chance*100:.0f}%)")
    print("English vs toki pona both AFTER the sweep (shared spot at the end?)")
    for c in ["full", "no-dict", "full-replay"]:
        xs = [r["new_tp_vs_new_en"] for r in R if r["cond"] == c and r["where"] == where]
        print(c.ljust(22) + f"{st.mean(x['accuracy'] for x in xs)*100:.0f}%".rjust(20)
              + f"{st.mean(x['corr_same'] for x in xs):+.2f}".rjust(12) + f"{st.mean(x['corr_other'] for x in xs):+.2f}".rjust(14))

print("\nPer word, 'full', MLP neurons, old toki pona spot: average correlation with its own concept, and how often it was the best match")
per = defaultdict(list)
for r in R:
    if r["cond"] == "full" and r["where"] == "mlp":
        for row in r["old_tp_vs_new_en"]["rows"]:
            per[(row["en"], row["tp"])].append(row)
for (en, tp), rows in sorted(per.items(), key=lambda kv: -st.mean(x["corr_own"] for x in kv[1])):
    print(f"  {en:8s} -> {tp:7s} corr {st.mean(x['corr_own'] for x in rows):+.2f}   best match {sum(x['best']==tp for x in rows)}/{len(rows)}"
          + ("   (synonym, never in dictionary)" if rows[0]["synonym"] else ""))
