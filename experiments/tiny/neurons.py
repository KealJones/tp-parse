"""Does English go through the same neurons toki pona set up?

For each concept (water / telo, house / tomo, ...), record which of the 96 MLP
neurons fire when the model reads the toki pona word, right after stage 1
(toki pona only). Then, after the English sweep, record which neurons fire when
it reads the English word(s) for that concept. If English reuses toki pona's
"spot", the English word's firing pattern should match its own toki pona
word's old pattern better than any other concept's.

Measured for:
  full         toki pona -> dictionary -> English
  no-dict      toki pona -> English
  full-replay  toki pona -> dictionary -> English with 10% toki pona mixed in
plus a control: the same comparison against a *different* seed's stage-1 model,
where neuron numbers don't correspond, so any match there is chance.

Run: python3 neurons.py [seeds]
"""
import copy, json, random, sys, time
import torch
from stages import Model, train, tp_corpus, en_corpus, dict_lines, CTX, S1_STEPS, S2_STEPS, S3_STEPS

SEEDS = list(range(int(sys.argv[1]) if len(sys.argv) > 1 else 6))
CONCEPTS = {  # toki pona word: English words for the same thing
    "telo": ["water", "liquid"], "tomo": ["house", "home"], "suli": ["big", "large"], "pona": ["good", "nice"],
    "moku": ["eats", "munches", "drinks"], "waso": ["bird"], "kili": ["fruit"], "lape": ["sleeps"],
    "pan": ["bread"], "kala": ["fish"], "jan": ["person"], "soweli": ["dog"], "ike": ["bad"], "lili": ["small"],
    "suwi": ["sweet"], "tawa": ["goes"], "lukin": ["sees"], "olin": ["loves"],
}
SYNONYMS = {"liquid", "home", "large", "nice", "munches"}


@torch.no_grad()
def patterns(model, sents, stoi, words, where="mlp"):
    """Average activation at each occurrence of each word. where='mlp': the 96 MLP
    neurons; where='hidden': the 48-number residual stream after the layer."""
    acts = {}
    def hook(_, __, out):
        acts["x"] = out
    layer = model.mlp[1] if where == "mlp" else model.ln3
    h = layer.register_forward_hook(hook)
    sums = {w: 0 for w in words}
    counts = {w: 0 for w in words}
    toks = torch.tensor([stoi[w] for s in sents for w in s.split()])
    n = len(toks) // CTX
    x = toks[: n * CTX].view(n, CTX)
    model(x)
    a = acts["x"]  # (n, CTX, units)
    for w in words:
        mask = x == stoi[w]
        if mask.any():
            sums[w] = a[mask].mean(0)
            counts[w] = int(mask.sum())
    h.remove()
    return {w: sums[w] for w in words if counts[w] > 0}


def center(pats):
    mean = torch.stack(list(pats.values())).mean(0)
    return {w: v - mean for w, v in pats.items()}


def corr(a, b):
    a, b = a - a.mean(), b - b.mean()
    return (a @ b / (a.norm() * b.norm() + 1e-9)).item()


def compare(tp_pats, en_pats):
    """For each English word: is its pattern closest to its own concept's toki pona pattern?"""
    tp_c, en_c = center(tp_pats), center(en_pats)
    hits, same, diff, rows = 0, [], [], []
    for tpw, ens in CONCEPTS.items():
        for e in ens:
            if e not in en_c or tpw not in tp_c:
                continue
            scores = {t: corr(en_c[e], v) for t, v in tp_c.items()}
            best = max(scores, key=scores.get)
            hits += best == tpw
            same.append(scores[tpw])
            diff += [s for t, s in scores.items() if t != tpw]
            rows.append({"en": e, "tp": tpw, "best": best, "corr_own": round(scores[tpw], 3), "synonym": e in SYNONYMS})
    n = len(rows)
    return {"accuracy": hits / n, "corr_same": sum(same) / len(same), "corr_other": sum(diff) / len(diff), "rows": rows}


def main():
    t0 = time.time()
    vocab = sorted({w for s in tp_corpus(3000, 0) + en_corpus(3000, 0) + dict_lines() for w in s.split()})
    stoi = {w: i for i, w in enumerate(vocab)}
    tp_probe = tp_corpus(1500, 55)
    en_probe = en_corpus(1500, 56)
    en_words = sorted({e for es in CONCEPTS.values() for e in es})

    stage1 = {}  # seed -> stage-1 snapshot
    out = []
    for seed in SEEDS:
        for cond in ["full", "no-dict", "full-replay"]:
            torch.manual_seed(seed)
            r = random.Random(seed)
            model = Model(len(vocab))
            train(model, lambda: tp_corpus(4000, 1000 + seed), S1_STEPS, stoi, r)
            snap = copy.deepcopy(model)
            stage1.setdefault(seed, snap)
            if cond != "no-dict":
                train(model, lambda: dict_lines() * 20, S2_STEPS, stoi, r)
            fn = (lambda: en_corpus(2000, 2000 + seed) + tp_corpus(200, 3000 + seed)) if cond == "full-replay" \
                else (lambda: en_corpus(2000, 2000 + seed))
            train(model, fn, S3_STEPS, stoi, r)
            for where in ["mlp", "hidden"]:
                before_tp = patterns(snap, tp_probe, stoi, list(CONCEPTS), where)
                after_en = patterns(model, en_probe, stoi, en_words, where)
                after_tp = patterns(model, tp_probe, stoi, list(CONCEPTS), where)
                out.append({"seed": seed, "cond": cond, "where": where,
                            "old_tp_vs_new_en": compare(before_tp, after_en),
                            "new_tp_vs_new_en": compare(after_tp, after_en)})
        print(f"seed {seed} done ({time.time() - t0:.0f}s)", flush=True)

    # Control: compare each model's English against a different seed's stage-1 neurons.
    for seed in SEEDS:
        other = SEEDS[(SEEDS.index(seed) + 1) % len(SEEDS)]
        torch.manual_seed(seed)
        r = random.Random(seed)
        model = Model(len(vocab))
        train(model, lambda: tp_corpus(4000, 1000 + seed), S1_STEPS, stoi, r)
        train(model, lambda: dict_lines() * 20, S2_STEPS, stoi, r)
        train(model, lambda: en_corpus(2000, 2000 + seed), S3_STEPS, stoi, r)
        for where in ["mlp", "hidden"]:
            out.append({"seed": seed, "cond": "control-other-seed", "where": where,
                        "old_tp_vs_new_en": compare(patterns(stage1[other], tp_probe, stoi, list(CONCEPTS), where),
                                                    patterns(model, en_probe, stoi, en_words, where))})
    json.dump(out, open("neurons_results.json", "w"), indent=1)
    print(f"saved neurons_results.json ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
