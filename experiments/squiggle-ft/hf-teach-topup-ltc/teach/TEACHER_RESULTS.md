# Teacher episodes (squiggle-ft)

Teacher Qwen/Qwen3-30B-A3B-Thinking-2507-FP8 on gpu: 33 of 30 episodes in 11 min (deadline 3.0 min), 21 training examples, 629 generated tokens/s. Teacher stats: {'calls': 256, 'retries': 41, 'failed': 0, 'too_long': 0, 'unfinished': 0, 'gen_tokens': 428101, 'answer_chars': 86779, 'judge_calls': 8}.

| family | habit | episodes | right answer | kept (strict) | examples |
| --- | --- | --- | --- | --- | --- |
| lookup_then_compute | two lookups, then calculate | 30 | 10 | 0 (0%) | 0 |
| recipe_web | use a recipe on web lookups | 3 | 3 | 3 (100%) | 21 |
| **all** | | 33 | 13 | 3 (9%) | 21 |

## Why episodes were dropped (top 40)

- 14 × lookup_then_compute: no calculate call for the difference
- 11 × lookup_then_compute: the reply doesn't give the calculated difference
- 6 × lookup_then_compute: didn't find both birth years in a result about each person
- 5 × lookup_then_compute: the calculate expression doesn't use both looked-up birth years
- 5 × lookup_then_compute: judge: the reply picks 'neither', not the gold
- 3 × lookup_then_compute: no plan for a two-lookup task
- 1 × lookup_then_compute: turn 1: a Check line doesn't refer to the result it follows: 'fetch_url gave Pelle Almqvis
- 1 × lookup_then_compute: turn 1: the reply states a fact no prompt or tool result of the turn has: number 16
- 1 × lookup_then_compute: turn 1: stated a computed number (35) that no calculate result gave
- 1 × lookup_then_compute: turn 1: the reply states a fact no prompt or tool result of the turn has: number 35
- 1 × lookup_then_compute: turn 1: stated a computed number (9) that no calculate result gave
- 1 × lookup_then_compute: turn 1: stated a computed number (6) that no calculate result gave
- 1 × lookup_then_compute: turn 1: the reply states a fact no prompt or tool result of the turn has: number 6
- 1 × lookup_then_compute: turn 1: stated a computed number (19) that no calculate result gave
- 1 × lookup_then_compute: turn 1: the reply states a fact no prompt or tool result of the turn has: number 19
- 1 × lookup_then_compute: turn 1: the reply doesn't say where its facts came from (page, repo, file)
- 1 × lookup_then_compute: turn 1: stated a computed number (13) that no calculate result gave
- 1 × lookup_then_compute: turn 1: the reply states a fact no prompt or tool result of the turn has: number 13
- 1 × lookup_then_compute: turn 1: stated a computed number (21) that no calculate result gave
- 1 × lookup_then_compute: turn 1: the reply states a fact no prompt or tool result of the turn has: number 21
- 1 × lookup_then_compute: turn 1: a Check line doesn't refer to the result it follows: 'The two birth years are 1881
- 1 × lookup_then_compute: turn 1: a Check line doesn't refer to the result it follows: 'Dan Bejar born 1972 (from Wi
- 1 × lookup_then_compute: turn 1: a Check line doesn't refer to the result it follows: 'Chanda Rubin born 1976 (from
- 1 × lookup_then_compute: turn 1: the reply states a fact no prompt or tool result of the turn has: number 72
- 1 × lookup_then_compute: turn 1: the reply states a fact no prompt or tool result of the turn has: number 769
- 1 × lookup_then_compute: turn 1: a Check line doesn't refer to the result it follows: 'Michael McKean born 1947, Si
- 1 × lookup_then_compute: turn 1: the reply states a fact no prompt or tool result of the turn has: number 67
- 1 × lookup_then_compute: turn 1: a Check line doesn't refer to the result it follows: 'Birth years from step result
- 1 × lookup_then_compute: turn 1: a Check line doesn't refer to the result it follows: 'Bertalan Farkas: "born Augus
- 1 × lookup_then_compute: turn 1: a Check line doesn't refer to the result it follows: 'Step 1 says Herschell Gordon
- 1 × lookup_then_compute: turn 1: a Check line doesn't refer to the result it follows: 'Step 3 needs the difference 
