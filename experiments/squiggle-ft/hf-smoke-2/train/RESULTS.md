# Squiggle small-model fine-tune: results

**Verdict: NO-GO (not yet)** for `gemma3`.

| check | pass | value |
| --- | --- | --- |
| trained types, strict mean | no | 0% (bar 50%) |
| held-out types, strict mean | no | 0% (bar 30%) |
| no held-out type at 0% | no | lowest 0% |
| well-formed model calls | no | 0.0% (bar 95%) |
| episodes that loop or hit the call cap | no | 42.9% (bar ≤ 5%) |
| plain chat stays plain | no | 50% (bar 90%) |
| messy within 10 points of clean | yes | clean 0%, messy 0% |
| beats the untouched Gemma 3 270M | no | 0%/0% vs 0%/0% |

## Strict score per task type (right answer and the habit)

| type | habit | untouched-gemma3 | gemma3 | functiongemma | lfm25 |
| --- | --- | --- | --- | --- | --- |
| bare_link | read a bare link | 0% (0%) | 0% (0%) | 0% (0%) | 0% (0%) |
| chat | plain chat stays plain | 0% (0%) | 0% (0%) | 0% (0%) | 0% (0%) |
| chat_after | a task, then plain thanks | 0% (0%) | 0% (0%) | 0% (0%) | 0% (0%) |
| hermes_compute | compute (Hermes requests) | 0% (0%) | 0% (0%) | 0% (0%) | 0% (0%) |
| hermes_need | ask for missing input (Hermes requests) | 0% (0%) | 0% (0%) | 0% (0%) | 0% (0%) |
| math | compute with run_js | 0% (0%) | 0% (0%) | 0% (0%) | 0% (0%) |
| memory_repo | use memory, don't ask | 0% (0%) | 0% (0%) | 0% (0%) | 0% (0%) |
| need_math (held out) | ask for a missing number (held out) | 0% (0%) | 0% (0%) | 0% (0%) | 0% (0%) |
| need_repo | ask which repo | 0% (0%) | 0% (0%) | 0% (0%) | 0% (0%) |
| past_chat | find an earlier chat | 0% (0%) | 0% (0%) | 0% (0%) | 0% (0%) |
| recipe_compare (held out) | use a recipe on web lookups (held out) | 0% (100%) | 0% (0%) | 0% (100%) | 0% (100%) |
| recipe_repo | use a recipe | 0% (0%) | 0% (0%) | 0% (0%) | 0% (0%) |
| refs | follow 'it' to the last repo | 0% (0%) | 0% (0%) | 0% (0%) | 0% (100%) |
| repo_fact | look in the repo | 0% (0%) | 0% (0%) | 0% (0%) | 0% (0%) |
| repo_two | plan a two-part repo task | 0% (0%) | 0% (0%) | 0% (0%) | 0% (0%) |
| repo_where | find a definition | 0% (0%) | 0% (0%) | 0% (0%) | 0% (0%) |
| web_bridge (held out) | plan a two-hop lookup (held out) | 0% (0%) | 0% (0%) | 0% (0%) | 0% (50%) |
| web_compare | plan + look up two things | 0% (0%) | 0% (100%) | 0% (100%) | 0% (100%) |
| web_fact | look it up | 0% (0%) | 0% (0%) | 0% (0%) | 0% (0%) |

(right answer only in brackets)

## Habits

| measure | untouched-gemma3 | gemma3 | functiongemma | lfm25 |
| --- | --- | --- | --- | --- |
| trained types, strict mean | 0% | 0% | 0% | 0% |
| trained types, right answer | 0% | 6% | 6% | 12% |
| held-out types, strict mean | 0% | 0% | 0% | 0% |
| well-formed calls | 0% | 0% | 0% | 0% |
| episodes looping / call-capped | 0% | 43% | 0% | 0% |
| plans multi-step requests | 0% | 0% | 0% | 0% |
| asks (need) when info is missing | 0% | 0% | 0% | 0% |
| plain chat stays plain | 100% | 50% | 100% | 0% |
| done results carry the answer | - | - | - | - |
| clean requests, strict | 0% | 0% | 0% | 0% |
| messy requests, strict | 0% | 0% | 0% | 0% |

## Notes

- `gemma3` (unsloth/gemma-3-270m-it): trained 1 epochs on 78 examples in 0 min.
- `functiongemma` (unsloth/functiongemma-270m-it): trained 1 epochs on 78 examples in 0 min.
- `lfm25` (LiquidAI/LFM2.5-350M): trained 1 epochs on 78 examples in 0 min.
