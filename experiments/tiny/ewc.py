"""Elastic weight consolidation: do stiffened toki pona paths survive, and does English route through them?

After stage 1 (toki pona), measure how important each weight was for toki pona
(the "Fisher information": average squared gradient on toki pona text). Then,
during the dictionary and English stages, every weight is pulled back toward its
stage-1 value in proportion to that importance:

    loss = next-word loss + strength * sum( importance * (weight - old_weight)^2 )

Important weights become stiff; unimportant ones stay free for English.

Compared at several strengths (0 = no protection) on:
  - English test loss (did it still learn English?)
  - toki pona test loss (did it remember?)
  - hub reuse: does each English word fire the MLP neurons its toki pona word
    fired after stage 1? (same measure as neurons.py)

Run: python3 ewc.py [seeds]
"""
import json, random, sys, time
import torch
import torch.nn.functional as F
from stages import Model, train, tp_corpus, en_corpus, dict_lines, to_ids, CTX, S1_STEPS, S2_STEPS, S3_STEPS
from neurons import patterns, compare, CONCEPTS
import copy

SEEDS = list(range(int(sys.argv[1]) if len(sys.argv) > 1 else 6))
STRENGTHS = [0, 10, 100, 1000, 10000]


def fisher(model, sents, stoi, r, batches=60):
    """Average squared gradient of the next-word loss, per weight."""
    imp = {n: torch.zeros_like(p) for n, p in model.named_parameters()}
    toks = to_ids(sents, stoi)
    for _ in range(batches):
        starts = [r.randrange(0, len(toks) - CTX - 1) for _ in range(32)]
        x = torch.stack([toks[i:i + CTX] for i in starts])
        y = torch.stack([toks[i + 1:i + CTX + 1] for i in starts])
        model.zero_grad()
        F.cross_entropy(model(x).reshape(-1, model.emb.num_embeddings), y.reshape(-1)).backward()
        for n, p in model.named_parameters():
            imp[n] += p.grad.detach() ** 2 / batches
    total = sum(v.sum() for v in imp.values())
    return {n: v / total for n, v in imp.items()}  # normalised so strengths are comparable


def train_ewc(model, sents_fn, steps, stoi, r, old, imp, strength):
    opt = torch.optim.AdamW(model.parameters(), lr=3e-3, weight_decay=0.0)
    for step in range(steps):
        if step % 50 == 0:
            sents = sents_fn()
            r.shuffle(sents)
            toks = to_ids(sents, stoi)
        starts = [r.randrange(0, len(toks) - CTX - 1) for _ in range(32)]
        x = torch.stack([toks[i:i + CTX] for i in starts])
        y = torch.stack([toks[i + 1:i + CTX + 1] for i in starts])
        loss = F.cross_entropy(model(x).reshape(-1, model.emb.num_embeddings), y.reshape(-1))
        if strength:
            pen = sum((imp[n] * (p - old[n]) ** 2).sum() for n, p in model.named_parameters())
            loss = loss + strength * pen * 1000  # imp is normalised to sum to 1, so scale up
        opt.zero_grad(); loss.backward(); opt.step()


@torch.no_grad()
def test_loss(model, toks):
    n = (len(toks) - 1) // CTX
    x = toks[: n * CTX].view(n, CTX)
    y = toks[1: n * CTX + 1].view(n, CTX)
    return F.cross_entropy(model(x).reshape(-1, model.emb.num_embeddings), y.reshape(-1)).item()


def main():
    t0 = time.time()
    vocab = sorted({w for s in tp_corpus(3000, 0) + en_corpus(3000, 0) + dict_lines() for w in s.split()})
    stoi = {w: i for i, w in enumerate(vocab)}
    tp_test, en_test = to_ids(tp_corpus(500, 77), stoi), to_ids(en_corpus(500, 78), stoi)
    tp_probe, en_probe = tp_corpus(1500, 55), en_corpus(1500, 56)
    en_words = sorted({e for es in CONCEPTS.values() for e in es})
    out = []
    for seed in SEEDS:
        torch.manual_seed(seed)
        r = random.Random(seed)
        base = Model(len(vocab))
        train(base, lambda: tp_corpus(4000, 1000 + seed), S1_STEPS, stoi, r)
        old = {n: p.detach().clone() for n, p in base.named_parameters()}
        imp = fisher(base, tp_corpus(1000, 4000 + seed), stoi, random.Random(seed))
        before_tp = patterns(base, tp_probe, stoi, list(CONCEPTS), "mlp")
        for strength in STRENGTHS:
            model = copy.deepcopy(base)
            rr = random.Random(seed + 1)
            train_ewc(model, lambda: dict_lines() * 20, S2_STEPS, stoi, rr, old, imp, strength)
            train_ewc(model, lambda: en_corpus(2000, 2000 + seed), S3_STEPS, stoi, rr, old, imp, strength)
            hub = compare(before_tp, patterns(model, en_probe, stoi, en_words, "mlp"))
            out.append({"seed": seed, "strength": strength, "en_loss": test_loss(model, en_test),
                        "tp_loss": test_loss(model, tp_test), "hub_accuracy": hub["accuracy"],
                        "hub_corr_same": hub["corr_same"], "hub_corr_other": hub["corr_other"], "rows": hub["rows"]})
        print(f"seed {seed} done ({time.time() - t0:.0f}s)", flush=True)
    json.dump(out, open("ewc_results.json", "w"), indent=1)
    print(f"saved ewc_results.json ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
