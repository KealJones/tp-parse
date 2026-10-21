"""Role-matched hub test: verbs vs verbs, nouns vs nouns, adjectives vs adjectives.

The plain hub test compared each English word with every toki pona word, so a
verb could "match" its toki pona verb just because both are verbs sitting in
the same sentence slot. Here each English word is only compared with toki pona
words of the same kind, and patterns are centred within that group, so what's
left is meaning, not part of speech.

Runs stage 1 (toki pona), then dictionary + English with EWC strength 0 (no
protection) and 10 (the best from ewc.py). Also a control against a different
seed's stage-1 neurons.

Run: python3 roles.py [seeds]
"""
import copy, json, random, sys, time
import torch
from stages import Model, train, tp_corpus, en_corpus, dict_lines, S1_STEPS, S2_STEPS, S3_STEPS
from neurons import patterns, corr
from ewc import fisher, train_ewc

SEEDS = list(range(int(sys.argv[1]) if len(sys.argv) > 1 else 6))
GROUPS = {
    "verbs": {"moku": ["eats", "drinks", "munches"], "lukin": ["sees"], "olin": ["loves"], "tawa": ["goes"], "lape": ["sleeps"]},
    "nouns": {"telo": ["water", "liquid"], "tomo": ["house", "home"], "waso": ["bird"], "kili": ["fruit"],
              "pan": ["bread"], "kala": ["fish"], "jan": ["person"], "soweli": ["dog"]},
    "adjectives": {"suli": ["big", "large"], "lili": ["small"], "pona": ["good", "nice"], "ike": ["bad"], "suwi": ["sweet"]},
}
SYNONYMS = {"liquid", "home", "large", "nice", "munches"}
SYN_PAIRS = [("big", "large", "adjectives"), ("good", "nice", "adjectives"), ("house", "home", "nouns"),
             ("water", "liquid", "nouns"), ("eats", "munches", "verbs")]


def synonym_scores(en_pats):
    """Inside English only: how much more alike are synonyms than other same-kind words?"""
    out = []
    for a, b, gname in SYN_PAIRS:
        words = [e for es in GROUPS[gname].values() for e in es if e in en_pats]
        mean = torch.stack([en_pats[w] for w in words]).mean(0)
        c = lambda x, y: corr(en_pats[x] - mean, en_pats[y] - mean)
        others = [c(a, w) for w in words if w not in (a, b)] + [c(b, w) for w in words if w not in (a, b)]
        out.append({"pair": f"{a}/{b}", "syn_corr": round(c(a, b), 3), "other_corr": round(sum(others) / len(others), 3)})
    return out


def group_compare(tp_pats, en_pats, group):
    tps = [t for t in group if t in tp_pats]
    tp_mean = torch.stack([tp_pats[t] for t in tps]).mean(0)
    ens = [e for t in tps for e in group[t] if e in en_pats]
    en_mean = torch.stack([en_pats[e] for e in ens]).mean(0)
    rows = []
    for t in tps:
        for e in group[t]:
            if e not in en_pats:
                continue
            scores = {u: corr(en_pats[e] - en_mean, tp_pats[u] - tp_mean) for u in tps}
            rows.append({"en": e, "tp": t, "best": max(scores, key=scores.get), "scores": {k: round(v, 3) for k, v in scores.items()},
                         "synonym": e in SYNONYMS})
    return rows


def main():
    t0 = time.time()
    vocab = sorted({w for s in tp_corpus(3000, 0) + en_corpus(3000, 0) + dict_lines() for w in s.split()})
    stoi = {w: i for i, w in enumerate(vocab)}
    tp_probe, en_probe = tp_corpus(1500, 55), en_corpus(1500, 56)
    tp_words = [t for g in GROUPS.values() for t in g]
    en_words = [e for g in GROUPS.values() for es in g.values() for e in es]
    stage1_pats = {}
    finals = {}
    out = []
    for seed in SEEDS:
        torch.manual_seed(seed)
        r = random.Random(seed)
        base = Model(len(vocab))
        train(base, lambda: tp_corpus(4000, 1000 + seed), S1_STEPS, stoi, r)
        old = {n: p.detach().clone() for n, p in base.named_parameters()}
        imp = fisher(base, tp_corpus(1000, 4000 + seed), stoi, random.Random(seed))
        stage1_pats[seed] = {w: patterns(base, tp_probe, stoi, tp_words, w) for w in ["mlp", "hidden"]}
        # English only: a fresh model that never sees toki pona or the dictionary.
        torch.manual_seed(seed)
        fresh = Model(len(vocab))
        train(fresh, lambda: en_corpus(2000, 2000 + seed), S3_STEPS, stoi, random.Random(seed + 1))
        for where in ["mlp", "hidden"]:
            out.append({"seed": seed, "strength": "english-only", "where": where, "group": "synonyms",
                        "syn": synonym_scores(patterns(fresh, en_probe, stoi, en_words, where))})
        for strength in [0, 10]:
            model = copy.deepcopy(base)
            rr = random.Random(seed + 1)
            train_ewc(model, lambda: dict_lines() * 20, S2_STEPS, stoi, rr, old, imp, strength)
            train_ewc(model, lambda: en_corpus(2000, 2000 + seed), S3_STEPS, stoi, rr, old, imp, strength)
            for where in ["mlp", "hidden"]:
                en_p = patterns(model, en_probe, stoi, en_words, where)
                finals[(seed, strength, where)] = en_p
                out.append({"seed": seed, "strength": strength, "where": where, "group": "synonyms", "syn": synonym_scores(en_p)})
                for gname, group in GROUPS.items():
                    out.append({"seed": seed, "strength": strength, "where": where, "group": gname,
                                "rows": group_compare(stage1_pats[seed][where], en_p, group)})
        print(f"seed {seed} done ({time.time() - t0:.0f}s)", flush=True)
    for seed in SEEDS:  # control: another seed's stage-1 neurons
        other = SEEDS[(SEEDS.index(seed) + 1) % len(SEEDS)]
        for where in ["mlp", "hidden"]:
            for gname, group in GROUPS.items():
                out.append({"seed": seed, "strength": "control", "where": where, "group": gname,
                            "rows": group_compare(stage1_pats[other][where], finals[(seed, 10, where)], group)})
    json.dump(out, open("roles_results.json", "w"), indent=1)
    print(f"saved roles_results.json ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
