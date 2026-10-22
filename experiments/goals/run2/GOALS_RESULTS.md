# Goals + lookup: results

3 seeds, 200 test episodes per split. N = English goal episodes in the last stage.
Success = the model's own plan, run in the world, gets the goal.

## Sanity check: the tp model planning in toki pona (exact match with the gold plan, before English)

- iid 80%, combo 87%

## N = 64

| condition | iid | combo (hidden + locked) | long (4–5 obstacles) | looked up when needed | looked up when not needed |
|---|---|---|---|---|---|
| tp | 18% | 6% | 2% | 13% | 6% |
| english | 0% | 0% | 0% | 4% | 5% |
| reference | 76% | 78% | 64% | 93% | 0% |

## N = 256

| condition | iid | combo (hidden + locked) | long (4–5 obstacles) | looked up when needed | looked up when not needed |
|---|---|---|---|---|---|
| tp | 45% | 42% | 25% | 25% | 2% |
| english | 4% | 1% | 0% | 6% | 4% |
| reference | 74% | 75% | 66% | 89% | 0% |

## N = 1024

| condition | iid | combo (hidden + locked) | long (4–5 obstacles) | looked up when needed | looked up when not needed |
|---|---|---|---|---|---|
| tp | 71% | 68% | 64% | 39% | 4% |
| english | 7% | 1% | 1% | 12% | 3% |
| reference | 75% | 74% | 62% | 90% | 0% |

## tp vs english, per seed (mean success over the three splits)

- N=64: tp ahead by +8.3 points, better in 3/3 seeds
- N=256: tp ahead by +35.7 points, better in 3/3 seeds
- N=1024: tp ahead by +64.4 points, better in 3/3 seeds

## Why plans failed (all seeds, N, splits)

- tp: wrong choice 1147, false claim 652, bad go 561, bad take 478, bad open 314, garbled 154, bad unlock 32, done without goal 9, wrong agent 9, bad search 5
- english: wrong choice 1651, garbled 1334, false claim 945, bad take 444, bad search 253, bad open 244, wrong agent 218, bad go 176, bad unlock 26, done without goal 22
- reference: bad go 880, garbled 299, bad take 241, bad open 90, wrong choice 13, false claim 7, wrong agent 2, bad unlock 1
