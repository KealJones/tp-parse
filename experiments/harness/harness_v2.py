"""Harness v2: the same 18 tasks, with tools offered in Qwen3's own trained tool-calling format.

Tools are passed as JSON schemas through the chat template (`tools=`); the model calls one with
<tool_call>{"name": ..., "arguments": {...}}</tool_call>, and the harness answers with a "tool" message.
A reply with no tool call is the final answer. Same search/fetch code and cache as v1 (harness.py).

  python harness_v2.py [--pilot]     writes out/traces.json, out/AUTO.md, out/cache.json
"""
import json, re, sys, time
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
import harness as H                                       # search, fetch, chunking, cache, tasks

CONFIGS = [("Qwen/Qwen3-0.6B", False), ("Qwen/Qwen3-0.6B", True), ("Qwen/Qwen3-1.7B", False), ("Qwen/Qwen3-1.7B", True)]
if H.PILOT:
    CONFIGS = CONFIGS[:2]
MAX_TURNS = 6

TOOLS = [
    {"type": "function", "function": {"name": "search", "description": "Search the web. Use it for anything you don't know well or where exact details matter (commands, names, numbers, prices).",
     "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "the search query"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "fetch", "description": "Read the text of a web page.",
     "parameters": {"type": "object", "properties": {"url": {"type": "string", "description": "the page URL"}}, "required": ["url"]}}},
    {"type": "function", "function": {"name": "ask_user", "description": "Ask the person a clarifying question, only when searching can't settle it.",
     "parameters": {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]}}},
]
SYSTEM = ("You are a helpful assistant that knows little but can look things up with tools. Never guess facts you are not "
          "sure of: search first. The person's message may be messy, misspelled, rambling or spoken. When you have what you "
          "need, reply with a short, direct answer and no tool call.")
CALL = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.S)


def run_tool(name, args):
    if name == "search":
        return H.search(str(args.get("query", "")))
    if name == "fetch":
        u = str(args.get("url", ""))
        return H.fetch(u if u.startswith("http") else "https://" + u)
    if name == "ask_user":
        return "Keal isn't available right now. Work it out yourself, or answer and say what you'd need to be sure."
    return f"(unknown tool {name})"


class Runner(H.Runner):
    @torch.no_grad()
    def reply(self, convs, max_new):
        texts = [self.tok.apply_chat_template(c, tools=TOOLS, tokenize=False, add_generation_prompt=True,
                                              enable_thinking=self.think) for c in convs]
        outs = []
        for i in range(0, len(texts), 6):
            enc = self.tok(texts[i:i + 6], return_tensors="pt", padding=True, add_special_tokens=False).to("cuda")
            g = self.model.generate(**enc, max_new_tokens=max_new, do_sample=False, pad_token_id=self.tok.pad_token_id)
            outs += [self.tok.decode(g[j, enc["input_ids"].shape[1]:], skip_special_tokens=False)
                     .replace("<|im_end|>", "").replace("<|endoftext|>", "") for j in range(len(texts[i:i + 6]))]
        return outs

    def solve_all(self, tasks):
        max_new = 1024 if self.think else 400
        convs, traces = [], []
        for t in tasks:
            body = (f"Context: {t['ctx']}\n\n" if t["ctx"] else "") + t["msg"]
            convs.append([{"role": "system", "content": SYSTEM}, {"role": "user", "content": body}])
            traces.append({"id": t["id"], "msg": t["msg"], "steps": [], "answer": None, "bad_calls": 0})
        active = list(range(len(tasks)))
        for turn in range(MAX_TURNS + 1):
            if not active:
                break
            outs = self.reply([convs[i] for i in active], max_new)
            still = []
            for i, o in zip(active, outs):
                visible = o.split("</think>")[-1]
                m = CALL.search(visible)
                call = None
                if m:
                    try:
                        call = json.loads(m[1])
                    except json.JSONDecodeError:
                        traces[i]["bad_calls"] += 1
                if call is None or turn == MAX_TURNS:
                    traces[i]["answer"] = CALL.sub("", visible).strip()
                    continue
                name, args = call.get("name", ""), call.get("arguments", {}) or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                result = run_tool(name, args)
                traces[i]["steps"].append({"tool": name, "args": args, "result": result[:400]})
                convs[i].append({"role": "assistant", "content": "", "tool_calls": [{"type": "function", "function": {"name": name, "arguments": args}}]})
                convs[i].append({"role": "tool", "content": result[:H.RESULT_CHARS]})
                still.append(i)
            active = still
        return traces


def main():
    t0, out = time.time(), []
    for name, think in CONFIGS:
        r = Runner(name, think)
        for tr in r.solve_all(H.TASKS):
            t = H.TASKS[tr["id"]]
            ans = tr["answer"] or ""
            tr.update(model=name, think=think,
                      auto_pass=all(re.search(p, ans, re.I | re.S) for p in t["auto"]) and not any(re.search(p, ans, re.I) for p in t["fail_if"]))
            out.append(tr)
        rows = [o for o in out if o["model"] == name and o["think"] == think]
        print(f"{name} think={think}: auto {sum(o['auto_pass'] for o in rows)}/{len(rows)}, tool calls {sum(len(o['steps']) for o in rows)} "
              f"({time.time()-t0:.0f}s)", flush=True)
        del r; torch.cuda.empty_cache()
        json.dump(out, open("out/traces.json", "w"), indent=1, ensure_ascii=False)
        json.dump(H.CACHE, open("out/cache.json", "w"), indent=1, ensure_ascii=False)
    L = ["# Harness v2 (native tool calls): auto check (first pass; Claude grades by hand)", ""]
    for name, think in CONFIGS:
        rows = [o for o in out if o["model"] == name and o["think"] == think]
        acts = {}
        for o in rows:
            for s in o["steps"]:
                acts[s["tool"]] = acts.get(s["tool"], 0) + 1
        L.append(f"- {name}, thinking {'on' if think else 'off'}: {sum(o['auto_pass'] for o in rows)}/{len(rows)}; tool calls: {acts or 'none'}; "
                 f"malformed calls: {sum(o['bad_calls'] for o in rows)}")
    open("out/AUTO.md", "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
