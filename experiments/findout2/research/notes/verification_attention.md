# Verification of attention-focusing methods and attention theory for small models

All items were checked against arXiv full text (HTML). Arrows (→) mean "baseline → method". Status labels are CONFIRMED, CORRECTED or NOT FOUND.

## 1. DEX: differential attention retrofitted onto pretrained models (arXiv 2505.16333)

### Takeaway
CONFIRMED: Qwen2.5-0.5B goes 51.8 → 54.4 (+2.6) and Llama-3B multi-needle goes 66.9% → 78.3%. Training used 887M tokens for one epoch. Only selected self-attention parameters plus the λ/annealing parameters were updated, and the FFN stayed frozen. Caveat: most of the Qwen-0.5B gain comes from one of the 11 benchmarks (41.3 → 61.5).

### Cited Findings
- CONFIRMED (Table 1, Qwen-0.5B rows): the base model averages 51.8. "Ours" (DEX) averages 54.4, marked +2.6. Every other adaptation baseline scores 51.3–52.1: LoRA r=8 51.8, LoRA r=32 51.6, PiSSA 51.3, full FT 52.1, GaLore 51.4, APOLLO 51.5. — [DEX, arXiv 2505.16333](https://arxiv.org/html/2505.16333)
- Nuance: the per-task scores for Qwen-0.5B with DEX are mixed. Several tasks drop (for example 62.3 → 56.5 and 74.0 → 73.0). The 11th column goes from 41.3 to 61.5, so most of the average gain comes from that one benchmark. Other cases are small: Qwen-1.5B gains +0.2 (62.2 → 62.4), and the model block listed just before it gains +1.1 (55.6 vs a base of about 54.5; the model label was cut off in my extraction, probably Llama-1B). — [DEX](https://arxiv.org/html/2505.16333)
- CONFIRMED (Fig. 10 text): "Dex improves the average accuracy score by 11.4% (absolute increase from 66.9% to 78.3%)" on multi-needle retrieval with base Llama-3B. — [DEX](https://arxiv.org/html/2505.16333)
- Data: "This corpus contains 887M tokens (Llama-3 tokenizer), less than 0.01% of the models' original pretraining data size". It is drawn from Dolmino-mix-1124 in these proportions: web 74.3%, papers 6.5%, encyclopedia 7.9%, code 11.3%. Training ran for 1 epoch with a cosine schedule and 0.03 warmup. "Notable gains appear with just 400M tokens." — [DEX App. E.1 and Sec. 4](https://arxiv.org/html/2505.16333)
- Models tested: Llama-3.1-8B, Llama-3.2-3B/1B and Qwen-2.5-1.5B/0.5B. — [DEX](https://arxiv.org/html/2505.16333)
- Weights trained: "we update [the selected heads' attention projections] along with [λ parameters] within self-attention, keeping all other parameters (e.g., FFN) frozen." Only a top-k subset of heads per layer is adapted, chosen as the highest-entropy heads (best) or the lowest-importance heads. λ uses a scheduled annealing that starts at zero and then hands over to a learnable λ. — [DEX Sec. 3.2–3.4](https://arxiv.org/html/2505.16333)
- Compute: the paper gives no GPU-hours figure in the text I searched. Inference benchmarks ran on a single A100-80GB. DEX "incurs negligible overhead" compared with native Diff attention, which "costs significantly more compute at test-time". — [DEX Sec. 4 / App.](https://arxiv.org/html/2505.16333)
- Ablation (Llama-3B): entropy-based head selection combined with learnable and annealed λ gives the best 11-benchmark average, 64.2%. — [DEX Table 5](https://arxiv.org/html/2505.16333)

### Inferences
- For a 0.5B model, the headline +2.6 average should be described as "driven largely by one benchmark". The training budget (<1B tokens, one epoch, attention-only updates) is realistic on a single node.

### Gaps
- No explicit GPU-hours or training-hardware figure was found for the DEX fine-tuning runs.
- I did not decode the 11th benchmark's name from the stripped table header. The 11-task list is in Table 1 of the paper.

## 2. DiffLoRA (arXiv 2507.23588)

### Takeaway
CONFIRMED and identified: the paper is arXiv 2507.23588, "DiffLoRA: Differential Low-Rank Adapters for Large Language Models" (Misrahi, Chirkova, Louis, Nikoulina; EPFL / NAVER LABS Europe, July 2025). On Llama-3.2-1B-Instruct RAG, DiffLoRA-64 scores 0.5202 against 0.601 for the LoRA baseline.

### Cited Findings
- Appendix D, Table 3 (RAG with top-5 docs, LLM-as-a-judge; averaged over BioASQ, FiQA, KILT-NQ, PopQA and TechQA):

  | Model | Avg |
  |---|---|
  | Llama-3.2-1B-Instruct | 0.5562 |
  | FullLoRA | 0.601 |
  | DiffLoRA-64 | 0.5202 |
  | DiffLoRA-64, λ=0.1 | 0.534 |
  | DiffLoRA-32 | 0.508 |
  | DiffLoRA-32 + GroupNorm | 0.0506 (collapsed) |
  | DiffLoRA-32 + Tulu3 | 0.4792 |

  — [DiffLoRA](https://arxiv.org/html/2507.23588v1)
- Correction to the wording: the baseline is labelled "FullLoRA" in the paper, not "plain LoRA". DiffLoRA also scores below the un-fine-tuned instruct model (0.556). — [DiffLoRA](https://arxiv.org/html/2507.23588v1)
- Abstract: "although DiffLoRA falls short of other parameter-efficient fine-tuning methods in most evaluation tasks, it shows interesting results in certain domains (+11 pts on LoRA for HumanEval)." — [DiffLoRA](https://arxiv.org/html/2507.23588v1)

### Inferences
- This is a negative result for retrofitting differential attention through low-rank adapters on a 1B model. It contrasts with DEX, which updates attention projections fully on selected heads and anneals λ.

### Gaps
- None for the claimed numbers.

## 3. Gated attention (Qiu et al., arXiv 2505.06708)

### Takeaway
CONFIRMED: first-token attention falls from 46.7% to 4.8%, and RULER at 128k rises from 31.65 to 58.82. The "MMLU +2.0" figure is for the element-wise SDPA gate on the 15B-A2B MoE (58.79 → 60.82). The cheaper head-wise gate gives +1.26 MMLU for about 1.6M added parameters.

### Cited Findings
- CONFIRMED (Fig. 2 caption): "The baseline model suffers from a significant attention sink, with an average of 46.7% of attention scores across layers directed towards the first token. Introducing a gate effectively alleviates this, reducing the proportion to 4.8%." In layer 21 the first-token share is 83% for the baseline and 4% with the gate. — [Gated Attention](https://arxiv.org/html/2505.06708)
- CONFIRMED (Table 5): setup is a model trained on 3.5T tokens, extended to 32k (RoPE base 10k → 1M, +80B tokens), then extended by YaRN to 128k. RULER at 128k: Baseline 31.65, SDPA-Gate 58.82. At 64k: 37.51 → 66.60. Within 32k without YaRN, the gains are small (32k: 79.50 → 79.77; 4k: 88.89 → 90.56). — [Gated Attention Table 5](https://arxiv.org/html/2505.06708)
- MMLU (Table 1, MoE-15A2B, 400B tokens):

  | Gate | Added params | MMLU | Avg PPL |
  |---|---|---|---|
  | None (baseline) | 0 | 58.79 | 6.026 |
  | SDPA element-wise sigmoid | 201M | 60.82 (+2.03) | 5.761 |
  | SDPA head-wise sigmoid | 1.6M | 60.05 (+1.26) | 5.792 |
  | v head-wise | 0.2M | 59.32 | — |

  The paper's summary says "up to 0.2 PPL reduction and 2 points on MMLU". — [Gated Attention](https://arxiv.org/html/2505.06708)
- Per-head gate cost: "Applying headwise gating … introduces very few additional parameters (less than 2M for the MoE-15A2B model) but still delivers substantial improvements." Wall-time latency overhead is "less than 2%". — [Gated Attention Sec. 3](https://arxiv.org/html/2505.06708)
- Scales tested: a 15B MoE (2.54B active) and a 1.7B dense model. Nothing below 1B was tested. — [Gated Attention](https://arxiv.org/html/2505.06708)

### Inferences
- Head-wise gating has a gate dimension of 1 per head, so it costs roughly d_model × n_heads parameters per layer. This explains the ~1.6M total for the MoE. It is the cheapest variant to add to a small model.

### Gaps
- No sub-1B results appear in the paper.

## 4. Diff Transformer V1 and Multi-Token Attention at 880M (Golovneva et al., Meta FAIR, arXiv 2504.00927)

### Takeaway
All claimed numbers come from the Multi-Token Attention (MTA) paper's v1 (April 2025), which trains 880M models on 105B SlimPajama tokens. They are CONFIRMED for v1. arXiv v2 revised several values: MTA perplexity is 10.91 (not 11.09), Diff is 11.15, and MTA memory and slowdown are larger (73.8 GB; 5.7k TPS).

### Cited Findings
- v1 Table 2, pretraining average validation perplexity: Transformer 11.25, Diff Transformer 11.14, MTA 11.09, MTA without group norm 11.16. After long-context fine-tuning: 11.02 / 10.89 / 10.85. — [MTA v1](https://arxiv.org/html/2504.00927v1)
- v2 (current) Table 2: Transformer 11.25, Diff 11.15, Talking-heads 11.04, MTA 10.91. After long-context fine-tuning: 11.02 / 10.89 / 10.88 / 10.65. — [MTA v2](https://arxiv.org/html/2504.00927)
- CONFIRMED (v1 Table 5), multi-needle accuracy on the long-context fine-tuned models at 4K:

  | Model | N=2 | N=4 | N=6 |
  |---|---|---|---|
  | Transformer | 90.5 | 41.1 | 31.9 |
  | Diff Transformer | 95.7 | 73.8 | 60.0 |
  | MTA | 97.6 | 77.7 | 67.0 |
  | MTA w/o GN | 94.4 | 96.3 | 79.0 |

  The "31.9 → 60.0" claim is therefore Transformer vs Diff. Note that MTA without group norm scores higher than MTA on this test. — [MTA v1](https://arxiv.org/html/2504.00927v1)
- CONFIRMED (v1 Table 10, 32× H200 with unoptimized code):

  | Model | Memory (GB) | TPS (thousands) |
  |---|---|---|
  | Transformer | 17.5 | 54.3 |
  | Diff Transformer | 21.6 | 17.6 |
  | MTA | 59.1 | 11.5 |

  This gives 3.38× the memory and 4.72× slower throughput for MTA, matching the claimed ~3.4× / ~4.7×. In v2 (Table 9) MTA uses 73.8 GB and runs at 5.7k TPS, about 4.2× memory and 9.5× slower. The authors attribute the slowdown to not using fused SDPA kernels. — [MTA v1](https://arxiv.org/html/2504.00927v1); [MTA v2](https://arxiv.org/html/2504.00927)
- Parameter overhead is negligible: 876.55M (Transformer) vs 876.57M (Diff) vs 876.58M (MTA). — [MTA v2 Table 8](https://arxiv.org/html/2504.00927)

### Inferences
- This is the only independent same-setup comparison of Diff Transformer that I located. It shows a small perplexity gain from Diff (about 0.1) but a large gain on multi-needle retrieval.

### Gaps
- Which version the original notes cited is unknown. Cite v1 explicitly or update to the v2 numbers.

## 5. Softpick (arXiv 2504.20966, v4)

### Takeaway
CORRECTED: the numbers 15.10 → 17.87 (Wikitext ppl) and 49.4 → 43.5 (LAMBADA acc) are softmax vs softpick, both at 1.8B. They do not compare 340M with 1.8B. At 340M softpick roughly matches softmax.

### Cited Findings
- Table 1: at 1.8B, softmax vs softpick gives Wikitext word ppl 15.10 vs 17.87 (+2.77), LAMBADA acc 49.43 vs 43.51 (−5.92), LAMBADA ppl 11.38 vs 15.81, ARC-e acc_norm 67.21 vs 62.04, and SciQ acc_norm 86.40 vs 80.40. At 340M: Wikitext 23.85 vs 24.32, LAMBADA acc 36.25 vs 36.21, LAMBADA ppl 30.33 vs 28.63, and SciQ acc_norm 74.90 vs 77.30. — [Softpick](https://arxiv.org/html/2504.20966)
- The 340M models were trained for 100k steps (52B tokens). The final training-loss gap was 0.004 at 340M and 0.12 at 1.8B. The authors state that softpick "is competitive with softmax at 340M, it underperforms at 1.8B". They offer two hypotheses: underscoring of long contexts, and dead or dormant heads. — [Softpick](https://arxiv.org/html/2504.20966)

### Inferences
- Softpick is viable at the ~300M scale but scales poorly under the authors' recipe.

### Gaps
- None for the claimed numbers.

## 6. Scalable-Softmax, SSMax (Nakanishi, arXiv 2501.19399)

### Takeaway
CONFIRMED: the model is 162M parameters (12 layers, 12 heads). It generalizes to about 10× the training length. Swapping in SSMax after pretraining helps but performs "noticeably worse" than training with it from the start.

### Cited Findings
- "The model has 12 layers, 12 attention heads, and 162M parameters." It was trained on SlimPajama with sequence length 1024 for 200k iterations (≈419B tokens). SSMax adds only 144 scalar parameters (one per layer-head). — [SSMax](https://arxiv.org/html/2501.19399)
- Length generalization: SSMax models "maintain lower test loss across long contexts, demonstrating improved generalization to sequence lengths up to approximately 10 times the training sequence length". On needle-in-a-haystack, the SSMax model retrieves key information "even at context sizes approximately 10 times longer than in training". RoPE θ was raised 50× without retraining. — [SSMax](https://arxiv.org/html/2501.19399)
- Post-pretraining swap: in configuration (e), softmax is replaced with SSMax after pretraining, with s initialized to ≈0.168 (the reciprocal of the average log n). It "exhibits higher loss at shorter context sizes, suggesting that post-training replacement struggles to adapt to shorter contexts". On needle-in-a-haystack, "(e) achieves a substantial improvement over (a) but still performs noticeably worse than (b), suggesting limited adaptability when switching post-training." Configuration (f) switches during the final phase of pretraining; it "slightly outperforms (e)" but "remains significantly behind (b)". — [SSMax](https://arxiv.org/html/2501.19399)

### Gaps
- None.

## 7. Veličković et al., "softmax is not enough (for sharp out-of-distribution)" (arXiv 2410.01104)

### Takeaway
CONFIRMED. The dispersion result is two statements: Lemma 2.1 (bounded logits imply Θ(1/n) coefficients) and Theorem 2.2 (with a finite vocabulary, every softmax head in an MLP+attention Transformer must eventually fall below any ε).

### Cited Findings
- Lemma 2.1 ("softmax must disperse"): "Let e⁽ⁿ⁾ ∈ ℝⁿ be a collection of n logits going into the softmax_θ function with temperature θ>0, bounded above and below s.t. m ≤ e_k⁽ⁿ⁾ ≤ M for some choice of constants m, M ∈ ℝ. Then, as more items are added (n → +∞), it must hold that, for each item 1 ≤ k ≤ n, softmax_θ(e⁽ⁿ⁾)_k = Θ(1/n)." — [Veličković et al.](https://arxiv.org/html/2410.01104)
- Theorem 2.2 ("softmax in Transformers over vocabularies must disperse"): inputs come from a finite set 𝒳 ⊂ ℝᵐ (|𝒳| < ∞), and the architecture is built from MLPs and softmax self-attention layers. Then "for any θ>0 and ε>0, there must exist an n ∈ ℕ such that softmax_θ(e⁽ⁿ⁾)_k < ε" for all items. In the paper's words: "attention coefficients must disperse in all global Transformer heads if the input vocabulary is finite." The proof uses compactness: continuous FFNs and convex-combination attention keep features in a compact set, so the logits are bounded. — [Veličković et al.](https://arxiv.org/html/2410.01104)
- The paper notes that the logit spread (M−m) controls the rate of dispersion. Zero temperature (hard attention) escapes the result but is hard to train. — [Veličković et al.](https://arxiv.org/html/2410.01104)

### Gaps
- The exact "< ε" inequality was partly garbled in the HTML extraction (the "<" sign was stripped). The paraphrase above follows the surrounding text and the paper's own summary sentence.

## 8. Sanford, Hsu & Telgarsky, "Transformers, parallel computation, and logarithmic depth" (ICML 2024, arXiv 2402.09268)

### Takeaway
CONFIRMED with a precise form: the construction uses depth L = ⌊log₂ k⌋ + 2 with one head and O(1) width (Theorem 4.2; the theorem number is 4.2, not 4.1). There is a matching conditional lower bound of Ω(log k). The one-layer impossibility result is specifically about 1-layer transformers with chain-of-thought (Corollary 5.6). It is not a bare statement that "one layer can't do it".

### Cited Findings
- Theorem 4.2: "For any k ∈ ℕ and alphabet Σ with |Σ| ≤ N, there exists T ∈ MaskTransformer^N_{m,L,H} that computes hop_k … with m = O(1), L = ⌊log₂ k⌋ + 2, and H = 1." — [Sanford et al.](https://arxiv.org/html/2402.09268)
- Lower bound (Corollary 4.3, conditional on the MPC conjecture 2.4): any transformer with mH = O(k^{1−ε}) that computes hop_k has depth L = Ω(log k). Empirically, "a performance threshold appears to specifically lie at ⌊log₂ k⌋+2 that coincides with Theorem 4.2." — [Sanford et al.](https://arxiv.org/html/2402.09268)
- Corollary 5.6 (1-layer result): "Any T ∈ MaskTransformer^{N+N_CoT}_{m,1,H} that computes hop_k(X)_N with N_CoT tokens of chain-of-thought requires either N_CoT ≥ k or mHp = Ω(N/k⁶)." In words, a single layer needs either chain-of-thought linear in k or width/heads/precision that grow polynomially with N. — [Sanford et al. Sec. 5.4](https://arxiv.org/html/2402.09268)

### Inferences
- For small models, multi-hop retrieval within one forward pass needs depth that grows like log₂ k. Shallow models must instead use chain-of-thought steps that grow linearly in k.

### Gaps
- None.

## 9. JuICE (Li et al., "Taming Knowledge Conflicts in Language Models", ICML 2025, arXiv 2503.10996)

### Takeaway
CONFIRMED in substance. JuICE fixes K = 5 heads (an example value) and uses dual-run scaling of their outputs. On context-faithfulness tasks it averages 66.2–66.8 across three models, against 34.9–45.0 for the original models and up to 60.0 for the strongest baseline. The claimed "35–51" range matches the original-to-CAD range.

### Cited Findings
- Method: "In practice, we fix K to be a constant number (e.g., 5) and determine the scaling factors using the validation set." Stage 1 identifies heads that consistently help under positive or negative scaling, using very few samples (4 in the PH3_s comparison). Stage 2 runs the model twice, saving the head outputs and then adding scaled copies of them. — [JuICE](https://arxiv.org/html/2503.10996)
- Table 4 (enhancing contextual knowledge), averages over NQ-Swap, Hate-Speech Ending, History-of-Science QA, Proverb Ending and Proverb Translation:

  | Model | Original | Prompt | CAD | PH3_l | JuICE |
  |---|---|---|---|---|---|
  | Gemma | 45.0 | 47.4 | 51.1 | 60.0 | 66.2 |
  | Llama2 | 34.9 | 39.5 | 41.4 | 51.9 | 66.6 |
  | Llama3 | 43.4 | 46.9 | 51.2 | 55.6 | 66.8 |

  — [JuICE Table 4](https://arxiv.org/html/2503.10996)
- Correction to the wording: "35–51" covers Original through CAD. The PH3_l baseline reaches 51.9–60.0, so the gap to the best baseline is smaller (6–15 points). — [JuICE](https://arxiv.org/html/2503.10996)

### Gaps
- I did not verify the exact model sizes (Gemma variant and Llama sizes) from the experimental-setup text. All are likely ≥2B, so this is not sub-1B evidence.

## 10. Retrieval heads (Wu et al., arXiv 2404.15574)

### Takeaway
CONFIRMED: retrieval heads are "less than 5%" of heads. The paper covers 4 families and 6 scales, and the smallest model tested is 6B (Yi-6B). It contains no sub-1B evidence.

### Cited Findings
- "sparse: only a small portion (less than 5%) of the attention heads are retrieval." Details: "Only about 3% to 6% of the attention heads have a retrieval score larger than 0.1". About 45–73% of heads have a retrieval score of 0, and 25–52% have a score between 0 and 0.1. — [Retrieval Heads](https://arxiv.org/html/2404.15574)
- Models (Table 1): Llama-2-7B (+80K, 13B-64K), Mistral-7B-v0.2 (+Instruct, Mixtral-8x7B), Yi-6B (+200K, Yi-34B-200K), Qwen1.5-14B (+Chat). The smallest is Yi-6B / Llama-2-7B, so the smallest tested is 6B. — [Retrieval Heads Table 1](https://arxiv.org/html/2404.15574)
- Within a family, retrieval-score maps correlate at Pearson r > 0.8; across families the correlation is below 0.1. — [Retrieval Heads](https://arxiv.org/html/2404.15574)

### Gaps
- The paper has no sub-6B evidence.

## Gap fill A: retrieval heads, attention sinks and entropy in models under 1B

### Takeaway
The literature on sub-1B models is thin but not empty. Attention sinks are documented down to Pythia-14M, and controlled small LLaMA-style models (~60M) also develop sinks. Sigmoid attention without normalization removes sinks up to 1B. A NeurIPS 2026 paper directly tests middle-of-context needle retrieval in Gemma-3-270M, Gemma-3-1B, Qwen1.5-0.5B and Qwen2.5-0.5B. I found no retrieval-head (Wu et al.-style) analysis of Qwen2.5-0.5B, SmolLM, LFM2-350M or Gemma-3-270M.

### Cited Findings
- Gu et al. (ICLR 2025, "When Attention Sink Emerges in Language Models: An Empirical View", arXiv 2410.10781): "attention sink emerges in small LMs, even in Pythia-14M". Models measured include Pythia-14M through 12B, OPT-125M/350M/1.3B and GPT-2. Their controlled pretraining experiments use a ~60M-parameter LLaMA-style model (d=768, 10 blocks, 8 heads; non-embedding parameters). "After relaxing such dependence by replacing softmax attention with other attention operations, such as sigmoid attention without normalization, attention sinks do not emerge in LMs up to 1B parameters." — [Gu et al. 2410.10781](https://arxiv.org/html/2410.10781v2)
- "Attention Architecture and Positional Retrieval in Small Language Models" (NeurIPS 2026) runs a controlled needle-in-a-haystack test on Gemma 3 270M and Gemma 3 1B (sliding-window attention), Qwen1.5-0.5B (MHA) and Qwen2.5-0.5B (GQA). It finds that "Gemma 3 270M's middle-position accuracy collapses to 0% by 4K tokens and remains at 0% through 16K, while both the MHA and GQA models retain 100% middle-position accuracy at every tested length through 8K." Gemma 3 1B shows "a different and non-monotonic failure pattern at 16K". Only the abstract page was available. — [NeurIPS 2026 abstract](https://neurips.cc/virtual/2026/162683)
- Wong et al., "On the Existence and Behavior of Secondary Attention Sinks" (arXiv 2512.22213, v3 March 2026) covers 11 model families. Secondary sinks arise in middle layers, are formed by specific MLPs and draw less attention mass than BOS sinks. The model sizes covered were not verified. — [arXiv 2512.22213](https://arxiv.org/abs/2512.22213)

### Gaps
- No retrieval-head or attention-entropy study specific to SmolLM, LFM2-350M or Gemma-3-270M was found in this pass. (LFM2 is largely convolutional plus GQA, so a retrieval-head analysis would cover only its few attention layers.)
- The NeurIPS 2026 paper was verified from its abstract only, not its full text.

## Gap fill B: head-to-head comparisons of attention variants on the same small model

### Takeaway
Three same-setup comparisons exist at or near small scale:
- MTA paper (880M): Transformer vs Diff vs Talking-heads vs MTA.
- Softpick paper (340M, short 10k-step runs): sink rate and activations for 8 sink-mitigation variants.
- SSMax paper (162M): softmax vs SSMax variants, including a post-hoc swap.

### Cited Findings
- Softpick v4 Table 3 compares sink-free variants. All are trained with the 340M config for 10k steps; they are "minimally trained, we do not run benchmarks". Sink rate at two thresholds: Softmax 47.97/34.89, Softpick 0.02/0.00, Scaled Softpick 0.01/0.00, Gated Attention 5.00/2.00, ReLU-Softmax 8.16/4.56, GPT-OSS sink 19.34/8.78, Softmax+1 (off-by-one) 24.38/16.36, Rectified-only 33.08/25.60. Activation kurtosis: Softmax 6452.72, Gated 135.62, Softpick 281.57, Rectified-only 11054.50. Attention sparsity: Softpick 92.74%, Gated 0.73%. — [Softpick v4](https://arxiv.org/html/2504.20966)
- MTA paper (880M, 105B tokens), same data and recipe, v2: avg ppl Transformer 11.25, Diff 11.15, Talking-heads 11.04, MTA 10.91. See item 4 for needle and throughput numbers. — [MTA](https://arxiv.org/html/2504.00927)
- Gated-attention paper: Table 1 compares 15 gating positions and variants on the same MoE-15A2B. This is a same-model comparison, but not a small model. — [Gated Attention](https://arxiv.org/html/2505.06708)
- DEX Table 1: LoRA, PiSSA, full FT, GaLore, APOLLO and DEX all applied to the same Qwen2.5-0.5B with the same 887M-token data. This is the cleanest sub-1B same-model comparison, but it compares adaptation methods rather than attention variants trained from scratch. — [DEX](https://arxiv.org/html/2505.16333)

### Inferences
- No single study trains Diff, gated, softpick, SSMax and MTA together on the same sub-1B model with downstream benchmarks. The closest is the Softpick paper, which reports only sink and activation metrics.

### Gaps
- I did not find a from-scratch, benchmarked head-to-head of all of these variants below 1B.
