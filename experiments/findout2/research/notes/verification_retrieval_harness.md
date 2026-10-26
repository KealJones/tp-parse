# Verification: retrieval-augmented small models and model–harness co-design

Status key: CONFIRMED / CORRECTED (old -> correct) / NOT FOUND. All checks were made against the full text (arXiv HTML/PDF) or the official blog or model card, as noted.

## 1. Retrieval-augmented LMs (Toolformer, Atlas, REALM, RETRO, RA-DIT)

### Takeaway
Most of the classic figures hold. Two corrections: Toolformer's base model is GPT-J 6.7B, and Atlas's 3% margin over PaLM-540B on NQ is 42.4 vs 39.6. The other classic claims check out, but REALM, Atlas and RETRO all report parameter efficiency on knowledge-heavy QA and language modelling, not on general capability.

### Cited Findings
- **Toolformer base model: CONFIRMED / clarified.** It is built on "a pretrained GPT-J model ... with 6.7B parameters" (Introduction). — [Toolformer HTML](https://arxiv.org/html/2302.04761v1)
- **Toolformer emergence at 775M: CONFIRMED.** Sec. 4.4 (Scaling Laws) tests GPT-2 models of "124M, 355M, 775M and 1.6B parameters" plus GPT-J. The paper says "the ability to leverage the provided tools only emerges at around 775M parameters". — [Toolformer PDF](https://arxiv.org/pdf/2302.04761)
- **Atlas 11B, NQ 64-shot: CONFIRMED.** Atlas-11B scores 42.4 EM against PaLM 540B's 39.6 (Table 8). The abstract says Atlas reaches "over 42% accuracy on Natural Questions using only 64 examples, outperforming a 540B parameters model by 3% despite having 50x fewer parameters". — [Atlas PDF](https://arxiv.org/pdf/2208.03299)
- **Atlas MMLU by size: CONFIRMED.** In Table 5 (5-shot), Atlas-770M scores 38.9 and Atlas-11B scores 43.4, against 36.1 for closed-book T5-11B. Other settings for Atlas-11B: 5-shot multi-task 56.4 and full/transfer 65.8. Atlas-770M scores 56.3 on full/transfer. The closed-book T5-11B equivalents are 43.5 and 54.0. The model family also includes a 3B size. Some 770M cells were not legible in the extraction. — [Atlas PDF](https://arxiv.org/pdf/2208.03299)
- **REALM size and comparison with T5-11B: CONFIRMED (330M).** Table 1 (Open-QA test) lists REALM at 330m parameters:
  - REALM (X=CC-News): NQ 40.4, WQ 40.7, CuratedTREC 42.9
  - REALM (X=Wikipedia): NQ 39.2, WQ 40.2, CuratedTREC 46.8
  - T5-11B closed-book (11,318m): NQ 34.5, WQ 37.4, no CuratedTREC result

  REALM therefore beats T5-11B on NQ by about 6 points and on WQ by about 3 points, with roughly 34x fewer parameters. — [REALM PDF](https://arxiv.org/pdf/2002.08909)
- **RETRO: CONFIRMED.** The abstract says RETRO "obtains comparable performance to GPT-3 and Jurassic-1 on the Pile, despite using 25× fewer parameters" with "a 2 trillion token database". Models were trained at 172M, 425M, 1.5B and 7.5B (Table 2 gives 7,532M for the largest). The paper also says "Retro 7.5B outperforms Jurassic-1 and Gopher on a majority of the test sets" and "Retro provides a constant gain for models ranging from 150M to 7B parameters." — [RETRO abstract](https://arxiv.org/abs/2112.04426); [RETRO PDF](https://arxiv.org/pdf/2112.04426)
- **NVIDIA "Shall We Pretrain Autoregressive LMs with Retrieval?": CONFIRMED.** The abstract says "RETRO largely outperforms GPT on knowledge-intensive tasks, but is on par with GPT on other tasks". It adds that RETRO outperforms GPT on text generation "with much less degeneration (i.e., repetition)". It also introduces RETRO++, which improves open-domain QA ("EM score +8.6 on Natural Question"). — [arXiv 2304.06762](https://arxiv.org/abs/2304.06762)
- **RA-DIT: CONFIRMED.** The abstract reports gains of "up to +8.9% in 0-shot setting and +1.4% in 5-shot setting on average" over in-context RALM approaches. The best model is RA-DIT 65B. Note that these are "up to" and "on average" figures for a 65B model, not for a small one. — [RA-DIT abstract](https://arxiv.org/abs/2310.01352)

### Inferences
- The "retrieval lets a small model beat a big one" evidence (REALM 330M vs T5-11B, Atlas 11B vs PaLM, RETRO 7.5B vs Jurassic-1 178B) comes from open-domain QA and LM perplexity. These models were pretrained or jointly trained with retrieval. None of them bolts retrieval onto an off-the-shelf small instruct model.

### Gaps
- Atlas-770M multi-task MMLU and closed-book T5-770M MMLU cells were not legible in the PDF extraction.

## 2. Small models using retrieved context (arXiv 2603.11513, Search-R1, DGPO, compressed or parametric memory)

### Takeaway
The March 2026 study holds: retrieval did not help models of 7B and below, and the main failure is ignoring the passage. One correction: the −11.0/−7.5/−2.5 figures come from an n=200 pilot, and 360M was also hurt (−1.5). Search-R1's 0.431 is the 7B base model, while the 3B figure of 0.325 is the instruct model. DGPO brings a 0.5B search agent to 0.329 average EM, against 0.353 for its 3B teacher.

### Cited Findings
- **arXiv 2603.11513: CONFIRMED with clarifications.**
  - Title: "Can Small Language Models Use What They Retrieve? An Empirical Study of Retrieval Utilization Across Model Scale." Single author: Sanchit Pandey (BITS Pilani, Hyderabad).
  - Models: SmolLM2-360M-Instruct (the smallest, so **360M is CONFIRMED**), Qwen2.5-1.5B, 3B and 7B (all 4-bit NF4), and Llama-3.1-8B (FP16 via Groq API, which the author says is not directly comparable).
  - Retrieval effect (dense minus no retrieval, EM) comes from the **pilot study (n=200)**: 360M −1.5 pp, 1.5B −11.0, 3B −7.5, 7B −2.5. "Hurt at every size" therefore holds for 360M to 7B.
  - Gold-passage (oracle) EM on the Unknown split (n=756): 360M 0.0%, 1.5B 10.0%, 3B 12.8%, 7B 14.6%. **Range 0–14.6% CONFIRMED.** On the Known split, oracle EM runs from 0.0% (360M, n=11) to 58.4% (7B). The paper says models "fail to extract the correct answer 85–100% of the time on questions they cannot answer alone."
  - "Irrelevant generation" (ignoring the context) as a share of oracle failures: 360M 100%, 1.5B 64%, 3B 73%, 7B 61%. **61–100% CONFIRMED.**

  — [arXiv 2603.11513 HTML](https://arxiv.org/html/2603.11513)
- **Search-R1 (v5, Aug 2025): CONFIRMED with a variant caveat.** Table 2 average EM:
  - Qwen2.5-7B-base: Search-R1 0.431 vs RAG 0.304
  - Qwen2.5-7B-instruct: Search-R1 0.385
  - Qwen2.5-3B-instruct: Search-R1 0.325 vs RAG 0.270
  - Qwen2.5-3B-base: Search-R1 0.303

  The retrieved-token loss-masking ablation (Table 4, 7B-base, PPO) gives 0.431 with masking and 0.343 without (**CONFIRMED**). The abstract claims +24% (7B) and +20% (3B) over RAG baselines, while the contributions list says 41% and 20%. These do not fully reconcile with the table. — [Search-R1 HTML](https://arxiv.org/html/2503.09516)
- **DGPO (arXiv 2508.20324): FILLED.**
  - Title: "Can Compact Language Models Search Like Agents? Distillation-Guided Policy Optimization for Preserving Agentic RAG Capabilities." Authors: Kotoge (U. Osaka), Nishimura and Ma (OMRON SINIC X).
  - Qwen2.5-0.5B student, average EM over NQ, TriviaQA, PopQA, HotpotQA, 2Wiki, MuSiQue and Bamboogle (Table 2): untrained 0.006, PPO (Search-R1 recipe) 0.238, SFT→PPO 0.289, KD 0.298, **DGPO 0.329**, 3B teacher 0.353.
  - DGPO beats the 3B teacher on NQ (0.378 vs 0.365), PopQA (0.402 vs 0.393) and HotpotQA (0.342 vs 0.340).
  - GRPO was excluded because it "proved unstable for compact models, collapsing early."
  - Other settings: with a 7B teacher, the 0.5B student reaches DGPO 0.323 (teacher 0.385). Llama 1B with an 8B teacher reaches DGPO 0.389 (teacher 0.438, PPO 0.250).

  — [DGPO HTML](https://arxiv.org/html/2508.20324)
- **xRAG: CONFIRMED.** HotpotQA EM for Mistral-7B: no retrieval 27.02, RAG 38.79, xRAG 34.05. Mixtral-8x7B scores 32.87 / 43.46 / 39.66. The abstract says FLOPs are reduced "by a factor of 3.53" (Table 2, Mistral-7B). The paper concedes that on reasoning tasks like HotpotQA "xRAG lags behind by a considerable gap." — [xRAG HTML](https://arxiv.org/html/2405.13792)
- **Memory Decoder: CONFIRMED.**
  - Title: "Memory Decoder: A Pretrained, Plug-and-Play Memory for Large Language Models." Authors: Cao, Wang, Wei, Guo, Chen, Zhou, Lin.
  - Table 3 average perplexity over Bio/Fin/Law: Qwen2-0.5B 14.88, +LoRA 7.60, **+MemDec 4.05**. Qwen2.5-0.5B: 14.30 / 7.55 / 4.06.
  - The memory decoder itself has 0.5B parameters; a "single Memory Decoder (0.5B parameters)" is shared across Qwen models from 0.5B to 72B.

  — [Memory Decoder HTML](https://arxiv.org/html/2508.09874)
- **KBLaM: CONFIRMED as ICLR 2025** (ICLR proceedings and virtual poster page). The abstract describes integrating "more than 10K triples into an 8B pre-trained LLM" on one A100 80GB, with "computational overhead [that] scales linearly with KB size rather than quadratically". The abstract evaluates no model under 1B. — [arXiv 2410.10450](https://arxiv.org/abs/2410.10450); [ICLR 2025 proceedings](https://proceedings.iclr.cc/paper_files/paper/2025/hash/803485352e61e3ebf41221e4776c9fd4-Abstract-Conference.html); [ICLR poster](https://iclr.cc/virtual/2025/poster/29174)
- **Cartridges: CONFIRMED for 38.6x / 26.4x; Llama 4 Scout comparison FILLED; training cost NOT FOUND.**
  - The abstract says cartridges "match ICL performance while using 38.6× less memory and enabling 26.4× higher throughput" (averaged across benchmarks).
  - Blog: on MTOB, Llama-3.1-8B + cartridge reaches 36.1 chrF with a 0.54 GB cache, against 36.3 for Llama 4 Scout (109B) with the full 400k-token textbook in context.
  - Blog: on LongHealth, a 0.96 GB cartridge scores 55.1%, beating full ICL, with a 13.8x cache reduction. A 52 MB cartridge scores 47.7%, with a claimed 256x compression and 121x throughput gain.
  - Neither the paper nor the blog gives GPU-hours or dollar cost. The smallest model used is Llama-3B (throughput measurements only).

  — [Cartridges HTML](https://arxiv.org/html/2506.06266); [Hazy Research blog](https://hazyresearch.stanford.edu/blog/2025-06-08-cartridges)

### Inferences
- The strongest sub-1B knowledge-injection result found is Memory Decoder on Qwen2-0.5B and Qwen2.5-0.5B. It cuts domain perplexity about 3.7x and beats LoRA, but it reports perplexity, not QA accuracy, and the add-on memory is itself as large as the base model. KBLaM, Cartridges and xRAG were not tested below 3B to 8B.
- Taken together, 2603.11513 and DGPO suggest that small models can use retrieved text if they are trained to do so (RL or distillation), but not zero-shot.

### Gaps
- No cartridge, KBLaM or xRAG evaluation on a sub-1B model was found.
- No cartridge training cost was found in the paper or blog.

## 3. Tool and agent results for small models (TinyAgent, ToolRL, 2509.04518, MobileLLM, sub-1B agents) and Allen-Zhu & Li Part 3.3

### Takeaway
All TinyAgent, ToolRL, 2509.04518 and MobileLLM numbers are confirmed. Sub-1B tool-use results do exist:
- STAR-0.6B (Feb 2026): BFCLv3 51.70 (base 47.33), with plain SFT hurting.
- DGPO-0.5B (search agent).
- Memory Decoder-0.5B (knowledge, from section 2).
- MobileLLM-350M (API calling).

xLAM-2-1b-fc-r reaches BFCL v3 58.90, but it is 1B, not sub-1B.

### Cited Findings
- **TinyAgent: CONFIRMED.**
  - TinyLlama-1.1B success rate rises from 12.71% to 78.89% after fine-tuning. Wizard-2-7B rises from 41.25% to 83.09%.
  - With the learned ToolRAG retriever (fine-tuned DeBERTa-v3-small, 0.998 tool recall, 1,397 prompt tokens), the 1.1B model scores **80.06%** and the 7B scores 84.95%. **GPT-4-Turbo scores 79.08%.**
  - Basic (off-the-shelf) RAG gives 74.88% for 1.1B and 78.50% for 7B. Table 1 says top-3 tools at 0.949 recall, but the text says top-6 at 0.968, so the blog contradicts itself.
  - 4-bit quantization (Table 2): the 1.1B model is **0.68 GB**, 2.9 s latency and 80.35% success (16-bit: 2.2 GB, 3.9 s, 80.06%). The 7B is 4.37 GB, 13.1 s and 85.14%.
  - Data: 80K training, 1K validation and 1K test examples, at "a total cost of only ~$500".

  — [BAIR blog](https://bair.berkeley.edu/blog/2024/05/29/tiny-agent/)
- **ToolRL (2504.13958): CONFIRMED.** BFCL V3 overall for Qwen2.5-1.5B-Instruct: raw 19.41%, SFT400 40.21%, SFT4k 40.67%, **GRPO cold start 46.20%**. For Llama-3.2-3B: raw 22.09%, SFT4k 44.16%, GRPO 44.10% (essentially tied with SFT). The RL set has 4K examples (2K ToolACE, 1K Hammer-masked, 1K xLAM). No 0.5B result. — [ToolRL HTML](https://arxiv.org/html/2504.13958)
- **arXiv 2509.04518: CONFIRMED with caveats.**
  - Title: "Advancing SLM Tool-Use Capability using Reinforcement Learning." Authors: Paprunia, Kharidia, Doshi (NMIMS Mumbai).
  - Hardware is "a T4 GPU" (the paper does not say "single"). Training ran 500 steps on 4,000 xLAM-60K samples and was tested on 1,000. The metric is the paper's own "Overall Accuracy", not BFCL.
  - Results (overall accuracy / JSON validity, base → after GRPO):
    - Qwen2.5-1.5B: 3.40% / 73% → 26.60% / 100%
    - Qwen2.5-3B: 6.10% → 71.1%
    - Llama-3.2-3B: 0.98% → 22.00%
  - Internal inconsistencies: the stated multipliers (e.g. "6.28×") don't match the table, and model names are inconsistent. Treat as low-rigor.

  — [arXiv 2509.04518 HTML](https://arxiv.org/html/2509.04518)
- **MobileLLM-350M API calling: CONFIRMED.** Table 6:

  | Model | EM intent | EM structure | ROUGE-1 | ROUGE-L |
  |---|---|---|---|---|
  | MobileLLM-350M | 65.3 | 48.8 | 46.8 | 44.6 |
  | LLaMA-v2 7B | 62.8 | 50.9 | 56.5 | 54.3 |

  The text claims "comparable intent and structure exact match scores to LLaMA-v2 7B". No 125M API-calling row is reported. — [MobileLLM HTML](https://arxiv.org/html/2402.14905)
- **Allen-Zhu & Li Physics of LMs Part 3.3: CONFIRMED.**
  - Abstract: models "can and only can store 2 bits of knowledge per parameter, even when quantized to int8".
  - Remark 1.1: "a sufficiently trained 7B language model can store 14B bits of knowledge".
  - Result 5 (1000 exposures): "Reducing the MLP size of GPT2 architecture by 1/4 or even eliminating all MLP layers does not affect its capacity ratio."
  - Result 6 (100 exposures): shrinking the MLP by 1/4 has "negligible impact", but "Removing MLPs decreases the capacity ratio by more than 1.5x."
  - Junk data: with a 1:7 useful-to-junk ratio, "capacity for useful knowledge loses by a factor of 20x".
  - GPT-2 with rotary "matches or even surpasses LLaMA/Mistral", which is attributed to GatedMLP being less stable.

  Note the MLP-removal claim depends on the exposure regime. — [arXiv abstract](https://arxiv.org/abs/2404.05405); [PDF](https://arxiv.org/pdf/2404.05405)
- **GAP FILL: STAR (arXiv 2602.03022, Feb 2026)**, "Similarity-guided Teacher-Assisted Refinement for Super-Tiny Function Calling Models".
  - Qwen3-0.6B on BFCLv3 overall: base 47.33, SFT 44.58, **STAR 51.70**. Multi-turn: 1.88 / 1.62 / 7.00.
  - ACEBench Normal summary: base 27.20, SFT 2.10 ("Standard SFT leads to a performance collapse"), **STAR 53.00**.
  - For comparison, Llama3.1-8B scores 49.57 BFCL / 46.60 ACEBench and Qwen3-8B scores 66.34 / 72.90. STAR-0.6B therefore slightly beats Llama3.1-8B on both but trails Qwen3-8B.
  - Recipe: a Qwen3-8B teacher refined with similarity-based GRPO, then constrained KD, then Sim-RL (GRPO) on about 128k examples (ToolACE, xLAM, xLAM-irrelevance, Tool-use-synthetic), using 8x H20.

  — [STAR HTML](https://arxiv.org/html/2602.03022)
- **GAP FILL: xLAM-2-1b-fc-r** (APIGen-MT, arXiv 2504.03601). BFCL v3 overall is 58.90 (rank 36 as of 04/03/2025), and multi-turn is 43.12. The text says this is "substantially outperforming o1 (36%) and gpt-4o in function-calling mode (41%)" on multi-turn. For comparison, xLAM-2-3b scores 65.11, 8b scores 72.83 and 70b scores 78.19. Recipe: filtered behavioural cloning on APIGen-MT trajectories mixed with APIGen function-calling data, with full fine-tuning for at most 3 epochs. The model card lists the 1B as a Qwen-2.5-based model (32k context) trained on APIGen-MT-5k and xlam-function-calling-60k. — [APIGen-MT HTML](https://arxiv.org/html/2504.03601); [HF model card](https://huggingface.co/Salesforce/xLAM-2-1b-fc-r)
- **GAP FILL: Hammer.** Hammer2.1-0.5b is fine-tuned from Qwen2.5-Coder-0.5B-Instruct on xlam-function-calling-60k plus xlam-irrelevance-7.5k with function masking, and it is integrated into Google AI Edge for on-device use. Its BFCL-v3 numbers appear only as an image on the card, so no figures are recorded here. The Hammer paper's smallest model is 1.5B (BFCL 73.04 vs xLAM-1.3B-fc 74.90, on the older BFCL). — [HF card](https://huggingface.co/MadeAgents/Hammer2.1-0.5b); [Hammer HTML](https://arxiv.org/html/2410.04587)
- EGPO (arXiv 2508.05118) has no result below 3B. — [EGPO HTML](https://arxiv.org/html/2508.05118)

### Inferences
- Across ToolRL, STAR and DGPO, RL or distillation beats plain SFT for small tool and search agents. Plain SFT can actively hurt at 0.6B (STAR's ACEBench collapse), and GRPO can be unstable at 0.5B (DGPO). Distillation from a larger teacher is the common ingredient in the sub-1B successes.
- The TinyAgent result is a harness result. A learned tool retriever cuts the prompt from 2,762 to 1,397 tokens and lifts 1.1B success from 78.89% to 80.06%. Naive RAG drops it to 74.88%, so a bad retriever is worse than none.

### Gaps
- No Hammer2.1-0.5B numeric BFCL score (image only) and no Octopus sub-1B model were found; Octopus v2 is Gemma-2B, which was not re-verified.
- xLAM-2-1b-fc-r's exact base model and per-model trajectory count are not stated in the paper text.
- STAR's author list was not retrieved.
