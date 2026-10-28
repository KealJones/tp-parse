# Squiggle small-model fine-tune: results

**Verdict: NO-GO (not yet)** for `lfm25`.

| check | pass | value |
| --- | --- | --- |
| trained types, strict mean | no | 0% (bar 50%) |
| held-out types, strict mean | no | 0% (bar 30%) |
| no held-out type at 0% | no | lowest 0% |
| well-formed model calls | no | 56.9% (bar 95%) |
| episodes that loop or hit the call cap | yes | 3.3% (bar ≤ 5%) |
| plain chat stays plain | no | 0% (bar 90%) |
| messy within 10 points of clean | yes | clean 0%, messy 0% |
| beats the untouched Gemma 3 270M | no | 0%/0% vs 0%/0% |

## Strict score per task type (right answer and the habit)

| type | habit | untouched-gemma3 | lfm25 |
| --- | --- | --- | --- |
| bare_link | read a bare link | 0% (0%) | 0% (0%) |
| chat | plain chat stays plain | 0% (0%) | 0% (0%) |
| chat_after | a task, then plain thanks | 0% (0%) | 0% (0%) |
| hermes_compute | compute (Hermes requests) | 0% (0%) | 0% (0%) |
| hermes_need | ask for missing input (Hermes requests) | 0% (0%) | 0% (0%) |
| math | compute with run_js | 0% (0%) | 0% (0%) |
| memory_repo | use memory, don't ask | 0% (0%) | 0% (100%) |
| need_math (held out) | ask for a missing number (held out) | 0% (0%) | 0% (0%) |
| need_repo | ask which repo | 0% (0%) | 0% (0%) |
| past_chat | find an earlier chat | 0% (0%) | 0% (0%) |
| recipe_compare (held out) | use a recipe on web lookups (held out) | 0% (0%) | 0% (0%) |
| recipe_repo | use a recipe | 0% (0%) | 0% (0%) |
| refs | follow 'it' to the last repo | 0% (0%) | 0% (0%) |
| repo_fact | look in the repo | 0% (0%) | 0% (0%) |
| repo_two | plan a two-part repo task | 0% (0%) | 0% (0%) |
| repo_where | find a definition | 0% (0%) | 0% (0%) |
| web_bridge (held out) | plan a two-hop lookup (held out) | 0% (0%) | 0% (0%) |
| web_compare | plan + look up two things | 0% (50%) | 0% (100%) |
| web_fact | look it up | 0% (0%) | 0% (0%) |

(right answer only in brackets)

## Habits

| measure | untouched-gemma3 | lfm25 |
| --- | --- | --- |
| trained types, strict mean | 0% | 0% |
| trained types, right answer | 3% | 12% |
| held-out types, strict mean | 0% | 0% |
| well-formed calls | 0% | 57% |
| episodes looping / call-capped | 0% | 3% |
| plans multi-step requests | 0% | 11% |
| asks (need) when info is missing | 0% | 0% |
| plain chat stays plain | 100% | 0% |
| done results carry the answer | - | 100% |
| clean requests, strict | 0% | 0% |
| messy requests, strict | 0% | 0% |
| episodes evaluated | 30 | 30 |

## Output length

Generated tokens per model call (thinking + call or reply). Seconds per call at ~15 tokens/s on a phone CPU.

| model | calls | tokens per call | seconds per call |
| --- | --- | --- | --- |
| untouched-gemma3 | 36 | 60 | 4 |
| lfm25 | 210 | 94 | 6 |

## Sample generations

The first model call of three eval episodes per model, raw (as the harness got it).

**untouched-gemma3**, `chat-0` (chat): 'omg yes'

````text
Okay, I understand the instructions. Let's begin!
````

**untouched-gemma3**, `web_compare-0` (chat): 'Which is a black-and-white film, Flying Padre or Inside Job?'

````text
I am Squiggle and I don't have access to the movie library of today. Therefore, I cannot answer your question about the Black-And-White Film.
````

**untouched-gemma3**, `repo_fact-0` (chat): 'who committed last in jprichardson/node-fs-extra?'

````text
Okay, I'm ready to be Squiggle! Let's start with the information about JPRICHARDSON/NODE-FS-EXTRA.
````

**lfm25**, `chat-0` (chat): 'omg yes'

````text
<
Check: The user said "yes" after the initial confirmation; no prior context about which tool to use.
Next: Use plan to structure steps before finalizing answers.
</think>
```tool_call
{"name": "plan", "arguments": {"goal": "Request confirmed: Yes, answer with details from the source.", "steps": ["Find the correct tools for the task (e.g., grep, read_file")."}}
```
````

**lfm25**, `web_compare-0` (chat): 'Which is a black-and-white film, Flying Padre or Inside Job?'

````text
<
Request: Which of the two films (Black-and-White Film, Flying Padre, Inside Job) is a Black-and-White?
Pieces: 1. The film with "Black-and-White". 2. Its title and source.
Know: No prior context; must confirm if they're referring to specific movies.
Don't know: Which one (Flying Padre or Inside Job) the user meant, so need two steps.
Goal: Find which movie is a Black-and-White film by using plan.
Next: Call plan with "Find" and "Confirm Film Title".
</think>
```tool_call
{"name": "plan", "arguments": {"goal": "Identify which of the two films (Flying Padre or Inside Job) is a Black-and-White movie", "steps": ["Search for 'Black-and-Blue' in film databases"]
```
````

**lfm25**, `repo_fact-0` (chat): 'who committed last in jprichardson/node-fs-extra?'

````text
<think>
Request: Who committed last in the repo "jprichardson/node-fs-extra"?
Pieces: 1. Which commit is from the latest email.
Know: The tool to find commits; need its name or source.
Don't know: The repository path, but the user provided it.
Goal: Identify the last commit message in "jprichardson/node-fs-extra".
Next: Use find to discover tools for locating GitHub repos and their commits.
</think>
```tool_call
{"name": "find", "arguments": {"query": "recent commits"}}
```
````


## Notes

- `lfm25` (LiquidAI/LFM2.5-350M): trained 4 epochs on 243 examples in 2 min.
