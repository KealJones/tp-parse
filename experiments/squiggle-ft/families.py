"""Task families: each makes Episodes from real data (sources.py) and checks a finished episode end to end.

Every family exercises one or more habits from docs/harness.md ("What the fine-tune should learn"):
  1 don't guess (look it up, check it's about the right thing)   2 plan multi-step work, done(result) with facts
  3 use a recipe when the prompt has one   4 need instead of bluffing   5 messy voice input   6 plain chat stays plain

check(result) returns {"ok": right answer, "strict": right answer AND the habit the family is about, "reasons": [...]}.
Teacher episodes are kept only when strict; the eval reports both.
"""
import json, random, re, unicodedata
from pathlib import Path
import quality as Q
from sqrun import Episode

HERE = Path(__file__).resolve().parent

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
    rn = None
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
            elif "/" in t or "." in t:            # a path or file: anywhere inside a longer path counts ("/repos/x/src/a.py")
                rn = norm(reply) if rn is None else rn
                if not re.search(r"(?<![\w.])" + re.escape(t) + r"(?![\w])", rn):
                    good = False
                    break
            elif t not in rset and not any(r.startswith(t) and len(t) >= 5 for r in rset):
                good = False
                break
        if good:
            return True
    return False


NON_ANSWER = re.compile(r"\b(could ?n[o']t (be )?(find|found|confirm|determine|tell|verify|locate)|can ?n[o']t (find|confirm|compare|determine|tell|say|verify)|"
                        r"cannot (find|confirm|compare|determine|tell|say|verify)|unable to|not sure|no (information|relevant results?|results?|data|match(es)?)|"
                        r"was not found|wasn't found|could not be found|not (be )?found|i don'?t know|unknown|"
                        r"not (a |an )?(confirmed|verified|recognized|recognised|listed|mentioned|stated|shown|given|available|clear)|unverified|unconfirmed|"
                        r"(doesn'?t|does not|didn'?t|did not) (say|mention|list|state|show|give|confirm|specify)|(is|was|remains) unclear|"
                        r"neither (source|page|result|lookup|search)\b|no (clear|definitive|direct) answer)\b", re.I)
# A hedged answer is a guess, not an answer: the habit is to look again or say it couldn't be verified.
HEDGE = re.compile(r"\b(probably|likely|most likely|i believe|i think|i guess|presumably|possibly|perhaps|might be|may be|"
                   r"seems to be|appears to be|should be|i assume|assuming|my (best )?guess|if i recall|as far as i know|afaik)\b", re.I)
# A list of candidates ("either A or B", "A or possibly B") isn't an answer either.
CANDIDATES = re.compile(r"\b(either\b.{1,80}\bor\b|or (possibly|maybe|perhaps|alternatively)\b|one of (the following|these|them)\b|"
                        r"sources (differ|disagree|conflict)|conflicting (sources|results|information))", re.I)


def non_answer(reply):
    """A reply that says it couldn't find or decide something isn't an answer, even if it names the right thing."""
    return bool(NON_ANSWER.search(reply or ""))


def hedged(reply):
    return bool(HEDGE.search(reply or "")) or bool(CANDIDATES.search(reply or ""))


def negated(reply, answers):
    """The gold answer appears right after a negation ("not X", "isn't X", "rather than X")."""
    r = norm(reply)
    for a in answers if isinstance(answers, (list, tuple)) else [answers]:
        at = [t for t in toks(a) if t not in STOP]
        if not at:
            continue
        head = re.escape(at[0])
        # norm() turns "isn't" into "isn t"
        if re.search(r"\b(not|never|(isn|wasn|aren|weren|doesn|didn) t|rather than|instead of|other than|excluding|except)\s+(\w+\s+){0,2}" + head + r"\b", r):
            return True
    return False


def yes_no(reply):
    t = toks(reply)[:12]
    y = any(w in ("yes", "yep", "yeah", "both") for w in t)
    n = any(w in ("no", "nope", "neither", "not") for w in t)
    return "yes" if y and not n else "no" if n and not y else None


# ── voice-dictated, rambling requests (habit 5) ─────────────────────────────
FILL = ["um ", "uh ", "so ", "ok so ", "hey ", "like ", "okay um ", "so basically ", "quick one ", ""]
TAIL = ["", "", " thanks", " thx", " lol", " please", " pls"]   # never words that could read as part of a name
MISHEAR = [("github", "get hub"), ("readme", "read me"), ("json", "jason"), ("npm", "n p m"), ("javascript", "java script")]
# Keal's texting habits and common dictation slips, on everyday words only (never on names, numbers or paths).
SLANG = {"and": "n", "you": "u", "your": "ur", "please": "pls", "thanks": "thx", "about": "abt", "because": "cuz",
         "probably": "prolly", "really": "rly", "what": "wat", "version": "verison", "latest": "lastest",
         "which": "wich", "defined": "defind", "license": "lisence", "commit": "comit", "people": "ppl", "with": "w/"}


def messy(rng, text, swap=None, keep=(), phrases=()):
    """Spoken-style rewrite that keeps every fact. swap=(right, wrong): a false start corrected in place.
    Fillers and stutters never go inside a name (between two capitalised words) or inside a phrase in `phrases`
    (an alias like "my agent project": AUDIT_V1 problem 7, "my um agent project"). `keep`: words SLANG leaves alone."""
    s = text.strip()
    if swap and rng.random() < 0.6:
        right, wrong = swap
        fix = rng.choice([" no wait ", " sorry i mean ", " no no ", " uh actually ", ", scratch that, "])
        s = re.sub(re.escape(right), lambda m: wrong + fix + right, s, count=1)
    s = s.rstrip("?.!")
    w = s.split()
    cap = lambda x: bool(re.match(r"[A-Z0-9\[\(\"']", x))

    def inside(ws, i):
        """Inserting between ws[i-1] and ws[i] would split a protected phrase."""
        low = [x.lower().strip(",.?!") for x in ws]
        for ph in phrases:
            pw = ph.lower().split()
            for st in range(0, len(low) - len(pw) + 1):
                if low[st:st + len(pw)] == pw and st < i < st + len(pw):
                    return True
        return False
    safe = [i for i in range(1, len(w)) if not (cap(w[i - 1]) and cap(w[i])) and not cap(w[i]) and not inside(w, i)]
    safe_st = [i for i in safe if not any(re.search(r"\d", x) for x in w[max(0, i - 2):i])]
    if len(w) > 5 and safe_st and rng.random() < 0.35:           # a stutter / restart (never repeats a number)
        i = rng.choice(safe_st)
        w = w[:i] + w[max(0, i - 2):i] + w[i:]
        safe = [j for j in range(1, len(w)) if not (cap(w[j - 1]) and cap(w[j])) and not cap(w[j]) and not inside(w, j)]
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
    if rng.random() < 0.6:                                       # "n" for "and", "u", typos
        rate = rng.choice([0.3, 0.6])
        s = " ".join(SLANG[w] if w in SLANG and w not in keep and rng.random() < rate else w for w in s.split(" "))
    if rng.random() < 0.2:                                       # run-on: a second thought tacked on
        s += rng.choice([" and like if thats not easy just tell me", " or whatever u can find", " idk if that makes sense",
                         " i think thats it", " n let me know"])
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
    return bool(t.get("waiting")) or bool(t.get("asked")) or bool(last and last[0]["name"] == "need")


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


PLAIN = {("chat", 0), ("chat_after", 1)}       # (family, user turn) that are plain chat
PERSONAL = {("personal", 0)}                    # (family, user turn) that are personal advice / empathy


def plain_mode(fam, k):
    """What quality.py's `plain` argument is for turn k of a family: "personal", True (plain chat) or False."""
    return "personal" if (fam, k) in PERSONAL else (fam, k) in PLAIN


def call_problems(result):
    """Keal's quality bar (quality.py) for every model call, plus: a reply after web or repo tools cites its sources."""
    r = []
    fam = result.get("family")
    for k, seg in enumerate(turn_calls(result)):
        plain = plain_mode(fam, k)
        for j, x in enumerate(seg):
            probs, _ = Q.output_problems(x["out"], x["messages"] or [], x["kind"], plain)
            r += [f"turn {k + 1} call {j + 1} ({x['kind']}): {p}" for p in probs]
        used = set(names(seg))
        t = (result.get("turns") or [])[k] if k < len(result.get("turns") or []) else {}
        reply = t.get("reply") or ""
        asked = bool(t.get("asked")) or bool(t.get("waiting"))
        searched_nothing = fam in UNKNOWN_FAMS and NOT_KNOWN.search(reply)     # nothing found is the finding; no page to cite
        if used & (WEB | REPO_TOOLS | COMPUTE) and not asked and not searched_nothing:
            if not Q.final_cites(reply):
                r.append(f"turn {k + 1}: the reply doesn't say where its facts came from (page, repo, file)")
            elif not cited_source_called(reply, seg):
                r.append(f"turn {k + 1}: the reply cites a source this turn never used")
        if not plain and narrated_without_tools(seg, reply):
            r.append(f"turn {k + 1}: says it checked / confirmed / found something, but no tool result was seen")
        req = request_text(seg)
        for line in check_refers_to_result(seg, req)[:2]:
            r.append(f"turn {k + 1}: a Check line doesn't refer to the result it follows: {line!r}")
        if not asked:
            for n in computed_numbers_grounded(seg, reply)[:3]:
                r.append(f"turn {k + 1}: stated a computed number ({n:g}) that no calculate result gave")
        if "run_js" in used and fam in ("math", "need_math", "hermes_compute", "lookup_then_compute", "math_pair"):
            r.append(f"turn {k + 1}: computes via run_js (plain arithmetic goes through calculate)")
        if fam in ONE_LOOKUP and planned(seg):
            r.append(f"turn {k + 1}: made a plan for a one-lookup request")
        for d in done_ungrounded(seg, req)[:2]:
            r.append(f"turn {k + 1}: a done result carries nothing from this step's results or the request: {d!r}")
    return r


def done_ungrounded(seg, request=""):
    """done results whose concrete tokens (numbers, paths, capitalised or quoted words) are all absent from the tool
    results this step saw and from the request: narration with a capital letter ("The repo is Cloned")."""
    bad = []
    rq = set(toks(request))
    for x in seg:
        for c in x["parsed"]["calls"][:1]:
            if c["name"] != "done":
                continue
            r = str(c["arguments"].get("result", ""))
            seen = set()
            for m in x["messages"] or []:
                if m["role"] == "user" and m["content"].startswith("Result of "):
                    seen |= set(toks(m["content"]))
            concrete = subtoks(" ".join(re.findall(r"\d[\d.,]*|/[\w./-]+|[A-Za-z][\w.-]*/[\w.-]+|\"[^\"]+\"|'[^']+'|[\w.-]+\.\w{1,4}\b|(?<![.!?]\s)(?<!^)[A-Z][a-z]+|[0-9a-f]{7,40}", r)))
            concrete -= STOP
            if concrete and not (concrete & (subtoks_set(seen) | subtoks_set(rq))):
                bad.append(r[:60])
    return bad


def subtoks(text):
    """Tokens plus their pieces split on / - . : so a path, a date or a hash matches however it was joined."""
    return subtoks_set(set(toks(text)))


def subtoks_set(tokens):
    out = set()
    for t in tokens:
        out.add(t)
        out |= {p for p in re.split(r"[/.:-]", t) if len(p) >= 3}
    return out


def grounded_answer_problems(seg, answers, request="", early=True):
    """Why a right-looking answer still isn't earned: the gold isn't in any tool result of the turn, or (early) it
    appeared in the model's own text before a result had it (a guess that got confirmed, or head knowledge). early is
    off when the "answer" is a place to look (the manifest for a "doesn't depend on" answer) rather than a fact."""
    p = []
    if not answer_grounded(seg, answers):
        p.append("the answer appears in no tool result of this turn (unverified claim)")
    elif early and guessed_early(seg, answers, request):
        p.append("the answer was written (thinking, query or path) before any tool result contained it")
    return p


def base_check(result, need_tools=True):
    """Problems every family shares: errors, the quality bar, loops, stuck steps."""
    r = []
    if result.get("error"):
        r.append("error: " + result["error"][:200])
    if result.get("capped"):
        r.append("too many model calls (stopped)")
    r += call_problems(result)
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


def plan_follows_recipe(res, k):
    """In turn k, the plan reuses the recipe's steps (word overlap of at least a third)."""
    segs = turn_calls(res)
    if len(segs) <= k:
        return False
    sys = next((x["messages"][0]["content"] for x in segs[k] if x["messages"]), "")
    m = re.search(r"## Recipe from a similar task[^\n]*\n(.*?)(\n## |\Z)", sys, re.S)
    plans = args_of(segs[k], "plan")
    if not m or not plans:
        return False
    rw = set(toks(re.sub(r"<\w+>", " ", m.group(1)))) - STOP
    pw = set(toks(" ".join(map(str, plans[0].get("steps", []))))) - STOP
    return bool(rw) and len(rw & pw) / len(rw | pw) >= 0.3


# ── grounding: facts must come from this turn's tool results ────────────────
# AUDIT_V1 problem 1: the v1 checkers only asked whether some tool was called, never whether the answer came from a
# result. These helpers read the results back out of the prompts the model saw (results_of) and tie the answer, the
# citation, the Check lines and every computed number to them.
RESULT_RE = re.compile(r"Result of ([a-z_]+):\n(\{.*?\})(?=\n\nResult of |\Z)", re.S)


def turn_results(seg):
    """[(tool, json text, is_error)] for every tool result the model saw in this turn, in order, deduplicated."""
    out, seen = [], set()
    for x in seg:
        for m in x["messages"] or []:
            if m["role"] != "user":
                continue
            for name, blk in RESULT_RE.findall(m["content"]):
                if blk in seen:
                    continue
                seen.add(blk)
                err = False
                try:
                    d = json.loads(blk)
                    err = isinstance(d, dict) and "error" in d and not d.get("result") and not d.get("content") and not d.get("results")
                except Exception:
                    pass
                out.append((name, blk, err))
    return out


def good_results(seg):
    return [(n, unescape(b)) for n, b, e in turn_results(seg) if not e]


def unescape(blob):
    """JSON escapes as plain text, so numbers and words next to a \\t or \\n in a result are seen as such."""
    return re.sub(r"\\[ntr]", " ", blob).replace('\\"', '"')


def request_text(seg):
    """The user's own words in this turn (the request and their answers), never tool results."""
    parts = []
    for x in seg:
        for m in x["messages"] or []:
            if m["role"] == "user" and not m["content"].startswith("Result of "):
                parts.append(m["content"].split("\n\nWork on step")[0].split("\n\nEvery step is done")[0])
    return "\n".join(dict.fromkeys(parts))


def answer_grounded(seg, answers):
    """Some gold answer appears in a (non-error) tool result of this turn."""
    return any(answer_in(b, answers) for _, b in good_results(seg))


def guessed_early(seg, answers, request=""):
    """The gold answer (its words that aren't already in the request) shows up in the model's own text (thinking, a
    query, a path) before any tool result that contains it: a guess that was then confirmed, or head knowledge."""
    rq = set(toks(request)) | STOP
    seen_in_result = False
    for x in seg:
        if not seen_in_result:
            for m in x["messages"] or []:
                if m["role"] == "user" and m["content"].startswith("Result of ") and answer_in(unescape(m["content"]), answers):
                    seen_in_result = True
        if seen_in_result:
            return False
        own = x["out"]
        for a in answers if isinstance(answers, (list, tuple)) else [answers]:
            at = [t for t in toks(a) if t not in rq and (len(t) >= 3 or num(t) is not None)]
            if at and answer_in(own, [" ".join(at)]):
                return True
    return False


def cited_source_called(reply, seg):
    """The reply cites a page, file, repo, log, search or calculator that this turn actually used (the citation's shape
    alone, quality.final_cites, accepted "from memory" and "and/or")."""
    r = norm(reply)
    calls = [c for x in seg for c in x["parsed"]["calls"][:1]]
    used = {c["name"] for c in calls}
    args = " ".join(json.dumps(c["arguments"]) for c in calls)
    results = " ".join(b for _, b in good_results(seg))
    # 1. a URL, path or owner/name the model passed to a tool, or a file it read
    for tok in re.findall(r"https?://\S+|/repos/\S+|/home/\S+|[A-Za-z][\w.-]*/[A-Za-z][\w.-]*|[\w-]+\.(?:json|md|js|py|ts|toml|txt)", reply or ""):
        t = tok.rstrip(".,;:)")
        if t.lower() in args.lower() or t.lower() in results.lower():
            return True
    # 2. a page title the search or fetch returned
    titles = re.findall(r"\\n\d+\. ([^\\\n]{3,80})\\n", results) + re.findall(r'"title":"([^"]{3,80})"', results)
    if any(norm(t.split(" - Wikipedia")[0]) and norm(t.split(" - Wikipedia")[0]) in r for t in titles):
        return True
    # 3. the kind of source, matching a tool that ran
    kinds = [("git log", {"git_log"}), ("commit", {"git_log"}), ("package.json", {"read_file", "grep"}), ("pyproject", {"read_file", "grep"}),
             ("readme", {"read_file", "grep"}), ("wikipedia", WEB), ("web search", {"web_search"}), ("search result", {"web_search"}),
             ("the page", {"fetch_url"}), ("that page", {"fetch_url"}), ("its page", {"fetch_url"}), ("the article", {"fetch_url"}),
             ("calculat", {"calculate"}), ("the repo", REPO_TOOLS), ("the file", {"read_file", "grep"}), ("grep", {"grep"}),
             ("past chat", {"find", "search_history"}), ("earlier chat", {"find", "search_history"}), ("memory", {"find"})]
    return any(k in r and used & tools for k, tools in kinds)


def check_lines(x):
    return re.findall(r"(?m)^Check:[ \t]+(.*)$", x["parsed"]["thinking"])


def check_refers_to_result(seg, request=""):
    """Every Check line brings something from the result it follows: a quoted span of it, or a word that is in the
    result and not in the request (AUDIT_V1 problem 8: 125/1,814 Check lines restated the request)."""
    bad = []
    rq = set(toks(request)) | STOP
    for x in seg:
        last = next((m for m in reversed(x["messages"] or []) if m["role"] == "user"), None)
        if not last or not last["content"].startswith("Result of "):
            continue
        res = last["content"]
        rtoks = set(toks(res)) - rq
        for line in check_lines(x):
            quoted = [q for q in re.findall(r"[\"“]([^\"”]{6,})[\"”]", line) if norm(q) in norm(res)]
            fresh = [t for t in toks(line) if t in rtoks and len(t) >= 3]
            if not quoted and not fresh:
                bad.append(line[:80])
    return bad


NARRATED = re.compile(r"\b(i |we )?(checked|confirmed|verified|searched|looked (it |this |that )?up|found|according to|a quick (check|search))\b", re.I)


def narrated_without_tools(seg, reply):
    """"I checked / confirmed / found" in the thinking or reply of a turn that saw no tool result (gemma-traces lesson 2)."""
    if good_results(seg):
        return False
    text = " ".join(x["parsed"]["thinking"] for x in seg) + " " + (reply or "")
    return bool(NARRATED.search(text))


def planned(seg):
    return "plan" in names(seg)


ARITH = re.compile(r"\b(total|totals|sum|altogether|in all|combined|difference|apart|more than|less than|fewer than|times as|percent|average|"
                   r"left over|remaining|remainder|earns?|spent|spends?|saves?|pays?|paid|profit|years? (older|younger|apart)|"
                   r"ratio|half of|double|twice|triple|minus|plus|divided|multiplied|equals?|comes to|adds up|works out)\b|[%$€£=×÷]|\d\s*[+*]\s*\d", re.I)
NUMBER = re.compile(r"(?<![\w.])[-+]?\$?\d[\d,]*(?:\.\d+)?%?(?![\w])")
REFNUM = re.compile(r"\b(line|lines|page|pages|step|steps|result|results|version|v|chapter|section|no|number|#|issue|pr|id|commit|build)\s*$", re.I)


def numbers_in(text, skip_refs=False):
    out = set()
    for mm in NUMBER.finditer(text or ""):
        m = mm.group(0)
        if skip_refs and (REFNUM.search(text[max(0, mm.start() - 12):mm.start()]) or re.match(r"[-/.]\d", text[mm.end():mm.end() + 2] or "")):
            continue
        n = num(m.rstrip("%"))
        if n is not None:
            out.add(round(n, 6))
            if m.endswith("%"):
                out.add(round(n / 100, 6))
    return out


def calc_results(seg):
    out = set()
    for name, blk in good_results(seg):
        if name != "calculate":
            continue
        try:
            d = json.loads(blk)
        except Exception:
            continue
        if isinstance(d.get("result"), (int, float)):
            v = float(d["result"])
            out |= {round(v, 6), round(v, 2), round(v, 1), round(v, 0)}
    return out


def computed_numbers_grounded(seg, reply):
    """CORPUS_V2 §2h: a number in the reply or a done result that isn't copied from the request or a tool result, and
    sits in a sentence with arithmetic wording, must equal a calculate result of this turn. Returns the offending
    numbers."""
    seen = numbers_in(request_text(seg)) | set().union(*(numbers_in(b) for _, b in good_results(seg))) if seg else set()
    calc = calc_results(seg)
    said = [reply or ""] + [str(a.get("result", "")) for a in args_of(seg, "done")]
    bad = []
    for text in said:
        for sent in re.split(r"(?<=[.!?])\s+|\n+", text):
            if not ARITH.search(sent):
                continue
            for n in numbers_in(sent, skip_refs=True):
                if n in seen or n in calc or any(abs(n - c) < 1e-6 for c in calc):
                    continue
                if 1800 <= n <= 2100 and not re.search(r"\b(apart|difference|older|younger|years)\b", sent, re.I):
                    continue                          # a year, not a computation
                if n in (0, 1, 2) and str(int(n)) not in sent:     # "half", "twice" are words, not stated numbers
                    continue
                bad.append(n)
    return sorted(set(bad))


def need_questions(seg):
    return [str(a.get("what", "")) for a in args_of(seg, "need")]


def need_new_numbers(seg, request=""):
    """Numbers in a need question that the request didn't contain: a value the model assumed and is asking to confirm."""
    had = numbers_in(request)
    return sorted(n for q in need_questions(seg) for n in numbers_in(q) if n not in had)


def need_guesses(seg, candidates, allow_after=("github_list_repos",)):
    """A need question that names a candidate answer (a repo, a number, an entity) is a guess dressed as a question
    (TEACHER.md habit 1: never put a guessed answer inside a need question). Allowed once a tool listed the candidates."""
    listed = False
    for x in seg:
        for c in x["parsed"]["calls"][:1]:
            if c["name"] in allow_after:
                listed = True
            if c["name"] == "need" and not listed:
                q = norm(str(c["arguments"].get("what", "")))
                for cand in candidates:
                    ct = [t for t in toks(cand) if t not in STOP]
                    if ct and all(t in q.split() for t in ct):
                        return cand
    return None


# ── families ────────────────────────────────────────────────────────────────
WEB = {"web_search", "fetch_url"}
REPO_TOOLS = {"git_clone", "git_log", "read_file", "grep", "list_files", "git_status", "github_list_repos"}
COMPUTE = {"calculate"}
ONE_LOOKUP = {"web_fact", "chat_after", "repo_fact", "repo_where", "bare_link", "memory_repo", "need_repo", "refs", "past_chat",
              "math", "need_math", "hermes_compute", "hermes_need", "unknown_word", "unknown_action", "need_web", "near_miss"}


def _ep(fam, i, first, gold, world=None, user=None, rng=None, messy_=False, **meta):
    return Episode(id=f"{fam}-{i}", family=fam, first=first, world=world or {}, gold=gold, user=user, meta={"messy": messy_, **meta})


def maybe_messy(rng, text, p, swap=None, keep=(), phrases=()):
    if rng.random() < p:
        return messy(rng, text, swap, keep, phrases), True
    return text, False


# 1. web_fact: a real search question (NQ). Habit 1. Questions whose answer changes over time are skipped.
TIME_BOUND = re.compile(r"\b(current|currently|latest|last|now|recent|recently|new|newest|next|upcoming|present|today|this year|"
                        r"this season|who won|who is the|who's the|who is in charge|how many .* (are there|have)|most recent|still)\b", re.I)


def timeless(q):
    return not TIME_BOUND.search(q)


def make_web_fact(rng, row, i, p_messy=0.45):
    q = row["question"].strip()
    q = q[0].upper() + q[1:] + ("?" if not q.endswith("?") else "")
    text, m = maybe_messy(rng, q, p_messy)
    return _ep("web_fact", i, text, {"answers": row["answer"]}, messy_=m)


def check_web_fact(res):
    seg = turn_calls(res)[0] if res.get("turns") else []
    reasons = base_check(res)
    rep = reply_of(res, 0)
    ok = answer_in(rep, res["gold"]["answers"]) and not non_answer(rep) and not negated(rep, res["gold"]["answers"])
    if not ok:
        reasons.append("wrong or missing answer")
    elif hedged(rep):
        reasons.append("the answer is hedged or a list of candidates (look again or say it couldn't be verified)")
    looked = bool(WEB & set(names(seg)))
    if not looked:
        reasons.append("answered without looking it up")
    if "need" in names(seg):
        reasons.append("asked the user instead of looking it up")
    if ok:
        reasons += grounded_answer_problems(seg, res["gold"]["answers"], res.get("first", ""))
    return {"ok": ok, "strict": ok and looked and not reasons, "reasons": reasons}


# 2. web_compare: a two-hop comparison (HotpotQA). Habits 1, 2.
def make_web_compare(rng, row, i, p_messy=0.45, fam="web_compare"):
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


def first_mention(reply, names_):
    """Character position of the earliest mention of any of these names in the reply (content words), or None."""
    r = norm(reply)
    best = None
    for n in names_:
        nt = [t for t in toks(n) if t not in STOP] or toks(n)
        if not nt:
            continue
        pos = [m.start() for t in nt[:2] for m in [re.search(r"\b" + re.escape(t) + r"\b", r)] if m]
        if len(pos) == len(nt[:2]):
            best = min(pos) if best is None else min(best, min(pos))
    return best


def picked(reply, gold, titles):
    """For an "A or B" question: the reply picks the gold if the gold is the first candidate it names, not under a
    negation, and no other candidate is named before it (AUDIT_V1 problem 2: naming both used to pass)."""
    gold_names = [gold] + same_entity(gold, titles)
    others = [t for t in titles if not same_entity(gold, [t]) and norm(t) not in norm(gold)]
    gp, op = first_mention(reply, gold_names), first_mention(reply, others)
    if gp is None or negated(reply, gold_names):
        return False
    return op is None or gp < op


def check_web_compare(res, k=0):
    segs = turn_calls(res)
    seg = segs[k] if len(segs) > k else []
    reasons = base_check(res)
    gold = res["gold"]["answer"]
    rep = reply_of(res, k)
    titles = res["gold"].get("titles", [])
    if gold.lower() in ("yes", "no"):
        ok = yes_no(rep) == gold.lower()
    else:
        ok = answer_in(rep, [gold] + same_entity(gold, titles))
        if same_entity(gold, titles):                 # an "A or B" question: which one did the reply pick?
            ok = ok and picked(rep, gold, titles)
    ok = ok and not non_answer(rep)
    if not ok:
        reasons.append("wrong or missing answer")
    elif hedged(rep):
        reasons.append("the answer is hedged or a list of candidates")
    if ok and gold.lower() not in ("yes", "no"):
        reasons += grounded_answer_problems(seg, [gold] + same_entity(gold, titles), res.get("first", ""))
    # Each compared entity must have been looked at: its page title in some result of this turn.
    missing = [t for t in titles if not answer_in(" ".join(b for _, b in good_results(seg)), [re.sub(r"\s*\(.*?\)\s*", " ", t)])]
    if ok and missing:
        reasons.append("compared without a result about: " + ", ".join(missing[:2]))
    n = names(seg)
    searches = sum(1 for x in n if x in WEB)
    if searches < 2:
        reasons.append("fewer than two lookups for a two-part question")
    planned = "plan" in n
    if not planned:
        reasons.append("no plan for a multi-step question")
    return {"ok": ok, "strict": ok and not reasons, "reasons": reasons, "planned": planned}


# 3. math: GSM8K, computed with calculate (CORPUS_V2 §2h: never in the head, never run_js). Habit 1.
def make_math(rng, row, i, p_messy=0.45):
    text, m = maybe_messy(rng, row["question"], p_messy)
    return _ep("math", i, text, {"answer": row["answer"]}, messy_=m)


def check_math(res, k=-1):
    segs = turn_calls(res)
    seg = segs[k] if segs else []
    reasons = base_check(res)
    rep = reply_of(res, k)
    ok = answer_in(rep, [res["gold"]["answer"]]) and not non_answer(rep)
    if not ok:
        reasons.append("wrong or missing answer")
    elif hedged(rep):
        reasons.append("the answer is hedged")
    ran = bool(COMPUTE & set(names(seg)))
    if not ran:
        reasons.append("did the maths in its head (no calculate call)")
    g = num(res["gold"]["answer"])
    if ok and ran and g is not None and not any(abs(g - c) < 1e-6 for c in calc_results(seg)):
        reasons.append("the answer isn't a calculate result of this turn (computed in its head or copied)")
    if ok and guessed_early(seg, [res["gold"]["answer"]], request_text(seg)):
        reasons.append("the answer was written before calculate returned it")
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
        if turn["n"] == 0 and (turn.get("asked") or turn.get("waiting")):
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
    if need_new_numbers(first, res.get("first", "")):
        reasons.append("the need question contains a number the request didn't have (an assumed value inside the question)")
    if COMPUTE & set(names(first)) or "run_js" in names(first):
        reasons.append("computed before asking for the missing number")
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
    if non_answer(reply):
        return False
    if kind == "version" or kind == "latest_author":
        return answer_in(reply, gold["answers"])
    if kind == "license":
        lic = gold["license"].split("-")[0]          # the SPDX id as a whole word: "commit" is not "MIT" (AUDIT_V1 problem 3)
        return bool(re.search(r"(?<![\w-])" + re.escape(lic) + r"(?![\w-])", reply or "", re.I))
    if kind == "latest_commit":
        st = [t for t in toks(gold["subject"]) if t not in STOP]
        rs = set(toks(reply))
        hit = sum(1 for t in st if t in rs)
        return gold["oid"][:7] in reply or (st and hit / len(st) >= 0.6)
    if kind == "depends":
        return yes_no(reply) == gold["yesno"]
    if kind == "where":
        # The whole path, as given or under /repos/<name>/: a different file with the same basename and parent fails.
        p = gold["path"]
        return bool(re.search(r"(?<![\w./-])(?:/repos/[\w.-]+/)?" + re.escape(p) + r"(?![\w/-])", reply or ""))
    return False


def make_repo_fact(rng, facts, i, p_messy=0.45, fam="repo_fact"):
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
    rep = reply_of(res, k)
    ok = check_repo_answer(g["kind"], g, rep)
    if not ok:
        reasons.append("wrong or missing answer")
    elif hedged(rep):
        reasons.append("the answer is hedged (read the file or log, don't guess)")
    looked = bool(REPO_TOOLS & set(names(seg)))
    if not looked:
        reasons.append("answered without looking at the repo")
    if ok:
        reasons += grounded_answer_problems(seg, repo_gold_values(g), res.get("first", "") if k == 0 else "", early=g["kind"] != "depends")
    return {"ok": ok, "strict": ok and looked and not reasons, "reasons": reasons}


def repo_gold_values(g):
    """What a repo answer must have read: the version, author, licence id, commit id or subject, or the path."""
    k = g["kind"]
    if k in ("version", "latest_author"):
        return list(g["answers"])
    if k == "license":
        return [g["license"].split("-")[0]]
    if k == "latest_commit":
        return [g["oid"][:7], g["subject"]]
    if k == "where":
        return [g["path"], g["path"].split("/")[-1]]
    if k == "depends":
        return [g["dep"]] if g.get("yesno") == "yes" else ["package.json", "pyproject.toml"]   # "no" is grounded by having read the manifest
    return []


WHERE_ASKS = {"train": ["Where is {n} defined in {r}?", "in {r}, which file has {n}?", "can you find where {n} is defined in the {r} repo",
                        "where does {r} define {n}?", "find the {n} definition in {r} for me", "which file in {r} defines {n}",
                        "what file is {n} in, in {r}", "locate {n} in {r}", "{r}: where's {n} defined"],
              "eval": ["point me to where {n} lives in {r}", "in which file of {r} is {n} declared", "where would i find {n} inside {r}"]}


def make_repo_where(rng, facts, i, p_messy=0.45, split="train"):
    f = rng.choice([x for x in facts if x.get("defs")])
    d = rng.choice(f["defs"])
    r = repo_ref(rng, f)
    tpl = rng.choice(WHERE_ASKS[split])
    text, m = maybe_messy(rng, tpl.format(n=d["name"], r=r), p_messy)
    return _ep("repo_where", i, text, {"kind": "where", "repo": f["repo"], "path": d["path"], "line": d["line"], "name": d["name"]},
               world={"repos": world_repos(facts)}, messy_=m, repo=f["repo"])


check_repo_where = check_repo_fact


# 6. two-part repo task (plan) — also the first half of the recipe family. Habit 2.
def make_repo_two(rng, facts, i, f=None, fam="repo_two", p_messy=0.45):
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
    else:
        for p in g["parts"]:
            reasons += [f"{p['kind']}: {x}" for x in grounded_answer_problems(seg, repo_gold_values(p), res.get("first", ""))]
    planned_ = "plan" in names(seg)
    if not planned_:
        reasons.append("no plan for a two-part task")
    return {"ok": ok, "strict": ok and planned_ and not reasons, "reasons": reasons, "planned": planned_}


# 7. recipe: a similar task was done in an earlier session, so memory holds the recipe the app saved from it (real
# recipes from gold.py's finished plans, examples/gold_recipes.json); the prompt shows it and the plan should use it.
# Habit 3. (Making the recipe in the same episode depended on the first task planning, which tied two habits together.)
GOLD_RECIPES = None


def gold_recipes():
    global GOLD_RECIPES
    if GOLD_RECIPES is None:
        from pathlib import Path
        p = Path(__file__).resolve().parent / "examples" / "gold_recipes.json"
        GOLD_RECIPES = json.loads(p.read_text()) if p.exists() else []
    return GOLD_RECIPES


RECIPE_ASKS = ["Clone {r} and tell me what version it's at and what the latest commit was.",
               "what's the version and latest commit of {r}?", "find {r}'s version and latest commit",
               "can you get me the version and the latest commit for {r}", "version and latest commit for {r} please",
               "tell me {r}'s version and its latest commit"]


def make_recipe_repo(rng, facts, i):
    recs = gold_recipes()
    cands = [f for f in facts if (f.get("package") or {}).get("version") and f.get("commits")]
    if not recs or not cands:
        return None
    b = rng.choice(cands)
    others = [r for r in recs if r.get("repo") != b["repo"]]
    if not others:
        return None
    rec = {k: v for k, v in rng.choice(others).items() if k not in ("from_episode", "repo")}
    c = b["commits"][0]
    gold = {"parts": [{"kind": "version", "answers": [b["package"]["version"]]}, {"kind": "latest_commit", "subject": c["subject"], "oid": c["oid"]}],
            "repo": b["repo"], "recipe": rec["id"]}
    # A request similar enough for the app to offer the recipe (recipes.match >= STRONG): it talks about the version
    # and the latest commit. Messy, but those two words stay spelled right (a misspelling would hide the recipe).
    text, m = maybe_messy(rng, rng.choice(RECIPE_ASKS).format(r=b["repo"]), 0.45, keep={"version", "latest", "commit"})
    world = {"repos": world_repos(facts), "recipes": [rec]}
    return _ep("recipe_repo", i, text, gold, world=world, messy_=m, repo=b["repo"])


def recipe_seen(res, k=0):
    segs = turn_calls(res)
    return len(segs) > k and any("## Recipe from a similar task" in (x["messages"][0]["content"] if x["messages"] else "") for x in segs[k])


def check_recipe_repo(res):
    reasons = base_check(res)
    c = check_repo_two(res, 0, res["gold"])
    seen = recipe_seen(res, 0)
    follows = seen and plan_follows_recipe(res, 0)
    if not seen:
        reasons.append("the recipe didn't reach the prompt (no strong match)")
    elif not follows:
        reasons.append("the plan doesn't follow the recipe")
    reasons += [r for r in c["reasons"] if r not in reasons]
    return {"ok": c["ok"], "strict": c["ok"] and seen and follows and not reasons, "reasons": reasons, "recipe_seen": seen}


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
    follows = seen and plan_follows_recipe(res, 1)
    extra = ([] if seen else ["no recipe in the second prompt"]) + ([] if follows or not seen else ["second plan doesn't follow the recipe"])
    return {"ok": c2["ok"], "strict": c2["strict"] and follows, "reasons": reasons + c2["reasons"] + extra, "recipe_seen": seen}


# 8. need_repo: "my repo" with several repos and nothing saying which. Habit 4.
NEED_REPO_ASKS = {
    "train": ["What's the latest commit on my repo?", "can you check the newest commit in the repo", "what changed last in my project?",
              "who made the last commit on my repo", "whats the most recent commit message on the repo", "what was the last thing pushed to my repo",
              "can u look at the top commit in my project", "who touched my repo last", "latest commit on the project pls",
              "what did the last commit to my repo do", "whos the most recent committer on my repo", "check the last commit for me on the repo"],
    "eval": ["what's the newest commit in my repository", "who was the last person to commit to my project", "tell me the most recent commit on the repo",
             "what got committed last to my repo", "who committed most recently to my repo"],
}


def make_need_repo(rng, facts, i, p_messy=0.5, split="train"):
    f = rng.choice([x for x in facts if x.get("commits")])
    tpl = rng.choice(NEED_REPO_ASKS[split])
    kind = "latest_author" if "who" in tpl else "latest_commit"
    text, m = maybe_messy(rng, tpl, p_messy)
    c = f["commits"][0]
    gold = {"kind": kind, "repo": f["repo"], "repos": [x["repo"] for x in facts],    # repos: what the need question must not guess
            **({"answers": [c["author"]]} if kind == "latest_author" else {"subject": c["subject"], "oid": c["oid"]})}

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
    guess = need_guesses(first, list(res["gold"].get("repos") or []) + [res["gold"]["repo"]])
    if guess:
        reasons.append(f"the need question names a repo it was never told ({guess}): a guess inside a question")
    ok = bool(asked) and len(res.get("turns", [])) > 1 and check_repo_answer(res["gold"]["kind"], res["gold"], reply_of(res, -1))
    if not ok:
        reasons.append("wrong or missing answer after asking")
    elif len(segs) > 1:
        reasons += grounded_answer_problems(segs[1], repo_gold_values(res["gold"]), res.get("first", ""))
        if not REPO_TOOLS & set(names(segs[1])):
            reasons.append("answered after asking without looking at the repo")
    return {"ok": ok, "strict": ok and not reasons, "reasons": reasons}


# 9. memory_repo: memory says which repo "my agent project" is (true facts about Keal's repos). Habits 1, 4 (find, don't ask).
KEAL_FACTS = [
    {"s": "Keal", "p": "builds", "o": "Squiggle, a browser-only AI agent (repo KealJones/squiggle)"},
    {"s": "Keal", "p": "runs fine-tune experiments in", "o": "the repo KealJones/tp-parse"},
    {"s": "squiggle", "p": "is deployed on", "o": "Cloudflare Workers (the relay) and GitHub Pages"},
]
MEM_ASK = {"train": {"KealJones/squiggle": ["my agent project", "the squiggle repo", "my browser agent"],
                     "KealJones/tp-parse": ["my fine-tune experiments repo", "the repo where I run my experiments", "my experiments repo"]},
           # eval: aliases that only memory can resolve, never seen in training
           "eval": {"KealJones/squiggle": ["the thing i deploy on cloudflare", "my phone assistant repo"],
                    "KealJones/tp-parse": ["my training-run repo", "the repo with my hf jobs"]}}
MEM_TPL = {"train": {"latest_commit": ["What's the latest commit in {w}?", "what did I last commit to {w}", "check the newest commit on {w}"],
                     "version": ["What version is {w} at?", "what's the version number of {w} right now"]},
           "eval": {"latest_commit": ["whats the most recent commit on {w}", "last commit to {w}?"],
                    "version": ["which version is {w} on now"]}}


def make_memory_repo(rng, facts, i, p_messy=0.5, split="train"):
    repo = rng.choice(list(MEM_ASK[split]))
    f = next(x for x in facts if x["repo"] == repo)
    c = f["commits"][0]
    what = rng.choice(MEM_ASK[split][repo])
    kind = rng.choice(["latest_commit", "version"]) if (f.get("package") or {}).get("version") else "latest_commit"
    tpl = rng.choice(MEM_TPL[split][kind])
    text, m = maybe_messy(rng, tpl.format(w=what), p_messy, keep=set(what.split()), phrases=[what])   # never filler inside the alias
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
    text, m = maybe_messy(rng, ask, 0.55)

    def user(turn, ep):
        return (text, "later") if turn["n"] == 0 else None
    return _ep("past_chat", i, first, {"answers": row["answer"]}, user=user, messy_=m)   # messy only when rewritten (audit 7)


def check_past_chat(res):
    reasons = base_check(res)
    if len(res.get("turns", [])) < 2:
        return {"ok": False, "strict": False, "reasons": reasons + ["second chat never ran"]}
    first_ok = answer_in(reply_of(res, 0), res["gold"]["answers"]) and not non_answer(reply_of(res, 0))
    ok = answer_in(reply_of(res, 1), res["gold"]["answers"]) and not non_answer(reply_of(res, 1))
    segs = turn_calls(res)
    n1 = names(segs[1])
    # Smart context may already have retrieved the earlier chat into the prompt; answering from it is right too.
    sys1 = (segs[1][0]["messages"][0]["content"] if segs[1] and segs[1][0]["messages"] else "")
    retrieved = "(from the chat " in sys1 and answer_in(sys1, res["gold"]["answers"])
    used_memory = bool({"find", "search_history"} & set(n1)) or retrieved
    if not first_ok:
        reasons.append("first chat got it wrong")
    elif not WEB & set(names(segs[0])):
        reasons.append("first chat answered without looking it up")
    else:
        reasons += [f"first chat: {x}" for x in grounded_answer_problems(segs[0], res["gold"]["answers"], res.get("first", ""))]
    if not ok:
        reasons.append("didn't recall the earlier answer")
    elif not retrieved and not answer_grounded(segs[1], res["gold"]["answers"]):
        reasons.append("the recalled answer is in no find / search_history result and wasn't retrieved into the prompt")
    if not used_memory:
        reasons.append("didn't search past chats (and the prompt didn't already have the answer)")
    return {"ok": ok, "strict": ok and first_ok and used_memory and not reasons, "reasons": reasons}


# 11. refs: a follow-up that says "it"/"that one" about the repo from the turn before. Habits 1, 5.
REFS_FIRST = {"train": ["What version is {r} at?", "what's the current version of {r}", "which version of {r} is current", "version of {r}?"],
              "eval": ["can you tell me what version {r} is on", "whats {r} at version-wise"]}
REFS_FOLLOW = {
    "train": {"latest_commit": ["and what was the last commit on it?", "cool. whats the latest commit there", "and the most recent commit on that one?",
                                "ok and the newest commit in it", "what changed last in that repo"],
              "latest_author": ["who made the last commit on it?", "and who committed to it last", "who was the last to push to that one"],
              "license": ["what license is it under?", "and the license on that one?", "is it MIT or something else"]},
    "eval": {"latest_commit": ["thanks. and its most recent commit?", "k what was committed to it last"],
             "latest_author": ["and who last touched it?"],
             "license": ["which license does that one have"]},
}


def make_refs(rng, facts, i, split="train"):
    f = rng.choice([x for x in facts if x.get("commits") and (x.get("package") or {}).get("version")])
    qs = {k: (t, g) for k, t, g in repo_questions(f)}
    first = rng.choice(REFS_FIRST[split]).format(r=f["repo"])
    k2 = rng.choice([k for k in ("latest_commit", "latest_author", "license") if k in qs])
    text = rng.choice(REFS_FOLLOW[split][k2])

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
    elif not REPO_TOOLS & set(names(segs[0])):
        reasons.append("first answer given without looking at the repo")
    else:
        reasons += [f"first: {x}" for x in grounded_answer_problems(segs[0], repo_gold_values(g["first"]), res.get("first", ""))]
    if not ok:
        reasons.append("follow-up wrong")
    elif not REPO_TOOLS & set(names(segs[1])):
        # Earlier results aren't in the follow-up's prompt (AUDIT_V1: 11/11 licence follow-ups answered from nothing).
        reasons.append("follow-up answered without looking at the repo again")
    else:
        reasons += [f"follow-up: {x}" for x in grounded_answer_problems(segs[1], repo_gold_values(g["second"]))]
    if asked_user(res, 1):
        reasons.append("asked which repo although it was just discussed")
    return {"ok": ok, "strict": ok and ok1 and not reasons, "reasons": reasons}


# 12. chat: plain chat stays plain. Habit 6. (Casual openers; no facts in them.)
# Split by train/eval so the eval never scores a string the model trained on (AUDIT_V1 problem 5: 8/16 eval chat inputs
# were in training). The eval list is phrased differently on purpose (longer, typos, emoji-free, other moods).
CHAT = ["hey whats up lol", "hi!", "good morning", "thanks, that worked", "lol nice", "ok cool", "how's it going?", "yo",
        "thank you so much", "haha that's funny", "you're pretty helpful", "night!", "sup", "ugh mondays", "brb",
        "hey squiggle", "ok im back", "that's awesome", "nvm i figured it out", "cool cool cool", "hello there",
        "what's up", "thanks!", "i'm bored lol", "omg yes", "sorry for the late reply", "nice, thank you", "heyyy",
        "good night squiggle", "you rock", "can you say hi to me", "how are you doing today?", "hey hows ur day going",
        "morning! coffee time", "i'm so tired today", "lmao", "ok", "gotcha, thanks", "great job", "hmm interesting",
        "that makes sense", "wow", "never mind", "cheers", "appreciate it", "hey so um nothing really just saying hi",
        "are you there?", "hi again", "ok thanks bye", "you're the best", "have a good one"]
CHAT_EVAL = ["yooo its friday finally", "ok that was perfect thanks a bunch", "ha ok fair enough", "evening squiggle", "ugh long day",
             "k", "sweet", "oh nice ok", "hey hey", "alright talk later", "lol ok ok", "thx again u r great", "hows your morning going",
             "good afternoon!", "well that was easy", "huh neat", "ok noted", "lmaooo", "ty!!", "sup squiggle whats good",
             "back again hi", "ok gotta run bye", "oh wow ok", "i'm sleepy", "happy friday", "oof", "nice one", "hey :)",
             "thanks mate", "ok good to know"]


def make_chat(rng, i, text=None, split="train"):
    t = text or rng.choice(CHAT if split == "train" else CHAT_EVAL)
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
def make_chat_after(rng, row, i, split="train"):
    ep = make_web_fact(rng, row, i, p_messy=0.3)
    follow = rng.choice(["cool thanks", "nice, thank you!", "ok perfect", "lol ok", "awesome thx", "great, that's what i needed"] if split == "train"
                        else ["perfect ty", "ok cool thanks a lot", "got it, cheers", "ah ok makes sense", "nice thx!!"])

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
    return _ep("bare_link", i, text, {"url": url, "title": title}, messy_=False)    # not a dictation rewrite (audit 7)


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
    # Grounded: most of the reply's content words (5+ letters, not the title, not boilerplate) are on the page.
    page = " ".join(b for n, b in good_results(seg) if n == "fetch_url")
    pt = set(toks(page))
    content = [w for w in set(toks(rep)) if len(w) >= 5 and w not in STOP and w not in words and w not in BOILER]
    share = sum(1 for w in content if w in pt) / len(content) if content else 0.0
    if fetched and (not content or share < 0.6):
        reasons.append(f"the summary isn't from the page ({share:.0%} of its content words appear in the fetched text)")
    ok = fetched and len(rep) >= 40 and about
    return {"ok": ok, "strict": ok and not reasons, "reasons": reasons}


BOILER = {"wikipedia", "article", "summary", "summarize", "overview", "section", "sections", "introduction", "history", "references",
          "about", "describes", "covers", "explains", "discusses", "according", "page", "link"}


# 15. web_bridge (held out): a two-hop bridge question. Habits 1, 2.
def make_web_bridge(rng, row, i):
    return make_web_compare(rng, row, i, p_messy=0.3, fam="web_bridge")


def check_web_bridge(res):
    c = check_web_compare(res)
    return c


# 16. unknown_word: a request built around a made-up word (data/sources/unknown_words.json: invented, checked to have
#     no search hits), in a work/tech or a personal setting. Habit: look the word up, say plainly it isn't a known word,
#     a guess only if it's labelled as one, and ask the one question (need, or at the end of the reply). Never present
#     an invented meaning as fact. Held out: unknown_action, where the word is something to DO ("can you <word> my config").
UNKNOWN_FAMS = {"unknown_word", "unknown_action"}
UNKNOWN_ASK = {
    "work": ["my coworker keeps {ing} the shared drive is that bad", "my manager says we have to {base} the backlog before friday, what does that involve",
             "the new intern keeps {ing} the build server, should I be worried", "my team lead told me to stop {ing} my pull requests, what did I do wrong",
             "someone in standup said our api is {ing} again, is that a problem", "is it normal for a sysadmin to {base} the logs every night",
             "my boss wants me to {base} the quarterly report, how long should that take", "our client {ed} the whole project plan, what do I do now"],
    "personal": ["my mom keeps trying to {base} me at dinner", "my roommate always {s} the fridge, how do I get him to stop",
                 "my sister says I {base} too much when we talk on the phone, is that rude", "my friend keeps {ing} our group chat, what should I say",
                 "my dad wants to {base} the garden this weekend, should I help", "my partner said I was {ing} again last night, what does that mean",
                 "my kid came home saying everyone at school is {ing} now, should I be worried", "my neighbor {ed} our fence, is that a big deal"],
}
UNKNOWN_ACTION = ["can you {base} my config so it loads faster", "how do I {base} a git branch", "what's the fastest way to {base} a python list",
                  "can you help me {base} my spreadsheet formulas", "is there a way to {base} my npm packages", "{base} my resume so it sounds more professional",
                  "can you {base} this week's meeting notes for me", "how long does it take to {base} a sourdough starter"]
NOT_KNOWN = re.compile(r"\b(not (a |an )?(real|known|standard|common|recognized|recognised|english|dictionary|actual) (word|term|verb)|"
                       r"(isn'?t|is not|doesn'?t seem to be|does not seem to be|not) (a )?(real |known |standard |common )?(word|term)|"
                       r"(could ?n[o']t|can'?t|did ?n[o']t|unable to) find (it|any|a|the|anything|that word|this word|a definition|a meaning|what)|"
                       r"no (definition|meaning|results?|matches|hits|entry|record)|not familiar|unfamiliar|don'?t recogni[sz]e|made[- ]up|"
                       r"not sure what .{0,30} means|don'?t know what .{0,30} means|unknown word|no idea what .{0,30} means)\b", re.I)
GUESS = re.compile(r"\b(guess|maybe|might|may|perhaps|possibly|probably|could (mean|be)|sounds like|seems like|my best guess|if you mean|"
                   r"not sure|unclear|don'?t know|no idea|assum\w*|i think|likely|if it means|in case)\b", re.I)
DEFINES = re.compile(r"\b(means|meaning|refers to|is when|is the act|is a (term|word|slang|way|kind|type|form)|is slang|stands for|"
                     r"describes|is basically|is just|is another word|involves|=)\b", re.I)
_UNKNOWN = None


def unknown_words(split):
    global _UNKNOWN
    if _UNKNOWN is None:
        _UNKNOWN = json.loads((HERE / "data" / "sources" / "unknown_words.json").read_text())
    return [w for w in _UNKNOWN if w["split"] == split]


def make_unknown_word(rng, w, i, fam="unknown_word", p_messy=0.4):
    ctx = rng.choice(["work", "personal"]) if fam == "unknown_word" else "action"
    tpl = rng.choice(UNKNOWN_ASK[ctx] if fam == "unknown_word" else UNKNOWN_ACTION)
    text = tpl.format(**w["forms"])
    text, m = maybe_messy(rng, text, p_messy, keep=set(w["forms"].values()))
    return _ep(fam, i, text, {"word": w["word"], "forms": sorted(set(w["forms"].values()))}, messy_=m, context=ctx)


def make_unknown_action(rng, w, i):
    return make_unknown_word(rng, w, i, fam="unknown_action")


def defines_as_fact(text, forms):
    """A sentence that says what the made-up word means, with no hedge (guess, maybe, not a known word...)."""
    stems = {f.lower() for f in forms} | {f.lower()[:-1] for f in forms if f.endswith("e")}
    for sent in re.split(r"(?<=[.!?])\s+|\n+", text or ""):
        low = sent.lower()
        if any(re.search(r"\b" + re.escape(x), low) for x in stems) and DEFINES.search(sent) and not GUESS.search(sent) \
                and not NOT_KNOWN.search(sent) and not re.search(r"\b(not|n't|no)\b", low):
            return True
    return False


def check_unknown_word(res):
    reasons = base_check(res)
    g = res["gold"]
    forms = [f.lower() for f in g["forms"]]
    segs = turn_calls(res)
    seg = segs[0] if segs else []
    queries = [str(a.get("query", "")).lower() for a in args_of(seg, "web_search")]
    looked = any(any(f in q or f[:-1] in q for f in forms) for q in queries)
    if not looked:
        reasons.append("didn't look the word up with web_search" if not queries else "web_search didn't search for the word itself")
    rep = reply_of(res, 0)
    asked = asked_user(res, 0)
    need_q = " ".join(str(a.get("what", "")) for a in args_of(seg, "need"))
    done_r = " ".join(str(a.get("result", "")) for a in args_of(seg, "done"))
    shown = " ".join([rep, need_q, done_r])
    if defines_as_fact(shown, forms):
        reasons.append("stated a meaning for the made-up word as if it were real")
    if asked and (args_of(seg, "need")):
        good_end = "?" in need_q or bool(re.search(r"\b(what|which|how|mean)\b", need_q, re.I))
        if not good_end:
            reasons.append("the need question doesn't ask what they mean")
    else:
        if not NOT_KNOWN.search(rep):
            reasons.append("the reply doesn't say plainly that it isn't a known word")
        if "?" not in rep:
            reasons.append("the reply doesn't ask what they mean")
    if len(rep.split()) > 150:
        reasons.append("reply over 150 words")
    ok = looked and not defines_as_fact(shown, forms) and (asked or (NOT_KNOWN.search(rep) and "?" in rep))
    return {"ok": bool(ok), "strict": bool(ok) and not reasons, "reasons": reasons}


def check_unknown_action(res):
    return check_unknown_word(res)


# 17. personal: advice and empathy with nothing to look up (real requests from OpenAssistant oasst2 and Dolly-15k,
#     data/sources/personal.json). Habit: short thinking (Request / Need: feelings first, then options), no plan or tool,
#     a warm, concise reply; when key information is missing (marked by hand), one question at the end.
_PERSONAL = None


def personal_rows(split):
    global _PERSONAL
    if _PERSONAL is None:
        _PERSONAL = json.loads((HERE / "data" / "sources" / "personal.json").read_text())
    return [r for r in _PERSONAL if r["split"] == split]


def make_personal(rng, row, i, p_messy=0.35):
    text, m = maybe_messy(rng, row["text"], p_messy)
    # "ask": marked by hand in personal.json where the reply can't fit the person without one more fact (who the gift is
    # for, what happened); those replies must end with a question.
    return _ep("personal", i, text, {"ask": bool(row.get("ask")), "source": row["id"]}, messy_=m)


def check_personal(res):
    reasons = base_check(res)
    segs = turn_calls(res)
    seg = segs[0] if segs else []
    rep = reply_of(res, 0).strip()
    if names(seg):
        reasons.append("called tools for a personal request")
    n = len(rep.split())
    if n > 200:
        reasons.append(f"reply is {n} words (over 200)")
    if n < 15:
        reasons.append("reply too short to help")
    if re.match(r"\s*(\d+[.)]|[-*\u2022])\s", rep):
        reasons.append("opens with a list (feelings first, then options)")
    if res["gold"].get("ask") and not re.search(r"\?[\s\W]*$", rep):
        reasons.append("key information is missing but the reply doesn't end with a question")
    if rep.count("?") > 2:
        reasons.append("asks more than one question")
    ok = bool(rep) and not names(seg) and 15 <= n <= 200
    return {"ok": ok, "strict": ok and not reasons, "reasons": reasons}


# ── registry ───────────────────────────────────────────────────────────────
CHECK = {
    "web_fact": check_web_fact, "web_compare": check_web_compare, "web_bridge": check_web_bridge, "math": check_math,
    "need_math": check_need_math, "repo_fact": check_repo_fact, "repo_where": check_repo_where, "repo_two": check_repo_two,
    "recipe_repo": check_recipe_repo, "recipe_compare": check_recipe_compare, "need_repo": check_need_repo,
    "memory_repo": check_memory_repo, "past_chat": check_past_chat, "refs": check_refs, "chat": check_chat,
    "chat_after": check_chat_after, "bare_link": check_bare_link, "unknown_word": check_unknown_word,
    "unknown_action": check_unknown_action, "personal": check_personal,
}
HABIT = {
    "web_fact": "look it up", "web_compare": "plan + look up two things", "web_bridge": "plan a two-hop lookup (held out)",
    "math": "compute with calculate", "need_math": "ask for a missing number (held out)", "repo_fact": "look in the repo",
    "repo_where": "find a definition", "repo_two": "plan a two-part repo task", "recipe_repo": "use a recipe",
    "recipe_compare": "use a recipe on web lookups (held out)", "need_repo": "ask which repo", "memory_repo": "use memory, don't ask",
    "past_chat": "find an earlier chat", "refs": "follow 'it' to the last repo", "chat": "plain chat stays plain",
    "chat_after": "a task, then plain thanks", "bare_link": "read a bare link", "hermes_compute": "compute with calculate (Hermes requests)",
    "hermes_need": "ask for missing input (Hermes requests)", "unknown_word": "look up a made-up word, don't define it",
    "unknown_action": "a made-up word as a task (held out)", "personal": "warm advice, no tools",
}
HELD_OUT = {"web_bridge", "need_math", "recipe_compare", "unknown_action"}


def check(res):
    fam = res["family"]
    if fam.startswith("hermes_"):
        import hermes
        return hermes.check(res)
    try:
        return CHECK[fam](res)
    except Exception as e:
        return {"ok": False, "strict": False, "reasons": [f"checker crashed: {e!r}"]}
