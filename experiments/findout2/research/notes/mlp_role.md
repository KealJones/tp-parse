# What the MLP is for in a small LM, and how to spend and improve it when a harness supplies facts

Scope note: the user agrees MLPs are needed. The main questions are (a) what MLPs actually hold (facts vs skills), (b) how to make the MLP's math or capacity more efficient for a ~350M–2B model, and (c) how to allocate MLP or memory capacity when tools or retrieval supply facts. Removal results are summarized briefly as supporting evidence.

Sourcing note: findings marked "(abstract-level)" were checked only against the arXiv abstract page, not the full paper. Findings marked "(not re-fetched)" are well-known abstract claims I did not re-open in this session; the report writer should treat them as lower-confidence citations.

## Q1. What do MLPs store and compute: facts, patterns, skills?

### Takeaway
MLPs act as large pattern-to-output associative memories and hold most of a model's parameters. Facts are stored in them, but not exclusively, and factual "localization" is weaker than early editing work suggested. MLPs also implement computation (arithmetic is done by sparse sets of heuristic MLP neurons) and keep attention stacks from collapsing. So they hold skills as well as facts.

### Cited Findings
- Feed-forward layers are about two-thirds of a transformer's parameters. Each FFN "key" correlates with textual patterns in the training data, and each "value" induces a distribution over the output vocabulary. Lower layers capture shallow patterns and upper layers capture semantic ones; layer outputs are compositions of memories, refined through the residual stream. (abstract-level) — [Geva et al. 2021, FFN Layers Are Key-Value Memories](https://arxiv.org/abs/2012.14913)
- Follow-up work describes FFN updates as promoting concepts in vocabulary space. (not re-fetched) — [Geva et al. 2022](https://arxiv.org/abs/2203.14680)
- ROME and MEMIT localized factual recall to mid-layer MLPs at the last subject token and edited facts by rank-one or batched weight updates; MEMIT scales to thousands of edits. (not re-fetched) — [ROME, Meng et al. 2022](https://arxiv.org/abs/2202.05262); [MEMIT](https://arxiv.org/abs/2210.07229)
- Critique: causal-tracing localization "does not provide any insight into which model MLP layer would be best to edit." The choice of edited layer predicts edit success much better than the tracing results do. (abstract-level) — [Hase et al. 2023, Does Localization Inform Editing?](https://arxiv.org/abs/2301.04213v1)
- Knowledge is not MLP-exclusive. In the controlled synthetic-biography setting with 1000 exposures, architectures including GPT-2 with reduced or no MLP layers reach a similar ~2 bits/param capacity. With only 100 exposures, removing MLPs entirely cuts capacity by more than 1.5x, while shrinking the MLP to 1/4 size has a negligible effect. — [Allen-Zhu & Li, Physics of LMs Part 3.3](https://ar5iv.labs.arxiv.org/html/2404.05405)
- Arithmetic is computed by a circuit in which a sparse set of neurons implements simple heuristics, each tied to a numerical input pattern (e.g., an operand within a range). Together these heuristics explain most arithmetic accuracy and appear early in training: "a bag of heuristics rather than robust algorithms or memorization." (abstract-level) — [Nikankin et al., Arithmetic Without Algorithms (ICLR 2025)](https://arxiv.org/abs/2410.21272v1)
- Pure attention without skip connections or MLPs "converges doubly exponentially to a rank-1 matrix." MLPs and skip connections counteract this collapse. — [Dong et al. 2021, Attention is not all you need](https://arxiv.org/abs/2103.03404)
- One analysis of fast vs slow thinking suggests knowledge retrieval is localized in lower layers and reasoning adjustment in higher layers (layer-wise CKA, Qwen 7B / LLaMA 8B). Knowledge gains keep rising with scale (Qwen fast-thinking accuracy 53.9% at 1.5B to 79.5% at 32B). Reasoning-adjustment gains come mainly between ~1B and 8B, and Qwen 1.5B shows a negative reasoning gain (-3.9). Caveats: multiple-choice QA only, and the paper has an internal number inconsistency. — [Decoupling Knowledge and Reasoning (AAAI)](https://arxiv.org/html/2507.18178v1)

### Inferences
- "MLP = fact store" is incomplete. MLPs are the main pattern→output lookup substrate, and the same substrate holds facts, lexical/syntactic patterns, and heuristic "skill" neurons (arithmetic, likely code idioms). There is no clean parameter partition, so "what fraction stores knowledge vs computation" cannot be answered with a number.
- Supplying facts externally does not remove the need for MLP capacity. It changes what the capacity should hold: pattern and skill heuristics, plus the ability to copy and compose retrieved text.

### Gaps
- I found no measured split of parameters between knowledge and computation for any real LM.
- I found no direct mechanistic study showing that coding skill resides in MLP neurons. The arithmetic-heuristics result is the closest evidence, and extending it to code is an inference.
- Anthropic's superposition and MLP-feature work (Toy Models of Superposition; Towards Monosemanticity) is relevant (MLP neurons are polysemantic and store more features than dimensions) but was not fetched this session.

## Q2. Capacity math for a 350M–2B model (knowledge scaling laws)

### Takeaway
About 2 bits/param is the ceiling under heavy repetition (1000 exposures), about 1 bit/param at 100 exposures, and much lower with junk-heavy data. A 350M model therefore has an upper bound of roughly 0.35–0.7 Gbit (~45–90 MB) of factual knowledge. This tight budget is a strong argument for handing facts to a harness and spending parameters on skills.

### Cited Findings
- ~2 bits/param after sufficient training, and this survives int8 quantization. int4 cuts capacity substantially (more than 2x in the detailed results). A 7B model holds ~14B bits. — [Physics of LMs 3.3](https://ar5iv.labs.arxiv.org/html/2404.05405)
- 2 bits/param needs ~1000 exposures per fact; 100 exposures gives ~1 bit/param. — [same](https://ar5iv.labs.arxiv.org/html/2404.05405)
- Gated MLPs (LLaMA/Mistral) reach up to 1.3x lower capacity than GPT-2 MLPs at 100 exposures. — [same](https://ar5iv.labs.arxiv.org/html/2404.05405)
- With 7/8 junk tokens, capacity for useful knowledge drops up to ~20x at 100 exposures. Prepending a domain token reduces this loss to ~2x. — [same](https://ar5iv.labs.arxiv.org/html/2404.05405)
- A 32-expert MoE loses only ~1.3x (1000 exposures) or ~1.5x (100 exposures) capacity per total parameter. — [same](https://ar5iv.labs.arxiv.org/html/2404.05405)

### Inferences
- For 350M at ~1 bit/param on realistic data, encyclopedic memorization is a poor use of parameters. Junk-diluted web data makes it worse, which favours curated, skill-dense training data.
- The SwiGLU knowledge-capacity penalty is a real but small trade-off. GLU variants are still preferred for general LM quality (see Q3), and the penalty matters less if facts come from retrieval.

### Gaps
- These results come from synthetic biographies. Transfer to "skill capacity" (bits needed for coding heuristics) is unmeasured.

## Q3. Making the MLP's math more efficient (activations, sparsity, normalization, sub-billion design)

### Takeaway
At small scale, the best-supported cheap wins are a gated FFN (SwiGLU) for quality; ReLU² for activation sparsity and Primer-style compute savings; deep-and-thin shapes; and stable normalization (Peri-LN). Activation sparsity (ReLU²) is the only one of these that also reduces inference FLOPs.

### Cited Findings
- GLU variants (component-wise product of two projections, with sigmoid replaced by e.g. GELU/Swish) in the FFN "yield quality improvements" over ReLU/GELU. (abstract-level; the parameter-matched d_ff reduction is in the full paper) — [Shazeer 2020, GLU Variants](https://arxiv.org/abs/2002.05202)
- At 125M, replacing the vanilla FFN with SwiGLU raised average zero-shot accuracy from 42.6 to 43.9. — [MobileLLM](https://huggingface.co/papers/2402.14905.md)
- Deep-and-thin beats wide-and-shallow at ~125M (30–42 layers beat 12 layers). — [MobileLLM](https://huggingface.co/papers/2402.14905.md)
- Embedding sharing saves ~11.8% of params at 125M for a 0.2-point drop, which is recovered by reinvesting the parameters in depth. — [MobileLLM](https://huggingface.co/papers/2402.14905.md)
- Immediate block-wise weight sharing (running each block twice) gives +0.7 points (125M) and +0.8 points (350M) for small latency cost. — [MobileLLM](https://huggingface.co/papers/2402.14905.md)
- MobileLLM-350M averages 51.3 vs RWKV-430M's 47.0. — [MobileLLM](https://huggingface.co/papers/2402.14905.md)
- Primer (squared ReLU in the FFN plus depthwise conv on Q/K/V) cuts training cost 4x at 500M (T5/C4) and reaches GPT-3-XL-like (1.9B) one-shot quality with ~1/3 the compute. Gains grow with scale. The paper does not separate the ReLU² contribution from the conv contribution. (abstract-level) — [So et al. 2021, Primer](https://arxiv.org/abs/2109.08668)
- ReLU² "excel[s] across all three evaluation aspects" (sparsity–performance trade-off, predictability of sparsity, hardware affinity) among activations studied for sparse LLMs. (abstract-level, no numbers) — [ReLU² Wins](https://huggingface.co/papers/2402.03804)
- Related activation-sparsity work: [Turbo Sparse (dReLU)](https://arxiv.org/pdf/2406.05955) and [2:4 activation sparsity](https://arxiv.org/pdf/2503.16672) (not fetched).
- Peri-LN normalizes "peripherally around sublayers" (input and output of each attention/MLP). Up to 3.2B it gives more balanced variance growth and steadier gradients than Pre-LN. (abstract-level, no benchmark numbers fetched; ICML 2025) — [Kim et al., Peri-LN](https://arxiv.org/abs/2502.02732)

### Inferences
- SwiGLU and ReLU² pull in different directions. SwiGLU gives slightly better dense quality per parameter; ReLU² gives exploitable activation sparsity, which helps on-device inference. A small harness-driven model could test both. This is a choice to test, not a settled result.
- Weight sharing (MobileLLM-LS) is a cheap way to add depth or "compute" without adding stored knowledge. That matches the goal of spending capacity on skills, though this is my inference.

### Gaps
- I found no head-to-head SwiGLU vs ReLU² comparison at 350M with numbers in fetched material.
- Peri-LN's benchmark deltas were not retrieved.

## Q4. Sparse FFNs: MoE, memory layers, product keys, UltraMem

### Takeaway
Replacing a few (not all) dense FFNs with product-key memory layers is the strongest measured way to add factual capacity at near-constant compute. At 373M base, Memory+ beats a 5x-bigger MoE on factual QA. Memory layers help facts and in-context recall but can hurt multi-hop reasoning and need dense FFNs kept in most layers. MoE helps general quality per active parameter.

### Cited Findings
- Product-key memory adds up to 1B parameters with negligible compute; a 12-layer memory model beats a 24-layer baseline and is 2x faster at inference. (abstract-level) — [Lample et al. 2019](https://arxiv.org/abs/1907.05242)
- Memory Layers at Scale (Meta FAIR, Dec 2024): Memory+ shares one pool across 3 memory layers, uses SiLU gating, and keys of dimension d/2. At 373M base, factual QA scores:

  | Model | Total params | NQ | TQA | HotpotQA |
  |---|---|---|---|---|
  | Dense | 373M | 2.58 | 17.68 | 10.06 |
  | MoE | 1.83B | 3.99 | 19.94 | 12.50 |
  | PEER | 1.58B | 5.10 | 26.39 | 12.96 |
  | Memory+ | 1.43B | 5.76 | 28.10 | 13.34 |

  At 1.3B base, Memory+ with 64M values (138.7B total params) reaches NQ 20.78 / TQA 62.14, approaching Llama2-7B (25.1 / 64.0). Memory models roughly match dense models with 2x the parameters on QA; MoE trails memory variants "by large margins." — [Berges et al. 2024](https://arxiv.org/html/2412.09764v2)
- Negative result: gains peak at about 3 memory layers. Replacing 6 MLPs brings performance back down to single-layer level, which the paper attributes to removing dense parameters. At 8B and 1T tokens, Memory+ beats dense on MMLU (63.04 vs 59.68), TQA (68.15 vs 63.62) and HumanEval (31.71 vs 29.88) but is slightly worse on MBPP (42.20 vs 44.20). — [same](https://arxiv.org/html/2412.09764v2)
- UltraMemV2 (ByteDance Seed) reaches parity with 8-expert MoE at equal compute and parameters. Its largest model has 2.5B active of 120B total params. It beats MoE on long-context memorizing (23.5 vs 21.9), multi-round memorizing (31.2 vs 25.0), in-context learning (29.5 vs 21.6) and KV retrieval (57.1 vs 41.3). It is much worse on multi-hop reasoning (17.7 vs 34.8) and trails MoE on math/code/reasoning after 1.6T tokens. It has a "slow start" in early training and needs a memory layer in every block. Activation density matters more than total sparse parameter count. At 227M active / 1.2B total it scores 54.4 vs OLMoE's 54.6. — [UltraMemV2](https://arxiv.org/html/2508.18756v1); v1: [UltraMem, ICLR 2025](https://arxiv.org/abs/2411.12364v1) (the v1 inference-speed claims were not verified)
- MoE: OLMoE has 1B active / 7B total params. (not re-fetched) — [OLMoE](https://arxiv.org/html/2409.02060v2)
- A 32-expert MoE stores knowledge nearly as efficiently per total parameter as dense (see Q2). — [Physics 3.3](https://ar5iv.labs.arxiv.org/html/2404.05405)

### Inferences
- When facts come from a harness, memory layers' main win (factual QA) is partly redundant. Their measured weakness (multi-hop reasoning) is exactly the skill the harness pairing needs. For a skill-first small model, dense or MoE FFN capacity looks like a better default than a large product-key memory. A small memory layer may still help with retrieval-style in-context recall (UltraMemV2's ICL and KV-retrieval gains). This is my inference, not a measured result in a harness setting.
- Memory layers' parameter count is mostly storage (RAM or flash), not compute. On-device they trade cheap FLOPs for memory footprint, which matters for a 350M on-device target.

### Gaps
- I found no study combining memory layers with retrieval or tools to test whether they are complementary or redundant.

## Q5. Does offloading knowledge to retrieval or tools let a small model beat a bigger one, and what should the MLP spend on?

### Takeaway
Retrieval gives large measured wins on knowledge-intensive tasks (RETRO and Atlas match models 25–50x larger) but is "on par" on other tasks. Retrieval substitutes for factual parameters, not for reasoning parameters. Small models with skill-dense data (TinyStories, MobileLLM API calling) show that narrow skills fit in very few parameters. The "cognitive core" (knowledge-free reasoning model) is an opinion or proposal and has not been demonstrated.

### Cited Findings
- RETRO (7.5B) "obtains comparable performance to GPT-3 and Jurassic-1 on the Pile, despite using 25× fewer parameters." — [Borgeaud et al. 2021](https://arxiv.org/abs/2112.04426)
- A reproduction up to 9.5B finds RETRO "largely outperforms GPT on knowledge-intensive tasks, but is on par with GPT on other tasks," with less repetition and moderately higher factual accuracy. RETRO++ adds +8.6 EM on NaturalQuestions. — [Wang et al. 2023, Shall We Pretrain with Retrieval?](https://www.arxiv.org/abs/2304.06762)
- Atlas 11B scores 42.4% on NaturalQuestions 64-shot, beating PaLM 540B by ~3 points with 50x fewer parameters. Reader size still matters: MMLU 5-shot goes 38.9 (770M) → 42.3 (3B) → 43.4 (11B), and full-data 56.3 → 59.9 → 65.8. — [Izacard et al., Atlas](https://arxiv.org/pdf/2208.03299)
- MobileLLM-350M roughly matches LLaMA-v2 7B on an API-calling task (intent exact match 65.3 vs 62.8; structure exact match 48.8 vs 50.9). — [MobileLLM](https://huggingface.co/papers/2402.14905.md)
- TinyStories models under 10M params, even with a single transformer block, generate stories with "almost perfect grammar" and some reasoning (graded by GPT-4). — [Eldan & Li 2023](https://arxiv.org/abs/2305.07759)
- Opinion: Karpathy proposes a "cognitive core": "a few billion param model that maximally sacrifices encyclopedic knowledge for capability." This is a proposal, not an experiment. — [LessWrong post quoting tweet (Nov 2025)](https://www.lesswrong.com/posts/qBsj6HswdmP6ahaGB/andrej-karpathy-on-llm-cognitive-deficits)
- Reasoning gains from scale come mainly between ~1B and 8B and level off after; knowledge gains continue with scale. — [Decoupling Knowledge and Reasoning](https://arxiv.org/html/2507.18178v1)

### Inferences
- Allocation principle supported by the evidence: let retrieval cover the long tail of facts (the strongest measured substitution) and spend MLP capacity on skill-dense, repeated patterns. Examples are syntax and code idioms, tool-call formats, arithmetic and other heuristics, and copy/compose behaviours. These are seen many times, which is the regime where per-parameter capacity is highest (the 1000-exposure result).
- Because RETRO and Atlas gains are concentrated in knowledge tasks and reader size still matters, a 350M model plus a harness should beat a larger model alone on fact lookup and narrow tool use. On multi-step reasoning, parameters still matter, and the ~1–8B window is where reasoning gains appear.

### Gaps
- I found no published "knowledge-free" or "reasoning core" small LM trained from scratch with facts deliberately excluded and evaluated with a harness. This is the key unmeasured experiment.
- Phi-series "textbook data" claims were not fetched this session.

## Q6. Brief: removal and pruning results (supporting evidence only)

### Takeaway
In pretrained LLMs, attention layers are far more removable than MLP layers. Feed-forward layers can be replaced by persistent memory vectors in attention (an equivalent lookup function), but pure attention collapses. MLP-style capacity is needed in some form.

### Cited Findings
- Llama-2-70B (baseline average 73.9):
  - Dropping 40 of 80 attention layers gives 71.5 average at 1.48x speed.
  - Dropping 16 MLP layers gives 65.9 (1.08x).
  - Dropping 16 whole blocks gives 54.4.
- Mistral-7B (baseline 70.3):
  - Dropping 8 attention layers gives 69.8.
  - Dropping 8 MLP layers gives 53.4.
- Attention has lower importance scores than MLP throughout training. — [He et al. 2024, What Matters in Transformers?](https://arxiv.org/html/2406.15786v6)
- Persistent memory vectors added to attention "play a similar role as the feed-forward layer," allowing FFN removal without loss on char/word LM benchmarks. (abstract-level, no numbers fetched) — [Sukhbaatar et al. 2019](https://arxiv.org/abs/1907.01470)
- Pure attention collapses to rank 1 without MLPs or skips. — [Dong et al. 2021](https://arxiv.org/abs/2103.03404)

### Inferences
- The FFN's role (a learned key→value lookup) can be re-expressed, as persistent memory or product keys, but it cannot be dropped. Efficiency work should target the form of the MLP (gating, activation sparsity, MoE, memory) rather than its existence.

### Gaps
- No numbers were retrieved for the all-attention (persistent memory) model versus baselines.
