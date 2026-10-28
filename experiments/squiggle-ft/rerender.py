"""Replays kept teacher episodes through a newer Squiggle pin with the teacher's stored outputs and the stored user
messages, and compares every prompt with the stored one. An episode whose prompts are the same (apart from live web
results, the date line, untrusted-block keys and the calculate description) is kept as stored, with the calculate
description updated to the new wording; an episode whose prompts changed is dropped: its outputs were written for a
context the app no longer builds (injected memory facts, other chats, a longer history).

  python rerender.py --squiggle <checkout> --out data/rerendered [--limit N]

Writes <out>/<run>.jsonl.gz (kept episodes, prompts updated) and <out>/RERENDER.md (counts and reasons per family).
"""
import argparse, collections, dataclasses, gzip, json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build, families as F
from sqrun import Runner, ScriptBackend

OLD_CALC = ("Calculate a math expression exactly: + - * / ^, parentheses, percentages (15% of 240), and sqrt, round(x, digits), "
            "min, max, abs, floor, ceil, pow, log, ln, exp.")
NEW_CALC = ("Calculate a math expression exactly: + - * / ^, parentheses, percentages (15% of 240), pi and e, sqrt, round(x, digits), "
            "min, max, abs, floor, ceil, pow, log, ln, exp.")
KEY = re.compile(r'key=(\\?")[0-9a-f]+(\\?")')
LIVE = re.compile(r'(Result of (?!find:)\w+:\n)\{.*?\}(?=\n\nResult of |\Z)', re.S)   # tool results are data, not app text
TODAY = re.compile(r"Today is [A-Z][a-z]{2} [A-Z][a-z]{2} \d{2} \d{4}\.")
CTX_LEFT = re.compile(r'"context_left":"[^"]*"')


def calc_fix(text):
    return text.replace(OLD_CALC, NEW_CALC)


WEB_BLOCK = re.compile(r'(<untrusted source=\\?"(?:web search|https?://[^"\\]*)\\?" key=)[^>]*>.*?</untrusted[^>]*>', re.S)
CALC_DESC = re.compile(r'Calculate a math expression exactly:[^\n"\\]*')


def norm(text):
    t = WEB_BLOCK.sub(r"\1>[live web text]</untrusted>", calc_fix(text))
    t = LIVE.sub(r"\1<live>", KEY.sub(r"key=\1K\2", t))
    t = re.sub(r"\b[A-Z][a-z]{2} \d{1,2}, \d{1,2}:\d{2} [AP]M\b", "<when>", t)      # retrieved-message times
    return CTX_LEFT.sub('"context_left":"?"', TODAY.sub("Today is <date>.", t))


def stored_user_texts(rec):
    """The user's message at the start of each turn, read from the first call of that turn."""
    out, i = [], 0
    calls = [c for c in rec.get("calls", []) if c.get("kind") != "background"]
    for t in rec["turns"]:
        seg = calls[i:i + t.get("calls", 0)]
        i += t.get("calls", 0)
        msgs = seg[0]["messages"] if seg else []
        last = next((m["content"] for m in reversed(msgs) if m["role"] == "user"), None)
        out.append(last)
    return out


def episode_for(rec, rebuilt):
    ep = rebuilt.get(rec["id"].rstrip("r")) if rec["id"].endswith("r") else rebuilt.get(rec["id"])
    if ep is None:
        return None
    users = stored_user_texts(rec)

    sessions = [t.get("session") or "main" for t in rec["turns"]]

    def user(turn, e, users=users):
        k = turn["n"] + 1
        if k >= len(users):
            return None
        return users[k] if sessions[k] == "main" else (users[k], sessions[k])
    meta = {**ep.meta, "date_shift": (rec.get("meta") or {}).get("date_shift", 0)}     # teach-v1 ran before date shifts
    world = dict(ep.world)
    first_sys = next((c["messages"][0]["content"] for c in rec.get("calls", []) if c.get("messages")), "")
    if "## Recipe from a similar task" in first_sys:     # the recipe the stored episode had (a rebuild may draw another)
        match = [r for r in F.gold_recipes() if f"(for: {r.get('when')})" in first_sys]
        if match:
            world["recipes"] = [{k: v for k, v in match[0].items() if k not in ("from_episode", "repo", "kind")}]
    return dataclasses.replace(ep, id=rec["id"], first=rec["first"], gold=rec["gold"], world=world,
                               user=user if len(users) > 1 else None, meta=meta)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--squiggle", required=True)
    ap.add_argument("--out", default=str(HERE / "data" / "rerendered"))
    ap.add_argument("--work", default=str(HERE / "work"))
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    work = Path(args.work)
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    src = build.load_sources(work, "train")
    runs = {
        "teach-v1": (HERE / "hf-teach-2" / "teach" / "teacher_results.jsonl.gz",
                     {e.id: e for e in build.make_sets(src, build.TARGET_PLAN, seed=0, dedupe=False)}),
        "teach-v2": (HERE / "hf-teach-v2" / "teach" / "teacher_results.jsonl.gz",
                     {e.id: e for e in build.make_sets(src, build.V2_PLAN, seed=0, exclude=build.exclude_keys(work))}),
    }
    md = ["# Re-rendered on " + args.squiggle, ""]
    for name, (path, rebuilt) in runs.items():
        recs = [r for r in map(json.loads, gzip.open(path, "rt")) if r["check"]["strict"] and F.check(r)["strict"]]
        if args.limit:
            recs = recs[:args.limit]
        eps, skipped = [], []
        for r in recs:
            e = episode_for(r, rebuilt)
            (eps.append(e) if e else skipped.append(r["id"]))
        outs = {r["id"]: [c["output"] for c in r["calls"] if c.get("kind") != "background"] for r in recs}
        new = {x["id"]: x for x in Runner(ScriptBackend(outs), args.squiggle, str(work), concurrency=12, batch_wait=0.05,
                                          log=lambda *a: None).run(eps)}
        why, kept_recs = collections.Counter(), []
        rerendered = collections.Counter()
        fam_n, fam_kept = collections.Counter(), collections.Counter()
        for r in recs:
            fam_n[r["family"]] += 1
            n = new.get(r["id"])
            old_calls = [c for c in r["calls"] if c.get("kind") != "background"]
            new_calls = [c for c in (n or {}).get("calls", []) if c.get("kind") != "background"]
            reason = None
            if n is None:
                reason = "not rebuilt"
            elif len(old_calls) != len(new_calls):
                reason = f"call count {len(old_calls)} -> {len(new_calls)}"
            else:
                turn_of = [k for k, t in enumerate(r["turns"]) for _ in range(t.get("calls", 0))]
                for i, (a, b) in enumerate(zip(old_calls, new_calls)):
                    A, B = [norm(m["content"]) for m in a["messages"]], [norm(m["content"]) for m in b["messages"]]
                    if A != B and len(A) == len(B) and all(CALC_DESC.sub("<calc>", x) == CALC_DESC.sub("<calc>", y) for x, y in zip(A, B)):
                        # only the calculate description differs (it's cut to a length in the looked-up list): take the
                        # new wording, keep everything else as stored
                        for ma, mb in zip(a["messages"], b["messages"]):
                            new_desc = CALC_DESC.findall(mb["content"])
                            if new_desc:
                                it = iter(new_desc)
                                ma["content"] = CALC_DESC.sub(lambda _m: next(it, _m.group(0)), ma["content"])
                        continue
                    if A != B and F.plain_mode(r["family"], turn_of[i]) \
                            and not any(m["content"].startswith("Result of ") for m in a["messages"] + b["messages"]) \
                            and [m["role"] for m in a["messages"]] == [m["role"] for m in b["messages"]] \
                            and all(x == y for x, y in zip(A[1:], B[1:])):
                        # a call with no tool results whose system prompt changed (plain chat or personal advice after a
                        # lookup: the retrieved "earlier context" section is gone): its output didn't use that section,
                        # so it is re-rendered with the new prompt
                        a["messages"] = b["messages"]
                        rerendered[r["family"]] += 1
                        continue
                    if A != B:
                        sa, sb = norm(a["messages"][0]["content"]), norm(b["messages"][0]["content"])
                        if sa != sb:
                            gone = [h for h in re.findall(r"^## .+$", sa, re.M) if h not in sb]
                            reason = "system: " + (("lost " + gone[0][:50]) if gone else "changed")
                        else:
                            reason = f"messages changed ({len(a['messages'])} -> {len(b['messages'])})"
                        break
            if reason:
                why[(r["family"], reason)] += 1
                continue
            fam_kept[r["family"]] += 1
            for c in r["calls"]:
                for m in c.get("messages") or []:
                    m["content"] = calc_fix(m["content"])
            r["rerendered"] = args.squiggle
            kept_recs.append(r)
        with gzip.open(out / f"{name}.jsonl.gz", "wt") as f:
            for r in kept_recs:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        md += [f"## {name}: {len(kept_recs)} of {len(recs)} kept episodes kept (calculate description updated; "
               f"{sum(rerendered.values())} plain chat / personal calls re-rendered: {dict(rerendered)})", "",
               "| family | unchanged | of |", "| --- | --- | --- |"]
        md += [f"| {fam} | {fam_kept[fam]} | {fam_n[fam]} |" for fam in sorted(fam_n)]
        md += ["", "Dropped:", ""] + [f"- {n} × {fam}: {reason}" for (fam, reason), n in why.most_common()] + [""]
        print(f"{name}: {len(kept_recs)}/{len(recs)} unchanged; dropped {sum(why.values())}", flush=True)
    (out / "RERENDER.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
