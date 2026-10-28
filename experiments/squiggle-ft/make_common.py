"""data/sources/common_words.txt: words that real English text mostly writes in lowercase (databricks-dolly-15k,
CC BY-SA 3.0, human-written). The reply grounding check treats a capitalised word as a name unless it is on this list."""
import collections, json, re, sys
from pathlib import Path

src = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/claude-0/sqt/dolly/databricks-dolly-15k.jsonl")
lower, cap = collections.Counter(), collections.Counter()
for line in src.open():
    r = json.loads(line)
    for text in (r["instruction"], r["context"], r["response"]):
        for sent in re.split(r"(?<=[.!?:])\s+|\n+", text):
            words = re.findall(r"[A-Za-z][a-z']*", sent)
            for j, w in enumerate(words):
                if len(w) < 2:
                    continue
                if w.islower():
                    lower[w.replace("'", "")] += 1
                elif j > 0 and w[0].isupper() and w[1:].islower():
                    cap[w.lower().replace("'", "")] += 1
common = sorted(w for w, n in lower.items() if n >= 3 and n >= 2 * cap[w])
out = Path(__file__).resolve().parent / "data" / "sources" / "common_words.txt"
out.write_text("\n".join(common) + "\n")
print(len(common), "words ->", out)
for w in ["iroquois", "confederacy", "wikipedia", "paris", "monday", "january", "sure", "the", "great", "american", "english", "god", "president"]:
    print(w, w in set(common), lower[w], cap[w])
