# Teacher episodes (squiggle-ft)

Teacher Qwen/Qwen3-30B-A3B-Thinking-2507-FP8 on gpu: 24 of 24 episodes in 8 min (deadline 8.0 min), 13 training examples, 551 generated tokens/s. Teacher stats: {'calls': 135, 'retries': 27, 'failed': 1, 'too_long': 0, 'unfinished': 0, 'gen_tokens': 249585, 'answer_chars': 46976}.

| family | habit | episodes | right answer | kept (strict) | examples |
| --- | --- | --- | --- | --- | --- |
| chat_mid | plain chat after a task | 3 | 3 | 2 (67%) | 10 |
| hermes_compute | compute with calculate (Hermes requests) | 3 | 0 | 0 (0%) | 0 |
| lookup_then_compute | two lookups, then calculate | 3 | 0 | 0 (0%) | 0 |
| math_pair | compute, or ask for the missing number | 3 | 2 | 1 (33%) | 3 |
| messy_multi | split a run-on, answer every part | 3 | 0 | 0 (0%) | 0 |
| near_miss | flag a near-miss word, don't autocorrect | 3 | 3 | 3 (100%) | 7 |
| personal_mid | personal advice after a task | 3 | 2 | 1 (33%) | 5 |
| repo_chain | sequential plan (step 2 uses step 1) | 3 | 1 | 0 (0%) | 0 |
| **all** | | 24 | 11 | 7 (29%) | 25 |

## Why episodes were dropped (top 40)

- 3 × messy_multi: the web part is missing or wrong
- 3 × repo_chain: never read the file that defines it (step 2 must use step 1's path)
- 2 × lookup_then_compute: no calculate call for the difference
- 2 × lookup_then_compute: didn't find both birth years in a result about each person
- 2 × repo_chain: error: episode timed out
- 2 × repo_chain: the reply doesn't quote the line
- 1 × chat_mid: turn 1: the reply doesn't say where its facts came from (page, repo, file)
- 1 × chat_mid: turn 1: the reply states a fact no prompt or tool result of the turn has: number 2027
- 1 × hermes_compute: turn 1: the reply states a fact no prompt or tool result of the turn has: number 314.16
- 1 × hermes_compute: reply doesn't carry the computed value
- 1 × hermes_compute: turn 1 call 6 (step): output must start with <think> and close it with </think>
- 1 × hermes_compute: turn 1: computes via run_js (plain arithmetic goes through calculate)
- 1 × hermes_compute: turn 1: made a plan for a one-lookup request
- 1 × hermes_compute: error: episode timed out
- 1 × hermes_compute: didn't compute it with run_js
- 1 × lookup_then_compute: the reply doesn't give the calculated difference
- 1 × lookup_then_compute: turn 1: the reply doesn't say where its facts came from (page, repo, file)
- 1 × lookup_then_compute: context full
- 1 × lookup_then_compute: turn 1: a Check line doesn't refer to the result it follows: 'The question needs two birth
- 1 × math_pair: the answer was written before calculate returned it
- 1 × math_pair: turn 1: says it checked / confirmed / found something, but no tool result was seen
- 1 × math_pair: turn 1: the reply states a fact no prompt or tool result of the turn has: number 5
- 1 × math_pair: turn 2: the reply states a fact no prompt or tool result of the turn has: number 20
- 1 × messy_multi: no plan for a two-part request
- 1 × messy_multi: error: episode timed out
- 1 × messy_multi: the version part is missing or wrong
- 1 × personal_mid: turn 1: a Check line doesn't refer to the result it follows: 'fetch_url of Wikipedia list 
- 1 × personal_mid: error: episode timed out
- 1 × personal_mid: turn 1: answered without looking it up
- 1 × personal_mid: turn 1: no reply
- 1 × repo_chain: the line appears in no read_file result of this turn
- 1 × repo_chain: no plan for a two-step task
