# Plain vs smart harness, same model, no training

Held-out figure-it-out test (world2 v3, `fair_score`). The smart harness uses no answer key: it filters search results to the asked-about entities, points out new names once, and sends an answer back once if the model did fewer lookups than its own plan had steps, used a number no tool gave it, looked nothing up, or gave no 'Answer:' line (at most twice). CPU run, greedy, thinking off.

| model | harness | episodes | right (fair) | fair strict | clean / messy | answers sent back | new-name nudges | minutes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Qwen3.5-0.8B | plain | 40 | 15% | 5% | 24% / 5% | 0 | 0 | 51.4 |
| Qwen3.5-0.8B | smart | 40 | 18% | 8% | 29% / 5% | 2 | 9 | 45.4 |

## By held-out type (right, fair)

| type | Qwen3.5-0.8B plain | Qwen3.5-0.8B smart |
| --- | --- | --- |
| H:argmax4 | 25% | 50% |
| H:ask-diff | 25% | 38% |
| H:basket3 | 0% | 0% |
| H:bridge-compare | 25% | 0% |
| H:cost-compare | 0% | 0% |
