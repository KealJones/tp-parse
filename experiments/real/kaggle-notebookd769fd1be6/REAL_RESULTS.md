# Simple language first, real data: results

One seed. English budget: 10,000 SimpleStories + 74,668 Tatoeba English sentences (3.5M tokens). Ceiling: 112M tokens of fresh English. 6,000 training steps each, 64×256 tokens per step.

| model | English val loss (lower is better) | BLiMP | bAbI (mean of 20 tasks) |
|---|---|---|---|
| simple-first | 2.674 | 58.2% | 59.3% |
| english | 2.633 | 60.3% | 56.3% |
| ceiling | 1.925 | 59.4% | 60.7% |

## BLiMP by area

| model | syntax | morphology | syntax_semantics | semantics | syntax/semantics |
|---|---|---|---|---|---|
| simple-first | 54.1% | 64.0% | 58.3% | 58.9% | 55.3% |
| english | 56.7% | 66.6% | 60.2% | 58.5% | 59.4% |
| ceiling | 57.0% | 68.4% | 55.5% | 53.0% | 70.0% |

## bAbI by task (chance is roughly 1 in the number of possible answers)

| model | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| simple-first | 50 | 42 | 32 | 63 | 74 | 66 | 76 | 68 | 60 | 52 | 69 | 58 | 90 | 42 | 44 | 46 | 52 | 94 | 8 | 98 |
| english | 46 | 38 | 32 | 64 | 51 | 60 | 76 | 70 | 62 | 46 | 68 | 52 | 87 | 36 | 48 | 50 | 48 | 94 | 9 | 90 |
| ceiling | 50 | 39 | 39 | 70 | 70 | 71 | 78 | 72 | 65 | 57 | 68 | 64 | 88 | 36 | 46 | 49 | 58 | 94 | 10 | 90 |

simple-first's toki pona val loss at the end: 2.487

## English val loss over training

- simple-first: 500:9.01, 1000:9.58, 1500:10.28, 2000:3.51, 2500:3.24, 3000:3.16, 3500:2.67, 4000:2.69, 4500:2.77, 5000:2.89, 5500:3.01, 6000:3.13
- english: 500:2.87, 1000:2.63, 1500:2.66, 2000:2.80, 2500:2.98, 3000:3.20, 3500:3.46, 4000:3.72, 4500:3.99, 5000:4.19, 5500:4.37, 6000:4.49
- ceiling: 500:2.80, 1000:2.45, 1500:2.31, 2000:2.22, 2500:2.15, 3000:2.09, 3500:2.05, 4000:2.01, 4500:1.98, 5000:1.96, 5500:1.94, 6000:1.93

## Samples (prompt: Once upon a time / The little dog / Mia wanted to)

**simple-first**
> Once upon a time, in a land far away, a girl named Mia danced with the clouds. She felt free and happy, just like her. One day, while running, she saw a shooting star. "Here it will go!" she shouted, feeling joy in her heart. With a flick of her hand, she opened a door made of sparkles. Inside, the star was in her hand. She could see
> The little dog is sitting on my friend's arm.
> Mia wanted to see the sky.

**english**
> Once upon a time, in a land far away, a girl named Mia found a shiny key. It sparkled like the stars in the night sky. She was curious and wanted to know what it could open. Mia climbed in and found a world of candy! She met a talking rabbit named Leo. "Hello, little cat! I am here to help me find my home!" Mia thought for a moment. "What
> The little dog is crying.
> Mia wanted to be poor.

**ceiling**
> Once upon a time, in a land far away, a girl named Mia found a shiny stone. It sparkled in the light, and she felt a pull to it. She picked it up and ran to her friend, Kim, who was playing near the river. "Look what I found!" she said, holding the stone high. Kim's eyes widened, and she asked, "What is this?" Mia showed
> The little dog stood at the edge of the park. It had bright eyes and a big smile. "I can do this!" it thought. With a strong push, the dog pushed the button. To its surprise, the dog was free! It barked happily. But then it saw the dog looking sad. "What's wrong?" the dog asked. The dog said, "I can't remember anything
> Mia wanted to be a pirate. Every night, she looked at her map. "It says to go to the sea!" she said to her brother. "What's the worst thing?" He replied, "I think it's a pirate ship!" So, they set sail on a small boat. The water was warm and the sun shined. As they sailed, Mia noticed something strange. "Look!

Export check (max logit difference HF vs GGUF-style forward): simple-first 1.4e-05, english 1.7e-05, ceiling 1.7e-05
