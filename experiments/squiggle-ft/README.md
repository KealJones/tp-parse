# squiggle-ft: a small phone model for Squiggle's harness

**Question:** can a tiny model (≤ ~500 MB GGUF, running in wllama 3.8.1 on an iPhone CPU) learn the habits Squiggle's
harness needs: notice what it doesn't know and look it up (checking it found the right thing), plan multi-step work
and finish each step with `done(result)`, use a recipe when the prompt has one, say what's missing with `need`, cope
with messy voice-dictated input, and keep plain chat plain? It doesn't need world knowledge; the harness has tools.

The contract is Squiggle's `docs/harness.md` ("Small-model format", "Step prompt", "What the fine-tune should learn").

## How the data is made (and why it matches the app byte for byte)

Episodes are not rendered by a Python copy of the format. `sq/driver.mjs` runs **Squiggle's own `app/src` modules,
unchanged**, in node: `agent.runTurn` (chat phase → plan → one fresh prompt per step → final reply), `tasks.js`,
`find.js`, `context.js` (smart context), `refs.js`, `recipes.js`, `tools.js` and `engine-wllama.js` with the phone
settings (Gemma 3 270M engine, 4096-token context, smart context, no embeddings). Only the browser edges are swapped
(`sq/hooks.mjs`):

| app module | in node | what's different |
| --- | --- | --- |
| `storage.js` | `sq/stubs/storage.mjs` | the storage repo is an in-memory map (sessions, memory, recipes, /home) |
| `git.js` | `sq/stubs/git.mjs` | node filesystem instead of LightningFS; real clones from GitHub (cached); pushes are refused |
| `github.js` | `sq/stubs/github.mjs` | no sign-in; "repos you gave Squiggle" = the world's list of real public repos |
| `embed.js` | `sq/stubs/embed.mjs` | off, as on phones |
| wllama (CDN) | `sq/stubs/wllama.mjs` | `createChatCompletion` gets exactly what engine-wllama.js sends and asks the episode's model |
| browser APIs | `sq/env.mjs` | `DOMParser` (linkedom, with a browser-like `innerText`), run_js's sandbox (app/sandbox.html's own worker code in a worker thread), `fetch` with a disk cache |

One difference from the live app: the relay's `/api/search` scrapes DuckDuckGo Lite, which blocks servers, so in
episodes it answers from Wikipedia's search API plus DuckDuckGo's official Instant Answer API, in the same
`{answer, results: [{title, url, snippet}]}` shape. The model sees the same result format either way.

Each model call becomes one training example: the messages engine-wllama.js hands to wllama (system prompt with the
plan, step results, recipe, memory…, then the turns, tool results as `Result of <tool>:\n<json>`) and the model's raw
output (`<think>…</think>` then one ```` ```tool_call ```` block, or the reply). The app's chat template (from the GGUF)
renders them; training uses each base model's own template.

### Task families (families.py), all from real data

| family | habit | source |
| --- | --- | --- |
| web_fact | look it up, don't guess | Natural Questions (nq_open), time-sensitive questions dropped |
| web_compare | plan, look up two things, compare | HotpotQA comparison questions |
| math | compute with run_js, not in its head | GSM8K |
| repo_fact / repo_where / repo_two | clone, read, grep, log; plan two-part tasks | facts read out of 18 real public repos |
| need_repo | ask which repo instead of guessing | the same repos; the simulated user answers |
| memory_repo | use memory, don't ask | true facts about Keal's repos (squiggle, tp-parse) |
| past_chat | find an earlier chat | a web_fact answered in one chat, asked about in a new chat |
| recipe_repo | use the recipe saved from the first task | two similar repo tasks in two chats |
| refs | follow "it" to the repo from the last turn | two turns, same chat |
| chat, chat_after | plain chat stays plain | casual openers; a task followed by "thanks" |
| bare_link | a message that is just a link | Wikipedia pages named in HotpotQA |
| hermes_compute, hermes_need | compute; ask for a missing input | requests from interstellarninja/hermes_reasoning_tool_use (see hermes.py) |
| **held out** web_bridge, need_math, recipe_compare | two-hop plan; ask for a missing number; recipe on web tasks | HotpotQA bridge; GSM8K with a number removed; HotpotQA pairs |

About 40% of requests are rewritten as messy voice dictation (fillers, restarts, "no wait" corrections, misheard
words like "get hub"), never inside a name.

**Hermes:** its tools are invented APIs and its tool results invented data, so conversations can't be copied in under
"real data only". It supplies requests plus the reference model's call-or-ask decision: pure computations (→ run_js,
kept only if the reply carries what the sandbox computed) and requests missing an input (→ need, kept only if the
teacher also asks first). The rest of the corpus is not used.

### Teacher episodes (build.py)

A bigger model (Qwen3-4B-Instruct-2507 on vLLM) plays the phone model inside the harness, with real tools. It gets the
exact prompt plus a teacher-only note (backends.TEACHER_NOTE: thinking style, one call per reply, plan/done/need rules)
that never reaches the training data. Episodes are kept only when the family's checker passes **strict** (right
answer end to end and the habit, well-formed calls, no loops, no stuck steps, prompt within the phone's 4096 tokens).

### Training and eval (train.py)

Bases: Gemma 3 270M IT (today's phone model), FunctionGemma 270M IT, LFM2.5-350M (wllama 3.8.1's llama.cpp has the
LFM2 architecture; 379 MB at Q8_0). Full fine-tune, loss only on the model's output. Eval runs fresh episodes (other
questions, five repos never seen in training) plus the three held-out families through the same harness, sampling as
the phone does (temperature 0.7, top-k 64, top-p 0.95, repeat penalty 1.15 over the last 64 tokens, 1024-token replies,
4096-token context), against the untouched Gemma 3 270M.

## What go/no-go means

**GO** means: ship the winner as Squiggle's phone model. All of these must hold for the best fine-tuned model
(`train.BARS`, fixed before the run):
- trained task types (fresh data, unseen repos): strict mean ≥ 50%
- held-out task types: strict mean ≥ 30%, none at 0%
- ≥ 95% of model calls well-formed; ≤ 5% of episodes loop or hit the 30-call cap
- plain chat stays plain ≥ 90%
- messy requests within 10 points of clean ones
- better than the untouched Gemma 3 270M on trained and held-out scores

Anything less is **NO-GO (not yet)**, with the per-family table showing what failed.

## Running it

Locally (node 22, Python 3.11+, a Squiggle checkout):

```
npm ci
export SQUIGGLE_DIR=/path/to/squiggle          # at e9c27ca
python samples.py                              # 20 hand-written episodes through the real harness -> samples/
python selftest.py samples/samples.jsonl --tokenizers unsloth/gemma-3-270m-it,LiquidAI/LFM2.5-350M
python build.py sets --plan train --scale 0.02 # list some episodes (no model)
```

On Hugging Face Jobs (hf/README.md): a job file in `hf/queue/` runs `jobs/boot.py <script>`, which unpacks this folder
and Squiggle at the pinned commit, installs node, and runs `jobs/<script>`.

| job | script | flavor / limit | expected cost | what it does |
| --- | --- | --- | --- | --- |
| `squiggle-ft-smoke` | `jobs/smoke.sh` | l4x1, 70 min | ~$0.60 (cap $0.93) | self-test, ~50 teacher episodes, 1 short epoch on each base, tiny eval, GGUF conversion (no upload) |

## Status

- Built and checked locally: the node harness runs Squiggle's real loop; the 20 samples (`samples/SAMPLES.md`) all
  pass their checkers and the self-test (app parser, gemmaMessages round trip, Gemma 3 / FunctionGemma / LFM2.5
  templates, 4096/1024-token limits).
- Next: smoke job on HF.
