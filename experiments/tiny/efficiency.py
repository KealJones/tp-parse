"""Do planted hubs make English cheaper to learn? And is protection needed?

Every model goes: toki pona (4,000 sentences) -> mixed bridge (Spanglish-style
sentences) -> English with only N sentences, N in 50/100/200/400.

  planted+ewc     concepts planted in chosen MLP blocks, lightly protected
  planted         planted, no protection
  unplanted+ewc   same data and protection, nothing planted  <- the fair control:
                  identical training, only the planting differs
  english         English only, N sentences (context, not a fair comparison:
                  the others also saw English inside the mixed bridge)

Measured: English test loss after training on N sentences (lower = learned more
from less), and the hub score from the knockout test.
Run at 1 and 2 layers.

Run: python3 efficiency.py [seeds]
"""
import copy, json, math, random, statistics as st, sys, time
import torch
import torch.nn as nn
import torch.nn.functional as F
from stages import tp_corpus, en_corpus, to_ids, dict_lines, CTX, MLP, S1_STEPS
from knockout import train, knockout_matrix, CONCEPTS, ENGLISH, BLOCKS
from bridge import mixed_corpus
from ewc import fisher

SEEDS = list(range(int(sys.argv[1]) if len(sys.argv) > 1 else 6))
D, HEADS = 48, 4
BRIDGE_STEPS, EN_STEPS, EVAL_EVERY = 1200, 800, 50
SIZES = [50, 100, 200, 400]
LAYERS = [1, 2]
CONDITIONS = ["planted+ewc", "planted", "unplanted+ewc", "english"]


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


class DeepModel(nn.Module):
    """Same as the 1-layer model, but with L layers; planting and knockouts apply to every layer's MLP."""
    def __init__(self, V, layers):
        super().__init__()
        self.emb = nn.Embedding(V, D)
        nn.init.normal_(self.emb.weight, std=0.1)
        self.pos = nn.Parameter(torch.randn(CTX, D) * 0.02)
        self.blocks = nn.ModuleList(Block() for _ in range(layers))
        self.ln_f = nn.LayerNorm(D)
        self.register_buffer("mask", torch.triu(torch.ones(CTX, CTX, dtype=torch.bool), 1))

    def forward(self, idx, route=None, knock=None):
        T = idx.shape[1]
        h = self.emb(idx) + self.pos[:T]
        for b in self.blocks:
            h = b(h, self.mask[:T, :T], route, knock)
        return self.ln_f(h) @ self.emb.weight.T


@torch.no_grad()
def test_loss(model, toks):
    n = (len(toks) - 1) // CTX
    x = toks[: n * CTX].view(n, CTX)
    y = toks[1: n * CTX + 1].view(n, CTX)
    return F.cross_entropy(model(x).reshape(-1, model.emb.num_embeddings), y.reshape(-1)).item()


def train_english(model, sents, stoi, itos, r, test_toks, old, imp, strength):
    """Train on a small English set; keep the best test loss (early stopping)."""
    best = math.inf
    best_state = None
    opt = torch.optim.AdamW(model.parameters(), lr=3e-3, weight_decay=0.0 if strength else 0.01)
    toks = to_ids(sents * max(1, 400 // len(sents)), stoi)
    for step in range(1, EN_STEPS + 1):
        starts = [r.randrange(0, len(toks) - CTX - 1) for _ in range(32)]
        x = torch.stack([toks[i:i + CTX] for i in starts])
        y = torch.stack([toks[i + 1:i + CTX + 1] for i in starts])
        loss = F.cross_entropy(model(x).reshape(-1, model.emb.num_embeddings), y.reshape(-1))
        if strength:
            loss = loss + strength * 1000 * sum((imp[n] * (p - old[n]) ** 2).sum() for n, p in model.named_parameters())
        opt.zero_grad(); loss.backward(); opt.step()
        if step % EVAL_EVERY == 0:
            l = test_loss(model, test_toks)
            if l < best:
                best, best_state = l, copy.deepcopy(model.state_dict())
    model.load_state_dict(best_state)
    return best


def hub_score(m):
    return st.mean(m[k][k] - st.mean(m[k][t] for t in CONCEPTS if t != k) for k in CONCEPTS)


def main():
    t0 = time.time()
    vocab = sorted({w for s in tp_corpus(3000, 0) + en_corpus(3000, 0) + dict_lines() + mixed_corpus(3000, 0)
                    for w in s.split()})
    stoi = {w: i for i, w in enumerate(vocab)}
    itos = {i: w for w, i in stoi.items()}
    en_test = to_ids(en_corpus(800, 78), stoi)
    out = []
    for layers in LAYERS:
        for seed in SEEDS:
            rng = random.Random(seed)
            for cond in CONDITIONS:
                torch.manual_seed(seed)
                r = random.Random(seed)
                prefix = DeepModel(len(vocab), layers)
                old = imp = None
                strength = 10 if cond.endswith("ewc") else 0
                if cond != "english":
                    planted = cond.startswith("planted")
                    train(prefix, lambda: tp_corpus(4000, 1000 + seed), S1_STEPS, stoi, itos, r, routed=planted)
                    old = {n: p.detach().clone() for n, p in prefix.named_parameters()}
                    imp = fisher(prefix, tp_corpus(1000, 4000 + seed), stoi, random.Random(seed))
                    train(prefix, lambda: mixed_corpus(2000, 5000 + seed), BRIDGE_STEPS, stoi, itos, r,
                          routed=planted, old=old, imp=imp, strength=strength)
                for n in SIZES:
                    model = copy.deepcopy(prefix)
                    loss = train_english(model, en_corpus(n, 2000 + seed), stoi, itos, random.Random(seed + n),
                                         en_test, old, imp, strength)
                    _, m = knockout_matrix(model, en_test, stoi, ENGLISH, rng)
                    out.append({"layers": layers, "seed": seed, "cond": cond, "n": n, "en_loss": loss, "hub": hub_score(m)})
            print(f"layers {layers} seed {seed} done ({time.time() - t0:.0f}s)", flush=True)
            json.dump(out, open("efficiency_results.json", "w"), indent=1)
    print(f"saved efficiency_results.json ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
