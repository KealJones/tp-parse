"""Off-the-shelf small models on two tests, no fine-tuning, thinking off, greedy:
  1. tools: the held-out figure-it-out test (world2 v3 names), scored with world2's scorer and the fixed `fair_score`
  2. ts:    MultiPL-E HumanEval-TypeScript (159 problems), each answer run against its tests with Node's type stripping

  python multi_eval.py --models LiquidAI/LFM2.5-350M,Qwen/Qwen2.5-Coder-0.5B-Instruct --out out
Writes out/MULTI_RESULTS.md, out/tools_<model>.jsonl and out/ts_<model>.jsonl."""
import argparse, json, os, re, sys, time, zlib, gc, subprocess, tempfile, concurrent.futures as cf
import world2 as w

ap = argparse.ArgumentParser()
ap.add_argument("--models", default="LiquidAI/LFM2.5-350M")
ap.add_argument("--tests", default="tools,ts")
ap.add_argument("--per_type", type=int, default=24)
ap.add_argument("--max_turns", type=int, default=12)
ap.add_argument("--bs", type=int, default=24)
ap.add_argument("--limit", type=int, default=0, help="only this many episodes / problems (for smoke tests)")
ap.add_argument("--device", default="cuda")
ap.add_argument("--out", default="out")
A = ap.parse_args()
os.makedirs(A.out, exist_ok=True)
T0 = time.time()
LOG = open(os.path.join(A.out, "log.txt"), "a")


def log(*a):
    s = f"[{(time.time() - T0) / 60:5.1f} min] " + " ".join(str(x) for x in a)
    print(s, flush=True); LOG.write(s + "\n"); LOG.flush()


# ------------------------------------------------------------------ tool-call parsing (every format we may see)
def parse_any(text):
    """-> (visible text, [{"name", "arguments"}]) for LFM2.5, Qwen3.5 (XML) and Qwen2.5 / hermes (JSON) tool calls."""
    t = text.split("<|im_end|>")[0].split("<|endoftext|>")[0]
    t = re.sub(r"<think>.*?</think>", "", t, flags=re.S).replace("<think>", "").replace("</think>", "")
    if "<|tool_call_start|>" in t:
        return w.parse_lfm(t)
    calls = []
    for m in re.finditer(r"<tool_call>\s*<function=([\w.-]+)>(.*?)</function>\s*(?:</tool_call>|$)", t, re.S):
        calls.append({"name": m.group(1), "arguments": {k: v.strip() for k, v in re.findall(r"<parameter=(\w+)>\s*(.*?)\s*</parameter>", m.group(2), re.S)}})
    if not calls:
        for m in re.finditer(r"<tool_call>\s*(\{.*?\})\s*(?:</tool_call>|$)", t, re.S):
            try:
                j = json.loads(m.group(1)); calls.append({"name": j.get("name"), "arguments": j.get("arguments") or {}})
            except Exception:
                pass
    if not calls:   # small Qwen2.5 models often write the call as a bare JSON object (in a ```json block) instead of <tool_call>
        dec, i = json.JSONDecoder(), 0
        while True:                       # decode every top-level JSON object, however it is spread over lines
            i = t.find("{", i)
            if i < 0:
                break
            try:
                j, end = dec.raw_decode(t, i)
            except ValueError:
                i += 1; continue
            if isinstance(j, dict) and j.get("name") in ("search", "calculator", "ask_person"):
                calls.append({"name": j["name"], "arguments": j.get("arguments") or {}})
            i = end
        if calls:
            return t.split("```")[0].split("{")[0].strip(), calls
    return t.split("<tool_call>")[0].strip(), calls


def chat(tok, msgs, tools=None):
    kw = dict(tokenize=False, add_generation_prompt=True)
    try:
        return tok.apply_chat_template(msgs, tools=tools, enable_thinking=False, **kw)
    except TypeError:
        return tok.apply_chat_template(msgs, tools=tools, **kw)


class Runner:
    def __init__(self, name):
        from transformers import AutoTokenizer
        self.name = name
        self.tok = AutoTokenizer.from_pretrained(name)
        self.tok.padding_side = "left"
        if self.tok.pad_token is None:
            self.tok.pad_token = self.tok.eos_token
        self.model = None
        if A.device != "none":
            import torch, transformers
            self.torch = torch
            dt = torch.bfloat16 if A.device == "cuda" else torch.float32
            for cls in ("AutoModelForCausalLM", "AutoModelForImageTextToText"):
                try:
                    self.model = getattr(transformers, cls).from_pretrained(name, dtype=dt).to(A.device).eval()
                    log(f"{name}: loaded with {cls}")
                    break
                except Exception as e:
                    log(f"{name}: {cls} failed: {repr(e)[:300]}")
            if self.model is None:
                raise RuntimeError("could not load " + name)
        ids = [self.tok.convert_tokens_to_ids(t) for t in ("<|im_end|>", "<|endoftext|>")] + [self.tok.eos_token_id]
        self.stop = sorted({i for i in ids if isinstance(i, int) and i >= 0 and i != self.tok.unk_token_id})

    def generate(self, prompts, max_new):
        outs = []
        for k in range(0, len(prompts), A.bs):
            chunk = prompts[k:k + A.bs]
            enc = self.tok(chunk, return_tensors="pt", padding=True, add_special_tokens=False).to(A.device)
            with self.torch.no_grad():
                g = self.model.generate(**enc, max_new_tokens=max_new, do_sample=False, eos_token_id=self.stop, pad_token_id=self.tok.pad_token_id)
            for row in g[:, enc["input_ids"].shape[1]:]:
                outs.append(self.tok.decode(row, skip_special_tokens=False).replace(self.tok.pad_token or "", ""))
        return outs

    def close(self):
        del self.model; gc.collect()
        try:
            self.torch.cuda.empty_cache()
        except Exception:
            pass


# ------------------------------------------------------------------ test 1: figure-it-out (held-out types)
def tools_test(R):
    TEST = []
    for fn in w.HELD_OUT:
        TEST += w.make_set(zlib.crc32(fn.__name__.encode()) % 1000 + 300, A.per_type, [fn])
    if A.limit:
        TEST = TEST[::max(1, len(TEST) // A.limit)][:A.limit]
    S = [{"t": t, "msgs": [{"role": "system", "content": w.SYSTEM}, {"role": "user", "content": t["request"]}],
          "H": w.Harness(t), "final": None, "first": "", "outputs": [], "raw": []} for t in TEST]
    live, turn = list(range(len(S))), 0
    while live:
        turn += 1
        outs = R.generate([chat(R.tok, S[i]["msgs"], w.TOOLS) for i in live], 400)
        nxt = []
        for i, text in zip(live, outs):
            s = S[i]; s["raw"].append(text)
            vis, calls = parse_any(text)
            if turn == 1:
                s["first"] = vis
            if calls and turn < A.max_turns:
                res = [s["H"].run(c["name"], c["arguments"]) for c in calls]
                s["outputs"] += res
                s["msgs"].append({"role": "assistant", "content": vis, "tool_calls": [
                    {"id": f"c{turn}_{j}", "type": "function", "function": {"name": c["name"], "arguments": c["arguments"]}} for j, c in enumerate(calls)]})
                for j, (c, r) in enumerate(zip(calls, res)):
                    s["msgs"].append({"role": "tool", "tool_call_id": f"c{turn}_{j}", "name": c["name"], "content": r})
                nxt.append(i)
            else:
                s["final"] = vis
        live = nxt
        log(f"{R.name} tools: turn {turn}, {len(live)} still going")
    rows = []
    for s in S:
        sc = w.score(s["t"], s["final"] or "", s["H"], s["first"])
        fs = w.fair_score(s["t"], s["final"], s["H"], s["outputs"])
        rows.append({"type": s["t"]["type"], "style": s["t"]["style"], "request": s["t"]["request"], "gold": str(s["t"]["short"]),
                     "final": s["final"], "ok": sc["ok"], "strict": sc["strict"], **fs,
                     "calls": [[n, a] for n, a in s["H"].log], "outputs": s["outputs"], "raw": s["raw"]})
    return rows


# ------------------------------------------------------------------ test 2: MultiPL-E HumanEval-TypeScript
TS_ASK = ("Complete this TypeScript function. Reply with the complete function in one ```typescript code block "
          "and nothing else.\n\n```typescript\n{prompt}```")


def ts_problems():
    import pandas as pd
    from huggingface_hub import hf_hub_download
    df = pd.read_parquet(hf_hub_download("nuprl/MultiPL-E", "humaneval-ts/test-00000-of-00001.parquet", repo_type="dataset"))
    probs = df.to_dict("records")
    return probs[:A.limit] if A.limit else probs


def ts_program(prob, reply):
    m = re.search(r"```(?:typescript|ts|javascript|js)?\s*\n(.*?)(?:```|$)", reply, re.S)
    code = m.group(1) if m else reply
    code = re.sub(r"^\s*export\s+(default\s+)?", "", code, flags=re.M)
    fname = re.findall(r"function\s+(\w+)\s*\(", prob["prompt"])[-1]     # the signature, not "function" in the comment
    if not re.search(r"function\s+" + re.escape(fname) + r"\b", code):
        code = prob["prompt"] + code                  # the model wrote only the body
    return code + "\n\n" + prob["tests"]


def run_ts(program):
    with tempfile.NamedTemporaryFile("w", suffix=".ts", delete=False) as f:
        f.write(program)
    try:
        r = subprocess.run([sys.executable, "-m", "nodejs_wheel", "--experimental-transform-types", "--no-warnings", f.name],
                           capture_output=True, text=True, timeout=15)
        return r.returncode == 0, (r.stderr or "")[-300:]
    except subprocess.TimeoutExpired:
        return False, "timeout"
    finally:
        os.unlink(f.name)


def ts_test(R, probs):
    replies = R.generate([chat(R.tok, [{"role": "user", "content": TS_ASK.format(prompt=p["prompt"])}]) for p in probs], 768)
    progs = [ts_program(p, rep.split("<|im_end|>")[0]) for p, rep in zip(probs, replies)]
    with cf.ThreadPoolExecutor(8) as ex:
        results = list(ex.map(run_ts, progs))
    log(f"{R.name} ts: {sum(ok for ok, _ in results)}/{len(probs)} pass")
    return [{"name": p["name"], "pass": ok, "err": err, "reply": rep, "program": prog}
            for p, rep, prog, (ok, err) in zip(probs, replies, progs, results)]


# ------------------------------------------------------------------ main
def pct(xs):
    return f"{100 * sum(xs) / max(1, len(xs)):.0f}%"


tests = A.tests.split(",")
probs = ts_problems() if "ts" in tests else []
summary, by_type = [], {}
for name in A.models.split(","):
    short = name.split("/")[-1]
    t1 = time.time()
    try:
        R = Runner(name)
    except Exception as e:
        log(f"{name} failed to load: {e!r}"[:1000]); summary.append([short, "load failed", "", "", "", "", ""]); continue
    row = [short]
    try:
        if "tools" in tests:
            rows = tools_test(R)
            with open(os.path.join(A.out, f"tools_{short}.jsonl"), "w") as f:
                f.writelines(json.dumps(r) + "\n" for r in rows)
            cl = [r for r in rows if r["style"] == "clean"]; ms = [r for r in rows if r["style"] == "messy"]
            row += [pct([r["ok"] for r in rows]), pct([r["fair_ok"] for r in rows]), pct([r["fair_strict"] for r in rows]),
                    f"{pct([r['fair_ok'] for r in cl])} / {pct([r['fair_ok'] for r in ms])}"]
            for ty in sorted({r["type"] for r in rows}):
                by_type.setdefault(ty, {})[short] = pct([r["fair_ok"] for r in rows if r["type"] == ty])
        else:
            row += ["", "", "", ""]
        if "ts" in tests:
            ts = ts_test(R, probs)
            with open(os.path.join(A.out, f"ts_{short}.jsonl"), "w") as f:
                f.writelines(json.dumps(r) + "\n" for r in ts)
            row.append(f"{pct([r['pass'] for r in ts])} ({sum(r['pass'] for r in ts)}/{len(ts)})")
        else:
            row.append("")
    except Exception as e:
        import traceback
        log(f"{name} crashed: " + traceback.format_exc()[-2000:]); row += ["crashed"] * (6 - len(row))
    row.append(f"{(time.time() - t1) / 60:.1f}")
    R.close()
    summary.append(row)
    log(" | ".join(row))
    head = ["model", "tools: right (old scorer)", "tools: right (fair)", "tools: fair strict", "fair right, clean / messy", "TypeScript pass@1", "minutes"]
    md = ["# Small models off the shelf: figure-it-out test (v3 names) and TypeScript", "",
          "No fine-tuning, thinking off, greedy. Tools test: the 120 held-out episodes (5 types x 24), same system prompt and tools as "
          "the pilot, now with normal-sounding names; 'fair' is `world2.fair_score`. TypeScript: MultiPL-E HumanEval-TS, 159 problems, "
          "first answer only, run against the problem's tests.", "",
          "| " + " | ".join(head) + " |", "|" + " --- |" * len(head)] + ["| " + " | ".join(r) + " |" for r in summary]
    ms_ = [r[0] for r in summary]
    md += ["", "## Tools test by held-out type (fair right answer)", "", "| type | " + " | ".join(ms_) + " |", "|" + " --- |" * (len(ms_) + 1)]
    md += ["| " + ty + " | " + " | ".join(v.get(m, "") for m in ms_) + " |" for ty, v in by_type.items()]
    open(os.path.join(A.out, "MULTI_RESULTS.md"), "w").write("\n".join(md) + "\n")
log("done")
