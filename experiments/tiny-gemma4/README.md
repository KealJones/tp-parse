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
