"""Summarise bridge_results.json."""
import json, statistics as st
from knockout import CONCEPTS, ENGLISH
from bridge import CONDITIONS, UNBRIDGED

R = json.load(open("bridge_results.json"))
BRIDGED = [c for c in CONCEPTS if c not in UNBRIDGED]


def score(m, concepts):
    """Average of (damage to own words) minus (average damage to other concepts' words)."""
    return st.mean(m[k][k] - st.mean(m[k][t] for t in CONCEPTS if t != k) for k in concepts)


print("Knock out a planted block after the English sweep. Positive = it hurts its own concept more than others.\n")
print("condition".ljust(16) + "bridged".rjust(10) + "unbridged".rjust(11) + "own wins".rjust(10) + "seeds > +0.2".rjust(14))
for c in CONDITIONS:
    rows = [r["en_knockout"] for r in R if r["cond"] == c]
    b = [score(m, BRIDGED) for m in rows]
    u = [score(m, UNBRIDGED) for m in rows]
    wins = sum(max(m[k], key=lambda t: m[k][t]) == k for m in rows for k in BRIDGED) / (len(rows) * len(BRIDGED))
    print(c.ljust(16) + f"{st.mean(b):+.3f}".rjust(10) + f"{st.mean(u):+.3f}".rjust(11) + f"{wins*100:.0f}%".rjust(10)
          + f"{sum(x > 0.2 for x in b)}/{len(b)}".rjust(14))
print(f"  bridged = concepts in the bridge; unbridged = bird, fruit; 'own wins' chance = {100/len(CONCEPTS):.0f}%")

for c in CONDITIONS[:3]:
    print(f"\nPer concept, '{c}' (mean over seeds, own minus others; seeds where own block hurt its words most):")
    for k in CONCEPTS:
        rows = [r["en_knockout"] for r in R if r["cond"] == c]
        d = st.mean(m[k][k] - st.mean(m[k][t] for t in CONCEPTS if t != k) for m in rows)
        w = sum(max(m[k], key=lambda t: m[k][t]) == k for m in rows)
        print(f"  {k:7s} ({'/'.join(ENGLISH[k])}): {d:+.3f}   own block worst for own words {w}/{len(rows)}"
              + ("   (not bridged)" if k in UNBRIDGED else ""))
