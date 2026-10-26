# Plain vs smart harness, same model, no training

Held-out figure-it-out test (world2 v3, `fair_score`). The smart harness uses no answer key: it filters search results to the asked-about entities, points out new names once, and sends an answer back once if the model did fewer lookups than its own plan had steps, used a number no tool gave it, looked nothing up, or gave no 'Answer:' line (at most twice). CPU run, greedy, thinking off.

| model | harness | episodes | right (fair) | fair strict | clean / messy | answers sent back | new-name nudges | minutes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| LFM2.5-350M | plain | 120 | 18% | 1% | 17% / 18% | 0 | 0 | 5.2 |
| LFM2.5-350M | smart | 120 | 12% | 1% | 12% / 13% | 49 | 23 | 7.9 |

## By held-out type (right, fair)

| type | LFM2.5-350M plain | LFM2.5-350M smart |
| --- | --- | --- |
| H:argmax4 | 17% | 29% |
| H:ask-diff | 12% | 0% |
| H:basket3 | 0% | 0% |
| H:bridge-compare | 29% | 21% |
| H:cost-compare | 29% | 12% |
