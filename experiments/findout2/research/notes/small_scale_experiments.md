# Cheap experiments on ~100M–500M models: attention focusing, MLP shrinking, multi-hop tool composition

Context: ~$40 HF Jobs budget (L4 ~$0.80/h → ~50 L4-hours; A100 ~$2.50/h → ~16 A100-hours). Target models are LFM2.5-350M, Qwen2.5-Coder-0.5B-Instruct and Qwen3.5-0.8B/2B. The failure being targeted is multi-hop tool chaining: the model finds the bridge entity (the town) but never issues the second lookup (its population).

Notation: items marked "(prior knowledge, not re-fetched)" are well-known papers cited by arXiv ID from memory rather than read this session. Cost and time figures marked "Inference" are my own estimates, not reported numbers.

## Q1. Attention modifications that work when retrofitted onto an existing pretrained model

### Takeaway
The only retrofit with direct evidence at about 0.5B is DEX, a differential-attention extension. It fine-tunes only the attention projections on about 0.4–0.9B tokens and gave Qwen2.5-0.5B +2.6 points on an 11-benchmark average. Gated attention and Scalable-Softmax are proven when trained from scratch, but retrofit evidence is weak or missing. None of these targets the user's failure, which is behavioural (not issuing the second tool call) rather than retrieval within context.

### Cited Findings
- **DEX (Differential Extension)** reuses the pretrained softmax scores and applies a learnable differential operation on the output, O' = O − λ·f_D(O), instead of splitting heads into two groups. It adapts only about half the heads in each layer, chosen by attention entropy, and anneals λ over training. — [Understanding Differential Transformer Unchains Pretrained Self-Attentions (arXiv 2505.16333, NeurIPS 2025)](https://arxiv.org/pdf/2505.16333)
- DEX was tested on Qwen2.5-0.5B and 1.5B, Llama-3.2-1B and 3B, and Llama-3.1-8B. It trains W_K, W_V, W_O, a new W_D and λ while keeping the FFN frozen. Training is one epoch over an 887M-token corpus at 32k context with LR 1e-4. The paper reports "notable gains with as little as 400M tokens" but gives no GPU-hours. — [arXiv 2505.16333](https://arxiv.org/pdf/2505.16333)
- DEX results on the 11-benchmark average: Qwen-0.5B 51.8→54.4 (+2.6), Qwen-1.5B 62.2→62.4 (+0.2), Llama-1B 54.5→55.6, Llama-3B 60.2→64.2. Multi-needle retrieval on Llama-3B rose from 66.9%→78.3%, and attention mass on answer spans from 0.06→0.19. Removing head selection and λ scheduling cut the gain (64.2→62.4). — [arXiv 2505.16333](https://arxiv.org/pdf/2505.16333)
- **Gated attention** adds a head-specific sigmoid gate after SDPA (position G1, the best of more than 30 variants). It was tested on 1.7B dense and 15B-A2.5B MoE models trained from scratch on 400B–3.5T tokens. Average PPL fell 6.026→5.761 and MMLU rose 58.79→60.82. Mean first-token attention (the attention sink) fell from 46.7% to 4.8%, and RULER at 128k rose from 31.65 to 58.82. The paper does **not** study retrofitting. — [Gated Attention for LLMs (arXiv 2505.06708)](https://arxiv.org/abs/2505.06708); press coverage links the design to Qwen3-Next — [lilting.ch](https://lilting.ch/en/articles/qwen3-next-gated-attention-sink)
- **Scalable-Softmax (SSMax)** multiplies the query by s·log n to counter "attention fading" as context grows. Switching an already-pretrained model to SSMax gave only partial improvement on needle-in-a-haystack, far below a model trained with SSMax from the start. — [Liner review of arXiv 2501.19399](https://liner.com/review/scalablesoftmax-is-superior-for-attention) (secondary AI-generated summary; model sizes not given there)
- modded-nanoGPT added a "sparse attention gate" (record #28, 2.817→2.812 min) and later gates on value embeddings and skips. These are small from-scratch gains at 124M. — [modded-nanogpt README](https://github.com/KellerJordan/modded-nanogpt)

### Inferences
- A cheap DEX-style replication on Qwen2.5-0.5B is feasible. Inference: about 400M tokens at 0.5B with frozen FFN is roughly 6·0.5e9·0.4e9 ≈ 1.2e18 FLOPs. That is about 3–5 A100-hours at realistic MFU, or about $8–13, at 32k context. Using 2–4k context would be cheaper. This is the most evidence-backed attention retrofit at the target scale.
- Gated attention can be retrofitted mechanically: initialise the gate bias so sigmoid ≈ 1 (identity), then fine-tune the gate params plus LoRA. There is no published evidence on whether this helps a pretrained 0.5B model, so treat it as an exploratory experiment.
- Retrofit attention gains show up mostly on retrieval, needle and ICL metrics. They are unlikely to fix "does not issue the next tool call", which is a policy failure better addressed by data or RL (Q2–Q3). Run attention retrofits only if the probes in Q4 show the model failing to attend to the bridge entity in its tool output.
- LFM2.5-350M is a hybrid (convolution plus attention) model, so head-level retrofits apply only to its attention layers. Qwen2.5-0.5B is the cleaner testbed.

### Gaps
- No GPU-hour figures were found for DEX, and no public retrofit results for gated attention or attention-temperature changes at 0.5B.
- No study found that measures attention-retrofit effects on agentic or tool-use benchmarks.

## Q2. Small-scale multi-hop and compositional generalization: what helps

### Takeaway
Implicit (no-CoT) multi-hop composition is hard for small vanilla transformers. It needs grokking-length training, data that grows exponentially with hop count, and depth that grows linearly with hops, and out-of-distribution composition fails without weight sharing or recurrence. Explicit intermediate steps (scratchpads, which are what tool calls are) and looped or recurrent depth are the levers that work. A 2026 retrofit put recurrence into Qwen2.5-0.5B-Instruct itself, and LoRA rank 16 nearly matched the full-block version.

### Cited Findings
- **Grokked Transformers** (8-layer, 768-dim GPT-2-style model trained from scratch): two-hop composition generalizes in-distribution only after grokking, about 50× the steps needed to fit the training data. **OOD composition never emerged, even after 2M steps.** The reason is that the generalizing circuit stores a second copy of the atomic facts in upper layers, but only for facts seen as a second hop. Grokking speed tracks the inferred-to-atomic ratio ϕ, not data size. Sharing parameters between the first 4 and last 4 layers enabled OOD composition, slowly. Comparison tasks did generalize OOD. — [arXiv 2405.15071](https://arxiv.org/pdf/2405.15071)
- On a hard reasoning task, the fully grokked small transformer scored 99.3%, against 33.3% (GPT-4-Turbo with retrieval) and 37.3% (Gemini-1.5-Pro with retrieval). — [arXiv 2405.15071](https://arxiv.org/pdf/2405.15071)
- **Implicit k-hop reasoning** (k = 2–4): the training data needed grows exponentially with k and the layers needed grow linearly with k. Curriculum learning reduces the data requirement but does not remove it. — [EMNLP 2025, "Language models can learn implicit multi-hop reasoning, but only if they have lots of training data" (arXiv 2505.17923)](https://preview.aclanthology.org/setup/2025.emnlp-main.490)
- **Hopping Too Late** (LLaMA 2/3 and Pythia, 7B–70B): the bridge entity is resolved at the last token of the first hop, and failures correlate with resolving it too late, leaving too few layers for the second hop. Back-patching a later hidden state into an earlier layer fixed up to 66% of failures. — [arXiv 2406.12775](https://arxiv.org/pdf/2406.12775)
- **Loop, Think, & Generalize** (2026, trained from scratch): vanilla transformers fail both systematic generalization and depth extrapolation (train on ≤5 hops, test on 10). Recurrent-depth transformers succeed, with more inference-time loops giving deeper reasoning, after a three-stage grokking process (memorize → ID → systematic). Too many loops cause "overthinking". — [arXiv 2604.07822](https://arxiv.org/abs/2604.07822)
- **Retrofitting recurrent depth into Qwen2.5-0.5B-Instruct** (2026): layers 0–5 form a prelude, layers 6–17 a weight-tied recurrent block and layers 18–23 a coda, with a gated bridge. On a synthetic multi-step rule task (depths 1–14) the results were:

  | Model | Accuracy |
  |---|---|
  | Full-block recurrence (about 181M trainable) | 84.0% |
  | LoRA r16 adapter (about 6M trainable) | 83.8% |
  | Serialized scratchpad, same size | 72.1% |
  | Direct-answer dense, same size | 27.7% |
  | Direct-answer 1.5B | 36.6% |

  Beyond depth 10, recurrence kept 53.1% against 2.5% for the scratchpad. ARC-E/C was retained at loop 1. Zero-shot transfer to new surface forms was minimal, a learned depth selector failed, and learning a second operation caused interference. The paper reports no GPU-hours. — [arXiv 2608.11233](https://www.alphaxiv.org/abs/2608.11233.md)
- **Looped LMs improve compositional tool calling** (2026): native and retrofitted looped LMs under matched SFT, tested on API-Bank, BFCL and NESTful. Recurrence "generally benefits compositional and dependency-aware tool use", and multi-step accuracy rises with depth. Gains on isolated calls are smaller. The abstract gives no numbers. — [arXiv 2608.18171](https://arxiv.org/abs/2608.18171)
- Related retrofit work: "Teaching Pretrained Language Models to Think Deeper with Retrofitted Recurrence" — [arXiv 2511.07384](https://arxiv.org/pdf/2511.07384) (not read in detail). Huginn, a 3.5B recurrent-depth model trained from scratch — [arXiv 2502.05171](https://arxiv.org/abs/2502.05171) (prior knowledge, not re-fetched).

### Inferences
- The user's agent does not need *implicit* composition. Each hop is externalised as a tool call, which is the scratchpad regime that works. The failure (finds the town but never looks up its population) is a **planning/policy failure: it stops after one hop**, not an inability to compose in the weights. The cheapest fix is training data and rewards that require hop *k+1* to be issued after observing hop *k*, rather than architecture.
- Diverse task shapes: the Grokked result (OOD composition fails without sharing) and the recurrence result (minimal zero-shot surface transfer) both say held-out composition does **not** come free from in-distribution data. Build the eval with *held-out chain templates* (for example, train person→town→population and test company→HQ city→mayor) and *held-out hop counts* (train on 2–3, test on 4).
- A low-cost look at the looped idea: the 0.5B LoRA-r16 recurrence retrofit trained 6M params. Inference: on synthetic data at short context, a few thousand steps fits in about 2–6 L4-hours. It is still the riskiest experiment, since the paper shows weak transfer to natural surfaces.
- Experiments on a toy (about 50–100M from scratch) grokking setup take minutes to a few hours on one GPU. They are useful for intuition but are not what moves the 350M agent.

### Gaps
- The full-text numbers of arXiv 2608.18171 (looped tool calling) were not retrieved. "Why Knowing Both Hops Is Not Enough" ([arXiv 2608.07261](https://arxiv.org/pdf/2608.07261)) has the right title but its PDF could not be parsed.
- No direct study was found of "training on many diverse agentic task shapes → held-out multi-hop tool chains" at ≤500M.

## Q3. RL with verifiable rewards (GRPO etc.) for tool use at ≤1B

### Takeaway
GRPO with fine-grained, decomposed rewards reliably improves single-turn function calling at 1.5B–3B (BFCL +27 points at 1.5B with ToolRL). It runs on a single T4 with LoRA. For **multi-turn search agents at 0.5B**, pure RL from a near-zero start is unstable: GRPO collapsed in Search-R1-style training. An SFT or distillation warm start (SFT→PPO, KD, or DGPO) is needed first.

### Cited Findings
- **ToolRL** (Qwen2.5-1.5B/3B/7B, Llama-3.2-3B): about 4K RL examples (ToolACE 2K, Hammer 1K, xLAM 1K), GRPO in veRL with batch 512, 4 rollouts each, 15 epochs, temperature 1.0 and no KL. Results:

  | Model / benchmark | Raw | SFT400 | SFT4k | GRPO cold start |
  |---|---|---|---|---|
  | Qwen2.5-1.5B, BFCL | 19.41% | 40.21% | 40.67% | 46.20% |
  | Qwen2.5-1.5B, API-Bank | 30.65% | — | — | 63.15% |

  The reward is format (0/1) plus correctness in [-3, 3], decomposed into tool name, parameter names and parameter values. Fine-grained rewards were more stable, length rewards hurt, and a dynamic reward scale helped. GRPO on top of SFT400 moved BFCL only slightly (40.21→40.93) but API-Bank more (53.60→61.31). — [arXiv 2504.13958](https://arxiv.org/html/2504.13958v1)
- **SLM tool use via GRPO on a single T4**: Qwen2.5-1.5B, LoRA r64, 8 generations per prompt, LR 5e-6, 500 steps on 4K xLAM samples. JSON validity rose 73%→100% and accuracy 3.4%→26.6%. The 3B model went 6.1%→71.1%. The reward is valid JSON 0.125, function names 0.375, arguments 0.5, scaled down for extra calls. No wall-clock time is reported, and the paper's stated multipliers don't match its raw numbers. — [arXiv 2509.04518](https://arxiv.org/html/2509.04518v2)
- **DGPO / compact search agents (Qwen2.5-0.5B)**: the base 0.5B scores about 0 EM on NQ, HotpotQA, 2Wiki, MuSiQue and Bamboogle. Search-R1 PPO reaches an average of 0.238, SFT→PPO 0.289, KD 0.298, DGPO 0.329 (teacher 3B: 0.353). **Search-R1 GRPO collapsed early at 0.5B** and DGPO without a KD init collapsed around step 800. Hardware was 8×H200 for about 1 day per run. — [arXiv 2508.20324](https://arxiv.org/pdf/2508.20324)
- A Qwen2.5-0.5B DGPO checkpoint is public — [omron-sinicx/DGPO-qwen2.5-0.5b](https://featherless.ai/models/omron-sinicx/DGPO-qwen2.5-0.5b)
- Related: R-Search (multi-reward RL with search) — [arXiv 2506.04185](https://arxiv.org/pdf/2506.04185). AgenticQwen (small agentic models, data flywheels) — [ACL 2026 industry](https://preview.aclanthology.org/ingest-acl/2026.acl-industry.37/) (not read in detail).

### Inferences
- **Recommended recipe for the budget:**
  1. SFT or distillation on successful multi-hop traces generated by a larger teacher. Inference: 0.5B full SFT on about 5–20M tokens takes about 1 A100-hour, or $2–3.
  2. GRPO with LoRA on a *verifiable synthetic multi-hop environment*. Use a mocked search, link-follow and calculator over a fixed knowledge graph, so rollouts need no network and rewards are exact.
- **Rewards:** decomposed rewards per ToolRL, e.g. a valid call format, each required hop issued (partial credit per hop), and a correct final answer. Add a penalty for answering before the required lookups, which directly targets "guesses instead of looking up". Avoid length rewards.
- **Cost estimate (Inference):** at 0.5B with vLLM rollouts, 8 generations per prompt and multi-turn episodes of about 1–2k tokens, 300–800 GRPO steps fit in roughly 4–10 A100-hours, about $10–25. An L4 (24GB) is possible with LoRA, but vLLM colocation and multi-turn rollouts will be slow. A100 is probably better value per useful step. These are estimates; none of the papers report single-GPU wall-clock time.
- Don't start GRPO from the raw 350M/0.5B model on the 4% tool-use baseline. The DGPO evidence says it will collapse.

### Gaps
- No published single-GPU wall-clock numbers for multi-turn agentic GRPO at 0.35–0.5B were found.
- No published RL results for LFM2.5-350M or Qwen3.5-0.8B tool use were found.

## Q4. Cheap probes: attention entropy, retrieval heads, logit lens, MLP ablation

### Takeaway
All of these probes run in minutes to about 1 GPU-hour at 350M–500M on an L4. The published retrieval-head work covers only models of 6B and up, so testing whether retrieval-head structure exists at 0.5B is itself novel and cheap. The most diagnostic probe for this task: at the step after the first tool result, does attention from the decision token land on the bridge entity, and does the logit lens show the next tool name forming?

### Cited Findings
- **Retrieval heads**: a head's retrieval score is the fraction of needle tokens it copy-pastes, where its top-attended token equals the generated token. It is averaged over about 600 needle tests (1K–50K context, 10 depths), with a threshold of 0.1. About 3–6% of heads qualify. Masking about 50 top heads (about 5% of heads) drops needle performance below 50 and hurts CoT on MuSiQue and GSM8K, while random heads have little effect. Models tested were 6B–34B only; compute is not reported. Code is available. — [arXiv 2404.15574](https://arxiv.org/html/2404.15574v1); [github.com/nightdessert/retrieval_head](https://github.com/nightdessert/retrieval_head)
- **LOCOS** (logit-contribution scoring) projects each head's OV output onto the answer-token unembedding, one forward pass per trial. Ablating 50 LOCOS heads in Qwen3-8B dropped MuSiQue 0.55→0.08 and BABILong 0.62→0.20, with parametric recall and arithmetic staying near baseline. Models were 8B–32B on 2×H100. — [arXiv 2607.01002](https://huggingface.co/papers/2607.01002.md)
- **Hopping Too Late** uses Patchscopes to decode the bridge entity layer by layer, plus back-patching. This is a ready protocol for asking "did the model represent the town but fail to act on it?" — [arXiv 2406.12775](https://arxiv.org/pdf/2406.12775)
- Tooling: TransformerLens skill and docs pages — [tessl registry](https://tessl.io/registry/skills/github/Orchestra-Research/AI-Research-SKILLs/transformer-lens-interpretability). Background papers (prior knowledge, not re-fetched):
  - nnsight / NDIF — [arXiv 2407.14561](https://arxiv.org/abs/2407.14561)
  - MLPs as key-value memories (Geva et al.) — [arXiv 2012.14913](https://arxiv.org/abs/2012.14913)
  - ROME, which locates factual recall in mid-layer MLPs — [arXiv 2202.05262](https://arxiv.org/abs/2202.05262)

### Inferences
- **Time and cost (Inference):** a 0.5B model in bf16 is about 1GB, so all heads' attention maps for a few hundred 2–4k-token prompts fit easily on an L4.

  | Probe | Estimated time |
  |---|---|
  | Attention entropy per head | 10–30 min |
  | Logit lens over all layers | Minutes |
  | Retrieval-head scoring, ~600 needle trials at ≤8k context | ~1 L4-hour |
  | Ablating each of 24 MLP layers (zero/mean) × ~1k eval items | 24 eval passes, 1–2 L4-hours |

  The whole probe suite costs about $2–5. TransformerLens supports Qwen2; LFM2.5 (a hybrid convolution model) will likely need nnsight or plain PyTorch forward hooks.
- **Knowledge-vs-skill test for MLP shrinking:** ablate or shrink MLPs (or prune neurons) and compare (a) closed-book factual QA against (b) tool-use success when the facts are supplied in context. If (b) is robust while (a) collapses, the harness-supplied-context thesis is supported, and MLP width can be traded away for an agent that always looks things up. Record #30 in modded-nanoGPT ("dropped first MLP layer") shows that some MLP capacity is removable even at 124M.
- Use attention entropy before and after SFT/RL as a cheap metric of whether training "focused" attention on tool outputs.

### Gaps
- No reported runtimes were found for these probes at 350M–500M. The estimates above are mine.
- No study was found that applies retrieval-head detection to models under 1B.

## Q5. Speedrun and small-model community lessons (modded-nanoGPT, 124M)

### Takeaway
At 124M, the biggest from-scratch gains came from:
- the Muon optimizer (31.4→24.9 min)
- the bundle of ReLU², QK-norm, zero-init projections and padded embeddings (22.3→15.2)
- value embeddings, skip connections and logit softcap (10.8→8.2)
- U-net skips (7.8→7.2)
- long-context FlexAttention with sliding and block windows (7.2→5.03), then window warmup

Later records (2025–2026) add gating, multi-token prediction, hashed n-gram embeddings and many systems tricks. Most are pretraining-only and can't be retrofitted cheaply.

### Cited Findings
- Target: ≤3.28 val loss on FineWeb on 8×H100. The time fell from 45 min (llm.c baseline, 05/2024) to 0.665 min (#92, 08/30/2026). — [modded-nanogpt README](https://github.com/KellerJordan/modded-nanogpt)
- Key architecture and optimizer records — [modded-nanogpt](https://github.com/KellerJordan/modded-nanogpt):

  | # | Change | Time |
  |---|---|---|
  | 2 | Rotary embeddings plus LR tuning | 45 → 31.4 min |
  | 3 | Muon | → 24.9 min |
  | 5 | ReLU², QK-norm, zero-init projections, padded embeddings | → 15.2 min |
  | 8 | Untied embedding and head | → 10.8 min |
  | 9 | Value and embedding skip connections, momentum warmup, logit softcap | → 8.2 min |
  | 11 | U-net skips | → 7.2 min |
  | 12 | 64K-ctx FlexAttention (sliding window) | → 5.03 min |
  | 13 | Attention window warmup | → 4.66 min |
  | 14 | Value embeddings | → 4.41 min |
  | 16 | Block sliding window | → 3.80 min |
  | 18 | Logit softcap 30→15 | → 3.4 min |
  | 20 | Attention scale and long-short attention | → 2.992 min |
  | 28 | Sparse attention gate | → 2.812 min |
  | 30 | Dropped first MLP layer | → 2.717 min |
  | 35 | Dropped first attention layer | → 2.527 min |
  | 53 | Multi-token prediction | → 1.988 min |
  | 55 | Gates on value embeddings and skips | → 1.918 min |
  | 58 | Paired-head attention | → 1.820 min |
  | 62 | Bigram hash embedding | → 1.655 min |
  | 81 / 85 | MUDD skip connections and dynamically composable MHA | 1.363 / 1.271 min |
  | 90 | QK dim 128→96 | → 1.13 min |
  | 92 | Sampled softmax, 84.6M-row hashed n-gram table, ANVIL optimizer, depth reduction | → 0.665 min |

### Inferences
- Lessons relevant to "focus":
  - Attention-locality tricks (sliding and short windows on most layers, long attention on a few) and attention scale and softcap tuning repeatedly paid off at small scale.
  - Gating (sparse attention gate, value-embedding and skip gates) gave modest but real gains, consistent with the Gated Attention paper's results at larger scale.
  - Dropping the first MLP or attention layer helped speed, which suggests early-layer capacity is partly redundant at 124M.
- Most of these are from-scratch pretraining changes. A 124M speedrun-style run costs about 8×H100×~2–3 min ≈ 0.3–0.4 H100-hours for 3.28 loss. Inference: that is roughly 1–2 A100-hours on 1 GPU, so about $3–5 per ablation. This makes the speedrun repo a cheap sandbox for testing an attention or MLP idea from scratch at 124M before trying a retrofit at 350M–500M.
- The large hashed n-gram and bigram embedding gains (#62, #92) echo the "move memorized knowledge out of the MLP into lookup tables" idea. That is conceptually aligned with "harness-supplied context instead of parametric knowledge", but it is pretraining-only.

### Gaps
- The README gives no per-record isolated ablations (several changes per record), so attributing gains to single tricks is approximate.
- No evidence was found on which speedrun tricks transfer when added to an already-pretrained 350M–500M model.
