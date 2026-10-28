# Teacher episodes (squiggle-ft)

Teacher Qwen/Qwen3-30B-A3B-Thinking-2507-FP8 on gpu: 40 of 40 episodes in 15 min (deadline 15.0 min), 103 training examples, 300 generated tokens/s. Teacher stats: {'calls': 233, 'retries': 37, 'failed': 7, 'too_long': 0, 'unfinished': 0, 'gen_tokens': 273048, 'answer_chars': 74859}.

| family | habit | episodes | right answer | kept (strict) | examples |
| --- | --- | --- | --- | --- | --- |
| bare_link | read a bare link | 2 | 2 | 2 (100%) | 6 |
| chat | plain chat stays plain | 2 | 2 | 2 (100%) | 2 |
| chat_after | a task, then plain thanks | 1 | 0 | 0 (0%) | 0 |
| hermes_compute | compute (Hermes requests) | 2 | 1 | 1 (50%) | 3 |
| hermes_need | ask for missing input (Hermes requests) | 2 | 2 | 2 (100%) | 2 |
| math | compute with run_js | 4 | 4 | 3 (75%) | 9 |
| memory_repo | use memory, don't ask | 1 | 0 | 0 (0%) | 0 |
| need_repo | ask which repo | 2 | 1 | 1 (50%) | 5 |
| past_chat | find an earlier chat | 2 | 1 | 0 (0%) | 0 |
| recipe_repo | use a recipe | 2 | 0 | 0 (0%) | 0 |
| refs | follow 'it' to the last repo | 2 | 1 | 1 (50%) | 22 |
| repo_fact | look in the repo | 4 | 2 | 2 (50%) | 12 |
| repo_two | plan a two-part repo task | 2 | 2 | 1 (50%) | 9 |
| repo_where | find a definition | 3 | 1 | 1 (33%) | 5 |
| web_compare | plan + look up two things | 4 | 3 | 2 (50%) | 20 |
| web_fact | look it up | 5 | 2 | 2 (40%) | 8 |
| **all** | | 40 | 24 | 20 (50%) | 103 |

## Why episodes were dropped (top 40)

- 3 × web_fact: wrong or missing answer
- 2 × recipe_repo: no recipe in the second prompt (first task didn't plan, or no match)
- 2 × repo_fact: turn 1: the reply doesn't say where its facts came from (page, repo, file)
- 2 × repo_fact: wrong or missing answer
- 2 × repo_where: turn 1: the reply doesn't say where its facts came from (page, repo, file)
- 2 × repo_where: context full
- 2 × repo_where: wrong or missing answer
- 2 × web_compare: no plan for a multi-step question
- 1 × chat_after: turn 1 call 3 (chat): output must start with <think> and close it with </think>
- 1 × chat_after: turn 1: the reply doesn't say where its facts came from (page, repo, file)
- 1 × chat_after: wrong or missing answer
- 1 × hermes_compute: turn 1 call 3 (chat): output must start with <think> and close it with </think>
- 1 × hermes_compute: reply doesn't carry the computed value
- 1 × math: did the maths in its head
- 1 × memory_repo: turn 1 call 4 (chat): output must start with <think> and close it with </think>
- 1 × memory_repo: turn 1: the reply doesn't say where its facts came from (page, repo, file)
- 1 × memory_repo: wrong or missing answer
- 1 × need_repo: turn 2 call 5 (chat): output must start with <think> and close it with </think>
- 1 × need_repo: turn 2: the reply doesn't say where its facts came from (page, repo, file)
- 1 × need_repo: wrong or missing answer after asking
- 1 × past_chat: didn't search past chats
- 1 × past_chat: turn 1: the reply doesn't say where its facts came from (page, repo, file)
- 1 × past_chat: first chat got it wrong
- 1 × past_chat: didn't recall the earlier answer
- 1 × recipe_repo: turn 2 call 6 (chat): output must start with <think> and close it with </think>
- 1 × recipe_repo: turn 2: the reply doesn't say where its facts came from (page, repo, file)
- 1 × recipe_repo: first: missing part of the answer
- 1 × recipe_repo: first: no plan for a two-part task
- 1 × refs: turn 2 call 3 (chat): output must start with <think> and close it with </think>
- 1 × refs: turn 2: the reply doesn't say where its facts came from (page, repo, file)
- 1 × refs: follow-up wrong
- 1 × repo_fact: turn 1 call 4 (chat): output must start with <think> and close it with </think>
- 1 × repo_two: no plan for a two-part task
- 1 × web_compare: turn 1: the reply doesn't say where its facts came from (page, repo, file)
- 1 × web_compare: wrong or missing answer
- 1 × web_fact: turn 1: the reply doesn't say where its facts came from (page, repo, file)
