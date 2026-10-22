# Skins: the lesson without the nouns

Tests the "intuition block" idea: a module that pulls out the shape of a problem, with the nouns stripped away, so the lesson carries over to a domain the model has never planned in.

The goals world (someone wants something; there may be closed or locked doors, a key elsewhere, a missing fact to look up, a choice by property) is dressed in six skins. Each skin has its own word for every agent, place, item, property, key, door and verb. The grammar and the shared words ("the", "so", "because", "search", "plan") stay the same.

| skin | example sentence |
|---|---|
| home | the door of the school is locked , so the person needs the key . |
| computer | the lock of the server is locked , so the user requires the password . |
| ship | the gate of the dock is locked , so the captain demands the permit . |
| kitchen | the lid of the oven is locked , so the cook misses the opener . |
| **farm** (unseen) | the hatch of the stable is locked , so the farmer lacks the crowbar . |
| **space** (unseen) | the airlock of the lab is locked , so the pilot awaits the keycard . |

The model sees plans in the first four skins. Farm and space only appear as loose descriptive sentences, never as a plan and never side by side with another skin.

## Conditions

- `base`: a small GPT (about 3.6M parameters, 8 layers, as in the goals runs).
- `lesson`: the same GPT with a **lesson block** halfway up. It squeezes the model's state into a 64-number lesson vector and adds it back in. Two training signals shape the vector, only on the four plan skins:
  1. **Noun-free:** from the lesson vector alone, predict the next word's *job* (AGENT, PLACE-WITH-DOOR, ITEM, KEY, GO-verb…), not the word itself.
  2. **Same lesson in any skin:** the same problem in two skins must give the same lesson vectors, position by position.
- `reference`: plans in all six skins (a ceiling).

All three see exactly the same batches.

## Tests

- Plans in the seen skins and in the unseen skins with zero plans seen, on `short` (1–3 obstacles) and `long` (4–5, longer than any training plan) problems. The world runs each plan and checks the goal is really reached. Using a word from another skin counts as its own failure.
- Then 32 plans per unseen skin, a short top-up of training, and the unseen tests again.
- **Analogy test:** does the middle of the model file "airlock", "pries" and "crater" under the same job as "door", "opens" and "field"? Nearest job centroid, 13 jobs, chance about 8%.

## Run it on Kaggle

1. Open https://www.kaggle.com/kernels/welcome?src=https://github.com/KealJones/tp-parse/blob/main/experiments/skins/skins.ipynb
2. Settings → Accelerator → **GPU T4**. Internet can stay off.
3. Run All. About 1.5–2 hours. It writes `SKINS_RESULTS.md` and `skins_results.json`.

`python3 skins.py --show` prints one problem in all six skins. `skins.ipynb` is generated from `skins.py` by `make_notebook.py`, so edit the .py file and regenerate.
