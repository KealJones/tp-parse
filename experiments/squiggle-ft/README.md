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
| past_chat | find an earlier chat (or use it when smart context already retrieved it) | a web_fact answered in one chat, asked about in a new chat |
| recipe_repo | use the recipe in the prompt | a recipe the app itself saved (recipes.fromTask) from a gold task on another repo; requests the app's recipes.match offers it for |
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

### Teacher episodes (teacher.py, build.py teach)

An open-weights thinking model, **Qwen3-30B-A3B-Thinking-2507** (FP8, Apache-2.0, on vLLM in a Hugging Face Job),
plays the phone model inside the harness with real tools, one model call at a time. For each call it gets the rules
(the same as TEACHER.md: format, labelled thinking, habits) plus few-shot episodes written by `gold.py`'s templates,
and the phone model's whole prompt rendered with Gemma 3's chat template. Its own reasoning stays private; its visible
answer is the phone model's output (thinking in `<visible_thinking>`, mapped mechanically to `<think>`). Answers that
fail the quality bar (`quality.py`) go back to it with the list of problems; it rewrites them (at most twice), nothing
is edited on our side. Episodes are kept only when the family's checker passes **strict**.

**Quality bar** (`quality.py`, enforced on every call by the checker and `selftest.py`): labelled thinking in order
(new request: Request / Pieces / Know / Don't know / Goal / Plan or Next; start of a step: Step / Know / Next; after a
tool result: Check / Next; final reply: Answer; plain chat: one or two lines), exactly one ```` ```tool_call ```` block
at the end that the app's parser reads, a tool that exists with schema-valid arguments, real tools only after `find`
looked them up, `done` results that carry facts, 2–6 plan steps, replies that cite their sources after web or repo
tools, and a plan that follows the recipe when the prompt has one.

**Provenance.** Only teacher episodes train: every example carries `source: "teacher:<model>"` and train.py drops
anything else. Claude-written text (`samples/`, written before the quality bar existed and kept only as a record; the worked episodes in `TEACHER.md` / `examples/worked.jsonl`) and the
template gold (`examples/gold.jsonl`) are format and checker tests only. (A plan to have Claude agents write episodes
was stopped by Anthropic's safeguards against using Claude outputs to train models; `teach.py` / `TEACHER.md`, the
step-wise CLI built for it, remain as a way to inspect and hand-test episodes.)

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
python gold.py                                 # template gold episodes through the real harness -> examples/gold.jsonl
python selftest.py examples/gold.jsonl examples/worked.jsonl --tokenizers unsloth/gemma-3-270m-it,LiquidAI/LFM2.5-350M
node teach.mjs families                        # the step-wise CLI (TEACHER.md): play the phone model by hand
python build.py sets --plan train --scale 0.02 # list some episodes (no model)
```

On Hugging Face Jobs (hf/README.md): a job file in `hf/queue/` runs `jobs/boot.py <script>`, which unpacks this folder
and Squiggle at the pinned commit, installs node, and runs `jobs/<script>`.

| job | script | flavor / limit | expected cost | what it does |
| --- | --- | --- | --- | --- |
| `squiggle-ft-smoke` | (retired `smoke.sh`) | l4x1, 70 min | $0.07 (done) | failed early: no C compiler for vLLM; the harness and untouched eval ran |
| `squiggle-ft-smoke-2` | (retired `smoke.sh`) | l4x1, 70 min | $0.21 (done) | training, eval and baseline all ran on GPU; the Qwen3-4B-Instruct teacher never wrote `<think>` (0/44 kept); GGUF conversion failed (tokenizer, since fixed) |
| `squiggle-ft-teach-smoke` | `jobs/teach_smoke.sh` | l40sx1, 40 min | $0.60 (done) | 22/40 kept, every web episode failed (find used as web search; search API unreachable), fixed for smoke 2 |
| `squiggle-ft-teach-smoke-2` | `jobs/teach_smoke.sh` | l40sx1, 40 min | $0.73 (done) | 20/40 kept; web search works now (12/18); 7 episodes lost to `done` without a plan (fixed in the per-call hints) |
| `squiggle-ft-train-smoke` | `jobs/train_smoke.sh` | l4x1, 45 min | $0.03 (failed) | out of GPU memory in Gemma 3's first backward pass (262k-vocab logits); fixed with chunked loss + SDPA |
| `squiggle-ft-train-smoke-2` | `jobs/train_smoke.sh` | l4x1, 45 min | $0.08 (done) | all three bases trained and evaluated; export died on a missing git (now a pinned llama.cpp tarball) |
| `squiggle-ft-train-smoke-3` | `jobs/train_smoke.sh` (`BASES=gemma3,lfm25 EPOCHS=4`) | l4x1, 30 min | $0.11 (done) | loss 2.09 → 0.58 (gemma3), 1.96 → 0.42 (lfm25); Q8_0 + wllama 3.8.1 check ran on HF. Found: `copy_tokenizer` copied the base's weights over the trained ones, so every "trained" eval so far was the base (fixed) |
| `squiggle-ft-train-smoke-4` | `jobs/train_smoke.sh` (`BASES=gemma3,lfm25 EPOCHS=4`) | l4x1, 30 min | ~$0.11 (cap $0.40) | the same with the weights fix and llama-simple/Q4_0 built: trained models' well-formed rate, samples, output length |
| `squiggle-ft-teach` | `jobs/teach_smoke.sh` (`PLAN=targets`, `KV_FP8=0`, `CONCURRENCY=96`, `MINUTES=115`, `TAG=teach-v1`) | a100-large, 150 min | $0.19 (failed) | died loading data (datasets-server HTTP 429); the source slices are now committed in `data/sources/` |
| `squiggle-ft-teach-2` | same as `squiggle-ft-teach` | a100-large, 150 min | ~$5.20 (cap $6.25) | the full teacher run on the 830 target episodes (A100: 80 GB, so ~2× the episodes in flight of an L40S) |
| `squiggle-ft-train` | `jobs/train.sh` | l4x1, ≤180 min | ≤ $2.40 | train the three bases, eval, RESULTS.md, export + upload the winner |

Teacher data goes to the private dataset `kealjones/squiggle-ft-data/<tag>/` (not git); the training job downloads it.

## Status

- **Built and checked locally:** the node harness runs Squiggle's real loop; `quality.py` + checkers; `selftest.py`
  (app parser, gemmaMessages round trip, Gemma 3 / FunctionGemma / LFM2.5 templates, 4096/1024-token limits, quality
  bar); the step-wise CLI (`teach.mjs`) tested end to end on 5 episodes; `gold.py`'s 11 template episodes all pass;
  the teacher plumbing (format mapping, rejection and rewrite) with a stand-in model; GGUF export fixed and checked:
  a Gemma 3 270M saved by train.py (it held the base weights, see train-smoke-3; same architecture) converted to Q8_0
  (292 MB), and LFM2.5-350M (379 MB), load and generate in wllama 3.8.1 in headless Chromium.
- **On HF so far:** about $1.83 in finished jobs (see the table); the full teacher run and the second training smoke
  are running.
- **Next:** check the teacher run's keep rate per family, then the training run.
