# Mathematics and geometry of transformer attention: when it focuses, when it diffuses, and what helps

Verification legend used throughout:
- **[V]** = verified by fetching the primary source (abstract or full text) in this research session.
- **[K]** = from the researcher's prior knowledge of a well-known paper; URL given, but specific numbers were NOT re-fetched this session. The report writer should treat [K] items as likely correct but lower-confidence.
- **PROVEN** = a mathematical theorem under stated assumptions. **EMPIRICAL** = measured in experiments. **SPECULATIVE** = interpretation or extrapolation.

## 1. Rank collapse / token uniformity, and the role of skip connections, MLPs, LayerNorm

### Takeaway
It is PROVEN that stacking pure softmax self-attention (no residuals, no MLPs) makes all token representations converge to one vector, doubly exponentially fast with depth; residual connections and MLPs block this, and later theory shows LayerNorm can also block it, but only for suitable value matrices. Standard pre-LN transformers with residuals do not suffer full rank collapse in practice, so rank collapse is not a plausible explanation for a small modern model failing to focus.

### Cited Findings
- PROVEN: Pure self-attention output "converges doubly exponentially to a rank-1 matrix" with depth; skip connections and MLPs prevent this degeneration (Dong, Cordonnier, Loukas, ICML 2021). [V] — [arXiv 2103.03404](https://arxiv.org/abs/2103.03404)
- PROVEN: With attention masks (no LayerNorm), if the mask graph is quasi-strongly connected, "tokens converge to a common vector exponentially"; local/sparse masks (sliding window, causal) only slow the collapse, with rate depending on graph radius ("rank collapse should be slower for graphs with larger radius r"). [V] — [Wu et al., NeurIPS 2024, arXiv 2405.18781](https://arxiv.org/pdf/2405.18781)
- PROVEN: With LayerNorm and orthogonal value matrices, tokens still "converge to a common point on S^{d−1} exponentially"; but with appropriately chosen value matrices and a causal mask, there exist ≥2^k equilibria of rank k for each k ≤ min(N,d), and for a positive-measure set of inputs the representation does not converge to rank one. This refutes Dong et al.'s claim that LayerNorm "plays no role." [V] — [arXiv 2405.18781](https://arxiv.org/pdf/2405.18781)
- EMPIRICAL (cited inside Wu et al.): skip connections can make token-similarity measures unstable in deep layers and LayerNorm counteracts it; Joudaki et al. showed LayerNorm improves isometry and can prevent rank collapse; MLPs are needed for universal seq2seq approximation. [V, secondhand] — [arXiv 2405.18781](https://arxiv.org/pdf/2405.18781)
- PROVEN/EMPIRICAL: Rank collapse at initialization causes vanishing gradients for queries/keys; scaling residual branches fixes signal propagation (Noci et al., NeurIPS 2022). [K] — [arXiv 2206.03126](https://arxiv.org/abs/2206.03126)
- PROVEN (continuous-time idealization): self-attention dynamics viewed as interacting particles on the sphere cluster into a few points as depth→∞ (Geshkovski, Letrouit, Polyanskiy, Rigollet, "A mathematical perspective on transformers"). [K] — [arXiv 2312.10794](https://arxiv.org/abs/2312.10794)

### Inferences
- The "oversmoothing" family of results concerns very deep or idealized (weight-tied, no-MLP, infinite-depth) networks. A small standard model with residual stream + MLPs is outside the theorems' hypotheses; its failure to focus is better explained by sections 2 and 6 (dilution and depth for composition) than by rank collapse.
- (Per user reframe: MLP/residual necessity is taken as given; this section is background only. The actionable math is in sections 2–4 and 7.)

### Gaps
- No found result quantifies how close real small (e.g. <1B) pre-LN models get to collapse at their actual depths; the theorems are asymptotic.

## 2. Attention dilution / entropy collapse as context grows; limits of softmax

### Takeaway
It is PROVEN that with bounded logits, every softmax weight is Θ(1/n) as the number of keys n grows, so any global softmax head eventually disperses on long enough inputs ("softmax is not enough"); the fix space is (a) let logit gaps grow with n (log-n temperature scaling, adaptive temperature), (b) differential/noise-cancelling attention. Fixes have EMPIRICAL support only at small scale. Opposite failure (entropy *collapse* — attention becoming too peaked, destabilizing training) also exists and is treated by QK-norm/σReparam.

### Cited Findings
- PROVEN (Lemma 2.1): if logits lie in [m, M], then (1/n)·exp(−δ/θ) ≤ softmax_k ≤ (1/n)·exp(δ/θ), δ = M − m, i.e. each coefficient is Θ(1/n). [V] — [Veličković et al., "Softmax is not Enough (for Sharp Size Generalisation)", arXiv 2410.01104v3](https://arxiv.org/html/2410.01104v3)
- PROVEN (Theorem 2.2): for a transformer over a finite vocabulary with continuous layers, for any temperature θ and ε there is a length n at which all attention coefficients are < ε: "attention coefficients must disperse in all global Transformer heads if the input vocabulary is finite." [V] — [arXiv 2410.01104v3](https://arxiv.org/html/2410.01104v3)
- Same paper proposes an "ad-hoc" inference-time adaptive temperature to sharpen softmax; numeric gains were not retrieved in this session. [V abstract only] — [arXiv 2410.01104](https://arxiv.org/html/2410.01104v3)
- Max softmax weight ≤ 1/((n−1)·e^(z_min − z_max) + 1) → 0 as n grows ("attention fading"). Scalable-Softmax (SSMax) multiplies the query by s·log n (s learnable per head; 144 extra params). EMPIRICAL on one 162M, 12-layer Llama-2-style model trained at 1024 tokens: slightly lower training loss (~0.008), better per-position loss to ~20k tokens after RoPE θ×50, and needle retrieval at ~10× training length where baseline failed; retrofitting after pretraining helped less. Single scale, preprint. [V] — [Nakanishi, arXiv 2501.19399](https://arxiv.org/html/2501.19399v1)
- PROVEN: Hahn (2020) showed soft attention with bounded Lipschitz layers cannot robustly compute PARITY/Dyck on long inputs because a single input change has O(1/n) influence; Chiang & Cholak (2022) showed multiplying attention logits by log n restores the ability (theory + small experiments). This is the same log-n scaling idea as SSMax, earlier. [K] — [Hahn, arXiv 1906.06755](https://arxiv.org/abs/1906.06755); [Chiang & Cholak, arXiv 2202.12172](https://arxiv.org/abs/2202.12172)
- EMPIRICAL: Differential Transformer computes attention as the difference of two softmax maps to cancel "noise"; claims Transformers "overallocate attention to irrelevant context" and that Diff attention improves key-information retrieval, long-context modeling, and reduces hallucination across scales (numbers not retrieved this session). [V abstract] — [Ye et al., arXiv 2410.05258](https://arxiv.org/abs/2410.05258)
- EMPIRICAL: Attention entropy collapse (pathologically low entropy) correlates with training instability; σReparam (spectral reparametrization) prevents it. [K] — [Zhai et al., ICML 2023, arXiv 2303.06296](https://arxiv.org/abs/2303.06296)
- EMPIRICAL: Uncontrolled growth of attention logits destabilizes large ViT training; QK LayerNorm fixes it. [K] — [Dehghani et al., ViT-22B, arXiv 2302.05442](https://arxiv.org/abs/2302.05442)
- EMPIRICAL: "Attention sinks": models dump large attention mass on initial tokens (a no-op sink), which is a learned workaround for softmax having to sum to 1. [K] — [Xiao et al., StreamingLLM, arXiv 2309.17453](https://arxiv.org/abs/2309.17453)
- EMPIRICAL: LLM accuracy depends on where relevant info sits in context (U-shaped, "lost in the middle"). [K] — [Liu et al., arXiv 2307.03172](https://arxiv.org/abs/2307.03172)

### Inferences
- For a harness that supplies context: dilution is a function of n (number of competing keys) and the logit gap δ. Two levers follow directly from Lemma 2.1: shrink n (supply less, better-filtered context) or enlarge the gap (temperature scaling ∝ log n, QK-norm with a learnable scale, training so relevant keys score much higher). Shrinking n is the only lever that requires no retraining — this is a mathematically grounded argument for aggressive retrieval/reranking in the harness.
- SSMax/log-n scaling is cheap (one scalar per head) and well-motivated by two independent theory lines (Chiang & Cholak; Veličković), but evidence of benefit at small-model scale beyond toy/needle tasks is thin. SPECULATIVE that it fixes real-task focus.
- Attention sinks mean "attention not on the answer" is not necessarily wasted — heads need a place to put mass when nothing is relevant. Removing sinks without a replacement (e.g. softmax-off-by-one / gated attention) can hurt.

### Gaps
- Adaptive-temperature quantitative results (Veličković et al.) and Diff Transformer retrieval numbers were not retrieved.
- No independent replication of SSMax at >1B scale found.

## 3. Attention as associative memory / kernel smoothing (Hopfield, β, linear attention)

### Takeaway
It is PROVEN that the transformer attention update equals one update step of a continuous modern Hopfield network, which can store exponentially many patterns in the dimension and whose fixed points are (i) a global average, (ii) metastable averages over subsets, or (iii) single stored patterns; inverse temperature β (effectively the scale of q·k) decides which regime you get. Linear attention is a fast-weight / outer-product memory with capacity limited by dimension, so it retrieves less sharply.

### Cited Findings
- PROVEN: "The new update rule is equivalent to the attention mechanism used in transformers"; the network stores "exponentially (with the dimension of the associative space) many patterns," retrieves in one update with exponentially small error; three fixed-point types: global average, metastable subset averages, single-pattern. Authors used this to classify heads (many early-layer heads average globally; later heads more often in metastable/single regimes). [V] — [Ramsauer et al., arXiv 2008.02217](https://arxiv.org/abs/2008.02217)
- PROVEN (from same paper, [K] for detail): large β (relative to pattern separation) gives single-pattern retrieval; small β gives the global-average fixed point; standard attention uses β = 1/√d_k. Retrieval of a single pattern requires the pattern to be well separated from others relative to 1/β. [K] — [arXiv 2008.02217](https://arxiv.org/abs/2008.02217)
- PROVEN: Linear (kernelized) attention can be written as an RNN whose state is a sum of outer products v·φ(k)ᵀ. [K] — [Katharopoulos et al., arXiv 2006.16236](https://arxiv.org/abs/2006.16236)
- PROVEN/EMPIRICAL: Linear attention = fast weight programmers; capacity is bounded by the feature dimension (beyond that, retrieval interferes); delta-rule updates improve it. [K] — [Schlag, Irie, Schmidhuber, arXiv 2102.11174](https://arxiv.org/abs/2102.11174)
- EMPIRICAL/THEORY: Weight matrices act as associative memories storing outer products of near-orthogonal embeddings; induction heads form via this mechanism in a simplified two-layer model. [K] — [Bietti et al., "Birth of a Transformer: A Memory Viewpoint", arXiv 2306.00802](https://arxiv.org/abs/2306.00802)

### Inferences
- This is the cleanest "geometry" answer to "how do I make attention focus": focus = being in the single-pattern regime = (logit gap between the target key and others) × β must exceed ~log n. Separation of keys (near-orthogonality) and a large enough β are what matter; both are trainable (learned temperature, QK-norm with learned scale).
- For small models with small d_k, key separation is geometrically harder (fewer near-orthogonal directions), so more interference is expected. SPECULATIVE in quantitative terms.
- Linear attention / SSM-style memories are not a route to sharper retrieval in a small model; theory says they are worse at exact recall than softmax.

### Gaps
- Exact β thresholds from Ramsauer et al. were not re-fetched; no work found that measures Hopfield regimes in small (<1B) modern LMs specifically.

## 4. Geometric views: hyperspherical transformers (nGPT), QK-norm, cosine attention, RoPE, anisotropy

### Takeaway
Normalization-on-the-sphere designs (nGPT, QK-norm, cosine attention) are EMPIRICALLY useful mainly for training stability and speed; they make the attention logit a bounded cosine × a learned scale, which interacts directly with Lemma 2.1 (bounded logits ⇒ dispersion unless the scale is large/adaptive). There is no theorem that these geometries make attention "focus on what is needed"; claims of that kind are unproven.

### Cited Findings
- EMPIRICAL: nGPT normalizes "all vectors forming the embeddings, MLP, attention matrices and hidden states" to unit norm, so hidden states move on the hypersphere; claims 4–20× fewer training steps to reach the same accuracy, depending on sequence length. Authors' own claim; no independent verification fetched. [V abstract] — [Loshchilov et al., NVIDIA, arXiv 2410.01131](https://arxiv.org/abs/2410.01131)
- EMPIRICAL: QK-norm (LayerNorm/L2 on queries and keys) bounds logits and prevents logit explosion; originally proposed as cosine-attention-with-learned-scale ("Query-Key Normalization"). [K] — [Henry et al., arXiv 2010.04245](https://arxiv.org/abs/2010.04245); [Dehghani et al., arXiv 2302.05442](https://arxiv.org/abs/2302.05442)
- PROVEN property: RoPE encodes relative position by rotating q,k pairs, and the original paper argues a long-term decay of the inner-product upper bound with relative distance. [K] — [Su et al., RoFormer, arXiv 2104.09864](https://arxiv.org/abs/2104.09864)
- EMPIRICAL: Contextual representations in BERT/GPT-2 are anisotropic — they occupy a narrow cone, with high average cosine similarity between random tokens, especially in upper layers. [K] — [Ethayarajh, arXiv 1909.00512](https://arxiv.org/abs/1909.00512)

### Inferences
- With QK-norm/cosine attention, logits lie in [−s, s] where s is the scale; by Lemma 2.1 the max weight on one of n keys is at most ~e^{2s}/n. To keep a single key dominant as n grows, s must grow ~log n — so QK-norm should be paired with a learnable (or log-n) scale, not a fixed one. This is a derived inference, not a published theorem specific to QK-norm.
- RoPE's distance decay biases toward recency; for retrieval far back in the harness-supplied context, this works against focus. Mitigations (larger RoPE base, partial RoPE, NoPE layers) are empirical. SPECULATIVE for the user's model.
- Anisotropy means raw dot products include a large common component; centering/normalizing keys (QK-norm) removes it, which plausibly sharpens discrimination. SPECULATIVE.
- "New geometry" as a silver bullet: no evidence found that any geometric reparametrization by itself gives a small model multi-hop or focused retrieval ability it otherwise lacks. It changes optimization, not the expressivity limits in section 6.

### Gaps
- No controlled study found isolating nGPT's effect on retrieval/focus (vs. training speed) in small models.
- Independent replications of nGPT speedups not fetched.

## 5. Circuit-level findings: induction heads, retrieval heads, head sparsity, pruning

### Takeaway
EMPIRICALLY, focused retrieval in LMs is done by a small, sparse set of heads: induction heads (copying via previous-token + match), and "retrieval heads" (<5% of heads) that causally control needle-in-a-haystack retrieval; most other heads can be pruned with little loss. This suggests "focus" is a property of a few specialized heads that must form during training.

### Cited Findings
- EMPIRICAL: Retrieval heads are "less than 5%" of attention heads; universal across long-context models examined; intrinsic (already present in short-context pretraining and preserved through context extension); in Llama-2 7B, 12 heads consistently attend to the needed info; pruning them causes retrieval failure and hallucination while pruning random non-retrieval heads does not; masking them strongly hurts chain-of-thought (which re-reads question/earlier output) but less so direct knowledge recall. [V] — [Wu et al., ICLR 2025, arXiv 2404.15574](https://www.arxiv.org/abs/2404.15574)
- EMPIRICAL (with small-model mechanistic evidence): induction heads (a previous-token head composed with a match-and-copy head in a later layer — requires ≥2 layers) form in a phase change coinciding with a jump in in-context learning. [K] — [Olsson et al., Anthropic, 2022](https://transformer-circuits.pub/2022/in-context-learning-and-induction-heads/index.html); [Elhage et al., "A Mathematical Framework for Transformer Circuits"](https://transformer-circuits.pub/2021/framework/index.html)
- PROVEN: One-layer transformers fail to solve the induction-heads task unless their size is large (communication-complexity lower bound), whereas two layers suffice with small size. [V title/URL; details K] — [Sanford, Hsu, Telgarsky, arXiv 2408.14332](https://arxiv.org/html/2408.14332v1)
- EMPIRICAL: Many heads can be pruned at test time with little loss; in some layers a single head suffices. [K] — [Michel, Levy, Neubig, "Are Sixteen Heads Really Better than One?", arXiv 1905.10650](https://arxiv.org/abs/1905.10650); [Voita et al., arXiv 1905.09418](https://arxiv.org/abs/1905.09418)

### Inferences
- For a small model, the number of heads available to become retrieval/induction heads is small in absolute terms; if those few heads don't form or are diluted, retrieval fails. Probing which heads attend to the needed context (retrieval-score method of Wu et al.) is a concrete diagnostic the user can run.
- Head pruning results imply capacity is not spread evenly; adding heads may matter less than ensuring the right circuits train (data with lots of copy/lookup structure).

### Gaps
- Retrieval-head prevalence specifically in sub-1B models was not found.

## 6. Minimum depth/width for multi-hop composition (why chaining two lookups fails)

### Takeaway
Theory gives a clear picture: one attention layer cannot cheaply do even a single induction step (PROVEN lower bound); k-hop pointer-chasing in context needs about log₂k + 2 layers with a doubling construction, and models with too little depth must pay with width/heads polynomial in n or with k chain-of-thought tokens (PROVEN). Empirically, LLMs resolve the first hop in early/middle layers and fail the second hop when they "run out of layers," and composing two *parametric* facts latently is very hard (two-hop curse), while composition over facts present *in context* or with chain-of-thought works much better. So: yes, focusing a small model on a two-lookup chain is possible, but the math says it needs either enough depth, explicit intermediate tokens (CoT / harness splitting the hops), or both.

### Cited Findings
- PROVEN: A causally masked transformer with O(1) embedding dim, one head per layer, and L ≤ 2 + log₂(k) layers computes k-hop induction at all positions (each layer doubles pointer reach); SGD empirically finds this log-depth construction. [V] — [Sanford, Hsu, Telgarsky, "Transformers, parallel computation, and logarithmic depth", ICML 2024, arXiv 2402.09268, slides](https://cs.columbia.edu/~djhsu/papers/khop-slides.pdf)
- PROVEN (conditional/lower bounds, same work): under the 1-vs-2-cycle conjecture, transformers with sub-linear mH need Ω(log n) layers for graph connectivity; for a single attention layer with T chain-of-thought tokens, either T ≥ k or width×heads must be polynomially large in n (exponent partly garbled in extraction — check paper). [V] — [slides](https://cs.columbia.edu/~djhsu/papers/khop-slides.pdf)
- PROVEN: One-layer transformers fail the induction-heads task unless size is polynomial in n. [V title] — [arXiv 2408.14332](https://arxiv.org/html/2408.14332v1)
- EMPIRICAL: In two-hop queries, the bridge entity is resolved at the first-hop token in early layers; the answer emerges at the final token in mid/upper layers. In failures the bridge is resolved too late — the model "runs out" of layers. Back-patching later-layer states into earlier layers fixes 32–66% of previously wrong cases without training. [V] — [Biran et al., "Hopping Too Late", arXiv 2406.12775](https://arxiv.org/pdf/2406.12775)
- EMPIRICAL: Llama 3 8B and GPT-4o, fine-tuned on synthetic facts, "fail to compose two synthetic facts" latently, but can succeed when one fact is natural (two-hop curse). [V] — [Balesni et al., arXiv 2411.16353](https://arxiv.org/abs/2411.16353v1)
- EMPIRICAL: Transformers learn implicit composition only via grokking (long training past overfitting) and then fail OOD systematic generalization for composition (but not comparison); authors suggest "cross-layer knowledge sharing" as an architectural fix. [V] — [Wang et al., "Grokked Transformers are Implicit Reasoners", arXiv 2405.15071](https://arxiv.org/abs/2405.15071)
- Additional 2025–2026 work on this topic (not fetched): "Language models can learn implicit multi-hop reasoning, but only if they have lots of training data" [arXiv 2505.17923](https://arxiv.org/pdf/2505.17923); "Why Knowing Both Hops Is Not Enough" [arXiv 2608.07261](https://arxiv.org/pdf/2608.07261); identity-bridge mechanism [arXiv 2509.24653](https://arxiv.org/pdf/2509.24653). Titles only; contents unverified.

### Inferences
- For the user's failing two-lookup chain: theory says depth is the binding constraint, not geometry. Each hop needs a layer (or more) to (a) find the first key, (b) write the bridge into the residual stream, and (c) use it as a query for the second lookup — and that second lookup must happen in a layer *after* the bridge is written. A small, shallow model may simply lack enough layers after the point the bridge resolves.
- Cheapest fixes consistent with theory: (1) have the harness or the model emit the intermediate result as a token (CoT), turning one 2-hop into two 1-hop lookups — PROVEN to trade depth for tokens; (2) put both facts in context rather than relying on parametric memory (empirically much easier than the two-hop curse setting); (3) weight-tied/looped layers or "cross-layer sharing" to give effectively more depth (Wang et al. suggestion; SPECULATIVE for the user's model); (4) train on data rich in composed lookups.
- Is "new geometry/discrete math" able to make a small model's attention focus? Honest answer: the proven theory says *how much* focus is possible (gap vs. log n; depth vs. hops), and offers small, cheap, theory-motivated tweaks (log-n/learned temperature, QK-norm with learned scale, differential attention). None is proven to rescue multi-hop in a small model; the strongest levers are reducing n (harness filtering) and externalizing hops (CoT / harness orchestration). Claims that a novel geometry alone solves focus are unproven.

### Gaps
- Exact exponents in the Sanford et al. lower bounds were garbled in extraction.
- No result found giving a tight minimum layer count for a 2-hop *in-context* lookup in realistic tokenized text (vs. clean synthetic pointer chasing); the toy theory gives ~3 layers for k=2 but real models need extra layers for tokenization/entity resolution.

## 7. Changes to attention's math that are both theory-motivated AND measured to improve focus; attending to harness-supplied context vs. the model's own memory

### Takeaway
A short list of attention modifications have both a theoretical rationale and measured gains: log-n / learned temperature (SSMax), sparse normalizers (α-entmax), gated attention (sigmoid gate on SDPA output, removes attention sinks, large long-context gains), differential attention, and QK-norm with learned scale. For externally supplied context, the relevant theory is the Hopfield/associative-memory view (retrieved chunks become extra "stored patterns"; sharp retrieval needs key separation and large β relative to log n) plus mechanistic evidence that the same attention heads arbitrate context vs. parametric memory and can be re-weighted. Retrieval-native architectures (RETRO chunked cross-attention) show a small model plus supplied context can match much larger models on LM loss. None of this is proven to make a small model reliably "focus on what is needed" on real tasks; evidence is mostly single-paper, often at 0.1–15B scale.

### Cited Findings
Temperature / normalizer changes
- SSMax: q scaled by s·log n per head; one 162M model; better needle retrieval at ~10× training length; must be used from pretraining for full effect. EMPIRICAL, single scale. [V] — [arXiv 2501.19399](https://arxiv.org/html/2501.19399v1)
- Theory backing temperature growth: PROVEN Θ(1/n) dispersion for bounded logits [V] — [arXiv 2410.01104v3](https://arxiv.org/html/2410.01104v3); PROVEN that log-n logit scaling fixes long-input sensitivity failures [K] — [Chiang & Cholak, arXiv 2202.12172](https://arxiv.org/abs/2202.12172)
- α-entmax attention: replaces softmax with a differentiable normalizer that assigns exactly zero weight to low-scoring tokens; α learned per head so each head chooses between focused and spread attention; reported better interpretability and head diversity with no accuracy cost on MT (BLEU numbers not retrieved). Note sparsemax/entmax output is not forced to Θ(1/n) — the dispersion lemma is softmax-specific — so this is a principled escape from Lemma 2.1. [V abstract] — [Correia, Niculae, Martins, EMNLP 2019, arXiv 1909.00015](https://arxiv.org/abs/1909.00015v2)

Gating / noise cancellation
- Gated attention: head-specific, query-dependent sigmoid gate applied to the SDPA output (best of 5 positions tested, ~30 variants). On a 15B MoE (2.54B active, 400B tokens): perplexity 6.026→5.761, MMLU 58.79→60.82, GSM8K 52.92→55.27. Attention to first token (sink) 46.7%→4.8%. Long context after YaRN extension: RULER at 64k 37.51→66.60, at 128k 31.65→58.82 (at native 32k essentially equal, 79.50 vs 79.77). Also nearly eliminates loss spikes in 1.7B dense runs to 3.5T tokens. Gate scores are sparse (mean 0.116); input-independent or less-sparse gates are worse. Explanation offered: adds non-linearity between low-rank V and O projections + query-dependent sparsity. EMPIRICAL (NeurIPS 2025; used in Qwen3-Next per secondary sources). [V] — [Qiu et al., arXiv 2505.06708](https://arxiv.org/abs/2505.06708); [code](https://github.com/qiuzh20/gated_attention)
- Differential attention (difference of two softmax maps) claims less attention to irrelevant context and better key-information retrieval. EMPIRICAL. [V abstract] — [arXiv 2410.05258](https://arxiv.org/abs/2410.05258)

Retrieval-native architecture (attending to supplied context)
- RETRO: conditions an LM on chunks retrieved from a 2-trillion-token database via a frozen BERT retriever and chunked cross-attention; performs comparably to GPT-3 and Jurassic-1 on the Pile with 25× fewer parameters; can be trained from scratch or retrofitted onto a pretrained transformer. EMPIRICAL. [V abstract] — [Borgeaud et al., arXiv 2112.04426](https://arxiv.org/abs/2112.04426)
- Hopfield view: retrieved chunks are additional stored patterns; one-step retrieval of a single pattern is exponentially accurate when patterns are well separated; otherwise the update lands on a metastable average. PROVEN in the idealized model. [V] — [arXiv 2008.02217](https://arxiv.org/abs/2008.02217)

Context vs. parametric memory
- The same attention heads carry both contextual and parametric information ("CP superposition"); half of top "memory heads" flip to "context heads" under a different conflict type, so there are no clean dedicated context heads. Attention modules, not MLPs, were the consistent levers (6 attention modules vs 1 MLP vs 0 whole layers in Gemma). A training-free method (JuICE: identify ~5 heads from 4 examples, run twice, add scaled head outputs) raised context reliance to ~66 avg accuracy vs 35–51 for base models and the CAD baseline across Gemma/Llama2/Llama3. A simplified two-layer theory shows a shared head can encode both factual recall and induction, with the winner set by learned coefficient strengths. EMPIRICAL + toy theory. [V] — [Li et al., "Taming Knowledge Conflicts in Language Models", ICML 2025, arXiv 2503.10996](https://arxiv.org/html/2503.10996v2)
- Retrieval heads (<5% of heads) causally control copying from long context; pruning them breaks retrieval. [V] — [arXiv 2404.15574](https://www.arxiv.org/abs/2404.15574)
- Further 2026 work proposes a predictive "three regimes" framework for context–parametric conflict (title only, not fetched). — [arXiv 2605.11574](https://arxiv.org/pdf/2605.11574)

### Inferences
- Ranked, for a small model fed curated harness context (my synthesis, not a published ranking):
  1. No retraining: cut n (fewer, better chunks) and order/structure context so the target key is separable — directly from Lemma 2.1 and the Hopfield separation condition. Externalize hops (section 6). Steer a handful of identified retrieval/context heads (JuICE-style scaling) — measured on 2B–8B models.
  2. Cheap at training/fine-tune time: learned per-head temperature or s·log n scaling; QK-norm with learnable scale; gated attention on SDPA output (strongest measured long-context gains found in this research, but shown at 1.7B+ scale and mainly after context extension).
  3. Larger changes: α-entmax/sparse attention, differential attention, RETRO-style cross-attention for supplied context. All measured, none shown specifically to fix 2-hop failure in small models.
- Structured/tool-result context: theory predicts formatting that makes keys distinctive (unique field labels, delimiters, repeating the query key near the value) increases logit gaps — consistent with induction/retrieval-head mechanics, but I found no paper directly measuring this. SPECULATIVE.
- Because context and memory share heads, a small model's weak parametric prior can actually make it easier to bias toward context; conversely, conflicts with strong memorized facts will pull attention-head outputs away from supplied context. SPECULATIVE extrapolation from Li et al.

### Gaps
- No controlled comparison found of SSMax vs gated attention vs entmax vs Diff attention on the same small model.
- No study found measuring which context formatting maximizes attention logit gaps in small models.
- RETRO's dependence on retrieval vs. train/test leakage (discussed in the full paper) was not retrieved.
