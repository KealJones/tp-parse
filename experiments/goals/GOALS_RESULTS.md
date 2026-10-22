# Goals + lookup: results

3 seeds, 200 test episodes per split. N = English goal episodes in the last stage.
Success = the model's own plan, run in the world, gets the goal.

## N = 16

| condition | iid | combo (hidden + locked) | long (4–5 obstacles) | looked up when needed | looked up when not needed |
|---|---|---|---|---|---|
| tp | 0% | 0% | 0% | 1% | 4% |
| english | 0% | 0% | 0% | 0% | 1% |
| reference | 79% | 84% | 72% | 87% | 0% |

## N = 64

| condition | iid | combo (hidden + locked) | long (4–5 obstacles) | looked up when needed | looked up when not needed |
|---|---|---|---|---|---|
| tp | 1% | 0% | 0% | 3% | 6% |
| english | 0% | 0% | 0% | 2% | 4% |
| reference | 80% | 85% | 68% | 91% | 0% |

## N = 256

| condition | iid | combo (hidden + locked) | long (4–5 obstacles) | looked up when needed | looked up when not needed |
|---|---|---|---|---|---|
| tp | 10% | 5% | 2% | 8% | 6% |
| english | 4% | 1% | 1% | 8% | 3% |
| reference | 80% | 82% | 67% | 89% | 0% |

## tp vs english, per seed (mean success over the three splits)

- N=16: tp ahead by +0.1 points, better in 1/3 seeds
- N=64: tp ahead by +0.3 points, better in 2/3 seeds
- N=256: tp ahead by +3.9 points, better in 3/3 seeds

## Why plans failed (all seeds, N, splits)

- tp: wrong choice 1723, garbled 1098, false claim 878, wrong agent 483, bad take 352, bad open 268, bad search 260, bad go 176, done without goal 27, bad unlock 21
- english: garbled 2727, wrong choice 967, false claim 546, wrong agent 387, bad take 278, bad search 166, bad open 150, bad go 109, done without goal 17, bad unlock 16
- reference: bad go 736, garbled 208, bad take 145, bad open 89, false claim 20, wrong choice 9, wrong agent 3, too long 1
