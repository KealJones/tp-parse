# Big-model check on held-out episodes (Sun 25 Oct 2026)

Haiku and Sonnet, one fresh agent per episode, got only what the pilot model got: the same system prompt, the same three tool definitions,
and the exact request text (same seeds as `pilot.py`, 16 episodes from bridge-compare, ask-diff and argmax4). Tools are world2's real
`search`, `calculator` and `ask_person`, via `tool.py`. Every call is in `logs/`. `results.txt` is world2's own scorer.

| | right answer (world2 checker) | strict (world2) | actually right (read by hand) |
| --- | --- | --- | --- |
| Sonnet | 14/16 | 10/16 | 16/16 |
| Haiku | 14/16 | 11/16 | 15/16 |
| pilot gold / teacher (full held-out set) | 38% / 45% | 26% / 28% | — |

Scorer problems found:
1. "Is the town X lives in bigger than Y?" (14 of 24 bridge-compare test items) is a yes/no question, but the checker wants the winner's
   name and fails any answer that also names the loser. Both big models answered "Yes"/"No" correctly and were marked wrong.
2. Strict requires a search naming each entity. `search` adds a same-kind fact about another entity, and with only 6 towns that is often
   exactly the other number needed, so a correct run that reuses it fails strict.
3. A non-answer that mentions the winner passes ("Can't say; Loulneth has 70,568 people...").

The one real big-model failure: Haiku on "ok wait which is bigger: rineshjas town or loulneth idk" saw "Rineshja lives in Grafen" and did not
connect it to "rineshjas town" (the messy style strips the apostrophe).
