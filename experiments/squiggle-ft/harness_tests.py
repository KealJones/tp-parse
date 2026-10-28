"""Positive harness cases (checker fixtures, never training data) for the v2 families that don't need the live web: scripted fixture outputs (never training
text) through Squiggle's real harness; each episode must be KEPT (math_pair-0's fixture puts the answer in the
expression, so it is expected to be dropped; recipe_web only checks the recipe reaches the prompt). Needs SQUIGGLE_DIR.

  python harness_tests.py [work_dir]
"""
import json, os, re, sys
sys.path.insert(0, '.')
from pathlib import Path
import build, families as F
from gold import out, last_user, first_user, result
from sqrun import Runner, ScriptBackend

W = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / 'work'
src = build.load_sources(W, 'train')
eps = build.make_sets(src, {"math_pair": 4, "repo_chain": 3, "recipe_skip": 3, "recipe_web": 3, "near_miss": 3}, seed=5)
REQ = lambda: ["Request: fixture request.", "Pieces: 1. the asked thing.", "Know: the request.", "Don't know: the answer.",
               "Goal: answer it.", "Next: act."]


def calc_policy(ep):
    def act(req):
        last = last_user(req)
        users = [m for m in req["messages"] if m["role"] == "user" and not m["content"].startswith("Result of ")]
        if ep.gold["variant"] == "incomplete" and len(users) == 1:
            return out(REQ(), "need", {"what": "How many is the missing amount in your problem?"})
        if not last.startswith("Result of ") and "calculate" not in json.dumps(req["messages"][0]["content"]):
            return out(REQ(), "find", {"query": "calculate a math expression"})
        if result(req, "find") is not None and "calculate" in last:
            return out(["Check: find returned calculate.", "Next: compute."], "calculate", {"expression": str(ep.gold["answer"]).replace(",", "") + " * 1"})
        if result(req, "calculate"):
            v = result(req, "calculate")["result"]
            return out([f"Check: calculate returned {v}.", "Next: answer."], reply=f"The answer is {v:g} (calculated).")
        return out(REQ(), "find", {"query": "calculate a math expression"})
    return act


def chain_policy(ep):
    g = ep.gold
    name = g["repo"].split("/")[1]

    def act(req):
        last = last_user(req)
        fu = first_user(req)
        if "Every step is done" in fu:
            return out([f"Answer: step 2 read line {g['line']} of {g['path']}."], reply=f"The line after it is `{g['text']}` (from {g['path']} in the repo).")
        st = re.search(r"Work on step (\d+) now", fu)
        if not st:
            return out(REQ()[:-1] + ["Plan: find the definition, then read the next line."], "plan",
                       {"goal": "Read the line after the definition", "steps": [f"Grep {g['name']} in {g['repo']}", "Read the line after the definition"]})
        n = int(st.group(1))
        if n == 1:
            if not last.startswith("Result of "):
                return out(["Step: 1 of 2, find the definition.", "Know: nothing yet.", "Next: look up clone and grep."], "find", {"query": "clone a repo and search code"})
            if result(req, "find") is not None:
                return out(["Check: find gave git_clone and grep.", "Next: clone."], "git_clone", {"repo": g["repo"]})
            if result(req, "git_clone") is not None:
                return out([f"Check: cloned to /repos/{name}.", "Next: grep."], "grep", {"pattern": g["name"], "path": f"/repos/{name}"})
            return out([f"Check: grep shows {g['path']} line {g['line'] - 1}.", "Next: record it."], "done",
                       {"result": f"{g['name']} is defined in /repos/{name}/{g['path']} line {g['line'] - 1}"})
        if not last.startswith("Result of "):
            return out(["Step: 2 of 2, read the next line.", f"Know: step 1 found /repos/{name}/{g['path']}.", "Next: look up read_file."], "find", {"query": "read a file in a repo"})
        if result(req, "find") is not None:
            return out(["Check: find gave read_file.", "Next: read the line."], "read_file", {"path": f"/repos/{name}/{g['path']}", "start_line": g["line"], "end_line": g["line"]})
        return out([f"Check: line {g['line']} reads {g['text']}.", "Next: record it."], "done", {"result": f"line {g['line']} of {g['path']}: {g['text']}"})
    return act


def skip_policy(ep):
    g = ep.gold
    name = g["repo"].split("/")[1]

    def act(req):
        last = last_user(req)
        if not last.startswith("Result of "):
            return out(REQ(), "find", {"query": "clone a repo and show commits"})
        if result(req, "find") is not None:
            return out(["Check: find gave git_clone and git_log.", "Next: clone."], "git_clone", {"repo": g["repo"]})
        if result(req, "git_clone") is not None:
            return out([f"Check: cloned to /repos/{name}.", "Next: newest commit."], "git_log", {"repo": name, "count": 1})
        c = (result(req, "git_log") or {}).get("commits", "")
        mm = re.search(r"([0-9a-f]{8}) (\d{4}-\d\d-\d\d) (.+?): (.*)", c)
        oid, date, author, subj = mm.groups()
        rep = f"The latest commit in {g['repo']} is {oid} by {author}: \"{subj}\" (from the git log)."
        return out([f"Check: the log says {oid} by {author}: {subj}.", "Next: answer."], reply=rep)
    return act


def near_policy(ep):
    m = ep.gold["miss"]
    return lambda req: out(["Request: about a word I don't know.", "Pieces: 1. what the word is.", f"Know: the word {m}.",
                            f"Don't know: what {m} is.", "Goal: ask.", "Next: ask."],
                           reply=f"I don't recognise \"{m}\" as a word. Did you mean {ep.gold['real']}?")


def web_recipe_policy(ep):
    return lambda req: out(["Plain fixture."], reply="fixture")


pol = {"math_pair": calc_policy, "repo_chain": chain_policy, "recipe_skip": skip_policy, "near_miss": near_policy, "recipe_web": web_recipe_policy}
res = Runner(ScriptBackend({e.id: pol[e.family](e) for e in eps}), os.environ["SQUIGGLE_DIR"], str(W), concurrency=6, batch_wait=0.05, max_calls=20).run(eps)
for r in sorted(res, key=lambda r: r["id"]):
    c = F.check(r)
    seen = F.recipe_seen(r, 0) if r["family"].startswith("recipe") else None
    print("kept   " if c["strict"] else "DROPPED", r["id"], "| recipe in prompt:" if seen is not None else "", seen if seen is not None else "",
          "|", "; ".join(c["reasons"])[:300], (r.get("error") or "")[:150])
