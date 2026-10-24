"""Fine-tune test: does a small pretrained model learn the bound-harness planning task, and do state slots help?

  python ft.py worker --model Qwen/Qwen3-0.6B --version ft-slots --gpu 1 --tag full
  python ft.py report --model Qwen/Qwen3-0.6B

Versions (one model each):
  untouched  the model as downloaded, shown two worked examples in the prompt (few-shot)
  ft         full fine-tune on the planning task (embeddings frozen), no examples in the prompt
  ft-slots   the same fine-tune with 8 state slots added halfway up, updated at every token and
             trained without a simulator (from the slots alone, predict the next sentence's tokens)
  lora-slots the same slots, but the model itself frozen and only LoRA patches (rank 16) trained

Each is scored on: planning in the world (clean, messy = no periods, filler = no periods plus "um", "like"…
never seen in training), honest gaps (searching when a fact is missing), English kept (ARC-Easy, WikiText-2),
Keal's real messages (pick what he meant out of four, voice vs typed), and for the fine-tunes the same again
after squashing the weights to 4 bits.
"""
import json, math, os, random, re, statistics as st, sys, time

ARGV = sys.argv


def arg(name, default=None):
    return ARGV[ARGV.index(name) + 1] if name in ARGV else default


if "--gpu" in ARGV:
    os.environ["CUDA_VISIBLE_DEVICES"] = arg("--gpu")

import torch
import torch.nn as nn
import torch.nn.functional as F

DEV = "cuda" if torch.cuda.is_available() else "cpu"
K, R = 8, 32                     # slots × numbers per slot
FILLERS = ["um", "uh", "like", "you know", "so", "i mean", "like literally", "or whatever"]

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
# ## Text for the pretrained model

# %%
def problem_words(ep, skin, kind, seed):
    """The problem in a skin. messy: periods removed from the facts. filler: also speech filler sprinkled in."""
    words = to_skin(prompt_text(ep), skin).split()
    body, tail = words[:-2], words[-2:]              # tail = "plan :"
    if kind in ("messy", "filler"):
        body = [w for w in body if w != "."]
    if kind == "filler":
        r, out = random.Random(seed), []
        for w in body:
            if r.random() < 0.18:
                out += r.choice(FILLERS).split()
            out.append(w)
        body = out
    return body + tail


def plan_segments(ep, skin):
    return [(to_skin(t, skin), train) for s in ep["plan"] for t, train in step_text(s)]


def worked_example(ep, skin):
    return " ".join(problem_words(ep, skin, "clean", 0) + [t for t, _ in plan_segments(ep, skin)])


def few_shot_prefix(skin):
    r = random.Random(7)
    a = make_episode(r, frozenset({"H", "C"}))
    b = make_episode(r, frozenset({"L", "S"}))
    return ("Each problem lists facts, then a step-by-step plan. A missing fact is looked up with search.\n\n"
            + worked_example(a, skin) + "\n\n" + worked_example(b, skin) + "\n\n")


def tokenize_segments(segs):
    """[(text, trained)] → (ids, per-token trained mask). A token is trained if its last character is in a trained segment."""
    text, spans = "", []
    for t, train in segs:
        if text:
            text += " "
        spans.append((len(text), len(text) + len(t), train))
        text += t
    enc = TOK(text, return_offsets_mapping=True, add_special_tokens=False)
    mask = []
    for a, b in enc["offset_mapping"]:
        c = b - 1
        mask.append(any(s <= c < e and tr for s, e, tr in spans))
    return enc["input_ids"], mask


# %% [markdown]
# ## State slots for a pretrained model
#
# Hooked onto the input of the middle decoder layer. At each token the hidden state proposes new slot
# contents c and a keep-gate g (s ← g·s + (1 − g)·c); every token then reads the slots and adds what it
# read back in. The read-out starts at zero, so the model is unchanged until training moves it. Trained
# without a simulator: from the slots at each sentence end, predict the tokens of the next sentence.

# %%
class Slots(nn.Module):
    def __init__(self, D):
        super().__init__()
        self.w_ln, self.w_gate, self.w_new = nn.LayerNorm(D), nn.Linear(D, K * R), nn.Linear(D, K * R)
        self.s0 = nn.Parameter(torch.zeros(K, R))
        self.r_ln, self.r_q, self.r_out = nn.LayerNorm(D), nn.Linear(D, R), nn.Linear(R, D)
        self.pred = nn.Linear(K * R, D)
        for m in (self.w_gate, self.w_new, self.r_q, self.pred):
            nn.init.normal_(m.weight, std=0.02); nn.init.zeros_(m.bias)
        nn.init.zeros_(self.r_out.weight); nn.init.zeros_(self.r_out.bias)
        self.incremental, self.carry, self.last = False, None, None

    def forward(self, h):
        with torch.autocast(device_type="cuda", enabled=False):
            hf = h.float()
            B, T, _ = hf.shape
            u = self.w_ln(hf)
            g = torch.sigmoid(self.w_gate(u) + 2.0).view(B, T, K, R)
            c = torch.tanh(self.w_new(u)).view(B, T, K, R)
            s = self.carry if (self.incremental and self.carry is not None) else self.s0.float().unsqueeze(0).expand(B, K, R)
            out = []
            for t in range(T):
                s = torch.lerp(c[:, t], s, g[:, t])
                out.append(s)
            S = torch.stack(out, 1)
            if self.incremental:
                self.carry = s.detach()
            self.last = S
            a = torch.softmax(torch.einsum("btkr,btr->btk", S, self.r_q(self.r_ln(hf))) / R ** 0.5, -1)
            read = self.r_out(torch.einsum("btk,btkr->btr", a, S))
        return h + read.to(h.dtype)


def attach_slots(model):
    layers = model.get_decoder().layers
    mid = len(layers) // 2
    model.slots = Slots(model.config.hidden_size).to(next(model.parameters()).device)

    def pre_hook(mod, args, kwargs):
        if args:
            return (model.slots(args[0]),) + tuple(args[1:]), kwargs
        kwargs["hidden_states"] = model.slots(kwargs["hidden_states"])
        return args, kwargs

    layers[mid].register_forward_pre_hook(pre_hook, with_kwargs=True)
    print(f"slots attached before layer {mid} of {len(layers)}: {sum(p.numel() for p in model.slots.parameters())/1e6:.2f}M params", flush=True)


def slots_mode(model, incremental):
    if getattr(model, "slots", None) is not None:
        model.slots.incremental, model.slots.carry = incremental, None


class LoRALinear(nn.Module):
    """A frozen linear layer plus a trainable low-rank patch: W x + (alpha/r)·B A x. B starts at zero."""
    def __init__(self, base, r=16, alpha=32):
        super().__init__()
        self.base, self.scale = base, alpha / r
        self.A = nn.Parameter(torch.randn(r, base.in_features, device=base.weight.device) / math.sqrt(base.in_features))
        self.B = nn.Parameter(torch.zeros(base.out_features, r, device=base.weight.device))

    def forward(self, x):
        return self.base(x) + (x @ self.A.T.to(x.dtype)) @ (self.B.T.to(x.dtype) * self.scale)

    @torch.no_grad()
    def merge(self):
        self.base.weight += self.scale * (self.B @ self.A)
        self.B.zero_()


def attach_lora(model, r=16):
    targets = [(parent, cname, child) for layer in model.get_decoder().layers for parent in layer.modules()
               for cname, child in parent.named_children() if isinstance(child, nn.Linear)]
    for parent, cname, child in targets:                 # collected first, so no layer is wrapped twice
        setattr(parent, cname, LoRALinear(child, r))
    n = len(targets)
    for p_ in model.parameters():
        p_.requires_grad_(False)
    lora_params = [p_ for m in model.modules() if isinstance(m, LoRALinear) for p_ in (m.A, m.B)]
    for p_ in lora_params:
        p_.requires_grad_(True)
    print(f"LoRA rank {r} on {n} linear layers: {sum(p_.numel() for p_ in lora_params)/1e6:.1f}M trainable params", flush=True)


# %% [markdown]
# ## Loading and training

# %%
TOK, AMP_ON, END_IDS = None, DEV == "cuda", set()


def amp():
    return torch.autocast(device_type="cuda", dtype=torch.float16, enabled=AMP_ON)


def load(name):
    global TOK, END_IDS
    from transformers import AutoModelForCausalLM, AutoTokenizer
    TOK = AutoTokenizer.from_pretrained(name)
    if TOK.pad_token_id is None:
        TOK.pad_token = TOK.eos_token
    try:
        model = AutoModelForCausalLM.from_pretrained(name, dtype=torch.float32)
    except TypeError:
        model = AutoModelForCausalLM.from_pretrained(name, torch_dtype=torch.float32)
    model.to(DEV)
    END_IDS = {i for i in range(len(TOK)) if TOK.decode([i]).strip() in (".", "?")}
    print(f"loaded {name}: {sum(p.numel() for p in model.parameters())/1e6:.0f}M params, vocab {len(TOK)}, "
          f"{len(END_IDS)} sentence-end tokens", flush=True)
    return model


def hidden_and_logits(model, x, am, pick):
    """Run the decoder, then the LM head only at the positions in pick (a bool mask over x[:, :-1])."""
    with amp():
        h = model.get_decoder()(input_ids=x, attention_mask=am).last_hidden_state
        logits = model.get_output_embeddings()(h[:, :-1][pick])
    return logits.float()


def check_amp(model, batch):
    """fp16 can overflow in some models; fall back to fp32 if the loss isn't finite."""
    global AMP_ON
    x, am, y, pick, _ = batch
    with torch.no_grad():
        loss = F.cross_entropy(hidden_and_logits(model, x, am, pick), y[pick])
    if not torch.isfinite(loss):
        AMP_ON = False
        print("fp16 gave a non-finite loss; using fp32", flush=True)
    else:
        print(f"fp16 check ok (loss {loss.item():.3f})", flush=True)


def make_examples(n, seed):
    r = random.Random(seed)
    out = []
    for i in range(n):
        ep = make_episode(r, r.choice(SHORT))
        skin = r.choice(PLAN_SKINS)
        kind = "messy" if r.random() < 0.25 else "clean"
        segs = [(" ".join(problem_words(ep, skin, kind, i)), False)] + plan_segments(ep, skin)
        out.append(tokenize_segments(segs))
    return out


def collate(items):
    L = max(len(i) for i, _ in items)
    x = torch.full((len(items), L), TOK.pad_token_id, dtype=torch.long)
    am = torch.zeros(len(items), L, dtype=torch.long)
    tm = torch.zeros(len(items), L, dtype=torch.bool)
    nxt = []                                    # (row, position, next-sentence token ids) for the slot signal
    for b, (ids, m) in enumerate(items):
        x[b, :len(ids)] = torch.tensor(ids); am[b, :len(ids)] = 1; tm[b, :len(ids)] = torch.tensor(m)
        ends = [p for p, t in enumerate(ids) if t in END_IDS]
        for p, q in zip(ends, ends[1:]):
            nxt.append((b, p, ids[p + 1:q + 1]))
    pick = tm[:, 1:]
    return x.to(DEV), am.to(DEV), x[:, 1:].to(DEV), pick.to(DEV), nxt


def slot_loss(model, nxt):
    S = model.slots.last
    bs = torch.tensor([b for b, _, _ in nxt], device=DEV)
    ps = torch.tensor([p for _, p, _ in nxt], device=DEV)
    z = model.slots.pred(S[bs, ps].flatten(1))
    E = model.get_input_embeddings().weight.float()
    lp = F.log_softmax(z @ E.T, -1)
    rows = torch.tensor([i for i, (_, _, t) in enumerate(nxt) for _ in t], device=DEV)
    cols = torch.tensor([tok for _, _, t in nxt for tok in t], device=DEV)
    return -lp[rows, cols].mean()


def train(model, steps, micro=2, accum=4, lr=2e-5, lr_slots=1e-3, lam=0.3, seed=0):
    model.get_input_embeddings().weight.requires_grad_(False)
    out_emb = model.get_output_embeddings()
    if out_emb is not None:
        out_emb.weight.requires_grad_(False)
    slot_params = list(model.slots.parameters()) if getattr(model, "slots", None) is not None else []
    for p in slot_params:
        p.requires_grad_(True)
    sp = {id(p) for p in slot_params}
    is_lora = any(isinstance(m, LoRALinear) for m in model.modules())
    base = [p for p in model.parameters() if p.requires_grad and id(p) not in sp]
    groups = [{"params": base, "lr": 2e-4 if is_lora else lr}] + ([{"params": slot_params, "lr": lr_slots}] if slot_params else [])
    print(f"training {sum(p.numel() for p in base)/1e6:.1f}M base{' (LoRA)' if is_lora else ''} + "
          f"{sum(p.numel() for p in slot_params)/1e6:.2f}M slot params", flush=True)
    opt = torch.optim.AdamW(groups, weight_decay=0.0, betas=(0.9, 0.95))
    base_lr = [g["lr"] for g in opt.param_groups]
    data = make_examples(max(200, steps * micro * accum), seed)
    data = [d for d in data if len(d[0]) <= 600]
    r = random.Random(seed)
    check_amp(model, collate(data[:micro]))
    scaler = torch.amp.GradScaler("cuda", enabled=AMP_ON)
    model.train(); slots_mode(model, False)
    logs, t0 = [], time.time()
    for step in range(steps):
        f = min(1, (step + 1) / 50) * (0.1 + 0.9 * 0.5 * (1 + math.cos(math.pi * step / steps)))
        for g, b in zip(opt.param_groups, base_lr):
            g["lr"] = b * f
        tot_lm, tot_sl = 0.0, 0.0
        for _ in range(accum):
            x, am, y, pick, nxt = collate([r.choice(data) for _ in range(micro)])
            logits = hidden_and_logits(model, x, am, pick)
            loss = F.cross_entropy(logits, y[pick])
            tot_lm += loss.item() / accum
            if slot_params and nxt:
                sl = slot_loss(model, nxt)
                loss = loss + lam * sl
                tot_sl += sl.item() / accum
            if not torch.isfinite(loss):
                raise RuntimeError(f"non-finite loss at step {step}")
            scaler.scale(loss / accum).backward()
        scaler.unscale_(opt)
        nn.utils.clip_grad_norm_([p for g in opt.param_groups for p in g["params"]], 1.0)
        scaler.step(opt); scaler.update(); opt.zero_grad(set_to_none=True)
        logs.append((tot_lm, tot_sl))
        if (step + 1) % max(1, steps // 10) == 0:
            a = logs[-max(1, steps // 10):]
            print(f"    step {step+1}/{steps}  plan loss {st.mean(x[0] for x in a):.4f}"
                  + (f"  next-sentence {st.mean(x[1] for x in a):.3f}" if slot_params else "")
                  + f"  ({time.time()-t0:.0f}s)", flush=True)
    model.eval()
    return logs


# %% [markdown]
# ## Planning in the world (the harness loop)

# %%
def feed_text(sim, buf):
    """Hand every finished sentence in buf to the checker. Returns (leftover text, search answers to feed back)."""
    injections = []
    while sim.status is None:
        m = re.search(r"[.?]", buf)
        if not m:
            break
        sent, buf = buf[:m.end()], buf[m.end():]
        words = re.sub(r"([.,?:])", r" \1 ", sent.lower()).split()
        inj = sim.step(words) if words else None
        if inj:
            injections.append(inj)
    return buf, injections


@torch.no_grad()
def run_one(model, prefix, ep, skin, kind, seed, max_new=300):
    """Greedy decoding with a KV cache. Each finished sentence goes to the checker; search answers are fed back in."""
    slots_mode(model, True)
    sim = Sim(ep, skin)
    ids = TOK(prefix + " ".join(problem_words(ep, skin, kind, seed)), add_special_tokens=False)["input_ids"]
    with amp():
        out = model(input_ids=torch.tensor([ids], device=DEV), use_cache=True)
    past, logits = out.past_key_values, out.logits[0, -1]
    buf, text = "", ""
    eos = {TOK.eos_token_id, TOK.pad_token_id}
    for _ in range(max_new):
        t = int(logits.argmax())
        if t in eos:
            sim.fail("stopped")
            break
        piece = TOK.decode([t])
        text += piece
        buf, injections = feed_text(sim, buf + piece)
        feed = [t]
        for inj in injections:
            feed += TOK(" " + inj, add_special_tokens=False)["input_ids"]
            text += " " + inj
        if sim.status is not None:
            break
        with amp():
            out = model(input_ids=torch.tensor([feed], device=DEV), past_key_values=past, use_cache=True)
        past, logits = out.past_key_values, out.logits[0, -1]
    if sim.status is None:
        sim.fail("too long")
    sim.text = text.strip()
    slots_mode(model, False)
    return sim


BOOKKEEPING = ("bad go", "bad take", "bad open", "bad unlock", "false claim")


def plan_tests(n):
    r = random.Random(12345)
    return {split: episodes(r, n, combos) for split, combos in (("short", SHORT), ("long", LONG))}


def evaluate_plans(model, n, few_shot, kinds=("clean", "messy", "filler")):
    tests, res, sample = plan_tests(n), {}, None
    t0 = time.time()
    for kind in kinds:
        for split, eps in tests.items():
            sims = []
            for i, ep in enumerate(eps):
                skin = PLAN_SKINS[i % len(PLAN_SKINS)]
                prefix = few_shot_prefix(skin) if few_shot else ""
                sims.append(run_one(model, prefix, ep, skin, kind, i))
            need = [s for s in sims if needed(s)]
            why = {}
            for s in sims:
                if s.status != "ok":
                    why[s.why] = why.get(s.why, 0) + 1
            res[f"{kind}/{split}"] = {
                "success": st.mean(s.status == "ok" for s in sims),
                "looked_when_needed": st.mean(needed(s) <= s.searched for s in need) if need else None,
                "searched_when_not": st.mean(bool(s.searched - needed(s)) for s in sims),
                "fails": why}
            if kind == "clean" and split == "long" and sample is None:
                s = next((x for x in sims if {"H", "L"} <= x.ep["obs"]), sims[0])
                sample = {"problem": " ".join(problem_words(s.ep, s.skin, "clean", 0)), "plan": s.text, "result": s.status}
            print(f"    {kind}/{split}: {res[f'{kind}/{split}']['success']*100:.0f}%  ({time.time()-t0:.0f}s)", flush=True)
    return res, sample


# %% [markdown]
# ## Scoring by likelihood: real messages and kept English

# %%
@torch.no_grad()
def choice_scores(model, prompt, options):
    """Mean log-probability per token of each option after the prompt."""
    p_ids = TOK(prompt, add_special_tokens=False)["input_ids"]
    seqs, spans = [], []
    for o in options:
        o_ids = TOK(o, add_special_tokens=False)["input_ids"]
        seqs.append(p_ids + o_ids); spans.append((len(p_ids), len(p_ids) + len(o_ids)))
    L = max(len(s) for s in seqs)
    x = torch.full((len(seqs), L), TOK.pad_token_id, dtype=torch.long)
    am = torch.zeros(len(seqs), L, dtype=torch.long)
    for b, s in enumerate(seqs):
        x[b, :len(s)] = torch.tensor(s); am[b, :len(s)] = 1
    slots_mode(model, False)
    with amp():
        lg = model(input_ids=x.to(DEV), attention_mask=am.to(DEV)).logits.float()
    lp = F.log_softmax(lg, -1)
    out = []
    for b, (a, e) in enumerate(spans):
        tgt = x[b, a:e].to(DEV)
        out.append(lp[b, a - 1:e - 1].gather(-1, tgt[:, None]).mean().item())
    return out


def message_test(model, msgs):
    by = {"typed": [], "voice": []}
    for m in msgs:
        opts = [m["meant"]] + m["wrong"]
        order = list(range(4)); random.Random(m["id"]).shuffle(order)
        prompt = (m["context"] + "\n" if m["context"] else "") + f'Message: "{m["message"]}"\nWhat the person wants:'
        sc = choice_scores(model, prompt, [" " + opts[i] for i in order])
        by[m["kind"]].append(order[max(range(4), key=lambda j: sc[j])] == 0)
    return {k: (st.mean(v) if v else None) for k, v in by.items()} | {"all": st.mean(by["typed"] + by["voice"]), "n": len(msgs)}


ARC, WIKI = None, None


def load_english(n_arc, n_wiki):
    global ARC, WIKI
    from datasets import load_dataset
    try:
        d = load_dataset("allenai/ai2_arc", "ARC-Easy", split="test")
        ARC = [(r["question"], r["choices"]["text"], r["choices"]["label"].index(r["answerKey"])) for r in d.select(range(n_arc))]
    except Exception as e:
        print("ARC unavailable:", e, flush=True)
    try:
        d = load_dataset("Salesforce/wikitext", "wikitext-2-raw-v1", split="test")
        text = "\n".join(t for t in d["text"] if len(t) > 200)
        ids = TOK(text, add_special_tokens=False)["input_ids"]
        WIKI = [ids[i * 256:(i + 1) * 256] for i in range(n_wiki)]
    except Exception as e:
        print("WikiText unavailable:", e, flush=True)


@torch.no_grad()
def english_test(model):
    out = {}
    if ARC:
        hits = []
        for q, opts, ans in ARC:
            sc = choice_scores(model, f"Question: {q}\nAnswer:", [" " + o for o in opts])
            hits.append(max(range(len(opts)), key=lambda j: sc[j]) == ans)
        out["arc_easy"] = st.mean(hits)
    if WIKI:
        slots_mode(model, False)
        nll = []
        for chunk in WIKI:
            x = torch.tensor([chunk], device=DEV)
            with amp():
                lg = model(input_ids=x).logits.float()
            nll.append(F.cross_entropy(lg[0, :-1], x[0, 1:]).item())
        out["wiki_ppl"] = math.exp(st.mean(nll))
    return out


@torch.no_grad()
def squash_4bit(model, group=64):
    """Round every linear weight in the decoder to 4 bits (symmetric, one scale per group of 64)."""
    for m in model.modules():
        if isinstance(m, LoRALinear):
            m.merge()
    n = 0
    for name, mod in model.get_decoder().named_modules():
        if isinstance(mod, nn.Linear) and mod.weight.shape[1] % group == 0:
            W = mod.weight.data
            Wg = W.reshape(-1, group)
            scale = Wg.abs().amax(1, keepdim=True).clamp(min=1e-8) / 7
            W.copy_(((Wg / scale).round().clamp(-8, 7) * scale).reshape(W.shape))
            n += 1
    print(f"squashed {n} linear layers to 4 bits", flush=True)


# %% [markdown]
# ## Worker and report

# %%
SIZES = {"pilot": dict(steps=20, n=2, msgs=6, arc=10, wiki=4),
         "full": dict(steps=1000, n=24, msgs=10_000, arc=300, wiki=40)}


def short(name):
    return name.split("/")[-1].lower()


def worker():
    name, version, tag = arg("--model"), arg("--version"), arg("--tag", "full")
    cfg = SIZES[tag]
    torch.manual_seed(0); random.seed(0)
    t0 = time.time()
    model = load(name)
    model.eval()
    msgs = json.load(open("messages.json"))[: cfg["msgs"]]
    load_english(cfg["arc"], cfg["wiki"])
    row = {"model": name, "version": version, "tag": tag}
    if version in ("ft-slots", "lora-slots"):
        attach_slots(model)
    if version == "lora-slots":
        attach_lora(model)
    if version != "untouched":
        logs = train(model, cfg["steps"])
        row["final_plan_loss"] = st.mean(x[0] for x in logs[-max(1, len(logs) // 10):])
        row["train_s"] = round(time.time() - t0)
    row["plans"], row["sample"] = evaluate_plans(model, cfg["n"], few_shot=version == "untouched")
    row["messages"] = message_test(model, msgs)
    row["english"] = english_test(model)
    if version != "untouched":
        squash_4bit(model)
        row["plans_4bit"], _ = evaluate_plans(model, cfg["n"], few_shot=False)
        row["messages_4bit"] = message_test(model, msgs)
        row["english_4bit"] = english_test(model)
    row["total_s"] = round(time.time() - t0)
    with open(f"{tag}_{short(name)}_{version}.json", "w") as f:
        json.dump(row, f, indent=1)
    print(f"== {version} done in {row['total_s']}s: messages {row['messages']}, english {row['english']}", flush=True)


def report():
    import glob
    name = arg("--model")
    rows = {r["version"]: r for r in map(lambda f: json.load(open(f)), glob.glob(f"full_{short(name)}_*.json"))}
    pct = lambda v: "–" if v is None else f"{v*100:.0f}%"
    L = [f"# Fine-tune test: {name}", ""]
    if os.path.exists("PILOT.md"):
        L += [open("PILOT.md").read().strip(), ""]
    order = [v for v in ("untouched", "ft", "ft-slots", "lora-slots") if v in rows]
    if not order:
        L.append("No full results (see the pilot above).")
    else:
        n = SIZES["full"]["n"]
        L += [f"One seed. {n} problems per cell, spread over the four skins. Untouched is shown two worked examples;",
              "the fine-tunes see none. Clean = as trained; messy = periods removed (a quarter of training was like this);",
              "filler = periods removed plus speech filler (\"um\", \"like\", \"you know\"…), never seen in training.", "",
              "## Planning in the world", "",
              "| version | clean short | clean long | messy short | messy long | filler short | filler long | searched when needed | bookkeeping fails |",
              "|---|---|---|---|---|---|---|---|---|"]

        def plan_row(label, P):
            look = [v["looked_when_needed"] for v in P.values() if v["looked_when_needed"] is not None]
            book = sum(v["fails"].get(k, 0) for v in P.values() for k in BOOKKEEPING)
            cells = " | ".join(pct(P[f"{k}/{s}"]["success"]) for k in ("clean", "messy", "filler") for s in ("short", "long"))
            return f"| {label} | {cells} | {pct(st.mean(look) if look else None)} | {book} |"

        for v in order:
            L.append(plan_row(v, rows[v]["plans"]))
        for v in order:
            if "plans_4bit" in rows[v]:
                L.append(plan_row(v + ", 4-bit", rows[v]["plans_4bit"]))
        L += ["", "## Why plans failed (clean + messy + filler)", ""]
        for v in order:
            why = {}
            for c in rows[v]["plans"].values():
                for k, n_ in c["fails"].items():
                    why[k] = why.get(k, 0) + n_
            L.append(f"- {v}: " + (", ".join(f"{k} {n_}" for k, n_ in sorted(why.items(), key=lambda x: -x[1])) or "none"))
        nm = rows[order[0]]["messages"]["n"]
        L += ["", f"## Keal's real messages ({nm}: pick what he meant out of four; chance 25%)", "",
              "| version | typed | voice | all | 4-bit all |", "|---|---|---|---|---|"]
        for v in order:
            m, m4 = rows[v]["messages"], rows[v].get("messages_4bit")
            L.append(f"| {v} | {pct(m['typed'])} | {pct(m['voice'])} | {pct(m['all'])} | {pct(m4['all']) if m4 else '–'} |")
        L += ["", "## English kept", "", "| version | ARC-Easy | WikiText-2 perplexity | 4-bit ARC | 4-bit perplexity |", "|---|---|---|---|---|"]
        for v in order:
            e, e4 = rows[v]["english"], rows[v].get("english_4bit", {})
            f = lambda d, k, p: (pct(d[k]) if p else f"{d[k]:.1f}") if k in d else "–"
            L.append(f"| {v} | {f(e,'arc_easy',1)} | {f(e,'wiki_ppl',0)} | {f(e4,'arc_easy',1)} | {f(e4,'wiki_ppl',0)} |")
        L += ["", "## Time", ""] + [f"- {v}: {rows[v]['total_s']/60:.0f} min" + (f" (training {rows[v]['train_s']/60:.0f} min, final plan loss {rows[v]['final_plan_loss']:.4f})" if "train_s" in rows[v] else "") for v in order]
        L += ["", "## One long problem (clean)", ""]
        for v in order:
            s = rows[v]["sample"]
            if s:
                L += [f"- {v} ({s['result']}): problem `{s['problem']}`", f"  plan: `{s['plan']}`"]
    text = "\n".join(L) + "\n"
    open(f"FT_RESULTS_{short(name)}.md", "w").write(text)
    print(text)


if __name__ == "__main__":
    cmd = ARGV[1] if len(ARGV) > 1 else ""
    if cmd == "worker":
        worker()
    elif cmd == "report":
        report()
    elif cmd != "--no-run":
        print(__doc__)
