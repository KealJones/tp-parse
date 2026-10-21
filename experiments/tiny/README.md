# Tiny toki pona transfer experiments

Three small experiments on one question: if a model learns toki pona first, do English words "funnel" into the spots toki pona made for each concept (water next to telo), and does toki pona survive afterwards?

| | file | setup | result |
|---|---|---|---|
| v1 | `tiny_transfer.py` | 4 labelled pairs (telo→WET, water→WET…). No sentences. | English learned 2.7× faster after toki pona, and telo sat next to water, but only because the labels told it they match. A sanity check, not evidence. |
| v2 | `experiment.py` | 1-layer transformer, next-word prediction only, separate word tables per language with shared attention + MLP. Controls: toki pona grammar with random meanings, random toki pona words. | Toki pona gave a small English speed-up, but the controls gave the same one: generic practice, not meaning. English words did not land next to their toki pona words (chance level), compounds didn't either. |
| v3 | `stages.py` | One shared vocabulary. Stage 1 toki pona, stage 2 a text dictionary ("water means telo ."), stage 3 a big English sweep with synonyms toki pona lacks (liquid, home, large, nice, munches) that never appear in the dictionary. | The dictionary was memorised as trivia (100% on "X means ?" for listed words) without moving word vectors together. The English sweep then wiped out toki pona (test loss 0.82 → 9.4) and the dictionary (back to chance). No funnelling for unseen words or synonyms. Mixing 10% toki pona into stage 3 kept toki pona alive (1.28) but still produced no alignment. Freezing attention + MLP made forgetting worse, because the shared word table kept changing. |

| v4 | `neurons.py` | Same as v3, but looks inside: do English words fire the MLP neurons their toki pona word fired *before* the English sweep? | A faint but real trace: correlation with own concept +0.10 (MLP) / +0.25 (hidden) vs about 0 for other concepts and for a different-seed control. Toki pona itself was forgotten, but English kept a tilt toward its old spots. |
| v5 | `ewc.py` | v3 plus elastic weight consolidation after stage 1, at five strengths. | Light protection (10) kept toki pona (test loss 1.65 vs 10.5 unprotected), barely hurt English (0.946 vs 0.925), and tripled the hub trace (+0.29 vs +0.10), including synonyms never in the dictionary (large → suli +0.50, nice → pona +0.46). Stronger protection did slightly worse. |
| v6 | `roles.py` | Hub test restricted to same-kind words (verbs vs verbs, nouns vs nouns, adjectives vs adjectives), plus an English-only model as a baseline for synonym grouping. | With light EWC, verbs pick their own toki pona verb 31–38% of the time (chance 20%, control 7–12%); goes → tawa 5/6 seeds. Nouns stay near chance in accuracy but keep a positive correlation (+0.18–0.26). An English-only model already groups synonyms strongly (+0.86); toki pona + EWC is only slightly tighter (+0.97 MLP, ~equal in the hidden state). The toy world is too easy to show a synonym benefit: synonyms there are used identically. |

| v7 | `knockout.py` | Keal's grid idea: gradient routing plants each toki pona concept in its own block of 8 MLP neurons (routing by the word being predicted), then an unrestricted English sweep, then knock out each block. | Planting works: right after toki pona, knocking out a block hurts its own word by +4.3 vs +1.1 for others (own block is the worst hit 56% of the time; chance 11%). After the English sweep, English does not run through the planted blocks: own-concept damage is no bigger than other-concept damage (2–4% own wins, below chance), with or without EWC. With EWC the blocks still matter for English, but as general machinery rather than per concept. Likely reason: routing by predicted word ties each block to the toki pona *word*, and nothing links "water" to that block. |

Corpus samples for every version are in `CORPUS.md`. Full tables: `results_v2.txt`, `results_v3.txt`.

## What this says (at this tiny scale)

Updated after v4–v6: learned one after another, English overwrites toki pona's behaviour, but not entirely its spots. Protecting the toki pona weights with light EWC keeps toki pona alive and makes English route through toki pona's neurons about three times more, and for verbs this holds even against other verbs, so it's meaning rather than sentence position. The effect is real but modest. The toy world is too simple to show whether these hubs make a model more efficient; that needs rarer synonyms and a richer world.

Earlier summary (v1–v3):

Learning languages one after another, nothing makes the model reuse toki pona's spots for English: it can learn English its own way, and it does, overwriting what was there. Something has to force sharing. The most promising next try is code-switched sentences ("the soweli eats the pan"), which put words from both languages into the same slots in the same sentence, the way a bilingual kid hears them.

Run any of them with `python3 <file>` (v2 and v3 need PyTorch; v3 takes about 10 minutes on a laptop CPU).
