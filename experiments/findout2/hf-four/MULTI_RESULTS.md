# Small models off the shelf: figure-it-out test (v3 names) and TypeScript

No fine-tuning, thinking off, greedy. Tools test: the 120 held-out episodes (5 types x 24), same system prompt and tools as the pilot, now with normal-sounding names; 'fair' is `world2.fair_score`. TypeScript: MultiPL-E HumanEval-TS, 159 problems, first answer only, run against the problem's tests.

| model | tools: right (old scorer) | tools: right (fair) | tools: fair strict | fair right, clean / messy | TypeScript pass@1 | minutes |
| --- | --- | --- | --- | --- | --- | --- |
| LFM2.5-350M | 20% | 20% | 1% | 17% / 24% | 10% (16/159) | 0.8 |
| Qwen2.5-Coder-0.5B-Instruct | 7% | 7% | 0% | 5% / 9% | 51% (81/159) | 5.3 |
| Qwen3.5-0.8B | 19% | 22% | 2% | 32% / 9% | 19% (30/159) | 8.0 |
| Qwen3.5-2B | 44% | 46% | 37% | 54% / 36% | 41% (65/159) | 6.7 |

## Tools test by held-out type (fair right answer)

| type | LFM2.5-350M | Qwen2.5-Coder-0.5B-Instruct | Qwen3.5-0.8B | Qwen3.5-2B |
| --- | --- | --- | --- | --- |
| H:argmax4 | 17% | 17% | 67% | 67% |
| H:ask-diff | 17% | 0% | 8% | 17% |
| H:basket3 | 0% | 0% | 4% | 38% |
| H:bridge-compare | 38% | 17% | 25% | 21% |
| H:cost-compare | 29% | 0% | 4% | 88% |
