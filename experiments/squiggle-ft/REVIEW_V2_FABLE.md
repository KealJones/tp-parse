# Review of CORPUS_V2 (Fable, Oct 28 2026)

Scope: the v2 design (`CORPUS_V2.md` at e03ce56), its checkers (`quality.py`, `families.py`, `hermes.py`), the
split (`build.py`, `sources.py`) and training (`train.py`), read against `AUDIT_V1.md`, the v1 results and the
Squiggle harness at `d9cbfea`+ (`calc.js`, `tools.js`, `docs/harness.md`). Nothing was launched or spent. I wrote no
training text: the companion patch `review_v2_checker.patch` holds checker code, user-side request templates, and
negative fixtures for the checker tests (`checker_tests.py`), all mechanically mutated teacher text or short labelled
bad strings.

**Verdict: don't run v2 as written.** The design is right about *what* to teach (calculate, grounding, contrastive
math pairs, sequential plans, mid-session chat), but three things would make the run worthless or repeat v1:

1. The checkers the design relies on (`grounded()`, `computed_numbers_grounded()`, `narrated_check`, the plan rule) are
   described but don't exist, and `tool_specs.json` has no `calculate`, so `quality.validate_call` would reject every
   calculate call as `unknown tool 'calculate'`: the compute families would produce 0 kept episodes, and the rest would
   be filtered by the v1 checker the audit showed is porous. The patch implements these and more (§A).
2. Audit problems 2, 3, 4 and 6 are not addressed anywhere in CORPUS_V2 (§B), and I found 9 further holes the audit
   missed, each proven by running the checker on a mutated kept episode (§C).
3. The training recipe is unchanged from the run that overfit (train loss 0.21, held-out 0%): no dev split, no early
   stop, 3 epochs at 4e-5, heavy near-duplicate examples (§E).

With the patch applied, the re-checked v1 corpus keeps 405/565 (every audit-named wrong episode now fails; 0 of the
v1-rejected episodes flip to pass; math and hermes_compute go to 0/84 by design, they are regenerated with calculate).

---

## A. Highest impact: the checker must enforce "the fact came from a result" (patch)

What `review_v2_checker.patch` changes, all in `experiments/squiggle-ft/`:

| file | change |
|---|---|
| `tool_specs.json` | adds `calculate` (copied from `tools.js` at d9cbfea) and run_js's new description. Replace with the real re-export when the pin moves; the test file will tell you if the schema drifts. |
| `quality.py` `validate_call` | `plan`: rejects steps that write/review the reply and "find the tools" steps (`META_STEP`). `done`: `DONE_NARRATES` extended ("Tools found: …", "Ready…"), `DONE_FACT` no longer counts a sentence-initial capital. `calculate`: rejects code, words other than calc.js functions/"of"/"x", and expressions without a number. |
| `quality.py` `SOURCE` | "from memory", "from Brittany", "and/or", "ran" no longer count as citations. |
| `families.py` new helpers | `turn_results` / `good_results` (reads results back from the prompts, flags `{"error"}` results, unescapes JSON), `answer_grounded`, `guessed_early`, `cited_source_called`, `check_refers_to_result`, `narrated_without_tools`, `computed_numbers_grounded`, `done_ungrounded`, `need_guesses` / `need_new_numbers`, `hedged`, `negated`, `picked`. |
| `families.py` `call_problems` (every family) | citation must name a page/file/repo/tool used this turn; Check lines must bring a word or quote from the result they follow; "I checked/confirmed/found" needs a tool result; computed numbers must equal a `calculate` result; `run_js` in a math family fails; a plan on a one-lookup family fails; a `done` whose concrete tokens are in no result of that step fails. |
| `check_web_fact`, `check_repo_fact`, `check_repo_two`, `check_refs`, `check_need_repo`, `check_memory_repo`, `check_past_chat`, `chat_after` | the gold must appear in a non-error tool result of the turn, and must not appear in the model's own text (thinking, query, path) before a result had it. Hedged, negated and "either A or B" replies fail. `refs` and `need_repo` require a repo lookup in **each** answering turn. |
| `check_repo_answer` | licence as a whole word (`\bMIT\b`), path as a whole path (optionally under `/repos/<name>/`). |
| `check_web_compare` | `picked()`: for "A or B" golds the gold must be the first candidate named and not negated; both titles must appear in results; `hedged` fails. |
| `check_math`, `hermes.check` | `calculate` instead of `run_js`; the gold must equal a calculate result; `need` questions must not contain a number the request didn't have. Hermes string/list tools (`reverse_words`, `is_palindrome`…) stay on `run_js` (`NUMERIC` decides). |
| `check_bare_link` | ≥60% of the reply's content words (5+ letters, not boilerplate) must be in the fetched page. |
| `check_need_math` | no calculate/run_js before asking; the need question carries no new number. |
| `messy()` | `phrases=` keeps fillers and stutters out of an alias ("my um agent project"). |
| split (`CHAT_EVAL`, `NEED_REPO_ASKS`, `WHERE_ASKS`, `REFS_FIRST/FOLLOW`, `MEM_ASK`, `MEM_TPL`, `chat_after` follow-ups) | train/eval template sets, disjoint, threaded through `build.load_sources` (`src["split"]`) and `make_sets`. |
| `checker_tests.py` | 77 cases (unit + mutated-episode); each audit-named wrong episode (web_compare-24/-38/-57, refs-21, repo_two-12/-15) must fail; clean episodes of six families must still pass. Run it before any teacher job. |

Known cost of the stricter rules on v1 data (all judged by hand): `hermes_need-25` ("9x9 grid (81 numbers)") is
dropped by the no-new-numbers rule; `web_fact-59` (gold "member") by the early-guess rule; `web_fact-47` is dropped
because its Check guesses "pour point" from "lol" before searching, which is exactly the generator artifact the audit
flagged. Acceptable.

Two things the patch does **not** do, which the teach job should:
- **Judge for ambiguous comparisons.** `picked()` is a heuristic. Add `judge.py` in `jobs/teach_smoke.sh` after the
  run: for kept web_compare / lookup_then_compute episodes where the gold and another candidate are both named, ask the
  already-loaded Qwen3-30B "which candidate does this reply say is the answer? one word". ~150 calls, well under $0.05
  on the same vLLM process. Reject on disagreement with the gold. Do not use a judge for anything the grounding rules
  decide mechanically.
- **Few-shot leakage filter** (audit 6, see B6).

## B. The audit's eight problems against CORPUS_V2

| # | audit problem | v2 status | what's missing |
|---|---|---|---|
| 1 | answers without lookups | **partly**. §3 `grounded()` + §2h computed numbers + teacher rules. | (a) `grounded()` is gold-independent and only checks capitalised phrases/numbers, so a lowercase answer ("euro", "pour point") is vacuously grounded; (b) it reads only the *last* Check line; (c) nothing on the answer appearing in thinking or the search query before evidence; (d) nothing on error results; (e) `refs` still has no lookup requirement at all (§C-A). Patch: `answer_grounded` (gold in a non-error result), `guessed_early`, `check_refers_to_result` on every Check. Keep §3's quote rule as a *teacher* instruction; make the checker rule "gold in result + quote or fresh word in every Check". Allow two quoted spans (your Q1: yes). |
| 2 | web_compare check is empty | **not fixed**. §2b says "As v1, plus grounded step results". | `picked()` in the patch, non-answer regex extended ("not confirmed", "not a recognized", "no relevant results", "neither page/result"), optional Qwen judge (§A). Also `same_entity` is too loose: in web_compare-62 it mapped a sentence gold onto "Dime Magazine" via one shared word; require the title's content words to be a subset of the gold's, not 50% overlap. |
| 3 | licence substring | **not fixed** (not mentioned). | Patched: whole-word SPDX id. Also `repo_two-12/-15`: the done said "LICENCE file" and the reply said MIT with MIT in no result; grounding catches it. |
| 4 | citation accepts anything | **not fixed** (not mentioned). | Patched: `SOURCE` tightened + `cited_source_called` (the cited page title, path, repo or source kind must match a tool used this turn). |
| 5 | eval/train overlap | **partly**. Eval-only templates (3 of ≥12), PopQA, unseen repos, personal/word splits. | No mechanism in code; `chat` still "casual openers (v1 list)" so the 8/16 overlap stays, and `chat_mid` draws the same strings; memory_repo "unchanged" keeps 10/10 eval on the same two repos and the same aliases; need_repo "as v1" keeps 5 templates. Patched: disjoint train/eval lists for chat, chat_after follow-ups, need_repo, refs, repo_where, memory_repo aliases and phrasings, threaded by `src["split"]`. Add a unit test that every templated family's eval set is disjoint (in `checker_tests.py`). |
| 6 | Claude text leaked via few-shots | **not fixed** (not mentioned). `teacher.few_shot` still ships `gold-chat-0`, the exact leaked reply. | Add an n-gram filter in `build.examples`: drop an example whose output shares any 8-word run (outside tool-call JSON) with `examples/gold.jsonl`, `examples/worked.jsonl`, `samples/samples.jsonl` or `TEACHER.md`; log the count. Replace the chat few-shot with a template whose reply is built from the user's words. Note `gold-web_fact-ff` puts "2001" in the search query before any result: the new checker rejects it, and as a few-shot it teaches guess-then-confirm. Regenerate it with a query built from the question only. |
| 7 | skew | **partly**. Rebalanced by habit; recipes varied (recipe_web, recipe_skip). | By *domain* it is still repo-heavy: reused v1 kept episodes are 219/333 repo (66%), plus repo_chain 50 and recipe_skip 20. Cap reuse at ~25 kept episodes per v1 repo family (pick distinct repos × templates) and spend the saved examples on web/need/personal. Messy flag: `bare_link` and `past_chat` still hard-code `messy_=True`; set it from `maybe_messy`. Filler inside aliases: patched. Date: every prompt says Oct 28 2026; have `sq/env.mjs` set a fake `Date` per episode (random day in a ±2-year window) so the date line isn't a constant. |
| 8 | habits not enforced | **partly**. Plan rule (reply-writing steps, one-fact plan) stated. | Regex in §2b misses "find the tools" steps and "Tools found" dones (6 plans in v1); patched (`META_STEP`, `DONE_NARRATES`, `done_ungrounded`). Check-refers-to-result: patched for every Check line. "Answer: repeats the reply": leave it, it's harmless at 350M. |

## C. Holes the audit missed (each proven: `checker_tests.py` episode cases; all passed the v1 checker, all fail now)

| | hole | proof (mutated kept episode) |
|---|---|---|
| A | `check_refs` never requires a lookup in **either** turn: `ok1` is only `check_repo_answer`. | refs-0 with turn 0's calls removed except the reply: strict. |
| B | `repo_where` accepts any file with the same basename and parent dir. | gold `src/humanize/time.py`, reply `test/fixtures/src/humanize/time.py`: strict. |
| C | Hedged ("probably X, I believe"), listed ("either X or Zanzibar") and negated ("not X") replies count as right answers. | web_fact-57 reply swapped: strict ×3. |
| D | Every tool result replaced by `{"error":…}`, reply unchanged: strict. The checker never reads results. | web_fact, repo_fact version. |
| E | `done("Ready for the next step")`, `done("Found the tools needed")` pass `validate_call`. | unit. |
| J | A guessed repo inside the `need` question ("Do you mean X? Which repo?") passes need_repo. | need_repo-0 mutated. |
| N | A bare_link "summary" that is boilerplate naming the title passes. | bare_link-0. |
| S | The gold answer inside the `web_search` query (guess, then confirm) passes. | web_fact-2. |
| T | A Check line that restates the request passes (the audit counted 125 such lines but no check existed). | web_fact-0. |

Also found: `hermes.check` lets a `need` question carry an assumed value; `check_math` accepted an answer when run_js
printed nothing (audit 1) and never compared the result to the gold; `NUMBER` scanning missed numbers next to JSON
`\t`/`\n` escapes (now unescaped); `ARITH` wording list needed care (paths contain "/", "line 57" is a reference, years
aren't computations) — the patch's version was tuned on the v1 corpus until only real cases remained.

## D. Generalization and the eval split

1. **Template leakage** (B5) is the main dishonesty; patched. Sources are clean: NQ validation[0:1500] vs [3000:3600],
   HotpotQA validation[0:2500] vs [6000:7400], GSM8K train vs test, 18 vs 5 repos, personal and words split.
2. **find queries are four literal strings** in 415 of 740 v1 find calls ("search the web", "clone a github repo and
   read a file", "recent commits", "run javascript to calculate"), copied from TEACHER.md's "Good find queries". That teaches a lookup table, not a
   habit, and it is why held-out domains (scheduling, personal_tool) will not know what to ask `find`. Change the
   teacher rule to describe the query ("say what you need to do, in 3–6 words, with the kind of thing: web, repo,
   file, commits, past chats") and remove the literal list; in `build.examples`, cap identical `(tool, arguments)`
   signatures at 60 examples each (downweight the rest to 0.3 in the loss) so no single string dominates.
3. **Memorization vs transfer.** 3.85k examples / ~840 episodes is a fine size for a 350M full fine-tune of a *format*,
   but habit cells with < 25 kept episodes teach nothing: need_web 30 attempted (~18 kept), recipe_skip 20 (~12),
   personal_mid 30 (~20). Either raise those to 50 / 40 / 40 (+$0.35) or merge need_web into a wider "ask for the
   subject" family across web + repo + schedule phrasings. The sequential-plan transfer repo_chain → web_bridge is a
   long shot at 350M; keep web_bridge held out, but don't let the "no held-out cell at 0%" bar hinge on it: report it,
   and set the bar on the per-habit pooled held-out score.
4. **Contrastive pairs everywhere, not only math.** math_pair is the right idea. Add the same shape to: need_repo vs
   memory_repo on the *same* request text (already close; make the phrasing identical and only the memory differ),
   web_fact vs need_web (same question with and without the subject), recipe_web vs recipe_skip (same recipe, request
   that fits vs. half-fits). Pairs are what teach the decision; single-sided families teach the script.
5. **Held-out design questions (§7):** Q1 two spans, yes. Q2 key-term boundary is fine as long as `gold` marks the
   term and the checker tests only that term; add 10 eval-only near-misses in git/code as planned. Q3 enough: need_math
   with new removal patterns is in-domain; need_schedule and need_web-in-new-domains are the real transfer tests, and
   need_schedule needs a scripted user answer and a gold that the checker can verify ("asked before acting" + "no day
   or time invented"). Q4 train personal_tool a little (15 episodes, one fact type: books/films) and hold out 30 of
   another fact type (places/dates); otherwise "personal = no tools" becomes absolute and the cell measures only that.
6. **Frozen eval + no deadline** (§5.1): `train.evaluate` still passes `deadline=minutes*60`; remove it and size the job.

## E. Training setup (`train.py`)

v1 lfm25: 285 steps, lr 4e-5 cosine, 3 epochs, loss 0.69 → 0.37 → 0.21, held-out 0%. Concrete changes:

1. **Dev split and early stop.** `train()`: hold out 5% of *episodes* (`ex["episode"]`), compute dev loss (forward only)
   at the end of each epoch, keep the weights of the best epoch. Cheap (dev is ~150 examples) and the only way to see
   overfit without a 20-minute eval.
2. **LR / epochs.** lfm25 2e-5, 3 epochs with early stop (expect it to stop at 2); gemma3 keep 4e-5. Add `--lr-per-base`.
3. **Per-step token normalisation.** `(loss / n_t / accum)` weights each micro-batch equally whatever its token count;
   accumulate `sum(loss)` and `sum(n_t)` over the `accum` micro-batches and divide once.
4. **Duplicate control.** Weight examples by `1/sqrt(count of identical (kind, tool, arguments))` capped at 1, and cap
   examples per episode at 10 (v1 max 17) by dropping repeated find→result pairs; `render()` already gives you the
   hook. Without this, the 415 identical find calls are ~15% of the examples.
5. **Loss masking and templates** are correct: labels are -100 on the prompt, the end-of-turn token is trained, and
   `render()` asserts the prompt is a prefix. Keep `init_think_tokens`. One gap: the app uses the GGUF's template;
   add to `selftest.py` a byte comparison of the HF chat template with the one `convert_hf_to_gguf.py` writes.
6. **Base skills.** Math-in-head 31% → 6% is *intended* under §2h (the target is calculate, score it as such), and
   web_fact 12% → 0% was habit, not knowledge. What to protect is general language: add a 60-prompt "general chat"
   eval (open prompts, scored by `check_chat_turn` + length + no tools) run on untouched and tuned bases. If it drops
   more than 10 points, add replay: ~300 open prompts (Dolly/oasst2) answered by the **untouched LFM2.5 itself**
   (open weights, so allowed) in plain-chat format, mixed at ~8% of examples. Don't replay anything else.
7. **Verdict** (`verdict()`): the bar still says "beats untouched Gemma 3". Make it "beats the untouched *same* base on
   trained strict, held-out strict, and right-answer rate on web_fact and math_pair-complete", using
   `combine_results.py`'s table, and add the §2h measurements (computed-number grounded rate, run_js misuse rate) to
   `metrics()`.

## F. Smaller points

- `TEACHER.md` / `teacher.RULES` habit 7 still says run_js; rewrite to calculate (§2h text is right), and tell the
  teacher: empty or error result → rerun or say so; follow-up turns don't see earlier results, look again; cite only
  what you read this turn; never a candidate answer inside a need question.
- `CORPUS_V2` §4 cost table assumes a 55–70% keep rate; with the stricter checker expect 45–60% on web families. The
  "below 45% keep → don't train" rule is good; keep it per family (a family under 30% kept is dropped from training,
  not padded).
- `HABIT["math"]` and the family comment said run_js; patched to calculate.
- `jobs/boot.py` pin must move to ≥ d9cbfea before any job; re-export `tool_specs.json` and run `checker_tests.py`,
  `selftest.py` and `gold.py` (expect `gold-web_fact-ff` to fail until regenerated).

## G. Order of work before launching

1. Apply the patch; re-pin Squiggle; re-export `tool_specs.json`; run `checker_tests.py` and `selftest.py`.
2. Regenerate `gold-web_fact-ff` and `gold-chat-0`; add the n-gram leakage filter; fix `teacher.RULES` (run_js →
   calculate, find-query wording, no literal query list).
3. Implement the v2 families still missing from `families.py` (repo_chain, lookup_then_compute, messy_multi,
   math_pair, need_web, recipe_web, recipe_skip, near_miss, chat_mid, personal_mid, web_fact_retry) with the
   train/eval template split from the start, and `data/eval_v2.jsonl` frozen.
4. `train.py`: dev split + early stop, token normalisation, duplicate weighting, same-base verdict.
5. Teacher smoke (40 episodes, $0.60) to read the keep rate under the new checker, then the full round.
