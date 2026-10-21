"""Summarise ewc_results.json."""
import json, statistics as st
from collections import defaultdict

R = json.load(open("ewc_results.json"))
strengths = sorted({r["strength"] for r in R})
print(f"{len({r['seed'] for r in R})} seeds. Strength 0 = no protection.\n")
print("strength".ljust(10) + "English loss".rjust(14) + "toki pona loss".rjust(16) + "hub: picks own".rjust(16)
      + "corr own".rjust(10) + "corr other".rjust(12) + "synonyms corr".rjust(15))
for s in strengths:
    xs = [r for r in R if r["strength"] == s]
    syn = [row["corr_own"] for r in xs for row in r["rows"] if row["synonym"]]
    print(str(s).ljust(10)
          + f"{st.mean(r['en_loss'] for r in xs):.3f}".rjust(14)
          + f"{st.mean(r['tp_loss'] for r in xs):.2f}".rjust(16)
          + f"{st.mean(r['hub_accuracy'] for r in xs)*100:.0f}%".rjust(16)
          + f"{st.mean(r['hub_corr_same'] for r in xs):+.2f}".rjust(10)
          + f"{st.mean(r['hub_corr_other'] for r in xs):+.2f}".rjust(12)
          + f"{st.mean(syn):+.2f}".rjust(15))
print("\n(chance for 'picks own' ≈ 6%; toki pona loss right after stage 1 was about 0.8)")

best = max(strengths, key=lambda s: st.mean(r["hub_corr_same"] for r in R if r["strength"] == s))
print(f"\nPer word at strength {best}: correlation with own toki pona word's old neurons, best-match count")
per = defaultdict(list)
for r in R:
    if r["strength"] == best:
        for row in r["rows"]:
            per[(row["en"], row["tp"], row["synonym"])].append(row)
for (en, tp, syn), rows in sorted(per.items(), key=lambda kv: -st.mean(x["corr_own"] for x in kv[1])):
    print(f"  {en:8s} -> {tp:7s} corr {st.mean(x['corr_own'] for x in rows):+.2f}   best {sum(x['best']==tp for x in rows)}/{len(rows)}"
          + ("   (synonym)" if syn else ""))
