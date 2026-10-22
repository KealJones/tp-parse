# %% [markdown]
# # Simple language first, with real data
#
# Run 2 of the goals experiment showed that learning a skill in a small, clean language first
# made a small model learn it in English from far fewer examples. This notebook tries the same
# recipe with real text instead of a toy world:
#
# | stage | `simple-first` | `english` (fair rival) | `ceiling` |
# |---|---|---|---|
# | 1 | real toki pona (Tatoeba, Wikipedia, lipu kule) | the English budget | fresh English, unlimited |
# | 2 | bridge: toki pona ⇄ English sentence pairs, plus English stories with Basic English words swapped to their toki pona hub word | (same English budget) | (fresh English) |
# | 3 | the English budget (+ a little toki pona replay) | (same English budget) | (fresh English) |
#
# The English budget is a small, fixed set of SimpleStories plus the English half of the Tatoeba pairs.
# `simple-first` and `english` see exactly the same English and train for the same number of steps;
# the only difference is that `simple-first` spends part of its steps on toki pona instead of
# repeating English. `ceiling` gets unlimited fresh English as an upper bound. For every model the
# checkpoint with the best English validation loss is kept, so repeating data can't unfairly hurt `english`.
#
# **Tests**: English validation loss, BLiMP (67 grammar tests, 1,000 pairs each), and bAbI
# (20 reasoning tasks; every model gets the same short fine-tune on bAbI, then is tested).
#
# **On Kaggle**: Settings → Accelerator → GPU T4; Settings → **Internet on** (needed to download the
# datasets; it needs a phone-verified account). Then *Save Version → Save & Run All* so it runs in the
# background (about 2–2.5 hours), and download `real_export.zip` and `REAL_RESULTS.md` from the output.

# %%
import json, math, os, random, re, statistics as st, struct, sys, time, zipfile
import torch
import torch.nn as nn
import torch.nn.functional as F

try:
    import sentencepiece as spm
except ImportError:
    os.system("pip install -q sentencepiece")
    import sentencepiece as spm
from datasets import load_dataset

QUICK = "--quick" in sys.argv
DEV = "cuda" if torch.cuda.is_available() else "cpu"
AMP = dict(device_type=DEV, dtype=torch.float16 if DEV == "cuda" else torch.bfloat16, enabled=DEV == "cuda")

if QUICK:
    D, LAYERS, HEADS, FFN, CTX, VOCAB = 64, 2, 2, 128, 128, 2000
    S1, S2, S3, BATCH, EVAL_EVERY = 60, 40, 60, 8, 40
    N_STORIES, N_CEIL, BABI_STEPS, BLIMP_N, BABI_N = 300, 3000, 30, 20, 10
else:
    D, LAYERS, HEADS, FFN, CTX, VOCAB = 384, 8, 6, 1024, 256, 8192   # about 17M parameters
    S1, S2, S3, BATCH, EVAL_EVERY = 1500, 1500, 3000, 64, 500
    N_STORIES, N_CEIL, BABI_STEPS, BLIMP_N, BABI_N = 10_000, 400_000, 1500, 1000, 200
LR = 1e-3
SEED = 0
random.seed(SEED); torch.manual_seed(SEED)
T0 = time.time()


def log(*a):
    print(f"[{(time.time() - T0) / 60:5.1f} min]", *a, flush=True)


# %% [markdown]
# ## Data

# %%
def clean(s):
    return " ".join((s or "").split())


log("loading toki pona")
tato = load_dataset("NetherQuartz/tatoeba-tokipona", split="train")
pairs = [(clean(r["tok"]), clean(r["en"])) for r in tato if r["tok"] and r["en"]]
mined = load_dataset("NetherQuartz/tokipona-mined-pairs", split="train")
mono = load_dataset("NetherQuartz/tokipona-monolingual", split="train")
tp_text = list(dict.fromkeys([p[0] for p in pairs] + [clean(r["tok"]) for r in mined] + [clean(r["text"]) for r in mono]))
random.shuffle(pairs); random.shuffle(tp_text)
if QUICK:
    pairs, tp_text = pairs[:2000], tp_text[:4000]
tp_val, tp_text = tp_text[:500], tp_text[500:]

log("loading SimpleStories")
ss = load_dataset("SimpleStories/SimpleStories", split="train", streaming=True)
stories = []
for r in ss:
    stories.append(clean(r["story"]))
    if len(stories) >= N_STORIES + N_CEIL + 2000:
        break
val_stories, budget, ceil_pool = stories[:2000], stories[2000:2000 + N_STORIES], stories[2000 + N_STORIES:]
en_budget = budget + [p[1] for p in pairs]          # the English both rivals get

HUBS = json.load(open("hubs.json")) if os.path.exists("hubs.json") else None  # replaced inline in the notebook


# HUBS["table"]: English word -> toki pona hub (the 850 Basic English words mapped earlier, plus words whose
# Linku gloss points at exactly one toki pona word). HUBS["irregular"]: went -> go and so on.
def lemma(w):
    T, IRR = HUBS["table"], HUBS["irregular"]
    if w in T:
        return w
    if w in IRR and IRR[w] in T:
        return IRR[w]
    for suf, rep in (("ies", "y"), ("es", ""), ("s", ""), ("ied", "y"), ("ed", ""), ("ed", "e"), ("ing", ""), ("ing", "e"), ("ly", "")):
        if w.endswith(suf):
            b = w[: -len(suf)] + rep
            if b in T:
                return b
            if len(b) > 2 and b[-1] == b[-2] and b[:-1] in T:
                return b[:-1]
    return None


def mix(story, r, p=0.5):
    """Swap English words for their toki pona hub word, half the time (about 45% of words have a hub)."""
    def sw(m):
        w = m.group(0)
        b = lemma(w.lower())
        return HUBS["table"][b] if b and r.random() < p else w
    return re.sub(r"[A-Za-z]+", sw, story)


r = random.Random(1)
bridge_pairs = [f"tp: {a}\nen: {b}" if r.random() < 0.5 else f"en: {b}\ntp: {a}" for a, b in pairs]
mixed_stories = [mix(s, r) for s in budget]
log(f"toki pona {len(tp_text)} texts, pairs {len(pairs)}, budget {len(budget)} stories, ceiling pool {len(ceil_pool)}")
print("mixed example:", mixed_stories[0][:300])

# %% [markdown]
# ## Tokenizer: SentencePiece BPE, Llama-style (so it exports to GGUF / Ollama)

# %%
with open("spm_train.txt", "w") as f:
    for s in tp_text + [p[1] for p in pairs] + ceil_pool[:60_000]:
        f.write(s + "\n")
spm.SentencePieceTrainer.train(
    input="spm_train.txt", model_prefix="tok", vocab_size=VOCAB, model_type="bpe", byte_fallback=True,
    character_coverage=0.9995, normalization_rule_name="identity", add_dummy_prefix=True,
    remove_extra_whitespaces=False, split_digits=True, allow_whitespace_only_pieces=True,
    pad_id=3, unk_id=0, bos_id=1, eos_id=2, input_sentence_size=400_000, shuffle_input_sentence=True,
    num_threads=os.cpu_count(), minloglevel=2)
SP = spm.SentencePieceProcessor(model_file="tok.model")
V, EOS, PAD = SP.get_piece_size(), SP.eos_id(), SP.pad_id()


def stream(texts):
    ids = []
    for chunk in SP.encode(texts):
        ids += chunk + [EOS]
    return torch.tensor(ids, dtype=torch.long)


log("tokenising")
S = {"tp": stream(tp_text), "tp_val": stream(tp_val), "bridge": stream(bridge_pairs), "mixed": stream(mixed_stories),
     "en": stream(en_budget), "val": stream(val_stories)}
S["ceil"] = stream(ceil_pool)
for k, v in S.items():
    print(f"  {k:7} {len(v)/1e6:6.2f}M tokens")

# %% [markdown]
# ## Model and training

# %%
def make_model():
    from transformers import LlamaConfig, LlamaForCausalLM
    cfg = LlamaConfig(vocab_size=V, hidden_size=D, intermediate_size=FFN, num_hidden_layers=LAYERS,
                      num_attention_heads=HEADS, num_key_value_heads=HEADS, max_position_embeddings=CTX,
                      rms_norm_eps=1e-6, rope_theta=10000.0, tie_word_embeddings=True,
                      bos_token_id=1, eos_token_id=EOS, pad_token_id=PAD)
    try:
        m = LlamaForCausalLM._from_config(cfg, attn_implementation="sdpa")
    except Exception:
        m = LlamaForCausalLM(cfg)
    return m.to(DEV)


def windows(src, n, g):
    i = torch.randint(0, len(src) - CTX - 1, (n,), generator=g)
    idx = i[:, None] + torch.arange(CTX + 1)
    return src[idx]


VAL_WIN = windows(S["val"], 256 if not QUICK else 16, torch.Generator().manual_seed(7))
TPVAL_WIN = windows(S["tp_val"], 128 if not QUICK else 16, torch.Generator().manual_seed(8))


@torch.no_grad()
def val_loss(model, win=None):
    win = VAL_WIN if win is None else win
    model.eval()
    tot = 0.0
    for b in win.split(32):
        b = b.to(DEV)
        with torch.autocast(**AMP):
            lg = model(input_ids=b[:, :-1]).logits
        tot += F.cross_entropy(lg.float().reshape(-1, V), b[:, 1:].reshape(-1), reduction="sum").item()
    model.train()
    return tot / (win.shape[0] * CTX)


def make_scaler():
    try:
        return torch.amp.GradScaler("cuda", enabled=DEV == "cuda")
    except (AttributeError, TypeError):
        return torch.cuda.amp.GradScaler(enabled=DEV == "cuda")


class Trainer:
    """One optimizer and LR schedule across all stages; tracks the best English validation loss."""
    def __init__(self, model, total):
        self.m, self.total, self.step = model, total, 0
        self.opt = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=0.1, betas=(0.9, 0.95))
        self.scaler, self.g = make_scaler(), torch.Generator().manual_seed(SEED)
        self.best, self.best_state, self.curve = float("inf"), None, []

    def run(self, mixture, steps, track=True, name=""):
        names, weights = zip(*mixture)
        t = time.time()
        self.m.train()
        for k in range(steps):
            frac = self.step / self.total
            lr = LR * min(1, (self.step + 1) / 200) * (0.1 + 0.9 * 0.5 * (1 + math.cos(math.pi * frac)))
            for gr in self.opt.param_groups:
                gr["lr"] = lr
            counts = torch.multinomial(torch.tensor(weights, dtype=torch.float), BATCH, replacement=True, generator=self.g).bincount(minlength=len(names))
            b = torch.cat([windows(S[n], int(c), self.g) for n, c in zip(names, counts) if c > 0]).to(DEV)
            with torch.autocast(**AMP):
                lg = self.m(input_ids=b[:, :-1]).logits
            loss = F.cross_entropy(lg.float().reshape(-1, V), b[:, 1:].reshape(-1))
            self.opt.zero_grad(set_to_none=True)
            self.scaler.scale(loss).backward()
            self.scaler.unscale_(self.opt)
            nn.utils.clip_grad_norm_(self.m.parameters(), 1.0)
            self.scaler.step(self.opt); self.scaler.update()
            self.step += 1
            if self.step % EVAL_EVERY == 0 or k == steps - 1:
                v = val_loss(self.m)
                self.curve.append((self.step, v))
                if track and v < self.best:
                    self.best = v
                    self.best_state = {kk: vv.detach().clone() for kk, vv in self.m.state_dict().items()}
                eta = (time.time() - t) / (k + 1) * (steps - k - 1) / 60
                log(f"  {name} step {self.step}/{self.total}  train {loss.item():.3f}  english val {v:.3f}  best {self.best:.3f}  (stage eta {eta:.0f} min)")

    def finish(self):
        if self.best_state is not None:
            self.m.load_state_dict(self.best_state)
        return self.m


def train_condition(cond):
    torch.manual_seed(SEED)
    model = make_model()
    tr = Trainer(model, S1 + S2 + S3)
    if cond == "simple-first":
        tr.run([("tp", 1.0)], S1, track=False, name=cond)
        tr.run([("bridge", 0.4), ("mixed", 0.4), ("tp", 0.2)], S2, track=False, name=cond)
        tr.run([("en", 0.9), ("tp", 0.1)], S3, name=cond)
    elif cond == "english":
        tr.run([("en", 1.0)], S1 + S2 + S3, name=cond)
    else:
        tr.run([("ceil", 1.0)], S1 + S2 + S3, name=cond)
    model = tr.finish()
    return model, tr.curve


# %% [markdown]
# ## Tests: BLiMP and bAbI

# %%
@torch.no_grad()
def seq_logprob(model, texts, prefix_lens=None):
    """Sum of log-probs of each text's tokens (after an optional prefix of n tokens)."""
    model.eval()
    out = []
    enc = [[EOS] + x for x in SP.encode(texts)]
    order = sorted(range(len(enc)), key=lambda i: len(enc[i]))
    res = [0.0] * len(enc)
    for s in range(0, len(order), 128):
        idx = order[s:s + 128]
        L = min(max(len(enc[i]) for i in idx), CTX + 1)
        x = torch.full((len(idx), L), PAD, dtype=torch.long)
        m = torch.zeros(len(idx), L - 1)
        for j, i in enumerate(idx):
            e = enc[i][-L:]
            x[j, :len(e)] = torch.tensor(e)
            # position j predicts token j+1; score every token from index prefix_len on (index 1 on with no prefix)
            start = 0 if prefix_lens is None else max(0, prefix_lens[i] - 1 - (len(enc[i]) - len(e)))
            m[j, start:len(e) - 1] = 1
        x, m = x.to(DEV), m.to(DEV)
        with torch.autocast(**AMP):
            lg = model(input_ids=x[:, :-1]).logits
        lp = F.log_softmax(lg.float(), -1).gather(-1, x[:, 1:].unsqueeze(-1)).squeeze(-1)
        for j, i in enumerate(idx):
            res[i] = (lp[j] * m[j]).sum().item()
    return res


BLIMP_CONFIGS = ['adjunct_island', 'anaphor_gender_agreement', 'anaphor_number_agreement', 'animate_subject_passive', 'animate_subject_trans', 'causative', 'complex_NP_island', 'coordinate_structure_constraint_complex_left_branch', 'coordinate_structure_constraint_object_extraction', 'determiner_noun_agreement_1', 'determiner_noun_agreement_2', 'determiner_noun_agreement_irregular_1', 'determiner_noun_agreement_irregular_2', 'determiner_noun_agreement_with_adj_2', 'determiner_noun_agreement_with_adj_irregular_1', 'determiner_noun_agreement_with_adj_irregular_2', 'determiner_noun_agreement_with_adjective_1', 'distractor_agreement_relational_noun', 'distractor_agreement_relative_clause', 'drop_argument', 'ellipsis_n_bar_1', 'ellipsis_n_bar_2', 'existential_there_object_raising', 'existential_there_quantifiers_1', 'existential_there_quantifiers_2', 'existential_there_subject_raising', 'expletive_it_object_raising', 'inchoative', 'intransitive', 'irregular_past_participle_adjectives', 'irregular_past_participle_verbs', 'irregular_plural_subject_verb_agreement_1', 'irregular_plural_subject_verb_agreement_2', 'left_branch_island_echo_question', 'left_branch_island_simple_question', 'matrix_question_npi_licensor_present', 'npi_present_1', 'npi_present_2', 'only_npi_licensor_present', 'only_npi_scope', 'passive_1', 'passive_2', 'principle_A_c_command', 'principle_A_case_1', 'principle_A_case_2', 'principle_A_domain_1', 'principle_A_domain_2', 'principle_A_domain_3', 'principle_A_reconstruction', 'regular_plural_subject_verb_agreement_1', 'regular_plural_subject_verb_agreement_2', 'sentential_negation_npi_licensor_present', 'sentential_negation_npi_scope', 'sentential_subject_island', 'superlative_quantifiers_1', 'superlative_quantifiers_2', 'tough_vs_raising_1', 'tough_vs_raising_2', 'transitive', 'wh_island', 'wh_questions_object_gap', 'wh_questions_subject_gap', 'wh_questions_subject_gap_long_distance', 'wh_vs_that_no_gap', 'wh_vs_that_no_gap_long_distance', 'wh_vs_that_with_gap', 'wh_vs_that_with_gap_long_distance']
log("loading BLiMP and bAbI")
BLIMP = []
for c in (BLIMP_CONFIGS[:4] if QUICK else BLIMP_CONFIGS):
    d = load_dataset("nyu-mll/blimp", c, split="train")
    BLIMP += [(c, r["field"], r["sentence_good"], r["sentence_bad"]) for r in d.select(range(min(BLIMP_N, len(d))))]
babi_tr = load_dataset("Muennighoff/babi", split="train")
babi_te = load_dataset("Muennighoff/babi", split="test")
BABI_ANS = {}
for r_ in babi_tr:
    BABI_ANS.setdefault(r_["task"], set()).add(r_["answer"])
BABI_TRAIN = [(f"{clean(r_['passage'])}\nQuestion: {r_['question']}\nAnswer:", " " + r_["answer"]) for r_ in babi_tr]
_bt = {}
for r_ in babi_te:
    _bt.setdefault(r_["task"], []).append(r_)
BABI_TEST = [(t, f"{clean(x['passage'])}\nQuestion: {x['question']}\nAnswer:", x["answer"]) for t, xs in _bt.items()
             for x in random.Random(t).sample(xs, min(BABI_N, len(xs)))]


def blimp(model):
    good = seq_logprob(model, [b[2] for b in BLIMP])
    bad = seq_logprob(model, [b[3] for b in BLIMP])
    by = {}
    for (c, field, _, _), g, b in zip(BLIMP, good, bad):
        by.setdefault(field, []).append(g > b)
    allv = [x for v in by.values() for x in v]
    return {"overall": st.mean(allv), **{k: st.mean(v) for k, v in by.items()}}


def babi(model):
    """Same short fine-tune for every model (answer tokens only), then pick the most likely answer."""
    import copy
    m = copy.deepcopy(model)
    m.train()
    opt = torch.optim.AdamW(m.parameters(), lr=3e-4, weight_decay=0.0)
    scaler, r = make_scaler(), random.Random(3)
    for step in range(BABI_STEPS):
        items = [r.choice(BABI_TRAIN) for _ in range(32)]
        encs = [([EOS] + SP.encode(q))[-(CTX - 8):] for q, _ in items]
        ans = [SP.encode(a.strip()) for _, a in items]
        L = max(len(e) + len(a) for e, a in zip(encs, ans))
        x = torch.full((len(items), L), PAD, dtype=torch.long)
        w = torch.zeros(len(items), L - 1)
        for j, (e, a) in enumerate(zip(encs, ans)):
            x[j, :len(e) + len(a)] = torch.tensor(e + a)
            w[j, len(e) - 1:len(e) + len(a) - 1] = 1
        x, w = x.to(DEV), w.to(DEV)
        with torch.autocast(**AMP):
            lg = m(input_ids=x[:, :-1]).logits
        loss = (F.cross_entropy(lg.float().reshape(-1, V), x[:, 1:].reshape(-1), reduction="none") * w.reshape(-1)).sum() / w.sum()
        opt.zero_grad(set_to_none=True)
        scaler.scale(loss).backward(); scaler.unscale_(opt)
        nn.utils.clip_grad_norm_(m.parameters(), 1.0)
        scaler.step(opt); scaler.update()
    texts, owners, prefix = [], [], []
    for i, (t, q, a) in enumerate(BABI_TEST):
        n = len(SP.encode(q)) + 1
        for cand in sorted(BABI_ANS[t]):
            texts.append(q + " " + cand); owners.append((i, cand)); prefix.append(n)
    lp = seq_logprob(m, texts, prefix_lens=prefix)
    best = {}
    for (i, cand), v in zip(owners, lp):
        if i not in best or v > best[i][1]:
            best[i] = (cand, v)
    per = {}
    for i, (t, q, a) in enumerate(BABI_TEST):
        per.setdefault(t, []).append(best[i][0] == a)
    del m
    return {"mean": st.mean(st.mean(v) for v in per.values()), **{f"task{t}": st.mean(v) for t, v in sorted(per.items())}}


@torch.no_grad()
def samples(model, prompts=("Once upon a time", "The little dog", "Mia wanted to")):
    model.eval()
    out = []
    for p in prompts:
        x = torch.tensor([[EOS] + SP.encode(p)], device=DEV)
        g = model.generate(x, max_new_tokens=80, do_sample=True, temperature=0.7, top_k=40, pad_token_id=PAD, eos_token_id=EOS)
        out.append(SP.decode(g[0, 1:].tolist()))
    return out


# %% [markdown]
# ## Export: GGUF (F16) for Ollama / llama.cpp

# %%
GGUF_T = {"u32": 4, "i32": 5, "f32": 6, "bool": 7, "str": 8, "arr": 9, "u64": 10}


def _gs(out, s):
    b = s.encode("utf-8")
    out += struct.pack("<Q", len(b)) + b


def _gv(out, typ, v):
    if typ == "str":
        _gs(out, v)
    else:
        out += struct.pack({"u32": "<I", "i32": "<i", "f32": "<f", "bool": "<?", "u64": "<Q"}[typ], v)


def write_gguf(path, kvs, tensors, align=32):
    """tensors: [(name, torch tensor)]; 2-D weights stored as F16, the rest as F32."""
    blobs = []
    for name, t in tensors:
        t = t.detach().float().cpu().contiguous()
        if t.dim() == 2:
            blobs.append((name, list(t.shape), 1, t.half().numpy().tobytes()))
        else:
            blobs.append((name, list(t.shape), 0, t.numpy().astype("<f4").tobytes()))
    out = bytearray(b"GGUF") + struct.pack("<IQQ", 3, len(blobs), len(kvs))
    for key, typ, val in kvs:
        _gs(out, key)
        out += struct.pack("<I", GGUF_T[typ])
        if typ == "arr":
            et, items = val
            out += struct.pack("<IQ", GGUF_T[et], len(items))
            for it in items:
                _gv(out, et, it)
        else:
            _gv(out, typ, val)
    off = 0
    for name, shape, ty, data in blobs:
        _gs(out, name)
        ne = list(reversed(shape))
        out += struct.pack("<I", len(ne)) + b"".join(struct.pack("<Q", d) for d in ne)
        out += struct.pack("<IQ", ty, off)
        off += len(data) + (-len(data)) % align
    out += b"\0" * ((-len(out)) % align)
    for _, _, _, data in blobs:
        out += data + b"\0" * ((-len(data)) % align)
    with open(path, "wb") as f:
        f.write(out)


def gguf_metadata(name):
    pieces = [SP.id_to_piece(i) for i in range(V)]
    types = [2 if SP.is_unknown(i) else 3 if SP.is_control(i) else 6 if SP.is_byte(i) else 5 if SP.is_unused(i) else 1 for i in range(V)]
    return [
        ("general.architecture", "str", "llama"), ("general.name", "str", name), ("general.file_type", "u32", 1),
        ("llama.context_length", "u32", CTX), ("llama.embedding_length", "u32", D), ("llama.block_count", "u32", LAYERS),
        ("llama.feed_forward_length", "u32", FFN), ("llama.attention.head_count", "u32", HEADS),
        ("llama.attention.head_count_kv", "u32", HEADS), ("llama.rope.dimension_count", "u32", D // HEADS),
        ("llama.rope.freq_base", "f32", 10000.0), ("llama.attention.layer_norm_rms_epsilon", "f32", 1e-6),
        ("llama.vocab_size", "u32", V),
        ("tokenizer.ggml.model", "str", "llama"), ("tokenizer.ggml.tokens", "arr", ("str", pieces)),
        ("tokenizer.ggml.scores", "arr", ("f32", [SP.get_score(i) for i in range(V)])),
        ("tokenizer.ggml.token_type", "arr", ("i32", types)),
        ("tokenizer.ggml.unknown_token_id", "u32", 0), ("tokenizer.ggml.bos_token_id", "u32", 1),
        ("tokenizer.ggml.eos_token_id", "u32", EOS), ("tokenizer.ggml.padding_token_id", "u32", PAD),
        ("tokenizer.ggml.add_bos_token", "bool", False), ("tokenizer.ggml.add_eos_token", "bool", False),
        ("tokenizer.ggml.add_space_prefix", "bool", True),
    ]


def rope_permute(w):
    return w.reshape(HEADS, 2, w.shape[0] // HEADS // 2, w.shape[1]).transpose(1, 2).reshape(w.shape)


def gguf_tensors(model):
    sd = {k: v.detach().float().cpu() for k, v in model.state_dict().items()}
    T = {"token_embd.weight": sd["model.embed_tokens.weight"], "output_norm.weight": sd["model.norm.weight"]}
    for i in range(LAYERS):
        p, b = f"model.layers.{i}.", f"blk.{i}."
        T.update({b + "attn_norm.weight": sd[p + "input_layernorm.weight"],
                  b + "attn_q.weight": rope_permute(sd[p + "self_attn.q_proj.weight"]),
                  b + "attn_k.weight": rope_permute(sd[p + "self_attn.k_proj.weight"]),
                  b + "attn_v.weight": sd[p + "self_attn.v_proj.weight"],
                  b + "attn_output.weight": sd[p + "self_attn.o_proj.weight"],
                  b + "ffn_norm.weight": sd[p + "post_attention_layernorm.weight"],
                  b + "ffn_gate.weight": sd[p + "mlp.gate_proj.weight"],
                  b + "ffn_up.weight": sd[p + "mlp.up_proj.weight"],
                  b + "ffn_down.weight": sd[p + "mlp.down_proj.weight"]})
    return T


def llamacpp_style_logits(T, ids):
    hd, L = D // HEADS, len(ids)
    rms = lambda x, w: x * torch.rsqrt(x.pow(2).mean(-1, keepdim=True) + 1e-6) * w
    ang = torch.arange(L)[:, None].float() * (1.0 / 10000 ** (torch.arange(0, hd, 2).float() / hd))[None]
    cos, sin = ang.cos()[:, None], ang.sin()[:, None]

    def rope(q):
        a, b = q.view(L, HEADS, hd // 2, 2).unbind(-1)
        return torch.stack([a * cos - b * sin, a * sin + b * cos], -1).reshape(L, HEADS, hd)

    x = T["token_embd.weight"][torch.tensor(ids)]
    mask = torch.triu(torch.full((L, L), float("-inf")), 1)
    for i in range(LAYERS):
        b = f"blk.{i}."
        h = rms(x, T[b + "attn_norm.weight"])
        q, k = rope((h @ T[b + "attn_q.weight"].T).view(L, HEADS, hd)), rope((h @ T[b + "attn_k.weight"].T).view(L, HEADS, hd))
        v = (h @ T[b + "attn_v.weight"].T).view(L, HEADS, hd)
        att = torch.softmax(torch.einsum("qhd,khd->hqk", q, k) / hd ** 0.5 + mask, -1)
        x = x + torch.einsum("hqk,khd->qhd", att, v).reshape(L, D) @ T[b + "attn_output.weight"].T
        h = rms(x, T[b + "ffn_norm.weight"])
        x = x + (F.silu(h @ T[b + "ffn_gate.weight"].T) * (h @ T[b + "ffn_up.weight"].T)) @ T[b + "ffn_down.weight"].T
    return rms(x, T["output_norm.weight"]) @ T["token_embd.weight"].T


EXPORT_README = '''# Small story models (about 17M parameters each)

- `simple-first.gguf`: toki pona first, then a bridge, then a small English budget
- `english.gguf`: the same small English budget only
- `ceiling.gguf`: lots of fresh English (an upper bound)

They write simple English stories (trained on SimpleStories). They are not chat models:
give them the start of a story and they continue it.

    ollama create simple-first -f Modelfile.simple-first
    ollama run simple-first "Once upon a time, a girl named Kim"

`tok.model` is the SentencePiece tokenizer, and `hf-*/` holds the same models in Hugging Face format.
'''


def modelfile(name):
    return f'''FROM ./{name}.gguf
TEMPLATE """{{{{ .Prompt }}}}"""
PARAMETER temperature 0.7
PARAMETER top_k 40
PARAMETER num_ctx {CTX}
PARAMETER num_predict 200
'''


def export(models, out="real_export"):
    os.makedirs(out, exist_ok=True)
    checks = {}
    ids = [EOS] + SP.encode("Once upon a time, there was a little cat who wanted to fly.")
    for name, model in models.items():
        model.eval()
        T = gguf_tensors(model)
        with torch.no_grad():
            ref = model.float()(input_ids=torch.tensor([ids], device=DEV)).logits[0].float().cpu()
        checks[name] = (ref - llamacpp_style_logits(T, ids)).abs().max().item()
        write_gguf(f"{out}/{name}.gguf", gguf_metadata(name), list(T.items()))
        open(f"{out}/Modelfile.{name}", "w").write(modelfile(name))
        model.save_pretrained(f"{out}/hf-{name}")
    os.system(f"cp tok.model {out}/")
    open(f"{out}/README.md", "w").write(EXPORT_README)
    with zipfile.ZipFile(f"{out}.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(out):
            for fn in files:
                z.write(os.path.join(root, fn))
    log(f"export check (max logit diff, HF vs llama.cpp-style): {checks}; wrote {out}.zip ({os.path.getsize(out + '.zip')/1e6:.0f} MB)")
    return checks


# %% [markdown]
# ## Run everything

# %%
def main():
    log(f"device {DEV}, vocab {V}, params {sum(p.numel() for p in make_model().parameters())/1e6:.1f}M")
    R, models = {}, {}
    for cond in ("simple-first", "english", "ceiling"):
        log(f"=== {cond} ===")
        model, curve = train_condition(cond)
        res = {"val_loss": val_loss(model), "curve": curve}
        if cond == "simple-first":
            res["tp_val_loss"] = val_loss(model, TPVAL_WIN)
        log("  BLiMP"); res["blimp"] = blimp(model)
        log("  bAbI"); res["babi"] = babi(model)
        res["samples"] = samples(model)
        log(f"  {cond}: val {res['val_loss']:.3f}  BLiMP {res['blimp']['overall']*100:.1f}%  bAbI {res['babi']['mean']*100:.1f}%")
        for s in res["samples"]:
            print("   >", s[:300].replace("\n", " "))
        R[cond] = res
        models[cond] = model.cpu()
        json.dump(R, open("real_results.json", "w"), indent=1)
        torch.cuda.empty_cache() if DEV == "cuda" else None
    for m in models.values():
        m.to(DEV)
    checks = export(models)
    report(R, checks)


def report(R, checks):
    pct = lambda v: f"{v*100:.1f}%"
    conds = list(R)
    L = ["# Simple language first, real data: results", "",
         f"One seed. English budget: {N_STORIES:,} SimpleStories + {len(pairs):,} Tatoeba English sentences "
         f"({len(S['en'])/1e6:.1f}M tokens). Ceiling: {len(S['ceil'])/1e6:.0f}M tokens of fresh English. "
         f"{S1 + S2 + S3:,} training steps each, {BATCH}×{CTX} tokens per step.", "",
         "| model | English val loss (lower is better) | BLiMP | bAbI (mean of 20 tasks) |", "|---|---|---|---|"]
    for c in conds:
        L.append(f"| {c} | {R[c]['val_loss']:.3f} | {pct(R[c]['blimp']['overall'])} | {pct(R[c]['babi']['mean'])} |")
    fields = [k for k in R[conds[0]]["blimp"] if k != "overall"]
    L += ["", "## BLiMP by area", "", "| model | " + " | ".join(fields) + " |", "|---" * (len(fields) + 1) + "|"]
    for c in conds:
        L.append(f"| {c} | " + " | ".join(pct(R[c]["blimp"][f]) for f in fields) + " |")
    tasks = [k for k in R[conds[0]]["babi"] if k != "mean"]
    L += ["", "## bAbI by task (chance is roughly 1 in the number of possible answers)", "",
          "| model | " + " | ".join(t.replace("task", "") for t in tasks) + " |", "|---" * (len(tasks) + 1) + "|"]
    for c in conds:
        L.append(f"| {c} | " + " | ".join(f"{R[c]['babi'][t]*100:.0f}" for t in tasks) + " |")
    if "tp_val_loss" in R.get("simple-first", {}):
        L += ["", f"simple-first's toki pona val loss at the end: {R['simple-first']['tp_val_loss']:.3f}"]
    L += ["", "## English val loss over training", ""]
    for c in conds:
        L.append(f"- {c}: " + ", ".join(f"{s}:{v:.2f}" for s, v in R[c]["curve"]))
    L += ["", "## Samples (prompt: Once upon a time / The little dog / Mia wanted to)", ""]
    for c in conds:
        L.append(f"**{c}**")
        L += [f"> {s.replace(chr(10), ' ')}" for s in R[c]["samples"]] + [""]
    L += [f"Export check (max logit difference HF vs GGUF-style forward): " + ", ".join(f"{k} {v:.1e}" for k, v in checks.items())]
    text = "\n".join(L) + "\n"
    open("REAL_RESULTS.md", "w").write(text)
    print(text)


# %%
if __name__ == "__main__" or "ipykernel" in sys.modules:
    main()
