# Trace: Keal plans a dinner for a coeliac guest

The second recorded trace (2026-10-23, about 28 minutes): an everyday problem with an unknown word, research, safety checks and a written answer. `transcript.md` is Keal's transcription; the final answer he wrote is in `answer.md`.

## The loop, step by step

| time | step | what happened | principle (Finding Out) |
|---|---|---|---|
| 0:13 | notice a gap | didn't know "coeliac", looked it up, then reduced it to the working rule: "gluten is bad, no gluten" | 3 |
| 1:06 | know your own limits | "I'm bad at cooking", so he searched for *easy* recipes for four | 8 |
| 1:38 | catch a slip | searched "easy gluten recipes" by mistake and noticed it | 7 |
| 1:52 | prefer sources to summaries | skipped the AI overview on purpose and opened real pages | 4 |
| 5:03 | verify every piece | checked each ingredient one by one, building the shopping list as he went | 5, 7 |
| 6:15 | generalise a finding | "all vegetables are gluten-free" settled several later items at once | 5 |
| 8:30 | follow a surprise | found fructans in onion and garlic, a different problem, and kept it as a caveat | 11 |
| 9:50 | catch an unchecked claim | started writing "entirely gluten-free", then: "well, we don't actually know that yet" | 7 |
| 11:51 | check the caveat | is fructan sensitivity the same as coeliac? It isn't, so the meal is fine for a confirmed coeliac | 7 |
| 13:58 | judge the source | "I have zero idea if this is a reputable website": looked up the Gluten Intolerance Group (nonprofit since 1974, runs a certification program) | open question: trusting sources |
| 18:55 | find a hidden risk | chicken stock can contain gluten (natural flavouring, yeast extract), so he said to buy stock labelled gluten-free | 7 |
| 11:08, 15:28 | think about what an AI should do | "an AI should probably give more than one answer"; "if I was an AI I'd ask the user if fructans are an issue" | 12 |
| 17:04 | return from a tangent | "we got off track here", then back to the list | 6 |
| 18:37, 27:09 | notice better tools | "could have done this in a big batch"; "if I had a tool for presenting a recipe, I'd use it" | 2, 4 |
| 23:18 | check what the person has | asks whether they own a large soup pot; storage containers made optional | 8, 12 |

## What the answer got right and what it missed

Right: every ingredient was checked against sources; the stock risk was caught, with a concrete rule for reading labels; the source was vetted; the fructan point was looked into and correctly framed as separate from coeliac disease; and the answer offers to find an alternative.

Missed, in roughly the order a coeliac guest would care:
- **Cross-contact in the kitchen**, the biggest risk for coeliac disease: wooden spoons, cutting boards, colanders, toasters, and a butter tub with breadcrumbs in it. "How you'd make sure it's safe" covers the cooking, not just the ingredients.
- **Seasoned salt:** the recipe uses seasoned salt, but the list says plain salt and pepper. Store-bought blends are a common hidden source of gluten.
- **Quantities** are missing from the shopping list.
- **What "gluten-free" on a label means** (in the US, under 20 ppm) would make the label rule stronger.

## What it suggests for training data

- **Breadth-first verification:** take the parts list, check each part, and generalise where one finding covers many.
- **Caveats are researched, not just added.** He followed up the fructan worry before deciding how to word it.
- **Source trust is checked explicitly**, which matches open question 3 in the paper.
- **Blind spots come from the framing.** He checked "what is in it", not "what touches it". A model needs the habit of asking what the real failure mode is for this person.
