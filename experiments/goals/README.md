# Goals + lookup

Does learning goal-directed planning in toki pona first make a small (~3.6M parameter, 8 layers, deep and thin) model plan better in English, from only a few English examples?

Each episode is a small goal problem: someone wants something, and there may be obstacles. These are a closed or locked door, a key somewhere else, a missing fact, or a choice by property ("wants a sweet thing"). The model writes its plan as chain-of-thought sentences. When a fact is missing it can call a lookup tool (`search : where is the bread ?`), and the harness answers. The world runs the model's own plan and checks whether the goal was really reached.

| condition | stage 1 | stage 2 | stage 3 |
|---|---|---|---|
| `tp` | toki pona goal episodes | mixed English/toki pona scenes, no goals (+20% toki pona replay) | N English goal episodes + scenes + replay |
| `english` | plain English scenes, no goals (same number of steps) | | same as tp |
| `reference` | English goal episodes | English scenes (+20% replay) | same as tp (upper bound, not a fair rival) |

Tests, all in English and generated freely by the model:

- `iid`: new episodes like the English few-shot ones
- `combo`: a hidden fact and a locked door together. These are in the toki pona data but never in the English few-shot data.
- `long`: 4–5 obstacles, longer than anything in any training data

It also measures whether the model looks things up when a fact is missing, and whether it searches when it doesn't need to. All generated toki pona passes `tp-parse --strict`.

## Run it on Kaggle

1. Open https://www.kaggle.com/kernels/welcome?src=https://github.com/KealJones/tp-parse/blob/main/experiments/goals/goals.ipynb
   (or File → Import Notebook → paste that GitHub URL).
2. Settings (right panel) → Accelerator → **GPU T4 x2** (or P100). Internet can stay off.
3. Run All. It takes about an hour. It prints progress, then a markdown report at the end, and writes `GOALS_RESULTS.md` and `goals_results.json`.
4. Paste the report back to Claude.

Local smoke test (CPU, tiny): `python3 goals.py --quick`. To see sample episodes: `python3 goals.py --show`.

`goals.ipynb` is generated from `goals.py` by `make_notebook.py`, so edit the .py file and regenerate.
