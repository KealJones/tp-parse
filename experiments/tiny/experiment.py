"""Does learning toki pona first make a tiny transformer learn English faster?

No labels anywhere: every model only ever predicts the next word.

Model: a one-layer transformer (word vectors -> attention -> MLP -> next word).
Each language has its own word table (used for both input and output); the
attention and MLP in the middle are shared. So when a model trained on toki pona
moves on to English, it starts with a brand-new English word table but keeps the
"thinking" layers it built for toki pona.

Conditions (all then trained on the same English sentences):
  fresh            no pretraining
  tp               pretrained on toki pona about the same world
  tp-frozen        same, but the shared layers are locked during English
  tp-nonsense      pretrained on toki pona grammar with random meanings (control:
                   same grammar, no world knowledge)
  tp-random        pretrained on random toki pona words (control: just practice)
  tp+dict          like tp, plus a 4-pair seed dictionary pulling those English
                   word vectors toward their toki pona ones

Run: python3 experiment.py   (a few minutes on a laptop CPU)
"""
import json, math, random, sys, time
import torch
import torch.nn as nn
import torch.nn.functional as F
from world import corpus, NOUNS, ADJS

torch.set_num_threads(2)
D, HEADS, MLP, CTX = 32, 2, 64, 16
PRE_SENTS, PRE_STEPS = 4000, 1500
EN_SIZES = [25, 50, 100, 200, 400]
EN_STEPS, EVAL_EVERY = 600, 25
SEEDS = list(range(int(sys.argv[1]) if len(sys.argv) > 1 else 6))
CONDITIONS = ["fresh", "tp", "tp-frozen", "tp-nonsense", "tp-random", "tp+dict"]

# Seed dictionary for tp+dict, and the words it's scored on (none overlap).
DICT = [("dog", "soweli"), ("bread", "pan"), ("house", "tomo"), ("good", "pona")]
SINGLE = [("person", "jan"), ("bird", "waso"), ("fish", "kala"), ("fruit", "kili"), ("water", "telo"),
          ("big", "suli"), ("small", "lili"), ("bad", "ike"), ("sweet", "suwi"),
          ("eats", "moku"), ("drinks", "moku"), ("goes", "tawa"), ("sleeps", "lape"), ("sees", "lukin"), ("loves", "olin"),
          ("dog", "soweli"), ("bread", "pan"), ("house", "tomo"), ("good", "pona")]
COMPOUNDS = [("cake", ("pan", "suwi")), ("cat", ("soweli", "lili")), ("tree", ("kasi", "suli")),
             ("lake", ("telo", "suli")), ("child", ("jan", "lili"))]
CONTENT_EN = {w for _, w in NOUNS.values()} | {w for _, w in ADJS.values()}


def vocab_of(sents):
    return sorted({w for s in sents for w in s.split()})


class Shared(nn.Module):
    """Everything except the word tables: positions, attention, MLP."""
    def __init__(self):
        super().__init__()
        self.pos = nn.Parameter(torch.randn(CTX, D) * 0.02)
        self.ln1, self.ln2, self.ln3 = nn.LayerNorm(D), nn.LayerNorm(D), nn.LayerNorm(D)
        self.attn = nn.MultiheadAttention(D, HEADS, batch_first=True)
        self.mlp = nn.Sequential(nn.Linear(D, MLP), nn.GELU(), nn.Linear(MLP, D))
        self.register_buffer("mask", torch.triu(torch.ones(CTX, CTX, dtype=torch.bool), 1))

    def forward(self, x):  # x: (B, T, D) word vectors
        T = x.shape[1]
        h = x + self.pos[:T]
        a = self.ln1(h)
        h = h + self.attn(a, a, a, attn_mask=self.mask[:T, :T], need_weights=False)[0]
        h = h + self.mlp(self.ln2(h))
        return self.ln3(h)


def logits(shared, table, idx):
    h = shared(table[idx])
    return h @ table.T  # tied: the same word table reads words in and writes them out


def stream(sents, stoi, r):
    s = sents[:]
    r.shuffle(s)
    return torch.tensor([stoi[w] for sent in s for w in sent.split()])


def batches(tokens, r, n=32):
    starts = [r.randrange(0, len(tokens) - CTX - 1) for _ in range(n)]
    x = torch.stack([tokens[i:i + CTX] for i in starts])
    y = torch.stack([tokens[i + 1:i + CTX + 1] for i in starts])
    return x, y


def evaluate(shared, table, tokens, content_ids):
    with torch.no_grad():
        n = (len(tokens) - 1) // CTX
        x = tokens[: n * CTX].view(n, CTX)
        y = tokens[1: n * CTX + 1].view(n, CTX)
        lg = logits(shared, table, x)
        loss = F.cross_entropy(lg.reshape(-1, lg.shape[-1]), y.reshape(-1), reduction="none")
        is_content = torch.isin(y.reshape(-1), content_ids)
        return loss.mean().item(), loss[is_content].mean().item()


def new_table(n, g):
    return nn.Parameter(torch.randn(n, D, generator=g) * 0.1)


def pretrain(kind, seed, tp_stoi):
    g = torch.Generator().manual_seed(seed)
    torch.manual_seed(seed)
    shared = Shared()
    table = new_table(len(tp_stoi), g)
    sents = corpus(kind, PRE_SENTS, seed=1000 + seed)
    r = random.Random(seed)
    opt = torch.optim.AdamW(list(shared.parameters()) + [table], lr=3e-3, weight_decay=0.01)
    for _ in range(PRE_STEPS):
        if _ % 50 == 0:  # reshuffle the sentence order now and then
            toks = stream(sents, tp_stoi, r)
        x, y = batches(toks, r)
        loss = F.cross_entropy(logits(shared, table, x).reshape(-1, len(tp_stoi)), y.reshape(-1))
        opt.zero_grad(); loss.backward(); opt.step()
    return shared, table.detach()


def train_english(shared, tp_table, cond, n_sents, seed, en_stoi, tp_stoi, test_toks, content_ids):
    g = torch.Generator().manual_seed(10_000 + seed)
    table = new_table(len(en_stoi), g)
    frozen = cond == "tp-frozen"
    for p in shared.parameters():
        p.requires_grad_(not frozen)
    params = [table] + ([] if frozen else list(shared.parameters()))
    opt = torch.optim.AdamW(params, lr=3e-3, weight_decay=0.01)
    sents = corpus("en", n_sents, seed=2000 + seed)
    r = random.Random(seed)
    toks = stream(sents * max(1, 200 // n_sents), en_stoi, r)
    best = (math.inf, math.inf)
    curve = []
    for step in range(1, EN_STEPS + 1):
        x, y = batches(toks, r)
        loss = F.cross_entropy(logits(shared, table, x).reshape(-1, len(en_stoi)), y.reshape(-1))
        if cond == "tp+dict":
            e = torch.stack([table[en_stoi[a]] for a, _ in DICT])
            t = torch.stack([tp_table[tp_stoi[b]] for _, b in DICT])
            loss = loss + 1.0 * ((e - t) ** 2).sum(-1).mean()
        opt.zero_grad(); loss.backward(); opt.step()
        if step % EVAL_EVERY == 0:
            ev = evaluate(shared, table.detach(), test_toks, content_ids)
            curve.append(ev)
            if ev[0] < best[0]:  # keep the best checkpoint (early stopping)
                best = ev
                best_table = table.detach().clone()
    return best, best_table, curve


def alignment(en_table, tp_table, en_stoi, tp_stoi, skip_dict):
    en = F.normalize(en_table, dim=-1)
    tp = F.normalize(tp_table, dim=-1)
    tp_words = list(tp_stoi)
    hits, total = 0, 0
    for a, b in SINGLE:
        if skip_dict and (a, b) in DICT:
            continue
        sims = tp @ en[en_stoi[a]]
        top = tp_words[sims.argmax().item()]
        hits += top == b
        total += 1
    comp = []
    for a, (p1, p2) in COMPOUNDS:
        sims = tp @ en[en_stoi[a]]
        top2 = {tp_words[i] for i in sims.topk(2).indices.tolist()}
        both = F.normalize(tp_table[tp_stoi[p1]] + tp_table[tp_stoi[p2]], dim=-1)
        comp.append({"word": a, "top2_is_parts": top2 == {p1, p2}, "parts_in_top2": len(top2 & {p1, p2}),
                     "cos_to_sum": round((both @ en[en_stoi[a]]).item(), 3)})
    return hits / total, comp


def main():
    t0 = time.time()
    tp_vocab = vocab_of(corpus("tp", 3000, 0) + corpus("tp-random", 100, 0))
    en_vocab = vocab_of(corpus("en", 3000, 0))
    tp_stoi = {w: i for i, w in enumerate(tp_vocab)}
    en_stoi = {w: i for i, w in enumerate(en_vocab)}
    test = corpus("en", 600, seed=99)
    test_toks = torch.tensor([en_stoi[w] for s in test for w in s.split()])
    content_ids = torch.tensor([en_stoi[w] for w in CONTENT_EN])
    chance_single = 1 / len(tp_vocab)

    results = []
    for seed in SEEDS:
        pre = {k: pretrain(k, seed, tp_stoi) for k in ["tp", "tp-nonsense", "tp-random"]}
        for cond in CONDITIONS:
            for n in EN_SIZES:
                if cond == "fresh":
                    torch.manual_seed(seed)
                    shared, tp_table = Shared(), torch.randn(len(tp_stoi), D) * 0.1
                else:
                    src = {"tp": "tp", "tp-frozen": "tp", "tp+dict": "tp"}.get(cond, cond)
                    shared = Shared(); shared.load_state_dict(pre[src][0].state_dict())
                    tp_table = pre[src][1]
                (loss, content_loss), en_table, curve = train_english(
                    shared, tp_table, cond, n, seed, en_stoi, tp_stoi, test_toks, content_ids)
                acc, comp = alignment(en_table, tp_table, en_stoi, tp_stoi, skip_dict=(cond == "tp+dict"))
                results.append({"seed": seed, "cond": cond, "n": n, "loss": loss, "content_loss": content_loss,
                                "align": acc, "compounds": comp,
                                "steps_to_1_0": next((i * EVAL_EVERY for i, c in enumerate(curve, 1) if c[0] < 1.0), None)})
        print(f"seed {seed} done ({time.time() - t0:.0f}s)", flush=True)

    json.dump({"results": results, "chance_align": chance_single, "tp_vocab": tp_vocab, "en_vocab": en_vocab},
              open("results.json", "w"), indent=1)
    print(f"saved results.json ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
