# Squiggle small-model fine-tune: results

**Verdict: NO-GO (not yet)** for `lfm25`.

| check | pass | value |
| --- | --- | --- |
| trained types, strict mean | no | 36% (bar 50%) |
| held-out types, strict mean | no | 0% (bar 30%) |
| no held-out type at 0% | no | lowest 0% |
| well-formed model calls | yes | 98.7% (bar 95%) |
| episodes that loop or hit the call cap | yes | 3.8% (bar ≤ 5%) |
| plain chat stays plain | yes | 96% (bar 90%) |
| messy within 10 points of clean | yes | clean 19%, messy 26% |
| beats the untouched Gemma 3 270M | no | 36%/0% vs 0%/0% |

## Strict score per task type (right answer and the habit)

| type | habit | untouched-gemma3 | gemma3 | lfm25 | functiongemma |
| --- | --- | --- | --- | --- | --- |
| bare_link | read a bare link | 0% (0%) | 8% (25%) | 83% (100%) | 33% (33%) |
| chat | plain chat stays plain | 0% (0%) | 44% (44%) | 81% (81%) | 81% (81%) |
| chat_after | a task, then plain thanks | 0% (0%) | 0% (0%) | 0% (0%) | 0% (0%) |
| hermes_compute | compute (Hermes requests) | 0% (0%) | 0% (8%) | 33% (33%) | 25% (25%) |
| hermes_need | ask for missing input (Hermes requests) | 0% (0%) | 17% (17%) | 25% (25%) | 0% (0%) |
| math | compute with run_js | 0% (12%) | 12% (12%) | 6% (6%) | 19% (19%) |
| memory_repo | use memory, don't ask | 0% (0%) | 50% (50%) | 100% (100%) | 70% (80%) |
| need_math (held out) | ask for a missing number (held out) | 0% (0%) | 0% (0%) | 0% (0%) | 0% (0%) |
| need_repo | ask which repo | 0% (0%) | 8% (8%) | 50% (58%) | 0% (8%) |
| past_chat | find an earlier chat | 0% (8%) | 0% (8%) | 8% (8%) | 8% (8%) |
| recipe_compare (held out) | use a recipe on web lookups (held out) | 0% (4%) | 0% (22%) | 0% (48%) | 0% (39%) |
| recipe_repo | use a recipe | 0% (0%) | 0% (0%) | 67% (75%) | 17% (33%) |
| refs | follow 'it' to the last repo | 0% (0%) | 0% (8%) | 33% (42%) | 33% (67%) |
| repo_fact | look in the repo | 0% (0%) | 12% (31%) | 50% (62%) | 31% (38%) |
| repo_two | plan a two-part repo task | 0% (0%) | 0% (8%) | 0% (17%) | 0% (17%) |
| repo_where | find a definition | 0% (0%) | 0% (0%) | 6% (19%) | 12% (12%) |
| web_bridge (held out) | plan a two-hop lookup (held out) | 0% (3%) | 0% (3%) | 0% (17%) | 0% (10%) |
| web_compare | plan + look up two things | 0% (50%) | 0% (44%) | 25% (62%) | 0% (31%) |
| web_fact | look it up | 0% (6%) | 0% (6%) | 0% (0%) | 6% (12%) |

(right answer only in brackets)

## Habits

| measure | untouched-gemma3 | gemma3 | lfm25 | functiongemma |
| --- | --- | --- | --- | --- |
| trained types, strict mean | 0% | 10% | 36% | 21% |
| trained types, right answer | 5% | 17% | 43% | 29% |
| held-out types, strict mean | 0% | 0% | 0% | 0% |
| well-formed calls | 0% | 91% | 99% | 95% |
| episodes looping / call-capped | 1% | 6% | 4% | 3% |
| plans multi-step requests | 0% | 16% | 51% | 34% |
| asks (need) when info is missing | 0% | 15% | 30% | 4% |
| plain chat stays plain | 96% | 38% | 96% | 71% |
| done results carry the answer | - | - | 100% | 100% |
| clean requests, strict | 0% | 6% | 19% | 9% |
| messy requests, strict | 0% | 3% | 26% | 16% |
| episodes evaluated | 293 | 293 | 293 | 293 |

## Output length

Generated tokens per model call (thinking + call or reply). Seconds per call at ~15 tokens/s on a phone CPU.

| model | calls | tokens per call | seconds per call |
| --- | --- | --- | --- |
| untouched-gemma3 | 360 | 52 | 3 |
| gemma3 | 1487 | 121 | 8 |
| lfm25 | 2402 | 91 | 6 |
| functiongemma | 1903 | 105 | 7 |

## Sample generations

The first model call of three eval episodes per model, raw (as the harness got it).

**untouched-gemma3**, `chat-0` (chat): 'hmm interesting'

````text
Okay, I've analyzed the information provided. Let's try to figure out what this tool is and how it can be used.
````

**untouched-gemma3**, `web_compare-0` (chat): 'Which is a black-and-white film, Flying Padre or Inside Job?'

````text
The answer is **Flying Padre**.
````

**untouched-gemma3**, `repo_fact-0` (chat): 'What version is commander.js at right now?'

````text
Commander.js is available in the latest stable release (version 15.x) on GitHub.
````

**gemma3**, `chat-0` (chat): 'hmm interesting'

````text
<think>
A casual reply; no tools needed for this task.
</think>
No tools required (only lookups and info gathering).
````

**gemma3**, `web_compare-0` (chat): 'Which is a black-and-white film, Flying Padre or Inside Job?'

````text
<think>
Request: Which movie has no subtitles (black and white)?
Pieces: 1. The name of the only movie with no subtitles.
Know: Only "Flying Parde" exists in the prompt; nothing else is known about it.
Don't know: Whether "Inside Job" was a film or TV show; must look up separately.
Goal: Find which movie has no subtitles to answer the question directly.
Next: Use find to get web_search tools first (since we don't have them yet).
</think>
```tool_call
{"name": "find", "arguments": {"query": "Which is a black-and-white film, Flying Parde or Inside Job"}}
```
````

**gemma3**, `repo_fact-0` (chat): 'What version is commander.js at right now?'

````text
<think>
Request for the current version of Commander.js; nothing to look up yet!
Pieces: 1. The current version number (e.g., "c/m/s" or similar).
Know: Only prompt gives the repo name and no tools looked up.
Don't know: Tools available for cloning GitHub repos, reading package.json, etc.; must look them up.
Goal: Report current version from prompt.
Next: Use find to locate git_clone and read_file tool before using it.
</think>
```tool_call
{"name": "find", "arguments": {"query": "clone a github repo and read a file"}}
```
````

**lfm25**, `chat-0` (chat): 'hmm interesting'

````text
<think>
A casual thank you; nothing to look up.
</think>
Glad that helped! How can I assist you?
````

**lfm25**, `web_compare-0` (chat): 'Which is a black-and-white film, Flying Padre or Inside Job?'

````text
<think>
Request: Which of the two films is a black-and-white movie (Flying Padre or Inside Job)?
Pieces: 1. Character description: Black-and-white movie.
Know: Only the question; no prior context about these movies.
Don't know: Both film titles and character descriptions; must look up separately.
Goal: Identify which film is a black-and-white movie based on its title meaning "premierned" (Flying Padre) or "inside job" (Inside Job).
Next: Use find to locate the web search tool since it's not yet confirmed available.
</think>
```tool_call
{"name": "find", "arguments": {"query": "search the web"}}
```
````

**lfm25**, `repo_fact-0` (chat): 'What version is commander.js at right now?'

````text
<think>
Request: What version is commander.js at right now?
Pieces: 1. The current version of the package named "commander".
Know: Only the repo name "commander" and no tools are available for it.
Don't know: How to get the version (must look up via git log).
Goal: Find the current version from the repo's package.json.
Next: Use find to discover tools for cloning a GitHub repo and reading files.
</think>
```tool_call
{"name": "find", "arguments": {"query": "clone a github repo and read a file"}}
```
````

**functiongemma**, `chat-0` (chat): 'hmm interesting'

````text
<think>
Casual acknowledgment; no tools needed for this fact.
</think>
Interesting! Not much to look up, but thanks you for the casual response. Let me know if you need anything else.
````

**functiongemma**, `web_compare-0` (chat): 'Which is a black-and-white film, Flying Padre or Inside Job?'

````text
<think>
Request: Which is a "black-and-white film"? which is a "flying father of stutter movies" and "Inside job"?
Pieces: 1. The movie with the same name (White/Blue).
Know: Only the question; nothing in the prompt gives this fact.
Don't know: Both films are likely incorrect or have different names.
Goal: Report both film titles as black-and-white, citing sources.
Next: Find reliable web search tools to look up these facts.
</think>
```tool_call
{"name": "find", "arguments": {"query": "search the web"}}
```
````

**functiongemma**, `repo_fact-0` (chat): 'What version is commander.js at right now?'

````text
<think>
Request: What version of Commander.js is at right now.
Pieces: 1. the current version number.
Know: no tools looked up yet; must find package.json for this fact.
Don't know: tools to clone repo and read file, but not yet confirmed available.
Goal: Report the current version of Commander.js.
Next: use find to check if "clone a github repo" is a valid tool before using it.
</think>
```tool_call
{"name": "find", "arguments": {"query": "clone a github repo"}}
```
````


## Notes

- `gemma3` (unsloth/gemma-3-270m-it): trained 3 epochs on 2839 examples in 14 min.
- `lfm25` (LiquidAI/LFM2.5-350M): trained 3 epochs on 2839 examples in 13 min.
- `functiongemma` (unsloth/functiongemma-270m-it): trained 3 epochs on 2839 examples in 14 min.
