"""Summarise stages_results.json."""
import json, statistics as st
from collections import Counter

R = json.load(open("stages_results.json"))
conds = ["full", "no-tp", "no-dict", "english", "full-frozen", "full-replay"]


def m(cond, stage, key):
    xs = [r[stage][key] for r in R if r["cond"] == cond and stage in r]
    return (st.mean(xs), st.stdev(xs) if len(xs) > 1 else 0) if xs else None


def row(label, stage, key, pct=False):
    cells = []
    for c in conds:
        v = m(c, stage, key)
        cells.append("—" if v is None else (f"{v[0]*100:.0f}%" if pct else f"{v[0]:.2f}"))
    print(label.ljust(46) + "".join(x.rjust(13) for x in cells))


print(f"{len({r['seed'] for r in R})} seeds. Values are means.")
print("".ljust(46) + "".join(c.rjust(13) for c in conds))
print("\nAFTER STAGE 3 (the big English sweep)")
row("English test loss (lower = better)", "after_3", "en_loss")
row("toki pona test loss (lower = remembers more)", "after_3", "tp_loss")
row("toki pona prob leaking into English", "after_3", "en_leak", True)
row("English prob leaking into toki pona", "after_3", "tp_leak", True)
row("'X means ?' right, words IN dictionary", "after_3", "means_dict", True)
row("'X means ?' right, words NOT in dictionary", "after_3", "means_held", True)
row("'X means ?' right, synonyms (liquid, home…)", "after_3", "means_syn", True)
row("nearest tp word right, in dictionary", "after_3", "near_dict", True)
row("nearest tp word right, not in dictionary", "after_3", "near_held", True)
row("nearest tp word right, synonyms", "after_3", "near_syn", True)
row("compound: a part among 2 nearest", "after_3", "compound_one_part", True)

print("\nAFTER STAGE 2 (dictionary), before any English sweep")
row("'X means ?' right, words IN dictionary", "after_2", "means_dict", True)
row("nearest tp word right, in dictionary", "after_2", "near_dict", True)
row("toki pona test loss", "after_2", "tp_loss")

print("\nAFTER STAGE 1 (toki pona only)")
row("toki pona test loss", "after_1", "tp_loss")

print("\nWhat 'X means' answered after stage 3, condition 'full' (counts over seeds):")
for word in ["bird", "fruit", "sleeps", "drinks", "liquid", "home", "large", "nice", "munches"]:
    c = Counter(r["after_3"]["means_examples"][word] for r in R if r["cond"] == "full")
    print(f"  {word:8s} -> " + ", ".join(f"{w}×{n}" for w, n in c.most_common(4)))
