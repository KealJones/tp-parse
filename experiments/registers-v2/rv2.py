"""Registers v2: state slots carried alongside a small planner, now with a goal slot, every-word updates,
a teacher-free variant and a messy-input test. Same skins world as experiments/skins and experiments/registers.

  python rv2.py worker --gpu 0 --jobs base:0,taught-every:1 --steps 8000 --ntest 50 --tag full
  python rv2.py report

The Kaggle notebook (registers_v2.ipynb) writes this file out, runs a short pilot on both GPUs, then the
full run split across the GPUs, then the report.
"""
import json, math, os, random, re, statistics as st, sys, time

if "--gpu" in sys.argv:                      # pick the GPU before torch starts
    os.environ["CUDA_VISIBLE_DEVICES"] = sys.argv[sys.argv.index("--gpu") + 1]

import torch
import torch.nn as nn
import torch.nn.functional as F

DEV = "cuda" if torch.cuda.is_available() else "cpu"
if DEV == "cpu":
    torch.set_num_threads(2)

D, LAYERS, HEADS, K, R, CTX = 192, 8, 6, 8, 32, 256      # about 3.6M parameters, as in the earlier runs
PAIRS, LR = 32, 6e-4
REG_AT = LAYERS // 2           # registers are written from, and read into, the state entering this block
LAM_STATE = 0.5                # simulator teaching (taught-*), faded out between FADE[0] and FADE[1] of training
FADE = (0.5, 0.8)
LAM_SELF = 0.5                 # teacher-free signal (self-every): from the slots alone, predict the next sentence's words
AMP = dict(device_type=DEV, dtype=torch.float16 if DEV == "cuda" else torch.bfloat16, enabled=DEV == "cuda")

CONDS = {
    "base": dict(regs=None),                                   # plain GPT
    "taught-ends": dict(regs="ends", teach=True),              # slots update at sentence ends, taught by the simulator
    "taught-every": dict(regs="every", teach=True),            # slots update at every word, taught by the simulator
    "self-every": dict(regs="every", self_teach=True),         # slots update at every word, no simulator: predict what comes next
}
COND_ORDER = list(CONDS)

# %% [markdown]
# ## Skins
#
# Every skin gives one word for each job, in the same order, so a plan in one skin turns into the
# same plan in another skin word for word. Home is the canonical skin the world is written in.

# %%
ROLE_SLOTS = (["agent"] * 2 + ["doorplace"] * 3 + ["openplace"] * 2 + ["item"] * 5 + ["prop"] * 4
              + ["key", "door", "go", "open", "take", "has", "want", "need"])
SKINS = {
    "home": "person child | house shop school forest field | bread fruit water fish book | sweet hot cold big | key door goes opens takes has wants needs",
    "computer": "user admin | folder drive server desktop inbox | file photo song video note | small new old shared | password lock navigates accesses copies owns requests requires",
    "ship": "captain sailor | port harbor dock sea bay | cargo rope sail net map | heavy dry wet long | permit gate sails raises loads carries seeks demands",
    "kitchen": "cook helper | pantry fridge oven counter sink | egg flour milk salt butter | fresh warm sour salty | opener lid walks lifts grabs holds craves misses",
    "farm": "farmer worker | barn shed stable meadow orchard | hay corn wool apple seed | ripe green soft tall | crowbar hatch drives pries picks keeps desires lacks",
    "space": "pilot robot | station module lab orbit crater | fuel crystal sample battery probe | rare bright frozen dense | keycard airlock flies cycles collects stores targets awaits",
}
SKINS = {s: v.replace("|", " ").split() for s, v in SKINS.items()}
PLAN_SKINS = ["home", "computer", "ship", "kitchen"]
UNSEEN = ["farm", "space"]
ALL_SKINS = PLAN_SKINS + UNSEEN
CANON = SKINS["home"]
C2S = {s: dict(zip(CANON, w)) for s, w in SKINS.items()}          # home word → skin word
S2C = {s: dict(zip(w, CANON)) for s, w in SKINS.items()}          # skin word → home word
JOB = dict(zip(CANON, ROLE_SLOTS))                                # home word → its job
SKIN_WORDS = {s: set(w) for s, w in SKINS.items()}
ALL_SKIN_WORDS = set().union(*SKIN_WORDS.values())
assert all(len(w) == len(ROLE_SLOTS) for w in SKINS.values())
assert len(ALL_SKIN_WORDS) == len(SKINS) * len(ROLE_SLOTS), "a word is used by two skins"


def to_skin(text, skin):
    return " ".join(C2S[skin].get(w, w) for w in text.split())


def to_home(words, skin):
    return " ".join(S2C[skin].get(w, w) for w in words)


# %% [markdown]
# ## The world (written in home words, then dressed in a skin)

# %%
AGENTS, PLACE_N, ITEM_N, PROP_N = CANON[0:2], CANON[2:7], CANON[7:12], CANON[12:16]
DOOR_PLACES = PLACE_N[:3]
HAS_DOOR = {p: p in DOOR_PLACES for p in PLACE_N}

# obstacle combos: H hidden target, C closed / L locked target door, KH hidden key, KC key behind closed door, S choice
COMBOS = []
for H in (0, 1):
    for door in ("", "C", "L"):
        for KH in ((0, 1) if door == "L" else (0,)):
            for KC in ((0, 1) if door == "L" else (0,)):
                for S in (0, 1):
                    COMBOS.append(frozenset(o for o, on in [("H", H), (door, door), ("KH", KH), ("KC", KC), ("S", S)] if on))
SHORT = [c for c in COMBOS if len(c) <= 3]
LONG = [c for c in COMBOS if len(c) >= 4]


def make_episode(r, obs):
    """Sample a concrete world for an obstacle set. Returns the true state, what's told, and the gold plan."""
    agent = r.choice(AGENTS)
    door = "L" if "L" in obs else "C" if "C" in obs else ""
    tplace = r.choice(DOOR_PLACES) if door else r.choice(PLACE_N)
    doors = {p: "open" for p in DOOR_PLACES}
    if door:
        doors[tplace] = "closed" if door == "C" else "locked"
    loc, told_loc = {}, {}
    if "S" in obs:
        cands = r.sample(ITEM_N, r.choice((2, 3)))
        target, prop = cands[0], r.choice(PROP_N)
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
    told_doors = {p: doors[p] for p in DOOR_PLACES if p == tplace or p == kplace or r.random() < 0.3}
    facts = [("at", agent, start)] + [("loc", i, p) for i, p in told_loc.items()] + \
            [("door", p, s) for p, s in told_doors.items()]
    if "S" in obs:
        facts += [("prop", c, prop, c == target) for c in cands]
    r.shuffle(facts)
    goal = ("wantprop", agent, prop) if "S" in obs else ("want", agent, target)

    plan, here = [], start

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
    return {"obs": obs, "agent": agent, "start": start, "loc": loc, "doors": doors,
            "target": target, "prop": prop, "facts": facts, "goal": goal, "plan": plan}


def fact_text(f):
    k = f[0]
    if k in ("at", "loc"): return f"the {f[1]} is at the {f[2]} ."
    if k == "door": return f"the door of the {f[1]} is {f[2]} ."
    if k == "prop": return f"the {f[1]} is {f[2]} ." if f[3] else f"the {f[1]} is not {f[2]} ."
    if k == "want": return f"the {f[1]} wants the {f[2]} ."
    if k == "wantprop": return f"the {f[1]} wants a {f[2]} thing ."
    raise ValueError(f)


def step_text(s):
    """Plan step → [(text, trained-on)]. Search results come from the harness, so they're not trained on."""
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


def prompt_text(ep):
    return " ".join(fact_text(f) for f in ep["facts"] + [ep["goal"]]) + " plan :"


def render(ep):
    segs = [(prompt_text(ep), True)]
    for s in ep["plan"]:
        segs += step_text(s)
    return segs


def scene(r, n=None):
    """Loose sentences with the same words, but no goals, no 'so', 'because', search or plans."""
    out = []
    for _ in range(n or r.randint(4, 7)):
        a, p, i = r.choice(AGENTS), r.choice(PLACE_N), r.choice(ITEM_N + ["key"])
        pr, dp = r.choice(PROP_N), r.choice(DOOR_PLACES)
        out.append(r.choice([
            f"the {a} is at the {p} .", f"the {i} is at the {p} .", f"the {a} is not at the {p} .",
            f"the door of the {dp} is {r.choice(['open', 'closed', 'locked'])} .", f"the {i} is {pr} .",
            f"the {i} is not {pr} .", f"the {a} wants the {i} .", f"the {a} wants a {pr} thing .",
            f"the {a} goes to the {p} .", f"the {a} opens the door of the {dp} .", f"the {a} takes the {i} .",
            f"the {a} has the {i} .", f"the {a} needs the key .", f"the {a} opens the door of the {dp} with the key ."]))
    return " ".join(out)


def episodes(r, n, allowed):
    return [make_episode(r, r.choice(allowed)) for _ in range(n)]


# %% [markdown]
# ## The checker: runs the model's plan in the world, answering searches
#
# The model writes in a skin. Each finished sentence is turned back into home words and run in the
# world. A word from a different skin (say "house" in a space plan) is its own kind of failure.

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
    def __init__(self, ep, skin="home"):
        self.ep, self.skin, self.here, self.doors, self.held = ep, skin, ep["start"], dict(ep["doors"]), set()
        self.chosen = None if ep["prop"] else ep["target"]
        self.searched, self.status, self.why, self.text = set(), None, "", ""

    def fail(self, why):
        self.status, self.why = "fail", why

    def step(self, words):
        """Run one finished sentence (a list of skin words). Returns skin text to inject (a search result) or None."""
        if any(w in ALL_SKIN_WORDS and w not in SKIN_WORDS[self.skin] for w in words):
            return self.fail("another skin's word")
        sent = to_home(words, self.skin)
        inject = self._step(sent)
        return to_skin(inject, self.skin) if inject else None

    def _step(self, sent):
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
            if ep["loc"].get(g[1]) != self.here or self.doors.get(self.here, "open") != "open":
                return self.fail("bad take")
            self.held.add(g[1])
        elif kind == "check":
            if g[1] not in self.held:
                return self.fail("false claim")
        return None


def needed(s):
    o = s.ep["obs"]
    return ({s.ep["target"]} if "H" in o else set()) | ({"key"} if "KH" in o else set())


def score(sims):
    need = [s for s in sims if needed(s)]
    why = {}
    for s in sims:
        if s.status != "ok":
            why[s.why] = why.get(s.why, 0) + 1
    return {"success": st.mean(s.status == "ok" for s in sims),
            "looked_when_needed": st.mean(needed(s) <= s.searched for s in need) if need else None, "fails": why}


# %% [markdown]
# ## Vocabulary
#
# One token per word. A plan in one skin and the same plan in another skin are the same length and
# line up token for token. Each word also has a job (agent, place, item, verb…), used by the analogy tools in the skins run.

# %%
def build_vocab():
    r = random.Random(0)
    words = set(ALL_SKIN_WORDS)
    for c in COMBOS:
        for _ in range(30):
            for t, _ in render(make_episode(r, c)):
                words |= set(t.split())
    for _ in range(300):
        words |= set(scene(r).split())
    return sorted(words)


VOCAB = build_vocab()
STOI = {w: i for i, w in enumerate(VOCAB)}
V = len(VOCAB)
SHARED = sorted(set(VOCAB) - ALL_SKIN_WORDS)
JOBS = sorted(set(ROLE_SLOTS)) + SHARED
JOB_ID = {j: i for i, j in enumerate(JOBS)}
# home-word id → job id;  home-word id → the same word's id in each skin
JOB_OF = [JOB_ID[JOB.get(w, w)] if (w in JOB or w in SHARED) else -1 for w in VOCAB]
SKIN_MAP = {s: [STOI[C2S[s].get(w, w)] for w in VOCAB] for s in SKINS}


def encode(segs):
    """Home-word segments → (ids, trained-on mask)."""
    ids, m = [], []
    for t, train in segs:
        w = [STOI[x] for x in t.split()]
        ids += w; m += [train] * len(w)
    return ids[:CTX + 1], m[:CTX + 1]



# %% [markdown]
# ## State labels and teacher-free targets

# %%
SLOT_CLASSES = [5, 4, 4, 5]            # where the agent is, what it holds, the door where it stands, which item is the goal
NO_LAB = (-1, -1, -1, -1)
END_IDS = torch.tensor([STOI["."], STOI["?"]])
END_SET = {STOI["."], STOI["?"]}
CONTENT_ID = {STOI[w]: i for i, w in enumerate(CANON)}   # home-skin words (agents, places, items, props, verbs…)
NC = len(CANON)


def encode_labeled(ep):
    """Home-word plan → (ids, trained-on mask, per-token state labels). Same ids as encode(render(ep))."""
    known = {f[1]: f[2] for f in ep["facts"] if f[0] == "door"}
    loc, held, goal = ep["start"], set(), ITEM_N.index(ep["target"])
    ids, m, labs = [], [], []

    def lab():
        door = 0 if not HAS_DOOR[loc] else {"open": 1, "closed": 2, "locked": 3}.get(known.get(loc), -1)
        return (PLACE_N.index(loc), 2 * ("key" in held) + (ep["target"] in held), door, goal)

    def add(text, train, label):
        w = [STOI[x] for x in text.split()]
        ids.extend(w); m.extend([train] * len(w)); labs.extend([NO_LAB] * (len(w) - 1) + [label])

    for f in ep["facts"]:
        add(fact_text(f), True, NO_LAB)
    add(fact_text(ep["goal"]), True, lab())
    add("plan :", True, NO_LAB)
    for s in ep["plan"]:
        if s[0] == "go":
            loc = s[2]
        elif s[0] in ("open", "unlock"):
            known[s[2]] = "open"
        elif s[0] == "take":
            held.add(s[2])
        for text, train in step_text(s):
            add(text, train, lab())
    return ids[:CTX + 1], m[:CTX + 1], labs[:CTX + 1]


def encode_scene(text):
    ids, m = encode([(text, True)])
    return ids, m, [NO_LAB] * len(ids)


def next_sentence_words(ids):
    """For each sentence end at position p: the content words (home-skin, by role) of the sentence after it."""
    ends = [p for p, t in enumerate(ids) if t in END_SET]
    out = {}
    for a, b in zip(ends, ends[1:]):
        words = sorted({CONTENT_ID[t] for t in ids[a + 1:b + 1] if t in CONTENT_ID})
        if words:
            out[a] = words
    return out


# %% [markdown]
# ## Model: a small GPT, optionally with state registers
#
# K slots of R numbers ride alongside the text, entering at block REG_AT. At each token the model's state there
# proposes new slot contents and a keep-gate per number; the slots move toward the proposal by (1 − gate):
# s ← g·s + (1 − g)·c. In `ends` mode the gate is forced to "keep" except on "." and "?", so slots change only
# at sentence ends. In `every` mode any token can write. Every token then reads the slots (attention over
# the K slots) and adds what it read back in. The gates and proposals come from the state at REG_AT only,
# so the lower half runs in parallel and only this small update steps through the tokens.

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


class Registers(nn.Module):
    def __init__(self, mode):
        super().__init__()
        self.mode = mode
        self.w_ln, self.w_gate, self.w_new = nn.LayerNorm(D), nn.Linear(D, K * R), nn.Linear(D, K * R)
        self.s0 = nn.Parameter(torch.zeros(K, R))
        self.r_ln, self.r_q, self.r_out = nn.LayerNorm(D), nn.Linear(D, R), nn.Linear(R, D)
        self.heads = nn.ModuleList(nn.Linear(R, c) for c in SLOT_CLASSES)   # readouts of slots 0–3 (teaching only)
        self.next_head = nn.Linear(K * R, NC)                               # teacher-free readout (self-every only)

    def states(self, h, x):
        """Slot contents after each token: (B, T, K, R)."""
        B, T, _ = h.shape
        u = self.w_ln(h)
        g = torch.sigmoid(self.w_gate(u).float() + 2.0).view(B, T, K, R)    # starts mostly keeping
        c = torch.tanh(self.w_new(u).float()).view(B, T, K, R)
        if self.mode == "ends":
            m = (x.unsqueeze(-1) == END_IDS.to(x.device)).any(-1).float()[..., None, None]
            g = m * g + (1 - m)
        s = self.s0.float().unsqueeze(0).expand(B, K, R)
        out = []
        for t in range(T):
            s = torch.lerp(c[:, t], s, g[:, t])          # g·s + (1 − g)·c in one op
            out.append(s)
        return torch.stack(out, 1)

    def read(self, h, S):
        q = self.r_q(self.r_ln(h)).float()
        a = torch.softmax(torch.einsum("btkr,btr->btk", S, q) / R ** 0.5, -1)
        return self.r_out(torch.einsum("btk,btkr->btr", a, S))


class GPT(nn.Module):
    def __init__(self, regs=None):
        super().__init__()
        self.emb = nn.Embedding(V, D)
        self.pos = nn.Parameter(torch.zeros(CTX, D))
        self.blocks = nn.ModuleList(Block() for _ in range(LAYERS))
        self.ln = nn.LayerNorm(D)
        self.regs = Registers(regs) if regs else None
        self.apply(self._init)

    @staticmethod
    def _init(m):
        if isinstance(m, (nn.Linear, nn.Embedding)):
            nn.init.normal_(m.weight, std=0.02)
        if isinstance(m, nn.Linear) and m.bias is not None:
            nn.init.zeros_(m.bias)

    def forward(self, x, state=False):
        h = self.emb(x) + self.pos[: x.shape[1]]
        S = None
        for i, b in enumerate(self.blocks):
            if i == REG_AT and self.regs is not None:
                S = self.regs.states(h, x)
                h = h + self.regs.read(h, S)
            h = b(h)
        logits = self.ln(h) @ self.emb.weight.T
        return (logits, S) if state else logits


# %% [markdown]
# ## Training

# %%
def make_batch(items):
    """items: [(home ids, mask, labels, skin a, skin b)]. Rows 0..B-1 are skin a, rows B..2B-1 skin b."""
    B, L = len(items), max(len(i[0]) for i in items)
    X = torch.zeros(2 * B, L - 1, dtype=torch.long)
    Y = torch.zeros(2 * B, L - 1, dtype=torch.long)
    W = torch.zeros(2 * B, L - 1)
    LAB = torch.full((2 * B, L - 1, 4), -1, dtype=torch.long)
    NXT = torch.zeros(2 * B, L - 1, NC)
    NXM = torch.zeros(2 * B, L - 1)
    for b, (ids, m, labs, sa, sb) in enumerate(items):
        n = len(ids) - 1
        nxt = next_sentence_words(ids)
        for k, s in ((b, sa), (B + b, sb)):
            sid = [SKIN_MAP[s][t] for t in ids]
            X[k, :n] = torch.tensor(sid[:-1]); Y[k, :n] = torch.tensor(sid[1:])
            W[k, :n] = torch.tensor(m[1:], dtype=torch.float)
            LAB[k, :n] = torch.tensor(labs[:-1])
            for p, words in nxt.items():
                if p < n:
                    NXT[k, p, words] = 1.0
                    NXM[k, p] = 1.0
    return [t.to(DEV) for t in (X, Y, W, LAB, NXT, NXM)]


def state_loss(model, S, LAB):
    """Cross-entropy of slots 0–3 against the true state after each sentence. Returns (loss, accuracies)."""
    loss, acc = 0.0, []
    for k in range(4):
        y = LAB[..., k]
        mk = y >= 0
        if mk.any():
            lg = model.regs.heads[k](S[:, :, k][mk])
            loss = loss + F.cross_entropy(lg, y[mk])
            acc.append((lg.argmax(-1) == y[mk]).float().mean().item())
        else:
            acc.append(float("nan"))
    return loss, acc


def self_loss(model, S, NXT, NXM):
    mk = NXM > 0
    if not mk.any():
        return torch.zeros((), device=S.device)
    lg = model.regs.next_head(S.flatten(2)[mk])
    return F.binary_cross_entropy_with_logits(lg, NXT[mk])


def train(model, sampler, steps, r, teach=False, self_teach=False, log_every=500):
    opt = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=0.1, betas=(0.9, 0.95))
    try:
        scaler = torch.amp.GradScaler("cuda", enabled=DEV == "cuda")
    except (AttributeError, TypeError):
        scaler = torch.cuda.amp.GradScaler(enabled=DEV == "cuda")
    model.train()
    logs, t0 = [], time.time()
    for step in range(steps):
        frac = step / steps
        lr = LR * min(1, (step + 1) / 100) * (0.1 + 0.9 * 0.5 * (1 + math.cos(math.pi * frac)))
        for g in opt.param_groups:
            g["lr"] = lr
        lam = LAM_STATE * min(1.0, max(0.0, (FADE[1] - frac) / (FADE[1] - FADE[0]))) if teach else 0.0
        X, Y, W, LAB, NXT, NXM = make_batch([sampler(r) for _ in range(PAIRS)])
        with torch.autocast(**AMP):
            logits, S = model(X, state=True)
        lm = (F.cross_entropy(logits.float().reshape(-1, V), Y.reshape(-1), reduction="none") * W.reshape(-1)).sum() / W.sum()
        loss, acc, sl = lm, [float("nan")] * 4, 0.0
        if S is not None:
            if teach:
                st_loss, acc = state_loss(model, S, LAB)
                if lam > 0:
                    loss = loss + lam * st_loss
            if self_teach:
                sl_t = self_loss(model, S, NXT, NXM)
                loss = loss + LAM_SELF * sl_t
                sl = sl_t.item()
        if not torch.isfinite(loss):
            raise RuntimeError(f"loss is {loss.item()} at step {step}")
        opt.zero_grad(set_to_none=True)
        scaler.scale(loss).backward()
        scaler.unscale_(opt)
        nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        scaler.step(opt); scaler.update()
        logs.append((lm.item(), sl, *acc))
        if (step + 1) % log_every == 0:
            a = logs[-log_every:]
            line = f"    step {step+1}/{steps}  lm {st.mean(x[0] for x in a):.3f}"
            if self_teach:
                line += f"  next-words {st.mean(x[1] for x in a):.3f}"
            if teach:
                line += f"  teach {lam:.2f}  slots " + " ".join(
                    f"{st.mean([x[k] for x in a if x[k] == x[k]] or [0])*100:.0f}%" for k in (2, 3, 4, 5))
            print(line + f"  ({time.time()-t0:.0f}s)", flush=True)
    return logs


@torch.no_grad()
def slot_accuracy(model, eps, skins):
    """How well slots 0–3 read out the true state on gold plans, after training."""
    model.eval()
    acc = [[], [], [], []]
    for s in skins:
        for k in range(0, len(eps), 50):
            items = [encode_labeled(e) for e in eps[k:k + 50]]
            X, _, _, LAB, _, _ = make_batch([(i, m, l, s, s) for i, m, l in items])
            _, S = model(X, state=True)
            _, a = state_loss(model, S, LAB)
            for j in range(4):
                acc[j].append(a[j])
    return [st.mean([v for v in x if v == v] or [float("nan")]) for x in acc]


# %% [markdown]
# ## Running plans

# %%
def prompt_words(ep, skin, messy=False):
    """The problem in a skin. messy=True drops every period from the facts: one run-on line, no sentence ends."""
    words = to_skin(prompt_text(ep), skin).split()
    return [w for w in words if w != "."] if messy else words


@torch.no_grad()
def run_plans(model, eps, skin, messy=False, max_new=200):
    """The model writes plans in a skin; the checker runs each sentence and answers searches."""
    model.eval()
    seqs = [[STOI[w] for w in prompt_words(ep, skin, messy)] for ep in eps]
    start = [len(s) for s in seqs]
    sims = [Sim(ep, skin) for ep in eps]
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
            sent[i].append(VOCAB[t])
            if VOCAB[t] in (".", "?"):
                inject = sims[i].step(sent[i])
                sent[i] = []
                if inject:
                    seqs[i] += [STOI[w] for w in inject.split()]
    for i, s in enumerate(sims):
        if s.status is None:
            s.fail("too long")
        s.text = " ".join(VOCAB[t] for t in seqs[i][start[i]:])
    return sims


def test_sets(n):
    r = random.Random(12345)
    return {"short": episodes(r, n, SHORT), "long": episodes(r, n, LONG)}


def evaluate(model, tests, skins, messy=False):
    return {split: score(sum((run_plans(model, eps, s, messy) for s in skins), [])) for split, eps in tests.items()}


# %% [markdown]
# ## Workers and report

# %%
BOOKKEEPING = ("bad go", "bad take", "bad open", "bad unlock", "false claim")


def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def build_data(seed):
    dr = random.Random(1000 + seed)
    plans = [encode_labeled(e) for e in episodes(dr, 20000, SHORT)]
    scenes = [encode_scene(scene(dr)) for _ in range(20000)]
    return plans, scenes


def worker():
    jobs = sorted(((c, int(s)) for c, s in (j.split(":") for j in arg("--jobs").split(",") if j)), key=lambda j: (j[1], j[0]))
    steps, ntest, tag, gpu = int(arg("--steps", 8000)), int(arg("--ntest", 50)), arg("--tag", "full"), arg("--gpu", "0")
    out = f"{tag}_results_gpu{gpu}.jsonl"
    tests = test_sets(ntest)
    probe = episodes(random.Random(999), 100 if tag == "full" else 30, SHORT + LONG)
    show = next((e for e in tests["long"] if {"H", "L"} <= e["obs"]), tests["long"][0])
    print(f"worker gpu{gpu} ({DEV}, {torch.cuda.get_device_name(0) if DEV == 'cuda' else 'cpu'}): {len(jobs)} jobs, "
          f"{steps} steps, {ntest} test problems per split per skin", flush=True)
    data_seed, data = None, None
    for cond, seed in jobs:
        if seed != data_seed:
            data_seed, data = seed, build_data(seed)
        plans, scenes = data

        def sampler(r):
            if r.random() < 0.6:
                ids, m, labs = r.choice(plans)
                a, b = r.sample(PLAN_SKINS, 2)
            else:
                ids, m, labs = r.choice(scenes)
                a, b = r.sample(ALL_SKINS, 2)
            return ids, m, labs, a, b

        cfg = CONDS[cond]
        torch.manual_seed(seed)
        model = GPT(cfg["regs"]).to(DEV)
        print(f"== {cond} seed {seed}: {sum(p.numel() for p in model.parameters())/1e6:.3f}M params", flush=True)
        t0 = time.time()
        logs = train(model, sampler, steps, random.Random(seed), teach=cfg.get("teach", False),
                     self_teach=cfg.get("self_teach", False), log_every=max(100, steps // 10))
        row = {"tag": tag, "cond": cond, "seed": seed, "steps": steps, "train_s": round(time.time() - t0),
               "final_lm": st.mean(x[0] for x in logs[-200:])}
        t1 = time.time()
        row["seen"] = evaluate(model, tests, PLAN_SKINS)
        row["messy"] = evaluate(model, tests, PLAN_SKINS, messy=True)
        if cfg.get("teach"):
            row["slots_seen"] = slot_accuracy(model, probe, PLAN_SKINS)
            row["slots_unseen"] = slot_accuracy(model, probe, UNSEEN)
        if seed == 0:
            row["sample"] = {"problem": prompt_text(show), "clean": run_plans(model, [show], "home")[0].text,
                             "messy": run_plans(model, [show], "home", messy=True)[0].text}
        row["eval_s"] = round(time.time() - t1)
        with open(out, "a") as f:
            f.write(json.dumps(row) + "\n")
        pct = lambda d: " ".join(f"{k} {v['success']*100:.0f}%" for k, v in d.items())
        print(f"== {cond} seed {seed} done: seen {pct(row['seen'])} | messy {pct(row['messy'])} | lm {row['final_lm']:.3f} "
              f"| train {row['train_s']}s eval {row['eval_s']}s", flush=True)


def report():
    import glob
    R = [json.loads(l) for f in sorted(glob.glob("full_results_gpu*.jsonl")) for l in open(f)]
    P = [json.loads(l) for f in sorted(glob.glob("pilot_results_gpu*.jsonl")) for l in open(f)]
    pct = lambda v: "–" if v is None or v != v else f"{v*100:.0f}%"
    mean = lambda xs: st.mean(xs) if xs else float("nan")
    L = ["# Registers v2: results", ""]
    if os.path.exists("PILOT.md"):
        L += [open("PILOT.md").read().strip(), ""]
    if not R:
        L += ["The full run did not happen (see the pilot above)."]
    else:
        seeds = sorted({r["seed"] for r in R})
        L += [f"{len(seeds)} seeds, {R[0]['steps']} training steps per model. Seen skins only (home, computer, ship, kitchen).",
              "Success = the model's own plan, run in the world, gets the goal. Messy = the same problems with every period",
              "removed from the facts (one run-on line), never seen in training.", "",
              "| model | short | long | messy short | messy long | bookkeeping fails | wrong choice | final train loss |",
              "|---|---|---|---|---|---|---|---|"]
        for c in COND_ORDER:
            rows = [r for r in R if r["cond"] == c]
            if not rows:
                continue
            m = lambda key, sp: mean([x[key][sp]["success"] for x in rows])
            fails = lambda k: sum(v["fails"].get(k, 0) for x in rows for v in x["seen"].values())
            book = sum(fails(k) for k in BOOKKEEPING)
            L.append(f"| {c} | {pct(m('seen','short'))} | {pct(m('seen','long'))} | {pct(m('messy','short'))} | "
                     f"{pct(m('messy','long'))} | {book} | {fails('wrong choice')} | {mean([x['final_lm'] for x in rows]):.3f} |")
        L += ["", "## Per seed (seen long / messy long)", ""]
        for s in seeds:
            L.append(f"- seed {s}: " + ", ".join(f"{r['cond']} {pct(r['seen']['long']['success'])} / {pct(r['messy']['long']['success'])}"
                                                 for c in COND_ORDER for r in R if r["seed"] == s and r["cond"] == c))
        L += ["", "## Failures (seen, all seeds)", ""]
        for c in COND_ORDER:
            why = {}
            for r in R:
                if r["cond"] == c:
                    for v in r["seen"].values():
                        for k, n_ in v["fails"].items():
                            why[k] = why.get(k, 0) + n_
            L.append(f"- {c}: " + (", ".join(f"{k} {v}" for k, v in sorted(why.items(), key=lambda x: -x[1])) or "none"))
        trows = [r for r in R if "slots_seen" in r]
        if trows:
            L += ["", "## Do the taught slots still hold the true state? (gold plans, after teaching stopped)", "",
                  "| model, skins | where | holding | door here | goal item |", "|---|---|---|---|---|"]
            for c in ("taught-ends", "taught-every"):
                for key, name in (("slots_seen", "plan skins"), ("slots_unseen", "unseen skins")):
                    rs = [r[key] for r in trows if r["cond"] == c]
                    if rs:
                        L.append(f"| {c}, {name} | " + " | ".join(pct(mean([x[k] for x in rs])) for k in range(4)) + " |")
            L += ["", "Chance is about 20% / 25% / 25% / 20%."]
        L += ["", "## Time per model (seconds)", ""]
        for c in COND_ORDER:
            rows = [r for r in R if r["cond"] == c]
            if rows:
                L.append(f"- {c}: train {mean([r['train_s'] for r in rows]):.0f}, eval {mean([r['eval_s'] for r in rows]):.0f}")
        samples = [r for r in R if "sample" in r]
        if samples:
            L += ["", "## One long problem, seed 0 (home skin)", "", "Problem: " + samples[0]["sample"]["problem"], ""]
            for c in COND_ORDER:
                for r in samples:
                    if r["cond"] == c:
                        L.append(f"- {c}, clean: `{r['sample']['clean']}`")
                        L.append(f"- {c}, messy: `{r['sample']['messy']}`")
    text = "\n".join(L) + "\n"
    open("REGISTERS_V2_RESULTS.md", "w").write(text)
    print(text)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "worker":
        worker()
    elif cmd == "report":
        report()
    elif cmd != "--no-run":
        print(__doc__)
