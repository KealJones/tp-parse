"""Check episodes.jsonl: references, ids, timestamps, placeholders, and which run steps actually run.

  python3 validate.py            structural checks
  python3 validate.py --run      also run every `run` step with node (needs Node 22.6+ for .ts)
"""
import json, pathlib, re, subprocess, sys, tempfile

HERE = pathlib.Path(__file__).parent
ACTIONS = {"think", "search", "memory", "run", "ask", "fact", "assume", "need", "todo", "done", "idea", "drop", "draft", "check", "answer"}
OBS = {"result", "reply", "harness"}
PROV = {"recorded", "condensed", "reconstructed", "added"}


def secs(t):
    m, s = t.split(":")
    return int(m) * 60 + int(s)


def check(ep):
    errs, ids, keys, todos, ideas = [], {}, set(), {}, {}
    last_t = -1
    for i, x in enumerate(ep["events"]):
        where = f"{ep['id']}[{i}] {x['kind']}"
        k = x["kind"]
        if k not in ACTIONS | OBS:
            errs.append(f"{where}: unknown kind")
        if x.get("prov") not in PROV:
            errs.append(f"{where}: bad prov {x.get('prov')}")
        if x["trained"] != (k not in OBS):
            errs.append(f"{where}: trained flag wrong")
        if x.get("t"):
            if secs(x["t"]) < last_t:
                errs.append(f"{where}: time goes backwards ({x['t']})")
            last_t = secs(x["t"])
        if k in ("search", "memory", "run", "ask", "todo", "idea"):
            if x["id"] in ids:
                errs.append(f"{where}: duplicate id {x['id']}")
            ids[x["id"]] = k
        if k in ("result", "reply") and x.get("to") not in ids:
            errs.append(f"{where}: refers to unknown {x.get('to')}")
        if k in ("fact", "assume", "need"):
            keys.add(x["key"])
        if k == "fact" and x.get("source") not in ids and x.get("source") != "request":
            errs.append(f"{where}: unknown source {x.get('source')}")
        for a in x.get("assumes", []) if k in ("fact", "idea") else []:
            if a not in keys and not any(e.get("key") == a for e in ep["events"][i:] if e["kind"] == "need"):
                errs.append(f"{where}: assumes unknown key {a}")
        if k == "todo":
            todos[x["id"]] = True
        if k == "done":
            if x["id"] not in todos:
                errs.append(f"{where}: closes unknown todo {x['id']}")
            todos[x["id"]] = False
        if k == "idea":
            ideas[x["id"]] = True
        if k == "drop" and x["id"] not in ideas:
            errs.append(f"{where}: drops unknown idea {x['id']}")
        if x["trained"]:
            text = " ".join(str(v) for kk, v in x.items() if kk in ("text", "query", "code", "value"))
            if re.search(r"\.\.\.(?![\w(])|\[[a-z]+ [a-z ]+\]|\(same|\{ \.\.\.", text) and k not in ("think",):
                errs.append(f"{where}: placeholder or elision in a trained event")
    for td, still in todos.items():
        if still:
            errs.append(f"{ep['id']}: todo {td} never closed")
    if ep["events"][-1]["kind"] != "answer":
        errs.append(f"{ep['id']}: does not end with an answer")
    return errs


def run_all(ep):
    out = []
    for i, x in enumerate(ep["events"]):
        if x["kind"] != "run":
            continue
        with tempfile.NamedTemporaryFile("w", suffix=".ts", delete=False) as f:
            f.write(x["code"])
        r = subprocess.run(["node", "--experimental-strip-types", "--no-warnings", f.name], capture_output=True, text=True)
        got = (r.stdout + r.stderr).strip()
        want = next((e["text"] for e in ep["events"] if e["kind"] == "result" and e.get("to") == x["id"]), "")
        first = (got.splitlines() or [""])[0] if r.returncode else got
        ok = (want.strip() == got) or (r.returncode and want.split(":")[0] in got) or (want == "(no output)" and got == "")
        out.append(f"  {x['id']} ({x['prov']}): {'ok' if ok else 'MISMATCH'}" + ("" if ok else f"\n    want: {want[:120]!r}\n    got:  {first[:120]!r}"))
    return out


if __name__ == "__main__":
    eps = [json.loads(l) for l in (HERE / "episodes.jsonl").read_text().splitlines()]
    ids = [e["id"] for e in eps]
    all_errs = [f"duplicate episode id {i}" for i in set(ids) if ids.count(i) > 1]
    for ep in eps:
        all_errs += check(ep)
    print("\n".join(all_errs) or f"ok: {len(eps)} episodes, {sum(len(e['events']) for e in eps)} events, no structural problems")
    if "--run" in sys.argv:
        for ep in eps:
            r = run_all(ep)
            if r:
                print(ep["id"])
                print("\n".join(r))
    sys.exit(1 if all_errs else 0)
