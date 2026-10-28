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
}
MAX_WORDS = {"request": 260, "step_start": 180, "after_result": 180, "final": 160, "chat_plain": 40}


def call_kind(messages, kind, plain=False):
    """What the model is answering: a new request, the start of a step, a tool result, the final-reply prompt, or plain chat."""
    if plain:
        return "chat_plain"
    if kind == "final":
        return "final"
    last = next((m for m in reversed(messages) if m["role"] == "user"), {"content": ""})["content"]
    if last.startswith("Result of "):
        return "after_result"
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
    if name == "done" and isinstance(args.get("result"), str):
        r = args["result"].strip()
        if len(r) > 600:
            p.append("done: result over 600 characters (one to three lines of facts)")
        if re.match(r"^(I |I've|I have|I'm|Done\b|Successfully|The step (is|was)|Step \d+ (is|was)|Finished)", r):
            p.append("done: result narrates instead of giving the facts (start with the facts)")
        if not re.search(r"\d|/|\.\w|\"|'[A-Za-z]|[A-Z][a-z]+", r):
            p.append("done: result has no concrete facts (names, numbers, paths, quotes)")
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
    if name not in HARNESS and name in SPECS and name not in looked_up(messages):
        p.append(f"'{name}' isn't under 'Tools you have looked up' yet: call find first")
    if kind == "chat" and name == "done":
        p.append("done only ends a step; there is no plan yet")
    return p, {"name": name, "arguments": args}


SOURCE = re.compile(r"https?://|wikipedia|\bsource|according to|\bfrom (the )?(page|article|repo|readme|package\.json|git log|log|commit)|"
                    r"[\w.-]+/[\w.-]+|\b[\w-]+\.(json|md|js|py|ts|toml)\b|\bran\b|\bcalculated\b|\bcomputed\b|\bsandbox\b", re.I)


def final_cites(reply):
    return bool(SOURCE.search(reply or ""))
