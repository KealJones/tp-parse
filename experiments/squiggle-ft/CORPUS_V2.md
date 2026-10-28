# squiggle-ft corpus v2: design for review

**Status: design, with part of the code built (§0). Nothing has been launched or spent since the review.** v1 is described in
README.md, and its numbers come from `hf-train/RESULTS.md`: 293 eval episodes per model, untouched Gemma 3 270M plus
three fine-tuned bases. The goal of v2 is **generalization**. Each habit should appear across many domains and
phrasings, so the phone model learns the habit and not a template. Whole habit × domain combinations are held out to
check that.

Ground rules carried over from v1:
- Training text is written only by the open-weights teacher (Qwen3-30B-A3B-Thinking-2507) inside Squiggle's real
  harness. Claude, including this design and its reviewer, writes rules, families, checkers and data selection, never
  training text.
- Requests come from real datasets where one exists, and facts come from real tool results.
- Every call must pass `quality.py`, and every episode must pass its family checker on the **strict** setting.

## 0. What the code does now (after AUDIT_V1 and REVIEW_V2_FABLE)

This section describes the code at the commit that carries it. The design sections below are the plan; where they
disagree with this section, this section is what runs.

**Harness pin.**
- `jobs/boot.py` pins Squiggle main ab248b4, which has calculate (d9cbfea+) and typo-tolerant recipe matching.
- `tool_specs.json` is re-exported from that commit. It adds `calculate` and run_js's new description, and is
  byte-identical to the review patch's copy.
- Re-rendering every kept teach-v1 episode on both pins with its stored outputs:
  - **481 of 565 render identically** apart from live-data noise. Live web results and pages drift; the same pin
    replayed twice differs on 117 episodes, all from live data or the simulated user's random wording.
  - **The 84 that change are all math and hermes_compute.** find now also returns calculate.
  - The system prompt (LITE_SYSTEM) is unchanged.
  - None of the 404 episodes the v2 checker keeps are affected.

**Checker** (`quality.py`, `families.py`, `hermes.py`; from `review_v2_checker.patch`, tested by `checker_tests.py`, 77
cases):

| rule | what it does |
|---|---|
| grounding | The gold answer must appear in a **non-error** tool result of the turn. It must not appear in the model's own text (thinking, query, path) before a result has it (`answer_grounded`, `guessed_early`). Applies to web_fact, repo_*, refs, need_repo, memory_repo, past_chat and chat_after. `refs` and `need_repo` need a lookup in every answering turn. |
| checks refer to results | Every Check line must carry a word or quote from the result it follows (`check_refers_to_result`). |
| no narrated checks | "I checked/confirmed/found" needs a tool result (`narrated_without_tools`). |
| citations | The cited page, file, repo or tool must be one used in this turn (`cited_source_called`). `SOURCE` no longer accepts "from memory", "from <any word>" or "and/or". |
| computed numbers | A number in a reply or done that sits in arithmetic wording must equal a `calculate` result (`computed_numbers_grounded`). run_js in a math family fails. calculate expressions must be plain math. |
| plans | Steps that write or review the reply, or "find the tools", are rejected (`META_STEP`). So are narrating dones and a plan in a one-lookup family. |
| answers | Hedged, negated and "either A or B" replies fail. For "A or B" questions, `picked()` requires the gold to be the first candidate named. License names match as whole words, and paths as whole paths. |
| need | A need question may not contain a guessed candidate or a number the user didn't give. |
| eval split | Chat openers, need_repo/refs/repo_where templates and memory aliases have disjoint train and eval sets. |

On teach-v1 this keeps **404 of 830** episodes (v1 checker: 565):

| family | kept |
|---|---|
| chat | 50/50 |
| need_repo | 41/50 |
| repo_fact | 45/80 |
| repo_where | 40/70 |
| web_fact | 36/90 |
| memory_repo | 30/35 |
| bare_link | 29/35 |
| web_compare | 27/70 |
| recipe_repo | 26/40 |
| hermes_need | 22/40 |
| refs | 21/40 |
| repo_two | 16/50 |
| past_chat | 12/40 |
| chat_after | 9/30 |
| math | 0/70 |
| hermes_compute | 0/40 |

math and hermes_compute are 0 by design: they used run_js, and will be regenerated with calculate.

**Judge** (`teacher.judge`, `build.judge_options`). Inside the teach job, after the run, the loaded Qwen3-30B reads
each kept "A or B" episode whose reply names both candidates and answers with one letter. The families are
web_compare, recipe_compare, lookup_then_compute and recipe_web. A pick that isn't the gold drops the episode. On
teach-v1, 17 of 27 kept web_compare episodes would go to the judge. Nothing the grounding rules decide mechanically is
judged.

**Teacher** (`teacher.py`):
- The literal list of "good find queries" is gone. Queries are described instead: 3–6 own words naming the kind of
  thing.
- Habit 7 is calculate. Check quotes the answering words.
- The answer may never appear in a query or the thinking before a result has shown it.
- Empty or error results mean try again or say so. Follow-up turns look again, and the model cites only this turn.
- Need questions carry no candidate.
- The plan describes the task, not the reply.
- Few-shots:
  - gold-chat-0 (whose reply leaked into v1) and gold-web_fact-ff (answer in the query) are dropped.
  - Plain chat and the web lookup now come from kept teach-v1 teacher episodes (`examples/teacher_fewshot.jsonl`:
    chat-40, web_fact-15). No Claude-written replacement.
  - The remaining few-shots are gold.py templates: web_compare, need_repo, recipe_repo, unknown_word and personal.

**Training data** (`train.prepare`, `leak.py`):
- **Leak filter:** an example is dropped if its output shares an 8-word run with gold.jsonl, worked.jsonl,
  samples.jsonl or TEACHER.md, unless that run also appears in its own prompt (copied real data). On re-checked v1
  this drops 201 of 1,956 examples, mostly chat thinking copied from gold.
- **Within an episode:** repeated identical find calls are dropped, and an episode keeps at most 10 examples.
- **Reuse cap:** v1 repo-heavy families (repo_fact, repo_where, repo_two, recipe_repo, refs, need_repo, memory_repo)
  are capped at 25 episodes each, round-robin over repos.
- **Weights:** each example gets weight 1/√n, where n counts examples with the same (kind, tool, arguments). "search
  the web" (63 copies) weighs 0.13 each.
- **Result on v1:** 1,487 examples from 324 episodes.

**Sim.** Each episode's "today" is shifted by a random day within ±2 years (`date_shift`, seeded by episode id). The
frozen v1 eval set keeps the real date. Rate limits use the real clock.

**Training** (`train.py`):
- 5% of episodes are held out as dev. Dev loss is computed every epoch, and the weights of the best epoch are kept.
- Per-base learning rate: lfm25 2e-5, gemma3 4e-5.
- Each step's loss is divided by that step's weighted target tokens, not per micro-batch. Example weights apply per
  token.
- Every trained base is also evaluated untouched. The verdict compares the best model with **its own untouched base**
  on strict scores, and on right-answer rates (trained and held-out) too.
- The eval has no deadline.
- `metrics()` adds held-out right answers and the run_js misuse rate.
- A CPU code-path test covers the dev split, best-epoch keep, weights and normalisation.

**Families: all built for the trimmed plan** (makers + checkers; `build.V2_PLAN` = 815 attempted, `SMOKE_V2_PLAN` =
3 per family):
- web_fact_retry, need_web, math_pair, lookup_then_compute, repo_chain, messy_multi
- recipe_web, recipe_skip, near_miss, chat_mid, personal_mid, personal_tool
- held out: need_schedule, recipe_compute

Only user-side text was written: request templates, with eval-only templates for each family. The data is real:
- NQ, HotpotQA, GSM8K and repo files
- teach-v1's own searches for web_fact_retry (`data/sources/web_retry.json`)
- hand-picked near-misses (`make_nearmiss.py` → `data/sources/near_miss.json`)
  - one letter off a real term, with no exact match on the open web
  - git/code terms are eval-only

**Tests:**
- `checker_tests.py`: 98 cases, 77 from the review and 21 negative cases for the new families.
- `harness_tests.py`: scripted positive cases through the real harness. They're kept for repo_chain, recipe_skip and
  near_miss. recipe_web's recipe reaches the prompt.

**Squiggle finding.** recipes.match only offers a recipe (score ≥ 0.6) when the request's first five content words
overlap the recipe. With two-word names, "Who was born first, A or B?" scores 0.4, and so does "what's the latest
commit of X?" against the version-and-commit recipe. So in the real app, these recipes never reach the prompt for
such phrasings. recipe_web and recipe_skip therefore use phrasings that start with "find" (all 40 sampled score ≥ 0.6
in the app's own matchSync) and carry no dictation noise. That's a Squiggle matching limitation to look at
separately.

**Chat template.** `template_check.py` compares the HF chat template with what `convert_hf_to_gguf.py` writes.
- selftest runs it for every `--tokenizers` base.
- export runs it against the produced GGUF.
- Gemma 3, LFM2.5 and FunctionGemma are byte-identical, and a converted LFM2.5 GGUF matches too.

**v1 eval set.** The review's train/eval template split means the 293-episode v1 eval can't be rebuilt exactly any
more: 105 episodes in template families now differ. v1's numbers stand on their stored results, and v2's eval set will
be frozen when it is first built.

## 1. v1 failures and their causes (from the eval)

Best model: **LFM2.5-350M**.
- Trained types: strict 36% (bar 50%). Held-out types: 0% (bar 30%).
- Well-formed calls: 99%. Plain chat: 96%.
- Messy requests 26% vs clean 19%. Average 91 tokens per call.
- Strongest families: memory_repo 100%, bare_link 83%, recipe_repo 67%, need_repo 50%, repo_fact 50%.

| failure | what the eval shows | cause |
|---|---|---|
| **web_fact 0%** (lfm25; the other models are 0–6%) | 16 of 16 failures say "wrong or missing answer". The usual call sequence, find → web_search → fetch_url → reply, is right. The answers are not. Example: "who drives the number 95 car in nascar" → *"Vince Bell (from the Texas license plate Wikipedia page)"*. The model read an unrelated page and answered from it. Others planned a one-fact question or asked the user. | **Nothing in training made the model check the page.** v1 required the reply to cite a source, but nothing tied the answer to the page text. Even teacher answers often say *"The fetch_url result confirms…"* without quoting (sample B below), so the student learned the form of a citation without the check behind it. The teacher's own web_fact accuracy was only 51%, so there were just 46 kept examples. |
| **0% on every held-out type** | need_math 0/30, web_bridge 0/30, recipe_compare 0/23. Each one also fails on habit, not only on the answer. | Each held-out type needed a habit **that training never showed outside one narrow template**. Held-out was defined per family, so a whole habit was missing rather than a combination. |
| **need_math: never asks** | 29/30 runs `find → run_js → reply` on a problem with a number removed, and makes up the missing value. Example: *"The final value of all Maria's shares is $32.00 (calculated via JavaScript)"* (how many shares she bought was removed). | Training showed asking only for **which repo** (need_repo, 45 kept) and Hermes API inputs (23 kept). There were 58 math episodes, and every one of them was complete, so "word problem → run_js" was learned unconditionally. There was **no contrastive pair** (the same problem with and without a needed number). |
| **web_bridge: no two-hop plan** | 26/30 "no plan for a multi-step question". 21/30 do a single find → web_search (→ fetch) → reply, and often rewrite the question into one hop. Example: Lollipop Chainsaw → "Who played Lollipop Chainsaw in the Teen Titans spinoff". | Every trained plan was **parallel** (look up A, look up B, compare). No trained family had a **sequential** dependency, where step 2's query comes from step 1's result. |
| **recipe_compare: rarely gets a recipe** | 22 of 23 fail with "no recipe in the second prompt". | That family measures the harness as much as the model. A recipe exists only if chat 1 finishes a plan with `done` on every step and the app saves it. Even then, `recipes.match` needs a word-overlap score of at least 0.6 (STRONG) against the saved recipe. Two comparison questions share only frame words ("Who was born first…"), so they rarely match. The 0% is mostly not a model failure. *To verify in v2:* log whether chat 1 saved a recipe and what the match score was. |
| **gemma3: plain chat 38%** (lfm25 96%, functiongemma 71%) | 9/16 failures call tools on chat ("night!" → Request/Pieces… → find). Thinking reads the chat as a task: *"Request: They want to know about 'the night'…"*. | The training mix was 50 chat + 11 chat_after against about 500 task episodes, so the full-label "Request:" template dominated. Gemma 3 also got the least out of training overall (trained strict 10%). It needs more plain turns spread through multi-turn sessions, not a separate pile. |

**Untouched baselines** (`hf-baselines/RESULTS_COMBINED.md`, same 293 episodes; every base as released, with no
embedding changes):
- All three untouched bases score 0% strict and 0% well-formed.
- Fine-tuning moved lfm25's trained-strict score from 0% to 36% and its plans from 0% to 51%.
- **But on raw right-answer rates, training made some things worse:**
  - math: untouched lfm25 31% → tuned 6%. The tuned model routes every word problem through run_js and gets the
    JavaScript wrong. This backs Keal's calculate rule (§2h).
  - web_fact: 12% → 0%.
  - recipe_compare: 65% → 48%. The untouched model answers well-known comparisons from memory, without the habit.
- So v2's "worth it" bar compares against the untouched base on right-answer rates too, not only on strict scores.

Other lessons from `experiments/gemma-traces/RESULTS.md` (Gemma 4 E2B/E4B thinking on messy prompts) that v2 must
build in:
1. **Plan the task, not the reply.** Gemma's lists are "Analyze → Draft the response → Self-correct". A plan step
   must be an action that produces a fact or a change (find, read, fetch, run, clone). Steps like "write the answer",
   "draft", "review tone" or "self-correct" are rejected.
2. **Never narrate a check that didn't happen.** Gemma wrote *"(A quick check confirms 'quasimorphize' is not a
   standard term)"* with no tool call. Phrases like "checked / confirmed / searched / looked up / verified / I found"
   may appear only if a matching tool result is in the prompt.
3. **Near-miss words must be flagged, not autocorrected.** "zymbolic" was silently read as "symbolic" 6/6 times, and
   the guess became fact in the answer. v1's unknown_word family only uses obviously invented words, so v2 adds
   near-misses (§2, `near_miss`).
4. Keep the request split ("three distinct requests: 1… 2… 3…") and the constraint extraction. Drop tool-by-tool
   elimination: the personal-request habit is to think about the person, not the tool list.

## 2. Families for v2

**Habits** (the thing learned) × **domains** (where it happens) × **surfaces** (how it's said). Surfaces:
- clean
- messy voice (fillers, stutters, slang, "no wait" corrections, misheard words)
- terse ("v + last commit chalk")
- run-on multi-part
- mid-session follow-up (the request comes after 1–2 earlier turns)

Every family draws from at least 2 surfaces. Templated requests get at least 12 templates per family, and 3 of
them are reserved for eval only.

Counts are **attempted** teacher episodes. The keep rate is expected to run 55–70%, as in v1.

### 2a. Look it up, then verify (H1)

| family | n | source | habit | checker (strict) | held out |
|---|---|---|---|---|---|
| web_fact (changed) | 120 | NQ-open (timeless questions only) | find → web_search → fetch_url. Quote the page sentence that answers in Check, then reply from that quote. | Answer right (gold). **Grounded** (§3): the Check before the reply quotes a span that appears verbatim in a tool result of this turn, and the reply's answer appears in that span. Cites the page. No narrated checks. | the PopQA eval source (§5) |
| web_fact_retry (new) | 40 | NQ questions whose first search result is the wrong page (picked by replaying v1 searches) | Notice the page is the wrong entity (Check: "this page is about the Texas license plate, not NASCAR #95") and search again or fetch the right title. | As web_fact, plus at least 2 lookups, plus a Check that rejects the first result. | – |
| bare_link | 25 | HotpotQA page titles | Read the link and summarize it. | As v1, plus grounded. | – |
| repo_fact / repo_where | 60 / 50 | 18 train repos (eval: 5 unseen repos) | Clone, read or grep, and quote the line. | As v1, plus the quoted line or field must appear in the read_file/grep result. | unseen repos |

### 2b. Plan multi-step work, parallel and sequential (H2)

| family | n | source | habit | checker | held out |
|---|---|---|---|---|---|
| web_compare | 70 | HotpotQA comparison | Parallel plan: one step per entity, then compare. | As v1, plus grounded step results. | – |
| repo_two | 40 | train repos | Parallel plan within one repo. | As v1. | – |
| **repo_chain** (new) | 50 | train repos: dependencies from package.json / pyproject (repofacts.mjs already extracts them) | **Sequential plan.** Step 1 reads which dependency or file, and step 2 uses that result: "what license does chalk's first dependency use?", "who last committed to the file that defines `parse` in X?". | A plan with ≥2 steps. Step 2's tool arguments contain a value that first appeared in step 1's done result. Answer right. | **web_bridge** (sequential × web) stays held out, so we measure transfer of sequential planning from repo to web. |
| **lookup_then_compute** (new) | 40 | HotpotQA comparison pairs with dates or numbers ("how many years apart were A and B born?") | Sequential: two lookups, then find → calculate on the two values. | Plan; both values grounded; the calculate expression uses both numbers; answer equals the calculate result. | – |
| messy_multi (new) | 40 | combinations of the families above in one run-on message ("whats chalks version and also who was born first X or Y") | Split into pieces in the user's order. One plan covering every part; no part dropped after the first tool call (the Gemma miss). | Every part answered (each sub-gold). The plan covers each part. | 3 of 12 joiner templates are eval-only |
| plan rule (all families) | – | – | Plan steps are task actions. | `quality.validate_call(plan)`: rejects steps matching `^(write|draft|compose|review|summari[sz]e the (answer|reply)|respond|self-correct|format)`. A one-fact request with a plan fails ("plan when ≥2 separate lookups or actions"). | – |

### 2c. Ask for what's missing, don't invent it (H3)

| family | n | source | habit | checker | held out |
|---|---|---|---|---|---|
| need_repo | 35 | train repos | "my repo" → ask which. | As v1. | – |
| **math_pair** (new; replaces most of math) | 60 pairs (120 episodes) | GSM8K train: each problem **complete** and with one needed number removed (v1's need_math generator) | Complete: find → calculate, then answer. Incomplete: notice which quantity is missing and ask with need, never assume it. | Complete: answer = gold, and every computed number comes from calculate. Incomplete: need is asked before any calculate, the question names the missing quantity, and the answer after the user replies = gold. | – |
| hermes_need / hermes_compute | 40 / 40 | Hermes requests (as v1) | Ask for a missing API input / compute. | As v1. | – |
| **need_web** (new) | 30 | NQ questions with the subject replaced by a pronoun or a vague reference ("when did his first album come out", "how tall is that bridge"), with no earlier turn naming it | Ask who or what they mean. Don't pick a famous one. | need before any web_search, and no guessed entity in the question. | – |
| **held out: need_math** | eval only | GSM8K test with a number removed | – | – | ask × math on **test** problems, with **3 removal patterns not used in training** (rate, count, unit price) |
| **held out: need_schedule** | eval only | "move my 3pm" style asks with no day or calendar (templates) | – | – | ask × scheduling (a new domain) |

Note on math_pair: holding out ask × math (as v1 did) while training only complete math teaches the opposite habit.
In v2 the math *pairs* are trained, and generalization is measured on test-set problems with unseen removal patterns
and on a whole new domain (scheduling).

### 2d. Use a recipe (H4)

| family | n | source | habit | checker | held out |
|---|---|---|---|---|---|
| recipe_repo | 30 | the app's own saved recipes (gold_recipes.json) | The plan follows the recipe. | As v1. | – |
| **recipe_web** (new) | 30 | Recipes the app saves from **teacher** web_compare runs that were kept (`recipes.fromTask`), then offered on another comparison of the same shape, with the request phrased so `recipes.match` offers it | The plan follows the recipe and adapts the entities. | Recipe in the prompt. The plan follows it (Jaccard ≥ 0.3). Answer right. | – |
| **recipe_skip** (new) | 20 | A recipe for X offered on a request that only looks similar (e.g. recipe "version + latest commit", request "who wrote the latest commit") | Use only the steps that fit: "skip what's already answered / not asked". | The plan has no step for the part that wasn't asked. | – |
| **held out: recipe_compute** | eval only | a recipe from lookup_then_compute, offered on a new pair | – | – | recipe × compute |

The v1 recipe_compare family is replaced in eval by recipe_compute. Its episodes **start with the recipe in memory**,
so they measure the model's use of the recipe and not the harness's matching. A separate **harness test** (no model)
checks recipe saving and matching on 20 scripted pairs and reports the match rate. That number belongs to Squiggle,
not to the fine-tune.

### 2e. Unknown and near-miss words (H5)

| family | n | source | habit | checker | held out |
|---|---|---|---|---|---|
| unknown_word (built) | 60 | 32 invented train words (`data/sources/unknown_words.json`), 8 work + 8 personal templates | Flag it in Request / Don't know. find "search the web" → web_search for the word. Check: nothing explains it. Then need, or a reply that says it isn't a known word, gives a guess only if labelled, and asks. | Already built (families.py): the word is searched; no meaning is stated as fact in the reply, the need question or done; it says the word is unknown; it asks. | unknown_action (word as a task), eval words |
| **near_miss** (new) | 50 | Real words from the request domains (git, npm, cooking, school…), with one or two letters edited so the result has **no search hits** (same check as make_words.py). Examples: "zymbolic merge", "rebaze my branch", "a gluten-free cassarole". The edit lands on the **key term**, not on filler words. | Notice that the key term isn't a real word, say so, and offer the nearest real word **as a question or a labelled assumption** ("Did you mean a *symbolic* merge? If so, …"). Never silently swap it in. | The reply or need names the user's spelling (quoted or verbatim) and either asks or labels the assumption ("if you mean", "assuming"). It fails if the corrected word is used with the misspelling never mentioned, or if the misspelling is defined as real. | near-miss × git/code (the Gemma failure) is **eval-only**; training uses near-misses in everyday and non-git tech domains |
| dictation slips (no family; rule) | – | messy() slips on everyday words ("verison", "lastest", "n", "u") | These stay silently corrected. They are not the key term, and quality.py doesn't require flagging them. | – | – |

The boundary between near_miss and dictation slips: a slip changes an everyday word whose meaning is obvious and
isn't the subject of the request. A near-miss sits on the **term the request is about**, so a wrong correction would
change the answer. Families mark the key term in `gold`, so the checker knows which one it is.

### 2f. Plain chat and personal (H6)

| family | n | source | habit | checker | held out |
|---|---|---|---|---|---|
| chat | 50 | casual openers (v1 list) | 1–2 thinking lines, a short reply, no tools. | As v1. | – |
| **chat_mid** (new; replaces chat_after) | 50 | a plain-chat turn inserted **after** a kept task from another family in the same session ("lol ok", "night!", "ugh mondays") | Back to plain mode right after tool use. | The chat turn: no tools, 1–2 lines, ≤300 chars. The earlier turns must also pass their own checker. | – |
| personal (built) | 70 | 75 oasst2 / Dolly-15k requests (train split) | Request / Need, no tools, warm, under 200 words, one question when key info is missing (marked by hand). | Already built. | eval split (24 requests) |
| **personal_mid** (new) | 30 | A personal request after a task turn ("thanks. ugh my boss is gonna kill me about this report") | Switch to personal mode mid-session. | personal checker on that turn. | – |
| **held out: personal_tool** | eval only | personal requests that need one real fact ("my mom loves Agatha Christie, which of her books came out first?") | – | – | personal × lookup: one find/web_search is right here, and plain advice without the fact is wrong |

### 2g. Memory, past chats, references (H8, unchanged)

memory_repo 30, past_chat 40 (the checker counts an answer that smart context already retrieved), refs 40. These are
v1 families. Their v1 kept episodes are reused (§4).

## 2h. Computation goes through `calculate`, never the model and never run_js (Keal)

The `calculate` tool is final on Squiggle main (commit d9cbfea and later; code in `app/src/calc.js` and
`app/src/tools.js`).
- **Signature:** `calculate({expression: string})`; `expression` is required.
- **Returns:** `{expression, result: number}` (rounded to 12 significant digits) or `{expression, error: "plain words"}`.
- **Accepts:** `+ - * / ^`, parentheses, percentages ("15% of 240", postfix % = /100), and `sqrt`, `round(x, digits)`,
  `min`, `max`, `abs`, `floor`, `ceil`, `pow`, `log`, `ln`, `exp`. Also `$ € £`, thousands commas (not inside function
  calls), `x × ÷ **`, and "of" as multiply.
- **find:** money, totals, percentages, conversions and "how much is" route to calculate (intent boost 6).
- **run_js's description** now says "for code, data processing, or checking logic, not for plain math (use calculate)".
- **The sim uses Squiggle main's real `tools.js`, `find.js` and `calc.js`.** `jobs/boot.py` moves its Squiggle pin
  from e9c27ca to a main commit at or after d9cbfea, `tool_specs.json` is re-exported from that commit, and
  quality.py's schema check picks calculate up from there. `sq/hooks.mjs` needs no change: calc.js is pure and runs in
  node as-is.

Writing JavaScript is too error-prone for a 350M model. So in v2:
- **Every computation goes find → calculate.** That covers math_pair, hermes_compute, need_math (after the user
  answers), lookup_then_compute, comparisons that need a difference or ratio (web_compare "how many years apart"),
  and any unknown_word or personal edge case that involves arithmetic (a budget split, an age gap).
- The teacher rule and its find query become: "anything to compute (arithmetic, percentages, differences, dates as
  numbers) goes through calculate with one expression, never in your head and never run_js". The good find query is
  "calculate a math expression".
- **run_js stays only for real code or data tasks**: run this snippet, parse this JSON, sort this list, test a regex.
  v2 has no family that teaches run_js for arithmetic. v1 math and hermes_compute episodes that used run_js are **not
  reused**; they are regenerated with calculate (counted in §4).
- **New checker rule, `computed_numbers_grounded()`, applied to every family:**
  1. A number in a reply or a `done` result counts as **computed** if it isn't copied from the prompt or a tool
     result (page, file, user message) and it appears in a sentence with arithmetic wording (total, sum, altogether,
     difference, apart, more/less than, times, percent, %, average, per, left, remaining, each) or next to an
     operator.
  2. Every computed number must equal (after formatting: commas, currency, trailing zeros) a `calculate` result in
     the same turn. For real code tasks only, a `run_js` output also counts.
  3. Otherwise the episode fails: "stated a computed number that no calculate result gave".
  4. This also catches arithmetic hidden in a reply ("so that's 12 years apart") after two lookups.
- **calculate errors:** if calculate returns `{"error"}`, the next call fixes the expression and tries again, or says
  it couldn't compute. It never states a number.
- **Quality bar:** `calculate` comes from the re-exported `tool_specs.json`. Its `expression` must be a string with no
  code (`=`, `;`, `=>`, `function`, `console.log` are rejected). Words other than the allowed function names, "of" and
  "x" are rejected. Units belong in the reply, not in the expression.
- **Eval:** two new measurements. The *computed-number grounded rate* across all families, and the *run_js misuse
  rate* (run_js used for plain arithmetic). The v1 models get scored on these as a baseline; they use run_js, so the
  table shows them as "computes via run_js".
- **Before any teacher run:**
  - Re-pin, then re-run selftest, gold.py and the scripted checker cases on the new Squiggle commit.
  - The new pin also changes find's ranking and the LITE system prompt, if they changed upstream. v1's reused
    episodes were made under e9c27ca, so they are re-rendered with the new prompts where the harness can replay
    them, or kept only if their prompts are unchanged. That gets checked when the pin moves.
- **Not launched:** waiting for the v1 corpus/checker audit and the Fable review.

## 3. Web accuracy: verify before replying

> **As built (§0):** the teacher rule below (quote the answering words) is in teacher.py. The checker doesn't
> implement the quote-span test. It uses the review's rules instead:
> - the gold appears in a non-error result of the turn, and nowhere in the model's own text before that
> - every Check carries a word or quote from its result
> - citations name a tool used this turn
> - no narrated checks
>
> The quote-span version would be a further tightening, to add if teach-v2 shows ungrounded answers slipping
> through.

**Teacher rule (added to teacher.py RULES, habit 1):**
- After fetch_url, the Check line must **quote the exact sentence or infobox field from the page** that answers the
  question, in double quotes. Example: `Check: the "Born" field says "22 May 1859".`
- The Check must also say whether the page is about the right entity (name, year, type).
- The reply may only state what the quote says. If no sentence on the page answers it, the next move is another
  search or fetch, not a reply.
- Per-call hint, after a fetch_url result: "Quote the sentence that answers, or say the page doesn't."

**Checker (new, `families.grounded()`, used by every web and repo family):**
1. Take the last Check line before the reply (or before each `done`).
2. Pull its double-quoted spans.
3. At least one span must appear verbatim in a tool result of the same turn. Whitespace and quotes are normalized,
   and the `untrusted` wrapper is stripped.
4. The answer tokens of the reply or done result (gold-independent: every capitalized phrase, number and date)
   must be a subset of the tokens in that span.
5. If either test fails, the reason is "unverified claim".

This catches:
- the "Texas license plate" answer: the quote is from the page, but the answer isn't in it
- "the fetch_url result confirms…" with no quote
- answers taken from search snippets about another entity

**Narrated checks** (`quality.narrated_check`, applied to every call): thinking or reply text matching
`\b(i )?(checked|confirmed|verified|searched|looked (it )?up|found|according to)\b` fails unless the prompt has a
result from a matching tool. The mapping is: searched → web_search/search_history; looked up → any lookup tool;
found/confirmed/verified → any tool result in this turn. This also covers Gemma's "a quick check confirms".

**Expected effect:**
- The teacher keep rate on web drops a little; the 51% wrong-answer rate gets filtered rather than learned.
- Kept web examples all show quote-then-answer, which a small model can copy mechanically.
- Teacher accuracy should rise as well, because the rewrite feedback says exactly what was unverified.

## 4. Size, mix and cost

This is the plan in code: `build.V2_PLAN`, 1,015 new episodes attempted. On top come the reused teach-v1 episodes
after `train.prepare`: 324 episodes, 1,487 examples. With the stricter checker the keep rate is expected at 45–60%;
web families sit at the low end.

| habit | family (attempted) | built? |
|---|---|---|
| look it up, verify | web_fact 140, web_fact_retry 40, web_compare 60 | web_fact, web_compare yes; retry no |
| ask for what's missing | need_web 50, hermes_need 40, math_pair 120 (60 problems × complete/incomplete) | hermes_need yes |
| compute via calculate | hermes_compute 40, lookup_then_compute 40 | hermes_compute yes |
| plan | repo_chain 40, messy_multi 40 | no |
| recipes | recipe_web 40, recipe_skip 40 | no |
| words | unknown_word 60, near_miss 50 | unknown_word yes |
| chat and personal | personal 70, personal_mid 40, personal_tool 15, chat_mid 50, chat 40 | personal, chat yes |

Every cell has at least 40 attempted, except personal_tool at 15. It is trained on purpose in a small amount (one fact
type) and held out on another (review D5, Q4).

| | episodes | expected kept | examples |
|---|---|---|---|
| reused teach-v1 (re-checked, leak-filtered, repo families capped at 25) | 0 new | 324 | 1,487 |
| new (V2_PLAN) | 1,015 | about 500 | about 2,300 |
| **total** | | **about 820** | **about 3,800** |

The mix by habit (kept): H1 lookup + verify about 25%, H2 plan about 20%, H3 ask about 15%, H4 recipe about 7%,
H5 unknown/near-miss about 10%, H6 chat/personal about 15%, H8 memory/refs about 8%. That is about 15% plain or
personal, versus 11% in v1, and it is spread through sessions.

**Expected HF cost** (rates from v1: a100-large $2.50/h, about $0.43 per 100 teacher episodes including the share
of model loading; l4x1 $0.80/h):

| job | flavor | time | cost |
|---|---|---|---|
| teacher smoke (40 episodes across the new families, read the keep rate) | a100-large or l40sx1 | about 15 min | about $0.60 |
| teach-v2 (1,015 episodes) | a100-large | about 95 min + 8 min loading | **about $4.30** (cap $5.00) |
| train-v2: lfm25 + gemma3 (dev split, best epoch), each also evaluated untouched; no eval deadline | l4x1 | about 100 min | **about $1.35** (cap $1.80) |
| export of the winner | l4x1 | about 5 min | about $0.07 |
| **total** | | | **about $6.30** (caps $7.50) |

About $7.4 has been spent, so this lands at about $13.7 of the $15 cap. It is above Keal's "under $5 per experiment".
A trimmed plan comes in at about $5.30:
- drop the web_compare re-run (60) and the new chat (40)
- web_fact 140 → 100
- math_pair 120 → 80

That is about 815 episodes, teacher about $3.50. The pooled habits keep at least 40 attempted per cell except
personal_tool.

**What counts as worth it (decided before running):**
- lfm25 v2 must beat lfm25 v1 on trained strict by at least 10 points.
- It must reach at least 15% held-out strict, with no held-out cell at 0% (v1 had 0% everywhere).
- Grounded web answers must make up at least 70% of its web replies.

If the teacher run's keep rate is below 45%, the training run is not launched, and I report back instead. A family under
30% kept is dropped from training, not padded (review F).

## 5. Eval changes, so generalization is measured honestly

1. **A frozen eval set.** The eval episodes are committed once to `data/eval_v2.jsonl` (requests, worlds, gold), and
   every model runs all of them. The per-model deadline that could skip a random tail in v1 is replaced by a fixed
   call budget per episode (30) and enough job time for every episode.
2. **Three kinds of held out, reported separately:**
   - **(a) new source:** PopQA (long-tail entity questions, MIT license) for web_fact. The model never saw that
     question distribution.
   - **(b) held-out combinations:** need_math (test set, unseen removal patterns), need_schedule, web_bridge,
     near-miss × git, unknown_action, recipe_compute, personal_tool.
   - **(c) held-out surfaces:** eval-only templates (3 per templated family), eval-only invented and near-miss
     words, the 24 eval personal requests, and 5 unseen repos.
3. **Per-habit scores across domains.** For example, "asks when info is missing" pools need_repo, math_pair-incomplete,
   need_web, need_math and need_schedule, and is reported both as trained-domains and held-out-domains, so a habit
   learned in only one domain shows up as a gap.
4. **Confidence intervals.** There are at least 30 episodes per held-out cell, and each family reports a Wilson 95%
   interval. A difference smaller than the overlap is not called a win.
5. **New measurements:**
   - the grounded rate of web and repo replies
   - the narrated-check rate
   - the near-miss flag rate
   - the plan-step quality rate (no reply-writing steps)
   - the "parts dropped" rate on messy_multi
   - tokens per call
6. **Measure the shipped artifact.** A 60-episode subset runs on the exported GGUF Q4_0 through llama.cpp (CPU,
   phone sampling), next to the transformers eval. This also settles the open wllama question from the v1 export:
   the lfm25 GGUF produced no `<think>` in `delta.content`. `wllama_check.py` now records `reasoning_content`, and
   one wllama run on a real Squiggle prompt goes in the eval report.
7. **Harness-only numbers are separate.** Recipe save and match rates, and search reachability (the fraction of web
   episodes where web_search returned results), are reported as harness metrics, not model scores.
8. **Every base's untouched baseline is a standing part of every eval.** For each base that gets trained (lfm25,
   gemma3), the same eval set also runs on that base exactly as released: no training and no embedding changes.
   The previous fine-tuned model (v1 lfm25, from `kealjones/squiggle-small/hf`) runs too. Results go in one table,
   untouched vs fine-tuned for every base on every row (`combine_results.py`). This adds about 5–8 minutes of l4x1
   (about $0.10) per eval run, already counted in §4's train-v2 estimate. The first such table, for v1, comes from
   `squiggle-ft-baselines`, which runs untouched LFM2.5-350M and FunctionGemma 270M on squiggle-ft-train's exact 293
   episodes.

## 6. Sample episodes (target format)

These are not Claude-written. **Template** means `gold.py`'s scripted templates, filled from real tool results; those
are few-shot examples for the teacher, not training data. **Teacher** means Qwen3-30B-A3B-Thinking output from
teach-v1, kept by the checker. Tool results are cut to their first 230 characters. Notes on each one say what v2
keeps or changes.

- **A, gold-web_fact-ff (template):** the target for §3. The Check quotes the infobox ("Release dates: June 18,
  2001…") and the reply states only that.
- **B, web_fact-10 (teacher):** right answer, but the last Check says *"The fetch_url result confirms…"* with no
  quote. **v2's grounding check would drop it.** It's shown to make the rule concrete.
- **C, web_compare-58 (teacher):** a parallel plan of task actions only. Step 1's Check quotes the "Born" field.
  Step 2's Check paraphrases ("shows … born March 17, 1933"), which v2 also rejects.
- **D, hermes_need-19 (teacher):** asks for what's missing (which platform) instead of guessing. This is the target
  for need_web and math_pair-incomplete.
- **E, recipe_repo-6 (teacher):** Know names the recipe, and the plan follows its steps.
- **F, chat_after-1 (teacher):** a task, then a plain "thanks" turn. This is the target for chat_mid. Note that it
  answers from a search snippet ("Result 3 says…") without fetching the page, which v2's grounding rule allows only
  when the quoted snippet contains the answer.
- **G, gold-unknown_word-0 (template):** an invented word, searched, nothing found, said plainly, then the user is asked.
- **H, gold-personal-0 (template):** Request / Need, no tools, warm, ends with one question.

### A. gold-web_fact-ff (template; dropped from the few-shots and gold.py after the review, because its query had the answer)

```text
User: When did the first Fast and Furious come out?
  [model] <think>
          Request: When the first Fast and Furious film came out.
          Pieces: 1. the year it came out.
          Know: only the question; nothing in the prompt says when.
          Don't know: the release date; I'd be guessing, so I'll look it up on the web.
          Goal: Say when the first Fast and Furious film came out.
          Next: find only searches my tools, memory and past chats, so look up the web search tool.
          </think>
          ```tool_call
          {"name": "find", "arguments": {"query": "search the web"}}
          ```
  [tool] Result of find: {"found":"Tools:\n- web_search(query, count?): Search the web (DuckDuckGo).\n- search_history(query): Search the user's past conversations (all sessions) for something discussed before.\n- fetch_url(url): Read a we
  [model] <think>
          Check: find gave me web_search and fetch_url.
          Next: search the web for "The Fast and the Furious 2001 film release date".
          </think>
          ```tool_call
          {"name": "web_search", "arguments": {"query": "The Fast and the Furious 2001 film release date"}}
          ```
  [tool] Result of web_search: {"query":"The Fast and the Furious 2001 film release date","count":6,"results":"<untrusted source=\"web search\" key=\"105a908d\">\n1. The Fast and the Furious (2001 film)\n https://en.wikipedia.org/wiki/The_
  [model] <think>
          Check: result "The Fast and the Furious (2001 film)" is the page for the first film; the snippets don't give the date clearly.
          Next: read that page.
          </think>
          ```tool_call
          {"name": "fetch_url", "arguments": {"url": "https://en.wikipedia.org/wiki/The_Fast_and_the_Furious_(2001_film)"}}
          ```
  [tool] Result of fetch_url: {"truncated":"Result cut to fit your context; ask for less (e.g. grep, or a line range).","partial":"{\"url\":\"https://en.wikipedia.org/wiki/The_Fast_and_the_Furious_(2001_film)\",\"status\":200,\"title\":\"T
  [model] <think>
          Check: this is the Wikipedia page for the first film, and it says: "Release dates: June 18, 2001 (Mann Village Theatre)  June 22, 2001 ("
          Next: answer with the date and cite the page.
          </think>
          The first Fast and Furious film, The Fast and the Furious, came out on June 18, 2001 (from its Wikipedia page).
```

### B. web_fact-10 (teacher output)

```text
User: um where are the 10 plagues found in the bible idk if that makes sense thx
  [model] <think>
          Request: Where the 10 plagues are found in the Bible.
          Pieces: 1. The book and chapters in the Bible describing the 10 plagues.
          Know: Only the question; nothing in the prompt gives the reference.
          Don't know: The exact Bible passage; guessing would be incorrect.
          Goal: Find the correct biblical reference for the 10 plagues.
          Next: Use find to get the web_search tool, as it's required for factual Bible references.
          </think>
          ```tool_call
          {"name": "find", "arguments": {"query": "search the web"}}
          ```
  [tool] Result of find: {"found":"Tools:\n- web_search(query, count?): Search the web (DuckDuckGo).\n- search_history(query): Search the user's past conversations (all sessions) for something discussed before.\n- fetch_url(url): Read a we
  [model] <think>
          Check: The user asks where the 10 plagues are in the Bible. The tools list includes web_search, so use it.
          Next: Search the web for "10 plagues of Egypt Bible book and chapter" to find the exact reference.
          </think>
          ```tool_call
          {"name": "web_search", "arguments": {"query": "10 plagues of Egypt Bible book and chapter"}}
          ```
  [tool] Result of web_search: {"query":"10 plagues of Egypt Bible book and chapter","count":6,"results":"<untrusted source=\"web search\" key=\"dd17dd11\">\n1. Plagues of Egypt\n https://en.wikipedia.org/wiki/Plagues_of_Egypt\n In the Boo
  [model] <think>
          Check: search result 1 says "Plagues of Egypt" in Book of Exodus (Wikipedia link). The user needs the specific book and chapter.
          Next: fetch the Wikipedia page for "Plagues of Egypt" to find the exact Exodus chapters.
          </think>
          ```tool_call
          {"name": "fetch_url", "arguments": {"url": "https://en.wikipedia.org/wiki/Plagues_of_Egypt"}}
          ```
  [tool] Result of fetch_url: {"truncated":"Result cut to fit your context; ask for less (e.g. grep, or a line range).","partial":"{\"url\":\"https://en.wikipedia.org/wiki/Plagues_of_Egypt\",\"status\":200,\"title\":\"Plagues of Egypt - Wi
  [model] <think>
          Check: The fetch_url result confirms the plagues are in the Book of Exodus (Wikipedia: Plagues of Egypt).
          Next: Answer with the book name and cite the source.
          </think>
          The 10 plagues of Egypt are found in the Book of Exodus (from the Wikipedia page "Plagues of Egypt").
```

### C. web_compare-58 (teacher output)

```text
User: Who was born first, Arthur Conan Doyle or Penelope Lively?
  [model] <think>
          Request: Who was born first, Arthur Conan Doyle or Penelope Lively?
          Pieces: 1. Arthur Conan Doyle's birth date. 2. Penelope Lively's birth date. 3. which is earlier.
          Know: only the two names; no birth dates in the prompt.
          Don't know: both birth dates; we cannot guess.
          Goal: Say who was born first.
          Plan: two separate lookups for each person's birth date.
          </think>
          ```tool_call
          {"name": "plan", "arguments": {"goal": "Find who was born first: Arthur Conan Doyle or Penelope Lively", "steps": ["Find Arthur Conan Doyle's birth date", "Find Penelope Lively's birth date"]}}
          ```
  [model] <think>
          Step: 1 of 2, Arthur Conan Doyle's birth date; the reply needs the exact date.
          Know: no web tools looked up yet.
          Next: find the tool to search the web.
          </think>
          ```tool_call
          {"name": "find", "arguments": {"query": "search the web"}}
          ```
  [tool] Result of find: {"found":"Tools:\n- web_search(query, count?): Search the web (DuckDuckGo).\n- search_history(query): Search the user's past conversations (all sessions) for something discussed before.\n- fetch_url(url): Read a we
  [model] <think>
          Check: find provided web_search, which can find the birth date.
          Next: search the web for "Arthur Conan Doyle birth date" to get the exact date.
          </think>
          ```tool_call
          {"name": "web_search", "arguments": {"query": "Arthur Conan Doyle birth date"}}
          ```
  [tool] Result of web_search: {"query":"Arthur Conan Doyle birth date","count":6,"results":"<untrusted source=\"web search\" key=\"6be72615\">\n1. Professor Moriarty\n https://en.wikipedia.org/wiki/Professor_Moriarty\n Arthur Conan Doyle 
  [model] <think>
          Check: Web search results are about Arthur Conan Doyle's fictional works (Sherlock Holmes, Professor Moriarty) but don't contain his birth date. The correct Wikipedia page for his birth date is https://en.wikipedia.org/wiki/Arthur_Conan_Doyle.
          Next: Fetch that Wikipedia page to get his birth date.
          </think>
          ```tool_call
          {"name": "fetch_url", "arguments": {"url": "https://en.wikipedia.org/wiki/Arthur_Conan_Doyle"}}
          ```
  [tool] Result of fetch_url: {"truncated":"Result cut to fit your context; ask for less (e.g. grep, or a line range).","partial":"{\"url\":\"https://en.wikipedia.org/wiki/Arthur_Conan_Doyle\",\"status\":200,\"title\":\"Arthur Conan Doyle 
  [model] <think>
          Check: the fetch_url result is the Wikipedia page for Arthur Conan Doyle; the "Born" line says "22 May 1859".
          Next: done with the birth date and source.
          </think>
          ```tool_call
          {"name": "done", "arguments": {"result": "Arthur Conan Doyle: born 22 May 1859 (Wikipedia: Arthur Conan Doyle)"}}
          ```
  [model] <think>
          Step: 2 of 2, Penelope Lively's birth date; the reply needs the exact date.
          Know: no tools looked up for Penelope Lively yet; Arthur Conan Doyle used web_search.
          Next: search the web for "Penelope Lively birth date".
          </think>
          ```tool_call
          {"name": "web_search", "arguments": {"query": "Penelope Lively birth date"}}
          ```
  [tool] Result of web_search: {"query":"Penelope Lively birth date","count":6,"results":"<untrusted source=\"web search\" key=\"6be72615\">\n1. 2026 deaths in the United Kingdom\n https://en.wikipedia.org/wiki/2026_deaths_in_the_United_Ki
  [model] <think>
          Check: web_search results mention Penelope Lively in context (result 4) but don't state her birth date. Need to fetch her Wikipedia page directly.
          Next: call fetch_url on https://en.wikipedia.org/wiki/Penelope_Lively to find her birth date.
          </think>
          ```tool_call
          {"name": "fetch_url", "arguments": {"url": "https://en.wikipedia.org/wiki/Penelope_Lively"}}
          ```
  [tool] Result of fetch_url: {"truncated":"Result cut to fit your context; ask for less (e.g. grep, or a line range).","partial":"{\"url\":\"https://en.wikipedia.org/wiki/Penelope_Lively\",\"status\":200,\"title\":\"Penelope Lively - Wiki
  [model] <think>
          Check: fetch_url result shows Penelope Lively born March 17, 1933 (Wikipedia: Penelope Lively).
          Next: step done; record birth date and source.
          </think>
          ```tool_call
          {"name": "done", "arguments": {"result": "Penelope Lively: born 17 March 1933 (Wikipedia: Penelope Lively)"}}
          ```
  [model] <think>
          Answer: Step 1 gives Arthur Conan Doyle born 1859, step 2 gives Penelope Lively born 1933; 1859 is earlier. Cite both Wikipedia pages.
          </think>
          Arthur Conan Doyle was born first: born 22 May 1859 and Penelope Lively in 17 March 1933 (from their Wikipedia pages).
```

### D. hermes_need-19 (teacher output)

```text
User: Can you show me the profile picture of user @jane_doe?
  [model] <think>
          Request: Show the profile picture of user @jane_doe.
          Pieces: 1. The profile picture URL or image.
          Know: The user's handle is @jane_doe; no tools are available yet.
          Don't know: How to retrieve a profile picture (no tool listed for this).
          Goal: Get the profile picture URL for @jane_doe.
          Next: Find the right tool to fetch a user profile picture.
          </think>
          ```tool_call
          {"name": "find", "arguments": {"query": "get user profile picture"}}
          ```
  [tool] Result of find: {"found":"Nothing found. Try different words, look it up with a tool, or ask the user.","context_left":"about 3500 of 4096 tokens"}
  [model] <think>
          Check: find with "get user profile picture" found nothing.
          Next: can't proceed without knowing the platform (GitHub, Twitter, etc.); ask the user.
          </think>
          ```tool_call
          {"name": "need", "arguments": {"what": "Which platform (e.g., GitHub, Twitter) is @jane_doe on?"}}
          ```
```

### E. recipe_repo-6 (teacher output)

```text
User: uh can you get me the version and the latest commit for chalk/chalk please
  [model] <think>
          Request: Get version and latest commit for chalk/chalk.
          Pieces: 1. version. 2. latest commit.
          Know: repo is chalk/chalk; recipe from similar task (ms) has two steps: clone and read version, then get commit.
          Don't know: version and latest commit; need to look up.
          Goal: Report chalk/chalk's version and latest commit.
          Plan: Use the recipe steps: 1. Clone chalk/chalk and read version from package.json, 2. Get latest commit from git log.
          </think>
          ```tool_call
          {"name": "plan", "arguments": {"goal": "Find chalk/chalk's version and latest commit", "steps": ["Clone chalk/chalk and read the version from package.json", "Get the latest commit from the git log"]}}
          ```
  [model] <think>
          Step: 1 of 2, clone chalk/chalk and read version from package.json; the reply needs the version number.
          Know: no tools looked up yet (only plan, done, need, find available).
          Next: look up tools for cloning a repo and reading a file.
          </think>
          ```tool_call
          {"name": "find", "arguments": {"query": "clone a github repo and read a file"}}
          ```
  [tool] Result of find: {"found":"Tools:\n- read_file(path, start_line?, end_line?): Read lines of a text file from the workspace, with line numbers.\n- git_clone(repo, branch?): Clone a GitHub repo into /repos/<name>.\n- github_list_repo
  [model] <think>
          Check: find confirmed git_clone and read_file are available; repo is chalk/chalk from the user's request.
          Next: clone chalk/chalk to /repos/chalk.
          </think>
          ```tool_call
          {"name": "git_clone", "arguments": {"repo": "chalk/chalk"}}
          ```
  [tool] Result of git_clone: {"ok":true,"path":"/repos/chalk","branch":"main","files":35}
  [model] <think>
          Check: git_clone succeeded to /repos/chalk; package.json is standard location.
          Next: read /repos/chalk/package.json for version.
          </think>
          ```tool_call
          {"name": "read_file", "arguments": {"path": "/repos/chalk/package.json"}}
          ```
  [tool] Result of read_file: {"path":"/repos/chalk/package.json","total_lines":91,"start_line":1,"end_line":91,"content":"<untrusted source=\"file /repos/chalk/package.json\" key=\"16ea6875\">\n1: {\n2: \t\"name\": \"chalk\",\n3: \t\"vers
  [model] <think>
          Check: read_file shows version 6.0.1 in package.json at /repos/chalk/package.json.
          Next: step 1 is done; record version and source.
          </think>
          ```tool_call
          {"name": "done", "arguments": {"result": "version 6.0.1 (from /repos/chalk/package.json)"}}
          ```
  [model] <think>
          Step: 2 of 2, get the latest commit from git log; step 1 already cloned the repo to /repos/chalk.
          Know: git_log tool not yet looked up (only read_file, git_clone, github_list_repos available).
          Next: find the git_log tool before using it.
          </think>
          ```tool_call
          {"name": "find", "arguments": {"query": "recent commits"}}
          ```
  [tool] Result of find: {"found":"Tools:\n- git_log(repo, count?): Recent commits on the current branch.\n- git_commit(repo, message): Commit all changes in a repo on the current branch.","tools":["git_log","git_commit"]}
  [model] <think>
          Check: find confirmed git_log is available; the repo was cloned to /repos/chalk (from step 1).
          Next: call git_log on repo "chalk" with count 1 to get the latest commit.
          </think>
          ```tool_call
          {"name": "git_log", "arguments": {"repo": "chalk", "count": 1}}
          ```
  [tool] Result of git_log: {"commits":"<untrusted source=\"git log\" key=\"16ea6875\">\n72110019 2026-09-25 Sindre Sorhus: Meta tweaks\n</untrusted key=\"16ea6875\">"}
  [model] <think>
          Check: git_log result is for chalk repo (correct), commit 72110019 from 2026-09-25 by Sindre Sorhus with message "Meta tweaks".
          Next: step 2 done; record commit details and source.
          </think>
          ```tool_call
          {"name": "done", "arguments": {"result": "latest commit 72110019 (2026-09-25, Sindre Sorhus): Meta tweaks (from git log)"}}
          ```
  [model] <think>
          Answer: step 1 found version 6.0.1 from package.json, step 2 found commit 72110019 from git log; cite both sources.
          </think>
          chalk/chalk is at version 6.0.1 (from its package.json), and the latest commit is 72110019 from 2026-09-25 by Sindre Sorhus: "Meta tweaks" (from the git log).
```

### F. chat_after-1 (teacher output)

```text
User: Who sings gimme shelter with mick jagger?
  [model] <think>
          Request: Who sings "Gimme Shelter" with Mick Jagger.
          Pieces: 1. The name of the singer who collaborated on "Gimme Shelter" with Mick Jagger.
          Know: Only the song title and Mick Jagger's name; no other context.
          Don't know: The collaborator's name; guessing would be wrong.
          Goal: Find the correct collaborator for "Gimme Shelter".
          Next: Use find to locate the web search tool since this is a factual question about music.
          </think>
          ```tool_call
          {"name": "find", "arguments": {"query": "search the web"}}
          ```
  [tool] Result of find: {"found":"Tools:\n- web_search(query, count?): Search the web (DuckDuckGo).\n- search_history(query): Search the user's past conversations (all sessions) for something discussed before.\n- fetch_url(url): Read a we
  [model] <think>
          Check: The user's question is about the singers of "Gimme Shelter" with Mick Jagger. The tools available include web_search.
          Next: Use web_search to find the answer, as it's a factual question about a song.
          </think>
          ```tool_call
          {"name": "web_search", "arguments": {"query": "Who sings Gimme Shelter with Mick Jagger"}}
          ```
  [tool] Result of web_search: {"query":"Who sings Gimme Shelter with Mick Jagger","count":6,"results":"<untrusted source=\"web search\" key=\"5cb711a4\">\n1. Gimme Shelter\n https://en.wikipedia.org/wiki/Gimme_Shelter\n \"Gimme Shelter\" 
  [model] <think>
          Check: Result 3 says Merry Clayton worked with Mick Jagger on "Gimme Shelter" (Wikipedia: Merry Clayton).
          Next: Answer with the fact from the web search result.
          </think>
          Merry Clayton sings "Gimme Shelter" with Mick Jagger (from the web search result: Merry Clayton's Wikipedia page mentions her duet on the Rolling Stones song).
User (turn 2): great, that's what i needed
  [model] <think>
          A casual thanks; nothing to look up, just a short friendly reply.
          </think>
          You're welcome! Let me know if you need anything else.
```

### G. gold-unknown_word-0 (template)

```text
User: my coworker keeps frundozzling the shared drive is that bad
  [model] <think>
          Request: Whether it's bad that their coworker keeps "frundozzling" the shared drive.
          Pieces: 1. what "frundozzling" means. 2. whether that's bad.
          Know: only their message; I don't know the word "frundozzling".
          Don't know: what it means; it could be made up, misheard or office slang, so I'll look it up instead of guessing.
          Goal: Find out what the word means, then answer.
          Next: find only searches my tools, memory and past chats, so look up the web search tool.
          </think>
          ```tool_call
          {"name": "find", "arguments": {"query": "search the web"}}
          ```
  [tool] Result of find: {"found":"Tools:\n- web_search(query, count?): Search the web (DuckDuckGo).\n- search_history(query): Search the user's past conversations (all sessions) for something discussed before.\n- fetch_url(url): Read a we
  [model] <think>
          Check: find gave me web_search and fetch_url.
          Next: search the web for the word itself.
          </think>
          ```tool_call
          {"name": "web_search", "arguments": {"query": "frundozzling meaning"}}
          ```
  [tool] Result of web_search: {"query":"frundozzling meaning","count":0,"results":"<untrusted source=\"web search\" key=\"f9a71f2e\">\nNo results.\n</untrusted key=\"f9a71f2e\">","context_left":"about 3200 of 4096 tokens"}
  [model] <think>
          Check: no result explains "frundozzling"; nothing on the web defines it, so it's not a known word.
          Next: say so plainly, don't invent a meaning, and ask what their coworker actually does.
          </think>
          I searched the web for "frundozzling" and found nothing, so it doesn't seem to be a real word. It might be an in-joke or slang at your office, but that's only a guess. What does your coworker actually do to the shared drive?
```

### H. gold-personal-0 (template)

```text
User: I need an idea for a birthday present for my father.
  [model] <think>
          Request: A birthday present idea for their dad.
          Need: a few ideas that suit most dads, warmly; I don't know what he enjoys, so options first, then one question to narrow it down.
          </think>
          That's a lovely thing to be planning! A few ideas that work for a lot of dads: something for a hobby he already loves, an experience you share (a game, a meal out, a day trip), or something personal like a framed photo or a short letter about what he means to you. What does he enjoy doing in his free time?
```

## 7. Questions for the reviewer

1. Is quote-grounding (§3) too strict for answers that combine two sentences (e.g. a date from one line and a place
   from another)? Option: allow up to two quoted spans.
2. near_miss vs dictation slips: is "the key term" a boundary the teacher can follow? The alternative is to flag
   every non-word, which would make messy input tiring.
3. Does training math_pair (ask × math) leave enough held out for the "ask" habit? Held out are need_math with new
   removal patterns, need_schedule and need_web-style pronouns in new domains.
4. Should personal_tool (personal × one real lookup) be trained in a small amount, rather than held out, given how
   strong "personal = no tools" will be?
