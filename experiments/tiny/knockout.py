"""Keal's grid idea, at toy scale: plant concepts in chosen neurons, then knock them out.

Stage 1 (toki pona) uses gradient routing: when the next word to predict is a
concept word, only that concept's block of MLP neurons is allowed to learn from
that prediction.
    neurons  0-7  telo (water)     8-15 moku (eat)    16-23 tomo (house)
            24-31 waso (bird)     32-39 kili (fruit) 40-47 pan (bread)
            48-55 kala (fish)     56-63 soweli (animal)  64-71 jan (person)
            72-95 free (grammar and everything else)
The model still *uses* all neurons on every word; routing only limits where
learning from each word can land.

Stage 2: a big English sweep, no restrictions.

Knockout: switch off one concept's block (force it to 0) and measure how much
worse the model gets at predicting each concept's English words (e.g. "water" in
"the dog drinks the ___"). If English runs through the planted spots, knocking
out the telo block should hurt water/liquid much more than bird or house.

Conditions:
  routed        routed toki pona -> English
  routed+ewc    same, with light EWC protecting stage-1 weights during English
  unrouted      ordinary toki pona -> English (blocks mean nothing; control)
  english       English only (control)
Plus a random-neuron knockout in every condition.

Run: python3 knockout.py [seeds]
"""
import copy, json, random, sys, time
import torch
import torch.nn.functional as F
from stages import Model, tp_corpus, en_corpus, to_ids, CTX, MLP, S1_STEPS, S3_STEPS
from ewc import fisher

SEEDS = list(range(int(sys.argv[1]) if len(sys.argv) > 1 else 6))
BLOCK = 8
CONCEPTS = ["telo", "moku", "tomo", "waso", "kili", "pan", "kala", "soweli", "jan"]
ENGLISH = {"telo": ["water", "liquid"], "moku": ["eats", "munches", "drinks"], "tomo": ["house", "home"],
           "waso": ["bird"], "kili": ["fruit"], "pan": ["bread"], "kala": ["fish"], "soweli": ["dog", "cat"],
           "jan": ["person", "child"]}
FREE = list(range(len(CONCEPTS) * BLOCK, MLP))
BLOCKS = {c: list(range(i * BLOCK, (i + 1) * BLOCK)) for i, c in enumerate(CONCEPTS)}


class RoutedModel(Model):
    def forward(self, idx, route=None, knock=None):
        """route: (B, T, MLP) 0/1 mask of where gradient may flow. knock: neuron ids forced to 0."""
        T = idx.shape[1]
        h = self.emb(idx) + self.pos[:T]
        a = self.ln1(h)
        h = h + self.attn(a, a, a, attn_mask=self.mask[:T, :T], need_weights=False)[0]
        z = self.mlp[1](self.mlp[0](self.ln2(h)))
        if route is not None:
            z = z * route + (z * (1 - route)).detach()  # same values, gradient only through allowed neurons
        if knock is not None:
            z = z.clone()
            z[..., knock] = 0
        h = h + self.mlp[2](z)
        return self.ln3(h) @ self.emb.weight.T


_ROUTE_TABLE = {}


def route_mask(x, itos):
    """Next word is a concept -> its block only. Any other next word -> the free neurons only."""
    V = len(itos)
    if V not in _ROUTE_TABLE:
        table = torch.zeros(V, MLP)
        for i, w in itos.items():
            table[i, BLOCKS[w] if w in BLOCKS else FREE] = 1
        _ROUTE_TABLE[V] = table
    return _ROUTE_TABLE[V][x]


def train(model, sents_fn, steps, stoi, itos, r, routed=False, old=None, imp=None, strength=0):
    opt = torch.optim.AdamW(model.parameters(), lr=3e-3, weight_decay=0.0 if strength else 0.01)
    for step in range(steps):
        if step % 50 == 0:
            sents = sents_fn(); r.shuffle(sents); toks = to_ids(sents, stoi)
        starts = [r.randrange(0, len(toks) - CTX - 1) for _ in range(32)]
        x = torch.stack([toks[i:i + CTX] for i in starts])
        y = torch.stack([toks[i + 1:i + CTX + 1] for i in starts])
        # Route by the word being predicted: learning to predict "telo" lands in telo's block.
        out = model(x, route=route_mask(y, itos) if routed else None)
        loss = F.cross_entropy(out.reshape(-1, out.shape[-1]), y.reshape(-1))
        if strength:
            loss = loss + strength * 1000 * sum((imp[n] * (p - old[n]) ** 2).sum() for n, p in model.named_parameters())
        opt.zero_grad(); loss.backward(); opt.step()


@torch.no_grad()
def concept_losses(model, toks, stoi, targets, knock=None):
    """Average loss when the next word is one of each concept's words."""
    n = (len(toks) - 1) // CTX
    x = toks[: n * CTX].view(n, CTX)
    y = toks[1: n * CTX + 1].view(n, CTX)
    loss = F.cross_entropy(model(x, knock=knock).reshape(-1, model.emb.num_embeddings), y.reshape(-1), reduction="none")
    y = y.reshape(-1)
    return {c: loss[torch.isin(y, torch.tensor([stoi[w] for w in ws]))].mean().item() for c, ws in targets.items()}


def knockout_matrix(model, toks, stoi, targets, rng):
    base = concept_losses(model, toks, stoi, targets)
    m = {}
    for c in CONCEPTS:
        hit = concept_losses(model, toks, stoi, targets, knock=BLOCKS[c])
        m[c] = {t: hit[t] - base[t] for t in targets}
    rand = rng.sample(range(MLP), BLOCK)
    hit = concept_losses(model, toks, stoi, targets, knock=rand)
    m["random"] = {t: hit[t] - base[t] for t in targets}
    return base, m


def main():
    t0 = time.time()
    vocab = sorted({w for s in tp_corpus(3000, 0) + en_corpus(3000, 0) for w in s.split()} | {"means"})
    stoi = {w: i for i, w in enumerate(vocab)}
    itos = {i: w for w, i in stoi.items()}
    en_test = to_ids(en_corpus(800, 78), stoi)
    tp_test = to_ids(tp_corpus(800, 77), stoi)
    out = []
    for seed in SEEDS:
        rng = random.Random(seed)
        for cond in ["routed", "routed+ewc", "unrouted", "english"]:
            torch.manual_seed(seed)
            r = random.Random(seed)
            model = RoutedModel(len(vocab))
            log = {"seed": seed, "cond": cond}
            old = imp = None
            if cond != "english":
                train(model, lambda: tp_corpus(4000, 1000 + seed), S1_STEPS, stoi, itos, r, routed=cond.startswith("routed"))
                # Sanity check: does knocking a block hurt its own toki pona word after stage 1?
                _, log["tp_after_stage1"] = knockout_matrix(model, tp_test, stoi, {c: [c] for c in CONCEPTS}, rng)
                if cond == "routed+ewc":
                    old = {n: p.detach().clone() for n, p in model.named_parameters()}
                    imp = fisher(model, tp_corpus(1000, 4000 + seed), stoi, random.Random(seed))
            train(model, lambda: en_corpus(2000, 2000 + seed), S3_STEPS, stoi, itos, r,
                  old=old, imp=imp, strength=10 if cond == "routed+ewc" else 0)
            log["en_base"], log["en_knockout"] = knockout_matrix(model, en_test, stoi, ENGLISH, rng)
            out.append(log)
        print(f"seed {seed} done ({time.time() - t0:.0f}s)", flush=True)
    json.dump(out, open("knockout_results.json", "w"), indent=1)
    print(f"saved knockout_results.json ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
