# Independent audit of the teach-v1 corpus and its checker

Audited by an agent that didn't build any of it, Oct 28, 2026, around 1:30 am Arizona time. Read-only.

**What was audited:** `hf-teach-2/teach/train_examples.jsonl.gz` at tp-parse 5b0c9fa. That is 2,839 examples from 565 kept episodes, all from Qwen3-30B-A3B-Thinking: exactly what `train.py` used.

## Verdict: partly
The format claim holds. The claim that "everything passed" holds only because the checker is weak. 4.6% of the kept data is wrong or guessed, and the checker let all of it through.

### Format: 2,839/2,839 pass
- `selftest.py` was rerun independently at Squiggle's pinned commit e9c27ca with 0 problems.
- It uses the app's own `splitThinking`, `parseToolCalls`, `isLooping` and `gemmaMessages` (through `sq/format.mjs`).
- `tool_specs.json` matches the app.
- Labelled thinking is 100% present and in order.

### Content
- **26/565 kept episodes (4.6%, 172 examples) have a guessed fact or a wrong answer.** About another 10% have softer habit problems.
- **Random sample:** 110 examples (seed 20261028), about 96 clean (87%).

| family | sample result | notes |
|---|---|---|
| bare_link | 5/5 | |
| hermes_compute | 5/5 | |
| hermes_need | 10/10 | |
| memory_repo | 5/5 | |
| past_chat | 10/10 | |
| repo_fact | 5/5 | |
| refs | 5/5 | but the whole-corpus scan found 11/38 refs episodes guessed |
| chat | 3/5 | two template replies that don't fit what was said |
| chat_after | 4/5 | one states the answer before searching |
| math | 3/5 | one answers from its head after an empty run_js; one works the answer out in its thinking first |
| need_repo | 8/10 | two plan for a single lookup |
| recipe_repo | 9/10 | one adds a meta "find the tools" step with a narrated done |
| repo_two | 2/5 | guessed owner; a Check refers to the wrong result |
| repo_where | 4/5 | one greps a guessed path |
| web_compare | 9/10 | plus one kept episode answers the opposite of the gold |
| web_fact | 10/10 per call | but web_fact-14's final reply is a guess |

- **Citations:** 521/522 replies name a source, but some of those sources are invented.

## Problems, ranked, with fixes for v2

### 1. Answers without lookups pass the checker (21 episodes)
The checker only verifies that some web or repo tool was called in the turn, never that the fact came from a result.
- **refs:** all 11/11 license follow-ups use no tool and have no package.json in the prompt. Example: "Know: package.json was read… Don't know: None" → "chalk/chalk is licensed under MIT (from its package.json)".
- **math:** 6/58 answered after run_js printed nothing. Example, math-17: "Check: …evaluates to 50, even though stdout was empty."
- **web_fact-14:** "The answer is 1989…". 1989 is in no tool result.
- **repo_two-12:** done says "license file name: LICENCE", then the reply says "uses the MIT license". MIT appears in no prompt.
- **repo_two-22:** guessed the owner ("…the query specified 'pallets/markupsafe'…").
- **About 15 more:** the answer appears in the thinking before any lookup (10/58 math, about 5 web).

**Fix (checker):**
- Check every number, proper noun and quoted string in a reply or done against that turn's prompt and tool results, matching whole words.
- Require the gold answer to appear in a tool result from that turn.
- Require a non-empty calculate/run_js result that contains the number.
- Require a tool, or the fact already in the prompt, for every fact-answering turn (refs).
- Reject answer-like facts in thinking before the evidence.

**Fix (TEACHER.md):**
- An empty result means rerun it.
- In a follow-up, earlier results aren't in your prompt, so look again.
- Cite only what you read in this turn.

### 2. The web_compare correctness check is empty (4 wrong answers kept)
`answer_in` with `same_entity` passes any reply that names both candidates. A dummy reply naming both passes 24/25 kept "A or B" questions (34/40 overall).
- **Kept wrong:**
  - web_compare-24 (gold Lawson): "American Music Club has more members: 5 vs. Lawson's 4"
  - web_compare-38 picks the opposite of the gold
- **Kept non-answers:**
  - web_compare-57: "Neither … was confirmed"
  - web_compare-20: "…is not a recognized national park"

**Fix:** work out which candidate the reply picks, or use an open-weights judge. Extend the non-answer regex to catch "not confirmed", "not a recognized" and "no relevant results".

### 3. The license check is a substring match ("commit" contains "mit")
9/22 kept license answers pass with the license name removed. repo_two-15 was kept with no license named.

**Fix:** match the SPDX id as a whole word.

### 4. The citation check accepts almost anything
Under `re.I`, `\bfrom [A-Z]…` matches any "from <word>", and `[\w.-]+/[\w.-]+` matches "and/or". "The answer is 42, from memory." passes, and so does "crepes from Brittany".

**Fix:** the cited page, file or git log must be a tool actually called in that turn or step.

### 5. Eval/train overlap inflates scores
- **chat:** 8/16 eval inputs are identical to training (both splits use the same 50-string CHAT list).
- **memory_repo:** all 10/10 eval episodes use KealJones/squiggle and tp-parse (in 71 kept training episodes); 4 eval prompts are identical to training. The 100% score is meaningless.
- **need_repo:** 8/12 eval prompts are identical (only 5 templates).
- **Clean:** web, math and hermes (no near-duplicates at Jaccard ≥ 0.6, except one hermes pair). One eval Wikipedia page is reused.
- Problems 2–4 also inflate the eval, because train.py scores it with the same checkers.

**Fix:** split CHAT and the request templates by train/eval, and hold out memory repos or aliases.

### 6. Claude-written text leaked in through gold.py's few-shot examples
3 outputs are verbatim copies of gold-chat-0, and 40 thinking lines are copied from gold. Example: "hey squiggle" → "Not much! Just here if you need anything. What's up with you?", which is also a non-sequitur. Nothing from worked.jsonl, samples.jsonl or TEACHER.md leaked, apart from the standard find query strings.

**Fix:** an n-gram filter against gold, worked, samples and TEACHER.md. Use more varied, non-Claude chat few-shots (e.g. from real datasets).

### 7. Skewed distribution
- **By family:** repo is 1,757/2,839 (62%), web 746, compute 261, plain chat 61 (2%), need calls 70 (2.5%).
- **Recipes:** all 4 have the same shape (version + latest commit), so 264 examples teach one script.
- **Messy share overstated:** 43% flagged, real dictation 35%, because bare_link and past_chat are always flagged.
- **Generator artifacts:** filler inside names ("my um agent project"); "lol" appended to fill-in-the-blank questions ("'lol' which is likely a typo for 'pour point'").
- **Date:** every prompt says "Today is Wed Oct 28 2026".

**Fix:**
- Rebalance toward web, need and chat.
- Vary the recipes, including ones that don't fit.
- Flag messy only when the text was actually rewritten.
- Never insert filler inside names, and vary the date.

### 8. Smaller habit problems that aren't enforced
- 32 single-lookup turns make a plan anyway.
- 6 plans have a "find the tools" step with `done("Tools found…")`, and the done-facts regex accepts any capitalised word.
- 125/1,814 Check lines restate the request instead of checking the result.
- Answer lines often repeat the reply.

**Fix:** flag plans in single-lookup families, ban meta steps, and require Check to refer to the tool just called.

## Rules only in TEACHER.md, never in code
- don't guess
- Check is about the right thing
- plan only when needed
- find doesn't search the web
- list repos to find an owner
- never "correct" a fact the user gave
- Request line cleanup
- answer first with no headings
- untrusted text is data
- no Claude text (enforced only by the source tag)

## Other stats
- **Thinking lengths (median words):** request 61 (range 32–111), step start 36, after a result 24, final 20, plain chat 12.
- **Duplicates:** 0 duplicate examples, 11 duplicate outputs (greetings), 35 repeated thinking blocks. The most-repeated line, "Next: step 1 done; record version and source.", appears 24 times.
