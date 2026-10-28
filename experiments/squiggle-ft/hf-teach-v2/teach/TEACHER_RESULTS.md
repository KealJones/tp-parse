# Teacher episodes (squiggle-ft)

PARTIAL: 480 of 446 episodes (retries included) after 59 min (3 kept ones wait for the judge, in judge_pending.jsonl.gz).

| family | habit | episodes | right answer | kept (strict) | examples |
| --- | --- | --- | --- | --- | --- |
| chat_mid | plain chat after a task | 20 | 18 | 16 (80%) | 75 |
| hermes_compute | compute with calculate (Hermes requests) | 53 | 17 | 15 (28%) | 46 |
| hermes_need | ask for missing input (Hermes requests) | 25 | 9 | 9 (36%) | 13 |
| lookup_then_compute | two lookups, then calculate | 44 | 0 | 0 (0%) | 0 |
| math_pair | compute, or ask for the missing number | 77 | 43 | 27 (35%) | 89 |
| messy_multi | split a run-on, answer every part | 20 | 0 | 0 (0%) | 0 |
| near_miss | flag a near-miss word, don't autocorrect | 30 | 19 | 9 (30%) | 14 |
| need_web | ask what they mean, then look it up | 25 | 6 | 5 (20%) | 25 |
| personal | warm advice, no tools | 45 | 45 | 34 (76%) | 34 |
| personal_mid | personal advice after a task | 20 | 10 | 8 (40%) | 41 |
| personal_tool | one lookup inside a personal ask | 15 | 10 | 10 (67%) | 38 |
| recipe_skip | use only the recipe steps that fit | 20 | 6 | 6 (30%) | 25 |
| recipe_web | use a recipe on web lookups | 16 | 3 | 3 (19%) | 21 |
| repo_chain | sequential plan (step 2 uses step 1) | 20 | 0 | 0 (0%) | 0 |
| unknown_word | look up a made-up word, don't define it | 30 | 24 | 21 (70%) | 63 |
| web_fact_retry | look again when the first result is wrong | 20 | 4 | 2 (10%) | 8 |
| **all** | | 480 | 214 | 165 (34%) | 492 |

## Why episodes were dropped (top 40)

- 44 × lookup_then_compute: no calculate call for the difference
- 40 × lookup_then_compute: didn't find both birth years in a result about each person
- 39 × lookup_then_compute: error: episode timed out
- 28 × math_pair: error: episode timed out
- 21 × math_pair: didn't ask for the missing number
- 20 × math_pair: no answer after asking
- 20 × messy_multi: the web part is missing or wrong
- 20 × messy_multi: the version part is missing or wrong
- 20 × repo_chain: never read the file that defines it (step 2 must use step 1's path)
- 20 × repo_chain: the reply doesn't quote the line
- 19 × hermes_compute: didn't compute it with run_js
- 19 × messy_multi: error: episode timed out
- 19 × repo_chain: error: episode timed out
- 15 × hermes_compute: error: episode timed out
- 15 × web_fact_retry: turn 1: wrong or missing answer
- 14 × recipe_skip: error: episode timed out
- 14 × recipe_skip: wrong or missing answer
- 14 × recipe_skip: the recipe didn't reach the prompt (no strong match)
- 13 × hermes_need: didn't ask for the missing input
- 13 × math_pair: wrong or missing answer
- 13 × need_web: error: episode timed out
- 13 × need_web: didn't ask what they meant (searched or answered without a subject)
- 13 × need_web: no turn after the clarification
- 13 × recipe_web: wrong or missing answer
- 12 × recipe_web: fewer than two lookups for a two-part question
- 11 × hermes_compute: reply doesn't carry the computed value
- 11 × recipe_web: error: episode timed out
- 10 × math_pair: did the maths in its head (no calculate call)
- 10 × near_miss: never names the user's word (silently corrected or ignored)
- 10 × personal_mid: turn 1: answered without looking it up
- 9 × near_miss: turn 1: the reply doesn't say where its facts came from (page, repo, file)
- 8 × math_pair: the answer was written before calculate returned it
- 8 × personal_mid: error: episode timed out
- 8 × personal_mid: turn 1: no reply
- 7 × web_fact_retry: only one lookup (the first result didn't answer it: search again or read a page)
- 6 × hermes_compute: didn't compute it with calculate
- 6 × hermes_need: acted before asking: web_search
- 6 × near_miss: neither asks nor labels the assumption about the word
- 6 × need_web: turn 2: wrong or missing answer
- 6 × web_fact_retry: the Check after the first result doesn't say what was wrong or missing
