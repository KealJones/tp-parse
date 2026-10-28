"""Keal's quality bar for teacher examples, checked mechanically (TEACHER.md explains it to teachers).

An output that fails any rule is rejected; an episode with any rejected call is dropped, never patched up.

1. Tool-call syntax: thinking first, then exactly one ```tool_call block at the very end with nothing after it, JSON
   {"name", "arguments"} that the app's parseToolCalls reads (selftest.py checks the Python mirror agrees with the
   app), a tool that exists (tool_specs.json, exported from the app), arguments that match its schema (required
   present, no invented names, right types). Or a plain reply with no tool block.
2. Structured thinking, labelled lines in this order:
     new request (first call of a user turn)  Request: / Pieces: / Know: / Don't know: / Goal: / Plan: or Next:
     start of a step ("Work on step N now")   Step: / Know: / Next:
     right after a tool result                Check: / Next:
     final reply ("Every step is done")       Answer:
     plain chat                               one or two short lines, no labels, no tools
     personal advice / empathy                Request: / Need: (what they need: feelings first, then options);
                                              a warm reply under 200 words, no tools
3. Habits: a real tool is only called once it is listed under "Tools you have looked up" (find first); done(result)
   carries facts, not narration; a plan has 2-6 short steps; the final reply cites its sources.
"""
import json, re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPECS = {s["name"]: s for s in json.loads((HERE / "tool_specs.json").read_text())}
HARNESS = {"plan", "done", "need", "find"}

LABELS = {
    "request": ["Request:", "Pieces:", "Know:", "Don't know:", "Goal:", ("Plan:", "Next:")],
    "step_start": ["Step:", "Know:", "Next:"],
    "after_result": ["Check:", "Next:"],
    "final": ["Answer:"],
    "personal": ["Request:", "Need:"],
}
MAX_WORDS = {"request": 260, "step_start": 180, "after_result": 180, "final": 160, "chat_plain": 40, "personal": 90}
PERSONAL_REPLY_WORDS = 200


def call_kind(messages, kind, plain=False):
    """What the model is answering: a new request, the start of a step, a tool result, the final-reply prompt, plain chat
    (plain=True) or a personal advice / empathy request (plain="personal")."""
    if plain and plain != "personal":
        return "chat_plain"
    if kind == "final":
        return "final"
    last = next((m for m in reversed(messages) if m["role"] == "user"), {"content": ""})["content"]
    if last.startswith("Result of "):
        return "after_result"
    if plain == "personal":
        return "personal"
    if kind == "step":
        return "step_start"
    return "request"


def split_output(text):
    """(thinking, after) following engine-wllama splitThinking; thinking None when it doesn't open or close."""
    raw = str(text or "")
    rest = raw.lstrip()
    if not rest.startswith("<think>"):
        return None, raw
    end = rest.find("</think>")
    if end < 0:
        return None, ""
    return rest[7:end], rest[end + 8:]


def type_ok(value, schema):
    t = schema.get("type")
    if t == "string":
        return isinstance(value, str) and value.strip() != ""
    if t == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if t == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if t == "boolean":
        return isinstance(value, bool)
    if t == "array":
        item = (schema.get("items") or {}).get("type")
        return isinstance(value, list) and len(value) > 0 and all(type_ok(v, {"type": item}) for v in value) if item else isinstance(value, list)
    if "enum" in schema:
        return value in schema["enum"]
    return True


# Plan steps must be task actions that produce a fact or a change. Steps that write, review or format the reply, and
# meta steps ("find the tools"), are rejected: the reply is written automatically after the last step, and find is an
# action inside a step, not a step. (AUDIT_V1 problem 8; gemma-traces lesson 1.)
META_STEP = re.compile(r"^\s*(?:\d+[.)]\s*)?(write|draft|compose|review|summari[sz]e|respond|reply|answer|self-?correct|format|"
                       r"(?:verify|check|proofread|polish|refine) (?:the |my )?(answer|reply|response|tone|wording)|"
                       r"(?:find|look ?up|locate|identify|get|list|search for) (?:the |my |available |needed |required )?tools?\b|"
                       r"(?:prepare|present|deliver|provide|give|report|state|tell) (?:the |a )?(?:final )?(answer|reply|response|result|summary|user))\b", re.I)
# A done result narrates instead of stating facts. (AUDIT_V1 problem 8: the old regex accepted any capitalised word.)
DONE_NARRATES = re.compile(r"^(I |I've|I have|I'm|Done\b|Successfully|The step (is|was)|Step \d+ (is|was)|Finished|Completed|Ready\b|"
                           r"Tools? (found|located|looked up|identified|available|ready)|Found the tools?|Located the tools?|"
                           r"Looked up|Identified the tools?|Proceed|Moving on|Now |Next\b)", re.I)
DONE_FACT = re.compile(r"\d|/|\.\w|\"|'[A-Za-z]|(?<=\S )[A-Z][a-z]+|^[A-Z][a-z]+ [A-Z][a-z]+")   # a capital counts only after the first word
# calculate takes a plain expression: numbers, operators, parentheses, the functions calc.js has, "of" and "x".
CALC_WORDS = {"sqrt", "abs", "round", "floor", "ceil", "min", "max", "pow", "log", "ln", "exp", "pi", "e", "of", "x"}


def validate_call(name, args):
    p = []
    spec = SPECS.get(name)
    if not spec:
        return [f"unknown tool '{name}'"]
    if not isinstance(args, dict):
        return [f"{name}: arguments must be an object"]
    props = (spec.get("parameters") or {}).get("properties") or {}
    for r in (spec.get("parameters") or {}).get("required") or []:
        if r not in args:
            p.append(f"{name}: missing required argument '{r}'")
    for k, v in args.items():
        if k not in props:
            p.append(f"{name}: no argument named '{k}' (it takes {', '.join(props) or 'none'})")
        elif not type_ok(v, props[k]):
            p.append(f"{name}: '{k}' should be {props[k].get('type')}{' of ' + props[k]['items']['type'] if props[k].get('type') == 'array' and props[k].get('items') else ''}")
        elif "enum" in props[k] and v not in props[k]["enum"]:
            p.append(f"{name}: '{k}' must be one of {props[k]['enum']}")
    if name == "plan" and isinstance(args.get("steps"), list):
        n = len(args["steps"])
        if not 2 <= n <= 6:
            p.append(f"plan: {n} steps (use 2 to 6; a one-step job needs no plan)")
        if any(len(str(s)) > 140 for s in args["steps"]):
            p.append("plan: steps must be short (under 140 characters)")
        for s in args["steps"]:
            if META_STEP.match(str(s)):
                p.append(f"plan: step {str(s)[:60]!r} isn't a task action (no steps that write or review the reply, and no "
                         "'find the tools' steps: find is an action inside a step)")
    if name == "done" and isinstance(args.get("result"), str):
        r = args["result"].strip()
        if len(r) > 600:
            p.append("done: result over 600 characters (one to three lines of facts)")
        if DONE_NARRATES.match(r):
            p.append("done: result narrates instead of giving the facts (start with the facts)")
        if not DONE_FACT.search(r):
            p.append("done: result has no concrete facts (names, numbers, paths, quotes)")
    if name == "calculate" and isinstance(args.get("expression"), str):
        e = args["expression"]
        if re.search(r"=>|==|[=;{}\[\]`]|\b(function|return|console|let|const|var|Math)\b", e):
            p.append("calculate: the expression is code; give a plain math expression (numbers, + - * / ^ %, parentheses, sqrt, round...)")
        words = {w.lower() for w in re.findall(r"[A-Za-z_]+", e)}
        if words - CALC_WORDS:
            p.append(f"calculate: words in the expression ({', '.join(sorted(words - CALC_WORDS))}); units and names go in the reply, only numbers here")
        if not re.search(r"\d", e):
            p.append("calculate: the expression has no number")
    return p


FENCE = re.compile(r"```tool_call\s*\n([\s\S]*?)\n```")


def looked_up(messages):
    """Tool names listed under 'Tools you have looked up:' in the system message."""
    sys = messages[0]["content"] if messages and messages[0]["role"] == "system" else ""
    i = sys.find("Tools you have looked up:\n")
    if i < 0:
        return set()
    names = set()
    for line in sys[i:].split("\n")[1:]:
        m = re.match(r"- ([a-z_]+)\(", line)
        if not m:
            break
        names.add(m.group(1))
    return names


def is_looping(text, n=8, times=3):
    """engine-wllama.js isLooping: some run of 8 words appears 3 times (the phone stops such a reply as a loop)."""
    words = re.findall(r"[a-z0-9_']+", str(text).lower())
    if len(words) < n * times:
        return False
    seen = {}
    for i in range(len(words) - n + 1):
        k = " ".join(words[i:i + n])
        seen[k] = seen.get(k, 0) + 1
        if seen[k] >= times:
            return True
    return False


def thinking_problems(thinking, ckind):
    p = []
    t = thinking.strip()
    words = len(t.split())
    if not t:
        return ["empty thinking"]
    if words > MAX_WORDS[ckind]:
        p.append(f"thinking is {words} words (keep it under {MAX_WORDS[ckind]} for this kind of turn)")
    if ckind == "chat_plain":
        lines = [l for l in t.split("\n") if l.strip()]
        if len(lines) > 2:
            p.append("plain chat: thinking should be one or two short lines")
        return p
    positions = []
    for lab in LABELS[ckind]:
        alts = lab if isinstance(lab, tuple) else (lab,)
        hits = [m.start() for a in alts for m in re.finditer(r"(?m)^" + re.escape(a) + r"[ \t]+\S", t)]
        if not hits:
            p.append(f"thinking needs a line starting '{' or '.join(alts)}' (for {ckind.replace('_', ' ')})")
        else:
            positions.append(min(hits))
    if positions != sorted(positions):
        p.append("thinking labels are out of order: " + " / ".join(l if isinstance(l, str) else " or ".join(l) for l in LABELS[ckind]))
    return p


def output_problems(output, messages, kind, plain=False):
    """Every rule that a single model output must pass. Returns (problems, call or None)."""
    ckind = call_kind(messages, kind, plain)
    if is_looping(output):
        return ["the same 8 words appear 3 times in this output, so the phone's anti-loop guard would cut it off; don't repeat "
                "phrases (e.g. the plan steps) word for word in the thinking"], None
    thinking, after = split_output(output)
    if thinking is None:
        return ["output must start with <think> and close it with </think>"], None
    p = thinking_problems(thinking, ckind)
    body = after.strip()
    if not body:
        return p + ["nothing after the thinking: add one tool call or the reply"], None
    blocks = list(FENCE.finditer(body))
    if "```tool" in body and not blocks:
        return p + ["tool call block is malformed: use ```tool_call, newline, the JSON on its own, newline, ```"], None
    if not blocks:
        if ckind == "chat_plain" and len(body) > 300:
            p.append("plain chat reply over 300 characters")
        if ckind == "personal" and len(body.split()) > PERSONAL_REPLY_WORDS:
            p.append(f"personal reply is {len(body.split())} words (keep it under {PERSONAL_REPLY_WORDS}: warm and concise)")
        return p, None
    if len(blocks) > 1:
        p.append("more than one tool call (one per reply)")
    b = blocks[0]
    if body[:b.start()].strip():
        p.append("text before the tool call (put it in the thinking)")
    if body[b.end():].strip():
        p.append("text after the tool call (the block must be last)")
    try:
        obj = json.loads(b.group(1))
    except Exception as e:
        return p + [f"tool call JSON doesn't parse: {e}"], None
    if not isinstance(obj, dict) or set(obj) != {"name", "arguments"}:
        return p + ['tool call must be exactly {"name": ..., "arguments": {...}}'], None
    name, args = obj["name"], obj["arguments"]
    p += validate_call(name, args)
    if ckind == "final":
        p.append("the final reply can't call tools")
    if ckind == "chat_plain":
        p.append("plain chat gets a plain reply, no tools")
    if ckind == "personal" and name != "need":
        p.append("a personal advice request gets a warm reply, no tools (there is no fact to look up); if key information "
                 "is missing, ask one question at the end of the reply")
    if ckind == "personal" and name == "need":
        p.append("for a personal request, ask your one question at the end of a warm reply instead of using need")
    if name not in HARNESS and name in SPECS and name not in looked_up(messages):
        p.append(f"'{name}' isn't under 'Tools you have looked up' yet: call find first")
    if kind == "chat" and name == "done":
        p.append("done only ends a step; there is no plan yet")
    return p, {"name": name, "arguments": args}


# The shape of a citation. This is only the syntactic half: families.cited_source_called checks that what is cited is a
# page, file, repo or tool the model actually used in that turn ("from memory" and "and/or" no longer count;
# AUDIT_V1 problem 4).
SOURCE = re.compile(r"https?://|wikipedia|\bsource\b|according to|\bfrom (the |its |their )?(page|article|repo|readme|package\.json|pyproject|git log|log|commit|"
                    r"search result|web search|file|calculator|calculate)|"
                    r"\((?:from|via|per|source:?|see|wikipedia:?) [^)]{3,}\)|"
                    r"(?<![\w/])[A-Za-z][\w.-]*/[A-Za-z][\w.-]*(?![\w/])(?<!and/or)(?<!w/o)|/repos/|/home/|\b[\w-]+\.(json|md|js|py|ts|toml|txt)\b|"
                    r"\bcalculated\b|\bcomputed\b|\bcalculate\b", re.I)


def final_cites(reply):
    return bool(SOURCE.search(reply or ""))
