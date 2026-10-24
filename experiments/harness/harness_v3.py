"""Harness v3: v2 (native tool calls, thinking on) with a better search tool.

search(query) now:
  1. runs the model's query AND a query built from the key words of Keal's own message (+ context), merging results;
  2. opens the top two pages and returns the paragraphs that share the most words with the message and the query,
     so the model gets the relevant text itself, not just one-line snippets.

  python harness_v3.py [--pilot]     writes out/traces.json, out/AUTO.md, out/cache.json
"""
import json, re, time
import torch
import harness as H
import harness_v2 as V2

CONFIGS = [("Qwen/Qwen3-0.6B", True), ("Qwen/Qwen3-1.7B", True)]
if H.PILOT:
    CONFIGS = CONFIGS[:1]
STOP = set("""a an the and or but if so of to in on at for from by with about as is are was were be been being it its this that
these those i you he she we they me my your our their what which who whom how why when where do does did done can could would should
will just like um uh yeah okay ok really actually kind sort thing things stuff get got make made want wanna gonna there here then than
too very not no yes all any some more most much many also even still into out up down over again ever lol fucking fuck shit damn
earlier assistant said them they asked could didn don isn doesn wasn aren won wouldn shouldn couldn""".split())
WORD = re.compile(r"[a-z0-9][a-z0-9_.\-]*", re.I)


def keywords(text, n=8):
    seen, out = set(), []
    for w in WORD.findall(text.lower()):
        w = w.strip(".-")
        if len(w) > 2 and w not in STOP and w not in seen:
            seen.add(w); out.append(w)
    return out[:n]


def passages(page, terms, k=3, size=600):
    paras = [p.strip() for p in re.split(r"\n\s*\n|\n", page) if len(p.strip()) > 60]
    chunks = []
    for p in paras:                                          # long paragraphs → windows of ~size chars
        chunks += [p[i:i + size] for i in range(0, len(p), size)] if len(p) > size else [p]
    tset = set(terms)
    scored = sorted(chunks, key=lambda c: -len(tset & set(w.lower().strip(".-") for w in WORD.findall(c))))
    return [c for c in scored[:k] if tset & set(w.lower().strip(".-") for w in WORD.findall(c))]


URL = re.compile(r"\((https?://[^)\s]+)\)")


def smart_search(query, msg_text):
    terms = keywords(query + " " + msg_text, 14)
    msg_q = " ".join(keywords(msg_text, 8))
    results = [H.search(query)] + ([H.search(msg_q)] if msg_q and msg_q.lower() != query.lower() else [])
    lines, urls = [], []
    for r in results:
        for line in r.splitlines():
            if line not in lines:
                lines.append(line)
                urls += URL.findall(line)[:1]
    out = "Search results:\n" + "\n".join(lines[:8])
    got = 0
    for u in urls:
        if got == 2:
            break
        page = H.fetch(u)
        if page.startswith("(fetch failed") or page == "(empty page)":
            continue
        ps = passages(page, terms)
        if ps:
            out += f"\n\nFrom {u}:\n" + "\n...\n".join(ps)
            got += 1
    return out


def solve_all_v3(self, tasks):
    max_new = 1024
    convs, traces = [], []
    for t in tasks:
        body = (f"Context: {t['ctx']}\n\n" if t["ctx"] else "") + t["msg"]
        convs.append([{"role": "system", "content": V2.SYSTEM}, {"role": "user", "content": body}])
        traces.append({"id": t["id"], "msg": t["msg"], "steps": [], "answer": None, "bad_calls": 0})
    msgs = [t["msg"] + (" " + t["ctx"] if t["ctx"] else "") for t in tasks]      # the message's own words come first
    active = list(range(len(tasks)))
    for turn in range(V2.MAX_TURNS + 1):
        if not active:
            break
        outs = self.reply([convs[i] for i in active], max_new)
        still = []
        for i, o in zip(active, outs):
            visible = o.split("</think>")[-1]
            m = V2.CALL.search(visible)
            call = None
            if m:
                try:
                    call = json.loads(m[1])
                except json.JSONDecodeError:
                    traces[i]["bad_calls"] += 1
            if call is None or turn == V2.MAX_TURNS:
                traces[i]["answer"] = V2.CALL.sub("", visible).strip()
                continue
            name, args = call.get("name", ""), call.get("arguments", {}) or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            result = smart_search(str(args.get("query", "")), msgs[i]) if name == "search" else V2.run_tool(name, args)
            traces[i]["steps"].append({"tool": name, "args": args, "result": result[:1500]})
            convs[i].append({"role": "assistant", "content": "", "tool_calls": [{"type": "function", "function": {"name": name, "arguments": args}}]})
            convs[i].append({"role": "tool", "content": result[:3500]})
            still.append(i)
        active = still
    return traces


class Runner3(V2.Runner):
    solve_all = solve_all_v3


def main():
    t0, out = time.time(), []
    for name, think in CONFIGS:
        r = Runner3(name, think)
        for tr in r.solve_all(H.TASKS):
            t = H.TASKS[tr["id"]]
            ans = tr["answer"] or ""
            tr.update(model=name, think=think,
                      auto_pass=all(re.search(p, ans, re.I | re.S) for p in t["auto"]) and not any(re.search(p, ans, re.I) for p in t["fail_if"]))
            out.append(tr)
        rows = [o for o in out if o["model"] == name]
        print(f"{name}: auto {sum(o['auto_pass'] for o in rows)}/{len(rows)}, searches {sum(len(o['steps']) for o in rows)} ({time.time()-t0:.0f}s)", flush=True)
        del r; torch.cuda.empty_cache()
        json.dump(out, open("out/traces.json", "w"), indent=1, ensure_ascii=False)
        json.dump(H.CACHE, open("out/cache.json", "w"), indent=1, ensure_ascii=False)
    L = ["# Harness v3 (smarter search, thinking on): auto check (first pass; Claude grades by hand)", ""]
    for name, think in CONFIGS:
        rows = [o for o in out if o["model"] == name]
        acts = {}
        for o in rows:
            for s in o["steps"]:
                acts[s["tool"]] = acts.get(s["tool"], 0) + 1
        L.append(f"- {name}: {sum(o['auto_pass'] for o in rows)}/{len(rows)}; tool calls: {acts or 'none'}")
    open("out/AUTO.md", "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
