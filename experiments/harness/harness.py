"""The harness, first cut: an untouched model answers Keal's real messages with tools.

Each turn the model replies with one action line: SEARCH: <query> | FETCH: <url> | ASK: <question> | ANSWER: <answer>.
The harness runs it and feeds the result back (up to MAX_TURNS), then forces an answer. Long messages are first
chunked: the model notes what the person wants from each piece. Search and fetch results are cached by the exact
query/URL the model typed (a new query always gets a live search). ASK gets "Keal isn't available" in automated runs.

  python harness.py [--pilot]      writes out/traces.json, out/AUTO.md, out/cache.json
"""
import json, os, re, sys, time, urllib.parse
import requests
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

PILOT = "--pilot" in sys.argv
CONFIGS = [("Qwen/Qwen3-0.6B", False), ("Qwen/Qwen3-0.6B", True), ("Qwen/Qwen3-1.7B", True), ("Qwen/Qwen3-4B", True)]
if PILOT:
    CONFIGS = CONFIGS[:2]
MAX_TURNS, CHUNK_WORDS, RESULT_CHARS = 6, 150, 1800
os.makedirs("out", exist_ok=True)
TASKS = json.load(open("tasks.json"))[: 2 if PILOT else None]
CACHE = json.load(open("cache.json")) if os.path.exists("cache.json") else {}
UA = {"User-Agent": "Mozilla/5.0 (tp-parse harness research)"}

SYSTEM = """You are a small assistant inside a harness. You know little, but the harness can look things up for you.
Never guess facts you are not sure of. The person's message may be messy, misspelled, rambling or spoken.
Each turn, reply with exactly one line, in one of these forms:
SEARCH: <a web search query>
FETCH: <a url to read>
ASK: <a question for the person>
ANSWER: <your final answer to the person>
Search when the message mentions something you don't know well, or when exact details matter (commands, names,
numbers, prices). Answer only once you are confident; keep the answer short and direct."""


# ------------------------------------------------------------------ tools

def search(q):
    key = "search:" + q
    if key in CACHE:
        return CACHE[key]
    out = ""
    try:
        from ddgs import DDGS
        for attempt in range(3):
            try:
                rs = list(DDGS().text(q, max_results=5))
                out = "\n".join(f"- {r['title']} ({r['href']}): {r['body']}" for r in rs)
                break
            except Exception as e:
                time.sleep(2 + 3 * attempt)
    except ImportError:
        pass
    if not out:                                           # fallback: Wikipedia search
        try:
            j = requests.get("https://en.wikipedia.org/w/api.php", headers=UA, timeout=20, params={
                "action": "query", "list": "search", "srsearch": q, "format": "json", "srlimit": 5}).json()
            out = "\n".join(f"- {r['title']} (https://en.wikipedia.org/wiki/{urllib.parse.quote(r['title'].replace(' ', '_'))}): "
                            + re.sub(r"<[^>]+>", "", r["snippet"]) for r in j["query"]["search"])
        except Exception as e:
            out = f"(search failed: {e})"
    out = out or "(no results)"
    CACHE[key] = out
    time.sleep(1)
    return out


def fetch(url):
    key = "fetch:" + url
    if key in CACHE:
        return CACHE[key]
    try:
        html = requests.get(url, headers=UA, timeout=25).text
        try:
            import trafilatura
            text = trafilatura.extract(html) or ""
        except ImportError:
            text = ""
        if not text:
            text = re.sub(r"\s+", " ", re.sub(r"<(script|style)[^>]*>.*?</\1>|<[^>]+>", " ", html, flags=re.S | re.I))
        out = text.strip()[:6000] or "(empty page)"
    except Exception as e:
        out = f"(fetch failed: {e})"
    CACHE[key] = out
    return out


def run_tool(action, arg):
    if action == "SEARCH":
        return search(arg)
    if action == "FETCH":
        return fetch(arg if arg.startswith("http") else "https://" + arg)
    if action == "ASK":
        return "Keal isn't available right now. Work it out yourself, or answer and say what you'd need to be sure."
    return None


# ------------------------------------------------------------------ the loop

ACTION = re.compile(r"^\s*\**(SEARCH|FETCH|ASK|ANSWER)\**\s*:\s*(.+)", re.I | re.M)


def parse(text):
    """The first action line after any thinking; a reply with no action line counts as the answer."""
    visible = text.split("</think>")[-1]
    m = ACTION.search(visible)
    if not m:
        return "ANSWER", visible.strip()
    act, arg = m[1].upper(), m[2].strip()
    if act == "ANSWER":                                   # keep everything after ANSWER:, it may span lines
        arg = visible[m.start(2):].strip()
    return act, arg.lstrip("* ").strip()


def chunks(msg):
    words = msg.split()
    if len(words) <= CHUNK_WORDS:
        return [msg]
    sents, out, cur = re.split(r"(?<=[.?!])\s+", msg), [], []
    for s in sents:
        if cur and len(" ".join(cur + [s]).split()) > CHUNK_WORDS:
            out.append(" ".join(cur)); cur = []
        cur.append(s)
    return out + ([" ".join(cur)] if cur else [])


class Runner:
    def __init__(self, name, think):
        self.tok = AutoTokenizer.from_pretrained(name)
        self.tok.padding_side = "left"
        self.model = AutoModelForCausalLM.from_pretrained(name, dtype=torch.bfloat16).to("cuda").eval()
        self.think = think

    @torch.no_grad()
    def reply(self, convs, max_new):
        texts = [self.tok.apply_chat_template(c, tokenize=False, add_generation_prompt=True, enable_thinking=self.think) for c in convs]
        outs = []
        for i in range(0, len(texts), 6):
            enc = self.tok(texts[i:i + 6], return_tensors="pt", padding=True, add_special_tokens=False).to("cuda")
            g = self.model.generate(**enc, max_new_tokens=max_new, do_sample=False, pad_token_id=self.tok.pad_token_id)
            outs += [self.tok.decode(g[j, enc["input_ids"].shape[1]:], skip_special_tokens=True) for j in range(len(texts[i:i + 6]))]
        return outs

    def solve_all(self, tasks):
        max_new = 1024 if self.think else 300
        convs, traces = [], []
        for t in tasks:
            parts = chunks(t["msg"])
            notes = []
            if len(parts) > 1:                            # long input: note what they want from each piece first
                for k, p in enumerate(parts):
                    c = [{"role": "system", "content": "Read this part of a long message and write one line: what does the person want so far?"},
                         {"role": "user", "content": f"Notes so far: {' '.join(notes) or '(none)'}\nPart {k+1} of {len(parts)}: {p}"}]
                    notes.append(self.reply([c], 200)[0].split("</think>")[-1].strip())
            body = (f"Context: {t['ctx']}\n\n" if t["ctx"] else "") + (
                f"Message (long, summarized from {len(parts)} parts): {' | '.join(notes)}\nLast part: {parts[-1]}" if notes else f"Message: {t['msg']}")
            convs.append([{"role": "system", "content": SYSTEM}, {"role": "user", "content": body}])
            traces.append({"id": t["id"], "msg": t["msg"], "steps": [], "chunks": len(parts), "notes": notes, "answer": None})
        active = list(range(len(tasks)))
        for turn in range(MAX_TURNS + 1):
            if not active:
                break
            if turn == MAX_TURNS:
                for i in active:
                    convs[i].append({"role": "user", "content": "Give your ANSWER now."})
            outs = self.reply([convs[i] for i in active], max_new)
            still = []
            for i, o in zip(active, outs):
                act, arg = parse(o)
                if turn == MAX_TURNS:
                    act = "ANSWER"
                    arg = arg if parse(o)[0] == "ANSWER" else o.split("</think>")[-1].strip()
                convs[i].append({"role": "assistant", "content": o.split("</think>")[-1].strip()})
                if act == "ANSWER":
                    traces[i]["answer"] = re.sub(r"^\s*\**ANSWER\**\s*:\s*", "", arg, flags=re.I).strip()
                    continue
                result = run_tool(act, arg)
                traces[i]["steps"].append({"action": act, "arg": arg, "result": result[:400]})
                convs[i].append({"role": "user", "content": f"Result of {act}:\n{result[:RESULT_CHARS]}"})
                still.append(i)
            active = still
        return traces


def main():
    t0, out = time.time(), []
    for name, think in CONFIGS:
        r = Runner(name, think)
        for tr in r.solve_all(TASKS):
            t = TASKS[tr["id"]]
            ans = tr["answer"] or ""
            tr.update(model=name, think=think,
                      auto_pass=all(re.search(p, ans, re.I | re.S) for p in t["auto"]) and not any(re.search(p, ans, re.I) for p in t["fail_if"]))
            out.append(tr)
        print(f"{name} think={think}: auto {sum(o['auto_pass'] for o in out if o['model'] == name and o['think'] == think)}/{len(TASKS)}, "
              f"tool calls {sum(len(o['steps']) for o in out if o['model'] == name and o['think'] == think)} ({time.time()-t0:.0f}s)", flush=True)
        del r; torch.cuda.empty_cache()
        json.dump(out, open("out/traces.json", "w"), indent=1, ensure_ascii=False)
        json.dump(CACHE, open("out/cache.json", "w"), indent=1, ensure_ascii=False)
    L = ["# Harness run: auto check (first pass; Claude grades by hand against each rule)", ""]
    for name, think in CONFIGS:
        rows = [o for o in out if o["model"] == name and o["think"] == think]
        acts = {}
        for o in rows:
            for s in o["steps"]:
                acts[s["action"]] = acts.get(s["action"], 0) + 1
        L.append(f"- {name}, thinking {'on' if think else 'off'}: {sum(o['auto_pass'] for o in rows)}/{len(rows)}; "
                 f"tool calls: {acts or 'none'}")
    open("out/AUTO.md", "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
