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


# ── v2 families: synthetic negative cases (labelled fixtures, never training data) ────────────────────────────────
SYS = ("You are Squiggle (checker fixture).\n\nTools you have looked up:\n- web_search(query)\n- fetch_url(url)\n- calculate(expression)\n"
       "- read_file(path, start_line?, end_line?)\n- grep(pattern, path?)\n- git_clone(repo)\n- git_log(repo, count?)\n")


def out(lines, name=None, args=None, reply=None):
    t = "<think>\n" + "\n".join(lines) + "\n</think>\n"
    return t + ("```tool_call\n" + json.dumps({"name": name, "arguments": args}) + "\n```" if name else reply)


def synth(fam, first, gold, turns, system=SYS):
    """turns: [{"user", "calls": [(output, result_name, result_obj)], "reply", "asked"}] -> an episode result."""
    res = {"id": f"{fam}-fixture", "family": fam, "first": first, "gold": gold, "meta": {}, "turns": [], "calls": []}
    convo = [{"role": "system", "content": system}]
    for t in turns:
        convo.append({"role": "user", "content": t["user"]})
        for o, rname, robj in t["calls"]:
            res["calls"].append({"kind": "chat", "messages": copy.deepcopy(convo), "output": o})
            convo.append({"role": "assistant", "content": o})
            if rname:
                convo.append({"role": "user", "content": f"Result of {rname}:\n" + json.dumps(robj)})
        res["turns"].append({"reply": t.get("reply", ""), "calls": len(t["calls"]), "asked": t.get("asked", False)})
    return res


REQ = ["Request: fixture.", "Pieces: 1. fixture.", "Know: nothing.", "Don't know: the answer.", "Goal: answer.", "Next: act."]
CHK = ["Check: fixture result.", "Next: answer."]


def v2_cases():
    # web_fact_retry: one lookup only
    r = synth("web_fact_retry", "When did the cubs win a world series?", {"answers": ["1908"]}, [{"user": "When did the cubs win a world series?", "calls": [
        (out(REQ, "web_search", {"query": "cubs world series"}), "web_search", {"results": "1. Chicago Cubs: won the World Series in 1908"}),
        (out(["Check: result 1 says won the World Series in 1908.", "Next: answer."], reply="1908 (from the web search)."), None, None)],
        "reply": "1908 (from the web search)."}])
    rejected(r, "web_fact_retry: one lookup", "only one lookup")
    # need_web: searched without asking
    r = synth("need_web", "when did that come out?", {"answers": ["2001"], "question": "When did X come out?"}, [{"user": "when did that come out?", "calls": [
        (out(REQ, "web_search", {"query": "release date"}), "web_search", {"results": "nothing"}),
        (out(CHK, reply="I couldn't tell."), None, None)], "reply": "I couldn't tell."}])
    rejected(r, "need_web: searched without asking", "didn't ask what they meant")
    # need_web: the need question guesses the answer
    r = synth("need_web", "who sang that one?", {"answers": ["Merry Clayton"], "question": "Who sings gimme shelter?"}, [{"user": "who sang that one?", "calls": [
        (out(REQ, "need", {"what": "Do you mean Merry Clayton's song?"}), None, None)], "reply": "Do you mean Merry Clayton's song?", "asked": True}])
    rejected(r, "need_web: guess inside the need question", "guesses the answer")
    # math_pair complete: asked although complete
    r = synth("math_pair", "Ann has 4 apples and buys 3 more. How many?", {"answer": "7", "variant": "complete"}, [{"user": "Ann has 4 apples and buys 3 more. How many?", "calls": [
        (out(REQ, "need", {"what": "How many apples?"}), None, None)], "reply": "How many apples?", "asked": True}])
    rejected(r, "math_pair complete: asked anyway", "asked the user although")
    # math_pair incomplete: computed before asking
    r = synth("math_pair", "Ann has some apples and buys 3 more. How many?", {"answer": "7", "missing": "4", "variant": "incomplete"}, [{"user": "Ann has some apples and buys 3 more. How many?", "calls": [
        (out(REQ, "calculate", {"expression": "4 + 3"}), "calculate", {"expression": "4 + 3", "result": 7}),
        (out(CHK, reply="7 apples (calculated)."), None, None)], "reply": "7 apples (calculated)."}])
    rejected(r, "math_pair incomplete: assumed the missing number", "didn't ask for the missing number")
    # lookup_then_compute: calculate on numbers no result gave
    r = synth("lookup_then_compute", "how many years apart were A Person and B Person born?", {"titles": ["A Person", "B Person"]}, [{"user": "how many years apart were A Person and B Person born?", "calls": [
        (out(REQ, "web_search", {"query": "A Person born"}), "web_search", {"results": "A Person (born 12 May 1950) is a writer. B Person (born 3 June 1961) is a singer."}),
        (out(CHK, "calculate", {"expression": "1962 - 1949"}), "calculate", {"expression": "1962 - 1949", "result": 13}),
        (out(CHK, reply="13 years (calculated from Wikipedia)."), None, None)], "reply": "13 years (calculated from Wikipedia)."}])
    rejected(r, "lookup_then_compute: numbers not from results", "doesn't use both looked-up birth years")
    # repo_chain: read a different file
    r = synth("repo_chain", "in x/y, what's on the line after foo is defined?", {"repo": "x/y", "name": "foo", "path": "src/a.js", "line": 9, "text": "return bar(baz);"}, [{"user": "in x/y, what's on the line after foo is defined?", "calls": [
        (out(REQ, "read_file", {"path": "/repos/y/src/b.js", "start_line": 9, "end_line": 9}), "read_file", {"content": "9: return bar(baz);"}),
        (out(CHK, reply="It says return bar(baz); (from src/b.js)."), None, None)], "reply": "It says return bar(baz); (from src/b.js)."}])
    rejected(r, "repo_chain: read another file", "never read the file that defines it")
    # messy_multi: dropped the version part
    r = synth("messy_multi", "who wrote hamlet and also whats the version of x/y", {"answers": ["Shakespeare"], "repo": "x/y", "version": "1.2.3"}, [{"user": "who wrote hamlet and also whats the version of x/y", "calls": [
        (out(REQ, "web_search", {"query": "hamlet author"}), "web_search", {"results": "1. Hamlet, by William Shakespeare"}),
        (out(["Check: result 1 says by William Shakespeare.", "Next: answer."], reply="Shakespeare wrote it (from the web search)."), None, None)], "reply": "Shakespeare wrote it (from the web search)."}])
    rejected(r, "messy_multi: one part dropped", "the version part is missing")
    # recipe_web / recipe_compute: no recipe in the prompt
    r = synth("recipe_web", "Who was born first, A or B?", {"answer": "A", "titles": ["A", "B"], "type": "comparison"}, [{"user": "Who was born first, A or B?", "calls": [
        (out(REQ, reply="A."), None, None)], "reply": "A."}])
    rejected(r, "recipe_web: no recipe seen", "recipe didn't reach the prompt")
    r = synth("recipe_compute", "how many years apart were A and B born?", {"titles": ["A", "B"]}, [{"user": "how many years apart were A and B born?", "calls": [
        (out(REQ, reply="10."), None, None)], "reply": "10."}])
    rejected(r, "recipe_compute: no recipe seen", "recipe didn't reach the prompt")
    # recipe_skip: gives the version too
    rs = SYS + "\n## Recipe from a similar task\n1. Clone <repo> and read the version\n2. Get the latest commit\n"
    r = synth("recipe_skip", "who made the latest commit in x/y", {"kind": "latest_author", "repo": "x/y", "version": "1.2.3", "answers": ["Ann Lee"]}, [{"user": "who made the latest commit in x/y", "calls": [
        (out(REQ, "git_log", {"repo": "y", "count": 1}), "git_log", {"commits": "abcd1234 2026-01-01 Ann Lee: fix"}),
        (out(["Check: the log says Ann Lee.", "Next: answer."], reply="Ann Lee made the latest commit, and x/y is at version 1.2.3 (from the git log)."), None, None)],
        "reply": "Ann Lee made the latest commit, and x/y is at version 1.2.3 (from the git log)."}], system=rs)
    rejected(r, "recipe_skip: did the unasked step", "gives the version")
    # near_miss: silently corrected
    r = synth("near_miss", "whats the best way to clean a lasabna dish", {"miss": "lasabna", "real": "lasagna"}, [{"user": "whats the best way to clean a lasabna dish", "calls": [
        (out(REQ, reply="Soak the lasagna dish in hot soapy water first."), None, None)], "reply": "Soak the lasagna dish in hot soapy water first."}])
    rejected(r, "near_miss: silently autocorrected", "never names the user's word")
    # chat_mid: tools on the chat turn
    r = synth("chat_mid", "Who wrote Hamlet?", {"answers": ["Shakespeare"]}, [
        {"user": "Who wrote Hamlet?", "calls": [(out(REQ, "web_search", {"query": "hamlet author"}), "web_search", {"results": "1. Hamlet, by William Shakespeare"}),
                                                 (out(["Check: result 1 says by William Shakespeare.", "Next: answer."], reply="Shakespeare (from the web search)."), None, None)],
         "reply": "Shakespeare (from the web search)."},
        {"user": "lol nice", "calls": [(out(["A casual reply."], "web_search", {"query": "lol"}), "web_search", {"results": ""}),
                                        (out(["Plain."], reply="Ha!"), None, None)], "reply": "Ha!"}])
    rejected(r, "chat_mid: tools on a chat turn", "called tools for plain chat")
    # personal_mid: tools on the personal turn
    r = synth("personal_mid", "Who wrote Hamlet?", {"answers": ["Shakespeare"], "ask": False}, [
        {"user": "Who wrote Hamlet?", "calls": [(out(REQ, "web_search", {"query": "hamlet author"}), "web_search", {"results": "1. Hamlet, by William Shakespeare"}),
                                                 (out(["Check: result 1 says by William Shakespeare.", "Next: answer."], reply="Shakespeare (from the web search)."), None, None)],
         "reply": "Shakespeare (from the web search)."},
        {"user": "thanks. my boss keeps nagging me, what do i do", "calls": [(out(["Request: a nagging boss.", "Need: options."], "web_search", {"query": "nagging boss"}), "web_search", {"results": ""}),
                                                                             (out(["Request: a nagging boss.", "Need: options."], reply="That sounds draining. " * 4), None, None)],
         "reply": "That sounds draining. " * 4}])
    rejected(r, "personal_mid: tools on the personal turn", "called tools for a personal request")
    # personal_tool: answered from memory
    r = synth("personal_tool", "for my dad's card: who wrote Hamlet?", {"answers": ["Shakespeare"]}, [{"user": "for my dad's card: who wrote Hamlet?", "calls": [
        (out(REQ, reply="Shakespeare wrote it, a lovely pick for his card!"), None, None)], "reply": "Shakespeare wrote it, a lovely pick for his card!"}])
    rejected(r, "personal_tool: no lookup", "answered without looking it up")
    # need_schedule: invented a day
    r = synth("need_schedule", "can you move my meeting with sam", {}, [{"user": "can you move my meeting with sam", "calls": [
        (out(REQ, reply="Done, I moved it to Friday at 3pm."), None, None)], "reply": "Done, I moved it to Friday at 3pm."}])
    rejected(r, "need_schedule: invented a day and claimed it acted", "didn't ask for the day")
    # make_sets: train and eval templates are disjoint for the new families
    for d in (F.VAGUE, F.LTC_ASKS, F.CHAIN_ASKS, F.JOIN, F.NEAR_ASKS):
        tr = {x for v in (d["train"].values() if isinstance(d["train"], dict) else [d["train"]]) for x in v}
        ev = {x for v in (d["eval"].values() if isinstance(d["eval"], dict) else [d["eval"]]) for x in v}
        expect(not tr & ev, "v2 templates split train/eval")
    if F.near_rows("train") and F.near_rows("eval"):
        expect(not {r["miss"] for r in F.near_rows("train")} & {r["miss"] for r in F.near_rows("eval")}, "near-miss words split")


def constant_cases():
    """pi and e go in as constants (f54bbf7: calculate's description says it knows them)."""
    r = synth("math_pair", "A circle has a radius of 10 feet. What is its area?", {"answer": "314.159", "variant": "complete"},
              [{"user": "A circle has a radius of 10 feet. What is its area?", "calls": [
                  (out(REQ, "calculate", {"expression": "3.14 * 10^2"}), "calculate", {"expression": "3.14 * 10^2", "result": 314}),
                  (out(['Check: calculate gave "314".', "Next: answer."], reply="About 314 square feet (calculated)."), None, None)],
                "reply": "About 314 square feet (calculated)."}])
    rejected(r, "pi typed in as 3.14", "approximates pi")
    for bad in ["22/7 * 7^2", "2.71828 ^ 2", "3.14159 * 4"]:
        seg = [{"parsed": {"calls": [{"name": "calculate", "arguments": {"expression": bad}}]}, "messages": []}]
        expect(F.approx_constants(seg) != [], f"approx constant caught: {bad!r}")
    for ok, req in [("pi * 10^2", ""), ("e ^ 2", ""), ("3.14 * 10^2", "use 3.14 for pi"), ("13.145 + 2", "")]:
        seg = [{"parsed": {"calls": [{"name": "calculate", "arguments": {"expression": ok}}]}, "messages": []}]
        expect(F.approx_constants(seg, req) == [], f"constant ok: {ok!r} (request {req!r})")


def grounding_cases(by):
    """Every name, number and quote in a reply or done result comes from the turn (coordinator's audit of the v2
    smoke: need_web-1 named "the Iroquois Confederacy", which no prompt or result had, and passed on its gold)."""
    idx = F.source_index(["Lynda Carter starred in Wonder Woman (1975\u20131979). Revenue was $1,683,000 in the 2026\u201327 season."])
    expect(F.unsourced_facts("Lynda Carter played her, 1975 to 1979.", idx) == [], "grounding: names and a dashed year range pass")
    expect(F.unsourced_facts("About 1.68 million, in 2027.", idx) == [], "grounding: a scaled number and a short season pass")
    expect(F.unsourced_facts("It aired from 1975 with Gal Gadot.", idx) == ["name Gal", "name Gadot"], "grounding: a name from nowhere")
    expect(F.unsourced_facts("It ran 1975 to 1981.", idx) == ["number 1981"], "grounding: a number from nowhere")
    expect(F.unsourced_facts('The page says "Carter starred in Batman".', idx) [:1] == ['quote "Carter starred in Batman"'], "grounding: a quote the page lacks")
    expect(F.unsourced_facts("Hey! Sure, from Wikipedia and the git log.", idx) == [], "grounding: sentence starts and source labels pass")
    expect(F.unsourced_facts('Try saying "I\'m here" for 10 minutes, or ask Gal.', idx, names_only=True) == ["name Gal"], "grounding: personal advice checks names only")
    p = HERE / "hf-teach-smoke-v2a" / "teach" / "teacher_results.jsonl.gz"
    if p.exists():
        smoke = {r["id"]: r for r in map(json.loads, gzip.open(p, "rt")) if r.get("family")}
        rejected(smoke["recipe_skip-1"], "smoke recipe_skip-1: planned clone + one git_log (one lookup: no plan)", "one-lookup")
        rejected(smoke["need_web-1"], "smoke need_web-1: 'the Iroquois Confederacy' is in no result", "no prompt or tool result")
        for i in ["unknown_word-0", "unknown_word-1", "unknown_word-2", "web_fact_retry-1", "web_fact_retry-2", "personal-1", "personal-2",
                  "personal_tool-1", "personal_tool-2", "recipe_skip-0", "recipe_web-1", "recipe_web-2", "hermes_need-0", "web_fact-0"]:
            if i in smoke:
                accepted(smoke[i], f"smoke {i}")
    ids = {r["id"]: r for v in by.values() for r in v}
    if "chat_after-5" in ids:
        rejected(ids["chat_after-5"], "v1 chat_after-5: 'August 1962' came from memory, the snippet was cut", "no prompt or tool result")
    web = next((r for r in by.get("web_fact", []) if F.check(r)["strict"]), None)
    if web:
        r = set_reply(web, 0, web["turns"][0]["reply"] + " It was later backed by the Iroquois Confederacy.")
        rejected(r, "kept web_fact + an invented name in the reply", "no prompt or tool result")


if __name__ == "__main__":
    unit()
    v2_cases()
    by = episodes()
    if by:
        episode_cases(by)
    grounding_cases(by or {})
    constant_cases()
    print(f"\n{len(FAILS)} failing" if FAILS else "\nall checker tests pass")
    sys.exit(1 if FAILS else 0)
