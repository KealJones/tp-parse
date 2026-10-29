# Tiny Gemma 4

Goal (Keal, 2026-10-28/29): a Gemma 4 small enough for an iPhone browser tab (wllama, CPU), by surgery on
Gemma 4 E2B plus a short heal (distillation from Gemma itself; no Claude-written data).

Plan, from the "Model compression and vocab pruning" chat: vocab ~262K → ~80K (chosen from public text),
drop the middle layers that change the residual least (keeping the KV-source layers the shared layers reuse),
narrow the FFN, later hidden 1536 → 1024; heal on ~85% generic text, ~10% chat, ~5% Squiggle-format prompts.
Gemma 4 has no MatFormer nesting (unlike 3n), so there is no free slice.

Phone measurements that set the target (2026-10-28, iPhone Safari, wllama 3.8.1 compatibility build):
a tab survived ~1.9 GB; speed tracks the body size (Squiggle Small 350M: 16-18 tok/s on 4 cores or GPU;
Qwen3 0.6B: 9.3 tok/s on 4 cores). wllama's llama.cpp (b11364) supports gemma4.

## Stage 1 (`stage1.py`, no training)

Bits per byte on held-out FineWeb-Edu, code (codeparrot) and Squiggle teacher episodes for: full E2B-it,
pruned vocab, vocab + skipped layers, vocab + narrower FFN, combinations; LFM2.5-350M and Qwen3-0.6B as
baselines. Writes `results.json`, `RESULTS.md`, `kept_ids.json`, `tokenizer_pruned.json`.

Keal's own token list (keal_tokenizer) is private and is not used here; its coverage is checked offline.

### Stage 1 results (2026-10-29, l4x1, 7.6 min, ~$0.15) — `hf-stage1/`

Bits per byte (lower is better), no healing:

| config | web | code | Squiggle | total params |
|---|---|---|---|---|
| full E2B-it | 1.42 | 1.03 | 1.59 | 4.63B |
| vocab 80K | 1.45 | 1.05 | 1.59 | 2.72B |
| vocab + FFN 66% | 1.51 | 1.29 | 1.42 | 2.19B |
| vocab + FFN 42% | 1.70 | 1.53 | 1.56 | 1.81B |
| vocab + skip 6 | 2.27 | 3.25 | 3.41 | 2.20B |
| vocab + skip 10 | 2.91 | 4.12 | 4.00 | 1.89B |
| vocab + skip 17 | 6.60 | 8.73 | 9.31 | 1.38B |
| LFM2.5-350M | 1.31 | 1.51 | 2.07 | 0.35B |
| Qwen3-0.6B | 0.92 | 0.56 | 1.07 | 0.60B |

- The vocab cut is nearly free: ~99.2% of counted text covered, +1% tokens, samples identical, 4.63B → 2.72B.
  (Offline: 2.0% of Keal's own writing uses tokens outside the 80K, mostly emoji and slang.)
- Layers that change the residual least are 25–33, the KV-shared ones; skipping them breaks the model before
  healing (garbled samples from skip 6 on). FFN 66% still writes correctly; FFN 42% collapses ("model\nmodel…").
- The scorer matches transformers' own loss exactly (checked on a tiny random Gemma 4).
- Qwen3-0.6B models raw text far better than E2B-it (partly because E2B-it is chat-tuned).
- `surgery.py` physically cuts layers/FFN/vocab; verified identical to the simulated cuts on a tiny model.

### Heal probe (2026-10-29, a100-large, ~21 min training, `hf-heal-probe2/`)

Student: 80K vocab, layers 28–33 dropped (29 kept), FFN 42% → **1.50B params**. Distilled from uncut E2B-it
(KL over the kept vocab + 0.1 × next-token loss), batch 4 × 1024, lr 2e-4, ~4K tokens/s → **4.3M tokens**.
Checkpoint (bf16, 3 GB) is in the private results repo `kealjones/tp-parse-runs` under
`tiny-gemma4-heal-probe2/6ae3018c3fb22a235dd557a6/ckpt/` (too big for git).

| | web bpb | Squiggle bpb |
|---|---|---|
| teacher (E2B-it, 80K vocab) | 1.49 | 1.58 |
| student, cut, before healing | 2.66 | 2.84 |
| step 150 (0.6M tokens) | 1.47 | 0.88 |
| step 600 (2.5M tokens) | 1.31 | 0.59 |
| end, step 1062 (4.3M tokens) | 1.24 | 0.54 |

Read with care:
- **Squiggle bpb is contaminated**: teacher episodes share long, near-identical harness prompts, and the training
  mix cycled the other ~150 episodes many times, so the student memorised the harness text. Hold out whole
  episodes and strip shared system prompts before using this number.
- **Student < teacher on web** means it is learning raw web text (the 0.1 next-token term) rather than staying
  faithful to the chat-tuned teacher. No chat samples were taken, so it's unknown how much instruction-following
  survived. Next time: KD only (or much smaller CE weight) and greedy chat samples at every eval.
- Real signal: un-healed garbage (2.66) recovers past the teacher's raw-text level within ~0.6M tokens.
- 1.5B total (body ~0.8B) is still too slow for the phone target; the body needs to come down to ~0.2–0.4B.

Cost: stage 1 $0.10; probe 1 $1.25 (crashed at 2 min on zero-padded per-layer config keys, then hung on
streaming threads until the 30-min limit; both fixed: `surgery.py` key parsing, hard `os._exit` in both
scripts); probe 2 $1.11. Total **$2.46**.

Next, if continuing: (1) fix the eval (episode-level hold-out, chat samples, KD-only); (2) try a smaller
student (drop more of 25–33 plus FFN ~35%, body ~0.4B); (3) only then a longer heal on an H200.
Also compare against simply fine-tuning Qwen3-0.6B, which already runs at 9.3 tok/s on the iPhone and scores
far better than E2B-it on raw-text bpb.

### Stage 1b: direct importance, Minitron-style (2026-10-29, l4x1, 10.7 min, ~$0.15) — `hf-analyze/`

Per-layer removal (bpb change on web / Gemma replies, one layer at a time) disagrees with stage 1's angular-distance
proxy. Harmless or slightly helpful to remove: **12, 11, 2, 6, 7, 9** (12 and 11 lower web bpb by ~0.19).
Costly: **1 (+1.6), 3 (+1.6), 4 (+0.55), 23 (+0.53), 33 (+0.33)**. Layers 25–32 cost little one at a time;
stage 1's "skip 6" also removed 33, which is part of why it collapsed. Top 1024 of 1536 hidden channels carry 75%
of the activation mass.

Width-heavy candidates, physically cut, before healing (teacher web 1.47 / code 1.08 / Gemma replies 1.61):

| candidate | body | total | web | code | replies |
|---|---|---|---|---|---|
| FFN 50% | 1.10B | 1.94B | 1.63 | 1.69 | 1.86 |
| hidden 1280, FFN 50% | 0.92B | 1.73B | 1.70 | 1.85 | 1.91 |
| hidden 1024, FFN 50% | 0.73B | 1.53B | 2.12 | 2.42 | 2.43 |
| hidden 1024, FFN 42%, drop 2/6/11/12 | 0.60B | 1.31B | 2.46 | 3.71 | 3.18 |
| hidden 1024, FFN 35%, drop 6 | 0.50B | 1.17B | 3.09 | 5.19 | 4.31 |
| hidden 768, FFN 42% | 0.49B | 1.27B | 2.64 | 3.62 | 3.43 |

Most of the remaining "total" is per-layer embeddings (80K × layers × 256 ≈ 0.6–0.7B): cheap lookups, but memory.
Shrinking or dropping them is the next lever after the body.

**Heal 1** (`hf-heal1/`): hidden 1024, FFN 42%, layers 2/6/11/12 removed (0.60B body), distillation only.
Result (a100-large, 68.8 min, $2.87, 16M tokens, KD only): web bpb 2.58 → **1.34** (teacher 1.49), Gemma replies from
held-out episodes 3.13 → **1.14** (teacher 1.61: the student learns Squiggle's format, which E2B-it never saw).
Greedy chat samples went from blank lines to chat-shaped answers that drift and loop ("The capital of France is
**Gemma de France…", "The sky is a blue and the sky is a blue."): 85% raw web teaches text, not answering.
Checkpoint: `kealjones/tp-parse-runs` → `tiny-gemma4-heal1/6ae32a7041e90535df78a3ff/ckpt/` (bf16, 2.6 GB).

**Heal 2** (`hf-heal2-chat/`): continue from heal 1 with 35% OpenAssistant oasst1 chat contexts (human-written,
Apache-2.0; distillation targets come from the teacher), lr 1e-4, ~22 min.
Result (a100-large, 22.8 min, $0.95, 4.9M tokens): web 1.34 → 1.34, Gemma replies 1.14 → 1.11. Greedy samples now
answer like an assistant ("The capital of France is **Paris…", "Here is a Python function that reverses a string.
```python def reverse_string…", "Here is a breakdown of why the sky is blue…") but still drift into wrong facts and
repetition. Checkpoint: `kealjones/tp-parse-runs` → `tiny-gemma4-heal2-chat/6ae33bbe41e90535df78b7d7/ckpt/`.

### Where it stands (2026-10-29 morning)

- A 0.60B-body Gemma 4 (1.31B total, 80K vocab, hidden 1024, FFN 42%, 31 of 35 layers) heals well on text
  (bpb below the chat-tuned teacher's) after ~21M tokens, and has started answering in chat form, but is far
  from coherent. Minitron-scale heals use billions of tokens; this was ~0.02B.
- Spend for this stretch (Keal's $5): analysis $0.15, heal 1 $2.87, heal 2 $0.95 = **$3.97**. Earlier tonight:
  stage 1 $0.10, probes $2.36.
- Next options: (1) a longer heal on an H200 (~3× A100 throughput per the earlier estimate) with ~30% chat
  contexts, ~$5 per hour → ~300–400M tokens; (2) drop or shrink the per-layer embeddings (most of the 0.7B
  non-body parameters) to cut phone memory; (3) GGUF export of the checkpoint and a phone test (needs llama.cpp's
  converter to accept the cut config and the 80K tokenizer). Samples should use a repetition penalty when judging
  quality, as the app does.

### Heal 3: E2B's own answers (2026-10-29, h200, 78 min, ~$6.55) — `hf-heal3b/`

On-policy data first (`gen.py`, Gemma 4 E2B-it on vLLM answering questions only, never the datasets' answers):
gen2 (a100, 15 min, ~$0.61) answered 10,686 prompts (Hermes function-calling requests with their tools in
Gemma's native format + SmolTalk maths/code/general) and kept 6,395; 40% hit the 1,024-token cap. gen3 (a100,
28.5 min, ~$1.19) answered 17,000 new SmolTalk questions with a 2,048 cap and kept 14,126. Together ~20.5k
conversations (2,668 with tool calls), ~20M tokens. (gen1 failed on a missing C compiler; heal3 died in 18 s on
an old `brotli` the Hub client now needs, so the job pins `brotli>=1.2.0`.)

Heal 3 resumed heal 2: distillation only, lr 1e-4, batch 12 × 1024, mix 38% E2B answers, 10% E2B tool calls,
15% FineMath, 10% Squiggle episodes, 13% web, 7% code, 7% oasst1. 3,841 steps, 47.2M tokens.

| | web bpb | agent replies bpb |
|---|---|---|
| teacher (E2B-it) | 1.49 | 1.61 |
| heal 2 (start) | 1.34 | 1.11 |
| heal 3 | 1.33 | 1.10 |

bpb barely moved, but behaviour changed a lot:

| prompt | heal 2 | heal 3 |
|---|---|---|
| capital of France (greedy) | "The capital of France is **** France** (or ** France**)…" | "The capital of France is **Paris** (or **Parisian**).<turn\|>" — stops |
| weather in Phoenix, `get_weather` tool | "I am **not a large language model…" | `<\|tool_call>call:get_weather{city:<\|"\|>Phoenix<\|"\|>}<tool_call\|>` — a correct native call |
| 17 × 23 | "Please provide the answer…" | "**1. Set up the equation** … 17 × (20 + 3) = …" |
| reverse a string | broken signature | "Here are a few ways… 1. Using `reversed()`" |

Still wrong in places (the sky "reflects light from the sun"; greedy decoding repeats `<|tool_response>`
after a call, which the runtime should stop on). Checkpoint: `kealjones/tp-parse-runs` →
`tiny-gemma4-heal3b/6ae371135ddcdc083026213d/ckpt/`. GGUF: `kealjones/tiny-gemma4-test`,
`tiny-gemma4-heal3-Q4_0.gguf`.

Spend for the $10 bigger-heal stretch: gen1 ~$0.16, gen2 ~$0.61, gen3 ~$1.19, GGUF builds ~$0.06, heal3 crash
~$0.05, heal 3 ~$6.55 = **~$8.62**.

### Later: vision (Keal, 2026-10-29)

The cut keeps only Gemma 4's text model: E2B's vision and audio encoders were never copied, and the GGUF has no
image projector, so tiny Gemma 4 is text-only (Squiggle's OCR still reads text in photos). E2B's vision encoder
can't simply be reattached either: its projector feeds the language model at E2B's width (1536) and the cut
model is 1024 wide. To bring vision back: slice the projector's output to the kept hidden channels (the same
`hidden_keep` indices as `surgery.cut`), then heal on image–text pairs with E2B as the teacher, and export the
encoder + projector as a llama.cpp mmproj file for wllama. Its own project; on the list for after the text heals.
