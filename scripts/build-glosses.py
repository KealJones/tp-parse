"""Build src/glosses.ts: English glosses for each toki pona word.

Sources (lipu Linku / sona, CC BY-SA 4.0):
  - words/translations/en/definition.toml  (Linku's English definitions)
  - ku_data in words/metadata/*.toml        (how often translators in the
    Toki Pona Dictionary used each English word; kept at >= MIN_KU percent)

Usage: python3 scripts/build-glosses.py path/to/sona
"""
import glob, json, re, sys, tomllib

sona = sys.argv[1] if len(sys.argv) > 1 else "../sona"
MIN_KU = 20
# Words in definitions that describe grammar rather than meaning.
SKIP = set("""
a an the of to for and or in on at by from with as be is are e.g eg etc
particle preverb preposition number interjection pronoun word phrase marks mark start
separates multiple possibilities replacing another placed after something negates forms yes-no
question indicate thinking pause animal noise communication onomatopoeia first second third
person plural singular previous statement context following verb direct object indicative
vocative imperative command wish instruction ordinal pronunciation variant used group modifier
""".split())

definitions = tomllib.load(open(f"{sona}/words/translations/en/definition.toml", "rb"))
out = {}
primary = {}
for f in sorted(glob.glob(f"{sona}/words/metadata/*.toml")):
    meta = tomllib.load(open(f, "rb"))
    word = meta["word"]
    glosses = set()
    text = definitions.get(word, "")
    text = re.sub(r"\[[^\]]*\]", " ", text)  # drop [grammar notes]
    text = re.sub(r"\([^)]*\)", " ", text)   # drop (part of speech)
    for tok in re.findall(r"[a-z][a-z'-]*", text.lower()):
        if tok not in SKIP and len(tok) > 1:
            glosses.add(tok)
    for eng, pct in (meta.get("ku_data") or {}).items():
        if pct >= MIN_KU:
            for tok in re.findall(r"[a-z][a-z'-]*", eng.lower()):
                if tok not in SKIP and len(tok) > 1:
                    glosses.add(tok)
    out[word] = sorted(glosses)
    first = re.findall(r"[a-z][a-z' -]*", text.lower())
    primary[word] = first[0].strip() if first else word

lines = [
    "// Generated from lipu Linku (sona): English definitions plus ku_data — CC BY-SA 4.0,",
    "// https://github.com/lipu-linku/sona. Regenerate with scripts/build-glosses.py.",
    "",
    "export const GLOSSES: Record<string, string[]> = {",
]
for w in sorted(out):
    lines.append(f"  {json.dumps(w)}: {json.dumps(out[w])},")
lines.append("};")
lines.append("")
lines.append("/** The first English sense in Linku's definition, for word-by-word glossing. */")
lines.append("export const PRIMARY_GLOSS: Record<string, string> = {")
for w in sorted(primary):
    lines.append(f"  {json.dumps(w)}: {json.dumps(primary[w])},")
lines.append("};")
open("src/glosses.ts", "w").write("\n".join(lines) + "\n")
print(f"wrote glosses for {len(out)} words, {sum(map(len, out.values()))} English forms")
