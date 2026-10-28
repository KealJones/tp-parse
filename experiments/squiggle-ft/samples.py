"""~20 hand-written sample episodes, run through Squiggle's real harness with real tools (web, git, sandbox), so the
exact training text can be checked by eye. The model's side is scripted here; tool results are real. Each sample is
also scored by its family's checker.

  python samples.py --out samples          -> samples/samples.jsonl (+ samples/SAMPLES.md, readable)
"""
import argparse, json, os, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import families as F
import sources as S
from sqrun import Episode, Runner, ScriptBackend


def T(think, name=None, args=None, reply=None):
    t = "<think>\n" + think.strip() + "\n</think>\n"
    if name:
        return t + "```tool_call\n" + json.dumps({"name": name, "arguments": args or {}}, ensure_ascii=False) + "\n```"
    return t + reply.strip()


def last(req, name):
    """The newest 'Result of <name>' JSON the model was shown."""
    for m in reversed(req["messages"]):
        if m["role"] == "user":
            hits = re.findall(r"Result of " + re.escape(name) + r":\n(\{.*?\})(?=\n\nResult of |\Z)", m["content"], re.S)
            if hits:
                return json.loads(hits[-1])
    return {}


def log_first(req):
    """First commit line from a git_log result: (oid, date, author, subject)."""
    c = last(req, "git_log").get("commits", "")
    for line in c.splitlines():
        m = re.match(r"([0-9a-f]{8}) (\d{4}-\d\d-\d\d) (.+?): (.*)", line)
        if m:
            return m.groups()
    return ("?", "?", "?", "?")


def json_field(req, path_hint, field):
    content = last(req, "read_file").get("content", "")
    m = re.search(r'\d+: \s*"' + field + r'":\s*"([^"]+)"', content)
    return m.group(1) if m else "?"


def grep_hit(req):
    m = re.search(r"(/repos/[^\s:]+):(\d+): ", last(req, "grep").get("matches", ""))
    return (m.group(1), m.group(2)) if m else ("?", "?")


def step_kind(req):
    first = next((m["content"] for m in req["messages"] if m["role"] == "user"), "")
    m = re.search(r"Work on step (\d+) now", first)
    return int(m.group(1)) if m else (0 if "Every step is done" not in first else -1)


class Seq:
    """A script: callables or strings, taken in order (one per model call)."""
    def __init__(self, *items):
        self.items, self.i = list(items), 0

    def __call__(self, req):
        it = self.items[min(self.i, len(self.items) - 1)]
        self.i += 1
        return it(req) if callable(it) else it


def samples(facts):
    sq, tp = facts["KealJones/squiggle"], facts["KealJones/tp-parse"]
    world = {"repos": F.world_repos([sq, tp])}
    out = []

    def add(fam, first, gold, script, world=None, user=None, meta=None):
        out.append((Episode(id=f"sample-{len(out):02d}-{fam}", family=fam, first=first, gold=gold, world=world or {}, user=user, meta=meta or {"messy": False}), script))

    # 1-3. plain chat
    add("chat", "hey whats up lol", {}, Seq(T("Just a casual hello. No question to answer and nothing to look up, so a short friendly reply.", reply="Not much, just here and ready to help. What's up with you?")))
    add("chat", "thanks, that worked", {}, Seq(T("They're saying thanks; something worked. Nothing to do, just reply warmly and briefly.", reply="Glad it worked! Let me know if anything else comes up.")))
    add("chat", "good night squiggle", {}, Seq(T("A goodnight message. Plain chat, a short reply is right.", reply="Good night! Sleep well.")))

    # 4. web fact: look it up, check it's the right thing
    add("web_fact", "When was the last time anyone was on the moon?", {"answers": ["December 1972"]}, Seq(
        T("They want the date of the most recent crewed Moon landing. That's a fact I should look up, not recall. I need a web search tool first.", "find", {"query": "search the web"}),
        T("find gave me web_search and fetch_url. I'll search for the last crewed Moon landing.", "web_search", {"query": "last crewed Moon landing Apollo 17"}),
        T("The results point to Apollo 17 as the last mission that landed people on the Moon. The snippets don't give the exact dates, so I'll read the Apollo 17 page to check.", "fetch_url", {"url": "https://en.wikipedia.org/wiki/Apollo_17"}),
        T("The page is about Apollo 17, the right mission: it says it was the final mission of the Apollo program and the last time humans set foot on the Moon, in December 1972. That answers it.",
          reply="The last time anyone was on the Moon was in December 1972, during Apollo 17. Its astronauts were the last people to walk on the lunar surface. (Source: Wikipedia's Apollo 17 article.)")))

    # 5. math with run_js
    q = "Janet’s ducks lay 16 eggs per day. She eats three for breakfast every morning and bakes muffins for her friends every day with four. She sells the remainder at the farmers' market daily for $2 per fresh duck egg. How much in dollars does she make every day at the farmers' market?"
    add("math", q, {"answer": "18"}, Seq(
        T("A word problem: eggs left after eating 3 and baking with 4, times $2 each. I shouldn't do arithmetic in my head; I'll find a tool that runs code.", "find", {"query": "run javascript to calculate"}),
        T("run_js runs JavaScript. Eggs left = 16 - 3 - 4, money = left * 2.", "run_js", {"code": "const left = 16 - 3 - 4;\nconsole.log(left, left * 2);"}),
        T("The sandbox printed 9 eggs left and 18 dollars. That matches the problem: 9 eggs at $2 each.", reply="She makes $18 a day: 16 − 3 − 4 = 9 eggs left, and 9 × $2 = $18.")))

    # 6. repo fact: version
    add("repo_fact", "What version is KealJones/squiggle at right now?", {"kind": "version", "answers": [sq["package"]["version"]]}, Seq(
        T("They want the current version of the squiggle repo. I don't know it; it's in the repo's package.json. First I need tools to clone a repo and read files.", "find", {"query": "clone a github repo and read a file"}),
        T("I have git_clone and read_file now. Clone KealJones/squiggle first.", "git_clone", {"repo": "KealJones/squiggle"}),
        T("Cloned into /repos/squiggle. The version is in package.json.", "read_file", {"path": "/repos/squiggle/package.json"}),
        lambda req: T(f"This is squiggle's package.json (name \"squiggle\"), so it's the right file. The version field says {json_field(req, 'package.json', 'version')}.",
                      reply=f"KealJones/squiggle is at version {json_field(req, 'package.json', 'version')} (from its package.json).")))

    # 7. repo where
    d = next(x for x in sq["defs"] if x["name"] == "renderFind")
    add("repo_where", "where is renderFind defined in the squiggle repo?", {"kind": "where", "path": d["path"]}, Seq(
        T("They want the file that defines renderFind in squiggle. I have only the repo name, not its owner, so I'll find a tool that lists their GitHub repos.", "find", {"query": "list my github repos"}),
        T("github_list_repos will show which repos they have.", "github_list_repos", {}),
        T("The list has KealJones/squiggle, so that's the one. Now I need a clone tool and a code search.", "find", {"query": "clone a repo and search code"}),
        T("Clone KealJones/squiggle.", "git_clone", {"repo": "KealJones/squiggle"}),
        T("Cloned. Search for where renderFind is defined, not just used.", "grep", {"pattern": "function renderFind", "path": "/repos/squiggle"}),
        lambda req: T(f"The match {grep_hit(req)[0]} line {grep_hit(req)[1]} is the definition (\"export function renderFind\"), so that's the answer.",
                      reply=f"renderFind is defined in {grep_hit(req)[0].replace('/repos/squiggle/', '')} (line {grep_hit(req)[1]}) in KealJones/squiggle.")), world=world)

    # 8. two-part repo task with a plan
    add("repo_two", "Clone KealJones/tp-parse and tell me what version it's at and what the latest commit was.",
        {"parts": [{"kind": "version", "answers": [tp["package"]["version"]]}, {"kind": "latest_commit", "subject": tp["commits"][0]["subject"], "oid": tp["commits"][0]["oid"]}]}, Seq(
        T("Two things about KealJones/tp-parse: its version and its latest commit. That's more than one step, so I'll plan it.", "plan",
          {"goal": "Find tp-parse's version and latest commit", "steps": ["Clone KealJones/tp-parse and read the version from package.json", "Get the latest commit from the git log"]}),
        T("Step 1: clone and read the version. I need the clone tool first.", "find", {"query": "clone a github repo"}),
        T("Clone KealJones/tp-parse.", "git_clone", {"repo": "KealJones/tp-parse"}),
        T("Cloned into /repos/tp-parse. Now read package.json for the version.", "find", {"query": "read a file"}),
        T("read_file it is.", "read_file", {"path": "/repos/tp-parse/package.json"}),
        lambda req: T(f"It's tp-parse's package.json; version {json_field(req, 'package.json', 'version')}. That finishes step 1.", "done", {"result": f"Cloned to /repos/tp-parse; version {json_field(req, 'package.json', 'version')}"}),
        T("Step 2: the latest commit. The repo is already cloned at /repos/tp-parse; I need a tool for the commit log.", "find", {"query": "recent commits of a repo"}),
        T("git_log shows recent commits; one is enough.", "git_log", {"repo": "tp-parse", "count": 1}),
        lambda req: T(f"The newest commit is {log_first(req)[0]} on {log_first(req)[1]}: \"{log_first(req)[3]}\". That's step 2 done.", "done", {"result": f"Latest commit {log_first(req)[0]} ({log_first(req)[1]}, {log_first(req)[2]}): {log_first(req)[3]}"}),
        lambda req: T("Both steps are done: the version from package.json and the newest commit from the log. I'll give both.",
                      reply=f"KealJones/tp-parse is at version {tp['package']['version']}, and the latest commit is {tp['commits'][0]['oid']}: \"{tp['commits'][0]['subject']}\".")), world=world)

    # 9. need: which repo?
    c = sq["commits"][0]
    add("need_repo", "whats the latest commit on my repo", {"kind": "latest_commit", "subject": c["subject"], "oid": c["oid"]}, Seq(
        T("They want the latest commit on \"my repo\", but they have more than one repo and nothing here says which. I can't look that up; only they know which one they mean.", "need", {"what": "Which of your repos do you mean?"}),
        T("They said the squiggle one, so KealJones/squiggle. I need tools to clone it and read its log.", "find", {"query": "clone a repo and show recent commits"}),
        T("Clone KealJones/squiggle.", "git_clone", {"repo": "KealJones/squiggle"}),
        T("Now the newest commit.", "git_log", {"repo": "squiggle", "count": 1}),
        lambda req: T(f"The log is for squiggle; the newest commit is {log_first(req)[0]}.", reply=f"The latest commit on KealJones/squiggle is {log_first(req)[0]} ({log_first(req)[1]}): \"{log_first(req)[3]}\".")),
        world=world, user=lambda turn, ep: "oh the squiggle one" if turn["n"] == 0 else None)

    # 10. memory says which repo
    add("memory_repo", "what's the latest commit in my agent project", {"kind": "latest_commit", "subject": c["subject"], "oid": c["oid"]}, Seq(
        T("\"My agent project\" — which repo is that? Memory might know before I ask them.", "find", {"query": "my agent project repo"}),
        lambda req: T("Memory says Keal builds Squiggle, a browser-only AI agent, in KealJones/squiggle. That's the agent project. I'll find the clone tool.", "find", {"query": "clone a github repo"}),
        T("Clone KealJones/squiggle.", "git_clone", {"repo": "KealJones/squiggle"}),
        T("Now the commit log.", "find", {"query": "recent commits"}),
        T("git_log, one commit.", "git_log", {"repo": "squiggle", "count": 1}),
        lambda req: T(f"Newest commit in squiggle: {log_first(req)[0]}.", reply=f"Your agent project (KealJones/squiggle) was last committed to on {log_first(req)[1]}: {log_first(req)[0]} \"{log_first(req)[3]}\".")),
        world={**world, "facts": F.KEAL_FACTS})

    # 11. bare link
    add("bare_link", "https://en.wikipedia.org/wiki/Gemma_(language_model)", {"url": "https://en.wikipedia.org/wiki/Gemma_(language_model)", "title": "Gemma (language model)"}, Seq(
        T("Just a link, nothing else. They probably want to know what's on the page. I need a tool that reads web pages.", "find", {"query": "read a web page"}),
        T("fetch_url reads a page by URL.", "fetch_url", {"url": "https://en.wikipedia.org/wiki/Gemma_(language_model)"}),
        T("The page loaded and it's the right one: Wikipedia's article on Gemma, Google DeepMind's family of open-weight language models. I'll sum up what it covers.",
          reply="That's Wikipedia's article on Gemma, Google DeepMind's family of open-weight language models, built from the same research as Gemini. It goes through the model generations and sizes and what they're for.")))

    # 12. hermes need
    add("hermes_need", "Reverse the given sentence.", {}, Seq(T("They want a sentence reversed, but no sentence is in the message. I can't make one up; only they can give it to me.", "need", {"what": "What is the sentence you want reversed?"})))

    # 13. hermes compute
    add("hermes_compute", "Find all pairs of numbers in the list [3, 6, 8, 1, 10] that sum up to 9.", {}, Seq(
        T("Pairs from [3, 6, 8, 1, 10] that add up to 9. I'll compute it with code instead of in my head.", "find", {"query": "run javascript"}),
        T("run_js: check every pair.", "run_js", {"code": "const a = [3, 6, 8, 1, 10];\nconst out = [];\nfor (let i = 0; i < a.length; i++) for (let j = i + 1; j < a.length; j++) if (a[i] + a[j] === 9) out.push([a[i], a[j]]);\nconsole.log(JSON.stringify(out));"}),
        lambda req: T(f"The code printed {last(req, 'run_js').get('stdout', '').strip()}: 3+6 and 8+1.", reply=f"The pairs that sum to 9 are {last(req, 'run_js').get('stdout', '').strip()}, i.e. 3 + 6 and 8 + 1.")))

    # 14. web compare with a plan
    add("web_compare", "Who was born first, Susan Oliver or W. S. Van Dyke?", {"answer": "Woodbridge Strong Van Dyke II", "titles": ["Susan Oliver", "W. S. Van Dyke"]}, Seq(
        T("Two people, and I need both birth dates before comparing. That's two lookups, so a plan.", "plan", {"goal": "Find who was born first: Susan Oliver or W. S. Van Dyke", "steps": ["Find Susan Oliver's birth date", "Find W. S. Van Dyke's birth date"]}),
        T("Step 1: Susan Oliver's birth date. I need a web tool.", "find", {"query": "search the web"}),
        T("Search for her.", "web_search", {"query": "Susan Oliver actress born"}),
        T("A Susan Oliver result is the actress. I'll read her page to get the exact date.", "fetch_url", {"url": "https://en.wikipedia.org/wiki/Susan_Oliver"}),
        T("The page is the American actress Susan Oliver; she was born February 13, 1932.", "done", {"result": "Susan Oliver (actress): born February 13, 1932"}),
        T("Step 2: W. S. Van Dyke's birth date. Web tools are already looked up.", "fetch_url", {"url": "https://en.wikipedia.org/wiki/W._S._Van_Dyke"}),
        T("This is the film director W. S. Van Dyke (Woodbridge Strong Van Dyke II), born March 21, 1889.", "done", {"result": "W. S. Van Dyke (director): born March 21, 1889"}),
        T("1889 is before 1932, so Van Dyke was born first.", reply="W. S. Van Dyke was born first: March 21, 1889, versus Susan Oliver on February 13, 1932.")))

    # 15. refs: "it"
    add("refs", "What version is KealJones/tp-parse at?", {"first": {"kind": "version", "answers": [tp["package"]["version"]]}, "second": {"kind": "latest_commit", "subject": tp["commits"][0]["subject"], "oid": tp["commits"][0]["oid"]}}, Seq(
        T("Version of KealJones/tp-parse; it's in package.json. I need clone and read tools.", "find", {"query": "clone a github repo and read a file"}),
        T("Clone it.", "git_clone", {"repo": "KealJones/tp-parse"}),
        T("Read package.json.", "read_file", {"path": "/repos/tp-parse/package.json"}),
        lambda req: T(f"tp-parse's package.json says {json_field(req, '', 'version')}.", reply=f"KealJones/tp-parse is at version {json_field(req, '', 'version')}."),
        T("\"It\" is tp-parse, the repo from my last answer, and it's already cloned at /repos/tp-parse. I need the commit log tool.", "find", {"query": "recent commits"}),
        T("git_log, one commit.", "git_log", {"repo": "tp-parse", "count": 1}),
        lambda req: T(f"Newest commit: {log_first(req)[0]}.", reply=f"The last commit on tp-parse is {log_first(req)[0]} ({log_first(req)[1]}): \"{log_first(req)[3]}\".")),
        world=world, user=lambda turn, ep: "and what was the last commit on it?" if turn["n"] == 0 else None)

    # 16. messy, self-correcting voice input
    add("repo_fact", "um so whats the like version of the squiggle repo no wait the tp parse repo thanks", {"kind": "version", "answers": [tp["package"]["version"]]}, Seq(
        T("Voice-typed and it corrects itself: they first said squiggle, then \"no wait\", the tp parse repo. So they want the version of tp-parse. They have KealJones/tp-parse. I need clone and read tools.", "find", {"query": "clone a github repo and read a file"}),
        T("Clone KealJones/tp-parse.", "git_clone", {"repo": "KealJones/tp-parse"}),
        T("The version is in package.json.", "read_file", {"path": "/repos/tp-parse/package.json"}),
        lambda req: T(f"It's tp-parse's package.json; version {json_field(req, '', 'version')}.", reply=f"tp-parse (not squiggle) is at version {json_field(req, '', 'version')}.")), world=world, meta={"messy": True})

    # 17. chat after a task
    add("chat_after", "When did the first Fast and Furious come out?", {"answers": ["2001"]}, Seq(
        T("The release year of the first Fast and Furious film. I'll look it up rather than trust memory.", "find", {"query": "search the web"}),
        T("Search for it.", "web_search", {"query": "The Fast and the Furious 2001 film release date"}),
        T("To be sure it's the first film (The Fast and the Furious), I'll read its page.", "fetch_url", {"url": "https://en.wikipedia.org/wiki/The_Fast_and_the_Furious_(2001_film)"}),
        T("The page is the 2001 film, the first in the franchise, released in June 2001.", reply="The first one, The Fast and the Furious, came out in June 2001. (Source: Wikipedia.)"),
        T("They're just saying thanks. Short and friendly, no tools.", reply="You're welcome!")),
        user=lambda turn, ep: "cool thanks" if turn["n"] == 0 else None)

    # 18. need_math: a number is missing
    add("need_math", "Terry eats a few yogurts a day. They are currently on sale at 4 yogurts for $5.00. How much does he spend on yogurt over 30 days?", {"answer": "75", "missing": "2"}, Seq(
        T("It says \"a few yogurts a day\" — the exact number is missing, and the answer depends on it. I can't look that up; only they know.", "need", {"what": "How many yogurts does Terry eat each day?"}),
        T("They said 2 a day. 2 × 30 = 60 yogurts; at 4 for $5 that's 60 / 4 × 5. I'll compute it with code.", "find", {"query": "run javascript to calculate"}),
        T("run_js.", "run_js", {"code": "const yogurts = 2 * 30;\nconsole.log(yogurts / 4 * 5);"}),
        T("The code printed 75.", reply="He spends $75: 2 a day for 30 days is 60 yogurts, which is 15 packs of 4 at $5.")),
        user=lambda turn, ep: "oh sorry, 2" if turn["n"] == 0 else None)

    # 19. past chat, then asked again in a new chat
    add("past_chat", "When did the first Fast and Furious come out?", {"answers": ["2001"]}, Seq(
        T("The release year of the first Fast and Furious film. I'll look it up.", "find", {"query": "search the web"}),
        T("Read the film's page directly.", "fetch_url", {"url": "https://en.wikipedia.org/wiki/The_Fast_and_the_Furious_(2001_film)"}),
        T("It's the 2001 film, the first one, released in June 2001.", reply="The first one, The Fast and the Furious, came out in June 2001."),
        T("They're asking about something from an earlier chat. Past chats are searchable with find.", "find", {"query": "first Fast and Furious come out"}),
        lambda req: T("A past chat has it: the first Fast and Furious came out in June 2001. That's the answer from before.", reply="Earlier I found that the first one, The Fast and the Furious, came out in June 2001.")),
        user=lambda turn, ep: ("remind me what you found out about when the first fast and furious came out?", "later") if turn["n"] == 0 else None)

    # 20. hermes need, second style
    add("hermes_need", "Flatten the given nested list.", {}, Seq(T("They want a nested list flattened, but there's no list in the message. Only they can give it.", "need", {"what": "What is the nested list you want flattened?"})))
    return out


def readable(res, check):
    lines = [f"## {res['id']} — {res['family']} ({'kept' if check['strict'] else 'NOT kept: ' + '; '.join(check['reasons'])})", ""]
    for c in res.get("calls", []):
        if c.get("kind") == "background":
            continue
        lines.append(f"### call ({c.get('kind')})")
        lines.append("")
        for m in c["messages"]:
            lines.append(f"**{m['role']}**")
            lines.append("```")
            lines.append(m["content"])
            lines.append("```")
        lines.append("**model output (training target)**")
        lines.append("```")
        lines.append(c.get("output") or "")
        lines.append("```")
        lines.append("")
    for t in res.get("turns", []):
        lines.append(f"Reply {t['n']}: {t.get('reply')}")
    return "\n".join(lines) + "\n\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE / "samples"))
    ap.add_argument("--work", default=str(HERE / "work"))
    ap.add_argument("--squiggle", default=os.environ.get("SQUIGGLE_DIR", str(HERE / "squiggle")))
    args = ap.parse_args()
    facts = S.repo_facts(args.work, ["KealJones/squiggle", "KealJones/tp-parse"])
    eps = samples(facts)
    backend = ScriptBackend({e.id: s for e, s in eps})
    runner = Runner(backend, args.squiggle, args.work, concurrency=6, batch_wait=0.05)
    results = runner.run([e for e, _ in eps])
    results.sort(key=lambda r: r["id"])
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    md = ["# Sample episodes", "", "Hand-written model side, real tools and real harness (Squiggle at the pinned commit). "
          "Each `call` is one training example: the messages exactly as engine-wllama.js hands them to the model, and the target output.", ""]
    with open(out / "samples.jsonl", "w") as f:
        for r in results:
            r["check"] = F.check(r)
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            md.append(readable(r, r["check"]))
            print(f"{r['id']}: {'kept' if r['check']['strict'] else 'NOT kept'} {r['check']['reasons'] if not r['check']['strict'] else ''} {r.get('error') or ''}"[:400])
    (out / "SAMPLES.md").write_text("\n".join(md))


if __name__ == "__main__":
    main()
