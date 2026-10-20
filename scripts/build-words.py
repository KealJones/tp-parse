"""Regenerate src/words.ts from a checkout of https://github.com/lipu-linku/sona.

Usage: python3 scripts/build-words.py path/to/sona
"""
import glob, json, sys, tomllib

sona = sys.argv[1] if len(sys.argv) > 1 else "../sona"
words = {}
for f in sorted(glob.glob(f"{sona}/words/metadata/*.toml")):
    d = tomllib.load(open(f, "rb"))
    words[d["word"]] = (d["usage_category"], bool(d.get("deprecated", False)))

out = [
    "// Generated from lipu Linku (sona) word metadata — CC BY-SA 4.0, https://github.com/lipu-linku/sona",
    "// Do not edit by hand; regenerate with scripts/build-words.py",
    "",
    "export type UsageCategory = 'core' | 'common' | 'uncommon' | 'obscure';",
    "",
    "export interface WordInfo { category: UsageCategory; deprecated: boolean }",
    "",
    "export const WORDS: Record<string, WordInfo> = {",
]
for k in sorted(words):
    cat, dep = words[k]
    out.append(f"  {json.dumps(k)}: {{ category: {json.dumps(cat)}, deprecated: {str(dep).lower()} }},")
out.append("};")
open("src/words.ts", "w").write("\n".join(out) + "\n")
print(f"wrote {len(words)} words")
