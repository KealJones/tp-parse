# Multi-hop composition fixes for small transformers (~350M–500M)

Scope: which interventions help a small model chain lookups (person → town → town's population), and which don't. Each number below comes from the full text or abstract I fetched in October 2026. Anything I could not verify is marked **[UNVERIFIED]** or listed under Gaps.

## Q1: Does architectural recurrence (looped depth / weight sharing) fix multi-hop composition in small models?

### Takeaway
Yes, with clear evidence at 0.5B–2.6B. Retrofitting a weight-tied recurrent block onto Qwen2.5-0.5B-Instruct gives 84.0% on a synthetic multi-step task. A 6M-parameter LoRA version reaches 83.8%. A same-size scratchpad model gets 72.1%, direct answering 27.7%, and a 3x larger dense model 36.6%. The gains do not transfer zero-shot to new surface forms. Looped models also clearly beat same-size dense models on compositional tool calling (BFCL parallel/multiple, NESTful), but not on single API calls (API-Bank). From-scratch studies agree that weight sharing between lower and upper layers unlocks out-of-distribution (OOD) second-hop composition.

### Cited Findings
**arXiv 2608.11233: Shapiro, "Retrofitting Recurrent Depth into a Pretrained Language Model…" (v1, 2026-07-31). Verified from full HTML.**
- Setup: Qwen2.5-0.5B-Instruct is split into Prelude, a weight-tied Recurrent Block, and Coda. Two training budgets: the full block (180.6M trainable parameters) and a rank-16 LoRA adapter (6,007,425 forward-active trainable parameters; the base weights stay frozen). — [arXiv 2608.11233](https://arxiv.org/html/2608.11233)
- Table 6, on a frozen synthetic family of 1,792 rows at depths 1–14 — [arXiv 2608.11233](https://arxiv.org/html/2608.11233):

  | Arm | Overall | Depths 11–14 |
  |---|---|---|
  | Recurrent, full block | 84.04% | 53.13% |
  | Recurrent, r16 adapter | 83.76% | 48.24% |
  | Dense 0.5B, scratchpad | 72.10% | 2.54% |
  | Dense 0.5B, direct | 27.68% | 11.72% |
  | Dense 1.5B, direct | 36.61% | 11.33% |

  The only 1.5B arm is a direct-answer control. The paper has no larger scratchpad baseline.
- The scratchpad model matches the recurrent model inside its trained horizon (127/128 at depth 10), then collapses: 13/128 at depth 11 and 0 at depths 12–14. — [arXiv 2608.11233](https://arxiv.org/html/2608.11233)
- Extrapolation: valid out to about 1.44–1.50x the supervised depth. The N24 model reaches 91.4% at depth 14, 70.3% at depth 18 and 10.9% at depth 22. — [arXiv 2608.11233](https://arxiv.org/html/2608.11233)
- Adapter vs full block: the adapter leads on depths 1–11; the full block leads on depths 12–14 (175/384 vs 136/384). — [arXiv 2608.11233](https://arxiv.org/html/2608.11233)
- Transfer to new surface forms (verbal "relay" and "pointer" renderings):
  - Zero-shot transfer is minimal: the adapter scores 16.2% and 17.2%, and the full block before verbal training 17.4% and 20.3%.
  - After verbal fine-tuning the full block reaches 86.0% and 79.0%.
  - With matched verbal training at the adapter budget, starting from the installed mechanism beats fresh training by 60.29% vs 41.73% (+18.55 points) at step 3,000. The fresh arm was stopped early by a guardrail.
  - — [arXiv 2608.11233](https://arxiv.org/html/2608.11233)
- Compute and latency (one A100, batch size 1, median per row):
  - The full-block recurrent model takes 28.8 ms at depth 1 and 301.8 ms at depth 14.
  - The adapter takes 42.1 ms at depth 1 and 488.4 ms at depth 14.
  - The scratchpad model takes about 2,284 ms (96 tokens); direct 0.5B about 770 ms; direct 1.5B about 905 ms.
  - This is "7.6x faster" than the scratchpad at depth 14. The paper calls this descriptive and makes no claim about batched throughput.
  - Training tokens and FLOPs are **not matched** across arms, so this is a system-level comparison, not a causal estimate for the architecture alone.
  - — [arXiv 2608.11233](https://arxiv.org/html/2608.11233)
- Retention: at loop 1, the full block is non-inferior to the base model on ARC-Easy and ARC-Challenge (3-point margin).
- Limitations:
  - Learned depth selection **failed**, so every result uses a forced loop count.
  - Adding an inverse task after installation caused catastrophic interference.
  - The adapter and N24 results are single-seed.
  - — [arXiv 2608.11233](https://arxiv.org/html/2608.11233)

**arXiv 2608.18171: Popescu, Sáez de Ocáriz Borde, Liò, "Looped Language Models Improve Compositional Tool Calling" (2026-08-17). Verified from full HTML.**
- Models:
  - Native looped: Ouro-1.4B and Ouro-2.6B (up to 4 recurrent iterations, about 7.7T pretraining tokens).
  - Dense baselines: Qwen3-1.7B/4B/8B and Llama-3.2-1B/3B, Llama-3.1-8B.
  - Retrofitted looped: Llama-3.2-1B and OLMo-2-1B.
  - Fine-tuning: LoRA r32 on the Hermes function-calling data, 2 epochs, one A100.
  - — [arXiv 2608.18171](https://arxiv.org/html/2608.18171)
- BFCL AST overall (after SFT):
  - Native looped vs dense: Ouro-1.4B 79.3, Ouro-2.6B 86.4, Qwen3-1.7B 40.7, Qwen3-4B 56.7, Llama-3.2-3B 78.4.
  - On Parallel-Multiple: Ouro-2.6B 76.5 vs Qwen3-4B 5.5.
  - Retrofits vs their parents: Llama-3.2-1B 21.4 → 32.9 looped; OLMo-2-1B 39.1 → 41.8 looped.
  - — [arXiv 2608.18171](https://arxiv.org/html/2608.18171)
- NESTful (nested, dependent calls; win rate): Ouro-1.4B 0.110 → 0.191 after SFT; Ouro-2.6B 0.190 → 0.371. Dense models score Qwen3-4B SFT 0.063, Llama-3.2-3B SFT 0.095 and Qwen3-8B instruct 0.345. — [arXiv 2608.18171](https://arxiv.org/html/2608.18171)
- API-Bank (single calls; Call/Exact) is mixed:
  - Ouro-1.4B 75.1/70.2 vs Qwen3-4B 76.6/73.8.
  - Llama-1B looped 17.9/16.2 vs its parent 16.3/14.1.
  - OLMo-1B looped 34.0/30.3 vs its parent 37.1/33.2, so the retrofit is worse here.
  - — [arXiv 2608.18171](https://arxiv.org/html/2608.18171)
- Accuracy generally rises with recurrent depth, with the biggest gains on Multiple and Parallel. Adaptive stopping matches the best fixed depth with fewer iterations. Limitations: no dense twin trained the same way as Ouro exists; retrofits remain "substantially weaker" than native looped models; all evaluations are static single-turn. — [arXiv 2608.18171](https://arxiv.org/html/2608.18171)

**arXiv 2405.15071: Wang et al., "Grokked Transformers are Implicit Reasoners" (2024). Verified from full HTML.**
- Setup: an 8-layer, 768-dimension GPT-2-style model trained from scratch.
- Composition reaches near-perfect in-distribution accuracy after grokking, but "OOD generalization is never observed," even after 2M steps. The comparison task, by contrast, does generalize systematically.
- — [arXiv 2405.15071](https://arxiv.org/html/2405.15071)
- Fix: sharing parameters between the first 4 and last 4 layers (Universal Transformer-style) "can unlock OOD generalization," but slowly. OOD numbers appear only in a figure (Fig. 14), not in the text. — [arXiv 2405.15071](https://arxiv.org/html/2405.15071)
- What drives generalization is the ratio φ of inferred facts to atomic facts (the "critical data distribution"), not dataset size. — [arXiv 2405.15071](https://arxiv.org/html/2405.15071)
- On a complex reasoning task with a large search space, the grokked transformer scores 99.3%. GPT-4-Turbo scores 31.3–33.3% and Gemini-Pro-1.5 11.3–37.3%. — [arXiv 2405.15071](https://arxiv.org/html/2405.15071)

**arXiv 2608.07261: Zhang et al., "Why Knowing Both Hops Is Not Enough" (v3, 2026-08-28). Verified from full HTML.**
- Setup: an 8-layer, 768-dimension GPT-2-style model, plus a Llama-architecture model, both trained from scratch on symbolic data and Wikidata5M two-hop data. No pretrained LMs are tested.
- Main finding: models generalize when the second hop follows the training distribution but "always fail when it deviates." The cause is a layer mismatch: lower layers build the bridge entity, but upper layers learn to map it to outputs rather than reason over it.
- — [arXiv 2608.07261](https://arxiv.org/html/2608.07261)
- Fix 1, a looped model sharing parameters between the top 4 and bottom 4 layers: bridge-representation cosine alignment S_bridge(e₂) rises from −0.003 to 0.813.
- The only accuracy table (Table 2; it appears to be looped results, but the text doesn't say so explicitly) gives:

  | Setup | Test-II | Test-IO | Test-OO | Test-OI |
  |---|---|---|---|---|
  | GPT-Symbolic | 1.0 | 0.97 | 0.84 | 0.97 |
  | Llama-Symbolic | — | 0.83 | 0.54 | — |
  | GPT-Real | — | 0.79 | 0.66 | — |
  | Llama-Real | — | 0.74 | 0.62 | — |

  The baseline is described only as "near chance" on IO/OO.
- Fix 2, continual training of the upper layers on atomic facts, is described as "substantially" improving IO/OO, with no numbers given.
- — [arXiv 2608.07261](https://arxiv.org/html/2608.07261)

**Huginn (Geiping et al. 2025, arXiv 2502.05171) and follow-up**
- Huginn is a 3.5B recurrent-depth model ([arXiv 2502.05171](https://arxiv.org/pdf/2502.05171)). I did not fetch its result tables, so its specific numbers are **[UNVERIFIED]**.
- Lu et al. 2025 decoded Huginn-3.5B's latent states on arithmetic. They found "limited evidence of interpretable latent CoT," and more recurrence gave only small gains, "well below" explicit-CoT models. — [arXiv 2507.02199](https://arxiv.org/abs/2507.02199)

### Inferences
- For a 350–500M model, the most directly relevant result is 2608.11233. On a controlled chained-operation task, a cheap LoRA-sized recurrent retrofit (about 6M parameters) roughly triples direct-answer accuracy, and it beats a 3x larger dense model and same-size scratchpad training, especially beyond the trained depth. The big caveat is that it did not transfer zero-shot to new phrasings. Each new surface form needs its own training data, though a model with recurrence already installed learns it faster.
- Recurrence helps most where calls depend on or compose with each other (NESTful, BFCL parallel-multiple). That matches the user's "lookup, then lookup again" failure better than single-call benchmarks do. Retrofits at 1B gave smaller and inconsistent gains than natively looped pretraining.
- Recurrent-depth models with frontier-style pretraining (Huginn) show weak evidence of interpretable latent step-by-step reasoning. The clean wins all come from narrow, well-specified tasks.

### Gaps
- Huginn's benchmark numbers were not verified; I found no Huginn-style result below 1B.
- 2608.07261 gives no accuracy numbers for its non-looped baseline or for the continual-training fix.
- 2405.15071's OOD numbers with parameter sharing appear only in a figure.
- No paper here tests recurrence on a model as small as 350M with natural-language entity → attribute chains of the user's type.

## Q2: Data and training: curriculum, diverse templates, data scaling, RL with per-step rewards

### Takeaway
For implicit (no-CoT) k-hop reasoning, the training data needed grows exponentially with the number of hops and the layers needed grow linearly (Yao et al., EMNLP 2025). Curriculum learning reduces this need but does not remove it. What matters is the mix of composed versus atomic examples, not raw data volume. Evidence that more template diversity helps is mostly from toy models and depends on conditions. I verified no per-step-reward RL paper.

### Cited Findings
- Yao, Du, Zhu, Hahn, Koller, "Language models can learn implicit multi-hop reasoning, but only if they have lots of training data":
  - Venue: EMNLP 2025 main, paper 490 per the ACL Anthology listing ([ACL Anthology](https://preview.aclanthology.org/setup/2025.emnlp-main.490)). The arXiv v2 itself shows no venue.
  - Quoted claim: "the required training data grows exponentially in k, and the required number of transformer layers grows linearly in k."
  - Setup: GPT-2-small architecture trained from scratch with RoPE, on 500 entities and 20 relations.
  - 3-hop accuracy: 2.5% at 1x data, 4.9% at 5x, 94.6% at 10x.
  - 4-hop accuracy: 2.0% at 1x, 6.3% at 50x, 100% at 100x (k-hop_large).
  - Curriculum (easier hops first) "significantly reduces the required training data" but "does not completely solve" the growth. Mixing tasks gives only modest gains.
  - — [arXiv 2505.17923](https://arxiv.org/html/2505.17923)
- Grokked transformers: the ratio of inferred to atomic facts, not dataset size, is "the actual deciding factor" for generalization. — [arXiv 2405.15071](https://arxiv.org/html/2405.15071)
- Template diversity (Behnia, Deora, Thrampoulidis 2025; a 4-layer toy transformer):
  - Higher diversity slows in-distribution factual learning.
  - On held-out templates, "diversity becomes essential for non-trivial factual learning" in some contextual structures.
  - Intermediate diversity works best under a fixed budget.
  - Multi-step reasoning was not evaluated.
  - — [arXiv 2510.16096](https://arxiv.org/html/2510.16096)
- 2608.11233: scratchpad (serialized reasoning) training at 0.5B matched recurrence within its trained depth but collapsed beyond it (2.5% at depths 11–14). — [arXiv 2608.11233](https://arxiv.org/html/2608.11233)
- Distillation with decomposition (Socratic CoT, Shridhar et al.): training small models as a separate decomposer and subproblem solver "boosts the performance of smaller models over 70% compared to the baselines" on GSM8K, StrategyQA and SVAMP. GPT-2 large sometimes beat a 10x larger model. The per-dataset numbers were not visible in the abstract. — [arXiv 2212.00193](https://arxiv.org/abs/2212.00193)

### Inferences
- To make a small model compose two hops internally, train with many composed examples relative to atomic ones, use a curriculum from 1-hop to 2-hop, and add plenty of surface-form variety. Expect a steep cost for each extra hop. At 2 hops (person → town → population) the data cost is manageable; at 3–4 hops it is not.
- Scratchpad or CoT training works inside the trained depth range. Since the user's chains are short (2 hops), explicit step-by-step output should be enough.

### Gaps
- I found no verified paper measuring held-out compositional generalization as a function of the number of task templates in a 100M–1B pretrained LM. The closest are toy-scale results (2510.16096) and FLAN-style instruction-diversity results at much larger scale (not verified here).
- RL with per-step or process rewards for multi-hop in small models was not researched within the tool budget, so I have no verified numbers.
- The exact curriculum data reduction in 2505.17923 (its Section 6) was not extracted.

## Q3: Diagnosis and inference-time interventions (back-patching, late hopping)

### Takeaway
In 7B–70B models, the first hop is resolved early in the network. The second hop often fails because by the time the bridge entity is available, the later layers no longer hold the knowledge needed. Back-patching (re-injecting a later layer's hidden state into an earlier layer) fixes up to 66% of failures. It is an oracle diagnostic, not a usable technique.

### Cited Findings
- Biran et al., "Hopping Too Late" (EMNLP 2024). Models: LLaMA 2 7B/13B, LLaMA 3 8B/70B, Pythia 6.9B/12B. — [arXiv 2406.12775](https://arxiv.org/html/2406.12775)
- Share of failures fixed by back-patching, at the first-hop token t1 / the last token t2 — [arXiv 2406.12775](https://arxiv.org/html/2406.12775):

  | Model | t1 | t2 |
  |---|---|---|
  | LLaMA 2 7B | 41.0% | 42.5% |
  | LLaMA 2 13B | 32.4% | 36.1% |
  | LLaMA 3 8B | 38.8% | 47.2% |
  | LLaMA 3 70B | 57.3% | 57.8% |
  | Pythia 6.9B | 66.3% | 56.4% |
  | Pythia 12B | 63.2% | 61.8% |

- These rates use the best source and target layer pair for each case, which requires knowing the answer, so the method is "not yet a practical inference technique." — [arXiv 2406.12775](https://arxiv.org/html/2406.12775)

### Inferences
- The same mechanism (the bridge entity is resolved too late for the remaining layers) is what looping or parameter sharing addresses in 2608.07261 and 2405.15071. Recurrence effectively gives the second hop "more layers after the bridge." This links the diagnosis to the architectural fix.
- A shallow 350–500M model has fewer layers left after the bridge entity is formed, so the problem is likely worse there. This is an inference; no measurement here covers that size.

### Gaps
- Hopping Too Late tested no models under 6.9B.

## Q4: Should the model compose internally, or should the harness force one hop per tool step?

### Takeaway
Across the evidence, explicit decomposition, where each hop is a separate step or tool call, is the most reliable fix for chains of 2–3 hops. Internal composition needs special architecture, steep amounts of data, or both, and it fails on new surface forms. I found no single paper that runs a controlled head-to-head of "internal vs harness-forced" for models of 350–500M.

### Cited Findings
- Press et al. 2022, "Measuring and Narrowing the Compositionality Gap":
  - As models memorize more facts, "the compositionality gap does not decrease."
  - Self-ask, where the model asks and answers its own follow-up questions, improves accuracy, and adding a search engine for the follow-ups "additionally improves accuracy."
  - The ~40% gap figure and the self-ask numbers are **[UNVERIFIED]**; they were not in the abstract.
  - — [arXiv 2210.03350](https://arxiv.org/abs/2210.03350)
- Socratic CoT: an explicit decomposer plus solver gives small models over 70% relative gains over baselines. — [arXiv 2212.00193](https://arxiv.org/abs/2212.00193)
- 2608.11233: within its trained depth, explicit serialized steps (scratchpad) match latent recurrence at 0.5B. Their weaknesses are length extrapolation and latency (about 2.3 s vs 0.3 s per row), not short-chain accuracy. — [arXiv 2608.11233](https://arxiv.org/html/2608.11233)
- Huginn latent-reasoning analysis: gains from more recurrence are "well below" explicit CoT. — [arXiv 2507.02199](https://arxiv.org/abs/2507.02199)
- Relevant benchmarks for testing this, not read in full: ToolHop ([arXiv 2501.02506](https://arxiv.org/pdf/2501.02506)), VAKRA ([arXiv 2608.12282](https://arxiv.org/pdf/2608.12282)) and NESTful (used in 2608.18171).

### Inferences
- For the user's failure (finds the town, never looks up its population), the cheapest and most reliable fix is likely harness-side:
  - Force the second tool call through a plan, state machine, or constrained decoding: after a lookup returns an entity, require another lookup until the requested attribute is filled.
  - Optionally train on traces that show one hop per tool call.
- Training or architecture changes (looping, curriculum) are worth it only if internal composition is a requirement.
- This recommendation is inferred from the evidence above, not from a direct controlled comparison at 350–500M.

### Gaps
- I found no verified small-model (<1B) head-to-head of internal composition vs harness-enforced decomposition: least-to-most, ReAct step forcing, or grammar/state-machine-constrained tool ordering.
- Least-to-most's SCAN result (about 99.7% vs 16% for CoT) was obtained with code-davinci-002, a large model, and was not re-verified here. **[UNVERIFIED]**
