# Fine-tune test: Qwen/Qwen3-0.6B

## Pilot (20 training steps, 2 problems per cell: every code path once)

- ft-slots: ran in 277s, clean short 0%
- ft: ran in 216s, clean short 0%
- lora-slots: ran in 454s, clean short 0%
- untouched: ran in 56s, clean short 0%

Pilot passed; full run started.

One seed. 24 problems per cell, spread over the four skins. Untouched is shown two worked examples;
the fine-tunes see none. Clean = as trained; messy = periods removed (a quarter of training was like this);
filler = periods removed plus speech filler ("um", "like", "you know"…), never seen in training.

## Planning in the world

| version | clean short | clean long | messy short | messy long | filler short | filler long | searched when needed | bookkeeping fails |
|---|---|---|---|---|---|---|---|---|
| untouched | 0% | 0% | 0% | 0% | 0% | 0% | 8% | 9 |
| ft | 100% | 100% | 96% | 100% | 58% | 58% | 93% | 5 |
| ft-slots | 100% | 100% | 100% | 100% | 96% | 58% | 95% | 2 |
| lora-slots | 100% | 96% | 100% | 96% | 83% | 67% | 97% | 4 |
| ft, 4-bit | 100% | 100% | 100% | 100% | 54% | 62% | 94% | 4 |
| ft-slots, 4-bit | 100% | 100% | 100% | 100% | 83% | 62% | 96% | 4 |
| lora-slots, 4-bit | 96% | 88% | 92% | 92% | 71% | 62% | 92% | 12 |

## Why plans failed (clean + messy + filler)

- untouched: garbled 116, wrong choice 8, another skin's word 8, bad open 3, wrong agent 3, false claim 2, bad unlock 2, bad go 1, bad take 1
- ft: garbled 13, bad go 3, wrong choice 3, false claim 1, bad take 1
- ft-slots: garbled 6, wrong choice 3, bad take 1, bad go 1
- lora-slots: garbled 9, bad go 4, wrong choice 1

## Keal's real messages (45: pick what he meant out of four; chance 25%)

| version | typed | voice | all | 4-bit all |
|---|---|---|---|---|
| untouched | 21% | 33% | 27% | – |
| ft | 38% | 43% | 40% | 33% |
| ft-slots | 21% | 33% | 27% | 33% |
| lora-slots | 38% | 43% | 40% | 31% |

## English kept

| version | ARC-Easy | WikiText-2 perplexity | 4-bit ARC | 4-bit perplexity |
|---|---|---|---|---|
| untouched | 57% | 36.2 | – | – |
| ft | 44% | 157.7 | 43% | 140.1 |
| ft-slots | 51% | 122.7 | 52% | 122.5 |
| lora-slots | 51% | 126.6 | 44% | 119.4 |

## Time

- untouched: 3 min
- ft: 42 min (training 15 min, final plan loss 0.0002)
- ft-slots: 46 min (training 18 min, final plan loss 0.0001)
- lora-slots: 58 min (training 19 min, final plan loss 0.0000)

## One long problem (clean)

- untouched (fail): problem `the door of the shop is locked . the door of the school is closed . the door of the house is open . the person is at the shop . the book is at the forest . the person wants the water . plan :`
  plan: `search : where is the water ? result : the water is at the shop . the person goes to the shop .`
- ft (ok): problem `the door of the shop is locked . the door of the school is closed . the door of the house is open . the person is at the shop . the book is at the forest . the person wants the water . plan :`
  plan: `search : where is the water ? result : the water is at the shop . the door of the shop is locked , so the person needs the key . search : where is the key ? result : the key is at the school . the person is not at the school , so the person goes to the school . the door of the school is closed , so the person opens the door of the school . the person takes the key . the person is not at the shop , so the person goes to the shop . the door of the shop is locked , so the person opens the door of the shop with the key . the person takes the water . the person has the water , so the goal is done . done .`
- ft-slots (ok): problem `the door of the shop is locked . the door of the school is closed . the door of the house is open . the person is at the shop . the book is at the forest . the person wants the water . plan :`
  plan: `search : where is the water ? result : the water is at the shop . the door of the shop is locked , so the person needs the key . search : where is the key ? result : the key is at the school . the person is not at the school , so the person goes to the school . the door of the school is closed , so the person opens the door of the school . the person takes the key . the person is not at the shop , so the person goes to the shop . the door of the shop is locked , so the person opens the door of the shop with the key . the person takes the water . the person has the water , so the goal is done . done .`
- lora-slots (ok): problem `the door of the shop is locked . the door of the school is closed . the door of the house is open . the person is at the shop . the book is at the forest . the person wants the water . plan :`
  plan: `search : where is the water ? result : the water is at the shop . the door of the shop is locked , so the person needs the key . search : where is the key ? result : the key is at the school . the person is not at the school , so the person goes to the school . the door of the school is closed , so the person opens the door of the school . the person takes the key . the person is not at the shop , so the person goes to the shop . the door of the shop is locked , so the person opens the door of the shop with the key . the person takes the water . the person has the water , so the goal is done . done .`
