# Making a small, curated context more useful than a huge one (for a ≤500 MB model)

Note on verification: items marked **[fetched]** were checked against the source during this session (Oct 2026). Items marked **[recall, not re-fetched]** come from the researcher's prior knowledge of the paper. They are linked to the primary arXiv page, but the report writer should treat their exact numbers as needing a check before quoting.

## Q1. How do models degrade with long or noisy context, and what is the effective context length vs the claimed one (especially for small models)?

### Takeaway
Every benchmark finds that accuracy drops as input grows, often well before the claimed window. The drop is worse when the needed fact is not lexically matched to the question, when similar distractors are present, and when the model is small. A focused ~300-token prompt beat a ~113k-token prompt for every model Chroma tested. For a sub-1B model, the evidence points toward a few thousand well-chosen tokens rather than "fill the window".

### Cited Findings
- **RULER** (13 synthetic tasks; "effective" length means staying above Llama2-7B's 4K score of 85.6%). Llama3.1-8B claims 128K but is effective only to 32K (95.5 at 4K, 77.0 at 128K). Mistral-v0.2-7B claims 32K, is effective to 16K, and falls from 93.6 at 4K to 13.8 at 128K. LWM-7B claims 1M but scores below the threshold even at 4K (82.3). Together-7B and LongChat-7B, both claiming 32K, score 0.0 at 64K. GPT-4 claims 128K and is effective to 64K. **[fetched]** — [RULER, Hsieh et al. 2024](https://arxiv.org/html/2404.06654v3)
- RULER: "almost all models exhibit large performance drops as the context length increases." In the Yi ablation, 34B is "significantly better" than 6B at both 4K and in relative degradation, so size helps with long context. Failure modes at long lengths: copying verbatim from the in-context example (Yi, LWM, LongAlpaca, almost never seen at short lengths), and ignoring the context in favour of priors (Mistral returns common words like "the" instead of counting). **[fetched]** — [RULER](https://arxiv.org/html/2404.06654v3)
- RULER tested nothing under 7B. No sub-2B effective-length numbers came from this source. **[fetched]** — [RULER](https://arxiv.org/html/2404.06654v3)
- **NoLiMa** (needle and question share minimal lexical overlap, so the model must make a latent association): of 12 models claiming ≥128K, 10 fall below 50% of their short-context baseline by 32K. GPT-4o drops from 99.3% to 69.7% at 32K. **[fetched]** — [NoLiMa, Modarressi et al. 2025 (ICML)](https://huggingface.co/papers/2502.05167)
- **Chroma "Context Rot" (July 2025)**: 18 models (Anthropic, OpenAI, Google, Qwen including Qwen3-8B) and 194,480 calls. Findings:
  - Low needle–question similarity degrades faster with length.
  - Even one distractor hurts and four compound the damage; some distractors are worse than others and show up in hallucinated answers.
  - Shuffled (incoherent) haystacks beat coherent ones for all 18 models.
  - On **LongMemEval**, focused prompts (~300 tokens) scored significantly higher than full prompts (~113k tokens) for every model.
  - On a repeated-words copy task, output degraded as length grew; Qwen3-8B began producing random output around 5,000 words.
  - Most exact accuracy values appear only in charts. **[fetched]** — [Chroma Context Rot](https://www.trychroma.com/research/context-rot)
- **Lost in the Middle**: accuracy is U-shaped in the position of the relevant document. With 20 documents, GPT-3.5-Turbo's multi-document QA accuracy with the answer in the middle fell below its closed-book (no-document) accuracy of about 56%, while position 1 scored about 75%. **[recall, not re-fetched]** — [Liu et al. 2023](https://arxiv.org/abs/2307.03172). The LongLLMLingua paper independently reports GPT-3.5 NQ original-prompt scores of 75.7 with the answer at position 1 vs 57.3 at position 5, which corroborates the size of the gap. **[fetched]** — [LongLLMLingua](https://www.alphaxiv.org/abs/2310.06839.md)
- **Shi et al. 2023, "LLMs can be easily distracted by irrelevant context"** (GSM-IC): adding one irrelevant sentence to grade-school math problems sharply cut accuracy. Instructing the model to ignore irrelevant information, self-consistency, and few-shot examples that contain distractors partly recovered it. **[recall, not re-fetched; exact numbers not verified]** — [Shi et al. 2023](https://arxiv.org/abs/2302.00093)

### Inferences
- If a 7–8B model's effective length is 16–32K, a 135M–500M model's useful window is likely much shorter. RULER's size ablation and its 7B collapse both point this way. Plan around roughly 2–8K tokens of high-relevance content, then measure.
- Distractors that are similar to the answer are the most harmful kind of noise. Near-duplicate memories or retrieved chunks are therefore worse than plainly unrelated text, so dedupe and filter for similarity, not only for relevance.
- Chroma's finding that shuffled beats coherent suggests that structure in a long context can pull attention away from the needed fact. Clearly delimited, separated chunks may help.

### Gaps
- No primary-source effective-length numbers (RULER/NoLiMa) were found for sub-2B models such as SmolLM2, Qwen3-0.6B, LFM2-350M or Gemma-3-270M. The harness author should run RULER or NoLiMa at 1K/2K/4K/8K on his own model.
- Chroma publishes most numbers only in charts.

## Q2. Which methods compress, select or restructure context so a small model uses it well, and what do they cost in accuracy?

### Takeaway
Query-aware hard compression (LongLLMLingua) can raise accuracy while removing about 75% of tokens, because it removes distractors and fixes position bias. It is also model-agnostic. Soft and learned compression (gist, ICAE, xRAG, 500x) reaches higher ratios, but needs training tied to one specific decoder and loses 25–40% of capability at extreme ratios. Attention-based KV eviction shows that only a small fraction of tokens carry most of the attention mass.

### Cited Findings
- **LongLLMLingua** (question-aware coarse-to-fine compression plus document reordering), GPT-3.5-Turbo on NaturalQuestions:
  - Up to +21.4% accuracy with about 4x fewer tokens when the gold document is at position 10.
  - At 4x compression, accuracy stays in a stable ~70–75 band across all positions; the uncompressed prompt scores 75.7 at position 1 and 57.3 at position 5.
  - LongBench: 48.3 at 6x compression vs 44.0 uncompressed (~10.3K tokens).
  - Cost cut by 94% on LooGLE; latency improves 1.4–2.6x.
  - Results tables go no higher than 6x. **[fetched]** — [LongLLMLingua, Jiang et al. 2023](https://www.alphaxiv.org/abs/2310.06839.md)
- **Survey of prompt compression** (Li et al. 2024/25):
  - LLMLingua reaches up to 20x, but it needs a separate small LM, which adds memory and may use a different tokenizer.
  - Gist tokens reach up to 26x but are limited by the short prompts used in fine-tuning, and they cannot be used with the untuned model.
  - ICAE compresses 512 tokens into 32/64/128 (4–16x); the survey flags possible Pile train/test leakage.
  - xRAG compresses a retrieved document into a single token for QA, using two LLMs plus a projector.
  - 500xCompressor reaches 6–480x while retaining 62.26–72.89% of uncompressed capability.
  - Soft-prompt encoders "are specific to the corresponding decoder LLMs" and must be retrained when the decoder changes. Hard-prompt methods transfer between models.
  - A compressor about the size of the decoder can make compression as slow as reading the original prompt. **[fetched]** — [Prompt Compression Survey](https://arxiv.org/html/2410.12388v2)
- **H2O**: keeping a KV cache of 20% "heavy-hitter" tokens plus recent tokens preserves quality, with up to 29x throughput and 1.9x lower latency (OPT, LLaMA, GPT-NeoX). This shows that attention mass concentrates on a small subset of tokens. **[fetched]** — [H2O, Zhang et al. 2023](https://arxiv.org/abs/2306.14048v2)
- **SnapKV**: an observation window at the end of the prompt, usually the question, predicts which prefix tokens each head will attend to during generation. This enables query-aware KV selection with little loss on LongBench. **[recall, not re-fetched; numbers not verified]** — [SnapKV, Li et al. 2024](https://arxiv.org/abs/2404.14469)
- **RECOMP**: extractive and abstractive compressors summarise retrieved documents before generation and may output an empty summary when the documents are irrelevant (selective augmentation). The paper reports compression to about 5–6% of tokens with small QA loss. **[recall, not re-fetched]** — [RECOMP, Xu et al. 2023](https://arxiv.org/abs/2310.04408)
- **Activation Beacon, Recurrent Memory Transformer, Infini-attention**: each condenses past context into learned memory (beacon activations, memory tokens passed between segments, or compressive memory inside attention). **[recall, not re-fetched; no numbers verified this session]** — [Activation Beacon](https://arxiv.org/abs/2401.03462), [RMT](https://arxiv.org/abs/2207.06881), [Infini-attention](https://arxiv.org/abs/2404.07143)

### Inferences
- For a harness that already controls the context, the cheapest high-value step is query-aware selection: rerank and drop chunks, put the best chunk at the start or end, and dedupe near-duplicates. This is model-agnostic and LongLLMLingua's results suggest it can improve accuracy, not just save cost.
- Running a separate compressor model (LLMLingua-style) next to a 500 MB model may cost as much memory and latency as it saves. A small cross-encoder reranker or BM25/embedding scoring is the more proportionate option.
- Soft compression (gist/ICAE/xRAG) is only worth it if the author is willing to fine-tune his own decoder and to retrain whenever he swaps base models.

### Gaps
- No verified numbers for gist tokens, ICAE, AutoCompressors or xRAG on sub-1B decoders. Most results are on 7B+ LLaMA/Mistral.

## Q3. Can context distillation, prompt baking or test-time training absorb a harness's standing instructions into a small model's weights?

### Takeaway
Yes, in principle. Prompt baking and context distillation train the unprompted model to match the prompted model's output distribution (KL), and they reduce "prompt forgetting" over long sequences. That frees context for task-specific content. Test-time training now matches full attention's scaling with context at 3B scale, but it is research-stage.

### Cited Findings
- **Prompt Baking** (Bhargava et al. 2024):
  - Minimises the KL divergence between the prompted and unprompted model to produce weights that behave as if the prompt were present.
  - Baking chain-of-thought prompts improves zero-shot GSM8K, ASDiv, MBPP, ARC-E/C and CSQA.
  - Baking instructions or personas reduces prompt forgetting over long sequences.
  - Baked models still respond to re-prompting, and iterating the process ("Prompt Pursuit") gave further gains. **[fetched]** — [Prompt Baking](https://arxiv.org/abs/2409.13697)
- Thinking Machines' Tinker documents "prompt distillation" as a standard recipe: generate with a long prompt, then fine-tune the model to produce those outputs without it. **[search result only]** — [Tinker prompt distillation](https://tinker-docs.thinkingmachines.ai/tutorials/advanced/prompt-distillation/)
- **Snell et al. 2022, "Learning by Distilling Context"**: fine-tunes a model to reproduce its own outputs from a context of instructions, scratchpad reasoning and examples, without that context, and reports that it can beat direct gradient-descent learning on the same information. **[recall, not re-fetched]** — [Snell et al. 2022](https://arxiv.org/abs/2209.15189)
- **End-to-End Test-Time Training for Long Context (Dec 2025)**:
  - A 3B sliding-window Transformer, trained on 164B tokens, keeps learning at test time by next-token prediction on the context.
  - It scales with context length like full attention, which Mamba 2 and Gated DeltaNet do not.
  - Latency stays constant in context length and is 2.7x faster than full attention at 128K.
  - Code is public. **[fetched]** — [TTT-E2E](https://arxiv.org/abs/2512.23675v1)

### Inferences
- A harness with a long, stable system prompt (tool schemas, persona, format rules) is a good candidate for baking with a cheap LoRA via KL distillation. The prompt tokens then become free context, and instruction adherence should hold up better over long sessions. Validate on the harness's own eval, because no sub-500M results were found.
- Baking does not replace retrieval for facts that change. Keep dynamic state in context.

### Gaps
- No verified prompt-baking or context-distillation results on sub-1B models. The models used in Prompt Baking were not confirmed from the fetched text.
- TTT-E2E has only been shown at 3B; its behaviour at ≤500M is unknown.

## Q4. Which architectural choices give a small model long context, and what effective context do they reach?

### Takeaway
Small hybrid models now ship with 32K windows (LFM2 has gated short convolutions plus a few GQA layers, from 350M up). Vendors rarely publish effective-length benchmarks for these models, though. Long context at small sizes is mostly unmeasured, which supports a curated-context design.

### Cited Findings
- **LFM2**: 350M, 700M, 1.2B and 2.6B dense models plus an 8.3B MoE (1.5B active). It is a hybrid of gated short convolutions with a small number of GQA blocks, found by hardware-in-the-loop search. It runs up to 2x faster prefill and decode on CPU, and all models have a 32K context. The report gives no RULER or long-context benchmark numbers. **[fetched]** — [LFM2 Technical Report](https://arxiv.org/abs/2511.23404v1)
- TTT-E2E reports that linear and recurrent hybrids (Mamba 2, Gated DeltaNet) do not keep improving with context the way full attention does, at 3B. **[fetched]** — [TTT-E2E](https://arxiv.org/abs/2512.23675v1)
- RULER results (Q1) show that architecture and training recipe matter as much as the claimed window: LWM-7B claims 1M but is effective below 4K, while GLM4-9B claims 1M and is effective to 64K. **[fetched]** — [RULER](https://arxiv.org/html/2404.06654v3)
- Gemma 2/3 interleave local sliding-window and global attention layers (Gemma 3 uses a 5:1 local:global ratio with a 1,024-token window) to cut KV memory. Qwen3-Next mixes Gated DeltaNet with gated attention at about 3:1. Jamba mixes Mamba and attention layers with MoE. **[recall, not re-fetched]** — [Gemma 3 report](https://arxiv.org/abs/2503.19786), [Jamba](https://arxiv.org/abs/2403.19887)

### Inferences
- For a ≤500 MB model, the main payoff of hybrid or sliding-window designs is a smaller KV cache and lower latency, which keeps a few-thousand-token curated context cheap. They are not evidence that 32K of uncurated context would be used well.

### Gaps
- No RULER or NoLiMa numbers were found for LFM2-350M, Gemma-3-270M, Qwen3-0.6B or Qwen3.5 small hybrids. Qwen3.5 small-model architecture details were not verified this session.

## Q5. What does agent "context engineering" practice say reliably helps, and with what evidence?

### Takeaway
Practitioner guidance from Anthropic and Manus converges on a few points:
- Treat context as a scarce "attention budget".
- Keep stable prefixes so caching works.
- Load data just in time by reference.
- Compact and summarise old history.
- Recite goals near the end of the context.
- Keep errors visible.
- Vary formatting to avoid few-shot ruts.

The evidence is mostly qualitative or cost-based; neither source gives accuracy benchmarks.

### Cited Findings
- **Anthropic (2025)**:
  - Context rot is gradual; each token draws down a finite attention budget, so aim for "the smallest set of high-signal tokens".
  - Write system prompts at the "right altitude" (neither hard-coded logic nor vague guidance).
  - Prefer a few diverse canonical examples over long lists of edge-case rules.
  - Keep tools minimal and non-overlapping, with token-efficient output.
  - Use just-in-time retrieval by reference.
  - Compact (Claude Code keeps the summary plus the 5 most recently accessed files), with clearing old tool results as the lightest form.
  - Use structured notes (NOTES.md, to-do lists).
  - Sub-agents explore with tens of thousands of tokens and return 1–2K-token summaries.
  - No benchmark percentages are given. **[fetched]** — [Anthropic, Effective context engineering](https://anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- **Manus**:
  - KV-cache hit rate is the top production metric: keep the prefix stable (no timestamps), append-only, deterministic serialisation.
  - Input-to-output ratio is about 100:1.
  - Cached input costs $0.30/MTok vs $3/MTok uncached (10x, Claude Sonnet).
  - Mask tool logits instead of removing tools.
  - Use the file system as memory, with reversible compression (drop page content, keep the URL).
  - A typical task is about 50 tool calls; rewriting todo.md puts goals at the end of the context and reduces goal drift.
  - Keep failed actions and stack traces in context.
  - Add structured variation to avoid copying repeated action–observation patterns. **[fetched]** — [Manus, Context Engineering lessons](https://manus.im/en/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus)
- Manus's few-shot-rut observation matches RULER's finding that models copy in-context examples verbatim at long lengths. **[fetched]** — [RULER](https://arxiv.org/html/2404.06654v3)

### Inferences
- For a tiny model, the following should carry over directly:
  - Recency placement (goal and question last, which also matches SnapKV's observation-window effect and the U-shaped position curve).
  - Strict deduplication of similar distractors.
  - Reversible pointers (IDs or paths) instead of full content.
  - A stable cached prefix.
- Tiny models have weaker in-context instruction retention, so baking the stable prefix (Q3) may be worth more for them than for frontier models.

### Gaps
- No controlled measurements were found from LangChain or other 2025–26 writeups in this pass; the LangChain source was not fetched. No context-engineering studies on sub-2B models were found.
