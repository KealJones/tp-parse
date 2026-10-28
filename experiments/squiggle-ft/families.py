"""Task families: each makes Episodes from real data (sources.py) and checks a finished episode end to end.

Every family exercises one or more habits from docs/harness.md ("What the fine-tune should learn"):
  1 don't guess (look it up, check it's about the right thing)   2 plan multi-step work, done(result) with facts
  3 use a recipe when the prompt has one   4 need instead of bluffing   5 messy voice input   6 plain chat stays plain

check(result) returns {"ok": right answer, "strict": right answer AND the habit the family is about, "reasons": [...]}.
Teacher episodes are kept only when strict; the eval reports both.
"""
import json, random, re, unicodedata
from sqrun import Episode

# ── text helpers ────────────────────────────────────────────────────────────
STOP = set("a an the of in on at to for and or is was are were be by with from as it its this that which who whom what when where how did does do".split())


def norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"(?<=\d),(?=\d{3})", "", s)
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9.$%/ -]", " ", s)).strip()


def toks(s):
    return [t.strip(".-/") for t in norm(s).split() if t.strip(".-/")]


def num(s):
    try:
        return float(str(s).replace(",", "").replace("$", "").rstrip("."))
    except ValueError:
        return None


def answer_in(reply, answers):
    """Every content word of some gold answer appears in the reply (numbers compared as numbers)."""
    rt = toks(reply)
    rset = set(rt)
    rnums = {num(t) for t in rt if num(t) is not None}
    for a in answers if isinstance(answers, (list, tuple)) else [answers]:
        at = [t for t in toks(a) if t not in STOP] or toks(a)
        if not at:
            continue
        good = True
        for t in at:
            n = num(t)
            if n is not None:
                if n not in rnums:
                    good = False
                    break
            elif t not in rset and not any(r.startswith(t) and len(t) >= 5 for r in rset):
                good = False
                break
        if good:
            return True
    return False


def yes_no(reply):
    t = toks(reply)[:12]
    y = any(w in ("yes", "yep", "yeah", "both") for w in t)
    n = any(w in ("no", "nope", "neither", "not") for w in t)
    return "yes" if y and not n else "no" if n and not y else None


# ── voice-dictated, rambling requests (habit 5) ─────────────────────────────
FILL = ["um ", "uh ", "so ", "ok so ", "hey ", "like ", "okay um ", "so basically ", "quick one ", ""]
TAIL = ["", "", " thanks", " thx", " lol", " if you can", " please", " real quick", " ok"]
MISHEAR = [("github", "get hub"), ("readme", "read me"), ("json", "jason"), ("npm", "n p m"), ("repo", "repo"),
           ("commit", "commit"), ("javascript", "java script"), ("version", "version")]


def messy(rng, text, swap=None):
    """Spoken-style rewrite that keeps every fact. swap=(right, wrong): a false start corrected in place.
    Fillers and stutters never go inside a name (between two capitalised words)."""
    s = text.strip()
    if swap and rng.random() < 0.6:
        right, wrong = swap
        fix = rng.choice([" no wait ", " sorry i mean ", " no no ", " uh actually ", ", scratch that, "])
        s = re.sub(re.escape(right), lambda m: wrong + fix + right, s, count=1)
    s = s.rstrip("?.!")
    w = s.split()
    cap = lambda x: bool(re.match(r"[A-Z0-9\[\(\"']", x))
    safe = [i for i in range(1, len(w)) if not (cap(w[i - 1]) and cap(w[i])) and not cap(w[i])]
    if len(w) > 5 and safe and rng.random() < 0.35:              # a stutter / restart
        i = rng.choice(safe)
        w = w[:i] + w[max(0, i - 2):i] + w[i:]
        safe = [j for j in range(1, len(w)) if not (cap(w[j - 1]) and cap(w[j])) and not cap(w[j])]
    if len(w) > 6 and safe and rng.random() < 0.3:               # a filler in the middle
        i = rng.choice(safe)
        w = w[:i] + [rng.choice(["like", "um", "you know", "uh"])] + w[i:]
    s = " ".join(w)
    if rng.random() < 0.85:
        s = s.lower()
    if rng.random() < 0.7:
        s = re.sub(r"[,;:]", "", s)
    if rng.random() < 0.5:
        for a, b in MISHEAR:
            if a in s and rng.random() < 0.5 and a != b:
                s = s.replace(a, b)
    lead = rng.choice(FILL)
    if rng.random() < 0.25:
        lead = rng.choice(["ok im trying to figure something out ", "random question ", "so i was wondering ", "hey can you help me with something "]) + lead
    return (lead + s + rng.choice(TAIL)).strip()


# ── reading a finished episode ──────────────────────────────────────────────
FENCE = re.compile(r"```tool_call\s*([\s\S]*?)(```|$)")


def parse_out(text):
    """Python mirror of engine-wllama splitThinking + parseToolCalls (the self-test checks it agrees with the app)."""
    raw = str(text or "")
    rest = raw.lstrip()
    thinking, body, closed = "", raw, True
    if rest.startswith("<think>"):
        end = rest.find("</think>")
        if end < 0:
            return {"thinking": rest[7:], "text": "", "calls": [], "closed": False}
        thinking, body = rest[7:end], rest[end + 8:].lstrip()
    calls = []
    for m in FENCE.finditer(body):
        blk = m.group(1)
        try:
            obj = json.loads(blk[blk.index("{"): blk.rindex("}") + 1])
        except Exception:
            continue
        name = obj.get("name") or obj.get("tool") if isinstance(obj, dict) else None
        if not name:
            continue
        args = obj.get("arguments", obj.get("args", obj.get("parameters", {})))
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                args = {}
        calls.append({"name": str(name), "arguments": args if isinstance(args, dict) else {}})
    return {"thinking": thinking, "text": body, "calls": calls, "closed": closed}


def turn_calls(result):
    """[[{kind, out, parsed}] per user turn] (background calls dropped)."""
    calls = [c for c in result.get("calls", [])]
    out, i = [], 0
    for t in result.get("turns", []):
        seg = calls[i:i + t.get("calls", 0)]
        i += t.get("calls", 0)
        out.append([{"kind": c.get("kind"), "out": c.get("output") or "", "parsed": parse_out(c.get("output")), "messages": c.get("messages")}
                    for c in seg if c.get("kind") != "background"])
    return out


def names(seg):
    return [c["name"] for x in seg for c in x["parsed"]["calls"][:1]]


def args_of(seg, name):
    return [c["arguments"] for x in seg for c in x["parsed"]["calls"][:1] if c["name"] == name]


def results_of(seg, name):
    """Tool results the model saw, read back from the next prompt: 'Result of <name>:\n<json>'."""
    out = []
    for x in seg:
        for m in x["messages"] or []:
            if m["role"] == "user":
                for blk in re.findall(r"Result of " + re.escape(name) + r":\n(\{.*?\})(?=\n\nResult of |\Z)", m["content"], re.S):
                    out.append(blk)
    return list(dict.fromkeys(out))


def reply_of(result, k=-1):
    t = result.get("turns") or []
    try:
        return t[k].get("reply") or ""
    except IndexError:
        return ""


def asked_user(res, k=0):
    """Turn k ended on a question to the user from need (step mode marks the task waiting; in the chat phase the
    question is simply the reply)."""
    segs = turn_calls(res)
    t = (res.get("turns") or [None] * (k + 1))[k] if len(res.get("turns") or []) > k else None
    if not t or len(segs) <= k or not segs[k]:
        return False
    last = segs[k][-1]["parsed"]["calls"]
    return bool(t.get("waiting")) or bool(last and last[0]["name"] == "need")


def format_problems(seg):
    bad = []
    for x in seg:
        p = x["parsed"]
        o = x["out"].strip()
        if not o.startswith("<think>"):
            bad.append("no <think>")
        elif "</think>" not in o:
            bad.append("thinking never closed")
        if "```tool" in p["text"] and not p["calls"]:
            bad.append("unparseable tool call")
        if len(p["calls"]) > 1:
            bad.append("more than one tool call")
        if p["calls"] and p["text"].split("```tool_call")[0].strip():
            bad.append("text before the tool call")
        if p["calls"] and re.search(r"```\s*\S", p["text"].split("```tool_call", 1)[1].split("```", 1)[-1] if "```tool_call" in p["text"] else ""):
            bad.append("text after the tool call")
        if x["kind"] == "final" and p["calls"]:
            bad.append("tool call in the final reply")
    return bad


def looped(result):
    return any("_(stopped: the model was repeating itself)_" in (t.get("reply") or "") for t in result.get("turns", [])) or \
        any("You were repeating yourself" in json.dumps(c.get("messages", "")) for c in result.get("calls", []))


def nudged(result):
    return any("Finish your thought, then call a tool" in json.dumps(c.get("messages", "")) for c in result.get("calls", []))


def base_check(result, need_tools=True):
    """Problems every family shares: errors, format, loops, stuck steps."""
    r = []
    if result.get("error"):
        r.append("error: " + result["error"][:200])
    segs = turn_calls(result)
    for s in segs:
        r += format_problems(s)
    if looped(result):
        r.append("looped")
    if nudged(result):
        r.append("stalled (nudged)")
    for t in result.get("turns", []):
        if re.search(r"I got stuck on step \d+", t.get("reply") or ""):
            r.append("stuck on a step")
        if "context filled up" in (t.get("reply") or "") or "too long for the model's context" in (t.get("reply") or ""):
            r.append("context full")
    return r


# ── families ────────────────────────────────────────────────────────────────
WEB = {"web_search", "fetch_url"}
REPO_TOOLS = {"git_clone", "git_log", "read_file", "grep", "list_files", "git_status", "github_list_repos"}


def _ep(fam, i, first, gold, world=None, user=None, rng=None, messy_=False, **meta):
    return Episode(id=f"{fam}-{i}", family=fam, first=first, world=world or {}, gold=gold, user=user, meta={"messy": messy_, **meta})


def maybe_messy(rng, text, p, swap=None):
    if rng.random() < p:
        return messy(rng, text, swap), True
    return text, False


# 1. web_fact: a real search question (NQ). Habit 1. Questions whose answer changes over time are skipped.
TIME_BOUND = re.compile(r"\b(current|currently|latest|last|now|recent|recently|newest|this year|this season|who won|who is the|who's the|how many .* (are there|have)|most recent|still)\b", re.I)


def timeless(q):
    return not TIME_BOUND.search(q)


def make_web_fact(rng, row, i, p_messy=0.4):
    q = row["question"].strip()
    q = q[0].upper() + q[1:] + ("?" if not q.endswith("?") else "")
    text, m = maybe_messy(rng, q, p_messy)
    return _ep("web_fact", i, text, {"answers": row["answer"]}, messy_=m)


def check_web_fact(res):
    seg = turn_calls(res)[0] if res.get("turns") else []
    reasons = base_check(res)
    ok = answer_in(reply_of(res, 0), res["gold"]["answers"])
    if not ok:
        reasons.append("wrong or missing answer")
    looked = bool(WEB & set(names(seg)))
    if not looked:
        reasons.append("answered without looking it up")
    if "need" in names(seg):
        reasons.append("asked the user instead of looking it up")
    return {"ok": ok, "strict": ok and looked and not reasons, "reasons": reasons}


# 2. web_compare: a two-hop comparison (HotpotQA). Habits 1, 2.
def make_web_compare(rng, row, i, p_messy=0.4, fam="web_compare"):
    text, m = maybe_messy(rng, row["question"], p_messy)
    return _ep(fam, i, text, {"answer": row["answer"], "titles": row["titles"], "type": row["type"]}, messy_=m)


def same_entity(answer, titles):
    """The Wikipedia title naming the same thing as the answer ("W. S. Van Dyke" for "Woodbridge Strong Van Dyke II")."""
    at = set(toks(answer)) - STOP
    out = []
    for t in titles:
        base = re.sub(r"\s*\(.*?\)\s*", " ", t).strip()
        bt = set(toks(base)) - STOP
        if bt and at and len(at & bt) / len(bt) >= 0.5 and len(bt) > 0:
            out.append(base)
    return out


def check_web_compare(res, k=0):
    segs = turn_calls(res)
    seg = segs[k] if len(segs) > k else []
    reasons = base_check(res)
    gold = res["gold"]["answer"]
    rep = reply_of(res, k)
    if gold.lower() in ("yes", "no"):
        ok = yes_no(rep) == gold.lower()
    else:
        ok = answer_in(rep, [gold] + same_entity(gold, res["gold"].get("titles", [])))
    if not ok:
        reasons.append("wrong or missing answer")
    n = names(seg)
    searches = sum(1 for x in n if x in WEB)
    if searches < 2:
        reasons.append("fewer than two lookups for a two-part question")
    planned = "plan" in n
    if not planned:
        reasons.append("no plan for a multi-step question")
    return {"ok": ok, "strict": ok and not reasons, "reasons": reasons, "planned": planned}


# 3. math: GSM8K, computed with run_js. Habit 1 (keep the maths in the calculator).
def make_math(rng, row, i, p_messy=0.3):
    text, m = maybe_messy(rng, row["question"], p_messy)
    return _ep("math", i, text, {"answer": row["answer"]}, messy_=m)


def check_math(res, k=-1):
    segs = turn_calls(res)
    seg = [x for s in segs for x in s]
    reasons = base_check(res)
    ok = answer_in(reply_of(res, k), [res["gold"]["answer"]])
    if not ok:
        reasons.append("wrong or missing answer")
    ran = "run_js" in names(seg)
    if not ran:
        reasons.append("did the maths in its head")
    return {"ok": ok, "strict": ok and ran and not reasons, "reasons": reasons}


# 4. need_math (held out): a GSM8K problem with its first number taken out; the user supplies it. Habits 4, 1.
NUM_WORD = re.compile(r"(?<![$\d.,])\b(\d+)\b(?![.,]?\d)(?!\s*%)")


def make_need_math(rng, row, i, p_messy=0.3):
    q = row["question"]
    m = NUM_WORD.search(q)
    if not m:
        return None
    value = m.group(1)
    vague = rng.choice(["some", "a few", "a number of", "several"])
    q2 = q[:m.start()] + vague + q[m.end():]
    text, messy_ = maybe_messy(rng, q2, p_messy)

    def user(turn, ep):
        if turn["n"] == 0 and turn.get("waiting"):
            return rng.choice([f"it's {value}", f"{value}", f"oh sorry, {value}", f"um {value} i think. yeah {value}"])
        return None
    return _ep("need_math", i, text, {"answer": row["answer"], "missing": value}, user=user, messy_=messy_)


def check_need_math(res):
    segs = turn_calls(res)
    reasons = base_check(res)
    first = segs[0] if segs else []
    asked = asked_user(res, 0)
    if not asked:
        reasons.append("didn't ask for the missing number")
    c = check_math(res, -1) if len(res.get("turns", [])) > 1 else {"ok": False, "reasons": ["no answer after asking"]}
    ok = asked and c["ok"]
    reasons += [r for r in c["reasons"] if r not in reasons]
    return {"ok": ok, "strict": ok and not reasons, "reasons": reasons}


# 5. repo questions on real public repos. Habits 1, 2 (and owner lookup when only the name is given).
def repo_ref(rng, f, owner_p=0.6):
    return f["repo"] if rng.random() < owner_p else f["name"]


def repo_questions(f):
    """(kind, question templates, gold) that this repo can answer."""
    qs = []
    pkg = f.get("package") or {}
    version = pkg.get("version") or (f.get("pyproject") or {}).get("version")
    if version:
        qs.append(("version", ["What version is {r} at right now?", "which version is {r} on", "what's the current version number in {r}?",
                               "check what version {r} is"], {"answers": [version]}))
    if f.get("license"):
        qs.append(("license", ["What license does {r} use?", "is {r} MIT or what license is it under?", "what's the license on {r}"],
                   {"license": f["license"]}))
    if f.get("commits"):
        c = f["commits"][0]
        qs.append(("latest_commit", ["What's the latest commit in {r}?", "what was the most recent commit to {r} about?",
                                     "tell me the last commit message on {r}"], {"subject": c["subject"], "oid": c["oid"]}))
        qs.append(("latest_author", ["Who made the most recent commit to {r}?", "who committed last in {r}?"], {"answers": [c["author"]]}))
    deps = pkg.get("deps") or []
    if pkg:
        if deps:
            d = deps[0]
            qs.append(("depends", [f"Does {{r}} depend on {d}?", f"is {d} a dependency of {{r}}?"], {"yesno": "yes", "dep": d}))
        for d in ["lodash", "react", "express", "axios", "chalk", "debug"]:
            if d not in deps and d != pkg.get("name") and d not in (pkg.get("devDeps") or []):
                qs.append(("depends", [f"Does {{r}} depend on {d}?", f"is {d} one of {{r}}'s dependencies?"], {"yesno": "no", "dep": d}))
                break
    return qs


def check_repo_answer(kind, gold, reply):
    if kind == "version" or kind == "latest_author":
        return answer_in(reply, gold["answers"])
    if kind == "license":
        lic = gold["license"].split("-")[0]
        return lic.lower() in norm(reply)
    if kind == "latest_commit":
        st = [t for t in toks(gold["subject"]) if t not in STOP]
        rs = set(toks(reply))
        hit = sum(1 for t in st if t in rs)
        return gold["oid"][:7] in reply or (st and hit / len(st) >= 0.6)
    if kind == "depends":
        return yes_no(reply) == gold["yesno"]
    if kind == "where":
        p = gold["path"]
        return p in reply or (p.count("/") >= 1 and p.split("/")[-1] in reply and p.split("/")[-2] in reply) or (p.count("/") == 0 and p in reply)
    return False


def make_repo_fact(rng, facts, i, p_messy=0.35, fam="repo_fact"):
    f = rng.choice(facts)
    qs = repo_questions(f)
    if not qs:
        return None
    kind, tpls, gold = rng.choice(qs)
    r = repo_ref(rng, f)
    text, m = maybe_messy(rng, rng.choice(tpls).format(r=r), p_messy)
    return _ep(fam, i, text, {"kind": kind, "repo": f["repo"], **gold}, world={"repos": world_repos(facts)}, messy_=m, repo=f["repo"])


def world_repos(facts):
    return [{"repo": f["repo"], "description": f.get("description", ""), "default_branch": f.get("branch") or "main"} for f in facts]


def check_repo_fact(res, k=0):
    segs = turn_calls(res)
    seg = segs[k] if len(segs) > k else []
    reasons = base_check(res)
    g = res["gold"]
    ok = check_repo_answer(g["kind"], g, reply_of(res, k))
    if not ok:
        reasons.append("wrong or missing answer")
    looked = bool(REPO_TOOLS & set(names(seg)))
    if not looked:
        reasons.append("answered without looking at the repo")
    return {"ok": ok, "strict": ok and looked and not reasons, "reasons": reasons}


def make_repo_where(rng, facts, i, p_messy=0.35):
    f = rng.choice([x for x in facts if x.get("defs")])
    d = rng.choice(f["defs"])
    r = repo_ref(rng, f)
    tpl = rng.choice(["Where is {n} defined in {r}?", "in {r}, which file has {n}?", "can you find where {n} is defined in the {r} repo",
                      "where does {r} define {n}?", "find the {n} definition in {r} for me"])
    text, m = maybe_messy(rng, tpl.format(n=d["name"], r=r), p_messy)
    return _ep("repo_where", i, text, {"kind": "where", "repo": f["repo"], "path": d["path"], "line": d["line"], "name": d["name"]},
               world={"repos": world_repos(facts)}, messy_=m, repo=f["repo"])


check_repo_where = check_repo_fact


# 6. two-part repo task (plan) — also the first half of the recipe family. Habit 2.
def make_repo_two(rng, facts, i, f=None, fam="repo_two", p_messy=0.3):
    f = f or rng.choice(facts)
    qs = {k: (t, g) for k, t, g in repo_questions(f)}
    if "latest_commit" not in qs or ("version" not in qs and "license" not in qs):
        return None
    k2 = "version" if "version" in qs else "license"
    r = repo_ref(rng, f, 0.8)
    what = {"version": "what version it's at", "license": "what license it uses"}[k2]
    tpl = rng.choice([f"Clone {{r}} and tell me {what} and what the latest commit was.",
                      f"for {{r}}: {what}, and the most recent commit message?",
                      f"can you check {{r}} — {what} plus the last commit"])
    text, m = maybe_messy(rng, tpl.format(r=r), p_messy)
    gold = {"parts": [{"kind": k2, **qs[k2][1]}, {"kind": "latest_commit", **qs["latest_commit"][1]}], "repo": f["repo"]}
    return _ep(fam, i, text, gold, world={"repos": world_repos(facts)}, messy_=m, repo=f["repo"])


def check_repo_two(res, k=0, gold=None):
    segs = turn_calls(res)
    seg = segs[k] if len(segs) > k else []
    reasons = base_check(res)
    g = gold or res["gold"]
    rep = reply_of(res, k)
    parts = [check_repo_answer(p["kind"], p, rep) for p in g["parts"]]
    ok = all(parts)
    if not ok:
        reasons.append("missing part of the answer")
    planned = "plan" in names(seg)
    if not planned:
        reasons.append("no plan for a two-part task")
    return {"ok": ok, "strict": ok and planned and not reasons, "reasons": reasons, "planned": planned}


# 7. recipe: the same kind of task twice, in two chats; the second prompt carries the recipe saved from the first. Habit 3.
def make_recipe_repo(rng, facts, i):
    a, b = rng.sample([f for f in facts if (f.get("package") or {}).get("version") and f.get("commits")], 2)
    e1 = make_repo_two(rng, facts, i, f=a, fam="recipe_repo", p_messy=0.0)
    e2 = make_repo_two(random.Random(rng.random()), facts, i, f=b, fam="recipe_repo", p_messy=0.3)
    if not e1 or not e2:
        return None
    tpl_first = e1.first

    def user(turn, ep):
        if turn["n"] == 0:
            return (e2.first, "second")
        return None
    return _ep("recipe_repo", i, tpl_first, {"first": e1.gold, "second": e2.gold}, world=e1.world, user=user, messy_=e2.meta["messy"])


def recipe_seen(res, k=1):
    segs = turn_calls(res)
    return len(segs) > k and any("## Recipe from a similar task" in (x["messages"][0]["content"] if x["messages"] else "") for x in segs[k])


def check_recipe_repo(res):
    reasons = base_check(res)
    if len(res.get("turns", [])) < 2:
        return {"ok": False, "strict": False, "reasons": reasons + ["second request never ran"]}
    c1 = check_repo_two(res, 0, res["gold"]["first"])
    c2 = check_repo_two(res, 1, res["gold"]["second"])
    seen = recipe_seen(res, 1)
    if not seen:
        reasons.append("no recipe in the second prompt (first task didn't plan, or no match)")
    ok = c1["ok"] and c2["ok"]
    reasons += [f"first: {r}" for r in c1["reasons"] if r not in reasons] + [f"second: {r}" for r in c2["reasons"] if r not in reasons]
    return {"ok": ok, "strict": ok and seen and c1["strict"] and c2["strict"], "reasons": reasons, "recipe_seen": seen, "second_ok": c2["ok"]}


# Held out: the recipe habit on web comparisons (two HotpotQA comparisons of the same shape).
def make_recipe_compare(rng, pair, i):
    a, b = pair
    e1 = make_web_compare(rng, a, i, p_messy=0.0, fam="recipe_compare")
    e2 = make_web_compare(rng, b, i, p_messy=0.3, fam="recipe_compare")

    def user(turn, ep):
        return (e2.first, "second") if turn["n"] == 0 else None
    return _ep("recipe_compare", i, e1.first, {"first": e1.gold, "second": e2.gold}, user=user, messy_=e2.meta["messy"])


def check_recipe_compare(res):
    reasons = base_check(res)
    if len(res.get("turns", [])) < 2:
        return {"ok": False, "strict": False, "reasons": reasons + ["second request never ran"]}
    r2 = dict(res, gold=res["gold"]["second"])
    c2 = check_web_compare(r2, 1)
    seen = recipe_seen(res, 1)
    return {"ok": c2["ok"], "strict": c2["strict"] and seen, "reasons": reasons + c2["reasons"] + ([] if seen else ["no recipe in the second prompt"]), "recipe_seen": seen}


# 8. need_repo: "my repo" with several repos and nothing saying which. Habit 4.
def make_need_repo(rng, facts, i, p_messy=0.4):
    f = rng.choice([x for x in facts if x.get("commits")])
    tpl = rng.choice(["What's the latest commit on my repo?", "can you check the newest commit in the repo", "what changed last in my project?",
                      "who made the last commit on my repo", "whats the most recent commit message on the repo"])
    kind = "latest_author" if "who" in tpl else "latest_commit"
    text, m = maybe_messy(rng, tpl, p_messy)
    c = f["commits"][0]
    gold = {"kind": kind, "repo": f["repo"], **({"answers": [c["author"]]} if kind == "latest_author" else {"subject": c["subject"], "oid": c["oid"]})}

    def user(turn, ep):
        if turn["n"] == 0:
            return rng.choice([f"{f['repo']}", f"oh the {f['name']} one", f"sorry, {f['repo']}", f"um its {f['name']}. {f['repo']} on github"])
        return None
    return _ep("need_repo", i, text, gold, world={"repos": world_repos(facts)}, user=user, messy_=m, repo=f["repo"])


def check_need_repo(res):
    segs = turn_calls(res)
    reasons = base_check(res)
    first = segs[0] if segs else []
    n0 = names(first)
    asked = asked_user(res, 0)
    if not asked:
        reasons.append("guessed which repo instead of asking")
    if set(n0) & {"git_clone", "git_log"}:
        reasons.append("cloned a repo before knowing which")
    ok = bool(asked) and len(res.get("turns", [])) > 1 and check_repo_answer(res["gold"]["kind"], res["gold"], reply_of(res, -1))
    if not ok:
        reasons.append("wrong or missing answer after asking")
    return {"ok": ok, "strict": ok and not reasons, "reasons": reasons}


# 9. memory_repo: memory says which repo "my agent project" is (true facts about Keal's repos). Habits 1, 4 (find, don't ask).
KEAL_FACTS = [
    {"s": "Keal", "p": "builds", "o": "Squiggle, a browser-only AI agent (repo KealJones/squiggle)"},
    {"s": "Keal", "p": "runs fine-tune experiments in", "o": "the repo KealJones/tp-parse"},
    {"s": "squiggle", "p": "is deployed on", "o": "Cloudflare Workers (the relay) and GitHub Pages"},
]
MEM_ASK = {"KealJones/squiggle": ["my agent project", "the squiggle repo", "my browser agent"],
           "KealJones/tp-parse": ["my fine-tune experiments repo", "the repo where I run my experiments", "my experiments repo"]}


def make_memory_repo(rng, facts, i, p_messy=0.4):
    repo = rng.choice(list(MEM_ASK))
    f = next(x for x in facts if x["repo"] == repo)
    c = f["commits"][0]
    what = rng.choice(MEM_ASK[repo])
    kind = rng.choice(["latest_commit", "version"]) if (f.get("package") or {}).get("version") else "latest_commit"
    tpl = {"latest_commit": rng.choice(["What's the latest commit in {w}?", "what did I last commit to {w}", "check the newest commit on {w}"]),
           "version": rng.choice(["What version is {w} at?", "what's the version number of {w} right now"])}[kind]
    text, m = maybe_messy(rng, tpl.format(w=what), p_messy)
    gold = {"kind": kind, "repo": repo, **({"subject": c["subject"], "oid": c["oid"]} if kind == "latest_commit" else {"answers": [f["package"]["version"]]})}
    return _ep("memory_repo", i, text, gold, world={"repos": world_repos(facts), "facts": KEAL_FACTS}, messy_=m, repo=repo)


def check_memory_repo(res):
    c = check_repo_fact(res, 0)
    segs = turn_calls(res)
    if asked_user(res, 0):
        c["reasons"].append("asked the user although memory knew")
        c["strict"] = False
    return c


# 10. past_chat: something looked up in another chat earlier, asked about again. Habit 1 (find, past chats).
def make_past_chat(rng, row, i):
    q = row["question"].strip().rstrip("?")
    first = q[0].upper() + q[1:] + "?"
    ask = rng.choice(["Earlier you looked up {q} for me. What was the answer again?", "remind me what you found out about {q}?",
                      "what did you tell me before about {q}", "you checked {q} the other day — what was it?"]).format(q=q)
    text, m = maybe_messy(rng, ask, 0.4)

    def user(turn, ep):
        return (text, "later") if turn["n"] == 0 else None
    return _ep("past_chat", i, first, {"answers": row["answer"]}, user=user, messy_=m)


def check_past_chat(res):
    reasons = base_check(res)
    if len(res.get("turns", [])) < 2:
        return {"ok": False, "strict": False, "reasons": reasons + ["second chat never ran"]}
    first_ok = answer_in(reply_of(res, 0), res["gold"]["answers"])
    ok = answer_in(reply_of(res, 1), res["gold"]["answers"])
    segs = turn_calls(res)
    n1 = names(segs[1])
    used_memory = bool({"find", "search_history"} & set(n1))
    if not first_ok:
        reasons.append("first chat got it wrong")
    if not ok:
        reasons.append("didn't recall the earlier answer")
    if not used_memory:
        reasons.append("didn't search past chats")
    return {"ok": ok, "strict": ok and first_ok and used_memory and not reasons, "reasons": reasons}


# 11. refs: a follow-up that says "it"/"that one" about the repo from the turn before. Habits 1, 5.
def make_refs(rng, facts, i):
    f = rng.choice([x for x in facts if x.get("commits") and (x.get("package") or {}).get("version")])
    qs = {k: (t, g) for k, t, g in repo_questions(f)}
    first = rng.choice(["What version is {r} at?", "what's the current version of {r}"]).format(r=f["repo"])
    k2 = rng.choice([k for k in ("latest_commit", "latest_author", "license") if k in qs])
    follow = {"latest_commit": ["and what was the last commit on it?", "cool. whats the latest commit there", "and the most recent commit on that one?"],
              "latest_author": ["who made the last commit on it?", "and who committed to it last"],
              "license": ["what license is it under?", "and the license on that one?"]}[k2]
    text = rng.choice(follow)

    def user(turn, ep):
        return text if turn["n"] == 0 else None
    return _ep("refs", i, first, {"first": {"kind": "version", "repo": f["repo"], **qs["version"][1]}, "second": {"kind": k2, "repo": f["repo"], **qs[k2][1]}},
               world={"repos": world_repos(facts)}, user=user, repo=f["repo"])


def check_refs(res):
    reasons = base_check(res)
    if len(res.get("turns", [])) < 2:
        return {"ok": False, "strict": False, "reasons": reasons + ["follow-up never ran"]}
    g = res["gold"]
    ok1 = check_repo_answer("version", g["first"], reply_of(res, 0))
    ok = check_repo_answer(g["second"]["kind"], g["second"], reply_of(res, 1))
    segs = turn_calls(res)
    if not ok1:
        reasons.append("first answer wrong")
    if not ok:
        reasons.append("follow-up wrong")
    if asked_user(res, 1):
        reasons.append("asked which repo although it was just discussed")
    return {"ok": ok, "strict": ok and ok1 and not reasons, "reasons": reasons}


# 12. chat: plain chat stays plain. Habit 6. (Casual openers; no facts in them.)
CHAT = ["hey whats up lol", "hi!", "good morning", "thanks, that worked", "lol nice", "ok cool", "how's it going?", "yo",
        "thank you so much", "haha that's funny", "you're pretty helpful", "night!", "sup", "ugh mondays", "brb",
        "hey squiggle", "ok im back", "that's awesome", "nvm i figured it out", "cool cool cool", "hello there",
        "what's up", "thanks!", "i'm bored lol", "omg yes", "sorry for the late reply", "nice, thank you", "heyyy",
        "good night squiggle", "you rock", "can you say hi to me", "how are you doing today?", "hey hows ur day going",
        "morning! coffee time", "i'm so tired today", "lmao", "ok", "gotcha, thanks", "great job", "hmm interesting",
        "that makes sense", "wow", "never mind", "cheers", "appreciate it", "hey so um nothing really just saying hi",
        "are you there?", "hi again", "ok thanks bye", "you're the best", "have a good one"]


def make_chat(rng, i, text=None):
    t = text or rng.choice(CHAT)
    return _ep("chat", i, t, {})


def check_chat_turn(res, k):
    segs = turn_calls(res)
    seg = segs[k] if len(segs) > k else []
    rep = reply_of(res, k)
    reasons = []
    if names(seg):
        reasons.append("called tools for plain chat")
    if len(rep) > 400:
        reasons.append("long reply to plain chat")
    if "```" in rep or not rep.strip():
        reasons.append("broken or empty chat reply")
    return reasons


def check_chat(res):
    reasons = base_check(res) + check_chat_turn(res, 0)
    return {"ok": not reasons, "strict": not reasons, "reasons": reasons}


# 13. chat_after: a task, then "thanks". Habit 6 in context.
def make_chat_after(rng, row, i):
    ep = make_web_fact(rng, row, i, p_messy=0.3)
    follow = rng.choice(["cool thanks", "nice, thank you!", "ok perfect", "lol ok", "awesome thx", "great, that's what i needed"])

    def user(turn, e):
        return follow if turn["n"] == 0 else None
    return _ep("chat_after", i, ep.first, ep.gold, user=user, messy_=ep.meta["messy"])


def check_chat_after(res):
    c = check_web_fact(res)
    reasons = c["reasons"] + (check_chat_turn(res, 1) if len(res.get("turns", [])) > 1 else ["follow-up never ran"])
    ok = c["ok"] and not check_chat_turn(res, 1) if len(res.get("turns", [])) > 1 else False
    return {"ok": ok, "strict": ok and c["strict"] and not reasons, "reasons": reasons}


# 14. bare_link: the message is just a link (a real Wikipedia page). Habits 1, 5.
def make_bare_link(rng, title, i):
    url = "https://en.wikipedia.org/wiki/" + title.replace(" ", "_")
    text = rng.choice(["{u}", "{u}", "{u} ?", "whats this {u}", "{u} tldr", "can u summarize {u}"]).format(u=url)
    return _ep("bare_link", i, text, {"url": url, "title": title})


def check_bare_link(res):
    seg = turn_calls(res)[0] if res.get("turns") else []
    reasons = base_check(res)
    urls = [a.get("url", "") for a in args_of(seg, "fetch_url")]
    gold = res["gold"]
    fetched = any(u.rstrip("/").split("/wiki/")[-1].replace(" ", "_").lower() == gold["url"].split("/wiki/")[-1].lower() for u in urls)
    rep = reply_of(res, 0)
    words = [w for w in toks(gold["title"]) if w not in STOP and len(w) > 2]
    about = any(w in toks(rep) for w in words) if words else True
    if not fetched:
        reasons.append("didn't read the link")
    if len(rep) < 40 or not about:
        reasons.append("reply isn't about the page")
    ok = fetched and len(rep) >= 40 and about
    return {"ok": ok, "strict": ok and not reasons, "reasons": reasons}


# 15. web_bridge (held out): a two-hop bridge question. Habits 1, 2.
def make_web_bridge(rng, row, i):
    return make_web_compare(rng, row, i, p_messy=0.3, fam="web_bridge")


def check_web_bridge(res):
    c = check_web_compare(res)
    return c


# ── registry ───────────────────────────────────────────────────────────────
CHECK = {
    "web_fact": check_web_fact, "web_compare": check_web_compare, "web_bridge": check_web_bridge, "math": check_math,
    "need_math": check_need_math, "repo_fact": check_repo_fact, "repo_where": check_repo_where, "repo_two": check_repo_two,
    "recipe_repo": check_recipe_repo, "recipe_compare": check_recipe_compare, "need_repo": check_need_repo,
    "memory_repo": check_memory_repo, "past_chat": check_past_chat, "refs": check_refs, "chat": check_chat,
    "chat_after": check_chat_after, "bare_link": check_bare_link,
}
HABIT = {
    "web_fact": "look it up", "web_compare": "plan + look up two things", "web_bridge": "plan a two-hop lookup (held out)",
    "math": "compute with run_js", "need_math": "ask for a missing number (held out)", "repo_fact": "look in the repo",
    "repo_where": "find a definition", "repo_two": "plan a two-part repo task", "recipe_repo": "use a recipe",
    "recipe_compare": "use a recipe on web lookups (held out)", "need_repo": "ask which repo", "memory_repo": "use memory, don't ask",
    "past_chat": "find an earlier chat", "refs": "follow 'it' to the last repo", "chat": "plain chat stays plain",
    "chat_after": "a task, then plain thanks", "bare_link": "read a bare link", "hermes_compute": "compute (Hermes requests)",
    "hermes_need": "ask for missing input (Hermes requests)",
}
HELD_OUT = {"web_bridge", "need_math", "recipe_compare"}


def check(res):
    fam = res["family"]
    if fam.startswith("hermes_"):
        import hermes
        return hermes.check(res)
    try:
        return CHECK[fam](res)
    except Exception as e:
        return {"ok": False, "strict": False, "reasons": [f"checker crashed: {e!r}"]}
