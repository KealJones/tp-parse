# Fine-tune test: HuggingFaceTB/SmolLM2-360M-Instruct

## Pilot (20 training steps, 2 problems per cell: every code path once)

- ft-slots: ran in 218s, clean short 0%
- ft: ran in 194s, clean short 0%
- lora-slots: ran in 306s, clean short 0%
- untouched: ran in 65s, clean short 0%

Pilot passed; full run started.

One seed. 24 problems per cell, spread over the four skins. Untouched is shown two worked examples;
the fine-tunes see none. Clean = as trained; messy = periods removed (a quarter of training was like this);
filler = periods removed plus speech filler ("um", "like", "you know"…), never seen in training.

## Planning in the world

| version | clean short | clean long | messy short | messy long | filler short | filler long | searched when needed | bookkeeping fails |
|---|---|---|---|---|---|---|---|---|
| untouched | 0% | 0% | 0% | 0% | 0% | 0% | 0% | 6 |
| ft | 100% | 100% | 100% | 100% | 42% | 38% | 91% | 10 |
| ft-slots | 96% | 100% | 92% | 96% | 42% | 54% | 92% | 13 |
| lora-slots | 96% | 96% | 92% | 96% | 58% | 58% | 92% | 12 |
| ft, 4-bit | 42% | 29% | 33% | 17% | 21% | 0% | 78% | 23 |
| ft-slots, 4-bit | 42% | 8% | 50% | 4% | 29% | 0% | 63% | 31 |
| lora-slots, 4-bit | 46% | 29% | 46% | 12% | 12% | 4% | 82% | 45 |

## Why plans failed (clean + messy + filler)

- untouched: garbled 64, wrong choice 47, too long 27, bad take 3, false claim 2, bad go 1
- ft: garbled 16, bad go 5, bad take 4, wrong choice 3, bad open 1
- ft-slots: garbled 14, bad go 7, bad open 2, bad take 2, bad unlock 2, wrong choice 1, too long 1
- lora-slots: garbled 12, bad go 9, bad take 2, bad open 1, wrong choice 1

## Keal's real messages (45: pick what he meant out of four; chance 25%)

| version | typed | voice | all | 4-bit all |
|---|---|---|---|---|
| untouched | 21% | 38% | 29% | – |
| ft | 29% | 43% | 36% | 36% |
| ft-slots | 29% | 48% | 38% | 36% |
| lora-slots | 33% | 57% | 44% | 40% |

## English kept

| version | ARC-Easy | WikiText-2 perplexity | 4-bit ARC | 4-bit perplexity |
|---|---|---|---|---|
| untouched | 49% | 24.1 | – | – |
| ft | 51% | 24.5 | 47% | 29.6 |
| ft-slots | 52% | 24.9 | 49% | 30.2 |
| lora-slots | 53% | 28.0 | 49% | 31.9 |

## Time

- untouched: 8 min
- ft: 32 min (training 12 min, final plan loss 0.0012)
- ft-slots: 35 min (training 14 min, final plan loss 0.0021)
- lora-slots: 53 min (training 18 min, final plan loss 0.0037)

## One long problem (clean)

- untouched (fail): problem `the door of the shop is locked . the door of the school is closed . the door of the house is open . the person is at the shop . the book is at the forest . the person wants the water . plan :`
  plan: `the person wants the water because the water is at the forest .`
- ft (ok): problem `the door of the shop is locked . the door of the school is closed . the door of the house is open . the person is at the shop . the book is at the forest . the person wants the water . plan :`
  plan: `search : where is the water ? result : the water is at the shop . the door of the shop is locked , so the person needs the key . search : where is the key ? result : the key is at the school . the person is not at the school , so the person goes to the school . the door of the school is closed , so the person opens the door of the school . the person takes the key . the person is not at the shop , so the person goes to the shop . the door of the shop is locked , so the person opens the door of the shop with the key . the person takes the water . the person has the water , so the goal is done . done .`
- ft-slots (ok): problem `the door of the shop is locked . the door of the school is closed . the door of the house is open . the person is at the shop . the book is at the forest . the person wants the water . plan :`
  plan: `search : where is the water ? result : the water is at the shop . the door of the shop is locked , so the person needs the key . search : where is the key ? result : the key is at the school . the person is not at the school , so the person goes to the school . the door of the school is closed , so the person opens the door of the school . the person takes the key . the person is not at the shop , so the person goes to the shop . the door of the shop is locked , so the person opens the door of the shop with the key . the person takes the water . the person has the water , so the goal is done . done .`
- lora-slots (ok): problem `the door of the shop is locked . the door of the school is closed . the door of the house is open . the person is at the shop . the book is at the forest . the person wants the water . plan :`
  plan: `search : where is the water ? result : the water is at the shop . the door of the shop is locked , so the person needs the key . search : where is the key ? result : the key is at the school . the person is not at the school , so the person goes to the school . the door of the school is closed , so the person opens the door of the school . the person takes the key . the person is not at the shop , so the person goes to the shop . the door of the shop is locked , so the person opens the door of the shop with the key . the person takes the water . the person has the water , so the goal is done . done .`
