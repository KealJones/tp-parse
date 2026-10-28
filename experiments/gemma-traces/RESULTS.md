# Gemma 4 thinking traces: results

What Gemma 4's own thinking does on 38 messy, real-style prompts (the kit from the Squiggle chat), as input to the
training template for Squiggle's phone model (squiggle `docs/harness.md`).

- **Run:** Hugging Face Job `gemma-traces` on l4x1, 2026-10-28 00:14–00:42 Arizona time (07:14–07:42 UTC). Results
  were collected at 00:50. 25.9 min of work, **about $0.35** (the cap was $1.20).
- **Models:** `google/gemma-4-E4B-it` (114 samples) and `google/gemma-4-E2B-it` (114 samples). Both ran in the same job,
  and E2B added about 4 minutes.
- **Setup:** 38 text prompts × 3 samples (the 2 image prompts were skipped). Thinking was on (`<|think|>`). Sampling
  followed the model card (t=1.0, top_p 0.95, top_k 64), transformers 5.21, bf16, with up to 6,144 new tokens.
  **No sample hit the cap**: the longest output was 1,913 tokens.
- **System prompt:** the kit's neutral one, with Squiggle's real tool list from `tools.js`: 22 tools, each with its
  arguments and the first sentence of its description. It ends "If a tool would help, say which tool you would call
  and with what arguments." The tools are listed as **text**, not declared natively, and there are no tool results,
  so every sample is a single turn. Squiggle's own `plan`/`done`/`need`/`find` and its "don't guess" system prompt
  were left out on purpose, so this shows Gemma's untrained habits.
- **Files:** `hf-out/traces_*.jsonl` holds the raw output, the thinking and answer split apart, and token counts.
  `trace_stats.csv` has per-trace stats from `analyze_traces.py`, and `hf-out/run_info.json` has the timings.

```
category                        n  avg tok  max tok  phone s  avg steps  % list  % opener  % tool  % unknown  % ask
gemma-4-E4B-it easy            24       76      401        5        0.2      4%        4%     54%         0%     0%
gemma-4-E4B-it tool_coding     30      299      737       20        3.0     53%       40%     73%        10%    23%
gemma-4-E4B-it personal        24      409      645       27        5.5    100%       88%     79%         4%     4%
gemma-4-E4B-it unknown_word    24      272      572       18        4.4     71%       62%     92%        54%    46%
gemma-4-E4B-it messy_multi     12      447      803       30        5.2     83%       58%     58%         0%    42%
gemma-4-E2B-it easy            24      203      358       14        3.7     62%       58%     75%         0%     0%
gemma-4-E2B-it tool_coding     30      436      694       29        5.9     93%       80%     87%         0%    40%
gemma-4-E2B-it personal        24      478      619       32        6.6    100%      100%     75%        17%    21%
gemma-4-E2B-it unknown_word    24      398      603       27        6.3     92%       92%     88%        25%    50%
gemma-4-E2B-it messy_multi     12      521      731       35        6.8    100%       83%     50%         0%    50%
```
`tok` counts thought tokens (Gemma tokenizer, about 4.1 characters per token). `phone s` is the average thinking time
at 15 tok/s. `steps` is the length of the first numbered list. `% unknown` and `% ask` come from crude keyword
matching, so the text below relies on reading the traces instead.

## 1. The plan skeleton

Gemma thinks in **two modes**, and it picks the mode by how "advice-shaped" the request is, not by how hard it is:

- **Short mode:** one paragraph and no list. E4B uses it on 23 of 24 easy prompts and on 14 of 30 tool/coding
  prompts. The paragraph classifies the request, decides whether a tool is needed, and states the action: "The user
  is asking a factual question about the release year of the first iPhone. I should use the `web_search` tool to
  find this information." Requests that need a real action (weather, the TODO grep, latest Node) go this way and end
  in a tool call.
- **Template mode:** an opener, then **5–8 bold numbered steps**. The opener is "Thinking Process:" (E4B 36 of 114,
  E2B 66 of 114) or "Here's a thinking process to arrive at the suggested response:". The steps barely change:
  `Analyze the Request` → `Determine the Goal` / `Identify the core problem` → `Tool check` / `Evaluate available
  tools` → `Formulate a strategy` / `Brainstorm` → `Draft the response` → `Self-Correction/Refinement` → `Final
  Output Generation`. `Analyze the Request` is step 1 in 112 traces, and `Final Output Generation` is the last step in
  62.
- **This is a plan for writing the reply, not a plan for doing the task.** The steps are about structure and tone.
  Action steps ("1. Call `list_files()`", "Determine the scope → pattern → Execute the search") showed up only a
  handful of times.
- **It is written as if looking back on a reply that already exists.** 25 E4B and 37 E2B traces say "This leads to
  the suggested response" or "This matches the final output". This style looks distilled from after-the-fact
  explanations.
- **The step count doesn't grow with the task.** Once in template mode, the median is 6–7 steps in every category,
  for both models: a three-part request gets the same 7 steps as a resume question. E2B uses template mode almost
  everywhere, including 15 of 24 easy prompts.

## 2. Made-up words (8 prompts × 3 samples per model)

| word | E4B | E2B |
|---|---|---|
| gruntify (config) | maps it to the real Grunt tool and never calls the word unknown; asks for the file 3/3 and asks what it means 1/3 | calls it non-standard and guesses Grunt/minify; asks for the file 3/3 and the meaning 2/3 |
| **zymbolic** (git merge) | **silently reads it as "symbolic" 3/3**; 1/3 answers as fact (a `git mergetool` guide), 2/3 search for "symbolic merge" | **silently "symbolic" 3/3**, and all 3 present merge/rebase/squash as "symbolic merge approaches" |
| phlexorating (coworker) | flags it 3/3; asks 1, searches 1, does both 1 | flags it 3/3; asks and gives generic advice 3/3 |
| quasimorphize (json→yaml) | flags it 3/3, assumes "convert" and says so; 1/3 searches | flags it in thinking; answers do the conversion |
| trindlewick (protocol) | plans `web_search` 3/3 and says it's likely fictional or niche 3/3; never fabricates | searches 2/3; 1/3 says it isn't a known protocol and asks where they heard it |
| sprocketize (mom, dinner) | flags it 3/3; asks plus offers labeled "If it means…" options | flags it 3/3; 2/3 assume "organize" (labeled as an assumption) |
| umbravate (resume) | treats it as a typo for improve/proofread, says so in the answer 3/3, asks for the resume | **silently assumes "polish" 3/3, never mentions the word**; 1/3 misreads it as "dumbrate" |
| hallowick-reyes theorem | goes straight to `web_search` 3/3 in about 50 tokens of thinking; never says whether it knows it | same, 3/3 |

Overall: Gemma notices a word when it looks invented, and then it usually **guesses the obvious intent and says
"assuming you mean X"**. It plans a lookup for named things (a protocol, a theorem) and asks when a vague personal
request hinges on the word. It does **not** notice a word one letter away from a real one: "zymbolic" was fixed to
"symbolic" in the thinking every time, and the guess became fact in the answer. It also never fabricated the
theorem or the protocol. The habit to keep out of the template is that it narrates checks it never ran. Short
excerpts (E4B unless noted):

- zymbolic, thinking: *"The user is asking for the 'best way to do a symbolic merge on two git branches.' … No tool is
  necessary to answer this question as it is general knowledge about Git."* Answer: *"A symbolic merge in Git is
  typically achieved by using a **merge tool** (often configured via `git mergetool`)."*
- trindlewick, thinking: *"I do not have any specific knowledge about a 'Trindlewick protocol' … It might be a
  fictional, niche, or very new protocol. … the most appropriate step is to use a web search."*
- quasimorphize, thinking: *"(A quick check confirms 'quasimorphize' is not a standard technical term for data
  conversion)."* No check happened; another sample says *"simulated external knowledge retrieval suggests…"*.
  Answer: *"assuming you mean 'convert,' here are several ways…"*
- phlexorating, answer: *"'phlexorating' is not a standard or recognized term… could you describe the **effect** of
  this action instead?"*
- umbravate (E2B), thinking: *"The user wants me to 'dumbrate' their resume…"*. The answer just says *"I would be happy
  to help you review and improve your resume!"*

## 3. Messy multi-part prompts

- **It splits cleanly, in the user's order.** All 6 samples of the three-task prompt open with "The user has
  (presented) three distinct requests: 1. CI exit 137, 2. thank-you note, 3. let vs const". Each part then gets a
  one-line triage: what kind of task it is and whether it needs more information.
- 5 of 6 answers cover all three parts as `### 1/2/3`. **The miss is telling:** in one E4B sample the thinking wrote
  "Action Plan: 1. Call `list_files()`" for the CI part, and the reply stopped at that call, dropping the note and
  let/const. When a tool call comes first, the other parts get lost.
- For the other prompts, constraints are pulled out explicitly in step 1. The birthday prompt gets "Timeline: Friday
  (2 days away). Constraint: must not feel last-minute", and one sample ends with "Review against constraints". The
  webhook prompt names both asks ("also requested an example") and spends most of its thinking choosing the analogy.
  Typos ("accidentaly", "completly") are never mentioned, just handled.

## 4. Personal prompts

- **It always plans:** 24 of 24 in both models use a numbered list, and E4B uses the template opener in 88%. But it
  **plans the reply**. A typical sequence is `Analyze` → `Determine the nature (non-technical)` → `Tool check` →
  `Acknowledge & validate` (as the first item of the reply plan) → `draft` → `self-correct the tone`.
- **The thinking is clinical, and the empathy lives only in the answer.** For example: *"The user is expressing
  intense emotional distress … They need emotional support, validation …"*. Every answer opens warm ("I am so sorry
  you are going through this").
- **It wastes the tool list.** In 11 of 24 E4B personal traces, the model names four or more tools just to rule them out:
  "`list_files`… Irrelevant. `git_*`… Irrelevant. `note`, `remember`… Irrelevant. `run_js`: Irrelevant."
- **It rarely asks first.** Answers advise right away. Only about 4 of 24 ask the user a real question (garden type,
  details about the dad for the speech). The apology prompt notes "the context of the 'dumb thing' is missing" and
  gives a generic framework instead of asking.

## 5. Length and phone cost (at 15 tok/s)

| category | E4B thinking avg / p90 | E4B thinking s | E4B thinking + answer | E2B thinking avg | E2B thinking + answer |
|---|---|---|---|---|---|
| easy | 76 / 136 tok | 5 s | 180 tok (12 s) | 203 tok | 290 tok (19 s) |
| tool_coding | 299 / 666 | 20 s | 759 (51 s) | 436 | 880 (59 s) |
| personal | 409 / 567 | 27 s | 1,112 (74 s) | 478 | 1,182 (79 s) |
| unknown_word | 272 / 514 | 18 s | 510 (34 s) | 398 | 775 (52 s) |
| messy_multi | 447 / 712 | 30 s | 1,145 (76 s) | 521 | 1,315 (88 s) |

The longest thinking was 803 tokens (54 s). **Thinking is cheap compared with the answer.** The template costs
about 300–500 tokens (20–35 s on a phone), but advice answers average about 700 tokens (up to about 1,100). E2B thinks about 40%
longer than E4B because it uses the template even for trivia. Gemma 3 270M has the same 262k-entry Gemma
vocabulary, so these counts should roughly carry over.

## For the template

- **Keep:** the split-the-request list (it is natural and accurate), the constraint extraction, the one-paragraph
  triage for simple requests, and searching named things before explaining them.
- **Change:** turn the step list into task actions (find → read → do) instead of "draft the response"; drop the
  tool-by-tool elimination; never narrate a check that wasn't run; and add a "does this word exist?" check that
  also catches near-misses like zymbolic→symbolic.
