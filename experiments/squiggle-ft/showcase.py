"""One kept episode per family from teacher_results.jsonl.gz, written out readably (for checking by eye).
  python showcase.py data_out/teacher_results.jsonl.gz out/TEACHER_EXAMPLES.md"""
import gzip, json, random, sys
from samples import readable

rs = [json.loads(l) for l in gzip.open(sys.argv[1], "rt")]
kept = [r for r in rs if r["check"]["strict"] and r.get("calls")]
random.Random(0).shuffle(kept)
seen, md = set(), ["# Teacher episodes, one kept per family", ""]
for r in sorted(kept, key=lambda r: r["family"]):
    if r["family"] not in seen:
        seen.add(r["family"])
        md.append(readable(r, r["check"]))
open(sys.argv[2], "w").write("\n".join(md))
print(f"{len(seen)} families written to {sys.argv[2]}")
