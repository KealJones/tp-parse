"""Summarise results.json from experiment.py."""
import json, statistics as st

data = json.load(open("results.json"))
R = data["results"]
conds = ["fresh", "tp", "tp-frozen", "tp-nonsense", "tp-random", "tp+dict"]
sizes = sorted({r["n"] for r in R})
seeds = sorted({r["seed"] for r in R})


def cell(cond, n, key):
    xs = [r[key] for r in R if r["cond"] == cond and r["n"] == n and r[key] is not None]
    return xs


def fmt(xs, pct=False):
    if not xs:
        return "—"
    m = st.mean(xs)
    sd = st.stdev(xs) if len(xs) > 1 else 0
    return f"{m*100:.0f}% ±{sd*100:.0f}" if pct else f"{m:.3f} ±{sd:.3f}"


def table(key, title, pct=False):
    print(f"\n{title}  (mean ± sd over {len(seeds)} seeds)")
    print("English sentences".ljust(14) + "".join(c.rjust(16) for c in conds))
    for n in sizes:
        print(str(n).ljust(14) + "".join(fmt(cell(c, n, key), pct).rjust(16) for c in conds))


table("loss", "Test loss on new English sentences, all words (lower is better)")
table("content_loss", "Test loss on content words only: nouns + adjectives (lower is better)")
table("align", f"Word alignment: English word's nearest toki pona word is the right one (chance {data['chance_align']*100:.0f}%)", pct=True)

print("\nCompound test (cake=pan suwi, cat=soweli lili, tree=kasi suli, lake=telo suli, child=jan lili)")
print("share of compounds whose 2 nearest toki pona words include both parts / at least one part")
for c in conds:
    row = []
    for n in sizes:
        comps = [x for r in R if r["cond"] == c and r["n"] == n for x in r["compounds"]]
        both = sum(x["top2_is_parts"] for x in comps) / len(comps)
        one = sum(x["parts_in_top2"] >= 1 for x in comps) / len(comps)
        row.append(f"{both*100:.0f}% / {one*100:.0f}%")
    print(c.ljust(14) + "".join(x.rjust(14) for x in row))

print("\nPer-compound, 'tp' condition at the largest size (how often both parts are the top 2):")
n = sizes[-1]
for word in ["cake", "cat", "tree", "lake", "child"]:
    xs = [x for r in R if r["cond"] == "tp" and r["n"] == n for x in r["compounds"] if x["word"] == word]
    print(f"  {word:6s} both parts top-2: {sum(x['top2_is_parts'] for x in xs)}/{len(xs)}   at least one: {sum(x['parts_in_top2']>=1 for x in xs)}/{len(xs)}")
