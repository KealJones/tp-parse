# Teacher episodes (squiggle-ft)

Teacher Qwen/Qwen3-4B-Instruct-2507 on gpu: 44 of 44 episodes in 4 min (deadline 10.0 min), 0 training examples. Teacher stats: {'calls': 197, 'retries': 591, 'too_long': 0, 'out_tokens': 64072}.

| family | habit | episodes | right answer | kept (strict) | examples |
| --- | --- | --- | --- | --- | --- |
| bare_link | read a bare link | 2 | 0 | 0 (0%) | 0 |
| chat | plain chat stays plain | 2 | 0 | 0 (0%) | 0 |
| chat_after | a task, then plain thanks | 1 | 0 | 0 (0%) | 0 |
| hermes_compute | compute (Hermes requests) | 3 | 0 | 0 (0%) | 0 |
| hermes_need | ask for missing input (Hermes requests) | 2 | 1 | 0 (0%) | 0 |
| math | compute with run_js | 4 | 4 | 0 (0%) | 0 |
| memory_repo | use memory, don't ask | 2 | 1 | 0 (0%) | 0 |
| need_repo | ask which repo | 2 | 0 | 0 (0%) | 0 |
| past_chat | find an earlier chat | 2 | 1 | 0 (0%) | 0 |
| recipe_repo | use a recipe | 2 | 0 | 0 (0%) | 0 |
| refs | follow 'it' to the last repo | 2 | 0 | 0 (0%) | 0 |
| repo_fact | look in the repo | 4 | 1 | 0 (0%) | 0 |
| repo_two | plan a two-part repo task | 2 | 0 | 0 (0%) | 0 |
| repo_where | find a definition | 4 | 1 | 0 (0%) | 0 |
| web_compare | plan + look up two things | 4 | 3 | 0 (0%) | 0 |
| web_fact | look it up | 6 | 3 | 0 (0%) | 0 |
| **all** | | 44 | 15 | 0 (0%) | 0 |

## Why episodes were dropped (top 40)

- 11 × web_fact: no <think>
- 8 × repo_fact: no <think>
- 8 × repo_where: no <think>
- 8 × web_compare: no <think>
- 7 × math: no <think>
- 5 × hermes_compute: no <think>
- 5 × web_fact: text before the tool call
- 4 × bare_link: no <think>
- 4 × memory_repo: no <think>
- 4 × need_repo: no <think>
- 4 × past_chat: no <think>
- 4 × recipe_repo: no <think>
- 4 × refs: no <think>
- 4 × repo_fact: text before the tool call
- 4 × repo_two: no <think>
- 4 × repo_where: text before the tool call
- 4 × web_compare: text before the tool call
- 3 × math: text before the tool call
- 2 × bare_link: text before the tool call
- 2 × chat: no <think>
- 2 × chat_after: no <think>
- 2 × hermes_compute: text before the tool call
- 2 × hermes_need: no <think>
- 2 × memory_repo: text before the tool call
- 2 × need_repo: text before the tool call
- 2 × recipe_repo: text before the tool call
- 2 × refs: text before the tool call
- 2 × repo_two: text before the tool call
- 1 × chat_after: wrong or missing answer
- 1 × hermes_compute: didn't compute it
- 1 × hermes_need: didn't ask for the missing input
- 1 × hermes_need: text before the tool call
- 1 × math: did the maths in its head
- 1 × past_chat: didn't search past chats
- 1 × past_chat: text before the tool call
- 1 × web_fact: answered without looking it up
