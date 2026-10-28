# Teacher episodes (squiggle-ft)

Teacher Qwen/Qwen3-30B-A3B-Thinking-2507-FP8 on gpu: 830 of 830 episodes in 78 min (deadline 115.0 min), 2839 training examples, 1029 generated tokens/s. Teacher stats: {'calls': 4248, 'retries': 401, 'failed': 4, 'too_long': 2, 'unfinished': 0, 'gen_tokens': 4819055, 'answer_chars': 1466302}.

| family | habit | episodes | right answer | kept (strict) | examples |
| --- | --- | --- | --- | --- | --- |
| bare_link | read a bare link | 35 | 31 | 31 (89%) | 95 |
| chat | plain chat stays plain | 50 | 50 | 50 (100%) | 50 |
| chat_after | a task, then plain thanks | 30 | 11 | 11 (37%) | 52 |
| hermes_compute | compute (Hermes requests) | 40 | 27 | 26 (65%) | 87 |
| hermes_need | ask for missing input (Hermes requests) | 40 | 23 | 23 (57%) | 25 |
| math | compute with run_js | 70 | 65 | 58 (83%) | 174 |
| memory_repo | use memory, don't ask | 35 | 34 | 34 (97%) | 160 |
| need_repo | ask which repo | 50 | 45 | 45 (90%) | 263 |
| past_chat | find an earlier chat | 40 | 16 | 14 (35%) | 85 |
| recipe_repo | use a recipe | 40 | 39 | 29 (72%) | 264 |
| refs | follow 'it' to the last repo | 40 | 38 | 38 (95%) | 275 |
| repo_fact | look in the repo | 80 | 63 | 54 (68%) | 294 |
| repo_two | plan a two-part repo task | 50 | 38 | 19 (38%) | 204 |
| repo_where | find a definition | 70 | 52 | 51 (73%) | 297 |
| web_compare | plan + look up two things | 70 | 46 | 36 (51%) | 324 |
| web_fact | look it up | 90 | 48 | 46 (51%) | 190 |
| **all** | | 830 | 626 | 565 (68%) | 2839 |

## Why episodes were dropped (top 40)

- 42 × web_fact: wrong or missing answer
- 29 × repo_two: no plan for a two-part task
- 23 × web_compare: wrong or missing answer
- 22 × past_chat: first chat got it wrong
- 22 × past_chat: didn't recall the earlier answer
- 19 × chat_after: wrong or missing answer
- 19 × repo_fact: answered without looking at the repo
- 17 × repo_fact: wrong or missing answer
- 17 × repo_where: wrong or missing answer
- 16 × web_compare: no plan for a multi-step question
- 14 × hermes_need: didn't ask for the missing input
- 12 × repo_two: missing part of the answer
- 11 × past_chat: didn't search past chats (and the prompt didn't already have the answer)
- 11 × recipe_repo: the plan doesn't follow the recipe
- 11 × recipe_repo: no plan for a two-part task
- 8 × hermes_compute: reply doesn't carry the computed value
- 8 × math: did the maths in its head
- 8 × web_compare: fewer than two lookups for a two-part question
- 7 × web_fact: answered without looking it up
- 7 × web_fact: asked the user instead of looking it up
- 5 × hermes_compute: didn't compute it
- 5 × math: wrong or missing answer
- 5 × need_repo: wrong or missing answer after asking
- 5 × repo_where: answered without looking at the repo
- 5 × repo_where: turn 1: the reply doesn't say where its facts came from (page, repo, file)
- 4 × bare_link: didn't read the link
- 4 × hermes_need: acted before asking: web_search
- 4 × repo_fact: turn 1: the reply doesn't say where its facts came from (page, repo, file)
- 3 × hermes_need: turn 1: the reply doesn't say where its facts came from (page, repo, file)
- 3 × hermes_need: acted before asking: web_search, fetch_url
- 3 × need_repo: turn 2: the reply doesn't say where its facts came from (page, repo, file)
- 3 × repo_where: context full
- 3 × web_compare: turn 1: the reply doesn't say where its facts came from (page, repo, file)
- 2 × chat_after: turn 1: the reply doesn't say where its facts came from (page, repo, file)
- 2 × chat_after: answered without looking it up
- 2 × hermes_need: acted before asking: run_js
- 2 × hermes_need: acted before asking: run_js, run_js
- 2 × past_chat: turn 1: the reply doesn't say where its facts came from (page, repo, file)
- 2 × past_chat: error: episode timed out
- 2 × past_chat: second chat never ran
