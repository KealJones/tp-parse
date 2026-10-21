"""Summarise efficiency_results.json."""
import json, statistics as st
from efficiency import CONDITIONS, SIZES, LAYERS

R = json.load(open("efficiency_results.json"))


def cell(layers, cond, n, key):
    xs = [r[key] for r in R if r["layers"] == layers and r["cond"] == cond and r["n"] == n]
    return (st.mean(xs), st.stdev(xs) if len(xs) > 1 else 0, len(xs)) if xs else None


for layers in LAYERS:
    print(f"\n===== {layers} layer{'s' if layers > 1 else ''} =====")
    print("English test loss after training on N English sentences (lower = learned more from less)")
    print("N".ljust(6) + "".join(c.rjust(18) for c in CONDITIONS))
    for n in SIZES:
        row = []
        for c in CONDITIONS:
            v = cell(layers, c, n, "en_loss")
            row.append("—" if not v else f"{v[0]:.3f} ±{v[1]:.3f}")
        print(str(n).ljust(6) + "".join(x.rjust(18) for x in row))
    print("\nHub score (knockout: own-concept damage minus other-concept damage; ~0 = no hubs)")
    print("N".ljust(6) + "".join(c.rjust(18) for c in CONDITIONS))
    for n in SIZES:
        row = []
        for c in CONDITIONS:
            v = cell(layers, c, n, "hub")
            row.append("—" if not v else f"{v[0]:+.2f} ±{v[1]:.2f}")
        print(str(n).ljust(6) + "".join(x.rjust(18) for x in row))
    print("\nPlanted vs unplanted (same data, same protection): planted+ewc minus unplanted+ewc, per seed")
    for n in SIZES:
        diffs = []
        for seed in sorted({r["seed"] for r in R if r["layers"] == layers}):
            a = [r["en_loss"] for r in R if r["layers"] == layers and r["seed"] == seed and r["n"] == n and r["cond"] == "planted+ewc"]
            b = [r["en_loss"] for r in R if r["layers"] == layers and r["seed"] == seed and r["n"] == n and r["cond"] == "unplanted+ewc"]
            if a and b:
                diffs.append(a[0] - b[0])
        if diffs:
            print(f"  N={n:<4} mean {st.mean(diffs):+.3f}   planted better in {sum(d < 0 for d in diffs)}/{len(diffs)} seeds")
