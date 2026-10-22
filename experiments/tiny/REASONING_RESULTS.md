# Reasoning hubs: results

4 seeds. Accuracy at the answer slot on new English reasoning episodes.
Chance: NEG/SAME/DIFF 1 in 6, IF/CAUSE 1 in 2. N = English examples of each pattern seen in training.

## N = 4

| condition | NEG | SAME | DIFF | IF | CAUSE | mean |
|---|---|---|---|---|---|---|
| planted | 22% | 16% | 18% | 56% | 68% | 36% |
| unplanted | 25% | 19% | 15% | 63% | 58% | 36% |
| english | 20% | 19% | 20% | 53% | 41% | 30% |

## N = 16

| condition | NEG | SAME | DIFF | IF | CAUSE | mean |
|---|---|---|---|---|---|---|
| planted | 16% | 17% | 18% | 89% | 89% | 46% |
| unplanted | 69% | 26% | 35% | 98% | 88% | 63% |
| english | 38% | 19% | 35% | 98% | 100% | 58% |

## N = 64

| condition | NEG | SAME | DIFF | IF | CAUSE | mean |
|---|---|---|---|---|---|---|
| planted | 15% | 15% | 18% | 100% | 100% | 50% |
| unplanted | 81% | 50% | 62% | 100% | 100% | 78% |
| english | 48% | 35% | 48% | 100% | 100% | 66% |

## Knockouts (planted): accuracy drop on own pattern vs average drop on other patterns

| N | NEG (ala) | SAME (sama) | DIFF (ante) | IF (la) | CAUSE (tan) |
|---|---|---|---|---|---|
| 4 | +4 / -1 | +2 / +1 | +0 / +1 | -0 / -1 | -6 / +1 |
| 16 | -3 / +6 | +0 / +3 | +2 / -0 | -5 / +2 | +0 / +6 |
| 64 | +0 / +1 | +0 / +1 | -0 / +0 | +2 / -0 | +18 / +0 |

Each cell: points lost on its own pattern / on other patterns when that hub's block is switched off.

## Planted vs unplanted per seed (mean accuracy over patterns)

- N=4: planted ahead by -0.1 points on average, better in 2/4 seeds
- N=16: planted ahead by -17.1 points on average, better in 0/4 seeds
- N=64: planted ahead by -28.9 points on average, better in 0/4 seeds
