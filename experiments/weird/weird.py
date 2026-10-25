# %% [markdown]
# # Weird maths in a transformer: what happens?
#
# A small GPT (nanoGPT-style, GPT-2 tokenizer) trained on FineWeb-Edu, the standard small-model corpus. Each variant
# sticks one odd function in front of or behind attention or the MLP, or between blocks. Everything else is identical:
# the same data in the same order, steps, optimiser and seed. The baseline runs with three seeds, so we know how big the noise is.
#
# Standard tests for every variant: FineWeb-Edu validation loss, WikiText-2 perplexity (held-out text from
# another source), BLiMP (67 grammar tests), and HellaSwag (common sense; near chance at this size, reported anyway),
# plus speed and whether training blew up.
#
# On Kaggle: GPU T4, internet on. Roughly 3 hours. Results: WEIRD_RESULTS.md.

# %%
import json, math, os, random, statistics as st, sys, time
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
import torch
import torch.nn as nn
import torch.nn.functional as F

QUICK = "--quick" in sys.argv
DEV = "cuda" if torch.cuda.is_available() else "cpu"
if QUICK:
    D, LAYERS, HEADS, CTX, BATCH, STEPS, TRAIN_TOK, VAL_TOK = 128, 2, 4, 128, 8, 30, 400_000, 50_000
    BLIMP_N, HS_N, VARIANTS_LIMIT = 10, 20, None   # every variant, a few steps each
else:
    D, LAYERS, HEADS, CTX, BATCH, STEPS, TRAIN_TOK, VAL_TOK = 384, 6, 6, 512, 16, 4000, 60_000_000, 1_000_000
    BLIMP_N, HS_N, VARIANTS_LIMIT = 100, 1000, None
LR, WARMUP = 1.5e-3, 200
T0 = time.time()


def log(*a):
    print(f"[{(time.time() - T0) / 60:6.1f} min]", *a, flush=True)


# %% [markdown]
# ## Data: FineWeb-Edu, GPT-2 tokens (tokenised once, shared by every variant)

# %%
from transformers import AutoTokenizer
from datasets import load_dataset

tok = AutoTokenizer.from_pretrained("gpt2")
EOT = tok.eos_token_id
V = 50304                                     # 50257 rounded up for speed, as in nanoGPT


def fineweb_tokens(n):
    ds = load_dataset("HuggingFaceFW/fineweb-edu", name="sample-10BT", split="train", streaming=True)
    import numpy as np
    buf, total, out = [], 0, []
    for r in ds:
        buf.append(r["text"])
        if len(buf) == 1024:
            for ids in tok(buf, add_special_tokens=False)["input_ids"]:
                out.append(np.asarray(ids + [EOT], dtype=np.int32)); total += len(ids) + 1
            buf = []
            if total >= n:
                break
    return torch.from_numpy(np.concatenate(out)[:n])


log("tokenising FineWeb-Edu")
ALL = fineweb_tokens(TRAIN_TOK + VAL_TOK)
TRAIN, VAL = ALL[:TRAIN_TOK], ALL[TRAIN_TOK:]
log(f"train {len(TRAIN)/1e6:.1f}M tokens, val {len(VAL)/1e6:.2f}M (tokens per variant: {STEPS*BATCH*CTX/1e6:.0f}M)")
g = torch.Generator().manual_seed(0)
ORDER = torch.randint(0, len(TRAIN) - CTX - 1, (STEPS, BATCH), generator=g)   # same batches for every variant


def batch_at(step):
    idx = ORDER[step][:, None] + torch.arange(CTX + 1)
    b = TRAIN[idx].long()
    return b[:, :-1].to(DEV, non_blocking=True), b[:, 1:].to(DEV, non_blocking=True)


# %% [markdown]
# ## The weird bits
#
# Each is a small module applied at one spot. "Known" marks ideas that exist in the literature in some form; the
# rest are, as far as I know, untried in this exact form.

# %%
class Fn(nn.Module):
    def __init__(self, f, name):
        super().__init__(); self.f, self.name = f, name

    def forward(self, x):
        return self.f(x)


class Poly(nn.Module):                     # learned per-channel cubic, starts as identity
    def __init__(self):
        super().__init__(); self.a = nn.Parameter(torch.ones(D)); self.b = nn.Parameter(torch.zeros(D)); self.c = nn.Parameter(torch.zeros(D))

    def forward(self, x):
        return self.a * x + self.b * x * x + self.c * x * x * x


class Power(nn.Module):                    # sign(x)|x|^p with a learned exponent per channel, starts at p = 1
    def __init__(self):
        super().__init__(); self.p = nn.Parameter(torch.zeros(D))

    def forward(self, x):
        p = 1 + 0.5 * torch.tanh(self.p)   # p stays in (0.5, 1.5)
        return torch.sign(x) * (x.abs() + 1e-4) ** p


class Rotate(nn.Module):                   # a fixed random rotation of the residual stream (not learned)
    def __init__(self, seed):
        super().__init__()
        q, _ = torch.linalg.qr(torch.randn(D, D, generator=torch.Generator().manual_seed(seed)))
        self.register_buffer("q", q)

    def forward(self, x):
        return x @ self.q


class Fourier(nn.Module):                  # add sin of a fixed random projection
    def __init__(self, seed):
        super().__init__()
        self.register_buffer("w", torch.randn(D, D, generator=torch.Generator().manual_seed(seed)) / math.sqrt(D))

    def forward(self, x):
        return x + 0.1 * torch.sin(x @ self.w)


def cummean(x):                             # causal running mean over the sequence
    return x.cumsum(1) / torch.arange(1, x.shape[1] + 1, device=x.device)[None, :, None]


def round_ste(x, step=0.1):                 # round in the forward pass, identity gradient
    return x + (torch.round(x / step) * step - x).detach()


def dither(x):
    return x + 0.05 * torch.randn_like(x) if x.requires_grad else x


VARIANTS = {
    "baseline": {},
    "baseline seed 2": {"seed": 2},
    "baseline seed 3": {"seed": 3},
    "sin after attention": {"post_attn": lambda i: Fn(torch.sin, "sin")},
    "sign-sqrt after attention": {"post_attn": lambda i: Fn(lambda x: torch.sign(x) * (torch.sqrt(x.abs() + 1) - 1), "ssqrt")},
    "learned cubic after attention": {"post_attn": lambda i: Poly()},
    "log after MLP": {"post_mlp": lambda i: Fn(lambda x: torch.sign(x) * torch.log1p(x.abs()), "log")},
    "learned power after MLP": {"post_mlp": lambda i: Power()},
    "rounding after MLP": {"post_mlp": lambda i: Fn(round_ste, "round")},
    "running mean after MLP": {"post_mlp": lambda i: Fn(lambda x: x + 0.5 * cummean(x), "cummean")},
    "abs before MLP": {"pre_mlp": lambda i: Fn(torch.abs, "abs")},
    "channel max before MLP": {"pre_mlp": lambda i: Fn(lambda x: torch.maximum(x, x.roll(1, -1)), "tropical")},
    "fourier before MLP": {"pre_mlp": lambda i: Fourier(100 + i)},
    "gaussian squash before attention": {"pre_attn": lambda i: Fn(lambda x: x * torch.exp(-x * x / 8), "gauss")},
    "tanh cap between blocks (known-ish)": {"between": lambda i: Fn(lambda x: 5 * torch.tanh(x / 5), "softcap")},
    "random rotation between blocks": {"between": lambda i: Rotate(200 + i)},
    "swap halves between blocks": {"between": lambda i: Fn(lambda x: x.roll(D // 2, -1), "swap")},
    "noise between blocks": {"between": lambda i: Fn(dither, "dither")},
    "attention x MLP product": {"product": True},
}
if VARIANTS_LIMIT:
    VARIANTS = dict(list(VARIANTS.items())[:VARIANTS_LIMIT])


# %% [markdown]
# ## Model

# %%
class Block(nn.Module):
    def __init__(self, i, spec):
        super().__init__()
        self.ln1, self.ln2 = nn.LayerNorm(D), nn.LayerNorm(D)
        self.qkv, self.proj = nn.Linear(D, 3 * D, bias=False), nn.Linear(D, D, bias=False)
        self.up, self.down = nn.Linear(D, 4 * D, bias=False), nn.Linear(4 * D, D, bias=False)
        mk = lambda k: spec[k](i) if k in spec else None
        self.pre_attn, self.post_attn, self.pre_mlp, self.post_mlp, self.between = (mk(k) for k in ("pre_attn", "post_attn", "pre_mlp", "post_mlp", "between"))
        self.product = spec.get("product", False)

    def attn(self, h):
        B, T, _ = h.shape
        q, k, v = self.qkv(h).view(B, T, 3, HEADS, D // HEADS).permute(2, 0, 3, 1, 4)
        return self.proj(F.scaled_dot_product_attention(q, k, v, is_causal=True).transpose(1, 2).reshape(B, T, D))

    def forward(self, x):
        h = self.ln1(x)
        h = self.pre_attn(h) if self.pre_attn else h
        a = self.attn(h)
        a = self.post_attn(a) if self.post_attn else a
        x = x + a
        h = self.ln2(x)
        h = self.pre_mlp(h) if self.pre_mlp else h
        m = self.down(F.gelu(self.up(h)))
        m = self.post_mlp(m) if self.post_mlp else m
        x = x + m + (0.1 * a * m if self.product else 0)
        return self.between(x) if self.between else x


class GPT(nn.Module):
    def __init__(self, spec):
        super().__init__()
        self.emb = nn.Embedding(V, D); self.pos = nn.Embedding(CTX, D)
        self.blocks = nn.ModuleList(Block(i, spec) for i in range(LAYERS))
        self.ln = nn.LayerNorm(D)
        self.apply(self._init)
        for b in self.blocks:                                    # GPT-2 style scaled init on residual projections
            nn.init.normal_(b.proj.weight, std=0.02 / math.sqrt(2 * LAYERS)); nn.init.normal_(b.down.weight, std=0.02 / math.sqrt(2 * LAYERS))

    @staticmethod
    def _init(m):
        if isinstance(m, (nn.Linear, nn.Embedding)):
            nn.init.normal_(m.weight, std=0.02)

    def forward(self, idx):
        x = self.emb(idx) + self.pos(torch.arange(idx.shape[1], device=idx.device))
        for b in self.blocks:
            x = b(x)
        return self.ln(x) @ self.emb.weight.T                    # tied embeddings


# %% [markdown]
# ## Training (identical for every variant)

# %%
def make_scaler():
    try:
        return torch.amp.GradScaler("cuda", enabled=DEV == "cuda")
    except (AttributeError, TypeError):
        return torch.cuda.amp.GradScaler(enabled=DEV == "cuda")


def train(spec):
    torch.manual_seed(spec.get("seed", 1))
    m = GPT(spec).to(DEV)
    decay = [p for n, p in m.named_parameters() if p.dim() >= 2]
    other = [p for n, p in m.named_parameters() if p.dim() < 2]
    opt = torch.optim.AdamW([{"params": decay, "weight_decay": 0.1}, {"params": other, "weight_decay": 0.0}], lr=LR, betas=(0.9, 0.95))
    scaler = make_scaler()
    curve, t, blew_up = [], time.time(), False
    m.train()
    for step in range(STEPS):
        lr = LR * min(1, (step + 1) / WARMUP) * (0.1 + 0.9 * 0.5 * (1 + math.cos(math.pi * step / STEPS)))
        for gr in opt.param_groups:
            gr["lr"] = lr
        x, y = batch_at(step)
        with torch.autocast(DEV, dtype=torch.float16, enabled=DEV == "cuda"):
            loss = F.cross_entropy(m(x).float().view(-1, V), y.reshape(-1))
        if not torch.isfinite(loss):
            blew_up = True; log(f"    blew up at step {step}"); break
        opt.zero_grad(set_to_none=True)
        scaler.scale(loss).backward(); scaler.unscale_(opt)
        nn.utils.clip_grad_norm_(m.parameters(), 1.0)
        scaler.step(opt); scaler.update()
        if (step + 1) % 250 == 0:
            curve.append((step + 1, round(loss.item(), 3)))
    secs = time.time() - t
    m.eval()
    return m, {"train_curve": curve, "blew_up": blew_up, "tok_per_s": (step + 1) * BATCH * CTX / secs,
               "params_M": sum(p.numel() for p in m.parameters()) / 1e6}


# %% [markdown]
# ## Standard tests

# %%
@torch.no_grad()
def lm_loss(m, flat):
    n = (len(flat) - 1) // CTX
    tot, cnt = 0.0, 0
    for i in range(0, n, 32):
        rows = torch.stack([flat[j * CTX:(j + 1) * CTX + 1] for j in range(i, min(n, i + 32))]).long().to(DEV)
        with torch.autocast(DEV, dtype=torch.float16, enabled=DEV == "cuda"):
            lg = m(rows[:, :-1]).float()
        tot += F.cross_entropy(lg.reshape(-1, V), rows[:, 1:].reshape(-1), reduction="sum").item(); cnt += rows[:, 1:].numel()
    return tot / cnt


def load_wikitext():
    try:
        d = load_dataset("Salesforce/wikitext", "wikitext-2-raw-v1", split="test")
        ids = tok("\n\n".join(r["text"] for r in d), add_special_tokens=False)["input_ids"]
        return torch.tensor(ids[: (50_000 if QUICK else None)], dtype=torch.int32)
    except Exception as e:
        log(f"wikitext unavailable: {e}"); return None


BLIMP_CONFIGS = ['adjunct_island', 'anaphor_gender_agreement', 'anaphor_number_agreement', 'animate_subject_passive', 'animate_subject_trans', 'causative', 'complex_NP_island', 'coordinate_structure_constraint_complex_left_branch', 'coordinate_structure_constraint_object_extraction', 'determiner_noun_agreement_1', 'determiner_noun_agreement_2', 'determiner_noun_agreement_irregular_1', 'determiner_noun_agreement_irregular_2', 'determiner_noun_agreement_with_adj_2', 'determiner_noun_agreement_with_adj_irregular_1', 'determiner_noun_agreement_with_adj_irregular_2', 'determiner_noun_agreement_with_adjective_1', 'distractor_agreement_relational_noun', 'distractor_agreement_relative_clause', 'drop_argument', 'ellipsis_n_bar_1', 'ellipsis_n_bar_2', 'existential_there_object_raising', 'existential_there_quantifiers_1', 'existential_there_quantifiers_2', 'existential_there_subject_raising', 'expletive_it_object_raising', 'inchoative', 'intransitive', 'irregular_past_participle_adjectives', 'irregular_past_participle_verbs', 'irregular_plural_subject_verb_agreement_1', 'irregular_plural_subject_verb_agreement_2', 'left_branch_island_echo_question', 'left_branch_island_simple_question', 'matrix_question_npi_licensor_present', 'npi_present_1', 'npi_present_2', 'only_npi_licensor_present', 'only_npi_scope', 'passive_1', 'passive_2', 'principle_A_c_command', 'principle_A_case_1', 'principle_A_case_2', 'principle_A_domain_1', 'principle_A_domain_2', 'principle_A_domain_3', 'principle_A_reconstruction', 'regular_plural_subject_verb_agreement_1', 'regular_plural_subject_verb_agreement_2', 'sentential_negation_npi_licensor_present', 'sentential_negation_npi_scope', 'sentential_subject_island', 'superlative_quantifiers_1', 'superlative_quantifiers_2', 'tough_vs_raising_1', 'tough_vs_raising_2', 'transitive', 'wh_island', 'wh_questions_object_gap', 'wh_questions_subject_gap', 'wh_questions_subject_gap_long_distance', 'wh_vs_that_no_gap', 'wh_vs_that_no_gap_long_distance', 'wh_vs_that_with_gap', 'wh_vs_that_with_gap_long_distance']


def load_blimp():
    out = []
    for c in (BLIMP_CONFIGS[:3] if QUICK else BLIMP_CONFIGS):
        try:
            d = load_dataset("nyu-mll/blimp", c, split="train")
            out += [(r["sentence_good"], r["sentence_bad"]) for r in d.select(range(min(BLIMP_N, len(d))))]
        except Exception as e:
            log(f"blimp {c} unavailable: {e}")
    return out


def load_hellaswag():
    try:
        d = load_dataset("Rowan/hellaswag", split="validation")
        return [(r["ctx"], r["endings"], int(r["label"])) for r in d.select(range(min(HS_N, len(d))))]
    except Exception as e:
        log(f"hellaswag unavailable: {e}"); return []


@torch.no_grad()
def seq_logprobs(m, pairs):
    """pairs: [(context, continuation)] -> (sum log-prob of continuation, continuation length)."""
    res = []
    for i in range(0, len(pairs), 64):
        enc = [([EOT] + tok(c, add_special_tokens=False)["input_ids"], tok(x, add_special_tokens=False)["input_ids"]) for c, x in pairs[i:i + 64]]
        L = min(CTX, max(len(a) + len(b) for a, b in enc))
        ids = torch.full((len(enc), L), EOT, dtype=torch.long); mask = torch.zeros(len(enc), L - 1)
        for j, (a, b) in enumerate(enc):
            s = (a + b)[-L:]; ids[j, :len(s)] = torch.tensor(s)
            start = max(0, len(s) - len(b) - 1); mask[j, start:len(s) - 1] = 1
        ids, mask = ids.to(DEV), mask.to(DEV)
        with torch.autocast(DEV, dtype=torch.float16, enabled=DEV == "cuda"):
            lp = F.log_softmax(m(ids[:, :-1]).float(), -1).gather(-1, ids[:, 1:, None]).squeeze(-1)
        res += [((lp[j] * mask[j]).sum().item(), mask[j].sum().item()) for j in range(len(enc))]
    return res


def blimp_acc(m, data):
    if not data:
        return None
    good = seq_logprobs(m, [("", g) for g, _ in data]); bad = seq_logprobs(m, [("", b) for _, b in data])
    return st.mean(g[0] > b[0] for g, b in zip(good, bad))


def hellaswag_acc(m, data):
    if not data:
        return None
    flat = [(c, " " + e) for c, es, _ in data for e in es]
    lp = seq_logprobs(m, flat)
    right = 0
    for k, (_, es, lab) in enumerate(data):
        scores = [s / max(n, 1) for s, n in lp[4 * k: 4 * k + 4]]       # length-normalised (acc_norm style)
        right += max(range(4), key=lambda i: scores[i]) == lab
    return right / len(data)


# %% [markdown]
# ## Run every variant

# %%
def report(R):
    base = [r for n, r in R.items() if n.startswith("baseline") and not r["blew_up"]]
    bm = st.mean(r["val_loss"] for r in base) if base else None
    bs = st.stdev([r["val_loss"] for r in base]) if len(base) > 1 else 0.0
    fmt = lambda v, f: "–" if v is None else f.format(v)
    rows = sorted(R.items(), key=lambda kv: kv[1]["val_loss"] if kv[1]["val_loss"] is not None else 99)
    L = ["# Weird maths in a transformer: results", "",
         f"GPT, {LAYERS} layers, width {D}, {max(r['params_M'] for r in R.values()):.0f}M parameters (incl. embeddings), GPT-2 tokenizer, "
         f"{STEPS * BATCH * CTX / 1e6:.0f}M FineWeb-Edu tokens each, same batches and seed.",
         f"Baseline FineWeb val loss {fmt(bm, '{:.3f}')} ± {bs:.3f} (std over 3 seeds); a difference smaller than about {2 * bs:.3f} is probably noise.", "",
         "| variant | FineWeb val loss | vs baseline | WikiText-2 ppl | BLiMP | HellaSwag | tokens/s | blew up |", "|---|---|---|---|---|---|---|---|"]
    for n, r in rows:
        d = None if (bm is None or r["val_loss"] is None) else r["val_loss"] - bm
        L.append(f"| {n} | {fmt(r['val_loss'], '{:.3f}')} | {fmt(d, '{:+.3f}')} | {fmt(r['wiki_ppl'], '{:.0f}')} | {fmt(r['blimp'], '{:.1%}')} | "
                 f"{fmt(r['hellaswag'], '{:.1%}')} | {r['tok_per_s']/1e3:.0f}k | {'crashed' if r.get('crashed') else 'yes' if r['blew_up'] else ''} |")
    L += ["", "HellaSwag chance is 25%; BLiMP chance is 50%. Lower loss and perplexity are better.", "",
          f"Total time {(time.time() - T0) / 60:.0f} min."]
    return "\n".join(L) + "\n"


def main():
    wiki, blimp, hs = load_wikitext(), load_blimp(), load_hellaswag()
    log(f"tests: wikitext {0 if wiki is None else len(wiki)} tokens, blimp {len(blimp)} pairs, hellaswag {len(hs)}")
    R = {}
    for name, spec in VARIANTS.items():
        log(f"=== {name}")
        try:
            m, info = train(spec)
            info["val_loss"] = None if info["blew_up"] else lm_loss(m, VAL)
            info["wiki_ppl"] = None if (info["blew_up"] or wiki is None) else math.exp(lm_loss(m, wiki))
            info["blimp"] = None if info["blew_up"] else blimp_acc(m, blimp)
            info["hellaswag"] = None if info["blew_up"] else hellaswag_acc(m, hs)
        except Exception as e:                       # one broken variant shouldn't sink the whole run
            log(f"    crashed: {type(e).__name__}: {e}")
            m, info = None, {"blew_up": True, "crashed": f"{type(e).__name__}: {e}", "val_loss": None, "wiki_ppl": None,
                             "blimp": None, "hellaswag": None, "tok_per_s": 0, "params_M": 0, "train_curve": []}
        R[name] = info
        log(f"    val {info['val_loss']}  wiki {info['wiki_ppl']}  blimp {info['blimp']}  hellaswag {info['hellaswag']}  {info['tok_per_s']/1e3:.0f}k tok/s")
        json.dump(R, open("weird_results.json", "w"), indent=1)
        del m; torch.cuda.empty_cache() if DEV == "cuda" else None
        open("WEIRD_RESULTS.md", "w").write(report(R))
    print(report(R))


# %%
if __name__ == "__main__" or "ipykernel" in sys.modules:
    main()
