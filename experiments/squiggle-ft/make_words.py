"""Invented words for the unknown_word family: pronounceable verbs that are NOT words, checked to have no search hits.

  python make_words.py            # -> data/sources/unknown_words.json

Each candidate (and its -ing/-s/-ed forms) must return zero results from English Wikipedia's full-text search and from
English Wiktionary's search (the harness's web_search answers from Wikipedia, so a word with no hits there can't be
"looked up" into a meaning). Survivors are then checked with a general web search by hand (see the README); words
with any hit there are dropped in WEB_HITS below. Half the words are for training, half for eval.
"""
import json, random, re, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "data" / "sources" / "unknown_words.json"
UA = {"User-Agent": "squiggle-ft/0.1 (https://github.com/KealJones/tp-parse; research)"}

ONSET = ["bl", "br", "dr", "fl", "fr", "gl", "gr", "pl", "pr", "sk", "sl", "sn", "sp", "spl", "str", "tr", "tw", "phl", "thr",
         "squ", "gw", "kr", "zl", "pr", "vr", "scr", "shm", "cl", "dw", "fn"]
VOWEL = ["a", "e", "i", "o", "u", "oo", "ai", "ee", "ou"]
MID = ["nd", "mb", "rk", "lb", "sk", "nt", "rv", "lz", "mp", "ndl", "rg", "zz", "bb", "ff", "nk", "ckl", "rp", "lv", "dg", "sp"]
END = ["ate", "ify", "le", "ize", "orate", "ulate", "ish", "ump", "ock", "wick", "en", "er", "ax", "ozzle", "inate"]
# Dropped by hand: real or too close to real words (flubber, fridge-ish...), or odd spellings.
SKIP = {"flubber", "fribber", "scribber", "glocklle", "vraindlle", "grantate", "dromben", "trounden", "fridgish", "sleeffer", "sneenkle"}
# The rest were also searched on the open web on 2026-10-28, six quoted words per query ("a" OR "b" ...): no result
# contained any of them (only near words such as "scrump", "plump", "shmendrik"). Words with a web hit would go here.
WEB_HITS = set()


def forms(base):
    if base.endswith("y"):
        return {"base": base, "ing": base + "ing", "s": base[:-1] + "ies", "ed": base[:-1] + "ied"}
    if base.endswith("e"):
        return {"base": base, "ing": base[:-1] + "ing", "s": base + "s", "ed": base + "d"}
    return {"base": base, "ing": base + "ing", "s": base + "s", "ed": base + "ed"}


def candidates(rng, n):
    seen = set()
    while len(seen) < n:
        w = rng.choice(ONSET) + rng.choice(VOWEL) + rng.choice(MID) + rng.choice(END)
        if 7 <= len(w) <= 12 and not re.search(r"(.)\1\1", w):
            seen.add(w)
    return sorted(seen)


def hits(host, q):
    url = f"https://{host}/w/api.php?" + urllib.parse.urlencode({"action": "query", "list": "search", "srsearch": q, "srlimit": 1,
                                                                 "srinfo": "totalhits", "format": "json"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
                return json.load(r)["query"]["searchinfo"]["totalhits"]
        except urllib.error.HTTPError as e:
            time.sleep(float(e.headers.get("Retry-After") or 0) or 20 * (attempt + 1))     # Wikipedia rate-limits shared IPs
        except Exception:
            time.sleep(5 * (attempt + 1))
    return None


def zero_hits(host, words):
    """The words with no hits on host: one OR query per batch of forms, split in half when a batch has hits."""
    q = " OR ".join(sorted({x for w in words for x in forms(w).values()}))
    n = hits(host, q)
    time.sleep(2.5)
    if n == 0:
        return set(words)
    if n is None or len(words) == 1:
        return set()                                     # a hit, or the search failed: not kept
    h = len(words) // 2
    return zero_hits(host, words[:h]) | zero_hits(host, words[h:])


def main():
    rng = random.Random(20261028)
    words = [w for w in candidates(rng, 90) if w not in SKIP and w not in WEB_HITS]
    clean = set(words)
    for host in ("en.wikipedia.org", "en.wiktionary.org"):
        for i in range(0, len(words), 5):
            batch = [w for w in words[i:i + 5] if w in clean]
            if batch:
                ok = zero_hits(host, batch)
                clean -= set(batch) - ok
                print(host, batch, "->", sorted(ok), flush=True)
    out = [{"word": w, "forms": forms(w), "hits": {"en.wikipedia.org": 0, "en.wiktionary.org": 0, "web": "no exact match"}}
           for w in words if w in clean]
    rng.shuffle(out)
    for i, x in enumerate(out):
        x["split"] = "train" if i % 2 == 0 else "eval"
    OUT.write_text(json.dumps(out, indent=1) + "\n")
    print(len(out), "words ->", OUT)


if __name__ == "__main__":
    main()
