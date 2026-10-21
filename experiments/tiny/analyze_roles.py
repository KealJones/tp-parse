"""Summarise roles_results.json."""
import json, statistics as st
from collections import defaultdict

R = json.load(open("roles_results.json"))
GROUP_SIZES = {"verbs": 5, "nouns": 8, "adjectives": 5}

for where, label in [("mlp", "MLP neurons"), ("hidden", "hidden state")]:
    print(f"\n== {label}: English word vs toki pona words of the SAME kind (old stage-1 spots)")
    print("group".ljust(12) + "chance".rjust(8) + "".join(c.rjust(18) for c in ["no protection", "light EWC (10)", "control"]))
    for g, size in GROUP_SIZES.items():
        cells = []
        for strength in [0, 10, "control"]:
            rows = [row for r in R if r["where"] == where and r["group"] == g and r["strength"] == strength for row in r["rows"]]
            acc = sum(row["best"] == row["tp"] for row in rows) / len(rows)
            own = st.mean(row["scores"][row["tp"]] for row in rows)
            cells.append(f"{acc*100:.0f}% ({own:+.2f})")
        print(g.ljust(12) + f"{100/size:.0f}%".rjust(8) + "".join(c.rjust(18) for c in cells))
    print("  each cell: how often the right toki pona word is the best match (average correlation with it)")

    print(f"\n== {label}: synonyms inside English (same spot?)")
    print("pair".ljust(14) + "".join(c.rjust(22) for c in ["English only", "toki pona first", "toki pona + light EWC"]))
    pairs = defaultdict(lambda: defaultdict(list))
    for r in R:
        if r["where"] == where and r["group"] == "synonyms":
            for x in r["syn"]:
                pairs[x["pair"]][r["strength"]].append(x["syn_corr"] - x["other_corr"])
    for pair, by in pairs.items():
        print(pair.ljust(14) + "".join(f"{st.mean(by[k]):+.2f}".rjust(22) for k in ["english-only", 0, 10]))
    allk = {k: st.mean(v for by in pairs.values() for v in by[k]) for k in ["english-only", 0, 10]}
    print("average".ljust(14) + "".join(f"{allk[k]:+.2f}".rjust(22) for k in ["english-only", 0, 10]))
    print("  each cell: (synonym-to-synonym correlation) minus (correlation with other same-kind words); higher = shares a spot")

print("\nPer word, MLP, light EWC: best toki pona match within its own kind (counts over seeds)")
per = defaultdict(list)
for r in R:
    if r["where"] == "mlp" and r["strength"] == 10 and r["group"] in GROUP_SIZES:
        for row in r["rows"]:
            per[(r["group"], row["en"], row["tp"])].append(row["best"])
for (g, en, tp), bests in sorted(per.items()):
    print(f"  {g:10s} {en:8s} should be {tp:7s}: right {bests.count(tp)}/{len(bests)}")
