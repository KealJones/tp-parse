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
