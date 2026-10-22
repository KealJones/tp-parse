# %% [markdown]
# # Registers: give a small model a table to keep track of the world
#
# A planner has to know, at every step, where the agent is, what it's holding and which doors are
# open. A plain transformer has no table for that. It rebuilds the state at every word by looking
# back over the whole plan, which costs a small model a lot of its capacity.
#
# This run adds **state registers**: 8 small slots (32 numbers each) that are carried alongside the
# text. At the end of every sentence the slots are updated from what the model just read (a small
# GRU, so the state really is passed forward, not re-derived). Every later word can read the slots
# with a little attention over them. They add about 1% to the model's size.
#
# **Conditions** (same model, same data, same steps, same skins world as the skins run):
# - `base`: a plain small GPT (the same as `base` in the skins run).
# - `registers`: 8 slots, no teaching. Does the shape alone help?
# - `taught`: the same 8 slots, but 3 of them are lightly taught from the simulator's true state after
#   each sentence: where the agent is, what it's holding (key, target), and the door where it stands.
#   The other 5 stay free. The teaching fades out between 50% and 80% of training, so the model keeps
#   the habit but is free to change how it uses the slots.
#
# The state labels are skin-free (place 3, holding the key), so the same table works in every skin.
#
# **Tests**, written freely by the model and run in the world: the four plan skins and the two
# unseen skins (farm, space; loose sentences only, never plans), on `short` (1–3 obstacles) and `long`
# (4–5 obstacles, longer than any training plan). The report also counts **bookkeeping failures**
# (going where it already is, taking what isn't there, opening the wrong door) and how well the
# taught slots still read out the true state at the end.
#
# On Kaggle: Settings → Accelerator → GPU (T4), then Run All. About 1.5–2 hours.
# At the end it prints a report and writes `REGISTERS_RESULTS.md`; paste that back to Claude.

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
    D, LAYERS, HEADS, K, R, CTX = 32, 2, 2, 4, 8, 256
    S_MAIN, SEEDS, NTEST, NTEST_SEEN, PAIRS, NPROBE = 30, [0], 6, 3, 4, 6
else:
    D, LAYERS, HEADS, K, R, CTX = 192, 8, 6, 8, 32, 256    # about 3.6M parameters, as in the goals runs
    S_MAIN, SEEDS, NTEST, NTEST_SEEN, PAIRS, NPROBE = 6000, [0, 1, 2], 150, 50, 32, 100
LR = 6e-4
REG_AT = LAYERS // 2             # registers are written from, and read into, the state entering this block
LAM_STATE = 0.5                  # weight of the state teaching (taught model only), faded out over training
FADE = (0.5, 0.8)                # teaching is full until 50% of training, then fades to zero by 80%
AMP = dict(device_type=DEV, dtype=torch.float16 if DEV == "cuda" else torch.bfloat16, enabled=DEV == "cuda")
COND = ["base", "registers", "taught"]

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
# line up token for token.

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
# ## State labels
#
# After every sentence the simulator knows the true state. Three things are taught (taught model only):
# where the agent is (place 1–5), what it holds (nothing / key / target / both), and the door where it
# stands (no door / open / closed / locked, or unknown if the problem never said). Labels sit on the
# sentence's last token ("." or "?"); facts before the goal sentence aren't labelled.

# %%
SLOT_CLASSES = [5, 4, 4]
NO_LAB = (-1, -1, -1)


def encode_labeled(ep):
    """Home-word plan → (ids, trained-on mask, per-token state labels). Same ids as encode(render(ep))."""
    known = {f[1]: f[2] for f in ep["facts"] if f[0] == "door"}
    loc, held = ep["start"], set()
    ids, m, labs = [], [], []

    def lab():
        door = 0 if not HAS_DOOR[loc] else {"open": 1, "closed": 2, "locked": 3}.get(known.get(loc), -1)
        return (PLACE_N.index(loc), 2 * ("key" in held) + (ep["target"] in held), door)

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


# %% [markdown]
# ## Model: a small GPT, optionally with state registers
#
# The registers are written from, and read into, the model's state halfway up (before block REG_AT):
# - **Write:** at each sentence end, a small GRU updates all K slots from the state at that token.
#   The slots start from learned values and carry forward from sentence to sentence.
# - **Read:** every token attends over the K slots as they stood after the last finished sentence,
#   and adds what it read back into its state.
# The lower half of the model never sees the registers, which keeps training parallel: only the tiny
# GRU step runs sentence by sentence.

# %%
END_IDS = torch.tensor([STOI["."], STOI["?"]])   # sentence ends


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
    def __init__(self, registers=False):
        super().__init__()
        self.emb = nn.Embedding(V, D)
        self.pos = nn.Parameter(torch.zeros(CTX, D))
        self.blocks = nn.ModuleList(Block() for _ in range(LAYERS))
        self.ln = nn.LayerNorm(D)
        self.registers = registers
        if registers:
            self.w_ln, self.w_in = nn.LayerNorm(D), nn.Linear(D, R)
            self.slot_emb = nn.Parameter(torch.randn(K, R) * 0.02)
            self.s0 = nn.Parameter(torch.zeros(K, R))
            self.cell = nn.GRUCell(R, R)
            self.r_ln, self.r_q, self.r_out = nn.LayerNorm(D), nn.Linear(D, R), nn.Linear(R, D)
            self.heads = nn.ModuleList(nn.Linear(R, c) for c in SLOT_CLASSES)   # readouts of slots 0–2 (teaching only)
        self.apply(self._init)

    @staticmethod
    def _init(m):
        if isinstance(m, (nn.Linear, nn.Embedding)):
            nn.init.normal_(m.weight, std=0.02)
        if isinstance(m, nn.Linear) and m.bias is not None:
            nn.init.zeros_(m.bias)

    def write(self, h, x):
        """Run the GRU over sentence ends. Returns slot states S (B, J+1, K, R), end positions (B, J),
        which ends are real (B, J), and for every token the index of the state it may read (B, T)."""
        B, T = x.shape
        end = (x.unsqueeze(-1) == END_IDS.to(x.device)).any(-1)
        J = int(end.sum(1).max().item())
        ar = torch.arange(T, device=x.device).expand(B, T)
        ends = torch.where(end, ar, torch.full_like(ar, T)).sort(1).values[:, :J]
        valid = ends < T
        he = self.w_in(self.w_ln(h.gather(1, ends.clamp(max=T - 1).unsqueeze(-1).expand(-1, -1, D))))   # (B, J, R)
        s = self.s0.unsqueeze(0).expand(B, K, R).float()
        states = [s]
        for j in range(J):
            inp = (he[:, j].unsqueeze(1) + self.slot_emb).reshape(B * K, R)
            new = self.cell(inp, s.reshape(B * K, R)).view(B, K, R).float()
            s = torch.where(valid[:, j, None, None], new, s)
            states.append(s)
        idx = end.long().cumsum(1) - end.long()          # sentence ends strictly before each token
        return torch.stack(states, 1), ends, valid, idx

    def forward(self, x, state=False):
        h = self.emb(x) + self.pos[: x.shape[1]]
        extra = None
        for i, b in enumerate(self.blocks):
            if i == REG_AT and self.registers:
                S, ends, valid, idx = self.write(h, x)
                Rt = S[torch.arange(x.shape[0], device=x.device)[:, None], idx]                  # (B, T, K, R)
                q = self.r_q(self.r_ln(h)).float()
                a = torch.softmax(torch.einsum("btkr,btr->btk", Rt, q) / R ** 0.5, -1)
                h = h + self.r_out(torch.einsum("btk,btkr->btr", a, Rt))
                extra = (S, ends, valid)
            h = b(h)
        logits = self.ln(h) @ self.emb.weight.T
        return (logits, extra) if state else logits


# %% [markdown]
# ## Training
#
# Batches are built exactly as in the skins run (pairs of one problem or scene in two skins), so the
# three conditions here, and `base` in the skins run, see the same kind of data.

# %%
def make_batch(items):
    """items: [(home ids, mask, labels, skin a, skin b)]. Rows 0..B-1 are skin a, rows B..2B-1 skin b."""
    B, L = len(items), max(len(i[0]) for i in items)
    X = torch.zeros(2 * B, L - 1, dtype=torch.long)
    Y = torch.zeros(2 * B, L - 1, dtype=torch.long)
    W = torch.zeros(2 * B, L - 1)
    LAB = torch.full((2 * B, L - 1, 3), -1, dtype=torch.long)
    for b, (ids, m, labs, sa, sb) in enumerate(items):
        n = len(ids) - 1
        for k, s in ((b, sa), (B + b, sb)):
            sid = [SKIN_MAP[s][t] for t in ids]
            X[k, :n] = torch.tensor(sid[:-1]); Y[k, :n] = torch.tensor(sid[1:])
            W[k, :n] = torch.tensor(m[1:], dtype=torch.float)
            LAB[k, :n] = torch.tensor(labs[:-1])
    return [t.to(DEV) for t in (X, Y, W, LAB)]


def state_loss(model, extra, LAB):
    """Cross-entropy of slots 0–2 against the true state after each sentence. Returns (loss, accuracies)."""
    S, ends, valid = extra
    T = LAB.shape[1]
    lab = LAB.gather(1, ends.clamp(max=T - 1).unsqueeze(-1).expand(-1, -1, 3))       # (B, J, 3)
    after = S[:, 1:]
    loss, acc = 0.0, []
    for k in range(3):
        y, mk = lab[..., k], valid & (lab[..., k] >= 0)
        if mk.any():
            lg = model.heads[k](after[:, :, k][mk])
            loss = loss + F.cross_entropy(lg, y[mk])
            acc.append((lg.argmax(-1) == y[mk]).float().mean().item())
        else:
            acc.append(float("nan"))
    return loss, acc


def train(model, sampler, steps, r, teach=False):
    opt = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=0.1, betas=(0.9, 0.95))
    try:
        scaler = torch.amp.GradScaler("cuda", enabled=DEV == "cuda")
    except (AttributeError, TypeError):
        scaler = torch.cuda.amp.GradScaler(enabled=DEV == "cuda")
    model.train()
    logs = []
    for step in range(steps):
        frac = step / steps
        lr = LR * min(1, (step + 1) / 100) * (0.1 + 0.9 * 0.5 * (1 + math.cos(math.pi * frac)))
        for g in opt.param_groups:
            g["lr"] = lr
        lam = LAM_STATE * min(1.0, max(0.0, (FADE[1] - frac) / (FADE[1] - FADE[0]))) if teach else 0.0
        X, Y, W, LAB = make_batch([sampler(r) for _ in range(PAIRS)])
        with torch.autocast(**AMP):
            logits, extra = model(X, state=True)
        lm = (F.cross_entropy(logits.float().reshape(-1, V), Y.reshape(-1), reduction="none") * W.reshape(-1)).sum() / W.sum()
        loss, acc = lm, [float("nan")] * 3
        if extra is not None:
            sl, acc = state_loss(model, extra, LAB)
            if lam > 0:
                loss = lm + lam * sl
        opt.zero_grad(set_to_none=True)
        scaler.scale(loss).backward()
        scaler.unscale_(opt)
        nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        scaler.step(opt); scaler.update()
        logs.append((lm.item(), *acc))
        if (step + 1) % 500 == 0:
            a = logs[-500:]
            line = f"    step {step+1}/{steps}  lm {st.mean(x[0] for x in a):.3f}"
            if teach:
                line += f"  teach {lam:.2f}  slots " + " ".join(f"{st.mean(x[k] for x in a if x[k] == x[k])*100:.0f}%" for k in (1, 2, 3))
            print(line, flush=True)
    return logs


@torch.no_grad()
def slot_accuracy(model, eps, skins):
    """How well slots 0–2 read out the true state on gold plans, after training."""
    model.eval()
    acc = [[], [], []]
    for s in skins:
        for k in range(0, len(eps), 50):
            items = [encode_labeled(e) for e in eps[k:k + 50]]
            X, _, _, LAB = make_batch([(i, m, l, s, s) for i, m, l in items])
            _, extra = model(X, state=True)
            _, a = state_loss(model, extra, LAB)
            for j in range(3):
                acc[j].append(a[j])
    return [st.mean([v for v in x if v == v] or [float("nan")]) for x in acc]


# %% [markdown]
# ## Running plans

# %%
@torch.no_grad()
def run_plans(model, eps, skin, max_new=200):
    """The model writes plans in a skin; the checker runs each sentence and answers searches."""
    model.eval()
    seqs = [[STOI[w] for w in to_skin(prompt_text(ep), skin).split()] for ep in eps]
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


def test_sets():
    r = random.Random(12345)
    return {"short": episodes(r, NTEST, SHORT), "long": episodes(r, NTEST, LONG)}


def evaluate(model, tests, skins, n):
    res = {}
    for split, eps in tests.items():
        sims = sum((run_plans(model, eps[:n], s) for s in skins), [])
        res[split] = score(sims)
    return res



# %% [markdown]
# ## Run everything

# %%
BOOKKEEPING = ("bad go", "bad take", "bad open", "bad unlock", "false claim")


def run():
    t0 = time.time()
    tests = test_sets()
    probe = episodes(random.Random(999), NPROBE, SHORT + LONG)
    print(f"device {DEV}, vocab {V} words, params base {sum(p.numel() for p in GPT().parameters())/1e6:.3f}M,"
          f" with registers {sum(p.numel() for p in GPT(True).parameters())/1e6:.3f}M", flush=True)
    results, samples = [], {}
    show = next(e for e in tests["long"] if {"H", "L"} <= e["obs"])
    for seed in SEEDS:
        dr = random.Random(1000 + seed)
        plans = [encode_labeled(e) for e in episodes(dr, 20000, SHORT)]
        scenes = [encode_scene(scene(dr)) for _ in range(20000)]

        def sampler(r):
            if r.random() < 0.6:
                ids, m, labs = r.choice(plans)
                a, b = r.sample(PLAN_SKINS, 2)
            else:
                ids, m, labs = r.choice(scenes)
                a, b = r.sample(ALL_SKINS, 2)
            return ids, m, labs, a, b

        for cond in COND:
            torch.manual_seed(seed)
            model = GPT(registers=cond != "base").to(DEV)
            train(model, sampler, S_MAIN, random.Random(seed), teach=cond == "taught")
            row = {"seed": seed, "cond": cond,
                   "seen": evaluate(model, tests, PLAN_SKINS, NTEST_SEEN),
                   "unseen": evaluate(model, tests, UNSEEN, NTEST)}
            if cond == "taught":
                row["slots_seen"] = slot_accuracy(model, probe, PLAN_SKINS)
                row["slots_unseen"] = slot_accuracy(model, probe, UNSEEN)
            if seed == SEEDS[0]:
                samples[cond] = {s: run_plans(model, [show], s)[0].text for s in ("home", "space")}
            results.append(row)
            f = lambda d: " ".join(f"{k} {v['success']*100:3.0f}%" for k, v in d.items())
            print(f"seed {seed} {cond:9}  seen: {f(row['seen'])}   unseen: {f(row['unseen'])}" +
                  (f"   slots (seen) where/holding/door " + " ".join(f"{a*100:.0f}%" for a in row["slots_seen"]) if "slots_seen" in row else "") +
                  f"   ({time.time()-t0:.0f}s)", flush=True)
        json.dump({"results": results, "samples": samples}, open("registers_results.json", "w"), indent=1, default=str)
    return results, samples, prompt_text(show)


def report(R, samples, show_prompt):
    pct = lambda v: "–" if v is None or v != v else f"{v*100:.0f}%"
    m = lambda rows, key, sp, k="success": st.mean([x[key][sp][k] for x in rows if x[key][sp][k] is not None] or [float("nan")])
    L = ["# Registers: results", "",
         f"{len({r['seed'] for r in R})} seeds. Plan skins: {', '.join(PLAN_SKINS)}. Unseen skins: {', '.join(UNSEEN)} "
         "(loose sentences only, never a plan).",
         "Success = the model's own plan, run in the world, gets the goal.", "",
         "| model | seen short | seen long | unseen short | unseen long | looked up when needed (seen) |",
         "|---|---|---|---|---|---|"]
    for c in COND:
        rows = [r for r in R if r["cond"] == c]
        if rows:
            look = st.mean([m(rows, "seen", sp, "looked_when_needed") for sp in ("short", "long")])
            L.append(f"| {c} | {pct(m(rows,'seen','short'))} | {pct(m(rows,'seen','long'))} | {pct(m(rows,'unseen','short'))} | "
                     f"{pct(m(rows,'unseen','long'))} | {pct(look)} |")
    L += ["", "## Per seed (seen long / unseen long)", ""]
    for s in sorted({r["seed"] for r in R}):
        L.append(f"- seed {s}: " + ", ".join(f"{r['cond']} {pct(r['seen']['long']['success'])} / {pct(r['unseen']['long']['success'])}"
                                             for r in R if r["seed"] == s))
    L += ["", "## Failures", "",
          "Bookkeeping failures are going where the agent already is, taking something that isn't there, opening",
          "the wrong door, or claiming something false. These are what a state table should prevent.", ""]
    for where in ("seen", "unseen"):
        for c in COND:
            why = {}
            for r in R:
                if r["cond"] == c:
                    for v in r[where].values():
                        for k, n_ in v["fails"].items():
                            why[k] = why.get(k, 0) + n_
            book = sum(v for k, v in why.items() if k in BOOKKEEPING)
            L.append(f"- {where}, {c}: bookkeeping {book}; all: " +
                     (", ".join(f"{k} {v}" for k, v in sorted(why.items(), key=lambda x: -x[1])) or "none"))
    rows = [r for r in R if "slots_seen" in r]
    if rows:
        L += ["", "## Do the taught slots still hold the true state? (gold plans, after training)", "",
              "| | where the agent is | what it holds | door where it stands |", "|---|---|---|---|"]
        for key, name in (("slots_seen", "plan skins"), ("slots_unseen", "unseen skins")):
            L.append(f"| {name} | " + " | ".join(pct(st.mean([r[key][k] for r in rows])) for k in range(3)) + " |")
        L.append("")
        L.append("Chance is about 20% / 25% / 25%. The teaching stopped at 80% of training, so this shows whether the model kept the table.")
    L += ["", "## One long problem (seed 0)", "", "Problem (home words): " + show_prompt, ""]
    for c, d in samples.items():
        for s, t in d.items():
            L.append(f"- {c}, {s}: `{t}`")
    text = "\n".join(L) + "\n"
    open("REGISTERS_RESULTS.md", "w").write(text)
    print(text)


# %%
if __name__ == "__main__" or "ipykernel" in sys.modules:
    if "--no-run" not in sys.argv:
        R, samples, show_prompt = run()
        report(R, samples, show_prompt)
