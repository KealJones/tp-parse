# Squiggle small-model fine-tune: results

**Verdict: NO-GO (not yet)** for `gemma3`.

| check | pass | value |
| --- | --- | --- |
| trained types, strict mean | no | 0% (bar 50%) |
| held-out types, strict mean | no | 0% (bar 30%) |
| no held-out type at 0% | no | lowest 0% |
| well-formed model calls | no | 86.5% (bar 95%) |
| episodes that loop or hit the call cap | yes | 0.0% (bar ≤ 5%) |
| plain chat stays plain | no | 0% (bar 90%) |
| messy within 10 points of clean | yes | clean 0%, messy 0% |
| beats the untouched Gemma 3 270M | no | 0%/0% vs 0%/0% |

## Strict score per task type (right answer and the habit)

| type | habit | untouched-gemma3 | gemma3 | lfm25 |
| --- | --- | --- | --- | --- |
| bare_link | read a bare link | 0% (0%) | 0% (0%) | 0% (0%) |
| chat | plain chat stays plain | 0% (0%) | 0% (0%) | 0% (0%) |
| chat_after | a task, then plain thanks | 0% (0%) | 0% (0%) | 0% (0%) |
| hermes_compute | compute (Hermes requests) | 0% (0%) | 0% (0%) | 0% (0%) |
| hermes_need | ask for missing input (Hermes requests) | 0% (0%) | 0% (0%) | 0% (0%) |
| math | compute with run_js | 0% (0%) | 0% (0%) | 0% (0%) |
| memory_repo | use memory, don't ask | 0% (0%) | 0% (0%) | 0% (0%) |
| need_math (held out) | ask for a missing number (held out) | 0% (0%) | 0% (0%) | 0% (0%) |
| need_repo | ask which repo | 0% (0%) | 0% (0%) | 0% (0%) |
| past_chat | find an earlier chat | 0% (0%) | 0% (0%) | 0% (0%) |
| recipe_compare (held out) | use a recipe on web lookups (held out) | 0% (50%) | 0% (0%) | 0% (100%) |
| recipe_repo | use a recipe | 0% (0%) | 0% (0%) | 0% (0%) |
| refs | follow 'it' to the last repo | 0% (0%) | 0% (0%) | 0% (0%) |
| repo_fact | look in the repo | 0% (0%) | 0% (0%) | 0% (0%) |
| repo_two | plan a two-part repo task | 0% (0%) | 0% (0%) | 0% (0%) |
| repo_where | find a definition | 0% (0%) | 0% (0%) | 0% (0%) |
| web_bridge (held out) | plan a two-hop lookup (held out) | 0% (0%) | 0% (0%) | 0% (0%) |
| web_compare | plan + look up two things | 0% (50%) | 0% (50%) | 0% (100%) |
| web_fact | look it up | 0% (0%) | 0% (0%) | 0% (0%) |

(right answer only in brackets)

## Habits

| measure | untouched-gemma3 | gemma3 | lfm25 |
| --- | --- | --- | --- |
| trained types, strict mean | 0% | 0% | 0% |
| trained types, right answer | 3% | 3% | 6% |
| held-out types, strict mean | 0% | 0% | 0% |
| well-formed calls | 0% | 87% | 0% |
| episodes looping / call-capped | 3% | 0% | 17% |
| plans multi-step requests | 0% | 56% | 22% |
| asks (need) when info is missing | 0% | 0% | 0% |
| plain chat stays plain | 100% | 0% | 0% |
| done results carry the answer | - | - | - |
| clean requests, strict | 0% | 0% | 0% |
| messy requests, strict | 0% | 0% | 0% |
| episodes evaluated | 30 | 30 | 30 |

## Output length

Generated tokens per model call (thinking + call or reply). Seconds per call at ~15 tokens/s on a phone CPU.

| model | calls | tokens per call | seconds per call |
| --- | --- | --- | --- |
| untouched-gemma3 | 36 | 75 | 5 |
| gemma3 | 193 | 100 | 7 |
| lfm25 | 195 | 108 | 7 |

## Sample generations

The first model call of three eval episodes per model, raw (as the harness got it).

**untouched-gemma3**, `chat-0` (chat): 'omg yes'

````text
Okay, I understand the instructions. Let's begin!
````

**untouched-gemma3**, `web_compare-0` (chat): 'Which is a black-and-white film, Flying Padre or Inside Job?'

````text
Okay, I've got it! The answer to the question is **Flying Padre**.
````

**untouched-gemma3**, `repo_fact-0` (chat): 'who committed last in jprichardson/node-fs-extra?'

````text
Okay, I understand the task. I'm ready to be Squiggle! Let's begin.
````

**gemma3**, `chat-0` (chat): 'omg yes'

````text
<think>
Request: answer "yes" with the correct tool and source. The user's question asks if there are multiple ways to solve this problem (e.g., using a calculator or coding).
Pieces: 1. Answer with the tool name and source; 2. Mention which tools were looked up before.
Know: no tools looked up yet, so plan is needed.
Don't know: tools looked up for calculation vs. programming. Need to find one first.
Goal: answer correctly using "yes" or "no".
Next: list all the tools looked up and cite their sources (using the tool_call block).
</think>
```tool_call
{"name": "find", "arguments": {"query": "list tools for a problem"}}
```
````

**gemma3**, `web_compare-0` (chat): 'Which is a black-and-white film, Flying Padre or Inside Job?'

````text
<think>
Request: Which movie is the Black and White Film (from its title) ?
Pieces: 1. The film's name; 2. Key plot points (best match).
Know: no trailers or info from the movie.
Don't know: trailer, key actors, director/screenplay details.
Goal: Find which one is a black and white film.
Next: look up "The Black and White Film" to see if it exists online.
</think>
```tool_call
{"name": "find", "arguments": {"query": "search for 'Black and White Film' (from movie"): ["The Black and White Film"]}}
```
````

**gemma3**, `repo_fact-0` (chat): 'who committed last in jprichardson/node-fs-extra?'

````text
<think>
Request: Who committed the last line of JPRICHARDSON's Node-FS-Extra package. The repo name "jsrc" doesn't exist; no tools found yet.
Pieces: 1. Which user gave the commit message. 2. The date and time for the commit (from its documentation).
Don't know: User given commit message, tool to get version number; need confirmation from source.
Goal: Find where JPRICHARDSON was committed.
Next: Use find to confirm if a tool like git_clone is available before using it.
</think>
```tool_call
{"name": "find", "arguments": {"query": "git clone"}}
```
````

**lfm25**, `chat-0` (chat): 'omg yes'

````text
Request: The user says "yes" after a long time; they want to know if it's true before finalizing the answer.
Pieces: 1. User said "yes"; need confirmation from data or source.
Know: No prior knowledge about the claim, but asked for certainty.
Don't know: Whether the statement is factual (e.g., yes/no) or requires evidence.
Goal: Provide a verified response with birth date and age.
Next: Use plan to structure the answer correctly before finalizing it.
medskip: Call plan first; then use it to confirm facts via web search.
 namn: "yes confirmation" → call plan for verification.
rodes: User's statement, need for data (birth/death dates/noise).
près: The user asked if they're a grown-up. Need birth date and age before confirming.
goal: Verify the claim with birth date and age from reliable sources.
next: Find web search tools to look up birth dates and ages.
ітет: plan, find; need two steps (verification first) but only one step is done yet.
 namn: "find" → call it for both verification steps.
rodes: User's statement ("yes"), the fact they want (birth date/age).
près: The user wants a verified answer. Need to confirm birth dates and ages from reliable sources before finalizing.
Goal: Provide a correct, verifiable response with birth date and age.
Next: Call plan for two separate steps (verification first) but use it only once.
 namn: "find" → call both tools for the search.
rodes: User's statement ("yes"), need birth dates/ages from web searches.
près: The user wants a verified an
````

**lfm25**, `web_compare-0` (chat): 'Which is a black-and-white film, Flying Padre or Inside Job?'

````text
Request: Which of the two films (Flying Padre and Inside Job) is a black-and-white movie?
Pieces: 1. The color scheme in each film.
Know: No prior knowledge; both are films from their respective cultures with no known color palette.
Don't know: Whether the user wants to know if they're viewing them in black-and-white or not.
Goal: Find which of the two films is a black-and-white movie, citing the source.
Next: Use find to get "black and white film" as a tool before looking it up.
\paragraph{find": "search for 'black and white' using web search tools."
medskip: Call find first; then use it to look up the specific titles from both films.
\footnote{"name": "find", "arguments": {"query": "black and white film"}}
\ref{"name": "find", "arguments": {"query": "Flying Padre or Inside Job"}}
\ref{"name": "find", "arguments": {"query": "inside job movie"}}
\ref{"name": "find", "arguments": {"query": "Flying Padre and inside job films: black-and-white"}}
\ref{"name": "plan", "arguments": {"goal": "Determine which film is a black-and-white movie", "steps": ["Check: Both films have no color palette (no black-and-white)"}}
\ref{"name": "plan", "arguments": {"goal": "Find the correct title for both films"}}
\ref{"name": "find", "arguments": {"query": "Flying Padre and inside job movies"}}
\ref{"name": "plan", "arguments": {"goal": "Answer with the film titles from each movie"}}
\ref{"name": "plan", "arguments": {"goal": "Compare: Flying Padre's black-and-white, Inside Job's color palette"}}

````

**lfm25**, `repo_fact-0` (chat): 'who committed last in jprichardson/node-fs-extra?'

````text
<|img_row_7_col_2|>
Request: Who committed last in the repo "jprichaudson/node-fs-extra"?
Pieces: 1. The user wants to know who has made their latest commit.
Know: No prior context; need to look up GitHub repos and commits.
Don't know: Which repo they mean, or whether it's a tool for finding users.
Goal: Find the person with the most recent commit in "jprichaudson/node-fs-extra".
Next: Call find to get user ID and git_clone tools.
<|reserved_383|>
```tool_call
{"name": "find", "arguments": {"query": "user who made their latest commit"}}
```
````


## Notes

- `gemma3` (unsloth/gemma-3-270m-it): trained 4 epochs on 243 examples in 2 min.
- `lfm25` (LiquidAI/LFM2.5-350M): trained 4 epochs on 243 examples in 2 min.

## Export

`gemma3` → squiggle-small-gemma3-Q8_0.gguf (292 MB), squiggle-small-gemma3-Q4_0.gguf (241 MB) (not uploaded: smoke).

llama.cpp (master) loads the Q8_0 file and generates: yes ('tal time =     522.96 ms /    33 tokens\nllama_perf_context_print:    graphs reused =         30\nllama_perf_context_print:   graph reallocs =          0    /     0        (same size) / (changed size)\n\n~llama_context:        CPU compute buffer size is   2.0267 MiB, matches expectation of   2.0267 MiB\n')

wllama 3.8.1 in Chromium, squiggle-small-gemma3-Q8_0.gguf: {"ok": true, "loadMs": 3532.8000000002794, "genMs": 24892.899999999907, "chunks": 119, "text": "<think>\nRequest: When was the last person on the moon?\nPieces: 1. The last person was on the moon. 2. When they were on the moon.\nKnow: No history; only facts.\nDon't know: Date, location, person.\nGoal: Find the last person on the moon.\nNext: Search the internet for \"moon landing history\" to find the date and location.\n</think>\n```tool_call\n{\"name\": \"find\", \"arguments\": {\"query\": \"moon landing history\"}}\n```", "has_think": true, "has_call": true}

wllama 3.8.1 in Chromium, squiggle-small-gemma3-Q4_0.gguf: {"ok": true, "loadMs": 3161.7000000001863, "genMs": 49875.39999999991, "chunks": 227, "text": "<think>\nRequest: Last time anyone was on the moon, 2026.\nPieces: 1. The date and time. 2. The name and source. 3. The goal.\nKnow: The moon's 2026, no record of the last time.\nDon't: Answer directly with the date and time.\nGoal: Find the last time anyone was on the moon using the tool.\nNeed: The date and time for the moon.\n<think>\nRequest: The last time anyone was on the moon.\nPieces: 1. The date and time. 2. The name and source. 3. The goal.\nKnow: The moon's 2026, no record of the last time
