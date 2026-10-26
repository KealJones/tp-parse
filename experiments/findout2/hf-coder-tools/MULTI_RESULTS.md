# Small models off the shelf: figure-it-out test (v3 names) and TypeScript

No fine-tuning, thinking off, greedy. Tools test: the 120 held-out episodes (5 types x 24), same system prompt and tools as the pilot, now with normal-sounding names; 'fair' is `world2.fair_score`. TypeScript: MultiPL-E HumanEval-TS, 159 problems, first answer only, run against the problem's tests.

| model | tools: right (old scorer) | tools: right (fair) | tools: fair strict | fair right, clean / messy | TypeScript pass@1 | minutes |
| --- | --- | --- | --- | --- | --- | --- |
| Qwen2.5-Coder-0.5B-Instruct | 4% | 4% | 0% | 5% / 4% |  | 5.7 |

## Tools test by held-out type (fair right answer)

| type | Qwen2.5-Coder-0.5B-Instruct |
| --- | --- |
| H:argmax4 | 17% |
| H:ask-diff | 0% |
| H:basket3 | 0% |
| H:bridge-compare | 4% |
| H:cost-compare | 0% |
