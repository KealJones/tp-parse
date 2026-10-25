# Gemma 4 on the pilot's held-out test set

Off the shelf, no fine-tuning. Same system prompt, tools and request text as the pilot; thinking off, greedy. `ok`/`strict` = world2's scorer (same as PILOT_RESULTS.md). `fair` = with the three scorer fixes (yes/no accepted, facts already seen in a tool result count, non-answers fail). Subset = the 16 episodes Haiku and Sonnet ran.

| model | held-out ok | held-out strict | fair ok | fair strict | 16-subset fair ok | minutes |
| --- | --- | --- | --- | --- | --- | --- |
| gemma-4-E2B-it | 58% | 43% | 58% | 48% | 13/16 | 4.4 |

## By held-out type (world2 strict / fair right answer)

| type | gemma-4-E2B-it |
| --- | --- |
| H:argmax4 | 71% strict / 71% fair |
| H:ask-diff | 50% strict / 67% fair |
| H:basket3 | 33% strict / 42% fair |
| H:bridge-compare | 4% strict / 42% fair |
| H:cost-compare | 58% strict / 67% fair |
