"""Negative tests for the checker (REVIEW_V2_FABLE.md). Every case here is a deliberately BAD output that the v1
checker accepted; each must now be rejected. The strings are checker fixtures, never training data: they are short,
wrong on purpose, and labelled. Most cases mutate a real kept teach-v1 episode mechanically (swap the reply, blank a
result, drop a call) so the fixture is the teacher's own text with one thing broken.

  python checker_tests.py          # needs hf-teach-2/teach/teacher_results.jsonl.gz for the episode cases
"""
import copy, gzip, json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import families as F
import quality as Q

FAILS = []


def expect(cond, name):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        FAILS.append(name)


def rejected(res, name, why=None):
    c = F.check(res)
    expect(not c["strict"] and (why is None or any(why in r for r in c["reasons"])), f"{name} -> {c['reasons'][:2]}")


def accepted(res, name):
    c = F.check(res)
    expect(c["strict"], f"{name} (must still pass) -> {c['reasons'][:2]}")


# ── quality.py: single-call rules ───────────────────────────────────────────
def unit():
    # done results that narrate (AUDIT_V1 problem 8: any capitalised word used to count as a fact)
    for bad in ["Tools located for the step", "Found the tools needed", "Ready for the next step", "Tools found: git_clone, read_file"]:
        expect(Q.validate_call("done", {"result": bad}), f"done narrates: {bad!r}")
    expect(not Q.validate_call("done", {"result": "version 6.0.1 (from /repos/chalk/package.json)"}), "done with facts passes")
    # plan steps that write the reply or "find the tools" (gemma-traces lesson 1)
    for bad in ["Draft the response", "Self-correct the reply", "Find the tools needed to clone the repo", "Summarize the answer for the user", "Review tone"]:
        expect(Q.validate_call("plan", {"goal": "g", "steps": ["Read package.json for the version", bad]}), f"plan meta step: {bad!r}")
    expect(not Q.validate_call("plan", {"goal": "g", "steps": ["Read package.json for the version", "Get the latest commit from the git log"]}), "plan of task actions passes")
    # calculate takes a plain expression
    for bad in ["const x = 3 * 4; console.log(x)", "12 apples * 3", "sqrt(16) => 4", "total"]:
        expect(Q.validate_call("calculate", {"expression": bad}), f"calculate rejects: {bad!r}")
    for good in ["15% of 240", "round((72 - 32) * 5 / 9, 1)", "$1,200 * 3", "2 x 3"]:
        expect(not Q.validate_call("calculate", {"expression": good}), f"calculate accepts: {good!r}")
    # citation shape (AUDIT_V1 problem 4)
    for bad in ["The answer is 42, from memory.", "crepes from Brittany are thin.", "yes and/or no.", "I ran it."]:
        expect(not Q.final_cites(bad), f"final_cites rejects: {bad!r}")
    for good in ["It is the euro (from the Wikipedia page Euro).", "version 6.0.1 (from its package.json)", "72110019 (from the git log)", "36 (calculated)"]:
        expect(Q.final_cites(good), f"final_cites accepts: {good!r}")
    # non-answers, hedges, negation (AUDIT_V1 problem 2 and new)
    for bad in ["Neither page confirmed it.", "That is not a recognized national park.", "No relevant results were found.", "The page doesn't say."]:
        expect(F.non_answer(bad), f"non_answer: {bad!r}")
    for bad in ["It's probably Paris.", "I believe it was 1989.", "Either Paris or Lyon, sources disagree."]:
        expect(F.hedged(bad), f"hedged: {bad!r}")
    expect(F.negated("It is not Paris; the page says Lyon.", ["Paris"]), "negated gold")
    expect(not F.negated("It is Paris, not Lyon.", ["Paris"]), "gold before the negation is fine")
    # licence as a whole word (AUDIT_V1 problem 3), path as a whole path
    expect(not F.check_repo_answer("license", {"license": "MIT"}, "I saw the latest commit (from the repo)."), "'commit' is not MIT")
    expect(F.check_repo_answer("license", {"license": "MIT"}, "chalk is MIT licensed (from its package.json)."), "MIT as a word")
    expect(not F.check_repo_answer("where", {"path": "src/index.js"}, "It's in test/fixtures/src/index.js (from grep)."), "same basename, other file")
    expect(F.check_repo_answer("where", {"path": "src/index.js"}, "It's in /repos/chalk/src/index.js line 8 (from grep)."), "path under /repos/<name>/")
    # web_compare pick (AUDIT_V1 problem 2)
    titles = ["Lawson (band)", "American Music Club"]
    expect(not F.picked("American Music Club has more members: 5 vs. Lawson's 4 (from Wikipedia).", "Lawson", titles), "names both, picks the other")
    expect(F.picked("Lawson has more members than American Music Club (from Wikipedia).", "Lawson", titles), "picks the gold")
    expect(not F.picked("American Music Club, not Lawson, has more members.", "Lawson", titles), "gold under a negation")
    # messy() keeps fillers out of a protected alias (AUDIT_V1 problem 7)
    import random
    bad = [F.messy(random.Random(s), "What's the latest commit in my agent project?", phrases=["my agent project"]) for s in range(200)]
    expect(all(re.search(r"my agent project", t) for t in bad), "no filler inside 'my agent project'")
    # chat lists are disjoint between train and eval (AUDIT_V1 problem 5)
    expect(not set(F.CHAT) & set(F.CHAT_EVAL), "CHAT and CHAT_EVAL are disjoint")
    for d in (F.NEED_REPO_ASKS, F.WHERE_ASKS, F.REFS_FIRST):
        expect(not set(d["train"]) & set(d["eval"]), "templates split train/eval")
    expect(not {a for v in F.MEM_ASK["train"].values() for a in v} & {a for v in F.MEM_ASK["eval"].values() for a in v}, "memory aliases split")


# ── families.py: whole-episode rules on mutated real episodes ───────────────
def set_reply(res, k, text):
    res = copy.deepcopy(res)
    res["turns"][k]["reply"] = text
    idx = sum(t["calls"] for t in res["turns"][:k + 1]) - 1
    out = res["calls"][idx]["output"]
    res["calls"][idx]["output"] = out.split("</think>")[0] + "</think>\n" + text
    return res


def blank_results(res, tool, text):
    res = copy.deepcopy(res)
    for c in res["calls"]:
        for m in c["messages"]:
            if m["role"] == "user" and m["content"].startswith("Result of " + tool):
                m["content"] = m["content"].split("\n")[0] + "\n" + text
    return res


def episodes():
    path = HERE / "hf-teach-2" / "teach" / "teacher_results.jsonl.gz"
    if not path.exists():
        print("skip episode cases: no", path)
        return None
    rows = [json.loads(l) for l in gzip.open(path, "rt")]
    kept = [r for r in rows if r["check"]["strict"]]
    return {f: [r for r in kept if r["family"] == f] for f in {r["family"] for r in kept}}


def episode_cases(by):
    # The kept v1 episodes that AUDIT_V1 named as wrong must now be rejected.
    ids = {r["id"]: r for rs in by.values() for r in rs}
    for eid in ["web_compare-24", "web_compare-38", "web_compare-57", "refs-21", "repo_two-12", "repo_two-15"]:
        if eid in ids:
            rejected(ids[eid], f"AUDIT_V1 case {eid}")
    # A: refs never required a lookup in either turn (new)
    r = by["refs"][0]
    m = copy.deepcopy(r)
    n0 = m["turns"][0]["calls"]
    m["calls"] = [m["calls"][n0 - 1]] + m["calls"][n0:]
    m["turns"][0]["calls"] = 1
    rejected(m, "refs: turn 0 answers with no tool call", "without looking at the repo")
    # B: repo_where accepted another file with the same basename and parent (new)
    r = next(x for x in by["repo_where"] if x["gold"]["path"].count("/") >= 1)
    p = r["gold"]["path"]
    rejected(set_reply(r, 0, r["turns"][0]["reply"].replace(p, "test/fixtures/" + p)), "repo_where: other file, same basename", "wrong or missing")
    # C: hedged, listed, negated answers (new)
    r = next(x for x in by["web_fact"] if len(x["gold"]["answers"][0].split()) <= 2)
    g = r["gold"]["answers"][0]
    rejected(set_reply(r, 0, f"It's probably {g}, I believe (Wikipedia)."), "web_fact: hedged", "hedged")
    rejected(set_reply(r, 0, f"It is either {g} or Zanzibar, the sources disagree (from Wikipedia)."), "web_fact: candidates", "hedged")
    rejected(set_reply(r, 0, f"It is not {g}; the page says otherwise (from Wikipedia)."), "web_fact: negated", "wrong or missing")
    # D: the answer is in no tool result (AUDIT_V1 problem 1); every result an error (new)
    m = copy.deepcopy(r)
    for c in m["calls"]:
        for msg in c["messages"]:
            if msg["role"] == "user" and msg["content"].startswith("Result of"):
                msg["content"] = re.sub(re.escape(g), "XXXX", msg["content"], flags=re.I)
    rejected(m, "web_fact: answer in no result", "no tool result")
    rejected(blank_results(r, "", '{"error":"fetch failed: HTTP 503"}'), "web_fact: all results are errors", "no tool result")
    # R, S: the answer appears in the model's own text before any result has it (new)
    r = by["web_fact"][2]
    g = r["gold"]["answers"][0]
    m = copy.deepcopy(r)
    m["calls"][0]["output"] = re.sub(r"(?m)^Know:.*$", f"Know: the answer is {g}.", m["calls"][0]["output"], count=1)
    rejected(m, "web_fact: answer in the first Know line", "before any tool result")
    m = copy.deepcopy(r)
    for c in m["calls"]:
        if '"name": "web_search"' in c["output"]:
            c["output"] = re.sub(r'"query": "([^"]*)"', lambda mm: f'"query": "{mm.group(1)} {g}"', c["output"])
    rejected(m, "web_fact: answer inside the search query", "before any tool result")
    # H: math with an empty run_js result, and run_js at all (CORPUS_V2 §2h)
    r = by["math"][0]
    rejected(blank_results(r, "run_js", '{"stdout":"","result":null}'), "math: run_js printed nothing", "calculate")
    rejected(r, "math: computes via run_js", "run_js")
    # J: a guessed repo inside the need question (TEACHER.md habit 1, never enforced)
    r = by["need_repo"][0]
    m = copy.deepcopy(r)
    for c in m["calls"]:
        if '"name": "need"' in c["output"]:
            c["output"] = re.sub(r'"what": "([^"]*)"', f'"what": "Do you mean {r["gold"]["repo"]}? Which repo?"', c["output"])
    m["turns"][0]["reply"] = f"Do you mean {r['gold']['repo']}? Which repo?"
    rejected(m, "need_repo: need question names a repo", "guess inside a question")
    # N: a bare_link summary that isn't from the page (new)
    r = by["bare_link"][0]
    rejected(set_reply(r, 0, f"The page is the Wikipedia article on {r['gold']['title']}. It has an introduction, a history section and references."),
             "bare_link: boilerplate summary", "isn't from the page")
    # Q: a Check line that restates the request (AUDIT_V1 problem 8)
    r = by["web_fact"][0]
    m = copy.deepcopy(r)
    m["calls"][-1]["output"] = re.sub(r"(?m)^Check:.*$", "Check: the user asked " + m["first"][:60].replace("\n", " "), m["calls"][-1]["output"], count=1)
    rejected(m, "web_fact: Check restates the request", "Check line")
    # T: a version answered after read_file errored (new)
    r = next(x for x in by["repo_fact"] if x["gold"]["kind"] == "version")
    rejected(blank_results(r, "read_file", '{"error":"ENOENT: no such file"}'), "repo_fact: read_file errored", "no tool result")
    # Plan on a one-fact request (AUDIT_V1 problem 8; CORPUS_V2 plan rule)
    r = by["web_fact"][3]
    m = copy.deepcopy(r)
    first = m["calls"][0]
    first["output"] = first["output"].split("```tool_call")[0] + '```tool_call\n{"name": "plan", "arguments": {"goal": "g", "steps": ["Search the web", "Read the page"]}}\n```'
    rejected(m, "web_fact: plan for one lookup", "one-lookup")
    # Still accepted: clean kept episodes of every family that v2 keeps (no false rejections on these)
    for fam in ["web_fact", "repo_fact", "need_repo", "chat", "bare_link", "recipe_repo"]:
        accepted(next(r for r in by[fam] if F.check(r)["strict"]), f"a clean {fam} episode")


if __name__ == "__main__":
    unit()
    by = episodes()
    if by:
        episode_cases(by)
    print(f"\n{len(FAILS)} failing" if FAILS else "\nall checker tests pass")
    sys.exit(1 if FAILS else 0)
