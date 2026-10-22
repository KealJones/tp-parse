# %% [markdown]
# # Skins: can a small model learn the *lesson* of a problem without its nouns?
#
# The "intuition block" idea: pull out the shape of a problem ("get past a locked thing by
# fetching the thing that unlocks it") with the nouns stripped away, so it works in any domain.
#
# This notebook tests that in the goals world. The same planning problems are dressed in six
# **skins**, each with its own words for every agent, place, item, property, key, door and verb:
#
# | skin | agent | places | items | key / door | verbs |
# |---|---|---|---|---|---|
# | home | person | house, shop, school, forest, field | bread, fruit… | key / door | goes, opens, takes… |
# | computer | user | folder, drive, server, desktop, inbox | file, photo… | password / lock | navigates, accesses, copies… |
# | ship | captain | port, harbor, dock, sea, bay | cargo, rope… | permit / gate | sails, raises, loads… |
# | kitchen | cook | pantry, fridge, oven, counter, sink | egg, flour… | opener / lid | walks, lifts, grabs… |
# | **farm** (unseen) | farmer | barn, shed, stable, meadow, orchard | hay, corn… | crowbar / hatch | drives, pries, picks… |
# | **space** (unseen) | pilot | station, module, lab, orbit, crater | fuel, crystal… | keycard / airlock | flies, cycles, collects… |
#
# The model writes plans in the first four skins. Farm and space only ever appear as loose
# descriptive sentences ("the pilot flies to the orbit .", "the airlock of the lab is locked ."),
# never as a plan and never side by side with another skin. Then it has to plan in them.
#
# **Conditions** (same model, same data, same steps):
# - `base`: a plain small GPT.
# - `lesson`: the same GPT plus a **lesson block** halfway up. The block squeezes the model's state
#   into a 64-number "lesson vector", which is added back into the model. Two training signals shape it,
#   both only on the four plan skins:
#   1. *Noun-free*: from the lesson vector alone, predict the next word's **job**, not the word
#      (AGENT, PLACE-WITH-DOOR, ITEM, KEY, GO-verb…, plus the shared words like "so" and "because").
#   2. *Same lesson in any skin*: the same problem in two skins must give the same lesson vectors.
# - `reference`: also sees plans in farm and space (a ceiling, not a rival).
#
# **Tests**, all written freely by the model and run in the world:
# - seen skins (home, computer, ship, kitchen), and unseen skins (farm, space) with zero plans seen
# - `short` (1–3 obstacles) and `long` (4–5 obstacles, longer than any training plan)
# - then 32 plans per unseen skin, a short top-up of training, and the unseen tests again
# - an **analogy test**: does the middle of the model file "airlock", "pries" and "crater" under the
#   same job as "door", "opens" and "field"?
#
# On Kaggle: Settings → Accelerator → GPU (T4), then Run All. About 1.5–2 hours.
# At the end it prints a report and writes `SKINS_RESULTS.md`; paste that back to Claude.

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
    D, LAYERS, HEADS, Z, CTX = 32, 2, 2, 16, 256
    S_MAIN, S_FEW, N_FEW, SEEDS, NTEST, NTEST_SEEN, PAIRS, NPROBE = 30, 10, 4, [0], 6, 3, 4, 6
else:
    D, LAYERS, HEADS, Z, CTX = 192, 8, 6, 64, 256    # about 3.6M parameters, as in the goals runs
    S_MAIN, S_FEW, N_FEW, SEEDS, NTEST, NTEST_SEEN, PAIRS, NPROBE = 6000, 400, 32, [0, 1, 2], 150, 50, 32, 100
LR, LR_FEW = 6e-4, 3e-4
LESSON_AT = LAYERS // 2          # the lesson block sits before this block
LAM_ROLE, LAM_SAME = 0.5, 1.0    # weights of the two lesson signals
AMP = dict(device_type=DEV, dtype=torch.float16 if DEV == "cuda" else torch.bfloat16, enabled=DEV == "cuda")
COND = ["base", "lesson", "reference"]

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
# line up token for token, which is what lets the lesson block compare them position by position.
# Each word also has a **job**: skin words map to their slot (AGENT, DOORPLACE, ITEM, GO…), shared
# words ("the", "so", "because", "search"…) are their own job. The lesson block predicts jobs, not words.

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
# ## Model: a small GPT, optionally with the lesson block
#
# The lesson block reads the model's state halfway up, squeezes it to Z numbers (the lesson vector),
# and adds a projection of it back in. The job head reads only the lesson vector, and is used only in
# training. The base model has no lesson block (about 1% fewer weights).

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
    def __init__(self, lesson=False):
        super().__init__()
        self.emb = nn.Embedding(V, D)
        self.pos = nn.Parameter(torch.zeros(CTX, D))
        self.blocks = nn.ModuleList(Block() for _ in range(LAYERS))
        self.ln = nn.LayerNorm(D)
        self.lesson = lesson
        if lesson:
            self.l_ln, self.l_in, self.l_out = nn.LayerNorm(D), nn.Linear(D, Z), nn.Linear(Z, D)
            self.job_head = nn.Linear(Z, len(JOBS))
        self.apply(self._init)

    @staticmethod
    def _init(m):
        if isinstance(m, (nn.Linear, nn.Embedding)):
            nn.init.normal_(m.weight, std=0.02)
        if isinstance(m, nn.Linear) and m.bias is not None:
            nn.init.zeros_(m.bias)

    def forward(self, x, mid=False):
        h = self.emb(x) + self.pos[: x.shape[1]]
        hm = z = None
        for i, b in enumerate(self.blocks):
            if i == LESSON_AT:
                hm = h
                if self.lesson:
                    z = self.l_in(self.l_ln(h))
                    h = h + self.l_out(z)
            h = b(h)
        logits = self.ln(h) @ self.emb.weight.T
        return (logits, hm, z) if mid else logits


# %% [markdown]
# ## Training
#
# Every batch is made of pairs: one problem (or scene) dressed in two different skins. All three
# conditions get exactly the same batches. Only the lesson model uses the pairing, and only when both
# skins are plan skins, so farm and space never get any help beyond their own loose sentences.

# %%
def make_batch(items):
    """items: [(home ids, mask, skin a, skin b)] → tensors. Rows 0..B-1 are skin a, rows B..2B-1 skin b."""
    B, L = len(items), max(len(i[0]) for i in items)
    X = torch.zeros(2 * B, L - 1, dtype=torch.long)
    Y = torch.zeros(2 * B, L - 1, dtype=torch.long)
    W = torch.zeros(2 * B, L - 1)
    VALID = torch.zeros(B, L - 1)
    YJ = torch.zeros(B, L - 1, dtype=torch.long)
    AUX = torch.zeros(2 * B, 1)
    for b, (ids, m, sa, sb) in enumerate(items):
        n = len(ids) - 1
        for k, s in ((b, sa), (B + b, sb)):
            sid = [SKIN_MAP[s][t] for t in ids]
            X[k, :n] = torch.tensor(sid[:-1]); Y[k, :n] = torch.tensor(sid[1:])
            W[k, :n] = torch.tensor(m[1:], dtype=torch.float)
            AUX[k] = float(s in PLAN_SKINS)
        VALID[b, :n] = 1
        YJ[b, :n] = torch.tensor([JOB_OF[t] for t in ids[1:]])
    return [t.to(DEV) for t in (X, Y, W, VALID, YJ, AUX)]


def train(model, sampler, steps, r, lr0=LR):
    opt = torch.optim.AdamW(model.parameters(), lr=lr0, weight_decay=0.1, betas=(0.9, 0.95))
    try:
        scaler = torch.amp.GradScaler("cuda", enabled=DEV == "cuda")
    except (AttributeError, TypeError):
        scaler = torch.cuda.amp.GradScaler(enabled=DEV == "cuda")
    model.train()
    logs = []
    for step in range(steps):
        lr = lr0 * min(1, (step + 1) / 100) * (0.1 + 0.9 * 0.5 * (1 + math.cos(math.pi * step / steps)))
        for g in opt.param_groups:
            g["lr"] = lr
        X, Y, W, VALID, YJ, AUX = make_batch([sampler(r) for _ in range(PAIRS)])
        B = VALID.shape[0]
        with torch.autocast(**AMP):
            logits, _, z = model(X, mid=True)
        lm = (F.cross_entropy(logits.float().reshape(-1, V), Y.reshape(-1), reduction="none") * W.reshape(-1)).sum() / W.sum()
        loss, job, same = lm, torch.zeros(()), torch.zeros(())
        if model.lesson:
            z = z.float()
            jm = torch.cat([VALID, VALID]) * AUX                            # job loss: plan-skin rows only
            jl = F.cross_entropy(model.job_head(z).reshape(-1, len(JOBS)), torch.cat([YJ, YJ]).reshape(-1), reduction="none")
            job = (jl * jm.reshape(-1)).sum() / jm.sum().clamp(min=1)
            pm = VALID * AUX[:B] * AUX[B:]                                  # same-lesson loss: plan-skin pairs only
            za, zb = F.normalize(z[:B], dim=-1), F.normalize(z[B:], dim=-1)
            same = (((za - zb) ** 2).sum(-1) * pm).sum() / pm.sum().clamp(min=1)
            loss = lm + LAM_ROLE * job + LAM_SAME * same
        opt.zero_grad(set_to_none=True)
        scaler.scale(loss).backward()
        scaler.unscale_(opt)
        nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        scaler.step(opt); scaler.update()
        logs.append((lm.item(), job.item(), same.item()))
        if (step + 1) % 500 == 0:
            a = logs[-500:]
            print(f"    step {step+1}/{steps}  lm {st.mean(x[0] for x in a):.3f}" +
                  (f"  job {st.mean(x[1] for x in a):.3f}  same {st.mean(x[2] for x in a):.3f}" if model.lesson else ""), flush=True)
    return logs


# %% [markdown]
# ## Running plans and the analogy test

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


@torch.no_grad()
def analogy(model, eps):
    """Does the middle of the model file farm/space words under the same job as plan-skin words?
    Job centroids come from plan-skin text; each unseen-skin word is assigned to the nearest centroid.
    Measured on the state entering the lesson block (both models) and on the lesson vector (lesson model)."""
    model.eval()
    feats = {}
    for skin in ALL_SKINS:
        vh, vz, jobs = [], [], []
        for k in range(0, len(eps), 50):
            chunk = [encode(render(e))[0] for e in eps[k:k + 50]]
            L = max(len(c) for c in chunk)
            x = torch.zeros(len(chunk), L, dtype=torch.long)
            for b, c in enumerate(chunk):
                x[b, : len(c)] = torch.tensor([SKIN_MAP[skin][t] for t in c])
            _, hm, z = model(x.to(DEV), mid=True)
            for b, c in enumerate(chunk):
                for p, t in enumerate(c):
                    if VOCAB[t] in JOB:                      # a skin word (agent, place, item, verb…)
                        vh.append(hm[b, p].float().cpu()); jobs.append(JOB[VOCAB[t]])
                        if z is not None:
                            vz.append(z[b, p].float().cpu())
        feats[skin] = (torch.stack(vh), torch.stack(vz) if vz else None, jobs)
    out = {}
    for which in (0, 1):
        if feats["home"][which] is None:
            continue
        train_v = torch.cat([feats[s][which] for s in PLAN_SKINS])
        train_j = sum((feats[s][2] for s in PLAN_SKINS), [])
        mu = train_v.mean(0)
        names = sorted(set(train_j))
        cent = F.normalize(torch.stack([train_v[torch.tensor([j == n for j in train_j])].mean(0) - mu for n in names]), dim=-1)
        hits = []
        for s in UNSEEN:
            v = F.normalize(feats[s][which] - mu, dim=-1)
            pred = (v @ cent.T).argmax(-1).tolist()
            hits += [names[p] == j for p, j in zip(pred, feats[s][2])]
        out["middle" if which == 0 else "lesson vector"] = st.mean(hits)
    return out


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
def run():
    t0 = time.time()
    tests = test_sets()
    probe = episodes(random.Random(999), NPROBE, SHORT)
    print(f"device {DEV}, vocab {V} words, {len(JOBS)} jobs, params base {sum(p.numel() for p in GPT().parameters())/1e6:.2f}M,"
          f" lesson {sum(p.numel() for p in GPT(True).parameters())/1e6:.2f}M", flush=True)
    results, samples = [], {}
    show = next(e for e in tests["short"] if {"H", "L"} <= e["obs"])
    for seed in SEEDS:
        dr = random.Random(1000 + seed)
        plans = [encode(render(e)) for e in episodes(dr, 20000, SHORT)]
        scenes = [encode([(scene(dr), True)]) for _ in range(20000)]
        few_r = random.Random(5000 + seed)
        few = [(encode(render(e)), s) for s in UNSEEN for e in episodes(few_r, N_FEW, SHORT)]

        def main_sampler(plan_skins):
            def f(r):
                if r.random() < 0.6:
                    ids, m = r.choice(plans)
                    a, b = r.sample(plan_skins, 2)
                else:
                    ids, m = r.choice(scenes)
                    a, b = r.sample(ALL_SKINS, 2)
                return ids, m, a, b
            return f

        def few_sampler(r):
            if r.random() < 0.5:
                (ids, m), s = r.choice(few)
                return ids, m, s, r.choice(PLAN_SKINS)
            return main_sampler(PLAN_SKINS)(r)

        for cond in COND:
            torch.manual_seed(seed)
            model = GPT(lesson=cond == "lesson").to(DEV)
            r = random.Random(seed)
            train(model, main_sampler(ALL_SKINS if cond == "reference" else PLAN_SKINS), S_MAIN, r)
            row = {"seed": seed, "cond": cond,
                   "seen": evaluate(model, tests, PLAN_SKINS, NTEST_SEEN),
                   "unseen": evaluate(model, tests, UNSEEN, NTEST),
                   "analogy": analogy(model, probe)}
            if seed == SEEDS[0]:
                samples[cond] = {s: run_plans(model, [show], s)[0].text for s in UNSEEN}
            if cond != "reference":
                train(model, few_sampler, S_FEW, r, LR_FEW)
                row["unseen_few"] = evaluate(model, tests, UNSEEN, NTEST)
            results.append(row)
            f = lambda d: " ".join(f"{k} {v['success']*100:3.0f}%" for k, v in d.items())
            print(f"seed {seed} {cond:9}  seen: {f(row['seen'])}   unseen 0-shot: {f(row['unseen'])}" +
                  (f"   unseen after {N_FEW}/skin: {f(row['unseen_few'])}" if "unseen_few" in row else "") +
                  "   analogy " + " ".join(f"{k} {v*100:.0f}%" for k, v in row["analogy"].items()) +
                  f"   ({time.time()-t0:.0f}s)", flush=True)
        json.dump({"results": results, "samples": samples}, open("skins_results.json", "w"), indent=1, default=str)
    return results, samples, prompt_text(show)


def report(R, samples, show_prompt):
    pct = lambda v: "–" if v is None else f"{v*100:.0f}%"
    m = lambda rows, key, sp, k="success": st.mean([x[key][sp][k] for x in rows if key in x and x[key][sp][k] is not None] or [float("nan")])
    L = ["# Skins: results", "",
         f"{len({r['seed'] for r in R})} seeds. Plan skins: {', '.join(PLAN_SKINS)}. Unseen skins: {', '.join(UNSEEN)} "
         f"(only loose sentences, never a plan, for base and lesson). {NTEST} test problems per split per unseen skin.",
         "Success = the model's own plan, run in the world, gets the goal.", "",
         "| model | seen short | seen long | unseen short (0 plans) | unseen long (0 plans) | unseen short (after "
         f"{N_FEW}/skin) | unseen long (after {N_FEW}/skin) | looked up when needed (unseen, 0 plans) |",
         "|---|---|---|---|---|---|---|---|"]
    for c in COND:
        rows = [r for r in R if r["cond"] == c]
        if not rows:
            continue
        few = lambda sp: pct(m(rows, "unseen_few", sp)) if any("unseen_few" in x for x in rows) else "–"
        look = st.mean([m(rows, "unseen", sp, "looked_when_needed") for sp in ("short", "long")])
        L.append(f"| {c} | {pct(m(rows,'seen','short'))} | {pct(m(rows,'seen','long'))} | {pct(m(rows,'unseen','short'))} | "
                 f"{pct(m(rows,'unseen','long'))} | {few('short')} | {few('long')} | {pct(look)} |")
    L += ["", "## Per seed: unseen skins, 0 plans (short / long)", ""]
    for s in sorted({r["seed"] for r in R}):
        L.append(f"- seed {s}: " + ", ".join(f"{r['cond']} {pct(r['unseen']['short']['success'])} / {pct(r['unseen']['long']['success'])}"
                                             for r in R if r["seed"] == s))
    L += ["", "## Analogy test", "",
          "How often a farm or space word lands nearest the right job (place with a door, item, go-verb…) as learned",
          f"from the plan skins. {len(set(ROLE_SLOTS))} jobs, so chance is about {100/len(set(ROLE_SLOTS)):.0f}%.", ""]
    for c in COND:
        rows = [r["analogy"] for r in R if r["cond"] == c]
        if rows:
            L.append(f"- {c}: " + ", ".join(f"{k} {pct(st.mean(x[k] for x in rows))}" for k in rows[0]))
    L += ["", "## Why unseen-skin plans failed (0 plans)", ""]
    for c in COND:
        why = {}
        for r in R:
            if r["cond"] == c:
                for v in r["unseen"].values():
                    for k, n_ in v["fails"].items():
                        why[k] = why.get(k, 0) + n_
        L.append(f"- {c}: " + (", ".join(f"{k} {v}" for k, v in sorted(why.items(), key=lambda x: -x[1])) or "none"))
    L += ["", "## One problem, zero plans seen in the skin (seed 0)", "", "Problem (home words): " + show_prompt, ""]
    for c, d in samples.items():
        for s, t in d.items():
            L.append(f"- {c}, {s}: `{to_skin(show_prompt, s)} {t}`")
    text = "\n".join(L) + "\n"
    open("SKINS_RESULTS.md", "w").write(text)
    print(text)


# %%
if __name__ == "__main__" or "ipykernel" in sys.modules:
    if "--show" in sys.argv:
        ep = make_episode(random.Random(1), frozenset({"H", "L", "KC"}))
        for s in SKINS:
            print(f"[{s}]", to_skin(" ".join(t for t, _ in render(ep)), s), "\n")
    elif "--no-run" not in sys.argv:
        R, samples, show_prompt = run()
        report(R, samples, show_prompt)
