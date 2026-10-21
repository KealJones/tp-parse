# tiny_transfer.py: does learning toki pona make learning English faster?
import math, random

TOKENS = ["telo", "moku", "water", "food"]
MEANINGS = ["WET", "EAT"]
DIM, LR = 2, 0.5

def new_model(seed):
    r = random.Random(seed)
    return {
        "emb": {t: [r.uniform(-0.1, 0.1) for _ in range(DIM)] for t in TOKENS},
        "W": [[r.uniform(-0.1, 0.1) for _ in range(DIM)] for _ in MEANINGS],
        "b": [0.0] * len(MEANINGS),
    }

def forward(m, tok):
    e = m["emb"][tok]
    logits = [sum(w * x for w, x in zip(m["W"][k], e)) + m["b"][k] for k in range(len(MEANINGS))]
    mx = max(logits)
    ex = [math.exp(l - mx) for l in logits]
    s = sum(ex)
    return e, [x / s for x in ex]

def step(m, tok, target, train_head=True):
    e, p = forward(m, tok)
    g = [p[k] - (1 if k == target else 0) for k in range(len(MEANINGS))]
    ge = [sum(g[k] * m["W"][k][d] for k in range(len(MEANINGS))) for d in range(DIM)]
    if train_head:
        for k in range(len(MEANINGS)):
            for d in range(DIM):
                m["W"][k][d] -= LR * g[k] * e[d]
            m["b"][k] -= LR * g[k]
    for d in range(DIM):
        e[d] -= LR * ge[d]
    return -math.log(p[target])

def train(m, pairs, train_head=True, max_steps=5000):
    for s in range(1, max_steps + 1):
        losses = [step(m, t, MEANINGS.index(y), train_head) for t, y in pairs]
        if max(losses) < 0.1:
            return s
    return max_steps

def dist(a, b):
    return math.dist(a, b)

tp = [("telo", "WET"), ("moku", "EAT")]
en = [("water", "WET"), ("food", "EAT")]
res = {"fresh": [], "after_tp": [], "after_tp_frozen_head": []}

for seed in range(20):
    a = new_model(seed); res["fresh"].append(train(a, en))
    b = new_model(seed); train(b, tp); res["after_tp"].append(train(b, en))
    c = new_model(seed); train(c, tp); res["after_tp_frozen_head"].append(train(c, en, train_head=False))

for k, v in res.items():
    print(f"{k:22s} avg steps to learn English: {sum(v)/len(v):.1f}")

m = new_model(0); train(m, tp); train(m, en)
print("\nEmbeddings after both (seed 0):")
for t in TOKENS:
    print(f"  {t:6s} {[round(x, 2) for x in m['emb'][t]]}")
print(f"telo-water distance: {dist(m['emb']['telo'], m['emb']['water']):.2f}")
print(f"telo-food  distance: {dist(m['emb']['telo'], m['emb']['food']):.2f}")
