"""Tiny Gemma 4, stage 1: how much does Gemma 4 E2B lose when it's cut, before any healing?

Measures, all in bits per byte (bpb: fair across tokenizers), on held-out FineWeb-Edu, code and
Squiggle-harness text (Gemma-written teacher episodes):

  1. vocab:  keep ~VOCAB_TARGET tokens chosen from public text (FineWeb-Edu + code + Squiggle prompts),
             closed under BPE merges (every piece a kept token is built from is kept), plus bytes and
             special tokens. Evaluated exactly: the pruned tokenizer's ids map back to the original
             rows, and the softmax runs over kept rows only (= a model with those rows removed;
             Gemma's input and output embeddings are tied).
  2. depth:  angular distance between each layer's input and output; skip the layers that change
             the residual least (a skipped layer passes its input through). Layer 0, the last layer
             and the two layers whose keys/values the KV-shared layers reuse are never skipped.
  3. width:  FFN channel importance = mean |activation| x |down_proj column|; keep the top fraction
             in every layer.
  4. baselines: LFM2.5-350M (Squiggle Small's base) and Qwen3-0.6B on the same text.

No hidden-size cut (1536 -> 1024) yet: that's real surgery, for stage 2 if this looks promising.

  python stage1.py OUT_DIR        env: MODEL, VOCAB_TARGET, COUNT_DOCS, EVAL_DOCS, QUICK
"""
import gzip, json, math, os, sys, time, random, collections
import torch
import torch.nn.functional as F

OUT = sys.argv[1] if len(sys.argv) > 1 else "out"
os.makedirs(OUT, exist_ok=True)
MODEL = os.environ.get("MODEL", "google/gemma-4-E2B-it")
VOCAB_TARGET = int(os.environ.get("VOCAB_TARGET", 80000))
COUNT_DOCS = int(os.environ.get("COUNT_DOCS", 40000))      # FineWeb-Edu docs for counting tokens
CODE_DOCS = int(os.environ.get("CODE_DOCS", 6000))
EVAL_DOCS = int(os.environ.get("EVAL_DOCS", 200))          # held-out FineWeb-Edu docs for bpb
EVAL_CODE = int(os.environ.get("EVAL_CODE", 60))
EVAL_AGENT = int(os.environ.get("EVAL_AGENT", 80))
CAL_DOCS = int(os.environ.get("CAL_DOCS", 96))             # calibration for layer/channel scores
MAX_CHARS = int(os.environ.get("MAX_CHARS", 3000))
BASELINES = os.environ.get("BASELINES", "LiquidAI/LFM2.5-350M,Qwen/Qwen3-0.6B").split(",")
AGENT_FILE = os.environ.get("AGENT_FILE", "teacher_results.jsonl.gz")
DEV = "cuda" if torch.cuda.is_available() else "cpu"
DTYPE = torch.bfloat16 if DEV == "cuda" else torch.float32
T0 = time.time()
results = {"model": MODEL, "vocab_target": VOCAB_TARGET, "configs": {}, "notes": []}


def log(*a):
    print(f"[{(time.time() - T0) / 60:5.1f} min]", *a, flush=True)


def save():
    json.dump(results, open(os.path.join(OUT, "results.json"), "w"), indent=1)


# ── Data ─────────────────────────────────────────────────────────────────────

def stream(name, config=None, field="text", n=1000, skip=0):
    from datasets import load_dataset
    try:
        ds = load_dataset(name, config, split="train", streaming=True)
        out = []
        for i, row in enumerate(ds):
            if i < skip:
                continue
            t = row.get(field) or ""
            if t.strip():
                out.append(t)
            if len(out) >= n:
                break
        log(f"{name}: {len(out)} docs")
        return out
    except Exception as e:
        log(f"could not read {name}: {e!r}")
        results["notes"].append(f"dataset {name} unavailable: {e!r}"[:300])
        return []


def agent_texts():
    """Squiggle-harness prompts with Gemma 4's replies (teacher pilot; Gemma output, Apache-2.0)."""
    if not os.path.exists(AGENT_FILE):
        log("no agent file", AGENT_FILE)
        return []
    out = []
    for line in gzip.open(AGENT_FILE, "rt"):
        r = json.loads(line)
        for c in r.get("calls") or []:
            msgs = c.get("messages") or []
            text = "\n\n".join(str(m.get("content", "")) for m in msgs if m.get("content")) + "\n\n" + str(c.get("output") or "")
            if len(text) > 200:
                out.append(text)
    random.Random(0).shuffle(out)
    log(f"agent texts: {len(out)}")
    return out


# ── Vocabulary ───────────────────────────────────────────────────────────────

def choose_vocab(tok_json, hf_tok, count_texts, must_texts):
    vocab = tok_json["model"]["vocab"]                 # piece -> id
    id2piece = {i: p for p, i in vocab.items()}
    merges = [tuple(m) if isinstance(m, list) else tuple(m.split(" ")) for m in tok_json["model"]["merges"]]
    producers = collections.defaultdict(list)
    for a, b in merges:
        producers[a + b].append((a, b))
    counts = collections.Counter()
    for i in range(0, len(count_texts), 256):
        for ids in hf_tok(count_texts[i:i + 256], add_special_tokens=False)["input_ids"]:
            counts.update(ids)
    must = set()
    for i in range(0, len(must_texts), 256):
        for ids in hf_tok(must_texts[i:i + 256], add_special_tokens=False)["input_ids"]:
            must.update(ids)
    base = {a["id"] for a in tok_json["added_tokens"]} | {i for p, i in vocab.items() if p.startswith("<0x") and len(p) == 6}
    base |= {i for p, i in vocab.items() if p.startswith("<") and p.endswith(">") and i < 300}   # control pieces
    base |= must
    ranked = [i for i, _ in counts.most_common()]

    def closure(ids):
        keep = set(ids)
        work = [id2piece[i] for i in keep if i in id2piece]
        while work:
            p = work.pop()
            for a, b in producers.get(p, ()):
                for q in (a, b):
                    j = vocab.get(q)
                    if j is not None and j not in keep:
                        keep.add(j); work.append(q)
        return keep

    lo, hi, best = 1000, len(ranked), None
    while lo <= hi:                                     # largest top-n whose closure fits the target
        mid = (lo + hi) // 2
        k = closure(base | set(ranked[:mid]))
        if len(k) <= VOCAB_TARGET:
            best, lo = (mid, k), mid + 1
        else:
            hi = mid - 1
    n, keep = best or (0, closure(base))
    total = sum(counts.values())
    covered = sum(c for i, c in counts.items() if i in keep)
    info = {"kept": len(keep), "top_n": n, "counted_tokens": total, "distinct_seen": len(counts),
            "must_keep_from_squiggle": len(must), "count_coverage": round(covered / max(1, total), 6),
            "min_count_kept": counts[ranked[n - 1]] if n else None}
    log("vocab", info)
    return sorted(keep), info


def prune_tokenizer(tok_json, keep_ids):
    from tokenizers import Tokenizer
    keep = set(keep_ids)
    t = json.loads(json.dumps(tok_json))
    old = t["model"]["vocab"]
    new_vocab, new2old = {}, []
    for piece, i in sorted(old.items(), key=lambda x: x[1]):
        if i in keep:
            new_vocab[piece] = len(new2old); new2old.append(i)
    old2new = {o: n for n, o in enumerate(new2old)}
    t["model"]["vocab"] = new_vocab
    ms = t["model"]["merges"]
    t["model"]["merges"] = [m for m in ms if all(p in new_vocab for p in (m if isinstance(m, list) else m.split(" ")))
                            and ("".join(m) if isinstance(m, list) else m.replace(" ", "")) in new_vocab]
    for a in t["added_tokens"]:
        a["id"] = old2new[a["id"]]
    # Post-processor templates refer to special tokens by id.
    def fix(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "ids" and isinstance(v, list):
                    o[k] = [old2new.get(x, x) for x in v]
                else:
                    fix(v)
        elif isinstance(o, list):
            for v in o:
                fix(v)
    fix(t.get("post_processor"))
    return Tokenizer.from_str(json.dumps(t)), new2old, t


# ── Gemma 4 with skips, channel masks and a restricted softmax ───────────────

def load_gemma():
    from transformers import AutoModelForImageTextToText, AutoModelForCausalLM
    try:
        m = AutoModelForImageTextToText.from_pretrained(MODEL, dtype=DTYPE)
        text, head = m.model.language_model, m.get_output_embeddings()
    except Exception as e:
        log("image-text-to-text load failed, trying causal LM:", repr(e)[:200])
        m = AutoModelForCausalLM.from_pretrained(MODEL, dtype=DTYPE)
        text, head = m.model, m.get_output_embeddings()
    m.to(DEV).eval()
    for p in m.parameters():
        p.requires_grad_(False)
    return m, text, head


class Surgery:
    def __init__(self, text):
        self.text = text
        self.cfg = text.config
        self.layers = list(text.layers)
        self.orig_fwd = [l.forward for l in self.layers]
        self.masks = [None] * len(self.layers)
        self.hooks = []
        for i, l in enumerate(self.layers):
            self.hooks.append(l.mlp.down_proj.register_forward_pre_hook(self._mask_hook(i)))

    def _mask_hook(self, i):
        def hook(mod, args):
            m = self.masks[i]
            return (args[0] * m,) if m is not None else None
        return hook

    def protected(self):
        L = self.cfg.num_hidden_layers
        first_shared = L - (getattr(self.cfg, "num_kv_shared_layers", 0) or 0)
        prev = self.cfg.layer_types[:first_shared]
        keep = {0, L - 1}
        for t in set(prev):
            keep.add(len(prev) - 1 - prev[::-1].index(t))
        return keep

    def set(self, skip=(), masks=None):
        for i, l in enumerate(self.layers):
            l.forward = (lambda h, *a, **k: h) if i in skip else self.orig_fwd[i]
        self.masks = masks or [None] * len(self.layers)


@torch.no_grad()
def nll_gemma(text_model, head, ids, kept_old=None, softcap=None):
    """Sum of next-token NLL (nats) for one sequence of ORIGINAL ids. kept_old: restrict the softmax."""
    x = torch.tensor([ids], device=DEV)
    h = text_model(input_ids=x).last_hidden_state[0, :-1]
    W = head.weight if kept_old is None else head.weight[kept_old]
    logits = (h @ W.T).float()
    if softcap:
        logits = torch.tanh(logits / softcap) * softcap
    tgt = torch.tensor(ids[1:], device=DEV)
    if kept_old is not None:
        tgt = kept_index[tgt]
    return F.cross_entropy(logits, tgt, reduction="sum").item()


kept_index = None


def bpb_gemma(text_model, head, encode, docs, kept_old=None, softcap=None):
    nats = byts = 0
    for d in docs:
        ids = encode(d)
        if len(ids) < 2:
            continue
        nats += nll_gemma(text_model, head, ids, kept_old, softcap)
        byts += len(d.encode("utf-8"))
    return nats / math.log(2) / max(1, byts)


@torch.no_grad()
def bpb_hf(name, docs):
    from transformers import AutoModelForCausalLM, AutoTokenizer
    try:
        tok = AutoTokenizer.from_pretrained(name)
        m = AutoModelForCausalLM.from_pretrained(name, dtype=DTYPE).to(DEV).eval()
    except Exception as e:
        log(f"baseline {name} failed: {e!r}")
        return None
    nats = byts = 0
    bos = [tok.bos_token_id] if tok.bos_token_id is not None else []
    for d in docs:
        ids = bos + tok(d, add_special_tokens=False)["input_ids"]
        if len(ids) < 2:
            continue
        x = torch.tensor([ids], device=DEV)
        logits = m(input_ids=x).logits[0, :-1].float()
        nats += F.cross_entropy(logits, x[0, 1:], reduction="sum").item()
        byts += len(d.encode("utf-8"))
    n = sum(p.numel() for p in m.parameters())
    del m
    torch.cuda.empty_cache() if DEV == "cuda" else None
    return nats / math.log(2) / max(1, byts), n


# ── Scores ───────────────────────────────────────────────────────────────────

@torch.no_grad()
def layer_scores(text_model, encode, docs):
    """Mean angular distance (0..1) between each layer's input and output."""
    L = len(text_model.layers)
    acc = torch.zeros(L, device=DEV); n = 0
    ins = [None] * L
    hooks = []
    for i, l in enumerate(text_model.layers):
        hooks.append(l.register_forward_pre_hook(lambda m, a, k=None, i=i: ins.__setitem__(i, a[0]), with_kwargs=False))
        def post(m, a, out, i=i):
            o = out[0] if isinstance(out, tuple) else out
            c = F.cosine_similarity(ins[i].float(), o.float(), dim=-1).clamp(-1, 1)
            acc[i] += (torch.arccos(c) / math.pi).mean()
        hooks.append(l.register_forward_hook(post))
    for d in docs:
        text_model(input_ids=torch.tensor([encode(d)], device=DEV)); n += 1
    for h in hooks:
        h.remove()
    return (acc / max(1, n)).tolist()


@torch.no_grad()
def channel_scores(text_model, encode, docs):
    L = len(text_model.layers)
    sums = [None] * L
    hooks = []
    for i, l in enumerate(text_model.layers):
        def pre(m, a, i=i):
            v = a[0].float().abs().reshape(-1, a[0].shape[-1]).sum(0)
            sums[i] = v if sums[i] is None else sums[i] + v
        hooks.append(l.mlp.down_proj.register_forward_pre_hook(pre))
    for d in docs:
        text_model(input_ids=torch.tensor([encode(d)], device=DEV))
    for h in hooks:
        h.remove()
    return [s * l.mlp.down_proj.weight.float().norm(dim=0) for s, l in zip(sums, text_model.layers)]


def masks_for(scores, frac):
    out = []
    for s in scores:
        k = max(1, int(round(len(s) * frac)))
        m = torch.zeros_like(s)
        m[s.topk(k).indices] = 1
        out.append(m.to(DTYPE))
    return out


def body_params(text_model, skip, frac, vocab_n):
    """Parameters if this config were physically cut (body + main embedding + PLE)."""
    cfg = text_model.config
    body = 0
    for i, l in enumerate(text_model.layers):
        if i in skip:
            continue
        for name, p in l.named_parameters():
            if ".mlp." in f".{name}" and frac < 1:
                body += int(p.numel() * frac)
            else:
                body += p.numel()
    kept_layers = len(text_model.layers) - len(skip)
    emb = vocab_n * cfg.hidden_size
    ple = vocab_n * kept_layers * (cfg.hidden_size_per_layer_input or 0)
    proj = cfg.hidden_size * kept_layers * (cfg.hidden_size_per_layer_input or 0)
    return {"body": body + proj, "embedding": emb, "ple": ple, "total": body + proj + emb + ple}


# ── Samples ──────────────────────────────────────────────────────────────────

PROMPTS = [
    "What is the capital of France? Answer in one sentence.",
    "Write a Python function that reverses a string.",
    "Explain why the sky is blue in two sentences.",
]


@torch.no_grad()
def sample(text_model, head, encode_raw, decode, chat_text, kept_old, softcap, n=48):
    outs = []
    for p in PROMPTS:
        ids = encode_raw(chat_text(p))
        gen = []
        for _ in range(n):
            x = torch.tensor([ids + gen], device=DEV)
            h = text_model(input_ids=x).last_hidden_state[0, -1]
            W = head.weight if kept_old is None else head.weight[kept_old]
            lg = (h @ W.T).float()
            j = int(lg.argmax())
            tok_old = j if kept_old is None else int(kept_old[j])
            gen.append(tok_old)
            if tok_old in STOP:
                break
        outs.append({"prompt": p, "reply": decode(gen)})
    return outs


STOP = set()


def main():
    global kept_index, STOP
    from transformers import AutoTokenizer
    from huggingface_hub import hf_hub_download
    tok = AutoTokenizer.from_pretrained(MODEL)
    tok_json = json.load(open(os.path.join(MODEL, "tokenizer.json") if os.path.isdir(MODEL) else hf_hub_download(MODEL, "tokenizer.json")))
    STOP = {i for i in [tok.eos_token_id, tok.convert_tokens_to_ids("<end_of_turn>"), tok.convert_tokens_to_ids("<turn|>")] if isinstance(i, int) and i >= 0}

    # Data: separate docs for counting, calibration and evaluation.
    web = stream("HuggingFaceFW/fineweb-edu", "sample-10BT", "text", COUNT_DOCS + CAL_DOCS + EVAL_DOCS)
    code = stream("codeparrot/codeparrot-clean-valid", None, "content", CODE_DOCS + EVAL_CODE + 16)
    agent = agent_texts()
    cut = lambda s: s[:MAX_CHARS]
    web_count, web_cal, web_eval = web[:COUNT_DOCS], web[COUNT_DOCS:COUNT_DOCS + CAL_DOCS], web[COUNT_DOCS + CAL_DOCS:]
    code_count, code_eval = code[:CODE_DOCS], code[CODE_DOCS:CODE_DOCS + EVAL_CODE]
    agent_must, agent_eval = agent[EVAL_AGENT:], agent[:EVAL_AGENT]
    evals = {"web": [cut(d) for d in web_eval], "code": [cut(d) for d in code_eval], "agent": [cut(d) for d in agent_eval]}
    evals = {k: v for k, v in evals.items() if v}
    cal = [cut(d) for d in web_cal] + [cut(d) for d in agent_must[:CAL_DOCS // 3]]
    results["data"] = {k: len(v) for k, v in evals.items()} | {"calibration": len(cal), "count_docs": len(web_count) + len(code_count)}

    # 1. Vocabulary.
    template = tok.apply_chat_template([{"role": "user", "content": "hi"}], tokenize=False, add_generation_prompt=True)
    keep_ids, vinfo = choose_vocab(tok_json, tok, [cut(d) for d in web_count + code_count], agent_must + [template])
    results["vocab"] = vinfo
    ptok, new2old, ptok_json = prune_tokenizer(tok_json, keep_ids)
    json.dump(ptok_json, open(os.path.join(OUT, "tokenizer_pruned.json"), "w"))
    json.dump(keep_ids, open(os.path.join(OUT, "kept_ids.json"), "w"))
    bos = tok.bos_token_id
    enc_full = lambda s: [bos] + tok(s, add_special_tokens=False)["input_ids"]
    enc_pruned = lambda s: [bos] + [new2old[i] for i in ptok.encode(s, add_special_tokens=False).ids]
    enc_raw_full = lambda s: tok(s, add_special_tokens=False)["input_ids"]
    enc_raw_pruned = lambda s: [new2old[i] for i in ptok.encode(s, add_special_tokens=False).ids]
    old2new = {o: n for n, o in enumerate(new2old)}
    # Token cost of the pruned tokenizer (more tokens per text = slower on the phone).
    for k, docs in evals.items():
        a = sum(len(enc_full(d)) for d in docs); b = sum(len(enc_pruned(d)) for d in docs)
        results["vocab"][f"tokens_{k}"] = {"full": a, "pruned": b, "ratio": round(b / max(1, a), 4)}
    save()

    # 2. Model.
    m, text_model, head = load_gemma()
    softcap = getattr(text_model.config, "final_logit_softcapping", None)
    kept_old = torch.tensor(new2old, device=DEV)
    kept_index = torch.full((head.weight.shape[0],), -1, dtype=torch.long, device=DEV)
    kept_index[kept_old] = torch.arange(len(new2old), device=DEV)
    S = Surgery(text_model)
    chat = lambda p: tok.apply_chat_template([{"role": "user", "content": p}], tokenize=False, add_generation_prompt=True)
    dec = lambda ids: tok.decode(ids, skip_special_tokens=True)
    results["protected_layers"] = sorted(S.protected())
    log("loaded; protected layers", results["protected_layers"])

    def run(name, skip=(), frac=1.0, pruned=True, scores=None):
        S.set(set(skip), masks_for(scores, frac) if frac < 1 else None)
        enc = enc_pruned if pruned else enc_full
        r = {k: round(bpb_gemma(text_model, head, enc, docs, kept_old if pruned else None, softcap), 4) for k, docs in evals.items()}
        r["skip"] = sorted(skip); r["ffn_keep"] = frac
        r["params"] = body_params(text_model, set(skip), frac, len(new2old) if pruned else head.weight.shape[0])
        r["samples"] = sample(text_model, head, enc_raw_pruned if pruned else enc_raw_full, dec, chat, kept_old if pruned else None, softcap)
        results["configs"][name] = r
        log(name, {k: v for k, v in r.items() if k not in ("samples", "params")}, f"total {r['params']['total'] / 1e6:.0f}M")
        save()

    run("full", pruned=False)
    run("vocab")

    # 3. Depth.
    S.set()
    ls = layer_scores(text_model, enc_pruned, cal)
    results["layer_scores"] = [round(x, 4) for x in ls]
    prot = S.protected()
    order = [i for i in sorted(range(len(ls)), key=lambda i: ls[i]) if i not in prot]
    log("layer scores (least change first)", [(i, round(ls[i], 3)) for i in order[:20]])
    # 4. Width.
    cs = channel_scores(text_model, enc_pruned, cal)
    save()

    for k in [int(x) for x in os.environ.get("SKIPS", "6,10,14,17").split(",")]:
        run(f"vocab+skip{k}", skip=order[:k])
    for f in [float(x) for x in os.environ.get("FFN", "0.66,0.42").split(",")]:
        run(f"vocab+ffn{f}", frac=f, scores=cs)
    run("vocab+skip17+ffn0.42", skip=order[:17], frac=0.42, scores=cs)
    run("vocab+skip10+ffn0.66", skip=order[:10], frac=0.66, scores=cs)

    # 5. Baselines (their own tokenizers; bpb is comparable).
    del m, text_model, head, S
    if DEV == "cuda":
        torch.cuda.empty_cache()
    results["baselines"] = {}
    for b in [x for x in BASELINES if x]:
        r = {}
        for k, docs in evals.items():
            v = bpb_hf(b, docs)
            if v is None:
                break
            r[k] = round(v[0], 4); r["params"] = v[1]
        results["baselines"][b] = r
        log("baseline", b, r)
        save()

    write_md()
    log("done")


def write_md():
    R = results
    keys = [k for k in ("web", "code", "agent") if k in R.get("data", {})]
    lines = ["# Tiny Gemma 4, stage 1 (no healing)", "",
             f"Model {R['model']}. Bits per byte, lower is better; fair across tokenizers.", "",
             "| config | " + " | ".join(keys) + " | params (body / total) |", "|---" * (len(keys) + 2) + "|"]
    for name, r in R["configs"].items():
        p = r["params"]
        lines.append(f"| {name} | " + " | ".join(str(r.get(k)) for k in keys) + f" | {p['body'] / 1e6:.0f}M / {p['total'] / 1e6:.0f}M |")
    for name, r in R.get("baselines", {}).items():
        lines.append(f"| {name} | " + " | ".join(str(r.get(k)) for k in keys) + f" | {r.get('params', 0) / 1e6:.0f}M |")
    v = R.get("vocab", {})
    lines += ["", f"Vocab: kept {v.get('kept')} tokens (coverage of counted text {v.get('count_coverage')}); "
              + ", ".join(f"{k}: {x['ratio']}x tokens" for k, x in v.items() if k.startswith("tokens_")), "",
              f"Protected layers: {R.get('protected_layers')}. Layer scores: {R.get('layer_scores')}", "", "## Samples", ""]
    for name, r in R["configs"].items():
        lines.append(f"### {name}")
        for s in r["samples"]:
            lines.append(f"- **{s['prompt']}** → {s['reply'][:300]!r}")
        lines.append("")
    if R["notes"]:
        lines += ["## Notes", *[f"- {n}" for n in R["notes"]]]
    open(os.path.join(OUT, "RESULTS.md"), "w").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    code = 0
    try:
        main()
    except BaseException:
        import traceback
        traceback.print_exc()
        code = 1
    finally:
        save()
        try:
            write_md()
        except Exception as e:
            print("write_md failed", e)
    # Exit hard: streaming-dataset threads can keep a crashed job alive until its time limit.
    sys.stdout.flush(); sys.stderr.flush()
    os._exit(code)
