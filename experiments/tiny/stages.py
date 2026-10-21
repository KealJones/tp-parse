"""Three-stage experiment: toki pona -> dictionary -> a big sweep of English.

One shared vocabulary for both languages (like a real model), one tiny
transformer (word vectors -> attention -> MLP -> next word). Only next-word
prediction; no labels.

  Stage 1  toki pona sentences about a small world
  Stage 2  a dictionary written as text: "water means telo ."
           Some words are deliberately left out of it.
  Stage 3  lots of plain English about the same world. English is messier than
           toki pona: it has synonyms toki pona doesn't (liquid / water -> telo,
           home / house -> tomo, large / big -> suli, nice / good -> pona,
           munches / eats -> moku). The synonyms never appear in the dictionary.

The question: do English words that were never in the dictionary end up in the
"spot" toki pona made for them (liquid next to telo), so that the model can
answer "liquid means ___" with "telo"? And does toki pona survive stage 3?

Conditions:
  full         stage 1 -> 2 -> 3
  no-tp        stage 2 -> 3 (dictionary but no toki pona sentences first)
  no-dict      stage 1 -> 3
  english      stage 3 only
  full-frozen  stage 1 -> 2 -> 3, attention + MLP locked during stage 3
  full-replay  stage 1 -> 2 -> 3, with 10% toki pona sentences mixed into stage 3

Run: python3 stages.py [seeds]
"""
import json, random, sys, time
import torch
import torch.nn as nn
import torch.nn.functional as F
from world import frame, toki_pona, NOUNS, ADJS

torch.set_num_threads(2)
D, HEADS, MLP, CTX = 48, 4, 96, 16
S1_STEPS, S2_STEPS, S3_STEPS = 1500, 400, 2000
SEEDS = list(range(int(sys.argv[1]) if len(sys.argv) > 1 else 6))
CONDITIONS = ["full", "no-tp", "no-dict", "english", "full-frozen", "full-replay"]

# English with synonyms toki pona doesn't have.
SYN = {"water": ["water", "liquid"], "house": ["house", "home"]}
ADJ_SYN = {"big": ["big", "large"], "good": ["good", "nice"]}
EAT_SYN = ["eats", "munches"]


def english(kind, slots, r):
    s, o = slots
    n = lambda c: r.choice(SYN.get(c, [NOUNS[c][1]]))
    S = n(s)
    if kind == "eat":
        return f"the {S} {r.choice(EAT_SYN)} the {n(o)} ."
    if kind == "drink":
        return f"the {S} drinks the {n('water')} ."
    if kind == "go":
        return f"the {S} goes to the {n(o)} ."
    if kind == "sleep":
        return f"the {S} sleeps in the {n(o)} ."
    if kind == "prop":
        return f"the {S} is {r.choice(ADJ_SYN.get(o, [ADJS[o][1]]))} ."
    if kind == "see":
        return f"the {S} sees the {n(o)} ."
    return f"the {S} loves the {n(o)} ."


def tp_corpus(n, seed):
    r = random.Random(seed)
    return [toki_pona(*frame(r)) for _ in range(n)]


def en_corpus(n, seed):
    r = random.Random(seed)
    return [english(*frame(r), r) for _ in range(n)]


# Dictionary stage. English -> toki pona.
DICT = [("person", "jan"), ("dog", "soweli"), ("fish", "kala"), ("bread", "pan"), ("water", "telo"),
        ("house", "tomo"), ("big", "suli"), ("small", "lili"), ("good", "pona"), ("bad", "ike"),
        ("sweet", "suwi"), ("eats", "moku"), ("goes", "tawa"), ("sees", "lukin"), ("loves", "olin"),
        ("cat", "soweli lili"), ("child", "jan lili")]
# Never in the dictionary: plain words, synonyms, and compounds.
HELD_OUT = [("bird", "waso"), ("fruit", "kili"), ("sleeps", "lape"), ("drinks", "moku")]
SYNONYMS = [("liquid", "telo"), ("home", "tomo"), ("large", "suli"), ("nice", "pona"), ("munches", "moku")]
HELD_COMPOUNDS = [("cake", ("pan", "suwi")), ("tree", ("kasi", "suli")), ("lake", ("telo", "suli"))]


def dict_lines():
    return [f"{a} means {b} ." for a, b in DICT]


class Model(nn.Module):
    def __init__(self, V):
        super().__init__()
        self.emb = nn.Embedding(V, D)
        nn.init.normal_(self.emb.weight, std=0.1)
        self.pos = nn.Parameter(torch.randn(CTX, D) * 0.02)
        self.ln1, self.ln2, self.ln3 = nn.LayerNorm(D), nn.LayerNorm(D), nn.LayerNorm(D)
        self.attn = nn.MultiheadAttention(D, HEADS, batch_first=True)
        self.mlp = nn.Sequential(nn.Linear(D, MLP), nn.GELU(), nn.Linear(MLP, D))
        self.register_buffer("mask", torch.triu(torch.ones(CTX, CTX, dtype=torch.bool), 1))

    def middle(self):
        return [self.pos, *self.ln1.parameters(), *self.ln2.parameters(), *self.ln3.parameters(),
                *self.attn.parameters(), *self.mlp.parameters()]

    def forward(self, idx):
        T = idx.shape[1]
        h = self.emb(idx) + self.pos[:T]
        a = self.ln1(h)
        h = h + self.attn(a, a, a, attn_mask=self.mask[:T, :T], need_weights=False)[0]
        h = h + self.mlp(self.ln2(h))
        return self.ln3(h) @ self.emb.weight.T


def to_ids(sents, stoi):
    return torch.tensor([stoi[w] for s in sents for w in s.split()])


def train(model, sents_fn, steps, stoi, r, frozen=False):
    for p in model.middle():
        p.requires_grad_(not frozen)
    params = [p for p in model.parameters() if p.requires_grad]
    opt = torch.optim.AdamW(params, lr=3e-3, weight_decay=0.01)
    for step in range(steps):
        if step % 50 == 0:
            sents = sents_fn()
            r.shuffle(sents)
            toks = to_ids(sents, stoi)
        starts = [r.randrange(0, len(toks) - CTX - 1) for _ in range(32)]
        x = torch.stack([toks[i:i + CTX] for i in starts])
        y = torch.stack([toks[i + 1:i + CTX + 1] for i in starts])
        loss = F.cross_entropy(model(x).reshape(-1, model.emb.num_embeddings), y.reshape(-1))
        opt.zero_grad(); loss.backward(); opt.step()
    for p in model.middle():
        p.requires_grad_(True)


@torch.no_grad()
def probes(model, stoi, itos, tp_ids, en_ids, tp_test, en_test):
    out = {}
    # Test loss and language leakage.
    for name, toks, other in [("tp", tp_test, en_ids), ("en", en_test, tp_ids)]:
        n = (len(toks) - 1) // CTX
        x = toks[: n * CTX].view(n, CTX)
        y = toks[1: n * CTX + 1].view(n, CTX)
        lg = model(x)
        out[f"{name}_loss"] = F.cross_entropy(lg.reshape(-1, lg.shape[-1]), y.reshape(-1)).item()
        probs = lg.softmax(-1)
        out[f"{name}_leak"] = probs[..., other].sum(-1).mean().item()  # mass on the other language's words

    tp_content = [i for i in tp_ids if itos[i] not in {"li", "e", "lon", "."}]

    def means(word):
        """Top toki pona word the model predicts after '<word> means'."""
        x = torch.tensor([[stoi[word], stoi["means"]]])
        lg = model(x)[0, -1]
        return itos[max(tp_content, key=lambda i: lg[i].item())]

    def nearest(word):
        e = F.normalize(model.emb.weight, dim=-1)
        sims = e[tp_content] @ e[stoi[word]]
        return [itos[tp_content[i]] for i in sims.topk(2).indices.tolist()]

    for group, pairs in [("dict", [(a, b) for a, b in DICT if " " not in b]), ("held", HELD_OUT), ("syn", SYNONYMS)]:
        out[f"means_{group}"] = sum(means(a) == b for a, b in pairs) / len(pairs)
        out[f"near_{group}"] = sum(nearest(a)[0] == b for a, b in pairs) / len(pairs)
    out["compound_one_part"] = sum(bool(set(nearest(a)) & set(parts)) for a, parts in HELD_COMPOUNDS) / len(HELD_COMPOUNDS)
    out["means_examples"] = {a: means(a) for a, _ in HELD_OUT + SYNONYMS}
    return out


def main():
    t0 = time.time()
    vocab = sorted({w for s in tp_corpus(3000, 0) + en_corpus(3000, 0) + dict_lines() for w in s.split()})
    stoi = {w: i for i, w in enumerate(vocab)}
    itos = {i: w for w, i in stoi.items()}
    tp_words = {w for s in tp_corpus(3000, 0) for w in s.split()} - {"."}
    en_words = {w for s in en_corpus(3000, 0) for w in s.split()} - {"."}
    tp_ids = sorted(stoi[w] for w in tp_words)
    en_ids = sorted(stoi[w] for w in en_words)
    tp_test = to_ids(tp_corpus(500, 77), stoi)
    en_test = to_ids(en_corpus(500, 78), stoi)

    results = []
    for seed in SEEDS:
        for cond in CONDITIONS:
            torch.manual_seed(seed)
            r = random.Random(seed)
            model = Model(len(vocab))
            log = {"seed": seed, "cond": cond}
            if cond in ("full", "no-dict", "full-frozen", "full-replay"):
                train(model, lambda: tp_corpus(4000, 1000 + seed), S1_STEPS, stoi, r)
                log["after_1"] = probes(model, stoi, itos, tp_ids, en_ids, tp_test, en_test)
            if cond in ("full", "no-tp", "full-frozen", "full-replay"):
                train(model, lambda: dict_lines() * 20, S2_STEPS, stoi, r)
                log["after_2"] = probes(model, stoi, itos, tp_ids, en_ids, tp_test, en_test)
            if cond == "full-replay":
                fn = lambda: en_corpus(2000, 2000 + seed) + tp_corpus(200, 3000 + seed)
            else:
                fn = lambda: en_corpus(2000, 2000 + seed)
            train(model, fn, S3_STEPS, stoi, r, frozen=(cond == "full-frozen"))
            log["after_3"] = probes(model, stoi, itos, tp_ids, en_ids, tp_test, en_test)
            results.append(log)
        print(f"seed {seed} done ({time.time() - t0:.0f}s)", flush=True)
    json.dump(results, open("stages_results.json", "w"), indent=1)
    print(f"saved stages_results.json ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
