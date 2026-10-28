# Squiggle small-model fine-tune: results

**Verdict: NO-GO (not yet)** for `lfm25`.

| check | pass | value |
| --- | --- | --- |
| trained types, strict mean | no | 15% (bar 50%) |
| held-out types, strict mean | no | 13% (bar 30%) |
| no held-out type at 0% | no | lowest 0% |
| well-formed model calls | yes | 97.8% (bar 95%) |
| episodes that loop or hit the call cap | yes | 1.8% (bar ≤ 5%) |
| plain chat stays plain | no | 83% (bar 90%) |
| messy within 10 points of clean | yes | clean 15%, messy 8% |
| beats `untouched-lfm25` (strict, trained/held-out) | yes | 15%/13% vs 0%/0% |
| right answers at least `untouched-lfm25`'s (trained/held-out) | yes | 30%/25% vs 8%/17% |

**Against `v1`: not better on every check.**

| check | pass | value |
| --- | --- | --- |
| trained types, strict mean | no | 15% (bar 50%) |
| held-out types, strict mean | no | 13% (bar 30%) |
| no held-out type at 0% | no | lowest 0% |
| well-formed model calls | yes | 97.8% (bar 95%) |
| episodes that loop or hit the call cap | yes | 1.8% (bar ≤ 5%) |
| plain chat stays plain | no | 83% (bar 90%) |
| messy within 10 points of clean | yes | clean 15%, messy 8% |
| beats `v1` (strict, trained/held-out) | yes | 15%/13% vs 14%/7% |
| right answers at least `v1`'s (trained/held-out) | yes | 30%/25% vs 27%/21% |

## Strict score per task type (right answer and the habit)

| type | habit | untouched-lfm25 | v1 | lfm25 |
| --- | --- | --- | --- | --- |
| bare_link | read a bare link | 0% (0%) | 50% (75%) | 33% (67%) |
| chat | plain chat stays plain | 0% (0%) | 81% (81%) | 88% (88%) |
| chat_after | a task, then plain thanks | 0% (12%) | 0% (0%) | 0% (0%) |
| chat_mid | plain chat after a task | 0% (0%) | 30% (50%) | 20% (20%) |
| hermes_compute | compute with calculate (Hermes requests) | 0% (0%) | 8% (17%) | 8% (8%) |
| hermes_need | ask for missing input (Hermes requests) | 0% (0%) | 42% (42%) | 75% (75%) |
| lookup_then_compute | two lookups, then calculate | 0% (0%) | 0% (0%) | 0% (0%) |
| math | compute with calculate | 0% (31%) | 0% (6%) | 0% (6%) |
| math_pair | compute, or ask for the missing number | 0% (17%) | 0% (0%) | 0% (0%) |
| memory_repo | use memory, don't ask | 0% (0%) | 30% (60%) | 40% (40%) |
| messy_multi | split a run-on, answer every part | 0% (0%) | 10% (10%) | 0% (0%) |
| near_miss | flag a near-miss word, don't autocorrect | 0% (20%) | 0% (0%) | 0% (30%) |
| need_math (held out) | ask for a missing number (held out) | 0% (0%) | 0% (0%) | 0% (0%) |
| need_repo | ask which repo | 0% (0%) | 33% (42%) | 0% (25%) |
| need_schedule (held out) | ask for the day/time (held out) | 0% (58%) | 33% (42%) | 58% (92%) |
| need_web | ask what they mean, then look it up | 0% (0%) | 0% (0%) | 8% (8%) |
| past_chat | find an earlier chat | 0% (0%) | 0% (8%) | 0% (0%) |
| personal | warm advice, no tools | 0% (80%) | 0% (5%) | 70% (70%) |
| personal_mid | personal advice after a task | 0% (0%) | 0% (50%) | 25% (75%) |
| recipe_compare (held out) | use a recipe on web lookups (held out) | 0% (22%) | 0% (44%) | 0% (22%) |
| recipe_repo | use a recipe | 0% (0%) | 33% (67%) | 25% (58%) |
| recipe_skip | use only the recipe steps that fit | 0% (0%) | 0% (40%) | 0% (40%) |
| recipe_web | use a recipe on web lookups | 0% (0%) | 0% (0%) | 0% (67%) |
| refs | follow 'it' to the last repo | 0% (0%) | 17% (50%) | 8% (33%) |
| repo_chain | sequential plan (step 2 uses step 1) | 0% (0%) | 0% (0%) | 0% (0%) |
| repo_fact | look in the repo | 0% (0%) | 31% (56%) | 12% (31%) |
| repo_two | plan a two-part repo task | 0% (0%) | 8% (33%) | 0% (33%) |
| repo_where | find a definition | 0% (0%) | 12% (19%) | 0% (12%) |
| unknown_action (held out) | a made-up word as a task (held out) | 0% (0%) | 0% (0%) | 6% (6%) |
| unknown_word | look up a made-up word, don't define it | 0% (0%) | 0% (0%) | 0% (0%) |
| web_bridge (held out) | plan a two-hop lookup (held out) | 0% (3%) | 0% (17%) | 0% (3%) |
| web_compare | plan + look up two things | 0% (44%) | 6% (25%) | 6% (44%) |
| web_fact | look it up | 0% (12%) | 6% (12%) | 12% (12%) |

(right answer only in brackets)

## Habits

| measure | untouched-lfm25 | v1 | lfm25 |
| --- | --- | --- | --- |
| trained types, strict mean | 0% | 14% | 15% |
| trained types, right answer | 8% | 27% | 30% |
| held-out types, strict mean | 0% | 7% | 13% |
| held-out types, right answer | 17% | 21% | 25% |
| well-formed calls | 0% | 98% | 98% |
| episodes looping / call-capped | 0% | 6% | 2% |
| plans multi-step requests | 0% | 52% | 41% |
| asks (need) when info is missing | 0% | 33% | 35% |
| plain chat stays plain | 88% | 88% | 83% |
| done results carry the answer | - | 100% | 100% |
| clean requests, strict | 0% | 10% | 15% |
| messy requests, strict | 0% | 10% | 8% |
| arithmetic through run_js | 0% | 71% | 9% |
| episodes evaluated | 443 | 443 | 443 |

## Output length

Generated tokens per model call (thinking + call or reply). Seconds per call at ~15 tokens/s on a phone CPU.

| model | calls | tokens per call | seconds per call |
| --- | --- | --- | --- |
| untouched-lfm25 | 532 | 107 | 7 |
| v1 | 3943 | 89 | 6 |
| lfm25 | 2048 | 99 | 7 |

## Sample generations

The first model call of three eval episodes per model, raw (as the harness got it).

**untouched-lfm25**, `chat-0` (chat): 'sup squiggle whats good'

````text
Sup Squiggle, today's the day! What's good for you? I'm ready to help with any queries or plans you might have—whether it's brainstorming ideas, organizing tasks, or just having a chat about anything that comes up. Just let me know how I can assist!
````

**untouched-lfm25**, `web_compare-0` (chat): 'Which is a black-and-white film, Flying Padre or Inside Job?'

````text
The tools provided are not relevant to answering the question about which movie has a black-and-white version of "Flying Padre." I cannot access external databases, reviews, or information directly through these systems. You may want to check movie catalogs like Wikipedia, IMDb, or streaming platforms for details on both films' versions. Let me know if you'd help with something else!
````

**untouched-lfm25**, `repo_fact-0` (chat): 'What version is commander.js at right now?'

````text
The current command version for Commander.js is **3.4.9**.

Would you like me to look up any details about this version or assist with something else today? (Note: I don't have real-time access to system information, so I can't confirm if Commander.js has a specific release date.)
````

**v1**, `chat-0` (chat): 'sup squiggle whats good'

````text
<think>
Request: What's the current opinion on "good" (typo "Squiggle" → "Glad").
Pieces: 1. The person or group who says "good".
Know: User corrected to "glad" after asking for a response; no prior context about Glad.
Don't know: Which user is correct, and what's the default answer (e.g., they mean Elvis/Glad).
Goal: Get the correct person from the user before looking up anything.
Next: Use need to ask which user is right.
</think>
```tool_call
{"name": "need", "arguments": {"what": "Which of you are asking about 'good' (Squiggle)?"}}
```
````

**v1**, `web_compare-0` (chat): 'Which is a black-and-white film, Flying Padre or Inside Job?'

````text
<think>
Request: Which of the two films is a black-and-white movie?
Pieces: 1. Whether "Flying Padre" and "Inside Job" are both black-and-white.
Know: Only the question; no prior context on these films.
Don't know: Both film titles; guessing would be wrong.
Goal: Determine which film is a black-and-white movie, given they're two distinct options.
Next: Use find to get web search tools for checking film genres.
</think>
```tool_call
{"name": "find", "arguments": {"query": "search the web"}}
```
````

**v1**, `repo_fact-0` (chat): 'What version is commander.js at right now?'

````text
<think>
Request: What version is the Commander.js file (repo name "commander") at current?
Pieces: 1. The version number of the Commander.js repo.
Know: User said "commander.js" but no repo name; only they know which one it's in.
Don't know: Which repo does commander.js belong to (e.g., owner/repo).
Goal: Find the current version of the Command.js repo.
Next: Use find to search for tools that can clone a GitHub repo and read files.
</think>
```tool_call
{"name": "find", "arguments": {"query": "clone a github repo and read a file"}}
```
````

**lfm25**, `chat-0` (chat): 'sup squiggle whats good'

````text
<think>
Request: What's "good" for someone who says they're "succinct".
Pieces: 1. A positive word or phrase to describe the succinctness of their words.
Know: The user said "succinct"; no prior context on its meaning (only the question).
Don't know: Whether "succinct" is a real term; it's not standard English.
Goal: Clarify what they mean by "succinct".
Next: Use need to ask for clarification since we don't know if the word exists or has a specific meaning.
</think>
```tool_call
{"name": "need", "arguments": {"what": "What does 'succinct' mean?"}}
```
````

**lfm25**, `web_compare-0` (chat): 'Which is a black-and-white film, Flying Padre or Inside Job?'

````text
<think>
Request: Which of the two films (Black-and-White vs. Inside Job) is a black-and-white movie.
Pieces: 1. Black-and-white feature film title. 2. Color version title.
Know: Only the question; no prior context on both titles.
Don't know: Both film identities; guessing would be wrong.
Goal: Identify which one is black-and-white (only the film name).
Next: Two separate lookups needed, so plan with two steps.
</think>
```tool_call
{"name": "plan", "arguments": {"goal": "Identify whether Flying Padre or Inside Job is a black-and-white movie", "steps": ["Find the title of the first film (Black-and-White)"], ["Find the title of the second film (Inside Job)"]}}
```
````

**lfm25**, `repo_fact-0` (chat): 'What version is commander.js at right now?'

````text
<think>
Request: What version of commander.js is the current one?
Pieces: 1. The specific version number.
Know: The repo name "commander.js" (from user's message).
Don't know: The actual version; it must be looked up from package.json or GitHub repos.
Goal: Get the version for commander.js using find.
Next: Call find to discover tools that can read file and get version info.
</think>
```tool_call
{"name": "find", "arguments": {"query": "read a text document and find its version"}}
```
````


## Notes

- `lfm25` (LiquidAI/LFM2.5-350M): lr 2e-05, up to 3 epochs on 1660 examples in 7 min; dev loss by epoch [0.6405, 0.5803, 0.5906], kept epoch 2.

## Export

`lfm25` → squiggle-small-lfm25-Q8_0.gguf (379 MB), squiggle-small-lfm25-Q4_0.gguf (219 MB), uploaded to the private repo `kealjones/squiggle-small`.

llama.cpp (master) loads the Q8_0 file and generates: yes ('tal time =     282.37 ms /    19 tokens\nllama_perf_context_print:    graphs reused =         16\nllama_perf_context_print:   graph reallocs =          0    /     0        (same size) / (changed size)\n\n~llama_context:        CPU compute buffer size is   0.5403 MiB, matches expectation of   0.5403 MiB\n')

chat template, GGUF vs the HF template training used: identical

wllama 3.8.1 in Chromium, squiggle-small-lfm25-Q8_0.gguf: {"ok": true, "loadMs": 3696.7000000029802, "genMs": 37644.09999999404, "chunks": 25, "text": "\n```tool_call\n{\"name\": \"find\", \"arguments\": {\"query\": \"search the web\"}}\n```", "reasoning": "\nRequest: When was the last time anyone was on the moon?\nPieces: 1. The year of the last moon landing.\nKnow: Only the question; no prior context.\nDon't know: The year; guessing would be wrong.\nGoal: Find the year of the last human moon landing.\nNext: Use find to look up the web search tool.\n", "deltaKeys": ["role", "content", "reasoning_content"], "has_think": false, "has_call": true}

wllama 3.8.1 in Chromium, squiggle-small-lfm25-Q4_0.gguf: {"ok": true, "loadMs": 3045.9000000059605, "genMs": 55747.29999999702, "chunks": 25, "text": "\n```tool_call\n{\"name\": \"find\", \"arguments\": {\"query\": \"search the web\"}}\n```", "reasoning": "\nRequest: When was the last time anyone was on the moon?\nPieces: 1. The year when humans last set foot on the moon.\nKnow: The prompt states \"last time anyone was on the moon\" as a factual statement.\nDon't know: The source of the information; it's a factual statement from the prompt.\nGoal: Find the year of the last human moon landing.\nNext: Use find to locate the web search tool.\n", "delta

Transformers weights: `kealjones/squiggle-small/hf`.
