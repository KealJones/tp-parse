# Tiny toki pona transfer experiments

Three small experiments on one question: if a model learns toki pona first, do English words "funnel" into the spots toki pona made for each concept (water next to telo), and does toki pona survive afterwards?

| | file | setup | result |
|---|---|---|---|
| v1 | `tiny_transfer.py` | 4 labelled pairs (telo→WET, water→WET…). No sentences. | English learned 2.7× faster after toki pona, and telo sat next to water, but only because the labels told it they match. A sanity check, not evidence. |
| v2 | `experiment.py` | 1-layer transformer, next-word prediction only, separate word tables per language with shared attention + MLP. Controls: toki pona grammar with random meanings, random toki pona words. | Toki pona gave a small English speed-up, but the controls gave the same one: generic practice, not meaning. English words did not land next to their toki pona words (chance level), compounds didn't either. |
| v3 | `stages.py` | One shared vocabulary. Stage 1 toki pona, stage 2 a text dictionary ("water means telo ."), stage 3 a big English sweep with synonyms toki pona lacks (liquid, home, large, nice, munches) that never appear in the dictionary. | The dictionary was memorised as trivia (100% on "X means ?" for listed words) without moving word vectors together. The English sweep then wiped out toki pona (test loss 0.82 → 9.4) and the dictionary (back to chance). No funnelling for unseen words or synonyms. Mixing 10% toki pona into stage 3 kept toki pona alive (1.28) but still produced no alignment. Freezing attention + MLP made forgetting worse, because the shared word table kept changing. |

Corpus samples for every version are in `CORPUS.md`. Full tables: `results_v2.txt`, `results_v3.txt`.

## What this says (at this tiny scale)

Learning languages one after another, nothing makes the model reuse toki pona's spots for English: it can learn English its own way, and it does, overwriting what was there. Something has to force sharing. The most promising next try is code-switched sentences ("the soweli eats the pan"), which put words from both languages into the same slots in the same sentence, the way a bilingual kid hears them.

Run any of them with `python3 <file>` (v2 and v3 need PyTorch; v3 takes about 10 minutes on a laptop CPU).
