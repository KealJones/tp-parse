# Teacher episodes (squiggle-ft)

Teacher Qwen/Qwen3-30B-A3B-Thinking-2507-FP8 on gpu: 40 of 40 episodes in 13 min (deadline 15.0 min), 140 training examples, 422 generated tokens/s. Teacher stats: {'calls': 272, 'retries': 39, 'failed': 2, 'too_long': 0, 'unfinished': 0, 'gen_tokens': 324227, 'answer_chars': 89064}.

| family | habit | episodes | right answer | kept (strict) | examples |
| --- | --- | --- | --- | --- | --- |
| bare_link | read a bare link | 2 | 2 | 2 (100%) | 6 |
| chat | plain chat stays plain | 2 | 2 | 2 (100%) | 2 |
| chat_after | a task, then plain thanks | 1 | 0 | 0 (0%) | 0 |
| hermes_compute | compute (Hermes requests) | 2 | 2 | 2 (100%) | 7 |
| hermes_need | ask for missing input (Hermes requests) | 2 | 2 | 2 (100%) | 2 |
| math | compute with run_js | 4 | 4 | 4 (100%) | 12 |
| memory_repo | use memory, don't ask | 1 | 1 | 1 (100%) | 11 |
| need_repo | ask which repo | 2 | 2 | 2 (100%) | 27 |
| past_chat | find an earlier chat | 2 | 0 | 0 (0%) | 0 |
| recipe_repo | use a recipe | 2 | 1 | 0 (0%) | 0 |
| refs | follow 'it' to the last repo | 2 | 2 | 1 (50%) | 7 |
| repo_fact | look in the repo | 4 | 2 | 2 (50%) | 20 |
| repo_two | plan a two-part repo task | 2 | 1 | 1 (50%) | 12 |
| repo_where | find a definition | 3 | 3 | 3 (100%) | 34 |
| web_compare | plan + look up two things | 4 | 2 | 0 (0%) | 0 |
| web_fact | look it up | 5 | 1 | 0 (0%) | 0 |
| **all** | | 40 | 27 | 22 (55%) | 140 |

## Why episodes were dropped (top 40)

- 4 × web_fact: wrong or missing answer
- 4 × web_fact: answered without looking it up
- 4 × web_fact: asked the user instead of looking it up
- 3 × web_compare: fewer than two lookups for a two-part question
- 3 × web_compare: no plan for a multi-step question
- 2 × past_chat: first chat got it wrong
- 2 × past_chat: didn't recall the earlier answer
- 2 × recipe_repo: no recipe in the second prompt (first task didn't plan, or no match)
- 2 × recipe_repo: first: no plan for a two-part task
- 2 × repo_fact: turn 1: the reply doesn't say where its facts came from (page, repo, file)
- 2 × repo_fact: wrong or missing answer
- 2 × web_compare: wrong or missing answer
- 1 × chat_after: turn 1: the reply doesn't say where its facts came from (page, repo, file)
- 1 × chat_after: wrong or missing answer
- 1 × recipe_repo: second: no plan for a two-part task
- 1 × recipe_repo: first: missing part of the answer
- 1 × refs: turn 1 call 4 (chat): output must start with <think> and close it with </think>
- 1 × refs: turn 1: the reply doesn't say where its facts came from (page, repo, file)
- 1 × refs: first answer wrong
- 1 × repo_fact: context full
- 1 × repo_fact: turn 1 call 4 (chat): output must start with <think> and close it with </think>
- 1 × repo_two: missing part of the answer
- 1 × web_compare: looped
- 1 × web_fact: turn 1: the reply doesn't say where its facts came from (page, repo, file)
