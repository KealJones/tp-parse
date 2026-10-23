# Registers v2: results

## Pilot (1,500 steps, seed 0)

- base: loss 0.392, seen short 5%, long 0%, 125s training
- taught-every: loss 0.335, seen short 42%, long 20%, 284s training

Pilot passed; full run started.

5 seeds, 8000 training steps per model. Seen skins only (home, computer, ship, kitchen).
Success = the model's own plan, run in the world, gets the goal. Messy = the same problems with every period
removed from the facts (one run-on line), never seen in training.

| model | short | long | messy short | messy long | bookkeeping fails | wrong choice | final train loss |
|---|---|---|---|---|---|---|---|
| base | 87% | 76% | 0% | 0% | 289 | 3 | 0.305 |
| taught-ends | 89% | 79% | 21% | 15% | 220 | 0 | 0.301 |
| taught-every | 95% | 97% | 80% | 72% | 80 | 0 | 0.300 |
| self-every | 97% | 94% | 74% | 64% | 61 | 4 | 0.301 |

## Per seed (seen long / messy long)

- seed 0: base 92% / 0%, taught-ends 70% / 18%, taught-every 94% / 81%, self-every 96% / 82%
- seed 1: base 55% / 0%, taught-ends 90% / 35%, taught-every 98% / 89%, self-every 94% / 56%
- seed 2: base 89% / 0%, taught-ends 88% / 4%, taught-every 98% / 51%, self-every 96% / 68%
- seed 3: base 70% / 0%, taught-ends 83% / 6%, taught-every 98% / 50%, self-every 89% / 61%
- seed 4: base 74% / 0%, taught-ends 64% / 8%, taught-every 97% / 87%, self-every 94% / 54%

## Failures (seen, all seeds)

- base: bad go 223, garbled 76, bad open 39, bad take 26, wrong choice 3, false claim 1, too long 1
- taught-ends: bad go 159, garbled 96, bad take 36, bad open 25
- taught-every: bad go 39, bad take 22, bad open 19, garbled 2
- self-every: garbled 27, bad take 23, bad go 22, bad open 15, wrong choice 4, another skin's word 2, false claim 1

## Do the taught slots still hold the true state? (gold plans, after teaching stopped)

| model, skins | where | holding | door here | goal item |
|---|---|---|---|---|
| taught-ends, plan skins | 100% | 100% | 94% | 100% |
| taught-ends, unseen skins | 29% | 66% | 65% | 18% |
| taught-every, plan skins | 100% | 100% | 96% | 100% |
| taught-every, unseen skins | 31% | 65% | 66% | 17% |

Chance is about 20% / 25% / 25% / 20%.

## Time per model (seconds)

- base: train 636, eval 10
- taught-ends: train 1535, eval 25
- taught-every: train 1490, eval 25
- self-every: train 1474, eval 24

## One long problem, seed 0 (home skin)

Problem: the door of the house is closed . the water is at the house . the fish is not cold . the person is at the school . the book is cold . the bread is at the school . the door of the shop is open . the fish is at the school . the water is not cold . the fruit is at the shop . the key is at the house . the door of the school is locked . the person wants a cold thing . plan :

- base, clean: `the person wants the book because the book is cold . the door of the school is locked , so the person needs the key . the person is not at the house , so the person goes to the house . the door of the house is closed , so the person opens the door of the house . the person takes the key . the person is not at the school , so the person goes to the school . the door of the school is locked , so the person opens the door of the school with the key . the person takes the book . the person has the book , so the goal is done . done .`
- base, messy: `the person wants the fruit because the water cold .`
- taught-ends, clean: `the person wants the book because the book is cold . the door of the school is locked , so the person needs the key . the person is not at the house , so the person goes to the house . the door of the house is closed , so the person opens the door of the house . the person takes the key . the person is not at the school , so the person goes to the school . the door of the school is locked , so the person opens the door of the school with the key . the person takes the book . the person has the book , so the goal is done . done .`
- taught-ends, messy: `the person wants the water because the water is cold .`
- taught-every, clean: `the person wants the book because the book is cold . the door of the school is locked , so the person needs the key . the person is not at the house , so the person goes to the house . the door of the house is closed , so the person opens the door of the house . the person takes the key . the person is not at the school , so the person goes to the school . the door of the school is locked , so the person opens the door of the school with the key . the person takes the book . the person has the book , so the goal is done . done .`
- taught-every, messy: `the person wants the fruit because the fruit is cold .`
- self-every, clean: `the person wants the book because the book is cold . the door of the school is locked , so the person needs the key . the person is not at the house , so the person goes to the house . the door of the house is closed , so the person opens the door of the house . the person takes the key . the person is not at the school , so the person goes to the school . the door of the school is locked , so the person opens the door of the school with the key . the person takes the book . the person has the book , so the goal is done . done .`
- self-every, messy: `the person wants the bread because the bread is cold .`
