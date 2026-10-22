# %% [markdown]
# # Goals + lookup, run 3: lookups, RL, and a model you can run in Ollama
#
# Every episode is a little goal problem: someone wants something, there may be
# obstacles (closed or locked doors, a key somewhere else, a missing fact, a choice),
# and the model writes its plan step by step. When a fact is missing it can call a
# lookup tool (`search : where is the bread ?`); the harness answers.
#
# What's new since run 2:
# 1. **Lookup fix.** The bridge now also swaps the plan's structure words (`alasa`↔`search`,
#    `la`↔`, so`, `tan ni`↔`because`…), so asking instead of guessing carries over to English.
# 2. **RL.** After training, the model tries plans on its own; the world scores them
#    (success, minus a penalty for guessing when it should have searched) and good plans get reinforced.
# 3. **Ollama export.** The model is a standard Llama architecture. At the end the notebook writes
#    `goals.gguf`, a `Modelfile`, and `chat.py` (a harness that answers the model's searches), zipped
#    as `goals_export.zip`.
#
# Conditions: `tp` (simple-language plans → mixed plans → 1,024 English plans → RL) and `reference`
# (English plans all along, as a ceiling). Tests are in English: `iid`, `combo` (hidden + locked,
# never in the English data or RL), `long` (4–5 obstacles, longer than any training data).
#
# On Kaggle: Settings → Accelerator → GPU (T4), then Run All. About 1–1.5 hours.
# Download `goals_export.zip` and `GOALS_RESULTS.md` from the output panel at the end.

# %%
import json, math, os, random, re, statistics as st, struct, sys, time, zipfile
import torch
import torch.nn as nn
import torch.nn.functional as F

QUICK = "--quick" in sys.argv          # tiny CPU smoke test
DEV = "cuda" if torch.cuda.is_available() else "cpu"
if DEV == "cpu":
    torch.set_num_threads(2)

if QUICK:
    D, LAYERS, HEADS, FFN, CTX = 32, 2, 2, 64, 256
    S1, S2, S3, RL_STEPS, SEEDS, N_EN, NTEST, BATCH = 40, 20, 20, 3, [0], 64, 12, 8
    RL_PROMPTS, RL_K = 4, 4
else:
    D, LAYERS, HEADS, FFN, CTX = 192, 8, 6, 512, 256   # about 3.7M parameters, Llama style
    S1, S2, S3, RL_STEPS, SEEDS, N_EN, NTEST, BATCH = 3000, 1500, 1500, 150, [0, 1, 2], 1024, 200, 64
    RL_PROMPTS, RL_K = 16, 8      # each RL step: 16 problems, 8 attempts each
LR, RL_LR = 6e-4, 2e-5
AMP = dict(device_type=DEV, dtype=torch.float16 if DEV == "cuda" else torch.bfloat16, enabled=DEV == "cuda")

# %% [markdown]
# ## The world

# %%
AGENTS = [("person", "jan"), ("child", "jan lili")]
PLACES = [("house", "tomo", True), ("shop", "tomo esun", True), ("school", "tomo sona", True),
          ("forest", "ma kasi", False), ("field", "ma", False)]
ITEMS = [("bread", "pan"), ("fruit", "kili"), ("water", "telo"), ("fish", "kala"), ("book", "lipu")]
PROPS = [("sweet", "suwi"), ("hot", "seli"), ("cold", "lete"), ("big", "suli")]
TP = {e: t for e, t in AGENTS + [(p[0], p[1]) for p in PLACES] + ITEMS + PROPS + [("key", "ilo open")]}
TPW = {**TP, "door": "lupa", "goes": "tawa", "opens": "open", "takes": "kama jo", "has": "jo", "wants": "wile",
       "closed": "pini", "locked": "pini wawa", "open": "open", "thing": "ijo"}
_MIX = None   # a random.Random while rendering mixed plans


def T(x):
    """toki pona for x, or (when mixing) the English word half the time."""
    return x if _MIX is not None and _MIX.random() < 0.5 else TPW[x]


def X(tp, en):
    """Structure words (la, tan ni, alasa, sona, nasin): also swapped to English half the time when mixing."""
    return en if _MIX is not None and _MIX.random() < 0.5 else tp
HAS_DOOR = {p[0]: p[2] for p in PLACES}
PLACE_N = [p[0] for p in PLACES]
ITEM_N = [i[0] for i in ITEMS]
DOOR_PLACES = [p for p in PLACE_N if HAS_DOOR[p]]

# obstacle combos: H hidden target, C closed / L locked target door, KH hidden key, KC key behind closed door, S choice
COMBOS = []
for H in (0, 1):
    for door in ("", "C", "L"):
        for KH in ((0, 1) if door == "L" else (0,)):
            for KC in ((0, 1) if door == "L" else (0,)):
                for S in (0, 1):
                    obs = frozenset(o for o, on in [("H", H), (door, door), ("KH", KH), ("KC", KC), ("S", S)] if on)
                    COMBOS.append(obs)


def split_of(obs):
    if len(obs) >= 4:
        return "long"
    if "H" in obs and "L" in obs:
        return "combo"
    return "iid"


def tp_door(p):
    d, t = T("door"), T(p)
    return f"{d} {t}" if " " not in t else f"{d} pi {t}"


def make_episode(r, obs):
    """Sample a concrete world for an obstacle set. Returns the true state, what's told, and the gold plan."""
    agent = r.choice(AGENTS)[0]
    door = "L" if "L" in obs else "C" if "C" in obs else ""
    tplace = r.choice(DOOR_PLACES) if door else r.choice(PLACE_N)
    doors = {p: "open" for p in DOOR_PLACES}
    if door:
        doors[tplace] = "closed" if door == "C" else "locked"
    loc, told_loc = {}, {}
    if "S" in obs:
        cands = r.sample(ITEM_N, r.choice((2, 3)))
        target, prop = cands[0], r.choice(PROPS)[0]
        r.shuffle(cands)
    else:
        cands, target, prop = [], r.choice(ITEM_N), None
    loc[target] = tplace
    kplace = None
    if door == "L":
        if "KC" in obs:
            kplace = r.choice([p for p in DOOR_PLACES if p != tplace])
            doors[kplace] = "closed"
        else:
            kplace = r.choice([p for p in PLACE_N if p != tplace])
        loc["key"] = kplace
    start = r.choice(PLACE_N)
    # distractors and the other choice candidates
    others = [i for i in ITEM_N if i != target]
    r.shuffle(others)
    extra = [c for c in cands if c != target] + [i for i in others if i not in cands][: r.choice((1, 2))]
    for i in extra:
        loc[i] = r.choice(PLACE_N)
    for i in loc:
        hidden = (i == target and "H" in obs) or (i == "key" and "KH" in obs)
        if not hidden:
            told_loc[i] = loc[i]
    if door != "L" and r.random() < 0.3:          # an irrelevant key, sometimes
        loc["key"] = told_loc["key"] = r.choice(PLACE_N)
    told_doors = {}
    for p in DOOR_PLACES:
        if p == tplace or p == kplace or r.random() < 0.3:
            told_doors[p] = doors[p]
    facts = [("at", agent, start)] + [("loc", i, p) for i, p in told_loc.items()] + \
            [("door", p, s) for p, s in told_doors.items()]
    if "S" in obs:
        facts += [("prop", c, prop, c == target) for c in cands]
    r.shuffle(facts)
    goal = ("wantprop", agent, prop) if "S" in obs else ("want", agent, target)

    plan, here, opened = [], start, set()

    def go(p):
        nonlocal here
        if here != p:
            plan.append(("go", agent, p)); here = p

    if "S" in obs:
        plan.append(("choose", agent, target, prop))
    if "H" in obs:
        plan.append(("search", target, tplace))
    if door == "L":
        plan.append(("needkey", agent, tplace))
        if "KH" in obs:
            plan.append(("search", "key", kplace))
        go(kplace)
        if doors.get(kplace) == "closed":
            plan.append(("open", agent, kplace))
        plan.append(("take", agent, "key"))
        go(tplace)
        plan.append(("unlock", agent, tplace))
    else:
        go(tplace)
        if door == "C":
            plan.append(("open", agent, tplace))
    plan.append(("take", agent, target))
    plan.append(("check", agent, target))
    plan.append(("done",))
    return {"obs": obs, "agent": agent, "start": start, "loc": loc, "told_loc": told_loc, "doors": doors,
            "target": target, "prop": prop, "cands": cands, "facts": facts, "goal": goal, "plan": plan}


# %% [markdown]
# ## Rendering: English and toki pona. Segments are (text, trained-on); tool results aren't trained on.

# %%
def en_fact(f):
    k = f[0]
    if k == "at": return f"the {f[1]} is at the {f[2]} ."
    if k == "loc": return f"the {f[1]} is at the {f[2]} ."
    if k == "door": return f"the door of the {f[1]} is {f[2]} ."
    if k == "prop": return f"the {f[1]} is {f[2]} ." if f[3] else f"the {f[1]} is not {f[2]} ."
    if k == "want": return f"the {f[1]} wants the {f[2]} ."
    if k == "wantprop": return f"the {f[1]} wants a {f[2]} thing ."
    raise ValueError(f)


def tp_fact(f):
    k = f[0]
    if k in ("at", "loc"): return f"{T(f[1])} li lon {T(f[2])} ."
    if k == "door": return f"{tp_door(f[1])} li " + T(f[2]) + " ."
    if k == "prop": return f"{T(f[1])} li {T(f[2])}" + ("" if f[3] else " ala") + " ."
    if k == "want": return f"{T(f[1])} li {T('wants')} e {T(f[2])} ."
    if k == "wantprop": return f"{T(f[1])} li {T('wants')} e {T('thing')} {T(f[2])} ."
    raise ValueError(f)


def en_step(s):
    k = s[0]
    if k == "search": return [(f"search : where is the {s[1]} ?", True), (f"result : the {s[1]} is at the {s[2]} .", False)]
    if k == "choose": return [(f"the {s[1]} wants the {s[2]} because the {s[2]} is {s[3]} .", True)]
    if k == "needkey": return [(f"the door of the {s[2]} is locked , so the {s[1]} needs the key .", True)]
    if k == "go": return [(f"the {s[1]} is not at the {s[2]} , so the {s[1]} goes to the {s[2]} .", True)]
    if k == "open": return [(f"the door of the {s[2]} is closed , so the {s[1]} opens the door of the {s[2]} .", True)]
    if k == "unlock": return [(f"the door of the {s[2]} is locked , so the {s[1]} opens the door of the {s[2]} with the key .", True)]
    if k == "take": return [(f"the {s[1]} takes the {s[2]} .", True)]
    if k == "check": return [(f"the {s[1]} has the {s[2]} , so the goal is done .", True)]
    if k == "done": return [("done .", True)]
    raise ValueError(s)


def tp_step(s):
    k = s[0]
    if k == "search": return [(f"{X('alasa', 'search')} : {T(s[1])} li lon seme ?", True), (f"{X('sona', 'result')} : {T(s[1])} li lon {T(s[2])} .", False)]
    if k == "choose": return [(f"{T(s[1])} li {T('wants')} e {T(s[2])} {X('tan ni :', 'because')} {T(s[2])} li {T(s[3])} .", True)]
    if k == "needkey": return [(f"{tp_door(s[2])} li {T('locked')} {X('la', ', so')} {T(s[1])} li {T('wants')} e {T('key')} .", True)]
    if k == "go": return [(f"{T(s[1])} li lon ala {T(s[2])} {X('la', ', so')} {T(s[1])} li {T('goes')} {T(s[2])} .", True)]
    if k == "open": return [(f"{tp_door(s[2])} li {T('closed')} {X('la', ', so')} {T(s[1])} li {T('opens')} e {tp_door(s[2])} .", True)]
    if k == "unlock": return [(f"{tp_door(s[2])} li {T('locked')} {X('la', ', so')} {T(s[1])} li {T('opens')} e {tp_door(s[2])} kepeken {T('key')} .", True)]
    if k == "take": return [(f"{T(s[1])} li {T('takes')} e {T(s[2])} .", True)]
    if k == "check": return [(f"{T(s[1])} li {T('has')} e {T(s[2])} {X('la', ', so')} wile li pini .", True)]
    if k == "done": return [(X("ale li pini", "done") + " .", True)]
    raise ValueError(s)


def prompt_text(ep, lang="en"):
    fact = en_fact if lang == "en" else tp_fact
    return " ".join(fact(f) for f in ep["facts"] + [ep["goal"]]) + (" plan :" if lang == "en" else f" {X('nasin', 'plan')} :")


def render(ep, lang, r=None):
    """lang: en, tp, or mix (toki pona grammar, content words English half the time; needs r)."""
    global _MIX
    if lang == "mix":
        _MIX = r
        try:
            return render(ep, "tp")
        finally:
            _MIX = None
    step = en_step if lang == "en" else tp_step
    segs = [(prompt_text(ep, lang), True)]
    for s in ep["plan"]:
        segs += step(s)
    return segs


# Scenes: loose sentences using the same words, but no goals, no "so", "because", search or plans.
def scene(r, n=None):
    out = []
    for _ in range(n or r.randint(4, 7)):
        a, p, i = r.choice(AGENTS)[0], r.choice(PLACE_N), r.choice(ITEM_N + ["key"])
        pr, dp = r.choice(PROPS)[0], r.choice(DOOR_PLACES)
        out.append(r.choice([
            f"the {a} is at the {p} .", f"the {i} is at the {p} .", f"the {a} is not at the {p} .",
            f"the door of the {dp} is {r.choice(['open', 'closed', 'locked'])} .", f"the {i} is {pr} .",
            f"the {i} is not {pr} .", f"the {a} wants the {i} .", f"the {a} wants a {pr} thing .",
            f"the {a} goes to the {p} .", f"the {a} opens the door of the {dp} .", f"the {a} takes the {i} .",
            f"the {a} has the {i} .", f"the {a} opens the door of the {dp} with the key ."]))
    return " ".join(out)


SWAP = {**TP, "door": "lupa", "closed": "pini", "locked": "pini wawa", "goes": "tawa", "opens": "open",
        "takes": "kama jo", "has": "jo", "wants": "wile", "not": "ala", "thing": "ijo", "open": "open"}


def mix(text, r):
    return " ".join(SWAP[w] if w in SWAP and r.random() < 0.5 else w for w in text.split())


def episodes(r, n, allowed):
    return [make_episode(r, r.choice(allowed)) for _ in range(n)]


TRAIN_COMBOS = [c for c in COMBOS if len(c) <= 3]                       # toki pona and reference see all of these
EN_COMBOS = [c for c in TRAIN_COMBOS if split_of(c) == "iid"]          # English few-shot: never hidden + locked together

# %% [markdown]
# ## Vocabulary and model
#
# Words are stored the way SentencePiece / llama.cpp expects (`▁bread`, plus every prefix like `▁b`, `▁br`…
# and byte fallbacks), so the exported model tokenises text exactly as it was trained. Only whole-word
# tokens are ever used in training.

# %%
def build_vocab():
    r = random.Random(0)
    words = set()
    for c in COMBOS:
        for _ in range(30):
            ep = make_episode(r, c)
            for lang in ("en", "tp", "mix"):
                for t, _ in render(ep, lang, r):
                    words |= set(t.split())
    for _ in range(500):
        words |= set(mix(scene(r), r).split()) | set(scene(r).split())
    pieces = ["<unk>", "<s>", "</s>", "<pad>"] + [f"<0x{b:02X}>" for b in range(256)]
    seen = set(pieces)
    for w in sorted(words):
        full = "▁" + w
        for k in range(1, len(full) + 1):
            if full[:k] not in seen:
                seen.add(full[:k]); pieces.append(full[:k])
    return sorted(words), pieces


WORDS, PIECES = build_vocab()
PIECE_ID = {p: i for i, p in enumerate(PIECES)}
STOI = {w: PIECE_ID["▁" + w] for w in WORDS}
ITOW = {i: w for w, i in STOI.items()}
PAD, V = PIECE_ID["<pad>"], len(PIECES)


def make_model():
    from transformers import LlamaConfig, LlamaForCausalLM
    cfg = LlamaConfig(vocab_size=V, hidden_size=D, intermediate_size=FFN, num_hidden_layers=LAYERS,
                      num_attention_heads=HEADS, num_key_value_heads=HEADS, max_position_embeddings=CTX,
                      rms_norm_eps=1e-6, rope_theta=10000.0, tie_word_embeddings=True,
                      bos_token_id=1, eos_token_id=2, pad_token_id=PAD)
    try:
        m = LlamaForCausalLM._from_config(cfg, attn_implementation="sdpa")
    except Exception:
        m = LlamaForCausalLM(cfg)
    return m.to(DEV)


def logits_of(model, x):
    return model(input_ids=x).logits


# %% [markdown]
# ## Data → tensors, training

# %%
def encode(segs):
    ids, m = [], []
    for t, train in segs:
        w = [STOI[x] for x in t.split()]
        ids += w; m += [train] * len(w)
    return ids[:CTX + 1], m[:CTX + 1]


def batch(items):
    L = max(len(i) for i, _ in items)
    x = torch.full((len(items), L - 1), PAD, dtype=torch.long)
    y = torch.full((len(items), L - 1), PAD, dtype=torch.long)
    w = torch.zeros(len(items), L - 1)
    for b, (ids, m) in enumerate(items):
        n = len(ids) - 1
        x[b, :n] = torch.tensor(ids[:-1]); y[b, :n] = torch.tensor(ids[1:]); w[b, :n] = torch.tensor(m[1:], dtype=torch.float)
    return x.to(DEV), y.to(DEV), w.to(DEV)


def make_scaler():
    try:
        return torch.amp.GradScaler("cuda", enabled=DEV == "cuda")
    except (AttributeError, TypeError):
        return torch.cuda.amp.GradScaler(enabled=DEV == "cuda")


def train(model, sampler, steps, r):
    opt = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=0.1, betas=(0.9, 0.95))
    scaler = make_scaler()
    model.train()
    for step in range(steps):
        lr = LR * min(1, (step + 1) / 100) * (0.1 + 0.9 * 0.5 * (1 + math.cos(math.pi * step / steps)))
        for g in opt.param_groups:
            g["lr"] = lr
        x, y, w = batch([sampler(r) for _ in range(BATCH)])
        with torch.autocast(**AMP):
            logits = logits_of(model, x)
        loss = (F.cross_entropy(logits.float().reshape(-1, V), y.reshape(-1), reduction="none") * w.reshape(-1)).sum() / w.sum()
        opt.zero_grad(set_to_none=True)
        scaler.scale(loss).backward()
        scaler.unscale_(opt)
        nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        scaler.step(opt); scaler.update()
        if (step + 1) % 500 == 0:
            print(f"    step {step+1}/{steps}  loss {loss.item():.3f}", flush=True)
    return loss.item()


# %% [markdown]
# ## The checker: runs the model's plan in the world, answering searches

# %%
SENT = [
    ("search", re.compile(r"^search : where is the (\w+) \?$")),
    ("choose", re.compile(r"^the (\w+) wants the (\w+) because the \2 is (\w+) \.$")),
    ("needkey", re.compile(r"^the door of the (\w+) is locked , so the (\w+) needs the key \.$")),
    ("go", re.compile(r"^the (\w+) is not at the (\w+) , so the \1 goes to the \2 \.$")),
    ("open", re.compile(r"^the door of the (\w+) is closed , so the (\w+) opens the door of the \1 \.$")),
    ("unlock", re.compile(r"^the door of the (\w+) is locked , so the (\w+) opens the door of the \1 with the key \.$")),
    ("take", re.compile(r"^the (\w+) takes the (\w+) \.$")),
    ("check", re.compile(r"^the (\w+) has the (\w+) , so the goal is done \.$")),
    ("done", re.compile(r"^done \.$")),
]


class Sim:
    def __init__(self, ep):
        self.ep, self.here, self.doors, self.held = ep, ep["start"], dict(ep["doors"]), set()
        self.chosen = None if ep["prop"] else ep["target"]
        self.searched, self.status, self.why = set(), None, ""

    def fail(self, why):
        self.status, self.why = "fail", why

    def step(self, sent):
        """Run one finished sentence. Returns text to inject (tool result) or None."""
        ep = self.ep
        for kind, rx in SENT:
            m = rx.match(sent)
            if m:
                break
        else:
            return self.fail("garbled")
        g = m.groups()
        if kind == "search":
            if g[0] not in ep["loc"]:
                return self.fail("bad search")
            self.searched.add(g[0])
            return f"result : the {g[0]} is at the {ep['loc'][g[0]]} ."
        if kind == "done":
            ok = self.chosen == ep["target"] and ep["target"] in self.held
            self.status, self.why = ("ok", "") if ok else ("fail", "done without goal")
            return None
        agent = g[1] if kind in ("needkey", "open", "unlock") else g[0]
        if agent != ep["agent"]:
            return self.fail("wrong agent")
        if kind == "choose":
            if not ep["prop"] or g[2] != ep["prop"] or g[1] != ep["target"]:
                return self.fail("wrong choice")
            self.chosen = g[1]
        elif kind == "needkey":
            if self.doors.get(g[0]) != "locked":
                return self.fail("false claim")
        elif kind == "go":
            if g[1] not in HAS_DOOR or self.here == g[1]:
                return self.fail("bad go")
            self.here = g[1]
        elif kind in ("open", "unlock"):
            want = "closed" if kind == "open" else "locked"
            if self.here != g[0] or self.doors.get(g[0]) != want or (kind == "unlock" and "key" not in self.held):
                return self.fail("bad " + kind)
            self.doors[g[0]] = "open"
        elif kind == "take":
            i = g[1]
            if ep["loc"].get(i) != self.here or self.doors.get(self.here, "open") != "open":
                return self.fail("bad take")
            self.held.add(i)
        elif kind == "check":
            if g[1] not in self.held:
                return self.fail("false claim")
        return None


class TpSim:
    """Checks a toki pona plan against the gold one, sentence by sentence; answers alasa with sona."""
    def __init__(self, ep):
        self.gold = [t for st_ in ep["plan"] for t in tp_step(st_)]
        self.k, self.status, self.why, self.searched, self.ep = 0, None, "", set(), ep

    def step(self, sent):
        text, _ = self.gold[self.k]
        if sent != text:
            self.status, self.why = "fail", "off plan"
            return None
        self.k += 1
        if self.k == len(self.gold):
            self.status = "ok"
            return None
        nxt, trained = self.gold[self.k]
        if not trained:          # tool result
            self.k += 1
            return nxt
        return None


@torch.no_grad()
def run_plans(model, eps, max_new=200, lang="en", sample=False, temp=1.0):
    """Let the model write plans; the checker runs each sentence and answers searches.
    With sample=True also returns the token sequences and which tokens the model wrote (for RL)."""
    model.eval()
    word_only = torch.full((V,), float("-inf"), device=DEV)
    word_only[list(STOI.values())] = 0.0
    seqs = [[STOI[w] for w in prompt_text(ep, lang).split()] for ep in eps]
    wrote = [[False] * len(s) for s in seqs]
    sims = [(Sim if lang == "en" else TpSim)(ep) for ep in eps]
    sent = [[] for _ in eps]
    active = list(range(len(eps)))
    for _ in range(max_new):
        active = [i for i in active if sims[i].status is None and len(seqs[i]) < CTX]
        if not active:
            break
        L = max(len(seqs[i]) for i in active)
        x = torch.full((len(active), L), PAD, dtype=torch.long)
        for b, i in enumerate(active):
            x[b, : len(seqs[i])] = torch.tensor(seqs[i])
        with torch.autocast(**AMP):
            logits = logits_of(model, x.to(DEV))
        last = torch.tensor([len(seqs[i]) - 1 for i in active], device=DEV)
        lg = logits[torch.arange(len(active), device=DEV), last].float() + word_only
        nxt = (torch.multinomial(F.softmax(lg / temp, -1), 1).squeeze(-1) if sample else lg.argmax(-1)).tolist()
        for i, t in zip(active, nxt):
            seqs[i].append(t); wrote[i].append(True)
            w = ITOW[t]
            sent[i].append(w)
            if w in (".", "?"):
                inject = sims[i].step(" ".join(sent[i]))
                sent[i] = []
                if inject:
                    ids = [STOI[x] for x in inject.split()]
                    seqs[i] += ids; wrote[i] += [False] * len(ids)
    for s in sims:
        if s.status is None:
            s.status, s.why = "fail", "too long"
    return (sims, seqs, wrote) if sample else sims


def needed(s):
    o = s.ep["obs"]
    return ({s.ep["target"]} if "H" in o else set()) | ({"key"} if "KH" in o else set())


def score(sims):
    ok = [s.status == "ok" for s in sims]
    need = [s for s in sims if needed(s)]
    why = {}
    for s in sims:
        if s.status != "ok":
            why[s.why] = why.get(s.why, 0) + 1
    return {"success": st.mean(ok), "looked_when_needed": st.mean(needed(s) <= s.searched for s in need) if need else None,
            "looked_when_not": st.mean(bool(s.searched - needed(s)) for s in sims), "fails": why}


def test_sets():
    r = random.Random(12345)
    out = {}
    for split in ("iid", "combo", "long"):
        cs = [c for c in COMBOS if split_of(c) == split and (split == "long" or len(c) <= 3)]
        out[split] = episodes(r, NTEST, cs)
    return out


def evaluate(model, tests):
    return {split: score(run_plans(model, eps)) for split, eps in tests.items()}


# %% [markdown]
# ## RL: the model tries, the world scores
#
# Each step: 16 new English problems (never hidden + locked together, never 4+ obstacles), 8 sampled
# attempts each. Reward = 1 if the plan really gets the goal, −0.5 if it skipped a search it needed
# (guessing), −0.2 if it searched for something it was already told. Attempts better than their
# group's average get pushed up, worse ones down (a GRPO-style update, no value model).

# %%
def reward(s):
    need = needed(s)
    return (1.0 if s.status == "ok" else 0.0) - 0.5 * bool(need - s.searched) - 0.2 * bool(s.searched - need)


def rl(model, steps, r):
    opt = torch.optim.AdamW(model.parameters(), lr=RL_LR, weight_decay=0.0, betas=(0.9, 0.95))
    scaler = make_scaler()
    log = []
    for step in range(steps):
        group = [e for e in episodes(r, RL_PROMPTS, EN_COMBOS) for _ in range(RL_K)]
        sims, seqs, wrote = run_plans(model, group, sample=True)
        R = torch.tensor([reward(s) for s in sims]).view(RL_PROMPTS, RL_K)
        adv = ((R - R.mean(1, keepdim=True)) / (R.std(1, keepdim=True) + 1e-4)).view(-1)
        log.append((R.mean().item(), st.mean(s.status == "ok" for s in sims)))
        if (step + 1) % 25 == 0:
            rr = log[-25:]
            print(f"    rl step {step+1}/{steps}  reward {st.mean(a for a, _ in rr):.2f}  success {st.mean(b for _, b in rr)*100:.0f}%", flush=True)
        if adv.abs().sum() == 0:
            continue
        model.train()
        L = max(len(q) for q in seqs)
        x = torch.full((len(seqs), L), PAD, dtype=torch.long)
        m = torch.zeros(len(seqs), L)
        for b, (q, w) in enumerate(zip(seqs, wrote)):
            x[b, : len(q)] = torch.tensor(q); m[b, : len(w)] = torch.tensor(w, dtype=torch.float)
        x, m, adv = x.to(DEV), m.to(DEV)[:, 1:], adv.to(DEV)
        with torch.autocast(**AMP):
            logits = logits_of(model, x[:, :-1])
        logp = F.log_softmax(logits.float(), -1).gather(-1, x[:, 1:].unsqueeze(-1)).squeeze(-1)
        loss = -(adv * (logp * m).sum(1) / m.sum(1).clamp(min=1)).mean()
        opt.zero_grad(set_to_none=True)
        scaler.scale(loss).backward()
        scaler.unscale_(opt)
        nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        scaler.step(opt); scaler.update()
    return log


# %% [markdown]
# ## Export: GGUF for Ollama / llama.cpp
#
# A small pure-Python GGUF writer (no extra packages needed). Weights are stored as float32. HF Llama
# and llama.cpp lay out RoPE differently, so q and k are permuted the same way llama.cpp's own
# converter does. A check below re-runs the exported weights the llama.cpp way and compares the
# outputs with the trained model.

# %%
GGUF_T = {"u32": 4, "i32": 5, "f32": 6, "bool": 7, "str": 8, "arr": 9, "u64": 10}


def _gguf_str(out, s):
    b = s.encode("utf-8")
    out += struct.pack("<Q", len(b)) + b


def _gguf_val(out, typ, v):
    if typ == "str":
        _gguf_str(out, v)
    else:
        out += struct.pack({"u32": "<I", "i32": "<i", "f32": "<f", "bool": "<?", "u64": "<Q"}[typ], v)


def write_gguf(path, kvs, tensors, align=32):
    """kvs: [(key, type, value)], arrays as ("arr", (elem_type, [values])). tensors: [(name, shape, float32 bytes)]."""
    out = bytearray(b"GGUF") + struct.pack("<IQQ", 3, len(tensors), len(kvs))
    for key, typ, val in kvs:
        _gguf_str(out, key)
        out += struct.pack("<I", GGUF_T[typ])
        if typ == "arr":
            et, items = val
            out += struct.pack("<IQ", GGUF_T[et], len(items))
            for it in items:
                _gguf_val(out, et, it)
        else:
            _gguf_val(out, typ, val)
    off = 0
    for name, shape, data in tensors:
        _gguf_str(out, name)
        ne = list(reversed(shape))                     # ggml lists the fastest dimension first
        out += struct.pack("<I", len(ne)) + b"".join(struct.pack("<Q", d) for d in ne)
        out += struct.pack("<IQ", 0, off)              # type 0 = F32
        off += len(data) + (-len(data)) % align
    out += b"\0" * ((-len(out)) % align)
    for _, _, data in tensors:
        out += data + b"\0" * ((-len(data)) % align)
    with open(path, "wb") as f:
        f.write(out)


def gguf_metadata():
    hd = D // HEADS
    types = [2 if p == "<unk>" else 3 if p in ("<s>", "</s>", "<pad>") else 6 if p.startswith("<0x") else 1 for p in PIECES]
    scores = [float(len(p)) if t == 1 else 0.0 for p, t in zip(PIECES, types)]
    return [
        ("general.architecture", "str", "llama"), ("general.name", "str", "goals"), ("general.file_type", "u32", 0),
        ("llama.context_length", "u32", CTX), ("llama.embedding_length", "u32", D), ("llama.block_count", "u32", LAYERS),
        ("llama.feed_forward_length", "u32", FFN), ("llama.attention.head_count", "u32", HEADS),
        ("llama.attention.head_count_kv", "u32", HEADS), ("llama.rope.dimension_count", "u32", hd),
        ("llama.rope.freq_base", "f32", 10000.0), ("llama.attention.layer_norm_rms_epsilon", "f32", 1e-6),
        ("llama.vocab_size", "u32", V),
        ("tokenizer.ggml.model", "str", "llama"), ("tokenizer.ggml.tokens", "arr", ("str", PIECES)),
        ("tokenizer.ggml.scores", "arr", ("f32", scores)), ("tokenizer.ggml.token_type", "arr", ("i32", types)),
        ("tokenizer.ggml.unknown_token_id", "u32", 0), ("tokenizer.ggml.bos_token_id", "u32", 1),
        ("tokenizer.ggml.eos_token_id", "u32", 2), ("tokenizer.ggml.padding_token_id", "u32", PAD),
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
    """Forward pass the way llama.cpp does it (interleaved RoPE on the permuted weights)."""
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
        q, k, v = (rope((h @ T[b + "attn_q.weight"].T).view(L, HEADS, hd)), rope((h @ T[b + "attn_k.weight"].T).view(L, HEADS, hd)),
                   (h @ T[b + "attn_v.weight"].T).view(L, HEADS, hd))
        att = torch.softmax(torch.einsum("qhd,khd->hqk", q, k) / hd ** 0.5 + mask, -1)
        x = x + torch.einsum("hqk,khd->qhd", att, v).reshape(L, D) @ T[b + "attn_output.weight"].T
        h = rms(x, T[b + "ffn_norm.weight"])
        x = x + (F.silu(h @ T[b + "ffn_gate.weight"].T) * (h @ T[b + "ffn_up.weight"].T)) @ T[b + "ffn_down.weight"].T
    return rms(x, T["output_norm.weight"]) @ T["token_embd.weight"].T


MODELFILE = '''FROM ./goals.gguf
TEMPLATE """{{ .Prompt }}"""
PARAMETER temperature 0
PARAMETER num_ctx 256
PARAMETER stop "?"
PARAMETER stop "the goal is done"
'''

EXPORT_README = '''# goals: a 3.7M-parameter planning model

Trained in a toy world (see experiments/goals in the tp-parse repo). It knows only the words in words.txt.

## Run with Ollama
    ollama create goals -f Modelfile
    python3 chat.py            # demo: test problems, with the harness answering its searches
    python3 chat.py --you      # type your own world; you answer its searches

Or plain: ollama run goals "the person is at the field . the bread is at the house . the person wants the bread . plan :"
(without chat.py nobody answers its "search" calls, so it stops at the "?").

## Files
- goals.gguf: the model (llama architecture, float32), also loads in llama.cpp / LM Studio
- hf/: the same model in Hugging Face format
- episodes.jsonl: test problems with the hidden facts, for chat.py's demo
'''


def export(model, out="goals_export"):
    os.makedirs(out, exist_ok=True)
    model.eval()
    T = gguf_tensors(model)
    ids = [STOI[w] for w in prompt_text(test_sets()["combo"][0]).split()]
    with torch.no_grad():
        ref = logits_of(model.float(), torch.tensor([ids], device=DEV))[0].float().cpu()
    mine = llamacpp_style_logits(T, ids)
    diff = (ref - mine).abs().max().item()
    print(f"export check: max logit difference HF vs llama.cpp-style = {diff:.2e}  ({'OK' if diff < 1e-2 else 'MISMATCH'})")
    write_gguf(f"{out}/goals.gguf", gguf_metadata(), [(n, list(t.shape), t.contiguous().numpy().astype("<f4").tobytes()) for n, t in T.items()])
    model.save_pretrained(f"{out}/hf")
    json.dump({"pieces": PIECES, "words": WORDS}, open(f"{out}/hf/vocab.json", "w"))
    open(f"{out}/Modelfile", "w").write(MODELFILE)
    open(f"{out}/chat.py", "w").write(CHAT_PY)
    open(f"{out}/README.md", "w").write(EXPORT_README)
    open(f"{out}/words.txt", "w").write("\n".join(WORDS) + "\n")
    with open(f"{out}/episodes.jsonl", "w") as f:
        for split, eps in test_sets().items():
            for ep in eps[:20]:
                gold = " ".join(t for s in ep["plan"] for t, _ in en_step(s))
                f.write(json.dumps({"split": split, "prompt": prompt_text(ep), "loc": ep["loc"], "gold": gold}) + "\n")
    with zipfile.ZipFile(f"{out}.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(out):
            for fn in files:
                z.write(os.path.join(root, fn))
    print(f"wrote {out}.zip ({os.path.getsize(out + '.zip') / 1e6:.1f} MB)")
    return diff



# %%
try:
    CHAT_PY
except NameError:
    CHAT_PY = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "chat.py")).read()


# %% [markdown]
# ## Run everything

# %%
def run():
    t0 = time.time()
    tests = test_sets()
    print(f"device {DEV}, vocab {len(WORDS)} words ({V} pieces), params {sum(p.numel() for p in make_model().parameters())/1e6:.2f}M", flush=True)
    results, best = [], (-1, None)
    for seed in SEEDS:
        dr = random.Random(1000 + seed)
        tp_goals = [encode(render(e, "tp")) for e in episodes(dr, 20000, TRAIN_COMBOS)]
        mixed_goals = [encode(render(e, "mix", dr)) for e in episodes(dr, 20000, TRAIN_COMBOS)]
        mixed_scene = [encode([(mix(scene(dr), dr), True)]) for _ in range(20000)]
        en_goals_all = [encode(render(e, "en")) for e in episodes(dr, 20000, TRAIN_COMBOS)]
        en_scene = [encode([(scene(dr), True)]) for _ in range(20000)]
        few = [encode(render(e, "en")) for e in episodes(random.Random(5000 + seed), N_EN, EN_COMBOS)]
        say = lambda name, res: print(f"seed {seed} {name:10} " + "  ".join(f"{k} {v['success']*100:3.0f}%" for k, v in res.items())
                                      + f"  looked-up-when-needed {st.mean([v['looked_when_needed'] for v in res.values() if v['looked_when_needed'] is not None] or [0])*100:.0f}%   ({time.time()-t0:.0f}s)", flush=True)
        for cond in ("tp", "reference"):
            torch.manual_seed(seed)
            model = make_model()
            r = random.Random(seed)
            if cond == "tp":
                train(model, lambda r: r.choice(tp_goals), S1, r)
                train(model, lambda r: r.choice(mixed_goals) if r.random() < 0.6 else
                      (r.choice(tp_goals) if r.random() < 0.5 else r.choice(mixed_scene)), S2, r)
                replay = tp_goals + mixed_goals
                tp_ok = {sp: st.mean(x.status == "ok" for x in run_plans(model, eps, lang="tp")) for sp, eps in tests.items() if sp != "long"}
                results.append({"seed": seed, "cond": "tp-in-simple-language", "res": tp_ok})
                print(f"seed {seed} plans in the simple language (exact): " + "  ".join(f"{k} {v*100:.0f}%" for k, v in tp_ok.items()), flush=True)
            else:
                train(model, lambda r: r.choice(en_goals_all), S1, r)
                train(model, lambda r: r.choice(en_goals_all) if r.random() < 0.2 else r.choice(en_scene), S2, r)
                replay = en_goals_all
            train(model, lambda r: r.choice(few) if r.random() < 0.5 else (r.choice(replay) if r.random() < 0.4 else r.choice(en_scene)), S3, r)
            res = evaluate(model, tests)
            results.append({"seed": seed, "cond": cond, "res": res}); say(cond, res)
            if cond == "tp":
                log = rl(model, RL_STEPS, random.Random(77 + seed))
                res = evaluate(model, tests)
                results.append({"seed": seed, "cond": "tp + RL", "res": res, "rl_log": log}); say("tp + RL", res)
                m = st.mean(v["success"] for v in res.values())
                if m > best[0]:
                    best = (m, {k: v.detach().clone() for k, v in model.state_dict().items()}, seed)
        json.dump(results, open("goals_results.json", "w"), indent=1)
    model = make_model(); model.load_state_dict(best[1])
    print(f"exporting tp + RL from seed {best[2]} (mean success {best[0]*100:.0f}%)")
    diff = export(model)
    return results, diff


def report(R, diff=None):
    pct = lambda v: "–" if v is None else f"{v*100:.0f}%"
    conds = ["tp", "tp + RL", "reference"]
    L = ["# Goals + lookup, run 3: results", "",
         f"{len({r['seed'] for r in R})} seeds, {NTEST} test episodes per split, {N_EN} English plans in the last stage.",
         "Success = the model's own plan, run in the world, gets the goal.", ""]
    tpr = [r["res"] for r in R if r["cond"] == "tp-in-simple-language"]
    if tpr:
        L += ["Plans in the simple language before English (exact match): " + ", ".join(f"{sp} {st.mean(x[sp] for x in tpr)*100:.0f}%" for sp in tpr[0]), ""]
    L += ["| model | iid | combo (hidden + locked) | long (4–5 obstacles) | looked up when needed | looked up when not needed |", "|---|---|---|---|---|---|"]
    for c in conds:
        rows = [r["res"] for r in R if r["cond"] == c]
        if not rows:
            continue
        m = lambda sp, k: st.mean([x[sp][k] for x in rows if x[sp][k] is not None])
        need = st.mean([m(sp, "looked_when_needed") for sp in ("iid", "combo", "long") if any(x[sp]["looked_when_needed"] is not None for x in rows)])
        notn = st.mean([m(sp, "looked_when_not") for sp in ("iid", "combo", "long")])
        L.append(f"| {c} | {pct(m('iid','success'))} | {pct(m('combo','success'))} | {pct(m('long','success'))} | {pct(need)} | {pct(notn)} |")
    L += ["", "## RL, per seed (mean success over splits, before → after)", ""]
    for s in sorted({r["seed"] for r in R}):
        g = lambda c: [st.mean(v["success"] for v in r["res"].values()) for r in R if r["seed"] == s and r["cond"] == c]
        if g("tp") and g("tp + RL"):
            L.append(f"- seed {s}: {g('tp')[0]*100:.0f}% → {g('tp + RL')[0]*100:.0f}%")
    L += ["", "## Why plans failed", ""]
    for c in conds:
        why = {}
        for r in R:
            if r["cond"] == c:
                for v in r["res"].values():
                    for k, n_ in v["fails"].items():
                        why[k] = why.get(k, 0) + n_
        L.append(f"- {c}: " + ", ".join(f"{k} {v}" for k, v in sorted(why.items(), key=lambda x: -x[1])))
    if diff is not None:
        L += ["", f"Export check (HF vs llama.cpp-style forward, max logit difference): {diff:.1e}"]
    text = "\n".join(L) + "\n"
    open("GOALS_RESULTS.md", "w").write(text)
    print(text)


# %%
if __name__ == "__main__" or "ipykernel" in sys.modules:
    if "--show" in sys.argv:
        r = random.Random(1)
        ep = make_episode(r, frozenset({"H", "L", "KC"}))
        for lang in ("en", "tp", "mix"):
            print(" ".join(t for t, _ in render(ep, lang, r)), "\n")
    elif "--no-run" not in sys.argv:
        R, diff = run()
        report(R, diff)
