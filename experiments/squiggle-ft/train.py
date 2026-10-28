"""Train candidate small models on the teacher episodes, score them end to end in Squiggle's real harness, write
RESULTS.md with a go/no-go, and (--export) turn the winner into a GGUF wllama 3.8.1 can load.

  python train.py --data train_examples.jsonl.gz --bases gemma3,functiongemma,lfm25 --epochs 2 --out out [--export]
  python train.py --eval-only --bases gemma3 --out out          # just score the untouched model

Training: full fine-tune, loss only on the model's output (thinking + call, or the reply), each base with its own
chat template (what its GGUF carries), micro-batches packed by tokens, AdamW + cosine.
Eval: fresh episodes of the trained task types (other repos, other questions) plus three held-out types, run in
the real harness with phone sampling (backends.HFStudent).
"""
import argparse, collections, gc, gzip, json, math, os, random, shutil, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import families as F

BASES = {
    "gemma3": "unsloth/gemma-3-270m-it",                # mirror of google/gemma-3-270m-it (the current phone model)
    "functiongemma": "unsloth/functiongemma-270m-it",   # mirror of google/functiongemma-270m-it
    "lfm25": "LiquidAI/LFM2.5-350M",
}
MULTI = {"repo_two", "web_compare", "web_bridge", "recipe_repo", "recipe_compare"}
NEED = {"need_repo", "need_math", "hermes_need"}

# Go/no-go bars (decided before the run; see README "What go/no-go means").
BARS = {"trained_strict": 0.50, "held_strict": 0.30, "held_min": 0.01, "format": 0.95, "loops": 0.05, "chat": 0.90, "messy_gap": 0.10}


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


# ── data ────────────────────────────────────────────────────────────────────
def read_jsonl(path):
    op = gzip.open if str(path).endswith(".gz") else open
    with op(path, "rt") as f:
        return [json.loads(l) for l in f if l.strip()]


def render(tok, ex, max_prompt=4096, max_out=1024):
    prompt = tok.apply_chat_template(ex["messages"], tokenize=False, add_generation_prompt=True)
    full = tok.apply_chat_template(ex["messages"] + [{"role": "assistant", "content": ex["output"]}], tokenize=False)
    if not full.startswith(prompt):
        return None
    p = tok(prompt, add_special_tokens=False).input_ids
    o = tok(full[len(prompt):], add_special_tokens=False).input_ids
    if len(p) > max_prompt or len(o) > max_out or not o:
        return None
    return p, o


def batches(items, budget, rng):
    """items: [(prompt_ids, out_ids)] -> micro-batches whose padded size stays under `budget` tokens."""
    order = sorted(range(len(items)), key=lambda i: len(items[i][0]) + len(items[i][1]))
    out, cur, longest = [], [], 0
    for i in order:
        n = len(items[i][0]) + len(items[i][1])
        if cur and max(longest, n) * (len(cur) + 1) > budget:
            out.append(cur)
            cur, longest = [], 0
        cur.append(i)
        longest = max(longest, n)
    if cur:
        out.append(cur)
    rng.shuffle(out)
    return out


# ── training ────────────────────────────────────────────────────────────────
def copy_tokenizer(base, out_dir):
    """The base model's own tokenizer files, unchanged (the tokenizer isn't trained). transformers 5 re-saves Gemma's
    tokenizer without tokenizer.model, which llama.cpp's converter then rejects."""
    from huggingface_hub import snapshot_download
    snap = snapshot_download(BASES[base], allow_patterns=["tokenizer*", "special_tokens_map.json", "added_tokens.json",
                                                          "chat_template.jinja", "generation_config.json"])
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    for f in Path(snap).iterdir():
        if f.is_file():
            shutil.copy(f, Path(out_dir) / f.name)



def train(base, examples, out_dir, epochs=2, lr=4e-5, budget=8192, per_step=32, seed=0):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    torch.manual_seed(seed)
    rng = random.Random(seed)
    tok = AutoTokenizer.from_pretrained(BASES[base])
    items = [r for r in (render(tok, ex) for ex in examples) if r]
    log(f"[{base}] {len(items)} of {len(examples)} examples fit; target tokens {sum(len(o) for _, o in items)}, all tokens {sum(len(p) + len(o) for p, o in items)}")
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    dt = torch.bfloat16 if dev == "cuda" and torch.cuda.is_bf16_supported() else torch.float32
    model = AutoModelForCausalLM.from_pretrained(BASES[base], dtype=torch.float32, attn_implementation="sdpa").to(dev)
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    log(f"[{base}] attention {model.config._attn_implementation}, gradient checkpointing {model.is_gradient_checkpointing}")
    model.config.use_cache = False
    head = model.get_output_embeddings()
    softcap = getattr(model.config, "final_logit_softcapping", None)

    def chunk_loss(hc, yc):
        logits = head(hc).float()
        if softcap:
            logits = torch.tanh(logits / softcap) * softcap
        return torch.nn.functional.cross_entropy(logits, yc, reduction="sum")
    opt = (torch.optim.SGD(model.parameters(), lr=lr) if os.environ.get("SQFT_SGD")       # tiny-memory local tests only
           else torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.0, betas=(0.9, 0.95)))
    mbs_per_epoch = len(batches(items, budget, random.Random(0)))
    ex_per_mb = len(items) / max(1, mbs_per_epoch)
    accum = max(1, round(per_step / ex_per_mb))
    total = math.ceil(mbs_per_epoch / accum) * epochs
    warm = max(5, total // 30)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1, (s + 1) / warm) * 0.5 * (1 + math.cos(math.pi * min(1.0, s / total))))
    log(f"[{base}] {mbs_per_epoch} micro-batches/epoch, accum {accum}, {total} steps, warmup {warm}")
    step = 0
    t0 = time.time()
    model.train()
    for ep in range(epochs):
        mbs = batches(items, budget, rng)
        run_loss, run_n = 0.0, 0
        opt.zero_grad(set_to_none=True)
        for k, mb in enumerate(mbs):
            L = max(len(items[i][0]) + len(items[i][1]) for i in mb)
            ids = torch.full((len(mb), L), tok.pad_token_id or 0, dtype=torch.long)
            att = torch.zeros((len(mb), L), dtype=torch.long)
            lab = torch.full((len(mb), L), -100, dtype=torch.long)
            for r, i in enumerate(mb):
                p, o = items[i]
                seq = p + o
                ids[r, :len(seq)] = torch.tensor(seq)
                att[r, :len(seq)] = 1
                lab[r, len(p):len(seq)] = torch.tensor(o)
            ids, att, lab = ids.to(dev), att.to(dev), lab.to(dev)
            with torch.autocast(dev, dtype=dt, enabled=dev == "cuda"):
                hid = model.model(input_ids=ids, attention_mask=att).last_hidden_state
                # Loss only where a target token is predicted. The vocabulary is huge (Gemma: 262k), so logits are made
                # 512 positions at a time and recomputed in the backward pass instead of kept.
                tgt = lab[:, 1:]
                sel = tgt != -100
                h = hid[:, :-1][sel]
                y = tgt[sel]
                loss = sum(torch.utils.checkpoint.checkpoint(chunk_loss, h[i:i + 512], y[i:i + 512], use_reentrant=False)
                           for i in range(0, h.shape[0], 512))
            n_t = int(sel.sum())
            (loss / max(1, n_t) / accum).backward()
            run_loss += loss.item(); run_n += n_t
            if (k + 1) % accum == 0 or k == len(mbs) - 1:
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                opt.step(); sched.step(); opt.zero_grad(set_to_none=True)
                step += 1
                if step % 20 == 0:
                    log(f"[{base}] epoch {ep + 1} step {step}/{total} loss {run_loss / max(1, run_n):.4f} lr {sched.get_last_lr()[0]:.2e} ({(time.time() - t0) / 60:.1f} min)")
                    run_loss, run_n = 0.0, 0
    model.config.use_cache = True
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    model.save_pretrained(out_dir, safe_serialization=True)
    copy_tokenizer(base, out_dir)
    del model, opt
    gc.collect()
    if dev == "cuda":
        torch.cuda.empty_cache()
    return (time.time() - t0) / 60


# ── eval ────────────────────────────────────────────────────────────────────
def evaluate(model_path, episodes, work, squiggle, label, out_dir, minutes=25):
    import torch
    from backends import HFStudent
    from sqrun import Runner
    st = HFStudent(model_path, device="cuda" if torch.cuda.is_available() else "cpu")
    runner = Runner(st, squiggle, work, concurrency=48, batch_wait=0.5, max_calls=30)
    t0 = time.time()
    res = runner.run(episodes, deadline=time.time() + minutes * 60)
    for r in res:
        r["check"] = F.check(r)
    with gzip.open(Path(out_dir) / f"eval_{label}.jsonl.gz", "wt") as f:
        for r in res:
            f.write(json.dumps({k: r.get(k) for k in ("id", "family", "first", "gold", "meta", "check", "error", "capped")} |
                               {"turns": [{"reply": t.get("reply"), "tools": t.get("tools")} for t in r.get("turns", [])],
                                "outputs": [{"kind": c.get("kind"), "output": c.get("output")} for c in r.get("calls", [])]}, ensure_ascii=False) + "\n")
    log(f"[{label}] eval {len(res)} episodes in {(time.time() - t0) / 60:.1f} min; student {st.stats}")
    del st
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return res


def metrics(res):
    fam = collections.defaultdict(list)
    for r in res:
        fam[r["family"]].append(r)
    m = {"families": {}}
    for f, rs in sorted(fam.items()):
        m["families"][f] = {"n": len(rs), "ok": sum(r["check"]["ok"] for r in rs) / len(rs), "strict": sum(r["check"]["strict"] for r in rs) / len(rs)}
    tr = [v["strict"] for f, v in m["families"].items() if f not in F.HELD_OUT]
    ho = [v["strict"] for f, v in m["families"].items() if f in F.HELD_OUT]
    m["trained_strict"] = sum(tr) / max(1, len(tr))
    m["trained_ok"] = sum(v["ok"] for f, v in m["families"].items() if f not in F.HELD_OUT) / max(1, len(tr))
    m["held_strict"] = sum(ho) / max(1, len(ho))
    m["held_min"] = min(ho) if ho else 0
    calls = [x for r in res for s in F.turn_calls(r) for x in s]
    bad = sum(1 for x in calls if F.format_problems([x]))
    m["format"] = 1 - bad / max(1, len(calls))
    m["loops"] = sum(1 for r in res if F.looped(r) or r.get("capped")) / max(1, len(res))
    multi = [r for r in res if r["family"] in MULTI]
    m["plans"] = sum(1 for r in multi if "plan" in F.names([x for s in F.turn_calls(r) for x in s])) / max(1, len(multi))
    needs = [r for r in res if r["family"] in NEED]
    m["asks"] = sum(1 for r in needs if F.asked_user(r, 0)) / max(1, len(needs))
    chats = [r for r in res if r["family"] == "chat"] + [r for r in res if r["family"] == "chat_after" and len(r.get("turns", [])) > 1]
    m["chat"] = sum(1 for r in chats if not F.check_chat_turn(r, 0 if r["family"] == "chat" else 1)) / max(1, len(chats))
    # done results carry the facts: in planned episodes that got the answer right, the step results hold it
    carried = []
    for r in res:
        if r["family"] in ("web_compare", "web_bridge") and r["check"]["ok"]:
            steps = " ".join((s.get("result") or "") for t in r.get("turns", []) if t.get("task") for s in t["task"].get("steps", []))
            if steps:
                carried.append(F.answer_in(steps, [r["gold"]["answer"]] + F.same_entity(r["gold"]["answer"], r["gold"].get("titles", []))) or r["gold"]["answer"].lower() in ("yes", "no"))
    m["done_facts"] = sum(carried) / len(carried) if carried else None
    for kind in (True, False):
        rs = [r for r in res if r.get("meta", {}).get("messy") is kind and r["family"] not in ("chat",)]
        m["messy" if kind else "clean"] = sum(r["check"]["strict"] for r in rs) / max(1, len(rs))
    m["messy_gap"] = m["clean"] - m["messy"]
    m["call_capped"] = sum(1 for r in res if r.get("capped")) / max(1, len(res))
    return m


def verdict(m, base_m):
    checks = [
        ("trained types, strict mean", m["trained_strict"] >= BARS["trained_strict"], f"{m['trained_strict']:.0%} (bar {BARS['trained_strict']:.0%})"),
        ("held-out types, strict mean", m["held_strict"] >= BARS["held_strict"], f"{m['held_strict']:.0%} (bar {BARS['held_strict']:.0%})"),
        ("no held-out type at 0%", m["held_min"] >= BARS["held_min"], f"lowest {m['held_min']:.0%}"),
        ("well-formed model calls", m["format"] >= BARS["format"], f"{m['format']:.1%} (bar {BARS['format']:.0%})"),
        ("episodes that loop or hit the call cap", m["loops"] <= BARS["loops"], f"{m['loops']:.1%} (bar ≤ {BARS['loops']:.0%})"),
        ("plain chat stays plain", m["chat"] >= BARS["chat"], f"{m['chat']:.0%} (bar {BARS['chat']:.0%})"),
        ("messy within 10 points of clean", m["messy_gap"] <= BARS["messy_gap"], f"clean {m['clean']:.0%}, messy {m['messy']:.0%}"),
    ]
    if base_m:
        better = m["trained_strict"] > base_m["trained_strict"] and m["held_strict"] > base_m["held_strict"]
        checks.append(("beats the untouched Gemma 3 270M", better, f"{m['trained_strict']:.0%}/{m['held_strict']:.0%} vs {base_m['trained_strict']:.0%}/{base_m['held_strict']:.0%}"))
    return all(c[1] for c in checks), checks


def write_results(out, arms, notes):
    names = list(arms)
    base_key = next((k for k in names if k.startswith("untouched")), None)
    tuned = [k for k in names if not k.startswith("untouched")]
    best = max(tuned, key=lambda k: arms[k]["trained_strict"] + arms[k]["held_strict"]) if tuned else None
    go, checks = verdict(arms[best], arms.get(base_key)) if best else (False, [])
    L = ["# Squiggle small-model fine-tune: results", ""]
    if best:
        L += [f"**Verdict: {'GO' if go else 'NO-GO (not yet)'}** for `{best}`.", ""]
        L += ["| check | pass | value |", "| --- | --- | --- |"] + [f"| {a} | {'yes' if b else 'no'} | {c} |" for a, b, c in checks] + [""]
    fams = sorted({f for a in arms.values() for f in a["families"]})
    L += ["## Strict score per task type (right answer and the habit)", "", "| type | habit | " + " | ".join(names) + " |", "| --- | --- |" + " --- |" * len(names)]
    for f in fams:
        L.append(f"| {f}{' (held out)' if f in F.HELD_OUT else ''} | {F.HABIT.get(f, '')} | " + " | ".join(
            f"{arms[a]['families'][f]['strict']:.0%} ({arms[a]['families'][f]['ok']:.0%})" if f in arms[a]["families"] else "-" for a in names) + " |")
    L += ["", "(right answer only in brackets)", "", "## Habits", "", "| measure | " + " | ".join(names) + " |", "| --- |" + " --- |" * len(names)]
    for key, label in [("trained_strict", "trained types, strict mean"), ("trained_ok", "trained types, right answer"), ("held_strict", "held-out types, strict mean"),
                       ("format", "well-formed calls"), ("loops", "episodes looping / call-capped"), ("plans", "plans multi-step requests"),
                       ("asks", "asks (need) when info is missing"), ("chat", "plain chat stays plain"), ("done_facts", "done results carry the answer"),
                       ("clean", "clean requests, strict"), ("messy", "messy requests, strict")]:
        L.append(f"| {label} | " + " | ".join("-" if arms[a].get(key) is None else f"{arms[a][key]:.0%}" for a in names) + " |")
    L += ["", "## Notes", ""] + notes
    (Path(out) / "RESULTS.md").write_text("\n".join(L) + "\n")
    return best, go


# ── export ──────────────────────────────────────────────────────────────────
def export(model_dir, base, out, hub_repo, results_md):
    """GGUF (Q8_0 and Q4_0) with llama.cpp's converter, a llama.cpp load-and-generate check, upload to a private repo."""
    work = Path(out) / "gguf"
    work.mkdir(parents=True, exist_ok=True)
    lc = Path(os.environ.get("LLAMA_CPP_DIR", "llama.cpp"))
    if not lc.exists():
        if subprocess.run(["git", "clone", "-q", "--depth", "1", "https://github.com/ggml-org/llama.cpp", str(lc)]).returncode != 0:
            subprocess.run([sys.executable, "-c", "import urllib.request as u; u.urlretrieve('https://codeload.github.com/ggml-org/llama.cpp/tar.gz/refs/heads/master', 'lc.tgz')"], check=True)
            subprocess.run(f"mkdir -p {lc} && tar xzf lc.tgz -C {lc} --strip-components=1", shell=True, check=True)
    copy_tokenizer(base, model_dir)            # models trained before this fix
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "gguf", "sentencepiece", "protobuf"], check=False)
    env = dict(os.environ, PYTHONPATH=str(lc / "gguf-py"))
    f8 = work / f"squiggle-small-{base}-Q8_0.gguf"
    subprocess.run([sys.executable, str(lc / "convert_hf_to_gguf.py"), model_dir, "--outtype", "q8_0", "--outfile", str(f8)], check=True, env=env)
    files = [f8]
    built = subprocess.run(f"cd {lc} && cmake -B build -DGGML_CUDA=OFF -DLLAMA_CURL=OFF -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_BUILD_SERVER=OFF >/dev/null "
                           "&& cmake --build build -j 8 --target llama-quantize llama-simple >/dev/null", shell=True).returncode == 0
    check = "llama.cpp build failed: no Q4_0 and no load check"
    if built:
        f16 = work / "f16.gguf"
        subprocess.run([sys.executable, str(lc / "convert_hf_to_gguf.py"), model_dir, "--outtype", "f16", "--outfile", str(f16)], check=True, env=env)
        f4 = work / f"squiggle-small-{base}-Q4_0.gguf"
        subprocess.run([str(lc / "build/bin/llama-quantize"), str(f16), str(f4), "Q4_0"], check=True)
        f16.unlink()
        files.append(f4)
        r = subprocess.run([str(lc / "build/bin/llama-simple"), "-m", str(f8), "-n", "32", "Hello"], capture_output=True, text=True, timeout=300)
        check = f"llama.cpp (master) loads the Q8_0 file and generates: {'yes' if r.returncode == 0 else 'NO'} ({(r.stdout + r.stderr)[-300:]!r})"
    sizes = {f.name: f.stat().st_size for f in files}
    log("GGUF", sizes, check)
    # The real runtime: wllama 3.8.1 in headless Chromium, the app's settings, a Squiggle prompt.
    subprocess.run(f"{sys.executable} -m pip install -q playwright && {sys.executable} -m playwright install --with-deps chromium >/dev/null 2>&1", shell=True)
    for f in files:
        r = subprocess.run([sys.executable, str(HERE / "wllama_check.py"), str(f)], capture_output=True, text=True, timeout=900)
        line = (r.stdout.strip().splitlines() or [r.stderr[-300:]])[-1]
        check += f"\n\nwllama 3.8.1 in Chromium, {f.name}: {line[:600]}"
        log("wllama check", f.name, line[:300])
    if hub_repo and os.environ.get("HF_TOKEN"):
        from huggingface_hub import HfApi
        api = HfApi(token=os.environ["HF_TOKEN"])
        api.create_repo(hub_repo, private=True, exist_ok=True)
        card = (f"# squiggle-small ({base})\n\nFine-tune of {BASES[base]} for Squiggle's phone harness (docs/harness.md, small-model format). "
                f"Load in wllama 3.8.1 with n_ctx 4096.\n\nFiles: " + ", ".join(f"{k} ({v / 1e6:.0f} MB)" for k, v in sizes.items()) + f"\n\n{check}\n\n" + Path(results_md).read_text())
        (work / "README.md").write_text(card)
        for f in files + [work / "README.md"]:
            api.upload_file(path_or_fileobj=str(f), path_in_repo=f.name, repo_id=hub_repo)
        log(f"uploaded to {hub_repo}")
    return sizes, check


# ── main ────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="")
    ap.add_argument("--bases", default="gemma3,functiongemma,lfm25")
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--lr", type=float, default=4e-5)
    ap.add_argument("--limit", type=int, default=0, help="use only this many training examples (smoke test)")
    ap.add_argument("--eval-scale", type=float, default=1.0)
    ap.add_argument("--eval-minutes", type=float, default=25)
    ap.add_argument("--eval-only", action="store_true")
    ap.add_argument("--no-untouched", action="store_true")
    ap.add_argument("--export", action="store_true")
    ap.add_argument("--budget-minutes", type=float, default=0, help="stop starting new bases when what's left can't fit one more (+15 min for export)")
    ap.add_argument("--hub-repo", default="kealjones/squiggle-small")
    ap.add_argument("--work", default=str(HERE / "work"))
    ap.add_argument("--out", default="out")
    ap.add_argument("--squiggle", default=os.environ.get("SQUIGGLE_DIR", str(HERE / "squiggle")))
    args = ap.parse_args()
    t_main = time.time()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    import build
    src = build.load_sources(Path(args.work), "eval")
    eval_eps = lambda: build.make_sets(src, build.EVAL_PLAN, seed=123, scale=args.eval_scale)
    log(f"eval set: {len(eval_eps())} episodes")
    arms, notes = {}, []
    bases = [b for b in args.bases.split(",") if b]
    if not args.no_untouched:
        arms["untouched-gemma3"] = metrics(evaluate(BASES["gemma3"], eval_eps(), args.work, args.squiggle, "untouched-gemma3", out, args.eval_minutes))
        json.dump(arms, open(out / "metrics.json", "w"), indent=1)
    if not args.eval_only:
        import glob
        examples = []
        paths = [g for p in args.data.split(",") if p for g in (sorted(glob.glob(p)) or [p])]
        log(f"training data: {paths}")
        for p in paths:
            for rec in read_jsonl(p):
                if "calls" in rec and "turns" in rec:          # an episode result: its calls, if it passes now
                    if F.check(rec)["strict"]:
                        examples += list(build.examples(rec, rec.get("source")))
                else:
                    examples.append(rec)
        # Only teacher episodes train (source "teacher:<open-weights model>"). Claude-written text (samples, worked
        # examples, CLI test episodes) and template gold are format/checker tests only.
        bad = [e for e in examples if not str(e.get("source", "")).startswith("teacher:")]
        examples = [e for e in examples if str(e.get("source", "")).startswith("teacher:")]
        if bad:
            log(f"dropped {len(bad)} examples that aren't from the open-weights teacher")
        held = [e for e in examples if e.get("family") in F.HELD_OUT]
        examples = [e for e in examples if e.get("family") not in F.HELD_OUT]      # held-out types never train
        if held:
            log(f"dropped {len(held)} examples of held-out types")
        random.Random(0).shuffle(examples)
        if args.limit:
            examples = examples[:args.limit]
        log(f"{len(examples)} training examples: {dict(collections.Counter(e['family'] for e in examples))}")
        last_cost = None
        for bi, b in enumerate(bases):
            if args.budget_minutes and last_cost:
                left = args.budget_minutes - (time.time() - t_main) / 60
                if left < last_cost * 1.3 + (15 if args.export else 3):
                    notes.append(f"- `{b}` skipped: {left:.0f} min left in the job's budget, the last base took {last_cost:.0f} min.")
                    log(notes[-1])
                    continue
            t_b = time.time()
            md = str(Path("models") / b)
            mins = train(b, examples, md, epochs=args.epochs, lr=args.lr)
            notes.append(f"- `{b}` ({BASES[b]}): trained {args.epochs} epochs on {len(examples)} examples in {mins:.0f} min.")
            arms[b] = metrics(evaluate(md, eval_eps(), args.work, args.squiggle, b, out, args.eval_minutes))
            json.dump(arms, open(out / "metrics.json", "w"), indent=1)
            write_results(out, arms, notes)
            nxt = bases[bi + 1] if bi + 1 < len(bases) else None
            last_cost = (time.time() - t_b) / 60 * (2.2 if nxt == "lfm25" and b != "lfm25" else 1.0)   # LFM2.5 is ~3x the compute
    best, go = write_results(out, arms, notes)
    log(open(out / "RESULTS.md").read())
    if args.export and best and not best.startswith("untouched"):
        sizes, check = export(str(Path("models") / best), best, out, args.hub_repo, out / "RESULTS.md")
        with open(out / "RESULTS.md", "a") as f:
            f.write(f"\n## Export\n\n`{best}` → " + ", ".join(f"{k} ({v / 1e6:.0f} MB)" for k, v in sizes.items()) +
                    f", uploaded to the private repo `{args.hub_repo}`.\n\n{check}\n")


if __name__ == "__main__":
    main()
