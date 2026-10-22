# Goals + lookup

Does learning goal-directed planning in toki pona first make a small (~3.6M parameter, 8 layers, deep and thin) model plan better in English, from only a few English examples?

Each episode is a small goal problem: someone wants something, and there may be obstacles. These are a closed or locked door, a key somewhere else, a missing fact, or a choice by property ("wants a sweet thing"). The model writes its plan as chain-of-thought sentences. When a fact is missing it can call a lookup tool (`search : where is the bread ?`), and the harness answers. The world runs the model's own plan and checks whether the goal was really reached.

| condition | stage 1 | stage 2 | stage 3 |
|---|---|---|---|
| `tp` | toki pona goal episodes | mixed plans: toki pona grammar with English words swapped in half the time (60%), plus toki pona plans and mixed scenes | N English goal episodes + scenes + replay |
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

## Results, run 1 (Kaggle T4, 3 seeds)

Full tables in `run1/GOALS_RESULTS.md`. Run 1's bridge was mixed scenes only, with no plans.

- **The setup works.** The reference model (English goals all along) solves about 80% of new episodes and 67–72% of the longer chains it never trained on. It looks things up 87–91% of the time when a fact is missing and never when it isn't.
- **Few-shot English planning failed for both rivals.** With 16–256 English plans, tp and english stay near 0%. tp is ahead at N=256 in 3/3 seeds (10% vs 4% iid), but that's a small edge on a floor.
- **tp did learn plan *structure*.** Its plans are far less often garbled (1,098 vs 2,727), but it fails on grounding instead: wrong choice, false claims, wrong agent.
- Likely cause: the bridge only mixed loose scenes, so nothing linked toki pona's plan skeleton (`la`, `tan ni`, `alasa`, `nasin`) to English's (`, so`, `because`, `search`, `plan`). The earlier reasoning test had short patterns. Here a plan is about 150 tokens of new English syntax to pick up from a handful of examples.

## Run 2 (current notebook)

The bridge now mixes whole plans, so toki pona's plan skeleton is used with English words before the model meets English plans, for example *lupa shop li pini wawa la child li opens e door shop kepeken key*. N is now 64 / 256 / 1024, and the notebook first checks that the tp model can plan in toki pona at all.

### Run 2 results (Kaggle T4, 3 seeds; full tables in `run2/GOALS_RESULTS.md`)

The tp model plans in toki pona first (exact match with the gold plan: iid 80%, combo 87%), then:

| N English plans | tp (iid / combo / long) | english | reference |
|---|---|---|---|
| 64 | 18% / 6% / 2% | 0% / 0% / 0% | 76% / 78% / 64% |
| 256 | 45% / 42% / 25% | 4% / 1% / 0% | 74% / 75% / 66% |
| 1024 | **71% / 68% / 64%** | 7% / 1% / 1% | 75% / 74% / 62% |

tp beat english in every seed at every N. At 1,024 it nearly matches the model trained on English plans all along, including the hidden + locked combos it never saw in English and chains longer than any training data.

The weak spot is lookups: tp searches for a missing fact only 39% of the time (reference 90%), so it often guesses. The search words (`alasa`, `sona`) were never swapped in the bridge, so that link had to come from the English examples alone.

Open question: is it *toki pona* that helps, or just learning to plan in any language first? The next control is the same pipeline with a made-up language in toki pona's place.
