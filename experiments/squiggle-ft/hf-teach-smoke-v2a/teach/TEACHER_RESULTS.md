# Teacher episodes (squiggle-ft)

Teacher Qwen/Qwen3-30B-A3B-Thinking-2507-FP8 on gpu: 51 of 51 episodes in 11 min (deadline 12.0 min), 50 training examples, 657 generated tokens/s. Teacher stats: {'calls': 252, 'retries': 27, 'failed': 1, 'too_long': 0, 'unfinished': 0, 'gen_tokens': 436291, 'answer_chars': 96527}.

| family | habit | episodes | right answer | kept (strict) | examples |
| --- | --- | --- | --- | --- | --- |
| chat_mid | plain chat after a task | 3 | 0 | 0 (0%) | 0 |
| hermes_compute | compute with calculate (Hermes requests) | 3 | 0 | 0 (0%) | 0 |
| hermes_need | ask for missing input (Hermes requests) | 3 | 1 | 1 (33%) | 1 |
| lookup_then_compute | two lookups, then calculate | 3 | 0 | 0 (0%) | 0 |
| math_pair | compute, or ask for the missing number | 3 | 2 | 0 (0%) | 0 |
| messy_multi | split a run-on, answer every part | 3 | 1 | 0 (0%) | 0 |
| near_miss | flag a near-miss word, don't autocorrect | 3 | 2 | 0 (0%) | 0 |
| need_web | ask what they mean, then look it up | 3 | 1 | 1 (33%) | 5 |
| personal | warm advice, no tools | 3 | 3 | 2 (67%) | 2 |
| personal_mid | personal advice after a task | 3 | 0 | 0 (0%) | 0 |
| personal_tool | one lookup inside a personal ask | 3 | 3 | 2 (67%) | 8 |
| recipe_skip | use only the recipe steps that fit | 3 | 2 | 2 (67%) | 12 |
| recipe_web | use a recipe on web lookups | 3 | 2 | 0 (0%) | 0 |
| repo_chain | sequential plan (step 2 uses step 1) | 3 | 3 | 0 (0%) | 0 |
| unknown_word | look up a made-up word, don't define it | 3 | 3 | 3 (100%) | 9 |
| web_fact | look it up | 3 | 1 | 1 (33%) | 4 |
| web_fact_retry | look again when the first result is wrong | 3 | 3 | 2 (67%) | 9 |
| **all** | | 51 | 27 | 14 (27%) | 50 |

## Why episodes were dropped (top 40)

- 3 × chat_mid: turn 1: wrong or missing answer
- 3 × lookup_then_compute: no calculate call for the difference
- 3 × lookup_then_compute: the reply doesn't give the calculated difference
- 3 × personal_mid: turn 1: wrong or missing answer
- 3 × recipe_web: the plan doesn't follow the recipe
- 3 × repo_chain: no plan for a two-step task
- 2 × hermes_compute: didn't compute it with run_js
- 2 × messy_multi: the web part is missing or wrong
- 2 × need_web: turn 2: wrong or missing answer
- 2 × repo_chain: never read the file that defines it (step 2 must use step 1's path)
- 2 × repo_chain: the line appears in no read_file result of this turn
- 2 × web_fact: wrong or missing answer
- 1 × chat_mid: turn 1: the reply doesn't say where its facts came from (page, repo, file)
- 1 × hermes_compute: reply doesn't carry the computed value
- 1 × hermes_compute: turn 1: the reply doesn't say where its facts came from (page, repo, file)
- 1 × hermes_compute: turn 1: made a plan for a one-lookup request
- 1 × hermes_need: acted before asking: web_search
- 1 × hermes_need: the need question contains a number the request didn't have (an assumed value inside the q
- 1 × hermes_need: didn't ask for the missing input
- 1 × hermes_need: acted before asking: web_search, web_search, fetch_url
- 1 × lookup_then_compute: didn't find both birth years in a result about each person
- 1 × math_pair: turn 1: a Check line doesn't refer to the result it follows: "The problem requires calcula
- 1 × math_pair: turn 1: a Check line doesn't refer to the result it follows: 'The problem asks for the num
- 1 × math_pair: wrong or missing answer
- 1 × messy_multi: turn 1: a done result carries nothing from this step's results or the request: "No version
- 1 × messy_multi: turn 1: a Check line doesn't refer to the result it follows: 'fetch_url gave the Wikipedia
- 1 × messy_multi: the version part is missing or wrong
- 1 × near_miss: turn 1: says it checked / confirmed / found something, but no tool result was seen
- 1 × near_miss: never names the user's word (silently corrected or ignored)
- 1 × near_miss: turn 1: the reply doesn't say where its facts came from (page, repo, file)
- 1 × need_web: turn 2: the reply doesn't say where its facts came from (page, repo, file)
- 1 × personal: key information is missing but the reply doesn't end with a question
- 1 × personal_mid: turn 2: key information is missing but the reply doesn't end with a question
- 1 × personal_tool: turn 1: the answer was written (thinking, query or path) before any tool result contained 
- 1 × recipe_skip: turn 1 call 3 (step): output must start with <think> and close it with </think>
- 1 × recipe_skip: wrong or missing answer
- 1 × recipe_web: wrong or missing answer
- 1 × web_fact_retry: only one lookup (the first result didn't answer it: search again or read a page)
