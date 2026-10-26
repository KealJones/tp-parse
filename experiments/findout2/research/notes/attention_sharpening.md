# Attention sharpening / sparsification / focusing mechanisms (2016–2026): evidence catalogue for a tiny browser model

Legend: [PR] = peer-reviewed venue; [PP] = preprint only; [BLOG] = blog/tech report; [MEM] = detail from researcher background knowledge of the paper, NOT re-verified by fetch in this session (report-writer should treat as lower confidence); [UNREP] = no independent replication found.

## Q1. For each mechanism: what changes mathematically, what improved, by how much, at what scale?

### Takeaway
Only a handful of mechanisms have evidence at ≥1B params with many tokens: gated attention (Qwen, up to 15B-MoE/1.7B dense, 3.5T tokens, peer-reviewed), Differential Transformer (up to 13B in scaling curves, peer-reviewed; V2 is an unfinished blog), and DeepSeek's top-k sparse attention (production scale, tech report). Most other "sharper attention" ideas (SSMax, softpick, selective attention, MTA, ASEntmax, stick-breaking, FoX) are validated mainly at 100M–1B, which is actually the user's target scale, but each has only the authors' own results, and softpick explicitly got *worse* at 1.8B.

### Cited Findings

**Sparsemax / entmax / adaptive sparse transformers (2016–2019, revived 2025–2026)**
- Sparsemax = Euclidean projection of scores onto the simplex, yielding exact zeros; α-entmax generalizes softmax (α=1) and sparsemax (α=2); adaptively sparse transformer learns α per head [PR, ICML 2016 / ACL 2019 / EMNLP 2019] — [Sparsemax](https://arxiv.org/abs/1602.02068); [Entmax, Peters et al.](https://arxiv.org/abs/1905.05702); [Adaptively Sparse Transformers](https://arxiv.org/abs/1909.00015). Early gains were on MT-scale models (~tens of M params), modest BLEU changes [MEM].
- ASEntmax (Vasylenko et al.): α-entmax + learnable (length-aware) temperature, so heads can move between sparse and softmax-like. Motivation: with softmax, uninformative tokens accumulate mass as length grows ("attention dispersion"/representational collapse); entmax assigns exact zeros. Reports up to 1000× length extrapolation on synthetic tasks, better perplexity trends and higher retrieval at 8× training length in LM, beats softmax, SSMax and fixed-temperature entmax; short-context performance preserved. No numeric LM results or sizes on abstract page — [arXiv 2506.16640](https://arxiv.org/abs/2506.16640v2). Accepted at ICLR 2026 [PR] — [ICLR 2026 poster](https://www.iclr.cc/virtual/2026/poster/10009641).
- Efficient entmax kernels (AdaSplash, ICML 2025) exist for GPU (Triton) [MEM] — [AdaSplash](https://arxiv.org/abs/2502.12082). No WebGPU/browser kernel found.

**Top-k attention**
- Keep only k largest scores per query, zero the rest. Older: Explicit Sparse Transformer [MEM] ([arXiv 1912.11637](https://arxiv.org/abs/1912.11637)); memory-efficient top-k attention, shown usable as drop-in at inference/fine-tune on pretrained models [MEM] ([arXiv 2106.06899](https://arxiv.org/abs/2106.06899)).
- 2025 preliminary study [PP]: decoding-only top-k (keep highest-similarity keys) on Llama-3-8B-ProLong-512k-Instruct and Qwen3-32B performed comparably or better than full attention on HELMET, LongBench v2, MATH500, GSM8K, AIME24 even at low top-k ratios; SFT of Llama-3-8B-ProLong base with 1% top-k kernel gave significant gains over the original Instruct on HELMET-8K; top-k SFT lowered attention entropy — [Native Top-k Sparse Attention study, arXiv 2512.03494](https://arxiv.org/pdf/2512.03494).
- DeepSeek Sparse Attention (DSA, V3.2-Exp/V3.2): a "lightning indexer" scores tokens and each query attends to top-k (k=2048) selected tokens; introduced by *continued training* from V3.1-Terminus (short dense warm-up training only the indexer, then sparse training) with benchmark parity and much cheaper long-context inference [BLOG/tech report] [MEM for k and training details] — [DeepSeek-V3.2 report](https://arxiv.org/pdf/2512.02556). The top-k study notes the indexer has only ~60% retrieval precision yet end-to-end performance stays strong, which the authors attribute to large scale — [arXiv 2512.03494](https://arxiv.org/pdf/2512.03494).

**Differential Transformer (DIFF V1) and DIFF V2**
- V1: attention = softmax(Q1K1ᵀ) − λ·softmax(Q2K2ᵀ), with learnable λ (exponential reparam), per-head RMSNorm; "noise-cancelling" idea. Peer reviewed (ICLR 2025 oral) — [Microsoft Research page](https://www.microsoft.com/en-us/research/publication/differential-transformer/). Headline claims: matches Transformer LM loss with ~62–65% of params or tokens (e.g., 6.8B DIFF ≈ 11B Transformer), better key-information retrieval, less hallucination in summarization/QA, fewer activation outliers [MEM numbers] — [arXiv 2410.05258](https://arxiv.org/abs/2410.05258); [The Decoder summary](https://the-decoder.com/microsofts-diff-transformer-promises-more-efficient-llms-with-fewer-hallucinations/).
- Independent from-scratch comparison at 880M/105B tokens (Meta MTA paper): DIFF avg val PPL 11.14 vs Transformer 11.25 (pretrain) and 10.89 vs 11.02 (after long-ctx FT); needle-in-haystack 4K, 4 needles: DIFF 73.8 vs Transformer 41.1; 6 needles 60.0 vs 31.9. But DIFF throughput 17.6k vs 54.3k tok/s and memory 21.6 vs 17.5 GB (unoptimized code) — [MTA paper, arXiv 2504.00927](https://arxiv.org/html/2504.00927). This is the closest thing to an independent small-scale replication of DIFF's gains.
- DIFF V2 (Jan 20 2026, Hugging Face blog, [BLOG], experiments "still running"): doubles query heads (2h) while keeping KV heads unchanged; adjacent query-head pairs share a GQA group; output = attn1 − sigmoid(λ)·attn2 where λ is projected *per token, per head*; removes per-head RMSNorm and exponential λ reparam; runs on standard FlashAttention (V1 needed custom kernel and loaded V cache twice); decoding speed claimed equal to baseline. Results: LM loss 0.02–0.03 lower than Transformer at 1T tokens on production-scale dense and a "30A3" MoE; fewer loss/gradient spikes at large LR (6e-4–1e-3); smaller activation outliers; ~25% fewer attention-module params estimated. **No downstream benchmarks, no long-context results, no mid/post-training evaluation yet** — [HF blog: diff-attn-v2](https://huggingface.co/blog/microsoft/diff-attn-v2); secondary summary [earezki](https://earezki.com/ai-news/2026-01-20-differential-transformer-v2/).
- Analysis paper (NeurIPS 2025 [PR]): attributes DIFF gains to (1) negative attention giving more expressivity, (2) reduced head redundancy, (3) better learning dynamics — [Kong, Jang, Kwak, NeurIPS 2025](https://neurips.cc/virtual/2025/poster/117087).

**Scalable-Softmax (SSMax) / attention temperature / log-length scaling**
- SSMax(z)_i = n^{s·z_i}/Σ_j n^{s·z_j}, i.e., multiply query by s·log n (n = context length, s learnable per layer/head). Fixes "attention fading" where max weight → 0 as n grows. Single 162M model, 12 layers, trained at 1024 ctx: generalizes to ~10× training length (to 20k) in loss with RoPE θ×50 and no extra training; softmax baseline fails needle retrieval beyond short contexts while SSMax keeps high accuracy at ~10× length; training loss ~0.008 lower. No variance reported, synthetic needle, [PP], [UNREP] at scale — [arXiv 2501.19399](https://arxiv.org/html/2501.19399).
- Same idea (log-n scaling of logits) has antecedents: Chiang & Cholak 2022 log-length scaling to overcome theoretical limits of softmax attention [MEM] ([arXiv 2202.12172](https://arxiv.org/abs/2202.12172)); YaRN's attention temperature for context extension [MEM] ([arXiv 2309.00071](https://arxiv.org/abs/2309.00071)). ASEntmax paper reports beating SSMax on extrapolation — [arXiv 2506.16640](https://arxiv.org/abs/2506.16640v2).

**Selective Attention (Leviathan, Kalman, Matias, Google)**
- Parameter-free change: tokens can reduce attention to earlier tokens deemed no longer needed (a soft mask accumulated over the sequence). On C4, matches validation PPL of a standard transformer with ~2× more heads and attention parameters; at equal PPL reduces attention-module memory ~16× (ctx 512), 25× (1024), 47× (2048) — [arXiv 2410.02703](https://arxiv.org/abs/2410.02703). Fetched page lists it as arXiv v2 (Apr 2025); I believe it appeared at ICLR 2025 [MEM — not confirmed]. Sizes were small decoder-only models (≤ ~1B) [MEM]. [UNREP].

**Stick-breaking attention (Tan et al., IBM/Mila)**
- Replaces softmax with a stick-breaking process: each query takes β_{i,j}=σ(score) from the most recent token backwards, remaining "stick" passed further back; implicitly encodes recency so no positional embedding needed. Reported better length generalization and competitive/better downstream results at ~1B and 3B scale, with a Triton kernel [MEM] — [arXiv 2410.17980](https://arxiv.org/abs/2410.17980). ICLR 2025 [PR, MEM]. [UNREP].

**Forgetting Transformer (FoX, Lin et al.)**
- Adds a data-dependent forget gate to softmax attention: logits get a cumulative sum of log forget-gates (down-weights distant tokens in a learned, input-dependent way); compatible with FlashAttention; no positional embedding needed. Reported better LM loss, length extrapolation and short-context tasks vs. Transformer at up to ~760M params, and retains long-context retrieval better than recurrent models (Mamba-2, HGRN2, DeltaNet) [MEM] — [arXiv 2503.02130](https://arxiv.org/abs/2503.02130). ICLR 2025 [PR, MEM]. [UNREP].

**Gated attention (Qwen team, "Gated Attention for LLMs")**
- Y′ = Y ⊙ σ(X W_θ), head-specific sigmoid gate on the SDPA output (position "G1"), X = pre-norm hidden state. >30 variants of 15B-A2.54B MoE and 1.7B dense, 400B–3.5T tokens. Best (elementwise G1) on 15A2B @400B tokens: avg PPL 6.026→5.761, MMLU 58.79→60.82, GSM8k 52.92→55.27, HellaSwag 73.07→74.64. First-token attention share 46.7%→4.8% (layer 21: 83%→4%); max activation 1053→94. Long context (YaRN to 128k): RULER 64k 37.51→66.60, 128k 31.65→58.82 (at 32k, no change: 79.50 vs 79.77). Nearly eliminates loss spikes; 1.7B/48-layer baseline diverges at LR 8e-3 while gated trains. Cost: elementwise gate +201M params on the MoE (headwise only +1.6M), <2% latency — [arXiv 2505.06708](https://arxiv.org/pdf/2505.06708). NeurIPS 2025 oral [PR] — [NeurIPS 2025](https://proceedings.neurips.cc/paper_files/paper/2025/hash/904e89bb4e632e75fb47f093b620b257-Abstract-Conference.html); [oral listing](https://nips.cc/virtual/2025/oral/130320). Adopted in Qwen3-Next / Qwen3.5 full-attention layers [MEM, not verified this session].

**Attention sinks / StreamingLLM**
- StreamingLLM: keeping KV of the first ~4 "sink" tokens plus a sliding window lets models stream to millions of tokens without perplexity blow-up; adding a dedicated learnable sink token in pretraining helps [MEM numbers] — [arXiv 2309.17453](https://arxiv.org/abs/2309.17453) (ICLR 2024 [PR]). "When Attention Sink Emerges" (Gu et al., ICLR 2025): sinks emerge from softmax's sum-to-one normalization after sufficient training; sigmoid attention without normalization avoids sinks in models up to ~1B [MEM] — [arXiv 2410.10781](https://arxiv.org/abs/2410.10781). Interpretation: sinks are a "no-op" dump; the softmax can't output "attend to nothing", which is the core reason gating/softpick/sigmoid remove them — consistent with Qwen gating results [arXiv 2505.06708](https://arxiv.org/pdf/2505.06708).

**Softpick**
- Softpick(x)_i = ReLU(e^{x_i}−1)/Σ_j|e^{x_j}−1|: exact zeros, need not sum to 1. 340M (52B tokens) and 1.8B (104B tokens fineweb-edu), from scratch. Sink rate 68.28%/41.73% (softmax 340M/1.8B) → 0%; hidden-state kurtosis 33,511→341 (340M), 74,457→2,193 (1.8B); 95–99% exact-zero attention; better low-bit quantization at 340M. **But at 1.8B worse on most tasks: SciQ 86.40→80.40, LAMBADA 49.43→43.51, Wikitext PPL 15.10→17.87; training-loss gap 0.004 at 340M vs 0.12 at 1.8B; authors say it "does not seem to scale well"; passkey retrieval only comparable; dead-head share higher** — [arXiv 2504.20966v3](https://arxiv.org/html/2504.20966v3) [PP].
- Follow-up "Underscoring the Problem: Why Softpick Fails at Initialization" (NeurIPS 2026 listing): rows with zero positive denominator at init → gradient norms >10¹²; a stop-gradient variant (forward D⁺+D⁻, backward only through D⁺) at 230M matches softpick on quantization, has fewer dead heads and more reliable passkey retrieval — [NeurIPS 2026](https://neurips.cc/virtual/2026/173816).

**Sigmoid attention**
- Replace softmax with elementwise sigmoid(QKᵀ/√d + b), b ≈ −log n crucial; FlashSigmoid kernel ~17% faster inference than FlashAttention-2 on H100; matches softmax across language/vision/speech when properly normalized/biased; instability without the bias/LayerScale [MEM] — [Apple, arXiv 2409.04431](https://arxiv.org/abs/2409.04431) (ICLR 2025 [PR, MEM]).

**Multi-Token Attention (Meta, Golovneva et al.)**
- Convolutions over queries, keys and heads so attention weights depend on several nearby q/k vectors (lets the model locate a token by multiple cues). 880M, 105B tokens SlimPajama (+10.5B long-ctx FT): avg val PPL 11.09 vs Transformer 11.25 vs DIFF 11.14; after FT 10.85 vs 11.02 vs 10.89; LAMBADA PPL 13.6 vs 17.6 (DIFF 14.9). NIAH 4K FT: 2/4/6 needles 97.6/77.7/67.0 vs Transformer 90.5/41.1/31.9 vs DIFF 95.7/73.8/60.0. **Cost (unoptimized): 59.1 GB memory vs 17.5, 11.5k vs 54.3k tok/s; incompatible with FlashAttention-style kernels** — [arXiv 2504.00927](https://arxiv.org/html/2504.00927) [PP per abstract page].

### Inferences
- Two families exist: (a) *remove the "must sum to 1" constraint / let a head output nothing* (gated attention, softpick, sigmoid, DIFF partly) → kills attention sinks and massive activations, helps stability and quantization; (b) *sharpen as context grows* (SSMax, log-n scaling, ASEntmax, top-k, selective attention, FoX/stick-breaking recency) → targets "attention dispersion" over long or noisy contexts — the user's actual problem (harness-supplied context with distractors).
- Most robust evidence-per-risk for a from-scratch tiny model: headwise sigmoid output gate (tiny cost, peer-reviewed, consistent gains at 1.7B and 15B, standard kernels). DIFF V1 has a credible independent 880M replication of retrieval gains but costs throughput unless V2-style GQA-pairing is used.

### Gaps
- Exact numbers for stick-breaking, FoX, sigmoid attention, StreamingLLM, entmax and DIFF V1 were not re-fetched; tagged [MEM].
- No public numbers on Qwen3.5/Qwen3-Next/LFM gating ablations beyond the Qwen paper; LFM hybrids not investigated.
- No downstream or long-context results for DIFF V2 exist yet (as of the Jan 2026 blog).

## Q2. Which can be retrofitted onto a pretrained model by fine-tuning, and with what results?

### Takeaway
Retrofitting evidence is thin and mostly negative or partial: SSMax swapped in after pretraining gives "some" but clearly inferior length generalization; DiffLoRA (DIFF via LoRA on Llama-3.2-1B) mostly underperforms plain LoRA; top-k attention is the most retrofit-friendly (works decoding-only and via SFT at 8B, and DeepSeek converted a frontier model via continued training). Gated attention, MTA, softpick, stick-breaking, FoX were only tested from scratch.

### Cited Findings
- SSMax after pretraining (162M): substantially better needle retrieval than softmax but noticeably worse than SSMax-from-start; switching mid-pretraining only slightly better than after; post-hoc swap also hurts short-context loss — [arXiv 2501.19399](https://arxiv.org/html/2501.19399).
- DiffLoRA on Llama-3.2-1B-Instruct (Tulu-2, 1 epoch): RAG avg (5 tasks) base 0.556, LoRA 0.601, DiffLoRA-64 0.520, DiffLoRA-32 0.508; TechQA 0.532 base vs 0.390 DiffLoRA-64; DROP −7 pts; HumanEval +11; beats LoRA on multi-value NIAH but loses on multi-key; GroupNorm variant collapses (~0.05); some degenerate outputs; attention maps barely changed; authors: "needs further investigation" — [arXiv 2507.23588](https://arxiv.org/html/2507.23588v1) [PP].
- DEX (NeurIPS 2025 [PR]): retrofits differential attention into pretrained LMs by reusing existing softmax scores and adding a lightweight differential op on the value/output side; claims <0.01% adaptation data and "substantial improvements" across benchmarks (numbers/models not on abstract page) — [NeurIPS 2025 poster](https://neurips.cc/virtual/2025/poster/117087).
- Top-k: decoding-only top-k on pretrained Llama-3-8B-ProLong and Qwen3-32B comparable or better than full attention; SFT with 1% top-k improved HELMET-8K over the original Instruct model — [arXiv 2512.03494](https://arxiv.org/pdf/2512.03494). DeepSeek V3.2 introduced DSA by continued training of V3.1-Terminus [MEM details] — [DeepSeek-V3.2](https://arxiv.org/pdf/2512.02556).
- Gated attention paper: all experiments from scratch; no retrofitting evidence — [arXiv 2505.06708](https://arxiv.org/pdf/2505.06708). MTA: no retrofitting tested — [arXiv 2504.00927](https://arxiv.org/html/2504.00927).
- StreamingLLM sink+window works on pretrained models with no fine-tuning (inference-time KV policy) [MEM] — [arXiv 2309.17453](https://arxiv.org/abs/2309.17453).

### Inferences
- A sigmoid output gate initialized to output ≈1 (e.g., large positive bias) is a structurally plausible retrofit (identity at init, then trainable), but no paper found that tests it; treat as an experiment, not established.
- log-n query scaling (SSMax-style) is a near-zero-cost retrofit worth trying with continued training, expecting partial gains only.
- For a 350M–2B pretrained base, the safest focusing retrofit with evidence is inference-time/SFT top-k (k small relative to context) — but small-model evidence for top-k retrofits is missing; the cited success is at 8B+.

### Gaps
- DEX's actual models/numbers not retrieved (abstract only).
- No retrofit studies found for gated attention, FoX, stick-breaking, selective attention, entmax on a modern pretrained LLM (entmax-retrofit evidence for BERT-era models may exist but was not found).

## Q3. Known downsides (instability, speed, kernels, small-scale failure, reasoning)

### Takeaway
The recurring costs are kernel support and throughput (MTA, DIFF V1, exact top-k, entmax), training pathologies of normalization-free variants (softpick dead heads/gradient blowups, sigmoid needing bias), and poor scaling of some (softpick at 1.8B). Gated attention and DIFF V2 report the opposite: improved stability.

### Cited Findings
- MTA: ~3.4× more memory and ~4.7× lower throughput than Transformer in unoptimized code; incompatible with FlashAttention-style kernels — [arXiv 2504.00927](https://arxiv.org/html/2504.00927).
- DIFF V1: 17.6k vs 54.3k tok/s, 21.6 vs 17.5 GB in same comparison — [arXiv 2504.00927](https://arxiv.org/html/2504.00927); V1 needed custom kernel and double V-cache load; V2 fixes this but ablations show removing sigmoid on λ → unbounded context RMS/instability, removing λ → too small RMS at init — [HF blog](https://huggingface.co/blog/microsoft/diff-attn-v2). DIFF retrofits (DiffLoRA) produce degenerate outputs/collapse in some variants — [arXiv 2507.23588](https://arxiv.org/html/2507.23588v1).
- Softpick: worse at 1.8B, more dead heads, passkey not improved — [arXiv 2504.20966v3](https://arxiv.org/html/2504.20966v3); gradient norms >10¹² at init from zero-denominator rows — [NeurIPS 2026](https://neurips.cc/virtual/2026/173816).
- Exact top-k conflicts with FlashAttention (scores not materialized), O(N²) scoring; approximate top-k loses fidelity and performance tracks indexer precision — [arXiv 2512.03494](https://arxiv.org/pdf/2512.03494).
- SSMax: post-hoc swap hurts short context; learnable bias variant hurts long context — [arXiv 2501.19399](https://arxiv.org/html/2501.19399).
- Gated attention: elementwise gate adds notable params (201M on 15A2B), headwise is near-free; <2% latency; *reduces* loss spikes and allows higher LR — [arXiv 2505.06708](https://arxiv.org/pdf/2505.06708).
- Removing attention sinks is not free in streaming use: StreamingLLM relies on sinks for window KV caching [MEM] — [arXiv 2309.17453](https://arxiv.org/abs/2309.17453).

### Inferences
- In a browser (WebGPU/WASM, e.g., ONNX Runtime Web / transformers.js), anything needing custom kernels (MTA convs over attention maps, entmax root-finding, exact top-k) will likely run as unfused ops — throughput penalties could exceed the GPU numbers above. Gating, DIFF V2 (standard attention calls), SSMax (query scaling) and FoX-style additive bias are expressible with standard ops.
- No source found measuring effects on multi-step reasoning specifically, other than Qwen's GSM8k +2.35 with gating and DiffLoRA's mixed results.

### Gaps
- No reasoning-specific (chain-of-thought) evaluations of sparse/sharpened attention found, besides top-k study's MATH500/AIME at 8B–32B.
- Stick-breaking kernel and FoX kernel overhead numbers not verified.

## Q4. Evidence at small scale (<1B) or in browser/edge settings

### Takeaway
Small-scale evidence is plentiful but mostly authors' own runs: SSMax (162M), softpick (340M, good) vs 1.8B (bad), MTA and DIFF (880M, independent-ish), FoX (≤760M), selective attention (small C4 models), softpick-fix (230M). No paper found evaluating any of these in a browser/WebGPU or edge deployment.

### Cited Findings
- 162M SSMax: 10× length generalization, needle retrieval retained — [arXiv 2501.19399](https://arxiv.org/html/2501.19399).
- 340M softpick ≈ softmax, quantizes better; 1.8B degrades — [arXiv 2504.20966v3](https://arxiv.org/html/2504.20966v3).
- 880M: MTA and DIFF both beat Transformer on PPL and multi-needle NIAH (e.g., 6 needles @4K: 67.0 / 60.0 / 31.9) — [arXiv 2504.00927](https://arxiv.org/html/2504.00927).
- 1.7B dense gated attention trained to 3.5T tokens: avg PPL 6.180→6.130, stability at high LR — [arXiv 2505.06708](https://arxiv.org/pdf/2505.06708).
- Llama-3.2-1B DiffLoRA retrofit: mostly negative — [arXiv 2507.23588](https://arxiv.org/html/2507.23588v1).
- Selective attention: ~2× attention-param efficiency and 16–47× attention memory savings at small scale — [arXiv 2410.02703](https://arxiv.org/abs/2410.02703).
- Quantization relevance: removing sinks/massive activations (softpick kurtosis 33k→341; gating max activation 1053→94) is directly useful for 4-bit browser models — [arXiv 2504.20966v3](https://arxiv.org/html/2504.20966v3); [arXiv 2505.06708](https://arxiv.org/pdf/2505.06708).

### Inferences
- For a ≤500MB model (roughly ≤1B params at 4-bit), the most promising, low-risk combination if training from scratch: headwise sigmoid output gate (stability + no sinks + quantization friendliness) plus SSMax/log-n query scaling (long-context focus), optionally DIFF V2-style paired heads. If starting from a pretrained base, expect only partial gains from SSMax swap/top-k at inference; DIFF retrofits are risky.
- Because the user's harness supplies context, benefits that matter are distractor robustness (multi-needle NIAH, RAG). The strongest small-scale numbers for this are DIFF/MTA at 880M — but none are tested in tool-use or RAG at <1B except DiffLoRA (negative).

### Gaps
- No browser/WebGPU benchmarks of any modified attention found.
- No replication of selective attention, SSMax, FoX or stick-breaking by independent groups found.
- No head-to-head study of these methods at the same small scale with identical data (MTA paper is the closest, covering only DIFF).
