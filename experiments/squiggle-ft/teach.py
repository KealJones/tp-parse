"""Step-wise teacher CLI: a Claude agent plays Squiggle's phone model, one model call at a time, inside the real
harness (sq/driver.mjs runs app/src unchanged). See TEACHER.md. `node teach.mjs …` runs this file.

  teach start <family> <n> --out DIR        claim n fresh episodes of a family; prints their ids
  teach next <id> [--out DIR] [--json] [--refresh]  what the phone model sees for its next call (rendered Gemma chat),
                                            or NEED TOOL RESULT, or DONE + the checker's verdict
  teach reply <id> <file> [--out DIR]       give the model's output for that call; it is checked against the quality
                                            bar first (rejected outputs are not stored), then the harness and tools run
                                            until the next model call, which is printed
  teach tool-result <id> <file> [--key K]   supply a web result the sandbox couldn't fetch (page text for a URL, or a
                                            JSON list of {title, url, snippet} for a search), then continue
  teach undo <id>                           take back your last output (e.g. after a double reply)
  teach show <id>                           the transcript so far;   teach drop <id> [reason]   give up on an episode
  teach families                            families, habits and target counts;   teach status --out DIR   progress

Episodes live in DIR/<id>/episode.json (spec, the outputs so far, the pending call). Each command replays the episode
from the start with the stored outputs (tools are cached, so this is quick and gives the same results), so any number
of agents can work in parallel, one process per command. Kept episodes' calls go to DIR/kept_examples.jsonl.
"""
import argparse, fcntl, gzip, hashlib, json, os, sys, time
from contextlib import contextmanager
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import families as F
import quality as Q
from sqrun import Episode, Runner

WORK = Path(os.environ.get("SQFT_WORK", HERE / "work"))
SQUIGGLE = os.environ.get("SQUIGGLE_DIR", str(HERE / "squiggle"))
DEFAULT_OUT = Path(os.environ.get("SQFT_TEACH_OUT", HERE / "teach_out"))

# Target episode counts per family for the Claude teachers (held-out families are never taught).
TARGETS = {"web_fact": 90, "web_compare": 70, "math": 70, "hermes_compute": 40, "hermes_need": 40, "repo_fact": 80,
           "repo_where": 70, "repo_two": 50, "recipe_repo": 40, "need_repo": 50, "memory_repo": 35, "past_chat": 40,
           "refs": 40, "chat": 50, "chat_after": 30, "bare_link": 35}


class Pause(Exception):
    """The harness needs a model call that hasn't been written yet."""


class Replay:
    def __init__(self, outputs):
        self.outputs, self.pending = outputs, None

    async def generate_one(self, req):
        i = req["index"]
        if i < len(self.outputs):
            return self.outputs[i]
        self.pending = req
        raise Pause()


@contextmanager
def locked(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def pool(family, n_needed):
    """The family's deterministic episode pool (the same in every process)."""
    import build
    src = build.load_sources(WORK, "train")
    eps = build.make_sets(src, {family: max(n_needed, 1)}, seed=1000 + sorted(build.TRAIN_PLAN).index(family) if family in build.TRAIN_PLAN else 999)
    return [e for e in eps if e.family == family]


def user_script(ep):
    """The simulated user's later messages, fixed now so every replay sees the same ones."""
    out = []
    if not ep.user:
        return out
    for k in range(ep.max_turns - 1):
        a = ep.user({"n": k, "waiting": True, "asked": True, "reply": ""}, ep)
        if not a:
            break
        b = ep.user({"n": k, "waiting": False, "asked": False, "reply": ""}, ep)
        text, session = (a, None) if isinstance(a, str) else a
        out.append({"text": text, "session": session, "when": "always" if b else "asked"})
    return out


def episode_path(out, eid):
    return Path(out) / eid / "episode.json"


def load(out, eid):
    p = episode_path(out, eid)
    if not p.exists():
        sys.exit(f"No episode {eid} in {out}. Start some with: teach start <family> <n> --out {out}")
    return json.loads(p.read_text())


def save(out, ep):
    p = episode_path(out, ep["id"])
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(ep, ensure_ascii=False, indent=1))
    os.replace(tmp, p)


def as_episode(ep):
    script = ep.get("user_turns", [])

    def user(turn, e):
        k = turn["n"]
        if k >= len(script):
            return None
        s = script[k]
        if s["when"] == "asked" and not (turn.get("asked") or turn.get("waiting")):
            return None
        return (s["text"], s["session"]) if s.get("session") else s["text"]
    return Episode(id=ep["id"], family=ep["family"], first=ep["first"], world=ep["world"], gold=ep["gold"], user=user,
                   meta={**ep.get("meta", {}), "noNet": ep.get("noNet", [])}, max_turns=4)


def replay(out, ep):
    """Runs the episode with the stored outputs; returns ('pending', req), ('missing', keys) or ('done', result)."""
    backend = Replay(ep["outputs"])
    runner = Runner(backend, SQUIGGLE, WORK, concurrency=1, batch_wait=0, max_calls=40)
    res = runner.run([as_episode(ep)])[0]
    if backend.pending is not None:
        req = backend.pending
        miss = [m for m in req.get("missing") or [] if m["key"] not in ep.get("supplied", [])]
        if miss:
            ep["noNet"] = sorted(set(ep.get("noNet", [])) | {m["key"] for m in miss if m["kind"] == "url"})
            return "missing", miss
        return "pending", {"index": req["index"], "kind": req["kind"], "turn": req["turn"], "messages": req["messages"]}
    if res.get("error") and "Pause" not in res["error"]:
        return "error", res
    return "done", res


def advance(out, ep):
    """Replay and record where the episode stands."""
    state, val = replay(out, ep)
    if state == "pending":
        ep.update(status="open", pending=val, missing=[])
    elif state == "missing":
        ep.update(status="needs_tool_result", missing=val, pending=None)
    elif state == "error":
        ep.update(status="error", pending=None, error=val.get("error"))
    else:
        res = val
        res["check"] = F.check(res)
        ep.update(status="kept" if res["check"]["strict"] else "dropped", pending=None, check=res["check"],
                  replies=[t.get("reply") for t in res.get("turns", [])])
        (Path(out) / ep["id"] / "result.json").write_text(json.dumps(res, ensure_ascii=False))
        if res["check"]["strict"]:
            import build
            exs = list(build.examples(res))
            with locked(Path(out) / ".kept.lock"):
                with open(Path(out) / "kept_examples.jsonl", "a") as f:
                    for x in exs:
                        f.write(json.dumps(x, ensure_ascii=False) + "\n")
            ep["examples"] = len(exs)
    save(out, ep)
    return ep


_tok = None


def render(messages):
    global _tok
    try:
        if _tok is None:
            from transformers import AutoTokenizer
            _tok = AutoTokenizer.from_pretrained("unsloth/gemma-3-270m-it")
        return _tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    except Exception:
        # Same layout as Gemma 3's template, written out (system folded into the first user turn).
        parts, sys_ = [], ""
        for m in messages:
            if m["role"] == "system":
                sys_ = m["content"] + "\n\n"
                continue
            role = "model" if m["role"] == "assistant" else "user"
            parts.append(f"<start_of_turn>{role}\n{(sys_ if role == 'user' and sys_ else '')}{m['content']}<end_of_turn>\n")
            if role == "user":
                sys_ = ""
        return "<bos>" + "".join(parts) + "<start_of_turn>model\n"


HOW = {
    "request": "a NEW REQUEST. Thinking lines, in order: Request: / Pieces: / Know: / Don't know: / Goal: / Plan: or Next:",
    "step_start": "the START OF A STEP. Thinking lines, in order: Step: / Know: / Next:",
    "after_result": "a TOOL RESULT. Thinking lines, in order: Check: / Next:",
    "final": "the FINAL REPLY (every step is done). Thinking line: Answer: ; then the reply (no tool call), citing sources",
    "chat_plain": "PLAIN CHAT. One or two short thinking lines, no labels; then a short normal reply, no tools",
}


def show_state(out, ep, as_json=False):
    eid = ep["id"]
    st = ep.get("status")
    if st in ("kept", "dropped"):
        c = ep.get("check", {})
        print(f"DONE {eid}: {'KEPT' if st == 'kept' else 'DROPPED'} ({ep.get('examples', 0)} training examples)")
        if c.get("reasons"):
            print("Checker: " + "; ".join(c["reasons"]))
        for i, r in enumerate(ep.get("replies") or []):
            print(f"Reply {i + 1}: {r}")
        return
    if st == "error":
        print(f"ERROR {eid}: the harness failed: {ep.get('error', '')[:800]}\nRun: teach drop {eid} 'harness error'")
        return
    if st == "dropped_by_teacher":
        print(f"DROPPED {eid} by the teacher: {ep.get('drop_reason')}")
        return
    if st == "needs_tool_result":
        print(f"NEED TOOL RESULT {eid}: the sandbox couldn't fetch this for the tool call you just made.")
        for m in ep["missing"]:
            if m["kind"] == "url":
                print(f"  page: {m['url']}\n    Fetch it (WebFetch), save the page's text to a file, then: node teach.mjs tool-result {eid} <file> --key '{m['key']}'")
            else:
                print(f"  web search: {m['query']}\n    Search it (WebSearch), save a JSON list of up to 8 results [{{\"title\", \"url\", \"snippet\"}}] (real results only), then: node teach.mjs tool-result {eid} <file> --key '{m['key']}'")
        return
    p = ep["pending"]
    fam = ep["family"]
    plain = (fam, p["turn"]) in F.PLAIN
    ck = Q.call_kind(p["messages"], p["kind"], plain)
    if as_json:
        print(json.dumps({"id": eid, "family": fam, "call": p["index"] + 1, "kind": p["kind"], "answering": ck, "messages": p["messages"]}, ensure_ascii=False, indent=1))
        return
    tools = sorted(Q.looked_up(p["messages"]))
    print(f"EPISODE {eid} ({fam}) — model call {p['index'] + 1}, {p['kind']} phase, user turn {p['turn'] + 1}")
    print(f"You are answering {HOW[ck]}.")
    print(f"Tools looked up so far: {', '.join(tools) if tools else 'none (call find to look tools up)'}")
    print("=" * 30 + " what the phone model reads (Gemma 3 chat template) " + "=" * 30)
    print(render(p["messages"]))
    print("=" * 30 + " end " + "=" * 30)
    print(f"Write your output (starting with <think>) to a file, then: node teach.mjs reply {eid} <file>")


def cmd_start(a):
    out = Path(a.out)
    if a.family not in TARGETS:
        sys.exit(f"Unknown or held-out family {a.family}. Families: {', '.join(TARGETS)}")
    with locked(out / ".registry.lock"):
        reg_p = out / "registry.json"
        reg = json.loads(reg_p.read_text()) if reg_p.exists() else {}
        taken = set(reg.get(a.family, []))
        eps = pool(a.family, len(taken) + a.n + 10)
        fresh = [e for e in eps if e.id not in taken][:a.n]
        for e in fresh:
            ep = {"id": e.id, "family": e.family, "first": e.first, "world": e.world, "gold": e.gold, "meta": e.meta,
                  "user_turns": user_script(e), "outputs": [], "status": "new", "created": time.time()}
            save(out, ep)
        reg[a.family] = sorted(taken | {e.id for e in fresh})
        reg_p.write_text(json.dumps(reg, indent=1))
    for e in fresh:
        ep = advance(out, load(out, e.id))
        print(e.id)
    if len(fresh) < a.n:
        print(f"(only {len(fresh)} fresh {a.family} episodes were left)", file=sys.stderr)


def cmd_next(a):
    ep = load(a.out, a.id)
    if ep.get("status") in ("new", "error") or (a.refresh and ep.get("status") in ("open", "needs_tool_result")):
        ep = advance(a.out, ep)
    show_state(a.out, ep, a.json)


def cmd_reply(a):
    ep = load(a.out, a.id)
    if ep.get("status") != "open" or not ep.get("pending"):
        show_state(a.out, ep)
        sys.exit(1)
    text = Path(a.file).read_text()
    if text.endswith("\n") and not text.rstrip().endswith("```"):
        text = text.rstrip("\n")
    text = text.strip("\n")
    p = ep["pending"]
    plain = (ep["family"], p["turn"]) in F.PLAIN
    probs, _ = Q.output_problems(text, p["messages"], p["kind"], plain)
    if probs:
        print(f"REJECTED (not stored) — fix these and reply again:")
        for x in probs:
            print(f"  - {x}")
        sys.exit(2)
    if ep["outputs"] and ep["outputs"][-1] == text and p["index"] == len(ep["outputs"]):
        print("REJECTED (not stored): this is the same output as your last call. If you meant to look at the episode, use: node teach.mjs next " + ep["id"])
        sys.exit(2)
    if a.call and a.call != p["index"] + 1:
        print(f"REJECTED (not stored): the pending call is {p['index'] + 1}, not {a.call}.")
        sys.exit(2)
    ep["outputs"].append(text)
    save(a.out, ep)
    ep = advance(a.out, ep)
    show_state(a.out, ep)


def cmd_undo(a):
    ep = load(a.out, a.id)
    if not ep["outputs"]:
        sys.exit("Nothing to undo.")
    gone = ep["outputs"].pop()
    if ep.get("status") in ("kept", "dropped"):
        sys.exit("This episode is finished; start a new one instead.")
    save(a.out, ep)
    print("removed the last output:\n" + gone[:300])
    show_state(a.out, advance(a.out, ep))


def cmd_tool_result(a):
    ep = load(a.out, a.id)
    miss = ep.get("missing") or []
    if not miss:
        sys.exit("This episode isn't waiting for a tool result.")
    m = next((x for x in miss if x["key"] == a.key), None) if a.key else miss[0]
    if not m:
        sys.exit(f"No missing result with key {a.key}; it needs: {[x['key'] for x in miss]}")
    body = Path(a.file).read_text()
    if m["kind"] == "search":
        results = json.loads(body)
        assert isinstance(results, list) and all(isinstance(r, dict) and r.get("title") and r.get("url") for r in results), "a JSON list of {title, url, snippet}"
        entry = {"status": 200, "type": "application/json", "body": json.dumps([{"title": r["title"], "url": r["url"], "snippet": r.get("snippet", "")} for r in results][:10]), "url": m["key"]}
    else:
        entry = {"status": 200, "type": "text/plain; charset=utf-8", "body": body[:3_000_000], "url": m["url"]}
    cache = WORK / "net-cache"
    cache.mkdir(parents=True, exist_ok=True)
    f = cache / (hashlib.sha1(m["key"].encode()).hexdigest()[:24] + ".json")
    f.write_text(json.dumps(entry, ensure_ascii=False))
    ep["supplied"] = sorted(set(ep.get("supplied", [])) | {m["key"]})
    ep["noNet"] = [k for k in ep.get("noNet", []) if k != m["key"]]
    ep["missing"] = [x for x in miss if x["key"] != m["key"]]
    save(a.out, ep)
    if ep["missing"]:
        show_state(a.out, ep)
        return
    show_state(a.out, advance(a.out, ep))


def cmd_show(a):
    ep = load(a.out, a.id)
    print(f"{ep['id']} ({ep['family']}) status {ep.get('status')}\nFirst message: {ep['first']}")
    for i, o in enumerate(ep["outputs"]):
        print(f"--- output {i + 1}\n{o}")
    if ep.get("pending"):
        print("--- pending call:")
        show_state(a.out, ep)


def cmd_drop(a):
    ep = load(a.out, a.id)
    ep.update(status="dropped_by_teacher", drop_reason=a.reason or "", pending=None)
    save(a.out, ep)
    print(f"dropped {a.id}")


def cmd_families(a):
    import build
    for f, n in TARGETS.items():
        print(f"{f:16} {n:4}  {F.HABIT.get(f, '')}")
    print(f"{'total':16} {sum(TARGETS.values()):4}")
    print("held out (never taught): " + ", ".join(sorted(F.HELD_OUT)))


def cmd_status(a):
    import collections
    c = collections.Counter()
    for p in Path(a.out).glob("*/episode.json"):
        ep = json.loads(p.read_text())
        c[(ep["family"], ep.get("status"))] += 1
    fams = sorted({f for f, _ in c})
    for f in fams:
        row = {s: n for (ff, s), n in c.items() if ff == f}
        print(f"{f:16} target {TARGETS.get(f, 0):4}  " + "  ".join(f"{s} {n}" for s, n in sorted(row.items())))
    ex = Path(a.out) / "kept_examples.jsonl"
    print(f"kept examples: {sum(1 for _ in open(ex)) if ex.exists() else 0}")


def main():
    ap = argparse.ArgumentParser(prog="teach", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("start"); s.add_argument("family"); s.add_argument("n", type=int); s.add_argument("--out", default=str(DEFAULT_OUT))
    s = sp.add_parser("next"); s.add_argument("id"); s.add_argument("--out", default=str(DEFAULT_OUT)); s.add_argument("--json", action="store_true"); s.add_argument("--refresh", action="store_true", help="replay again first")
    s = sp.add_parser("reply"); s.add_argument("id"); s.add_argument("file"); s.add_argument("--out", default=str(DEFAULT_OUT)); s.add_argument("--call", type=int, help="the call number you are answering (a guard against double replies)")
    s = sp.add_parser("undo"); s.add_argument("id"); s.add_argument("--out", default=str(DEFAULT_OUT))
    s = sp.add_parser("tool-result"); s.add_argument("id"); s.add_argument("file"); s.add_argument("--key"); s.add_argument("--out", default=str(DEFAULT_OUT))
    s = sp.add_parser("show"); s.add_argument("id"); s.add_argument("--out", default=str(DEFAULT_OUT))
    s = sp.add_parser("drop"); s.add_argument("id"); s.add_argument("reason", nargs="?"); s.add_argument("--out", default=str(DEFAULT_OUT))
    sp.add_parser("families")
    s = sp.add_parser("status"); s.add_argument("--out", default=str(DEFAULT_OUT))
    a = ap.parse_args()
    {"start": cmd_start, "next": cmd_next, "reply": cmd_reply, "tool-result": cmd_tool_result, "show": cmd_show,
     "drop": cmd_drop, "undo": cmd_undo, "families": cmd_families, "status": cmd_status}[a.cmd](a)


if __name__ == "__main__":
    main()
