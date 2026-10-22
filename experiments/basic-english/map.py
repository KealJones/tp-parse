"""Map Ogden's 850 Basic English words onto toki pona hub words.

Sources:
  be850_categories.json  Basic English 850, by Ogden's categories
                         (from Simple English Wikipedia's ordered wordlist)
  compounds.txt          ku translation data: how often translators rendered a
                         toki pona word or compound as each English word
                         (https://tokipona.org/compounds.txt, by jan Lipamanka)
  ../../src/words.ts     Linku usage categories (only core + common words become hubs)
  sona definitions       Linku's English definitions, as a fallback
                         (python3 map.py path/to/sona)

For each English word it finds every toki pona word or compound that translates
to it, then picks one hub:
  1. a single toki pona word whose ku score for it is highest, if >= MIN_SCORE
  2. otherwise the best compound; its first word (the head) is the hub
  3. otherwise a single word whose Linku definition lists it
  4. otherwise unmapped

Outputs: mapping.json, hubs.md (readable report).
"""
import json, re, sys, tomllib, glob
from collections import defaultdict

MIN_SCORE = 20
SONA = sys.argv[1] if len(sys.argv) > 1 else "/root/sona"

cats = json.load(open("be850_categories.json"))
cat_of = {w: c for c, ws in cats.items() for w in ws}

words_ts = open("../../src/words.ts").read()
usage = dict(re.findall(r'"([a-z]+)": \{ category: "([a-z]+)"', words_ts))
HUB_OK = {w for w, c in usage.items() if c in ("core", "common")}


BASIC = {w.lower() for ws in cats.values() for w in ws}


def variants(w):
    """Inflected forms an English gloss might take for the same Basic word.
    Short words are skipped ("be" would match "being", "rat" "rating"), and so is
    any form that is itself another Basic English word."""
    out = {w}
    if len(w) < 4:
        return out
    if w.endswith("e"):
        out |= {w + "d", w[:-1] + "ing"}
    out |= {w + "s", w + "es", w + "ed", w + "ing", w + "ly", w + "ness"}
    if w.endswith("y"):
        out |= {w[:-1] + "ies", w[:-1] + "ied", w[:-1] + "ily"}
    return {v for v in out if v == w or v not in BASIC}


# ku data: phrase -> {english: score}
ku = {}
for line in open("compounds.txt"):
    m = re.match(r"^([a-zA-Z ]+): \[(.*)\]\s*$", line)
    if not m:
        continue
    phrase = m.group(1).strip()
    ku[phrase] = {}
    for item in m.group(2).split(","):
        mm = re.match(r"\s*(.+?)\s+(\d+)\s*$", item)
        if mm:
            eng = mm.group(1).lower().split("(")[0].strip()
            ku[phrase][eng] = max(ku[phrase].get(eng, 0), int(mm.group(2)))

# Linku definitions (fallback)
defs = tomllib.load(open(f"{SONA}/words/translations/en/definition.toml", "rb"))
def_order = {}
for tp, text in defs.items():
    text = re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", text.lower())
    def_order[tp] = re.findall(r"[a-z][a-z'-]*", text)

# Full per-word ku data from Linku (longer lists than compounds.txt for single words)
for f in glob.glob(f"{SONA}/words/metadata/*.toml"):
    meta = tomllib.load(open(f, "rb"))
    for eng, sc in (meta.get("ku_data") or {}).items():
        eng = eng.lower().split("(")[0].strip()
        ku.setdefault(meta["word"], {})
        ku[meta["word"]][eng] = max(ku[meta["word"]].get(eng, 0), sc)

english_index = defaultdict(list)  # english -> [(phrase, score)]
for phrase, glosses in ku.items():
    for eng, sc in glosses.items():
        english_index[eng].append((phrase, sc))

mapping = {}
for w, cat in cat_of.items():
    lw = w.lower()
    exact = english_index.get(lw, [])
    loose = [x for v in variants(lw) - {lw} for x in english_index.get(v, [])]
    cands = {}
    for phrase, sc in exact:
        cands[phrase] = max(cands.get(phrase, 0), sc)
    for phrase, sc in loose:  # inflected forms count a bit less
        cands[phrase] = max(cands.get(phrase, 0), sc * 0.8)
    singles = sorted(((p, s) for p, s in cands.items() if " " not in p and p in HUB_OK), key=lambda x: -x[1])
    comps = sorted(((p, s) for p, s in cands.items() if " " in p and p.split()[0] in HUB_OK), key=lambda x: -x[1])
    hub, via, score = None, None, 0
    if singles and singles[0][1] >= MIN_SCORE:
        hub, via, score = singles[0][0], "word", singles[0][1]
    elif comps and comps[0][1] >= MIN_SCORE:
        hub, via, score = comps[0][0].split()[0], "compound: " + comps[0][0], comps[0][1]
    else:
        # Prefer the toki pona word whose definition mentions it earliest ("up" -> sewi: "up, top, ...").
        fallback = sorted((def_order[tp].index(lw), tp) for tp in HUB_OK if lw in def_order.get(tp, []))
        if fallback and len(lw) > 1:
            hub, via = fallback[0][1], "definition"
            if len(fallback) > 1:
                via += " (also " + ", ".join(tp for _, tp in fallback[1:4]) + ")"
        elif singles or comps:
            best = (singles + comps)[0]
            hub, via, score = best[0].split()[0], "weak: " + best[0], best[1]
    mapping[w] = {"category": cat, "hub": hub, "via": via, "score": round(score),
                  "candidates": [p for p, _ in sorted(cands.items(), key=lambda x: -x[1])[:5]]}

# Hand mappings (by Claude) for whatever the data missed.
from manual import MANUAL
for w, m in mapping.items():
    if not m["hub"] and w in MANUAL:
        phrase, note = MANUAL[w]
        m["hub"] = phrase.split()[0] if phrase else None
        m["via"] = f"hand: {phrase}" if phrase else "hand: none"
        m["note"] = note

json.dump(mapping, open("mapping.json", "w"), indent=1)

# ---------- report
by_hub = defaultdict(list)
for w, m in mapping.items():
    if m["hub"]:
        by_hub[m["hub"]].append(w)
unmapped = sorted(w for w, m in mapping.items() if not m["hub"])
strong = sum(1 for m in mapping.values() if m["via"] == "word")
compound = sum(1 for m in mapping.values() if (m["via"] or "").startswith("compound"))
weak = sum(1 for m in mapping.values() if (m["via"] or "").startswith(("definition", "weak")))
hand = sum(1 for m in mapping.values() if (m["via"] or "").startswith("hand") and m["hub"])

L = ["# Basic English 850 → toki pona hubs", "",
     f"- **{strong}** words map straight onto a single toki pona word (ku score ≥ {MIN_SCORE})",
     f"- **{compound}** map through a standard compound (hub = its head word, e.g. car → *tomo tawa* → **tomo**)",
     f"- **{weak}** map only loosely (Linku definition or a low ku score) — worth a human look",
     f"- **{hand}** hand-mapped by Claude where the data had nothing (marked `hand:` in mapping.json; review these)",
     f"- **{len(unmapped)}** don't map at all", "",
     f"{len(by_hub)} of {len(HUB_OK)} core/common toki pona words are used as hubs.", "",
     "## By Basic English category", "", "| category | words | single word | compound | loose | hand | none |", "|---|---|---|---|---|---|---|"]
for c, ws in cats.items():
    vs = [mapping[w]["via"] or "" for w in ws]
    L.append(f"| {c} | {len(ws)} | {sum(v == 'word' for v in vs)} | {sum(v.startswith('compound') for v in vs)} | "
             f"{sum(v.startswith(('definition', 'weak')) for v in vs)} | {sum(v.startswith('hand') and v != 'hand: none' for v in vs)} | "
             f"{sum(v in ('', 'hand: none') for v in vs)} |")
L += ["", "## Hubs, most English words first", "", "| hub | count | English words |", "|---|---|---|"]
for hub, ws in sorted(by_hub.items(), key=lambda x: (-len(x[1]), x[0])):
    L.append(f"| **{hub}** | {len(ws)} | {', '.join(sorted(ws))} |")
L += ["", "## Unmapped", "", ", ".join(unmapped), ""]
L += ["## Unused core/common words", "", ", ".join(sorted(HUB_OK - set(by_hub))), ""]
open("hubs.md", "w").write("\n".join(L))
print("\n".join(L[:12]))
