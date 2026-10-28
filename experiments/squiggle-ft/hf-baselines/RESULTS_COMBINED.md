# Untouched vs fine-tuned, every base

Same 293 eval episodes for every column (squiggle-ft-train's set: EVAL_PLAN_V1, seed 123). *untouched* = the base as released, no training and no embedding changes; *tuned* = trained on teach-v1 (3 epochs).

## Habits

| measure | untouched-gemma3 | gemma3 | untouched-lfm25 | lfm25 | untouched-functiongemma | functiongemma |
| --- | --- | --- | --- | --- | --- | --- |
| trained types, strict mean | 0% | 10% | 0% | 36% | 0% | 21% |
| trained types, right answer | 5% | 17% | 9% | 43% | 5% | 29% |
| held-out types, strict mean | 0% | 0% | 0% | 0% | 0% | 0% |
| well-formed calls | 0% | 91% | 0% | 99% | 0% | 95% |
| episodes looping / call-capped | 1% | 6% | 0% | 4% | 1% | 3% |
| plans multi-step requests | 0% | 16% | 0% | 51% | 0% | 34% |
| asks (need) when info is missing | 0% | 15% | 0% | 30% | 0% | 4% |
| plain chat stays plain | 96% | 38% | 88% | 96% | 100% | 71% |
| done results carry the answer | - | - | - | 100% | - | 100% |
| clean requests, strict | 0% | 6% | 0% | 19% | 0% | 9% |
| messy requests, strict | 0% | 3% | 0% | 26% | 0% | 16% |
| tokens per call | 52 | 121 | 96 | 91 | 74 | 105 |
| episodes evaluated | 293 | 293 | 293 | 293 | 293 | 293 |

## Strict score per task type (right answer only in brackets)

| type | untouched-gemma3 | gemma3 | untouched-lfm25 | lfm25 | untouched-functiongemma | functiongemma |
| --- | --- | --- | --- | --- | --- | --- |
| bare_link | 0% (0%) | 8% (25%) | 0% (0%) | 83% (100%) | 0% (0%) | 33% (33%) |
| chat | 0% (0%) | 44% (44%) | 0% (0%) | 81% (81%) | 0% (0%) | 81% (81%) |
| chat_after | 0% (0%) | 0% (0%) | 0% (12%) | 0% (0%) | 0% (0%) | 0% (0%) |
| hermes_compute | 0% (0%) | 0% (8%) | 0% (0%) | 33% (33%) | 0% (0%) | 25% (25%) |
| hermes_need | 0% (0%) | 17% (17%) | 0% (0%) | 25% (25%) | 0% (0%) | 0% (0%) |
| math | 0% (12%) | 12% (12%) | 0% (31%) | 6% (6%) | 0% (0%) | 19% (19%) |
| memory_repo | 0% (0%) | 50% (50%) | 0% (0%) | 100% (100%) | 0% (0%) | 70% (80%) |
| need_repo | 0% (0%) | 8% (8%) | 0% (0%) | 50% (58%) | 0% (0%) | 0% (8%) |
| past_chat | 0% (8%) | 0% (8%) | 0% (8%) | 8% (8%) | 0% (0%) | 8% (8%) |
| recipe_repo | 0% (0%) | 0% (0%) | 0% (0%) | 67% (75%) | 0% (0%) | 17% (33%) |
| refs | 0% (0%) | 0% (8%) | 0% (25%) | 33% (42%) | 0% (25%) | 33% (67%) |
| repo_fact | 0% (0%) | 12% (31%) | 0% (0%) | 50% (62%) | 0% (6%) | 31% (38%) |
| repo_two | 0% (0%) | 0% (8%) | 0% (0%) | 0% (17%) | 0% (0%) | 0% (17%) |
| repo_where | 0% (0%) | 0% (0%) | 0% (0%) | 6% (19%) | 0% (0%) | 12% (12%) |
| web_compare | 0% (50%) | 0% (44%) | 0% (50%) | 25% (62%) | 0% (38%) | 0% (31%) |
| web_fact | 0% (6%) | 0% (6%) | 0% (12%) | 0% (0%) | 0% (6%) | 6% (12%) |
| need_math (held out) | 0% (0%) | 0% (0%) | 0% (0%) | 0% (0%) | 0% (0%) | 0% (0%) |
| recipe_compare (held out) | 0% (4%) | 0% (22%) | 0% (65%) | 0% (48%) | 0% (22%) | 0% (39%) |
| web_bridge (held out) | 0% (3%) | 0% (3%) | 0% (7%) | 0% (17%) | 0% (0%) | 0% (10%) |
