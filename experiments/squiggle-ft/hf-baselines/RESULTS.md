# Squiggle small-model fine-tune: results

## Strict score per task type (right answer and the habit)

| type | habit | untouched-lfm25 | untouched-functiongemma |
| --- | --- | --- | --- |
| bare_link | read a bare link | 0% (0%) | 0% (0%) |
| chat | plain chat stays plain | 0% (0%) | 0% (0%) |
| chat_after | a task, then plain thanks | 0% (12%) | 0% (0%) |
| hermes_compute | compute (Hermes requests) | 0% (0%) | 0% (0%) |
| hermes_need | ask for missing input (Hermes requests) | 0% (0%) | 0% (0%) |
| math | compute with run_js | 0% (31%) | 0% (0%) |
| memory_repo | use memory, don't ask | 0% (0%) | 0% (0%) |
| need_math (held out) | ask for a missing number (held out) | 0% (0%) | 0% (0%) |
| need_repo | ask which repo | 0% (0%) | 0% (0%) |
| past_chat | find an earlier chat | 0% (8%) | 0% (0%) |
| recipe_compare (held out) | use a recipe on web lookups (held out) | 0% (65%) | 0% (22%) |
| recipe_repo | use a recipe | 0% (0%) | 0% (0%) |
| refs | follow 'it' to the last repo | 0% (25%) | 0% (25%) |
| repo_fact | look in the repo | 0% (0%) | 0% (6%) |
| repo_two | plan a two-part repo task | 0% (0%) | 0% (0%) |
| repo_where | find a definition | 0% (0%) | 0% (0%) |
| web_bridge (held out) | plan a two-hop lookup (held out) | 0% (7%) | 0% (0%) |
| web_compare | plan + look up two things | 0% (50%) | 0% (38%) |
| web_fact | look it up | 0% (12%) | 0% (6%) |

(right answer only in brackets)

## Habits

| measure | untouched-lfm25 | untouched-functiongemma |
| --- | --- | --- |
| trained types, strict mean | 0% | 0% |
| trained types, right answer | 9% | 5% |
| held-out types, strict mean | 0% | 0% |
| well-formed calls | 0% | 0% |
| episodes looping / call-capped | 0% | 1% |
| plans multi-step requests | 0% | 0% |
| asks (need) when info is missing | 0% | 0% |
| plain chat stays plain | 88% | 100% |
| done results carry the answer | - | - |
| clean requests, strict | 0% | 0% |
| messy requests, strict | 0% | 0% |
| episodes evaluated | 293 | 293 |

## Output length

Generated tokens per model call (thinking + call or reply). Seconds per call at ~15 tokens/s on a phone CPU.

| model | calls | tokens per call | seconds per call |
| --- | --- | --- | --- |
| untouched-lfm25 | 369 | 96 | 6 |
| untouched-functiongemma | 360 | 74 | 5 |

## Sample generations

The first model call of three eval episodes per model, raw (as the harness got it).

**untouched-lfm25**, `chat-0` (chat): 'hmm interesting'

````text
It looks like today is a Wednesday! If there's anything specific you'd like to explore or if the tool I'm using (perhaps "a planner" or "goal tracking") needs some clarification, just let me know and we can dive in together. What would you like to do next?
````

**untouched-lfm25**, `web_compare-0` (chat): 'Which is a black-and-white film, Flying Padre or Inside Job?'

````text
I don't have access to movie databases or content details like that information. Would you like me to help with something else related to movies, schedules, or other topics I can look up?
````

**untouched-lfm25**, `repo_fact-0` (chat): 'What version is commander.js at right now?'

````text
The provided context does not contain information about the current version of commander.js or any related tool calls and results. Please ensure you have included all necessary documents, such as logs or configuration files. Once I have access to those materials, I will be able to determine what version is currently associated with commander.js using the specified `tool_call`.
````

**untouched-functiongemma**, `chat-0` (chat): 'hmm interesting'

````text
I apologize, but I cannot assist with this request. My current capabilities are limited to assisting Squiggle with planning and finding information using the available tools. I cannot generate or retrieve complex strategic advice or analyses about business strategies like "interesting."
````

**untouched-functiongemma**, `web_compare-0` (chat): 'Which is a black-and-white film, Flying Padre or Inside Job?'

````text
I cannot assist with finding movie trivia about specific films like "Flying Padre" or "Inside Job." My current capabilities are limited to assisting with tool management tasks using the provided tools.
````

**untouched-functiongemma**, `repo_fact-0` (chat): 'What version is commander.js at right now?'

````text
I apologize, but I cannot assist with retrieving current software versions or specifications for different platforms like "Commander.js." My available tools are focused on planning and finding information related to specific applications and services.
````


## Notes

