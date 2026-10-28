"""Near-miss words for the near_miss family (CORPUS_V2 §2e): a real key term with one or two letters changed so the
result is NOT a word: zero hits in English Wikipedia's and Wiktionary's search (the same check as make_words.py).
Training terms are everyday and non-git tech; the eval terms are git/code (the Gemma "zymbolic merge" failure), so
near-miss x git is held out whole.

  python make_nearmiss.py      # -> data/sources/near_miss.json
"""
import json, random
from pathlib import Path

import make_words as M

HERE = Path(__file__).resolve().parent
OUT = HERE / "data" / "sources" / "near_miss.json"
TRAIN = ["sourdough", "lasagna", "thermostat", "spreadsheet", "mortgage", "bluetooth", "router", "firmware", "playlist",
         "carburetor", "sunscreen", "compost", "fertilizer", "dehumidifier", "toaster", "smoothie", "croissant",
         "vinaigrette", "espresso", "cardigan", "treadmill", "hammock", "voicemail", "screenshot", "printer"]
EVAL = ["rebase", "merge", "stash", "submodule", "squash", "checkout", "symbolic", "branch", "commit", "cherry-pick"]
CONS = "bcdfghjklmnpqrstvwxz"


def edits(rng, word, n=6):
    """Candidate near-misses: one interior consonant swapped (two for short words), first letter kept."""
    out = set()
    idx = [i for i in range(1, len(word) - 1) if word[i] in CONS]
    for _ in range(n * 4):
        w = list(word)
        for i in rng.sample(idx, min(len(idx), 1 if len(word) > 6 else 2)):
            w[i] = rng.choice([c for c in CONS if c != word[i]])
        cand = "".join(w)
        if cand != word:
            out.add(cand)
        if len(out) >= n:
            break
    return sorted(out)


# The near-misses in use: picked by hand from edits() output (one letter off where the result is still readable), then
# searched on the open web on 2026-10-28, seven quoted words per query: no result contained any of them. Wikipedia's
# API rate-limited the automatic check below from this machine, so `python make_nearmiss.py --auto` is the fallback.
PICKS = {"train": {"lasagna": "lasabna", "thermostat": "thermodtat", "spreadsheet": "spreadhheet", "mortgage": "morngage",
                   "bluetooth": "bluegooth", "router": "roufer", "firmware": "firmgare", "playlist": "playlidt",
                   "carburetor": "carbugetor", "sunscreen": "sumscreen", "compost": "compobt", "fertilizer": "ferbilizer",
                   "dehumidifier": "dehubidifier", "toaster": "toasber", "smoothie": "smoodhie", "croissant": "croijsant",
                   "vinaigrette": "vinaigretwe", "espresso": "espremso", "cardigan": "cardilan", "treadmill": "treadmibl",
                   "hammock": "hamfock", "voicemail": "voicekail", "screenshot": "screefshot", "printer": "prinver",
                   "sourdough": "sourdoukh"},
         "eval": {"rebase": "rebaze", "merge": "merje", "squash": "sqvash", "branch": "bramch", "commit": "comnit",
                  "checkout": "checkoub", "symbolic": "zymbolic", "submodule": "submodyle", "cherry-pick": "cherry-pyck", "stash": "stazh"}}


def main():
    import sys
    if "--auto" not in sys.argv:
        rows = [{"real": r, "miss": m, "split": sp, "checked": "open-web search, quoted, no exact match (2026-10-28)"}
                for sp, d in PICKS.items() for r, m in d.items()]
        OUT.write_text(json.dumps(rows, indent=1) + "\n")
        print(len(rows), "near-misses ->", OUT)
        return
    rng = random.Random(20261028)
    rows = []
    for split, terms in (("train", TRAIN), ("eval", EVAL)):
        for t in terms:
            cands = edits(rng, t.replace("-", ""))
            clean = set(cands)
            for host in ("en.wikipedia.org", "en.wiktionary.org"):
                ok = set()
                for i in range(0, len(cands), 6):
                    batch = [c for c in cands[i:i + 6] if c in clean]
                    if batch:
                        ok |= M.zero_hits(host, batch)
                clean &= ok
            pick = next((c for c in cands if c in clean), None)
            print(split, t, "->", pick, f"({len(clean)} of {len(cands)} candidates had no hits)", flush=True)
            if pick:
                rows.append({"real": t, "miss": pick if "-" not in t else pick[:t.index("-")] + "-" + pick[t.index("-"):],
                             "split": split, "hits": {"en.wikipedia.org": 0, "en.wiktionary.org": 0}})
    OUT.write_text(json.dumps(rows, indent=1) + "\n")
    print(len(rows), "near-misses ->", OUT)


if __name__ == "__main__":
    main()
