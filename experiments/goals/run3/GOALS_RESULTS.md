# Goals + lookup, run 3: results

3 seeds, 200 test episodes per split, 1024 English plans in the last stage.
Success = the model's own plan, run in the world, gets the goal.

Plans in the simple language before English (exact match): iid 83%, combo 88%

| model | iid | combo (hidden + locked) | long (4–5 obstacles) | looked up when needed | looked up when not needed |
|---|---|---|---|---|---|
| tp | 75% | 60% | 71% | 45% | 0% |
| tp + RL | 78% | 64% | 72% | 46% | 0% |
| reference | 91% | 98% | 93% | 99% | 0% |

## RL, per seed (mean success over splits, before → after)

- seed 0: 68% → 62%
- seed 1: 59% → 71%
- seed 2: 78% → 80%

## Why plans failed

- tp: bad go 180, bad take 179, bad open 114, garbled 63, wrong choice 20, false claim 6, done without goal 3, wrong agent 2
- tp + RL: bad go 231, bad take 154, bad open 53, garbled 50, wrong choice 24, false claim 4, done without goal 1
- reference: bad go 54, bad take 46, wrong choice 3, bad open 2, bad unlock 2, false claim 1

Export check (HF vs llama.cpp-style forward, max logit difference): 2.0e-05
