"""Template-written gold episodes: scripted policies that fill fixed sentence templates from the prompt and the real tool
results, run through Squiggle's real harness. They are the open-weights teacher's few-shot examples (teacher.py) and a
checker test. They are NOT training data (only teacher episodes, tagged source "teacher:<model>", are).

  python gold.py --out examples/gold.jsonl
"""
import argparse, json, os, random, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import families as F
import quality as Q
import sources as S
from sqrun import Episode, Runner, ScriptBackend


def out(lines, name=None, args=None, reply=None):
    t = "<think>\n" + "\n".join(lines) + "\n</think>\n"
    if name:
        return t + "```tool_call\n" + json.dumps({"name": name, "arguments": args}, ensure_ascii=False) + "\n```"
    return t + reply


def last_user(req):
    return next(m for m in reversed(req["messages"]) if m["role"] == "user")["content"]


def first_user(req):
    return next(m for m in req["messages"] if m["role"] == "user")["content"]


def result(req, name):
    m = re.match(r"Result of " + re.escape(name) + r":\n(\{.*\})\s*$", last_user(req), re.S)
    return json.loads(m.group(1)) if m else None


def log_line(req):
    c = (result(req, "git_log") or {}).get("commits", "")
    m = re.search(r"([0-9a-f]{8}) (\d{4}-\d\d-\d\d) (.+?): (.*)", c)
    return m.groups() if m else None


def pkg_version(req):
    c = (result(req, "read_file") or {}).get("content", "")
    m = re.search(r'\d+:\s*"version":\s*"([^"]+)"', c)
    n = re.search(r'\d+:\s*"name":\s*"([^"]+)"', c)
    return (m.group(1) if m else None), (n.group(1) if n else None)


# ── policies ────────────────────────────────────────────────────────────────
def repo_two_policy(repo, recipe=False):
    name = repo.split("/")[1]

    def act(req):
        last = last_user(req)
        if "Every step is done" in first_user(req):
            sysm = req["messages"][0]["content"]
            v = re.search(r"→ version ([\w.\-]+)", sysm)
            c = re.search(r"commit ([0-9a-f]{8}) \((\d{4}-\d\d-\d\d), (.+?)\): (.*)", sysm)
            return out([f"Answer: step 1 gave the version ({v.group(1)}) from package.json, step 2 the newest commit ({c.group(1)}) from the git log; give both and say where they came from."],
                       reply=f"{repo} is at version {v.group(1)} (from its package.json), and the latest commit is {c.group(1)} from {c.group(2)} by {c.group(3)}: \"{c.group(4)}\" (from the git log).")
        step = re.search(r"Work on step (\d+) now", first_user(req))
        if not step:
            know = (f"Know: the repo is {repo}, and the prompt has a recipe from a similar task (version, then latest commit)."
                    if recipe else f"Know: the repo is {repo}.")
            plan_line = ("Plan: the recipe's two steps, filled in with this repo." if recipe else
                         f"Plan: 1. clone {repo} and read the version from package.json, 2. get the latest commit from the git log.")
            return out([f"Request: For the {repo} repo, its current version and its latest commit.",
                        "Pieces: 1. the version. 2. the latest commit.",
                        know,
                        "Don't know: the version (it's in package.json) and the latest commit (the git log); I'd be guessing both.",
                        f"Goal: Report {name}'s version and latest commit.",
                        plan_line],
                       "plan", {"goal": f"Find {name}'s version and latest commit", "steps": [f"Clone {repo} and read the version from package.json", "Get the latest commit from the git log"]})
        n = int(step.group(1))
        if n == 1:
            if not last.startswith("Result of "):
                return out([f"Step: 1 of 2, clone {repo} and read its version; step 2 needs the clone.",
                            "Know: no tools looked up yet.",
                            "Next: look up how to clone a repo and read a file."], "find", {"query": "clone a github repo and read a file"})
            if result(req, "find"):
                return out(["Check: find gave me git_clone and read_file.", f"Next: clone {repo}."], "git_clone", {"repo": repo})
            if result(req, "git_clone"):
                g = result(req, "git_clone")
                return out([f"Check: cloned to {g.get('path')} on {g.get('branch')}, the right repo.", f"Next: read {g.get('path')}/package.json for the version."],
                           "read_file", {"path": f"/repos/{name}/package.json"})
            v, pn = pkg_version(req)
            return out([f"Check: this is the package.json of {pn} ({repo}); its version field says {v}.", "Next: step 1 is done; record the version and where the clone is."],
                       "done", {"result": f"version {v} (from /repos/{name}/package.json); cloned at /repos/{name}"})
        if not last.startswith("Result of "):
            return out(["Step: 2 of 2, the latest commit; the reply needs its id, date and message.",
                        f"Know: step 1 cloned the repo to /repos/{name}; git_log isn't looked up yet.",
                        "Next: look up the commit-log tool."], "find", {"query": "recent commits"})
        if result(req, "find"):
            return out(["Check: find gave me git_log.", f"Next: read the newest commit of /repos/{name}."], "git_log", {"repo": name, "count": 1})
        oid, date, author, subj = log_line(req)
        return out([f"Check: this is the log of /repos/{name}; the newest commit is {oid} from {date} by {author}: \"{subj}\".", "Next: step 2 is done; record the commit."],
                   "done", {"result": f"latest commit {oid} ({date}, {author}): {subj}"})
    return act


def need_repo_policy(repo):
    name = repo.split("/")[1]

    def act(req):
        last = last_user(req)
        user_msgs = [m for m in req["messages"] if m["role"] == "user"]
        if len(user_msgs) == 1 and not last.startswith("Result of "):
            return out(["Request: They want the latest commit on \"my repo\".", "Pieces: 1. which repo they mean. 2. its latest commit.",
                        "Know: they have several repos; nothing here says which one.",
                        "Don't know: which repo; only they can tell me, and picking one would be a guess.",
                        "Goal: Tell them the latest commit on the repo they mean.", "Next: ask which repo before cloning anything."],
                       "need", {"what": "Which of your repos do you mean?"})
        if not last.startswith("Result of "):
            return out([f"Request: Answering my question: they mean {repo}. So: its latest commit.", f"Pieces: 1. clone {repo}. 2. read its newest commit.",
                        f"Know: the repo is {repo}, from their answer.", "Don't know: its latest commit; the git log has it.",
                        f"Goal: Tell them the latest commit on {repo}.", "Next: look up tools to clone a repo and read its log."],
                       "find", {"query": "clone a github repo and show recent commits"})
        if result(req, "find"):
            return out(["Check: find gave me git_clone and git_log.", f"Next: clone {repo}."], "git_clone", {"repo": repo})
        if result(req, "git_clone"):
            g = result(req, "git_clone")
            return out([f"Check: cloned to {g.get('path')}, the repo they named.", "Next: read the newest commit, count 1."], "git_log", {"repo": name, "count": 1})
        oid, date, author, subj = log_line(req)
        return out([f"Check: the log of /repos/{name}; newest commit {oid} from {date} by {author}: \"{subj}\".", "Next: answer with it and say it's from the git log."],
                   reply=f"The latest commit on {repo} is {oid} from {date} by {author}: \"{subj}\" (from the repo's git log).")
    return act


def page_text(req):
    r = result(req, "fetch_url") or {}
    if "partial" in r:
        t = r["partial"]
    else:
        t = r.get("text", "")
    return re.sub(r"\\n|\s+", " ", t)


def sentence_with(text, needle, width=90):
    """The words around the first place the page says `needle` (at most ~2*width characters)."""
    i = text.find(needle)
    if i < 0:
        return None
    a, b = max(0, i - width), min(len(text), i + len(needle) + width)
    a = text.find(" ", a) + 1 if a else 0
    b = text.rfind(" ", 0, b) if b < len(text) else b
    return ("…" if a else "") + text[a:b].strip() + "…"


def web_fact_policy(question, query, title_hint, answer):
    def act(req):
        last = last_user(req)
        if not last.startswith("Result of "):
            return out([f"Request: {question}", "Pieces: 1. the year it came out.",
                        "Know: only the question; nothing in the prompt says when.",
                        "Don't know: the release date; I'd be guessing, so I'll look it up on the web.",
                        "Goal: Say when the first Fast and Furious film came out.",
                        "Next: find only searches my tools, memory and past chats, so look up the web search tool."],
                       "find", {"query": "search the web"})
        if result(req, "find"):
            return out(["Check: find gave me web_search and fetch_url.", f"Next: search the web for \"{query}\"."], "web_search", {"query": query})
        if result(req, "web_search"):
            res = result(req, "web_search").get("results", "")
            m = re.search(r"\d+\. ([^\n]*" + re.escape(title_hint) + r"[^\n]*)\n\s+(https://\S+)", res)
            return out([f"Check: result \"{m.group(1)}\" is the page for the first film; the snippets don't give the date clearly.", "Next: read that page."],
                       "fetch_url", {"url": m.group(2)})
        text = page_text(req)
        text = text[text.find('"text":'):] if '"text":' in text else text
        m = re.search(r"Release dates?\s*(?:\\n|\s)*([A-Z][a-z]+ \d{1,2}, " + re.escape(answer) + r"[^\\]{0,40})", text)
        sent = ("Release dates: " + m.group(1).strip()) if m else sentence_with(text, answer).replace('"', "'")
        return out([f"Check: this is the Wikipedia page for the first film, and it says: \"{sent}\"", "Next: answer with the date and cite the page."],
                   reply=f"The first Fast and Furious film, The Fast and the Furious, came out on {(m.group(1).split(' (')[0]) if m else answer} (from its Wikipedia page).")
    return act


def born(text):
    m = re.search(r"\b((?:January|February|March|April|May|June|July|August|September|October|November|December) \d{1,2}, (\d{4}))", text)
    return (m.group(1), int(m.group(2))) if m else (None, None)


def web_compare_policy(a, b):
    def act(req):
        last = last_user(req)
        first = first_user(req)
        if "Every step is done" in first:
            sysm = req["messages"][0]["content"]
            ya = re.search(re.escape(a) + r": born [A-Za-z]+ \d+, (\d{4})", sysm)
            yb = re.search(re.escape(b) + r": born [A-Za-z]+ \d+, (\d{4})", sysm)
            older, younger = (a, b) if int(ya.group(1)) < int(yb.group(1)) else (b, a)
            return out([f"Answer: step results give {a} born {ya.group(1)} and {b} born {yb.group(1)}; {older} was born first. Cite both Wikipedia pages."],
                       reply=f"{older} was born first: {a} was born in {ya.group(1)} and {b} in {yb.group(1)} (from their Wikipedia pages).")
        step = re.search(r"Work on step (\d+) now", first)
        if not step:
            return out([f"Request: Who was born first, {a} or {b}.", f"Pieces: 1. {a}'s birth date. 2. {b}'s birth date. 3. which is earlier.",
                        "Know: only the two names.", "Don't know: both birth dates; I'd be guessing.",
                        f"Goal: Say whether {a} or {b} was born first.",
                        f"Plan: two separate lookups, so a plan: 1. find {a}'s birth date, 2. find {b}'s birth date; the reply compares them."],
                       "plan", {"goal": f"Find who was born first: {a} or {b}", "steps": [f"Find {a}'s birth date", f"Find {b}'s birth date"]})
        who = a if step.group(1) == "1" else b
        url = "https://en.wikipedia.org/wiki/" + who.replace(" ", "_")
        if not last.startswith("Result of "):
            tools = Q.looked_up(req["messages"])
            if "fetch_url" in tools:
                return out([f"Step: {step.group(1)} of 2, {who}'s birth date; the reply needs the exact date.",
                            "Know: fetch_url is already looked up, and Wikipedia has a page per person.",
                            f"Next: read {who}'s Wikipedia page."], "fetch_url", {"url": url})
            return out([f"Step: {step.group(1)} of 2, {who}'s birth date; the reply needs the exact date.",
                        "Know: no web tools looked up yet.", "Next: look up the tool that reads web pages."], "find", {"query": "read a web page"})
        if result(req, "find"):
            return out(["Check: find gave me fetch_url.", f"Next: read {who}'s Wikipedia page."], "fetch_url", {"url": url})
        date, year = born(page_text(req))
        return out([f"Check: this is the Wikipedia page for {who}, and the opening gives the birth date {date}.", "Next: step done; record the date and the source."],
                   "done", {"result": f"{who}: born {date} (Wikipedia: {who})"})
    return act


CHAT_REPLIES = {"hey whats up lol": ("A casual hello; nothing to look up, just a short friendly reply.", "Not much! Just here if you need anything. What's up with you?"),
                "thanks, that worked": ("They're saying thanks; it worked. A short warm reply.", "Glad it worked! Shout if anything else comes up."),
                "good night squiggle": ("A goodnight; plain chat, a short reply.", "Good night! Sleep well.")}


def chat_policy(text):
    th, rep = CHAT_REPLIES[text]
    return lambda req: out([th], reply=rep)


def episodes(facts):
    world = {"repos": F.world_repos(list(facts.values()))}
    eps = []
    for t in CHAT_REPLIES:
        eps.append((Episode(id=f"gold-chat-{len(eps)}", family="chat", first=t), chat_policy(t)))
    for repo in ["lukeed/clsx", "vercel/ms", "chalk/chalk", "sindresorhus/p-limit"]:
        if repo in facts:
            f = facts[repo]
            gold = {"parts": [{"kind": "version", "answers": [f["package"]["version"]]}, {"kind": "latest_commit", "subject": f["commits"][0]["subject"], "oid": f["commits"][0]["oid"]}], "repo": repo}
            eps.append((Episode(id=f"gold-repo_two-{repo.split('/')[1]}", family="repo_two", first=f"Clone {repo} and tell me what version it's at and what the latest commit was.", gold=gold, world=world),
                        repo_two_policy(repo)))
    repo = "developit/mitt"
    if repo in facts:
        c = facts[repo]["commits"][0]
        eps.append((Episode(id="gold-need_repo-mitt", family="need_repo", first="what's the latest commit on my repo", world=world,
                            gold={"kind": "latest_commit", "repo": repo, "subject": c["subject"], "oid": c["oid"]},
                            user=lambda turn, ep: (f"the mitt one, {repo}" if turn["n"] == 0 else None)), need_repo_policy(repo)))
    recs = json.loads((HERE / "examples" / "gold_recipes.json").read_text()) if (HERE / "examples" / "gold_recipes.json").exists() else []
    rec = next((r for r in recs if r.get("repo") == "lukeed/clsx"), None)
    if rec and "expressjs/cors" in facts:
        f = facts["expressjs/cors"]
        gold = {"parts": [{"kind": "version", "answers": [f["package"]["version"]]}, {"kind": "latest_commit", "subject": f["commits"][0]["subject"], "oid": f["commits"][0]["oid"]}], "repo": "expressjs/cors"}
        eps.append((Episode(id="gold-recipe_repo-cors", family="recipe_repo", first="what's the version and latest commit of expressjs/cors?", gold=gold,
                            world={**world, "recipes": [{k: v for k, v in rec.items() if k not in ("from_episode", "repo")}]}), repo_two_policy("expressjs/cors", recipe=True)))
    eps.append((Episode(id="gold-web_fact-ff", family="web_fact", first="When did the first Fast and Furious come out?", gold={"answers": ["2001"]}),
                web_fact_policy("When the first Fast and Furious film came out.", "The Fast and the Furious 2001 film release date", "Fast and the Furious", "2001")))
    eps.append((Episode(id="gold-web_compare-born", family="web_compare", first="Who was born first, Susan Oliver or W. S. Van Dyke?",
                        gold={"answer": "Woodbridge Strong Van Dyke II", "titles": ["Susan Oliver", "W. S. Van Dyke"], "type": "comparison"}),
                web_compare_policy("Susan Oliver", "W. S. Van Dyke")))
    return eps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE / "examples" / "gold.jsonl"))
    ap.add_argument("--work", default=str(HERE / "work"))
    ap.add_argument("--squiggle", default=os.environ.get("SQUIGGLE_DIR", str(HERE / "squiggle")))
    a = ap.parse_args()
    facts = S.repo_facts(a.work, S.TRAIN_REPOS)
    eps = episodes(facts)
    res = Runner(ScriptBackend({e.id: p for e, p in eps}), a.squiggle, a.work, concurrency=4, batch_wait=0.05).run([e for e, _ in eps])
    res.sort(key=lambda r: r["id"])
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    recipes = []
    with open(a.out, "w") as f:
        for r in res:
            r["check"] = F.check(r)
            print(r["id"], "kept" if r["check"]["strict"] else f"NOT kept: {r['check']['reasons']}", r.get("error") or "")
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            if r["family"] == "repo_two" and r["check"]["strict"]:
                for rec in r.get("recipes") or []:
                    recipes.append({**rec, "from_episode": r["id"], "repo": r["gold"]["repo"]})
    # Recipes the app saved from the finished gold plans (lite mode: built from the task log). recipe_repo episodes
    # start with one of these in memory, as if the similar task had been done in an earlier session.
    Path(a.out).with_name("gold_recipes.json").write_text(json.dumps(recipes, ensure_ascii=False, indent=1))
    print(len(recipes), "recipes ->", Path(a.out).with_name("gold_recipes.json"))


if __name__ == "__main__":
    main()
