# %% [markdown]
# # Goals + lookup: does toki pona first make a small model plan better in English?
#
# Every episode is a little goal problem: someone wants something, there may be
# obstacles (closed or locked doors, a key somewhere else, a missing fact, a choice),
# and the model writes its plan step by step. When a fact is missing it can call a
# lookup tool (`search : where is the bread ?`); the harness answers.
#
# **Conditions** (same model, same number of training steps):
# - `tp`: goal episodes in toki pona → mixed plans (toki pona grammar, English words swapped in) → a few English goal episodes
# - `english`: plain English scenes (no goals) → the same few English goal episodes
# - `reference`: English goal episodes all along (an upper bound, not a fair rival)
#
# **Tests** (English, the model writes the whole plan and the world checks it):
# - `iid`: new episodes like the English training ones
# - `combo`: a hidden fact *and* a locked door together, never seen in English training
# - `long`: 4–5 obstacles, longer than anything in any training data
#
# Run 2: the bridge now mixes whole plans, not just loose sentences, so toki pona's plan skeleton
# (la, tan ni, alasa) is used with English words before the model meets English plans.
# Also checks that the tp model really plans in toki pona.
#
# On Kaggle: Settings → Accelerator → GPU (T4), then Run All. Takes roughly an hour on a T4.
# At the end it prints a report; paste that back to Claude.

# %%
import json, math, random, re, statistics as st, sys, time
import torch
import torch.nn as nn
import torch.nn.functional as F

QUICK = "--quick" in sys.argv          # tiny CPU smoke test
DEV = "cuda" if torch.cuda.is_available() else "cpu"
if DEV == "cpu":
    torch.set_num_threads(2)

if QUICK:
    D, LAYERS, HEADS, CTX = 64, 2, 4, 256
    S1, S2, S3, SEEDS, NS, NTEST, BATCH = 60, 30, 30, [0], [16], 20, 16
else:
    D, LAYERS, HEADS, CTX = 192, 8, 6, 256   # about 3.6M parameters: deep and thin
    S1, S2, S3, SEEDS, NS, NTEST, BATCH = 3000, 1500, 1500, [0, 1, 2], [64, 256, 1024], 200, 64
LR = 6e-4
AMP = dict(device_type=DEV, dtype=torch.float16 if DEV == "cuda" else torch.bfloat16, enabled=DEV == "cuda")
COND = ["tp", "english", "reference"]

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
    if k == "search": return [(f"alasa : {T(s[1])} li lon seme ?", True), (f"sona : {T(s[1])} li lon {T(s[2])} .", False)]
    if k == "choose": return [(f"{T(s[1])} li {T('wants')} e {T(s[2])} tan ni : {T(s[2])} li {T(s[3])} .", True)]
    if k == "needkey": return [(f"{tp_door(s[2])} li {T('locked')} la {T(s[1])} li {T('wants')} e {T('key')} .", True)]
    if k == "go": return [(f"{T(s[1])} li lon ala {T(s[2])} la {T(s[1])} li {T('goes')} {T(s[2])} .", True)]
    if k == "open": return [(f"{tp_door(s[2])} li {T('closed')} la {T(s[1])} li {T('opens')} e {tp_door(s[2])} .", True)]
    if k == "unlock": return [(f"{tp_door(s[2])} li {T('locked')} la {T(s[1])} li {T('opens')} e {tp_door(s[2])} kepeken {T('key')} .", True)]
    if k == "take": return [(f"{T(s[1])} li {T('takes')} e {T(s[2])} .", True)]
    if k == "check": return [(f"{T(s[1])} li {T('has')} e {T(s[2])} la wile li pini .", True)]
    if k == "done": return [("ale li pini .", True)]
    raise ValueError(s)


def prompt_text(ep, lang="en"):
    fact = en_fact if lang == "en" else tp_fact
    return " ".join(fact(f) for f in ep["facts"] + [ep["goal"]]) + (" plan :" if lang == "en" else " nasin :")


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
# ## Model: a small GPT

# %%
class Block(nn.Module):
    def __init__(self):
        super().__init__()
        self.ln1, self.ln2 = nn.LayerNorm(D), nn.LayerNorm(D)
        self.qkv, self.proj = nn.Linear(D, 3 * D), nn.Linear(D, D)
        self.up, self.down = nn.Linear(D, 4 * D), nn.Linear(4 * D, D)

    def forward(self, h):
        B, T, _ = h.shape
        q, k, v = self.qkv(self.ln1(h)).view(B, T, 3, HEADS, D // HEADS).permute(2, 0, 3, 1, 4)
        a = F.scaled_dot_product_attention(q, k, v, is_causal=True)
        h = h + self.proj(a.transpose(1, 2).reshape(B, T, D))
        return h + self.down(F.gelu(self.up(self.ln2(h))))


class GPT(nn.Module):
    def __init__(self, V):
        super().__init__()
        self.emb = nn.Embedding(V, D)
        self.pos = nn.Parameter(torch.zeros(CTX, D))
        self.blocks = nn.ModuleList(Block() for _ in range(LAYERS))
        self.ln = nn.LayerNorm(D)
        self.apply(self._init)

    @staticmethod
    def _init(m):
        if isinstance(m, (nn.Linear, nn.Embedding)):
            nn.init.normal_(m.weight, std=0.02)
        if isinstance(m, nn.Linear) and m.bias is not None:
            nn.init.zeros_(m.bias)

    def forward(self, x):
        h = self.emb(x) + self.pos[: x.shape[1]]
        for b in self.blocks:
            h = b(h)
        return self.ln(h) @ self.emb.weight.T


# %% [markdown]
# ## Data → tensors, training

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
    return ["<pad>"] + sorted(words)


VOCAB = build_vocab()
STOI = {w: i for i, w in enumerate(VOCAB)}


def encode(segs):
    ids, m = [], []
    for t, train in segs:
        w = [STOI[x] for x in t.split()]
        ids += w; m += [train] * len(w)
    return ids[:CTX + 1], m[:CTX + 1]


def batch(items):
    L = max(len(i) for i, _ in items)
    x = torch.zeros(len(items), L - 1, dtype=torch.long)
    y = torch.zeros(len(items), L - 1, dtype=torch.long)
    w = torch.zeros(len(items), L - 1)
    for b, (ids, m) in enumerate(items):
        n = len(ids) - 1
        x[b, :n] = torch.tensor(ids[:-1]); y[b, :n] = torch.tensor(ids[1:]); w[b, :n] = torch.tensor(m[1:], dtype=torch.float)
    return x.to(DEV), y.to(DEV), w.to(DEV)


def train(model, sampler, steps, r):
    opt = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=0.1, betas=(0.9, 0.95))
    try:
        scaler = torch.amp.GradScaler("cuda", enabled=DEV == "cuda")
    except (AttributeError, TypeError):
        scaler = torch.cuda.amp.GradScaler(enabled=DEV == "cuda")
    model.train()
    for step in range(steps):
        lr = LR * min(1, (step + 1) / 100) * (0.1 + 0.9 * 0.5 * (1 + math.cos(math.pi * step / steps)))
        for g in opt.param_groups:
            g["lr"] = lr
        x, y, w = batch([sampler(r) for _ in range(BATCH)])
        with torch.autocast(**AMP):
            logits = model(x)
        loss = (F.cross_entropy(logits.float().reshape(-1, len(VOCAB)), y.reshape(-1), reduction="none") * w.reshape(-1)).sum() / w.sum()
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
def run_plans(model, eps, max_new=200, lang="en"):
    model.eval()
    seqs = [[STOI[w] for w in prompt_text(ep, lang).split()] for ep in eps]
    sims = [(Sim if lang == "en" else TpSim)(ep) for ep in eps]
    sent = [[] for _ in eps]
    active = list(range(len(eps)))
    for _ in range(max_new):
        active = [i for i in active if sims[i].status is None and len(seqs[i]) < CTX]
        if not active:
            break
        L = max(len(seqs[i]) for i in active)
        x = torch.zeros(len(active), L, dtype=torch.long)
        for b, i in enumerate(active):
            x[b, : len(seqs[i])] = torch.tensor(seqs[i])
        with torch.autocast(**AMP):
            logits = model(x.to(DEV))
        last = torch.tensor([len(seqs[i]) - 1 for i in active], device=DEV)
        nxt = logits[torch.arange(len(active), device=DEV), last].argmax(-1).tolist()
        for i, t in zip(active, nxt):
            seqs[i].append(t)
            w = VOCAB[t]
            sent[i].append(w)
            if w in (".", "?"):
                inject = sims[i].step(" ".join(sent[i]))
                sent[i] = []
                if inject:
                    seqs[i] += [STOI[x] for x in inject.split()]
    for s in sims:
        if s.status is None:
            s.fail("too long")
    return sims


def score(sims):
    ok = [s.status == "ok" for s in sims]
    need = [s for s in sims if "H" in s.ep["obs"] or "KH" in s.ep["obs"]]
    needed = lambda s: ({s.ep["target"]} if "H" in s.ep["obs"] else set()) | ({"key"} if "KH" in s.ep["obs"] else set())
    look_when_needed = [needed(s) <= s.searched for s in need]
    look_when_not = [bool(s.searched - needed(s)) for s in sims]
    why = {}
    for s in sims:
        if s.status != "ok":
            why[s.why] = why.get(s.why, 0) + 1
    return {"success": st.mean(ok), "looked_when_needed": st.mean(look_when_needed) if need else None,
            "looked_when_not": st.mean(look_when_not), "fails": why}


def test_sets():
    r = random.Random(12345)
    out = {}
    for split in ("iid", "combo", "long"):
        cs = [c for c in COMBOS if split_of(c) == split and (split == "long" or len(c) <= 3)]
        out[split] = episodes(r, NTEST, cs)
    return out


# %% [markdown]
# ## Run everything

# %%
def run():
    t0 = time.time()
    tests = test_sets()
    n_params = sum(p.numel() for p in GPT(len(VOCAB)).parameters())
    print(f"device {DEV}, vocab {len(VOCAB)}, params {n_params/1e6:.2f}M", flush=True)
    results = []
    for seed in SEEDS:
        dr = random.Random(1000 + seed)
        tp_goals = [encode(render(e, "tp")) for e in episodes(dr, 20000, TRAIN_COMBOS)]
        en_goals_all = [encode(render(e, "en")) for e in episodes(dr, 20000, TRAIN_COMBOS)]
        en_scene = [encode([(scene(dr), True)]) for _ in range(20000)]
        mixed_scene = [encode([(mix(scene(dr), dr), True)]) for _ in range(20000)]
        mixed_goals = [encode(render(e, "mix", dr)) for e in episodes(dr, 20000, TRAIN_COMBOS)]
        pick = lambda pool: (lambda r: r.choice(pool))
        for cond in COND:
            torch.manual_seed(seed)
            base = GPT(len(VOCAB)).to(DEV)
            r = random.Random(seed)
            if cond == "tp":
                train(base, pick(tp_goals), S1, r)
                train(base, lambda r: r.choice(mixed_goals) if r.random() < 0.6 else
                      (r.choice(tp_goals) if r.random() < 0.5 else r.choice(mixed_scene)), S2, r)
                replay = tp_goals + mixed_goals
                tp_ok = {sp: st.mean(x.status == "ok" for x in run_plans(base, eps, lang="tp")) for sp, eps in tests.items() if sp != "long"}
                results.append({"seed": seed, "cond": "tp-in-toki-pona", "res": tp_ok})
                print(f"seed {seed} toki pona plans (exact): " + "  ".join(f"{k} {v*100:.0f}%" for k, v in tp_ok.items()), flush=True)
            elif cond == "english":
                train(base, pick(en_scene), S1 + S2, r)
                replay = en_scene
            else:
                train(base, pick(en_goals_all), S1, r)
                train(base, lambda r: r.choice(en_goals_all) if r.random() < 0.2 else r.choice(en_scene), S2, r)
                replay = en_goals_all
            state = {k: v.clone() for k, v in base.state_dict().items()}
            for n in NS:
                er = random.Random(5000 + seed * 100 + n)
                few = [encode(render(e, "en")) for e in episodes(er, n, EN_COMBOS)]
                model = GPT(len(VOCAB)).to(DEV); model.load_state_dict(state)
                rr = random.Random(seed * 7 + n)
                samp = lambda r: r.choice(few) if r.random() < 0.5 else (r.choice(replay) if r.random() < 0.4 else r.choice(en_scene))
                train(model, samp, S3, rr)
                res = {split: score(run_plans(model, eps)) for split, eps in tests.items()}
                results.append({"seed": seed, "cond": cond, "n": n, "res": res})
                print(f"seed {seed} {cond:9} N={n:<4} " + "  ".join(f"{k} {v['success']*100:3.0f}%" for k, v in res.items())
                      + f"   ({time.time()-t0:.0f}s)", flush=True)
        json.dump(results, open("goals_results.json", "w"), indent=1)
    return results


def report(R):
    pct = lambda v: "–" if v is None else f"{v*100:.0f}%"
    L = ["# Goals + lookup: results", "",
         f"{len({r['seed'] for r in R})} seeds, {NTEST} test episodes per split. N = English goal episodes in the last stage.",
         "Success = the model's own plan, run in the world, gets the goal.", ""]
    tpr = [r["res"] for r in R if r["cond"] == "tp-in-toki-pona"]
    if tpr:
        L += ["## Sanity check: the tp model planning in toki pona (exact match with the gold plan, before English)", ""]
        L += ["- " + ", ".join(f"{sp} {st.mean(x[sp] for x in tpr)*100:.0f}%" for sp in tpr[0]), ""]
    R = [r for r in R if r["cond"] != "tp-in-toki-pona"]
    for n in NS:
        L += [f"## N = {n}", "", "| condition | iid | combo (hidden + locked) | long (4–5 obstacles) | looked up when needed | looked up when not needed |",
              "|---|---|---|---|---|---|"]
        for c in COND:
            rows = [r["res"] for r in R if r["cond"] == c and r["n"] == n]
            if not rows:
                continue
            m = lambda sp, k: st.mean([x[sp][k] for x in rows if x[sp][k] is not None]) if any(x[sp][k] is not None for x in rows) else None
            need = st.mean([m(sp, "looked_when_needed") for sp in ("iid", "combo", "long") if m(sp, "looked_when_needed") is not None])
            notn = st.mean([m(sp, "looked_when_not") for sp in ("iid", "combo", "long")])
            L.append(f"| {c} | {pct(m('iid','success'))} | {pct(m('combo','success'))} | {pct(m('long','success'))} | {pct(need)} | {pct(notn)} |")
        L.append("")
    L += ["## tp vs english, per seed (mean success over the three splits)", ""]
    for n in NS:
        d = []
        for s in sorted({r["seed"] for r in R}):
            g = lambda c: [st.mean(v["success"] for v in r["res"].values()) for r in R if r["seed"] == s and r["n"] == n and r["cond"] == c]
            if g("tp") and g("english"):
                d.append(g("tp")[0] - g("english")[0])
        if d:
            L.append(f"- N={n}: tp ahead by {st.mean(d)*100:+.1f} points, better in {sum(x > 0 for x in d)}/{len(d)} seeds")
    L += ["", "## Why plans failed (all seeds, N, splits)", ""]
    for c in COND:
        why = {}
        for r in R:
            if r["cond"] == c:
                for v in r["res"].values():
                    for k, n_ in v["fails"].items():
                        why[k] = why.get(k, 0) + n_
        L.append(f"- {c}: " + ", ".join(f"{k} {v}" for k, v in sorted(why.items(), key=lambda x: -x[1])))
    text = "\n".join(L) + "\n"
    open("GOALS_RESULTS.md", "w").write(text)
    print(text)


# %%
if __name__ == "__main__" or "ipykernel" in sys.modules:
    if "--show" in sys.argv:
        r = random.Random(1)
        for c in [frozenset(), frozenset({"H", "L", "KC"}), frozenset({"S", "C"})]:
            ep = make_episode(r, c)
            print(" ".join(t for t, _ in render(ep, "en")), "\n", " ".join(t for t, _ in render(ep, "tp")), "\n")
        print(mix(scene(r), r))
    else:
        report(run())
