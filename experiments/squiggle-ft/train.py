"""Train candidate small models on the teacher episodes, score them end to end in Squiggle's real harness, write
RESULTS.md with a go/no-go, and (--export) turn the winner into a GGUF wllama 3.8.1 can load.

  python train.py --data train_examples.jsonl.gz --bases gemma3,functiongemma,lfm25 --epochs 2 --out out [--export]
  python train.py --eval-only --bases gemma3 --out out          # just score the untouched model

Training: full fine-tune, loss only on the model's output (thinking + call, or the reply), each base with its own
chat template (what its GGUF carries), micro-batches packed by tokens, AdamW + cosine.
Eval: fresh episodes of the trained task types (other repos, other questions) plus three held-out types, run in
the real harness with phone sampling (backends.HFStudent).
"""
import argparse, collections, gc, gzip, json, math, os, random, re, shutil, subprocess, sys, time
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
    import fnmatch
    from huggingface_hub import snapshot_download
    pats = ["tokenizer*", "special_tokens_map.json", "added_tokens.json", "chat_template.jinja"]
    snap = snapshot_download(BASES[base], allow_patterns=pats)
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    # Only these names: the snapshot folder also holds whatever else was downloaded for the base (model.safetensors,
    # config.json), and copying those would put the untrained weights back over the trained ones.
    for f in Path(snap).iterdir():
        if f.is_file() and any(fnmatch.fnmatch(f.name, p) for p in pats):
            shutil.copy(f, Path(out_dir) / f.name)



def init_think_tokens(model, tok, base):
    """LFM2.5-350M has single tokens for <think> and </think> whose embeddings were never trained: they are identical to
    hundreds of <|reserved_…|> / <|img_…|> rows (cosine 0.99999), so after a few dozen steps the model emits a random
    member of that cluster where <think> belongs (training smoke 4: 1 of 195 calls started with <think>). Such a row
    starts from the mean of the text pieces it stands for ("<", "think", ">"). Trained rows, and tokenizers where
    <think> is plain text (Gemma), are left alone."""
    import torch
    E = model.get_input_embeddings().weight
    O = model.get_output_embeddings().weight
    with torch.no_grad():
        for t, pieces in (("<think>", ["<", "think", ">"]), ("</think>", ["</", "think", ">"])):
            if tok(t, add_special_tokens=False).input_ids != [tok.convert_tokens_to_ids(t)]:
                continue
            i = tok.convert_tokens_to_ids(t)
            twins = int((torch.nn.functional.cosine_similarity(E, E[i][None], dim=1) > 0.999).sum())
            if twins < 10:
                continue
            ids = [x for p in pieces for x in tok(p, add_special_tokens=False).input_ids]
            E[i] = E[ids].mean(0)
            if O.data_ptr() != E.data_ptr():
                O[i] = O[ids].mean(0)
            log(f"[{base}] {t} (id {i}) had an untrained embedding ({twins} identical rows); started it from {tok.convert_ids_to_tokens(ids)}")


def split_dev(examples, frac=0.05, seed=0):
    """Hold out a fraction of whole episodes (never single calls of a training episode) for the dev loss."""
    eps = sorted({str(e.get("episode")) for e in examples})
    random.Random(seed).shuffle(eps)
    dev_eps = set(eps[:max(1, round(len(eps) * frac))]) if len(eps) >= 20 else set()
    return [e for e in examples if str(e.get("episode")) not in dev_eps], [e for e in examples if str(e.get("episode")) in dev_eps]


def train(base, examples, out_dir, epochs=2, lr=4e-5, budget=8192, per_step=32, seed=0, dev_frac=0.05):
    """Full fine-tune, loss on the output only. Each step's loss is normalised by the (weighted) target tokens of the
    whole step, examples carry a weight (duplicate control, see prepare()), and the weights of the epoch with the lowest
    dev loss (5% of episodes, held out) are the ones saved."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    torch.manual_seed(seed)
    rng = random.Random(seed)
    tok = AutoTokenizer.from_pretrained(BASES[base])
    train_ex, dev_ex = split_dev(examples, dev_frac, seed) if dev_frac else (examples, [])

    def rendered(exs):
        out = []
        for ex in exs:
            r = render(tok, ex)
            if r:
                out.append((r[0], r[1], float(ex.get("weight", 1.0))))
        return out
    items, dev_items = rendered(train_ex), rendered(dev_ex)
    log(f"[{base}] {len(items)} of {len(train_ex)} training examples fit (dev: {len(dev_items)} examples from "
        f"{len({e.get('episode') for e in dev_ex})} episodes); target tokens {sum(len(o) for _, o, _ in items)}, "
        f"weighted {sum(len(o) * w for _, o, w in items):.0f}, all tokens {sum(len(p) + len(o) for p, o, _ in items)}")
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    dt = torch.bfloat16 if dev == "cuda" and torch.cuda.is_bf16_supported() else torch.float32
    model = AutoModelForCausalLM.from_pretrained(BASES[base], dtype=torch.float32, attn_implementation="sdpa").to(dev)
    init_think_tokens(model, tok, base)
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    log(f"[{base}] attention {model.config._attn_implementation}, gradient checkpointing {model.is_gradient_checkpointing}")
    model.config.use_cache = False
    head = model.get_output_embeddings()
    softcap = getattr(model.config, "final_logit_softcapping", None)

    def chunk_loss(hc, yc, wc):
        logits = head(hc).float()
        if softcap:
            logits = torch.tanh(logits / softcap) * softcap
        return (torch.nn.functional.cross_entropy(logits, yc, reduction="none") * wc).sum()

    CH = 512 if dev == "cuda" else 64          # positions per logits chunk (CPU tests have little memory)

    def tensors(mb, its):
        L = max(len(its[i][0]) + len(its[i][1]) for i in mb)
        ids = torch.full((len(mb), L), tok.pad_token_id or 0, dtype=torch.long)
        att = torch.zeros((len(mb), L), dtype=torch.long)
        lab = torch.full((len(mb), L), -100, dtype=torch.long)
        wt = torch.zeros((len(mb), L), dtype=torch.float32)
        for r, i in enumerate(mb):
            p, o, w = its[i]
            seq = p + o
            ids[r, :len(seq)] = torch.tensor(seq)
            att[r, :len(seq)] = 1
            lab[r, len(p):len(seq)] = torch.tensor(o)
            wt[r, len(p):len(seq)] = w
        return ids.to(dev), att.to(dev), lab.to(dev), wt.to(dev)

    def mb_loss(mb, its):
        """(weighted loss sum, unweighted token count) of one micro-batch."""
        ids, att, lab, wt = tensors(mb, its)
        with torch.autocast(dev, dtype=dt, enabled=dev == "cuda"):
            hid = model.model(input_ids=ids, attention_mask=att).last_hidden_state
            # Loss only where a target token is predicted. The vocabulary is huge (Gemma: 262k), so logits are made
            # 512 positions at a time and recomputed in the backward pass instead of kept.
            tgt = lab[:, 1:]
            sel = tgt != -100
            h = hid[:, :-1][sel]
            y = tgt[sel]
            w = wt[:, 1:][sel]
            loss = sum(torch.utils.checkpoint.checkpoint(chunk_loss, h[i:i + CH], y[i:i + CH], w[i:i + CH], use_reentrant=False)
                       for i in range(0, h.shape[0], CH))
        return loss, int(sel.sum())

    def dev_loss():
        if not dev_items:
            return None
        model.eval()
        tot = n = 0.0
        with torch.no_grad():
            for mb in batches([(p, o) for p, o, _ in dev_items], budget, random.Random(0)):
                its = [(p, o, 1.0) for p, o, _ in (dev_items[i] for i in mb)]
                l, k = mb_loss(list(range(len(its))), its)
                tot += float(l); n += k
        model.train()
        return tot / max(1, n)
    opt = (torch.optim.SGD(model.parameters(), lr=lr) if os.environ.get("SQFT_SGD")       # tiny-memory local tests only
           else torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.0, betas=(0.9, 0.95), foreach=dev == "cuda"))
    mbs_per_epoch = len(batches([(p, o) for p, o, _ in items], budget, random.Random(0)))
    ex_per_mb = len(items) / max(1, mbs_per_epoch)
    accum = max(1, round(per_step / ex_per_mb))
    total = math.ceil(mbs_per_epoch / accum) * epochs
    warm = max(5, total // 30)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1, (s + 1) / warm) * 0.5 * (1 + math.cos(math.pi * min(1.0, s / total))))
    log(f"[{base}] {mbs_per_epoch} micro-batches/epoch, accum {accum}, {total} steps, warmup {warm}")
    step = 0
    t0 = time.time()
    model.train()
    best_dev, best_ep, dev_hist = None, None, []
    best_dir = str(out_dir) + ".best-epoch"
    for ep in range(epochs):
        mbs = batches([(p, o) for p, o, _ in items], budget, rng)
        run_loss, run_n, ep_loss, ep_n = 0.0, 0, 0.0, 0
        opt.zero_grad(set_to_none=True)
        for k, mb in enumerate(mbs):
            if k % accum == 0:      # the step's weighted target tokens, so every token in the step counts the same
                group = [i for b in mbs[k:k + accum] for i in b]
                denom = max(1e-6, sum(len(items[i][1]) * items[i][2] for i in group))
            loss, n_t = mb_loss(mb, items)
            (loss / denom).backward()
            run_loss += loss.item(); run_n += sum(len(items[i][1]) * items[i][2] for i in mb)
            ep_loss += loss.item(); ep_n += sum(len(items[i][1]) * items[i][2] for i in mb)
            if (k + 1) % accum == 0 or k == len(mbs) - 1:
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                opt.step(); sched.step(); opt.zero_grad(set_to_none=True)
                step += 1
                if step % 20 == 0:
                    log(f"[{base}] epoch {ep + 1} step {step}/{total} loss {run_loss / max(1, run_n):.4f} lr {sched.get_last_lr()[0]:.2e} ({(time.time() - t0) / 60:.1f} min)")
                    run_loss, run_n = 0.0, 0
        d = dev_loss()
        dev_hist.append(d)
        log(f"[{base}] epoch {ep + 1} done: mean loss {ep_loss / max(1, ep_n):.4f}, dev loss "
            f"{'-' if d is None else f'{d:.4f}'} ({(time.time() - t0) / 60:.1f} min)")
        if d is not None and (best_dev is None or d < best_dev):
            best_dev, best_ep = d, ep + 1
            if ep + 1 < epochs:                       # a later epoch could be worse: keep these weights on disk
                from safetensors.torch import save_file
                Path(best_dir).mkdir(parents=True, exist_ok=True)
                seen, state = set(), {}
                for k, v in model.state_dict().items():      # tied weights (embeddings = head) are saved once
                    if v is not None and v.data_ptr() not in seen:
                        seen.add(v.data_ptr())
                        state[k] = v.detach().contiguous().cpu()
                save_file(state, str(Path(best_dir) / "best.safetensors"))
    if best_ep is not None and best_ep < epochs:
        from safetensors.torch import load_file
        missing = model.load_state_dict(load_file(str(Path(best_dir) / "best.safetensors"), device=dev), strict=False).missing_keys
        model.tie_weights()
        if [k for k in missing if "lm_head" not in k]:
            raise RuntimeError(f"best-epoch weights incomplete: {missing[:5]}")
        log(f"[{base}] kept epoch {best_ep} (lowest dev loss {best_dev:.4f}; dev by epoch {['%.4f' % x for x in dev_hist]})")
    shutil.rmtree(best_dir, ignore_errors=True)
    TRAIN_INFO[base] = {"dev_loss": dev_hist, "best_epoch": best_ep or epochs}
    model.config.use_cache = True
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    model.save_pretrained(out_dir, safe_serialization=True)
    copy_tokenizer(base, out_dir)
    del model, opt
    gc.collect()
    if dev == "cuda":
        torch.cuda.empty_cache()
    return (time.time() - t0) / 60


TRAIN_INFO = {}           # base -> {dev_loss per epoch, best_epoch}


def prepare(examples, reuse_cap=0, per_episode_cap=10):
    """The training mix (REVIEW_V2_FABLE D2, E4; audit 6, 7):
    - drop examples that copy an 8-word run from template or Claude-written text (leak.py);
    - in each episode, drop repeated identical find calls, and cap the episode at per_episode_cap examples;
    - cap reused v1 repo-heavy families at reuse_cap episodes each, spread over repos;
    - weight each example 1/sqrt(n) where n counts examples with the same (kind, tool, arguments) signature, so one
      string ("search the web") can't dominate."""
    import leak
    kept, leaked = [], 0
    for e in examples:
        if leak.leaked(e["output"], e.get("messages", ())):
            leaked += 1
        else:
            kept.append(e)
    log(f"leak filter: dropped {leaked} of {len(examples)} examples")
    by_ep = collections.defaultdict(list)
    for e in kept:
        by_ep[str(e.get("episode"))].append(e)
    out, dup_find = [], 0
    for ep, exs in by_ep.items():
        seen, row = set(), []
        for e in exs:
            sig = call_signature(e)
            if sig and sig[1] == "find" and sig in seen:
                dup_find += 1
                continue
            seen.add(sig)
            row.append(e)
        out.append((ep, row[:per_episode_cap] if per_episode_cap and len(row) > per_episode_cap else row))
    if reuse_cap:
        fam_eps = collections.defaultdict(list)
        for ep, row in out:
            fam_eps[row[0]["family"] if row else ""].append((ep, row))
        capped = []
        for fam, lst in fam_eps.items():
            if fam in REUSE_CAP_FAMS and len(lst) > reuse_cap:
                by_repo = collections.defaultdict(list)          # round-robin over repos so the cap keeps variety
                for ep, row in sorted(lst):
                    by_repo[(row[0].get("repo") or "") if row else ""].append((ep, row))
                pick, queues = [], [q for _, q in sorted(by_repo.items())]
                while len(pick) < reuse_cap and any(queues):
                    for q in queues:
                        if q and len(pick) < reuse_cap:
                            pick.append(q.pop(0))
                log(f"reuse cap: {fam} {len(lst)} -> {len(pick)} episodes")
                lst = pick
            capped += lst
        out = capped
    flat = [e for _, row in out for e in row]
    counts = collections.Counter(call_signature(e) for e in flat)
    for e in flat:
        sig = call_signature(e)
        e["weight"] = min(1.0, 1.0 / math.sqrt(counts[sig])) if sig else 1.0
    heavy = [(s, c) for s, c in counts.most_common(5) if s]
    log(f"dedupe: dropped {dup_find} repeated find calls; {len(flat)} examples; most repeated signatures {heavy}")
    return flat


REUSE_CAP_FAMS = {"repo_fact", "repo_where", "repo_two", "recipe_repo", "refs", "need_repo", "memory_repo"}


def call_signature(ex):
    """(kind, tool, arguments) of the example's tool call, or None for a reply."""
    m = re.search(r"```tool_call\s*\n(.*?)\n```", ex.get("output") or "", re.S)
    if not m:
        return None
    try:
        obj = json.loads(m.group(1))
        return (ex.get("kind"), obj.get("name"), json.dumps(obj.get("arguments"), sort_keys=True))
    except Exception:
        return None


# ── eval ────────────────────────────────────────────────────────────────────
GEN_STATS = {}            # label -> the eval student's {calls, too_long, out_tokens}
PHONE_TOK_S = 15          # rough generation speed on a phone CPU, for the seconds-per-call column


def arm(res, label):
    """metrics + output length + three raw generations (first model call of a chat, a web and a repo episode)."""
    m = metrics(res)
    g = GEN_STATS.get(label, {})
    m["gen"] = {"calls": g.get("calls", 0), "out_tokens": g.get("out_tokens", 0),
                "per_call": g.get("out_tokens", 0) / max(1, g.get("calls", 0) - g.get("too_long", 0))}
    picks = []
    for fams in (("chat",), ("web_fact", "web_compare"), ("repo_fact", "repo_where", "repo_two")):
        r = next((r for r in sorted(res, key=lambda r: r["id"]) if r["family"] in fams and r.get("calls")), None)
        if r:
            c = r["calls"][0]
            picks.append({"id": r["id"], "request": r.get("first", ""), "kind": c.get("kind"), "output": (c.get("output") or "")[:1500]})
    m["samples"] = picks
    return m


def evaluate(model_path, episodes, work, squiggle, label, out_dir, minutes=25):
    import torch
    from backends import HFStudent
    from sqrun import Runner
    st = HFStudent(model_path, device="cuda" if torch.cuda.is_available() else "cpu")
    runner = Runner(st, squiggle, work, concurrency=48, batch_wait=0.5, max_calls=30)
    t0 = time.time()
    res = runner.run(episodes)          # no deadline: every model gets every episode (REVIEW D6)
    for r in res:
        r["check"] = F.check(r)
    with gzip.open(Path(out_dir) / f"eval_{label}.jsonl.gz", "wt") as f:
        for r in res:
            f.write(json.dumps({k: r.get(k) for k in ("id", "family", "first", "gold", "meta", "check", "error", "capped")} |
                               {"turns": [{"reply": t.get("reply"), "tools": t.get("tools")} for t in r.get("turns", [])],
                                "outputs": [{"kind": c.get("kind"), "output": c.get("output")} for c in r.get("calls", [])]}, ensure_ascii=False) + "\n")
    log(f"[{label}] eval {len(res)} episodes in {(time.time() - t0) / 60:.1f} min; student {st.stats}")
    GEN_STATS[label] = dict(st.stats)
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
    m["held_ok"] = sum(v["ok"] for f, v in m["families"].items() if f in F.HELD_OUT) / max(1, len(ho))
    # CORPUS_V2 §2h: plain arithmetic through run_js (any family whose task is a computation)
    comp = [r for r in res if r["family"] in COMPUTE_FAMS]
    m["run_js_misuse"] = (sum(1 for r in comp if "run_js" in F.names([x for s in F.turn_calls(r) for x in s])) / len(comp)) if comp else None
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


COMPUTE_FAMS = {"math", "math_pair", "need_math", "hermes_compute", "lookup_then_compute"}


def verdict(m, base_m, base_name="the untouched base"):
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
        # Against the SAME base as released: strict scores and the plain right-answer rates (training must not cost
        # the model answers it already got right).
        better = m["trained_strict"] > base_m["trained_strict"] and m["held_strict"] > base_m["held_strict"]
        checks.append((f"beats {base_name} (strict, trained/held-out)", better,
                       f"{m['trained_strict']:.0%}/{m['held_strict']:.0%} vs {base_m['trained_strict']:.0%}/{base_m['held_strict']:.0%}"))
        ok_better = m["trained_ok"] >= base_m["trained_ok"] and m.get("held_ok", 0) >= base_m.get("held_ok", 0)
        checks.append((f"right answers at least {base_name}'s (trained/held-out)", ok_better,
                       f"{m['trained_ok']:.0%}/{m.get('held_ok', 0):.0%} vs {base_m['trained_ok']:.0%}/{base_m.get('held_ok', 0):.0%}"))
    return all(c[1] for c in checks), checks


def write_results(out, arms, notes):
    names = list(arms)
    tuned = [k for k in names if not k.startswith("untouched") and k not in REFERENCE]
    best = max(tuned, key=lambda k: arms[k]["trained_strict"] + arms[k]["held_strict"]) if tuned else None
    base_key = f"untouched-{best}" if best and f"untouched-{best}" in arms else next((k for k in names if k.startswith("untouched")), None)
    go, checks = verdict(arms[best], arms.get(base_key), f"`{base_key}`") if best else (False, [])
    L = ["# Squiggle small-model fine-tune: results", ""]
    if best:
        L += [f"**Verdict: {'GO' if go else 'NO-GO (not yet)'}** for `{best}`.", ""]
        L += ["| check | pass | value |", "| --- | --- | --- |"] + [f"| {a} | {'yes' if b else 'no'} | {c} |" for a, b, c in checks] + [""]
        for ref in [k for k in names if k in REFERENCE]:     # e.g. the deployed v1: does the new model beat it?
            better, rchecks = verdict(arms[best], arms[ref], f"`{ref}`")
            L += [f"**Against `{ref}`: {'better on every check' if better else 'not better on every check'}.**", "",
                  "| check | pass | value |", "| --- | --- | --- |"] + [f"| {a} | {'yes' if b else 'no'} | {c} |" for a, b, c in rchecks] + [""]
    fams = sorted({f for a in arms.values() for f in a["families"]})
    L += ["## Strict score per task type (right answer and the habit)", "", "| type | habit | " + " | ".join(names) + " |", "| --- | --- |" + " --- |" * len(names)]
    for f in fams:
        L.append(f"| {f}{' (held out)' if f in F.HELD_OUT else ''} | {F.HABIT.get(f, '')} | " + " | ".join(
            f"{arms[a]['families'][f]['strict']:.0%} ({arms[a]['families'][f]['ok']:.0%})" if f in arms[a]["families"] else "-" for a in names) + " |")
    L += ["", "(right answer only in brackets)", "", "## Habits", "", "| measure | " + " | ".join(names) + " |", "| --- |" + " --- |" * len(names)]
    for key, label in [("trained_strict", "trained types, strict mean"), ("trained_ok", "trained types, right answer"), ("held_strict", "held-out types, strict mean"), ("held_ok", "held-out types, right answer"),
                       ("format", "well-formed calls"), ("loops", "episodes looping / call-capped"), ("plans", "plans multi-step requests"),
                       ("asks", "asks (need) when info is missing"), ("chat", "plain chat stays plain"), ("done_facts", "done results carry the answer"),
                       ("clean", "clean requests, strict"), ("messy", "messy requests, strict"), ("run_js_misuse", "arithmetic through run_js")]:
        L.append(f"| {label} | " + " | ".join("-" if arms[a].get(key) is None else f"{arms[a][key]:.0%}" for a in names) + " |")
    # Episodes not started before an arm's eval deadline are skipped (a random tail: the set is shuffled).
    L.append("| episodes evaluated | " + " | ".join(str(sum(v["n"] for v in arms[a]["families"].values())) for a in names) + " |")
    if any("gen" in arms[a] for a in names):
        L += ["", "## Output length", "", f"Generated tokens per model call (thinking + call or reply). Seconds per call at ~{PHONE_TOK_S} tokens/s on a phone CPU.", "",
              "| model | calls | tokens per call | seconds per call |", "| --- | --- | --- | --- |"]
        for a in names:
            g = arms[a].get("gen")
            if g:
                L.append(f"| {a} | {g['calls']} | {g['per_call']:.0f} | {g['per_call'] / PHONE_TOK_S:.0f} |")
    if any(arms[a].get("samples") for a in names):
        L += ["", "## Sample generations", "", "The first model call of three eval episodes per model, raw (as the harness got it).", ""]
        for a in names:
            for x in arms[a].get("samples", []):
                L += [f"**{a}**, `{x['id']}` ({x['kind']}): {x['request'][:200]!r}", "", "````text", x["output"] or "(empty)", "````", ""]
    L += ["", "## Notes", ""] + notes
    (Path(out) / "RESULTS.md").write_text("\n".join(L) + "\n")
    return best, go


# ── export ──────────────────────────────────────────────────────────────────
LLAMA_CPP_COMMIT = "8ca4060b7e30e76baaa5670ee1ec1b760b7f8552"


HUB_PREFIX = ""     # set from --hub-prefix: every upload goes under it
REFERENCE = set()   # --eval-models labels: compared against, never the "best" arm


def upload_weights(model_dir, hub_repo):
    """The trained model in transformers format, to <hub_repo>/hf/, so a failed GGUF export can be redone later."""
    if not (hub_repo and os.environ.get("HF_TOKEN")):
        return False
    from huggingface_hub import HfApi
    api = HfApi(token=os.environ["HF_TOKEN"])
    api.create_repo(hub_repo, private=True, exist_ok=True)
    api.upload_folder(folder_path=model_dir, path_in_repo=HUB_PREFIX + "hf", repo_id=hub_repo)
    log(f"uploaded {model_dir} to {hub_repo}/{HUB_PREFIX}hf")
    return True


def export(model_dir, base, out, hub_repo, results_md):
    """GGUF (Q8_0 and Q4_0) with llama.cpp's converter, a llama.cpp load-and-generate check, upload to a private repo."""
    work = Path(os.environ.get("SQFT_GGUF_DIR", "gguf"))     # outside `out`: the job uploads `out`, and model files don't belong in git
    work.mkdir(parents=True, exist_ok=True)
    lc = Path(os.environ.get("LLAMA_CPP_DIR", "llama.cpp"))
    if not lc.exists():
        # llama.cpp at the commit the export was checked with locally (convert -> Q8_0 -> loads in wllama 3.8.1); a
        # tarball, so the job needs no git.
        import urllib.request
        urllib.request.urlretrieve(f"https://codeload.github.com/ggml-org/llama.cpp/tar.gz/{LLAMA_CPP_COMMIT}", "lc.tgz")
        subprocess.run(f"mkdir -p {lc} && tar xzf lc.tgz -C {lc} --strip-components=1", shell=True, check=True)
    copy_tokenizer(base, model_dir)            # models trained before this fix
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "gguf", "sentencepiece", "protobuf"], check=False)
    env = dict(os.environ, PYTHONPATH=str(lc / "gguf-py"))
    f8 = work / f"squiggle-small-{base}-Q8_0.gguf"
    subprocess.run([sys.executable, str(lc / "convert_hf_to_gguf.py"), model_dir, "--outtype", "q8_0", "--outfile", str(f8)], check=True, env=env)
    files = [f8]
    built = subprocess.run(f"cd {lc} && cmake -B build -DGGML_CUDA=OFF -DLLAMA_CURL=OFF -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=ON -DLLAMA_BUILD_SERVER=OFF >/dev/null "
                           "&& cmake --build build -j 8 --target llama-quantize llama-simple >/dev/null", shell=True).returncode == 0
    check = "llama.cpp build failed: no Q4_0 and no load check"
    if built:
        f16 = work / "f16.gguf"
        subprocess.run([sys.executable, str(lc / "convert_hf_to_gguf.py"), model_dir, "--outtype", "f16", "--outfile", str(f16)], check=True, env=env)
        f4 = work / f"squiggle-small-{base}-Q4_0.gguf"
        r = subprocess.run([str(lc / "build/bin/llama-quantize"), str(f16), str(f4), "Q4_0"], capture_output=True)   # its log has raw vocab bytes
        if r.returncode != 0:
            raise RuntimeError(f"llama-quantize failed: {r.stderr.decode(errors='replace')[-500:]}")
        f16.unlink()
        files.append(f4)
        r = subprocess.run([str(lc / "build/bin/llama-simple"), "-m", str(f8), "-n", "32", "Hello"], capture_output=True, text=True, errors="replace", timeout=300)
        check = f"llama.cpp (master) loads the Q8_0 file and generates: {'yes' if r.returncode == 0 else 'NO'} ({(r.stdout + r.stderr)[-300:]!r})"
    try:                                              # the phone renders with the GGUF's template: must match training's
        import template_check as TC
        check += f"\n\nchat template, GGUF vs the HF template training used: {TC.compare(TC.hf_template(model_dir), TC.gguf_template(str(f8)))}"
    except Exception as e:
        check += f"\n\nchat template check failed to run: {e!r}"
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
            api.upload_file(path_or_fileobj=str(f), path_in_repo=HUB_PREFIX + f.name, repo_id=hub_repo)
        log(f"uploaded to {hub_repo}/{HUB_PREFIX}")
    return sizes, check


# ── main ────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="")
    ap.add_argument("--bases", default="gemma3,functiongemma,lfm25")
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--lr", type=float, default=4e-5)
    ap.add_argument("--lr-per-base", default="lfm25=2e-5", help="per-base learning rates, e.g. lfm25=2e-5,gemma3=4e-5")
    ap.add_argument("--dev-frac", type=float, default=0.05, help="episodes held out for the per-epoch dev loss (best epoch kept)")
    ap.add_argument("--reuse-cap", type=int, default=0, help="at most this many episodes per v1 repo-heavy family (REUSE_CAP_FAMS)")
    ap.add_argument("--limit", type=int, default=0, help="use only this many training examples (smoke test)")
    ap.add_argument("--eval-scale", type=float, default=1.0)
    ap.add_argument("--eval-minutes", type=float, default=25)
    ap.add_argument("--eval-only", action="store_true")
    ap.add_argument("--no-untouched", action="store_true")
    ap.add_argument("--eval-bases", default="", help="also evaluate these bases untouched, as released (e.g. lfm25,functiongemma)")
    ap.add_argument("--eval-plan", default="current", choices=["current", "v1"], help="v1: the 293-episode set squiggle-ft-train used")
    ap.add_argument("--export", action="store_true")
    ap.add_argument("--budget-minutes", type=float, default=0, help="stop starting new bases when what's left can't fit one more (+15 min for export)")
    ap.add_argument("--hub-repo", default="kealjones/squiggle-small")
    ap.add_argument("--hub-prefix", default="", help="folder inside --hub-repo for every upload (e.g. v2/), so a new model never replaces the deployed one")
    ap.add_argument("--eval-models", default="", help="also evaluate trained models as they are: label=owner/repo[/subfolder],... (e.g. v1=kealjones/squiggle-small/hf)")
    ap.add_argument("--work", default=str(HERE / "work"))
    ap.add_argument("--out", default="out")
    ap.add_argument("--squiggle", default=os.environ.get("SQUIGGLE_DIR", str(HERE / "squiggle")))
    ap.add_argument("--export-only", default="", help="base name: GGUF-export the weights an earlier run put in <hub-repo>/hf, and upload")
    ap.add_argument("--results", default="", help="with --export-only: that run's RESULTS.md (for the model card)")
    args = ap.parse_args()
    t_main = time.time()
    global HUB_PREFIX
    HUB_PREFIX = args.hub_prefix.strip("/") + "/" if args.hub_prefix.strip("/") else ""
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if args.export_only:
        from huggingface_hub import snapshot_download
        md = str(Path(snapshot_download(args.hub_repo, allow_patterns=[HUB_PREFIX + "hf/*"], token=os.environ.get("HF_TOKEN"))) / (HUB_PREFIX + "hf"))
        res = out / "RESULTS.md"
        res.write_text(Path(args.results).read_text() if args.results else f"# {args.export_only}\n")
        sizes, check = export(md, args.export_only, out, args.hub_repo, res)
        with open(res, "a") as f:
            f.write(f"\n## Export\n\n`{args.export_only}` → " + ", ".join(f"{k} ({v / 1e6:.0f} MB)" for k, v in sizes.items()) +
                    f", uploaded to the private repo `{args.hub_repo}`.\n\n{check}\n")
        return
    import build
    src = build.load_sources(Path(args.work), "eval")
    eval_plan = build.EVAL_PLAN_V1 if args.eval_plan == "v1" else build.EVAL_PLAN
    eval_eps = lambda: build.make_sets(src, eval_plan, seed=123, scale=args.eval_scale, date_shift=args.eval_plan != "v1")
    log(f"eval set: {len(eval_eps())} episodes")
    arms, notes = {}, []
    bases = [b for b in args.bases.split(",") if b]
    # Every trained base is also evaluated as released (CORPUS_V2 §5.8), plus any --eval-bases.
    untouched = [] if args.no_untouched else (bases if not args.eval_only else [])
    for b in list(dict.fromkeys(untouched + [x for x in args.eval_bases.split(",") if x])):
        label = f"untouched-{b}"
        arms[label] = arm(evaluate(BASES[b], eval_eps(), args.work, args.squiggle, label, out, args.eval_minutes), label)
        json.dump(arms, open(out / "metrics.json", "w"), indent=1)
    for item in [x for x in args.eval_models.split(",") if x]:      # an already trained model, e.g. the deployed v1
        label, ref = item.split("=", 1)
        REFERENCE.add(label)
        parts = ref.split("/")
        from huggingface_hub import snapshot_download
        sub = "/".join(parts[2:])
        path = snapshot_download("/".join(parts[:2]), allow_patterns=[f"{sub}/*"] if sub else None, token=os.environ.get("HF_TOKEN"))
        arms[label] = arm(evaluate(str(Path(path) / sub) if sub else path, eval_eps(), args.work, args.squiggle, label, out, args.eval_minutes), label)
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
        examples = prepare(examples, reuse_cap=args.reuse_cap)
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
            lrs = dict(x.split("=") for x in args.lr_per_base.split(",") if "=" in x)
            lr = float(lrs.get(b, args.lr))
            mins = train(b, examples, md, epochs=args.epochs, lr=lr, dev_frac=args.dev_frac)
            info = TRAIN_INFO.get(b, {})
            notes.append(f"- `{b}` ({BASES[b]}): lr {lr:g}, up to {args.epochs} epochs on {len(examples)} examples in {mins:.0f} min; "
                         f"dev loss by epoch {[round(x, 4) for x in info.get('dev_loss', []) if x is not None]}, kept epoch {info.get('best_epoch')}.")
            arms[b] = arm(evaluate(md, eval_eps(), args.work, args.squiggle, b, out, args.eval_minutes), b)
            json.dump(arms, open(out / "metrics.json", "w"), indent=1)
            write_results(out, arms, notes)
            nxt = bases[bi + 1] if bi + 1 < len(bases) else None
            last_cost = (time.time() - t_b) / 60 * (2.2 if nxt == "lfm25" and b != "lfm25" else 1.0)   # LFM2.5 is ~3x the compute
    best, go = write_results(out, arms, notes)
    log(open(out / "RESULTS.md").read())
    if args.export and not (best in bases and Path("models", best).exists()):
        # the deployed v1 (or an untouched base) scored best: export the best trained base anyway, for comparison
        trained = [b for b in bases if Path("models", b).exists()]
        if best and trained:
            log(f"best arm is {best}; exporting {trained[0]} anyway (under {HUB_PREFIX or 'the repo root'})")
        best = trained[0] if trained else None
    if args.export and best and not best.startswith("untouched"):
        md = str(Path("models") / best)
        try:
            saved = upload_weights(md, args.hub_repo)
        except Exception as e:                        # the GGUF export still runs; RESULTS.md says what happened
            saved = False
            log(f"weights upload failed: {e!r}")
        try:
            sizes, check = export(md, best, out, args.hub_repo, out / "RESULTS.md")
            where = f", uploaded to the private repo `{args.hub_repo}`" if args.hub_repo else " (not uploaded: smoke)"
            text = f"`{best}` → " + ", ".join(f"{k} ({v / 1e6:.0f} MB)" for k, v in sizes.items()) + f"{where}.\n\n{check}"
        except Exception as e:
            import traceback
            traceback.print_exc()
            text = f"GGUF export of `{best}` failed: {e!r}." + (f" The trained weights are in `{args.hub_repo}/hf`." if saved else "")
        if saved:
            text += f"\n\nTransformers weights: `{args.hub_repo}/hf`."
        with open(out / "RESULTS.md", "a") as f:
            f.write(f"\n## Export\n\n{text}\n")


if __name__ == "__main__":
    main()
