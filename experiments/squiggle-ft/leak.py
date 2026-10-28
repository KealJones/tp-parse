"""Leakage filter (audit 6): a training example is dropped when its output shares any run of 8 words with Claude- or
template-written text: gold.py's template episodes (examples/gold.jsonl), the worked episodes (examples/worked.jsonl),
the legacy samples (samples/samples.jsonl) and TEACHER.md. Tool-call JSON is ignored on both sides (a shared
`{"name": "find", ...}` isn't prose), and so are the label words at the start of thinking lines.

  python leak.py out/train_examples.jsonl.gz      # report how many examples would be dropped, with examples
"""
import gzip, json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
N = 8
SOURCES = [HERE / "examples" / "gold.jsonl", HERE / "examples" / "worked.jsonl", HERE / "samples" / "samples.jsonl", HERE / "TEACHER.md",
           HERE / "checker_tests.py", HERE / "harness_tests.py"]      # their fixtures are Claude-written too
FENCE = re.compile(r"```tool_call[\s\S]*?(```|$)")
LABEL = re.compile(r"(?m)^(Request|Pieces|Know|Don't know|Goal|Plan|Next|Step|Check|Answer|Need):\s*")
_SHINGLES = None


def words(text):
    text = LABEL.sub(" ", FENCE.sub(" ", str(text or "")).replace("<think>", " ").replace("</think>", " "))
    return re.findall(r"[a-z0-9']+", text.lower())


def shingles(text):
    w = words(text)
    return {" ".join(w[i:i + N]) for i in range(len(w) - N + 1)}


def _outputs(path):
    if path.suffix in (".md", ".py"):
        yield path.read_text()
        return
    for line in open(path):
        if line.strip():
            rec = json.loads(line)
            for c in rec.get("calls", []):
                yield c.get("output") or ""
            for t in rec.get("turns", []):
                yield t.get("reply") or ""


def source_shingles():
    global _SHINGLES
    if _SHINGLES is None:
        _SHINGLES = set()
        for p in SOURCES:
            if p.exists():
                for text in _outputs(p):
                    _SHINGLES |= shingles(text)
    return _SHINGLES


def leaked(output, messages=()):
    """The first 8-word run the output shares with the sources, or None. Runs that also appear in the example's own
    prompt (a commit subject, a memory fact, a page sentence) are real data copied from a result, not leakage."""
    src = source_shingles()
    hits = [s for s in shingles(output) if s in src]
    if hits and messages:
        own = shingles(" ".join(str(m.get("content", "")) for m in messages))
        hits = [s for s in hits if s not in own]
    return hits[0] if hits else None


def main():
    n = bad = 0
    shown = 0
    for path in sys.argv[1:]:
        op = gzip.open if path.endswith(".gz") else open
        for line in op(path, "rt"):
            ex = json.loads(line)
            n += 1
            hit = leaked(ex["output"], ex.get("messages", ()))
            if hit:
                bad += 1
                if shown < 12:
                    print(f"  {ex.get('episode')} ({ex.get('kind')}): \"{hit}\"")
                    shown += 1
    print(f"{bad} of {n} examples share an {N}-word run with template or Claude-written text")


if __name__ == "__main__":
    main()
