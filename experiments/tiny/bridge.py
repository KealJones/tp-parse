"""Stronger bridges between toki pona and English, then the knockout test.

Same setup as knockout.py --dict (toki pona concepts planted in chosen neuron
blocks with gradient routing, light EWC protecting them), but the bridge stage
between toki pona and the English sweep is varied:

  long-dict       the text dictionary ("water means telo .") for 3x as long
  mixed           Spanglish-style sentences: English with concept words swapped
                  for toki pona half the time ("the soweli eats the pan .")
  dict+mixed      both
  mixed-unrouted  mixed bridge, but nothing planted (control)
  english         English only (control)

bird (waso) and fruit (kili) are never part of any bridge, as a comparison.

Run: python3 bridge.py [seeds]
"""
import json, random, sys, time
import torch
from stages import tp_corpus, en_corpus, to_ids, dict_lines, S1_STEPS, S3_STEPS
from knockout import RoutedModel, train, knockout_matrix, CONCEPTS, ENGLISH
from ewc import fisher

SEEDS = list(range(int(sys.argv[1]) if len(sys.argv) > 1 else 6))
BRIDGE_STEPS = 1200
STRENGTH = 10
CONDITIONS = ["long-dict", "mixed", "dict+mixed", "mixed-unrouted", "english"]
UNBRIDGED = {"waso", "kili"}

# English word -> toki pona, for the mixed sentences (bird and fruit deliberately missing).
SWAP = {"water": "telo", "liquid": "telo", "house": "tomo", "home": "tomo", "bread": "pan", "fish": "kala",
        "dog": "soweli", "cat": "soweli lili", "person": "jan", "child": "jan lili", "eats": "moku",
        "munches": "moku", "drinks": "moku", "big": "suli", "large": "suli", "small": "lili",
        "good": "pona", "nice": "pona", "bad": "ike", "sweet": "suwi", "cake": "pan suwi",
        "tree": "kasi suli", "lake": "telo suli"}


def mixed_corpus(n, seed):
    r = random.Random(seed)
    out = []
    for s in en_corpus(n, seed):
        out.append(" ".join(SWAP[w] if w in SWAP and r.random() < 0.5 else w for w in s.split()))
    return out


def main():
    t0 = time.time()
    vocab = sorted({w for s in tp_corpus(3000, 0) + en_corpus(3000, 0) + dict_lines() + mixed_corpus(3000, 0)
                    for w in s.split()})
    stoi = {w: i for i, w in enumerate(vocab)}
    itos = {i: w for w, i in stoi.items()}
    en_test = to_ids(en_corpus(800, 78), stoi)
    out = []
    for seed in SEEDS:
        rng = random.Random(seed)
        for cond in CONDITIONS:
            torch.manual_seed(seed)
            r = random.Random(seed)
            model = RoutedModel(len(vocab))
            old = imp = None
            if cond != "english":
                routed = cond != "mixed-unrouted"
                train(model, lambda: tp_corpus(4000, 1000 + seed), S1_STEPS, stoi, itos, r, routed=routed)
                old = {n: p.detach().clone() for n, p in model.named_parameters()}
                imp = fisher(model, tp_corpus(1000, 4000 + seed), stoi, random.Random(seed))
                if cond == "long-dict":
                    bridge = lambda: dict_lines() * 20
                elif cond == "dict+mixed":
                    bridge = lambda: dict_lines() * 10 + mixed_corpus(2000, 5000 + seed)
                else:
                    bridge = lambda: mixed_corpus(2000, 5000 + seed)
                train(model, bridge, BRIDGE_STEPS, stoi, itos, r, routed=routed, old=old, imp=imp, strength=STRENGTH)
            train(model, lambda: en_corpus(2000, 2000 + seed), S3_STEPS, stoi, itos, r,
                  old=old, imp=imp, strength=STRENGTH if cond != "english" else 0)
            base, m = knockout_matrix(model, en_test, stoi, ENGLISH, rng)
            out.append({"seed": seed, "cond": cond, "en_base": base, "en_knockout": m})
        print(f"seed {seed} done ({time.time() - t0:.0f}s)", flush=True)
    json.dump(out, open("bridge_results.json", "w"), indent=1)
    print(f"saved bridge_results.json ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
