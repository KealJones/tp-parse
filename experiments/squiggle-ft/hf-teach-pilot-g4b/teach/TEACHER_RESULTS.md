# Teacher episodes (squiggle-ft)

Teacher google/gemma-4-26B-A4B-it on gpu: 51 of 48 episodes in 16 min (deadline 17.0 min), 124 training examples, 762 generated tokens/s. Teacher stats: {'calls': 344, 'retries': 68, 'failed': 6, 'too_long': 1, 'unfinished': 6, 'gen_tokens': 734676, 'answer_chars': 119383, 'judge_calls': 5}.

| family | habit | episodes | right answer | kept (strict) | examples |
| --- | --- | --- | --- | --- | --- |
| lookup_then_compute | two lookups, then calculate | 8 | 3 | 3 (38%) | 33 |
| math_pair | compute, or ask for the missing number | 7 | 3 | 2 (29%) | 6 |
| messy_multi | split a run-on, answer every part | 6 | 1 | 1 (17%) | 10 |
| near_miss | flag a near-miss word, don't autocorrect | 6 | 0 | 0 (0%) | 0 |
| need_web | ask what they mean, then look it up | 6 | 1 | 1 (17%) | 5 |
| recipe_web | use a recipe on web lookups | 6 | 5 | 5 (83%) | 37 |
| repo_chain | sequential plan (step 2 uses step 1) | 6 | 3 | 3 (50%) | 33 |
| web_fact_retry | look again when the first result is wrong | 6 | 0 | 0 (0%) | 0 |
| **all** | | 51 | 16 | 15 (29%) | 124 |

## Why episodes were dropped (top 40)

- 6 × near_miss: never names the user's word (silently corrected or ignored)
- 6 × web_fact_retry: turn 1: wrong or missing answer
- 5 × messy_multi: the web part is missing or wrong
- 4 × lookup_then_compute: didn't find both birth years in a result about each person
- 4 × lookup_then_compute: no calculate call for the difference
- 4 × messy_multi: the version part is missing or wrong
- 3 × math_pair: error: episode timed out
- 3 × math_pair: didn't ask for the missing number
- 3 × math_pair: no answer after asking
- 3 × messy_multi: error: episode timed out
- 3 × near_miss: error: episode timed out
- 3 × near_miss: neither asks nor labels the assumption about the word
- 3 × need_web: error: episode timed out
- 3 × need_web: didn't ask what they meant (searched or answered without a subject)
- 3 × need_web: no turn after the clarification
- 3 × repo_chain: never read the file that defines it (step 2 must use step 1's path)
- 3 × repo_chain: the reply doesn't quote the line
- 2 × lookup_then_compute: error: episode timed out
- 2 × need_web: turn 2: wrong or missing answer
- 2 × repo_chain: error: episode timed out
- 2 × web_fact_retry: the Check after the first result doesn't say what was wrong or missing
- 1 × lookup_then_compute: turn 1 call 3 (step): output must start with <think> and close it with </think>
- 1 × lookup_then_compute: turn 1 call 2 (step): output must start with <think> and close it with </think>
- 1 × lookup_then_compute: turn 1 call 6 (step): output must start with <think> and close it with </think>
- 1 × lookup_then_compute: turn 1: the reply doesn't say where its facts came from (page, repo, file)
- 1 × lookup_then_compute: context full
- 1 × math_pair: turn 1: the reply doesn't say where its facts came from (page, repo, file)
- 1 × math_pair: turn 1 call 2 (chat): output must start with <think> and close it with </think>
- 1 × math_pair: wrong or missing answer
- 1 × math_pair: did the maths in its head (no calculate call)
- 1 × near_miss: turn 1 call 3 (step): output must start with <think> and close it with </think>
- 1 × near_miss: turn 1: made a plan for a one-lookup request
- 1 × need_web: turn 1: says it checked / confirmed / found something, but no tool result was seen
- 1 × need_web: turn 2 call 6 (chat): output must start with <think> and close it with </think>
- 1 × need_web: turn 2: the reply doesn't say where its facts came from (page, repo, file)
- 1 × recipe_web: wrong or missing answer
- 1 × repo_chain: turn 1 call 2 (chat): output must start with <think> and close it with </think>
- 1 × web_fact_retry: only one lookup (the first result didn't answer it: search again or read a page)
- 1 × web_fact_retry: error: episode timed out
- 1 × web_fact_retry: turn 1: answered without looking it up
