"""Plant reasoning hubs in toki pona, then test few-shot English reasoning.

Reasoning patterns (toki pona / English):
  NEG   A li P ala . A li Q .                       the A is not P . the A is Q .
  SAME  A li P . B li sama A . B li P .             the A is P . the B is the same as the A . the B is P .
  DIFF  A li P . B li ante A . B li Q .             the A is P . the B is different from the A . the B is Q .
  IF    A li wile moku la A li moku . A li wile moku . A li moku .
                                                    if the A is hungry , the A eats . the A is hungry . the A eats .
  CAUSE A li moku tan ni : A li wile moku .         the A eats because the A is hungry .
(P/Q are opposites: big/small, good/bad, hot/cold. hungry->eats, tired->sleeps.)

Stages:
  1. toki pona: all patterns + plain sentences (4,000 episodes)
  2. bridge: plain English sentences (no reasoning patterns), with words swapped
     to toki pona half the time -- links words, teaches no English reasoning
  3. English: plain sentences + only N examples of each reasoning pattern

Conditions (identical data except where noted):
  planted    stage 1 with gradient routing: predictions inside a NEG episode may
             only update the ala block (+ shared neurons), SAME -> sama block,
             DIFF -> ante, IF -> la, CAUSE -> tan; plain -> shared only
  unplanted  same stages, no routing
  english    no toki pona: plain English instead of stages 1-2, then stage 3

Test: fresh English reasoning episodes; does the model put the right word in the
answer slot (choosing among that slot's options)? Plus knockouts of each planted block.

Run: python3 reasoning.py [seeds]
"""
import json, random, statistics as st, sys, time
import torch
import torch.nn as nn
import torch.nn.functional as F

torch.set_num_threads(2)
SEEDS = list(range(int(sys.argv[1]) if len(sys.argv) > 1 else 4))
D, HEADS, MLP, CTX, LAYERS = 48, 4, 96, 32, 2
S1, S2, S3 = 1500, 1200, 800
NS = [4, 16, 64]
BLOCK = 8
PATTERNS = ["NEG", "SAME", "DIFF", "IF", "CAUSE"]
HUB = {"NEG": "ala", "SAME": "sama", "DIFF": "ante", "IF": "la", "CAUSE": "tan"}
BLOCKS = {p: list(range(i * BLOCK, (i + 1) * BLOCK)) for i, p in enumerate(PATTERNS)}
SHARED = list(range(len(PATTERNS) * BLOCK, MLP))

ENT = [("soweli", "dog"), ("soweli lili", "cat"), ("waso", "bird"), ("jan", "person"), ("jan lili", "child"), ("kala", "fish")]
ADJ = [("suli", "big", "lili", "small"), ("pona", "good", "ike", "bad"), ("seli", "hot", "lete", "cold")]
STATE = [("wile moku", "hungry", "moku", "eats"), ("wile lape", "tired", "lape", "sleeps")]
ADJ_EN = [a[1] for a in ADJ] + [a[3] for a in ADJ]
ACT_EN = [s[3] for s in STATE]
STATE_EN = [s[1] for s in STATE]


def pick_adj(r):
    tp1, en1, tp2, en2 = r.choice(ADJ)
    return (tp1, en1, tp2, en2) if r.random() < 0.5 else (tp2, en2, tp1, en1)


def episode(kind, r):
    """Returns (toki pona, english, english answer, answer options). Answer is the last content word."""
    (ta, ea), (tb, eb) = r.sample(ENT, 2)
    if kind == "PLAIN":
        if r.random() < 0.5:
            tp, en, _, _ = pick_adj(r)
            return f"{ta} li {tp} .", f"the {ea} is {en} .", None, None
        s = r.choice(STATE)
        return (f"{ta} li {s[0]} .", f"the {ea} is {s[1]} .", None, None) if r.random() < 0.5 else \
               (f"{ta} li {s[2]} .", f"the {ea} {s[3]} .", None, None)
    if kind == "NEG":
        tp, en, tq, eq = pick_adj(r)
        return f"{ta} li {tp} ala . {ta} li {tq} .", f"the {ea} is not {en} . the {ea} is {eq} .", eq, ADJ_EN
    if kind == "SAME":
        tp, en, _, _ = pick_adj(r)
        return f"{ta} li {tp} . {tb} li sama {ta} . {tb} li {tp} .", \
               f"the {ea} is {en} . the {eb} is the same as the {ea} . the {eb} is {en} .", en, ADJ_EN
    if kind == "DIFF":
        tp, en, tq, eq = pick_adj(r)
        return f"{ta} li {tp} . {tb} li ante {ta} . {tb} li {tq} .", \
               f"the {ea} is {en} . the {eb} is different from the {ea} . the {eb} is {eq} .", eq, ADJ_EN
    if kind == "IF":
        s = r.choice(STATE)
        return f"{ta} li {s[0]} la {ta} li {s[2]} . {ta} li {s[0]} . {ta} li {s[2]} .", \
               f"if the {ea} is {s[1]} , the {ea} {s[3]} . the {ea} is {s[1]} . the {ea} {s[3]} .", s[3], ACT_EN
    if kind == "CAUSE":
        s = r.choice(STATE)
        return f"{ta} li {s[2]} tan ni : {ta} li {s[0]} .", f"the {ea} {s[3]} because the {ea} is {s[1]} .", s[1], STATE_EN
    raise ValueError(kind)


def tp_stage(n, seed):
    r = random.Random(seed)
    kinds = PATTERNS * 2 + ["PLAIN"] * 3
    return [(k, episode(k, r)[0]) for k in (r.choice(kinds) for _ in range(n))]


SWAP = {**{e: t for t, e in ENT}, **{a[1]: a[0] for a in ADJ}, **{a[3]: a[2] for a in ADJ},
        **{s[1]: s[0] for s in STATE}, **{s[3]: s[2] for s in STATE}}


def bridge_stage(n, seed, mix=True):
    r = random.Random(seed)
    out = []
    for _ in range(n):
        en = episode("PLAIN", r)[1]
        if mix:
            en = " ".join(SWAP[w] if w in SWAP and r.random() < 0.5 else w for w in en.split())
        out.append(("PLAIN", en))
    return out


def en_stage(n_each, seed, plain=400):
    r = random.Random(seed)
    eps = [("PLAIN", episode("PLAIN", r)[1]) for _ in range(plain)]
    for k in PATTERNS:
        eps += [(k, episode(k, r)[1]) for _ in range(n_each)]
    return eps


class Block(nn.Module):
    def __init__(self):
        super().__init__()
        self.ln1, self.ln2 = nn.LayerNorm(D), nn.LayerNorm(D)
        self.attn = nn.MultiheadAttention(D, HEADS, batch_first=True)
        self.up, self.down = nn.Linear(D, MLP), nn.Linear(MLP, D)

    def forward(self, h, mask, route, knock):
        a = self.ln1(h)
        h = h + self.attn(a, a, a, attn_mask=mask, need_weights=False)[0]
        z = F.gelu(self.up(self.ln2(h)))
        if route is not None:
            z = z * route + (z * (1 - route)).detach()
        if knock is not None:
            z = z.clone(); z[..., knock] = 0
        return h + self.down(z)


class Model(nn.Module):
    def __init__(self, V):
        super().__init__()
        self.emb = nn.Embedding(V, D)
        nn.init.normal_(self.emb.weight, std=0.1)
        self.pos = nn.Parameter(torch.randn(CTX, D) * 0.02)
        self.blocks = nn.ModuleList(Block() for _ in range(LAYERS))
        self.ln_f = nn.LayerNorm(D)
        self.register_buffer("mask", torch.triu(torch.ones(CTX, CTX, dtype=torch.bool), 1))

    def forward(self, idx, route=None, knock=None):
        T = idx.shape[1]
        h = self.emb(idx) + self.pos[:T]
        for b in self.blocks:
            h = b(h, self.mask[:T, :T], route, knock)
        return self.ln_f(h) @ self.emb.weight.T


ROUTE = torch.zeros(len(PATTERNS) + 1, MLP)
for i, p in enumerate(PATTERNS):
    ROUTE[i, BLOCKS[p] + SHARED] = 1
ROUTE[len(PATTERNS), SHARED] = 1
KIND_ID = {p: i for i, p in enumerate(PATTERNS)} | {"PLAIN": len(PATTERNS)}


def stream(eps, stoi, r):
    eps = eps[:]
    r.shuffle(eps)
    toks, kinds = [], []
    for k, s in eps:
        ws = s.split()
        toks += [stoi[w] for w in ws]
        kinds += [KIND_ID[k]] * len(ws)
    return torch.tensor(toks), torch.tensor(kinds)


def train(model, eps_fn, steps, stoi, r, routed=False):
    opt = torch.optim.AdamW(model.parameters(), lr=3e-3, weight_decay=0.01)
    for step in range(steps):
        if step % 100 == 0:
            toks, kinds = stream(eps_fn(), stoi, r)
        starts = [r.randrange(0, len(toks) - CTX - 1) for _ in range(32)]
        x = torch.stack([toks[i:i + CTX] for i in starts])
        y = torch.stack([toks[i + 1:i + CTX + 1] for i in starts])
        route = ROUTE[torch.stack([kinds[i + 1:i + CTX + 1] for i in starts])] if routed else None
        loss = F.cross_entropy(model(x, route=route).reshape(-1, model.emb.num_embeddings), y.reshape(-1))
        opt.zero_grad(); loss.backward(); opt.step()


def test_set(seed, n=60):
    r = random.Random(seed)
    out = []
    for k in PATTERNS:
        for _ in range(n):
            _, en, ans, opts = episode(k, r)
            ws = en.split()
            cut = len(ws) - 2  # drop answer and final "."
            assert ws[cut] == ans
            out.append((k, ws[:cut], ans, opts))
    return out


@torch.no_grad()
def accuracy(model, tests, stoi, knock=None):
    res = {k: [] for k in PATTERNS}
    by_len = {}
    for t in tests:
        by_len.setdefault(len(t[1]), []).append(t)
    for L, group in by_len.items():
        x = torch.tensor([[stoi["."]] + [stoi[w] for w in g[1]] for g in group])[:, -CTX:]
        lg = model(x, knock=knock)[:, -1]
        for g, row in zip(group, lg):
            opts = g[3]
            best = max(opts, key=lambda o: row[stoi[o]].item())
            res[g[0]].append(best == g[2])
    return {k: sum(v) / len(v) for k, v in res.items()}


def main():
    t0 = time.time()
    vocab = set()
    for s in [e for _, e in tp_stage(3000, 0)] + [e for _, e in bridge_stage(3000, 0)] + [e for _, e in en_stage(200, 0)]:
        vocab |= set(s.split())
    stoi = {w: i for i, w in enumerate(sorted(vocab))}
    tests = test_set(999)
    out = []
    for seed in SEEDS:
        for cond in ["planted", "unplanted", "english"]:
            torch.manual_seed(seed)
            r = random.Random(seed)
            base = Model(len(stoi))
            if cond == "english":
                train(base, lambda: bridge_stage(4000, 5000 + seed, mix=False), S1 + S2, stoi, r)
            else:
                train(base, lambda: tp_stage(4000, 1000 + seed), S1, stoi, r, routed=(cond == "planted"))
                train(base, lambda: bridge_stage(2000, 5000 + seed), S2, stoi, r)
            for n in NS:
                model = Model(len(stoi)); model.load_state_dict(base.state_dict())
                rr = random.Random(seed * 100 + n)
                train(model, lambda: en_stage(n, 2000 + seed + n), S3, stoi, rr)
                acc = accuracy(model, tests, stoi)
                ko = {p: accuracy(model, tests, stoi, knock=BLOCKS[p]) for p in PATTERNS}
                out.append({"seed": seed, "cond": cond, "n": n, "acc": acc, "knockout": ko})
        print(f"seed {seed} done ({time.time() - t0:.0f}s)", flush=True)
        json.dump(out, open("reasoning_results.json", "w"), indent=1)
    report(out)


def report(R):
    L = ["# Reasoning hubs: results", "",
         f"{len({r['seed'] for r in R})} seeds. Accuracy at the answer slot on new English reasoning episodes.",
         "Chance: NEG/SAME/DIFF 1 in 6, IF/CAUSE 1 in 2. N = English examples of each pattern seen in training.", ""]
    for n in NS:
        L += [f"## N = {n}", "", "| condition | " + " | ".join(PATTERNS) + " | mean |", "|---" * (len(PATTERNS) + 2) + "|"]
        for c in ["planted", "unplanted", "english"]:
            rows = [r["acc"] for r in R if r["cond"] == c and r["n"] == n]
            if not rows:
                continue
            vals = [st.mean(x[p] for x in rows) for p in PATTERNS]
            L.append(f"| {c} | " + " | ".join(f"{v*100:.0f}%" for v in vals) + f" | {st.mean(vals)*100:.0f}% |")
        L.append("")
    L += ["## Knockouts (planted): accuracy drop on own pattern vs average drop on other patterns", "",
          "| N | " + " | ".join(f"{p} ({HUB[p]})" for p in PATTERNS) + " |", "|---" * (len(PATTERNS) + 1) + "|"]
    for n in NS:
        cells = []
        for p in PATTERNS:
            rows = [r for r in R if r["cond"] == "planted" and r["n"] == n]
            own = st.mean(r["acc"][p] - r["knockout"][p][p] for r in rows)
            oth = st.mean(r["acc"][q] - r["knockout"][p][q] for r in rows for q in PATTERNS if q != p)
            cells.append(f"{own*100:+.0f} / {oth*100:+.0f}")
        L.append(f"| {n} | " + " | ".join(cells) + " |")
    L += ["", "Each cell: points lost on its own pattern / on other patterns when that hub's block is switched off.", ""]
    L += ["## Planted vs unplanted per seed (mean accuracy over patterns)", ""]
    for n in NS:
        d = []
        for s in sorted({r["seed"] for r in R}):
            a = [st.mean(r["acc"].values()) for r in R if r["seed"] == s and r["n"] == n and r["cond"] == "planted"]
            b = [st.mean(r["acc"].values()) for r in R if r["seed"] == s and r["n"] == n and r["cond"] == "unplanted"]
            if a and b:
                d.append(a[0] - b[0])
        if d:
            L.append(f"- N={n}: planted ahead by {st.mean(d)*100:+.1f} points on average, better in {sum(x > 0 for x in d)}/{len(d)} seeds")
    open("REASONING_RESULTS.md", "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
