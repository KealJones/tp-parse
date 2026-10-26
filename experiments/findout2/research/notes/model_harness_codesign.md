# Model–Harness Co-Design: Making a Small Model + Harness Beat a Larger Model

Scope note: findings marked **[verified]** were checked against the primary source in this session (paper HTML/PDF or official blog). Findings marked **[abstract, recalled]** are figures from well-known arXiv abstracts that I did not re-fetch this session; the writer should treat their exact numbers as needing a spot-check, though the direction of each claim is well established. Latest work comes first within each section.

---

## Q1. Interfaces between harness and model beyond plain text (KV entries, memory tokens, kNN attention, cross-attention, knowledge-as-attention, plug-in memories, scratchpads)

### Takeaway
There are working, measured interfaces that inject harness knowledge below the text level. They include trained KV caches (Cartridges), knowledge tokens read through "rectangular attention" (KBLaM), one-token retrieval embeddings (xRAG), a small parametric memory model blended at the output distribution (Memory Decoder), and kNN/cross-attention memories (Memorizing Transformers, LongMem, RETRO). Each one buys large compute or memory savings, or domain gains, at roughly equal quality on *fact recall*. All of them consistently lose to plain-text RAG on *multi-hop reasoning*. Almost all were shown on 7B–8B+ models, not on sub-500 MB models. Harness-maintained text state (todo-file recitation, files as memory, compaction) is the best-validated practice in production, but the evidence for it is engineering anecdote rather than controlled experiments.

### Cited Findings
**Cartridges (Stanford Hazy Research / Scaling Intelligence, June 2025, ICML 2025)** [verified]
- A "cartridge" is a small KV cache trained offline on one corpus by "self-study": synthetic conversations about the corpus, trained with a context-distillation objective. It matches full in-context (ICL) quality using **38.6× less memory** and gives **26.4× higher peak throughput** when serving many users with different long contexts — [Hazy Research blog](https://hazyresearch.stanford.edu/blog/2025-06-08-cartridges); [arXiv 2506.06266](https://arxiv.org/pdf/2506.06266)
- LongHealth: a 0.96 GB cartridge scores **55.1%**, above the full-ICL baseline, with a 13.8× smaller cache. A 52 MB cartridge (256× compression) scores 47.7%, versus 43.0% for the DuoAttention compression baseline at 6.77 GB — [Hazy Research blog](https://hazyresearch.stanford.edu/blog/2025-06-08-cartridges)
- MTOB (translating Kalamang from a 400k-token textbook): a Llama-3.1-8B cartridge of 0.54 GB scores **36.1 ChRF**, versus 36.3 for Llama 4 Scout (109B) reading the full textbook. This is a small model plus trained memory roughly matching a model ~13× larger — [Hazy Research blog](https://hazyresearch.stanford.edu/blog/2025-06-08-cartridges)
- Limitations the authors state: training is unoptimized and its cost is not quantified. Naive next-token training on the document memorized it but did not generalize, which is why self-study was needed. The post says cartridges "can be combined without retraining" but gives no compositional results — [Hazy Research blog](https://hazyresearch.stanford.edu/blog/2025-06-08-cartridges)

**Memory Decoder (NeurIPS 2025, arXiv 2508.09874)** [verified]
- A small transformer decoder (0.5B for cross-model experiments, 1B for QA) is pretrained to imitate a kNN-LM retriever's output distributions (KL plus LM loss). At inference it runs in parallel with the frozen base LM, and the two outputs are interpolated: α·p_mem + (1−α)·p_LM, with α≈0.6 for language modelling. There is no datastore search at inference and no change to base weights — [arXiv HTML](https://arxiv.org/html/2508.09874v1)
- Qwen2-0.5B average domain perplexity (bio/finance/law): **14.88 → 4.05**, versus 7.60 with LoRA. A 0.5B Memory Decoder paired with Qwen2.5-72B lowers its perplexity from 5.85 to 3.46, and the paper reports it beats vanilla 72B models in all three domains. The average perplexity reduction is 6.17 points — [arXiv HTML](https://arxiv.org/html/2508.09874v1)
- Knowledge QA with Llama3-8B: NQ 23.64 → 28.01 and HotpotQA 25.14 → 27.72, beating kNN-LM (24.00 / 24.48) — [arXiv HTML](https://arxiv.org/html/2508.09874v1)
- Latency on Qwen2.5-1.5B is **1.28×** the base model, versus 1.51× for in-context RAG and 2.17× for kNN-LM — [arXiv HTML](https://arxiv.org/html/2508.09874v1)
- Caveats: it does not win everywhere. DAPT beats it on GPT2-xl perplexity, and it is weaker on Llama legal text. Moving it to a different tokenizer needs retraining of embeddings and head (~10% of budget) — [arXiv HTML](https://arxiv.org/html/2508.09874v1)

**KBLaM (Microsoft Research, ICLR 2025, arXiv 2410.10450)** [verified via MSR blog]
- Each knowledge-base triple (entity, property, value) is encoded by a sentence encoder plus linear adapters into a key–value pair called a "knowledge token". These are injected into every attention layer with **rectangular attention**: prompt tokens attend to knowledge tokens, but knowledge tokens attend neither to each other nor to the prompt. Cost is linear in KB size, the base model is frozen, there is no separate retriever, and single triples can be updated without retraining — [Microsoft Research blog](https://www.microsoft.com/en-us/research/?p=1133691); [arXiv 2410.10450](https://arxiv.org/pdf/2410.10450)
- It handles 10,000+ triples (~200k text tokens) on one GPU with an 8K-context base model. At 4,096 triples, time-to-first-token is lower than RAG with 5 triples. With KBs above ~200 triples, it refuses unanswerable questions more precisely than in-context text does — [Microsoft Research blog](https://www.microsoft.com/en-us/research/?p=1133691)
- Limitations: it was trained mainly on factual QA pairs (much of it synthetic), and complex reasoning is untested. The authors say it is "not yet ready for large-scale deployment" — [Microsoft Research blog](https://www.microsoft.com/en-us/research/?p=1133691)

**xRAG (NeurIPS 2024, arXiv 2405.13792)** [verified]
- The retriever's existing document embedding is projected (by a projector holding only 0.46% of Mistral-7B's parameters) into **one token** in the LM's embedding space. That shrinks a 175-token average document to 1 token, cuts FLOPs **3.53×**, and gives ~1.64× CUDA-time speedup — [arXiv HTML](https://arxiv.org/html/2405.13792v2)
- Mistral-7B, no-retrieval → xRAG: NQ 30.25 → 39.10 EM, TriviaQA 57.08 → 65.77. Average +16.2% over no retrieval. Full-text RAG averages 43.63 versus 42.46 for xRAG — [arXiv HTML](https://arxiv.org/html/2405.13792v2)
- **It loses on multi-hop:** HotpotQA 34.05 versus 38.79 for full-text RAG, and FactKG 63.08 versus 67.76. The authors list reasoning over embeddings and handling multiple documents as open problems — [arXiv HTML](https://arxiv.org/html/2405.13792v2)

**Older memory/attention interfaces** [abstract, recalled]
- RETRO (DeepMind, 2021): chunked cross-attention over neighbours retrieved from a 2-trillion-token database. It is comparable to GPT-3 and Jurassic-1 on the Pile despite **25× fewer parameters** — [arXiv 2112.04426](https://arxiv.org/abs/2112.04426)
- Memorizing Transformers (2022): one layer does kNN attention over a non-differentiable external memory of past (key, value) pairs. Perplexity keeps improving as memory grows up to 262K tokens, and the model can use newly defined functions and theorems at test time — [arXiv 2203.08913](https://arxiv.org/abs/2203.08913)
- LongMem (2023): a frozen backbone LLM caches past-context KV in a memory bank. A trainable residual side-network retrieves from it and fuses the results, extending usable context to 65k tokens and beating long-context baselines on ChapterBreak — [arXiv 2306.07174](https://arxiv.org/abs/2306.07174)
- Gist tokens (2023): the LM learns to compress a prompt into a few "gist" tokens whose KV is cached, giving up to 26× prompt compression with small quality loss — [arXiv 2304.08467](https://arxiv.org/abs/2304.08467)

**Harness-maintained state / structured context (production practice)** [verified]
- Manus: the KV-cache hit rate is "the single most important metric" (cached Sonnet input $0.30/M versus $3/M uncached). Input:output token ratio is about 100:1. Practices: keep prompt prefixes stable and serialize JSON deterministically; **mask tool logits instead of removing tools**; use the file system as restorable external memory; recite a `todo.md` that gets rewritten to keep goals in recent attention across ~50 tool calls; keep errors in context; and vary serialization to avoid few-shot ruts — [Manus blog](https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus)
- Anthropic (Sep 29, 2025): "context rot" (recall degrades as the window fills) and a finite "attention budget". The aim is the smallest set of high-signal tokens. Techniques: just-in-time retrieval through lightweight references, compaction, structured note-taking outside the window, and sub-agents that return condensed summaries of 1–2k tokens — [Anthropic Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)

### Inferences
- For a ≤500 MB browser model, the most transferable interfaces are the cheap ones. These are (a) xRAG/KBLaM-style **projected knowledge tokens** that reuse the harness's retriever embeddings; (b) **precomputed KV for stable harness content** (system prompt, tool schemas, user memory profile) — either a plain prefix cache or a Cartridge-style trained cache; and (c) **logit masking / constrained decoding** driven by the harness. Memory Decoder's 0.5B side model is itself about the whole budget, so a much smaller variant would be needed. That is untested.
- A consistent pattern runs across xRAG, KBLaM and Cartridges: compressed/latent injection holds up for *lookup* but degrades for *composition across documents*. Co-design should therefore route multi-hop questions to full-text context, or to iterative retrieval, rather than to compressed tokens.
- KBLaM's rectangular attention is close to a direct answer to "change how attention interacts with harness info". It is a separate attention path whose keys and values the harness owns, with linear cost and freshness that can be edited per item.
- The Manus/Anthropic practices (recitation, files as memory, masking) are especially relevant to small models, whose long-context recall is weaker, but no source here measures them on small models.

### Gaps
- None of these injection methods has published results on sub-1B models in a browser/WebGPU setting. Memory Decoder's smallest *base* is 0.5B, but its memory module is also 0.5B.
- No controlled study found that compares KV-injection with text injection for *small* models on multi-hop tasks.
- Cartridge training cost and composition across several cartridges were not quantified in the source.
- The KBLaM base model is not named in the blog (I believe it is Llama-3-8B-Instruct, but did not verify).

---

## Q2. Training the model for its harness (joint retriever+LM, learning when to retrieve, RL on the agent loop, learning to ask)

### Takeaway
Training the LM *inside* its harness reliably beats bolting retrieval or tools onto an off-the-shelf model. With RL on the full loop, 3B–8B models gain 10–40% relative over prompted RAG, and on narrow tasks they beat frontier models: Planner-R1-8B/32B versus GPT-5 on TravelPlanner, and SpeakRL-7B versus Claude Sonnet 4 on clarification. The masking and reward-shaping details matter a lot. Gains at 3B are clearly smaller than at 7B, and essentially no published agent-RL results exist for ≤0.5B.

### Cited Findings
**RL on the full agent loop (2025–2026)**
- Search-R1 (2025): PPO/GRPO training on interleaved reasoning and `<search>` calls. Average EM across 7 QA sets, Qwen2.5-7B-Base: **0.431 versus 0.304** for RAG. Qwen2.5-3B: Base 0.303, Instruct 0.325, versus RAG 0.270. The abstract gives +24% (7B) and +20% (3B) relative; the intro says 41% for 7B, which is internally inconsistent [verified] — [arXiv 2503.09516](https://arxiv.org/html/2503.09516v5)
- Search-R1 design detail: **masking retrieved tokens out of the RL loss** matters a lot. 7B-Base scores 0.431 with masking versus 0.343 without. In other words, the model should not be trained to predict the harness's text [verified] — [arXiv 2503.09516](https://arxiv.org/html/2503.09516v5)
- Search-R1: at 3B, the *instruct* model beats the base model; at 7B, base beats instruct. GRPO converges faster but is less stable than PPO [verified] — [arXiv 2503.09516](https://arxiv.org/html/2503.09516v5)
- Planner-R1 (Sep 2025; ACL 2026): GRPO on just **180** TravelPlanner queries. Final pass rate: Planner-R1-32B **56.9%** and 8B 56.4% peak, versus GPT-5 21.2%, o3 11.3%, and base Qwen3-32B 0.6% / 8B 0.0%. The 8B model needed **dense process-level reward shaping**: with sparse rewards it collapsed in 3/5 and 5/5 runs, while 32B was robust. The 8B model reached 90% of the 32B peak with about 3.5× fewer update FLOPs [verified] — [arXiv 2509.25779](https://arxiv.org/html/2509.25779v1)
- ToolRL (2025): a study of reward design for tool-use RL (GRPO). It reports +17% over base and +15% over SFT models [abstract, recalled] — [arXiv 2504.13958](https://arxiv.org/abs/2504.13958)
- ReSearch (2025): RL that treats search as part of the reasoning chain, without supervised reasoning traces, on Qwen2.5-7B/32B. It reports ~8.9–22.4% absolute gains over baselines on multi-hop QA, and reflection/self-correction behaviours emerge [abstract, recalled] — [arXiv 2503.19470](https://arxiv.org/abs/2503.19470)

**Learning to ask the person**
- SpeakRL (Dec 2025): Qwen2.5-7B-Instruct, RL-trained with a format reward plus an LLM-judge reward on clarification-question quality. On MultiWOZ 2.4 task success it scores **46.17%**, versus 25.63% prompted, 28.78% SFT, 45.73% DPO and **44.08% for Claude-Sonnet-4**, in fewer turns (5.82 versus 8.12). Caveats: the judge and user simulator *are* Claude-Sonnet-4, there is no task-success reward, and nothing penalizes over-asking. The abstract's +20.14 does not match the +20.54 computed from its own table [verified] — [arXiv 2512.13159](https://arxiv.org/pdf/2512.13159)
- Other 2025–26 work in this line: "Learning to Clarify by RL through reward-weighted fine-tuning" [arXiv 2506.06964](https://arxiv.org/html/2506.06964v1); "Reasoning While Asking" [arXiv 2601.22139](https://arxiv.org/pdf/2601.22139); "Clarify or Answer" (VQA) [arXiv 2601.16400](https://arxiv.org/pdf/2601.16400). Not read in detail.

**Learning when to retrieve** [abstract, recalled]
- Self-RAG (2023): the LM is trained to emit reflection tokens (retrieve?, is-relevant, is-supported, is-useful), so the harness can retrieve on demand and critique. The 7B/13B models outperform ChatGPT and retrieval-augmented Llama2-chat on open-domain QA, reasoning and fact verification, with better citation accuracy — [arXiv 2310.11511](https://arxiv.org/abs/2310.11511)
- FLARE (2023): active retrieval that triggers retrieval when an upcoming sentence contains low-confidence tokens, using the tentative sentence as the query. It is superior or competitive on 4 long-form knowledge-intensive tasks — [arXiv 2305.06983](https://arxiv.org/abs/2305.06983)

**End-to-end retriever + LM training** [abstract, recalled]
- RA-DIT (2023): dual instruction tuning that fine-tunes the LM to use retrieved text *and* fine-tunes the retriever toward what the LM prefers. With 65B it reports +8.9% (0-shot) and +1.4% (5-shot) on average over in-context RALM baselines — [arXiv 2310.01352](https://arxiv.org/abs/2310.01352)
- Atlas (2022): jointly trained retriever + T5 reader. 11B Atlas reaches **42.4% on NQ with 64 examples**, beating a 540B model by ~3 points with 50× fewer parameters — [arXiv 2208.03299](https://arxiv.org/abs/2208.03299)
- REALM (2020): a retriever pretrained jointly with masked-LM. It gives +4–16% absolute on open-domain QA over prior methods — [arXiv 2002.08909](https://arxiv.org/abs/2002.08909)
- Toolformer (2023): GPT-J 6.7B self-supervises API-call insertion (calculator, QA, search, MT, calendar), keeping only calls that lower LM loss. It is often competitive with much larger models, and it beats GPT-3 175B on its math-word-problem and some factual subsets — [arXiv 2302.04761](https://arxiv.org/abs/2302.04761)

### Inferences
- The recipe most likely to make a small model synergize with its harness: (1) SFT on harness-format traces (TinyAgent-style synthetic data), then (2) RL on the whole loop with **harness-text masked from the loss**, **dense/process rewards** (critical below ~8B per Planner-R1), and an explicit action set that includes `ask_user`, `search`, `calc`, `answer`. Instruct-initialized models may be the better starting point at small scale (Search-R1, 3B).
- Joint retriever–LM training (Atlas/RA-DIT) remains attractive for a browser setting. The retriever can be tiny, the LM learns to trust it, and the retriever learns what the LM needs.
- A "when to ask/retrieve" policy is itself a learnable head (Self-RAG tokens, FLARE uncertainty). For a small model this is cheap and lets the harness spend tool budget only where needed.

### Gaps
- No results found for agent RL on ≤1B models with search/tools. The smallest found is 3B (Search-R1). Whether a ~0.3–0.5B model can learn multi-turn tool policies stably under RL is unproven.
- Clarification-RL results rely on LLM judges and simulators. I found no human-user validation at small scale.
- ToolRL and ReSearch numbers were not re-verified this session.

---

## Q3. The harness adapting to the model (optimized prompts/context, verifiers, self-consistency, program execution)

### Takeaway
Making the harness do the parts small models are bad at — exact arithmetic, search over candidates, verification — gives some of the largest documented lifts. Program-aided reasoning (PAL/PoT) and verifier-guided search (rStar-Math, compute-optimal test-time scaling) let 1B–7B models match or beat models 10–400× larger *on math*. Prompt/pipeline optimizers (DSPy) give large gains for small LMs, though those gains are measured against weak baselines.

### Cited Findings
- Compute-optimal test-time scaling (2025): with a reward-model-guided search strategy chosen per policy model, a **1B model beats a 405B model on MATH-500**, a 3B model beats 405B, and a 0.5B model beats GPT-4o (per the authors). This needs a strong process reward model, and the optimal strategy depends on the policy, PRM and difficulty [abstract, recalled] — [arXiv 2502.06703](https://arxiv.org/abs/2502.06703)
- rStar-Math (Microsoft, 2025): MCTS guided by a small process preference model, with self-evolved training. Qwen2.5-Math-7B rises from 58.8% → **90.0%** on MATH and Phi3-mini-3.8B from 41.4% → 86.4%, surpassing o1-preview on MATH. This is math-specific and relies on code-verified steps [abstract, recalled] — [arXiv 2501.04519](https://arxiv.org/abs/2501.04519)
- Snell et al. (2024): with compute-optimal test-time compute, a smaller model can outperform a **14× larger** model in FLOPs-matched comparisons, but only on prompts where the small model already has non-trivial success. For the hardest problems, pretraining scale wins [abstract, recalled] — [arXiv 2408.03314](https://arxiv.org/abs/2408.03314)
- DSPy (2023): compiled pipelines let GPT-3.5 and Llama2-13b-chat beat standard few-shot prompting by over 25% and 65% respectively, and beat expert-written demonstrations by 5–46% and 16–40%. Small LMs (770M T5, Llama2-13b) become competitive with expert-prompted GPT-3.5 pipelines [abstract, recalled] — [arXiv 2310.03714](https://arxiv.org/abs/2310.03714); also cited as the canonical system-optimization approach in [BAIR blog](https://bair.berkeley.edu/blog/2024/02/18/compound-ai-systems/) [verified]
- PAL (2022): the LM writes a Python program and the harness executes it. Codex + PAL beats PaLM-540B chain-of-thought on GSM8K by ~15% absolute top-1 [abstract, recalled] — [arXiv 2211.10435](https://arxiv.org/abs/2211.10435)
- Program-of-Thoughts (2022): delegating computation to an interpreter gives ~12% average gain over chain-of-thought across math and financial QA datasets [abstract, recalled] — [arXiv 2211.12588](https://arxiv.org/abs/2211.12588)
- Self-consistency (2022): sampling several reasoning paths and majority-voting adds +17.9% on GSM8K for large models [abstract, recalled] — [arXiv 2203.11171](https://arxiv.org/abs/2203.11171)
- TinyAgent's harness-side "Tool RAG" (a DeBERTa-v3-small classifier choosing ~4 of 16 tools) *improves* accuracy (1.1B: 78.89% → 80.06%) while shrinking the prompt from 2,762 to 1,397 tokens. Naive embedding-RAG tool selection *hurt* accuracy (74.88%) [verified] — [arXiv 2409.00608](https://arxiv.org/pdf/2409.00608)

### Inferences
- For a browser model, a code-execution/calculator tool plus a "write a program, harness runs it" format is likely the single cheapest large win on arithmetic-heavy tasks. Verifier/PRM search multiplies latency, which is a real constraint on-device.
- The harness should curate context *for this model* (TinyAgent's learned tool selector beat naive retrieval). For small models, *less but more precise* context outperforms *more* context, consistent with Anthropic's "attention budget" framing.

### Gaps
- Most PAL/PoT/self-consistency numbers come from ≥7B or proprietary models. Lift on sub-1B models is under-reported, and small models often cannot write correct code reliably.
- The 1B-beats-405B result depends on a large PRM (often 7B+), so the "system" is not small. Whether the PRM counts in the parameter budget changes the conclusion.
- The DSPy and test-time-scaling numbers were not re-verified this session.

---

## Q4. Division of labour: where small model + tools beats larger models, and where it still loses

### Takeaway
On **narrow, tool-shaped tasks** (function-call orchestration, math with execution, lookup QA, domain-specific planning, clarification dialogs), small models trained for their harness beat much larger generalists, sometimes frontier models. The wins are on the authors' own benchmarks, often with synthetic data. On **open-ended reasoning, multi-hop composition with compressed context, broad knowledge, and code quality**, scale still dominates, and compressed/latent interfaces specifically lose ground.

### Cited Findings
**Wins**
- TinyAgent-1.1B (4-bit, 0.68 GB) reaches **80.06–80.35%** success versus GPT-4-Turbo **79.08%** and GPT-3.5 65.04% on a 16-function Mac-assistant benchmark (correct function set + dependency DAG). Before fine-tuning it scored 12.71%. The training data is 80K synthetic examples generated by GPT-4-Turbo for ~$500 [verified] — [arXiv 2409.00608](https://arxiv.org/pdf/2409.00608)
- Planner-R1-8B/32B (~56%) versus GPT-5 (21.2%) on TravelPlanner [verified] — [arXiv 2509.25779](https://arxiv.org/html/2509.25779v1)
- SpeakRL-7B (46.17%) versus Claude-Sonnet-4 (44.08%) on MultiWOZ clarification-driven success [verified] — [arXiv 2512.13159](https://arxiv.org/pdf/2512.13159)
- Llama-3.1-8B + 0.54 GB Cartridge ≈ Llama 4 Scout 109B with full context on MTOB [verified] — [Hazy Research blog](https://hazyresearch.stanford.edu/blog/2025-06-08-cartridges)
- A 0.5B Memory Decoder lifts 72B models in-domain, and lifts Qwen2-0.5B's domain perplexity below its LoRA-tuned version [verified] — [arXiv 2508.09874](https://arxiv.org/html/2508.09874v1)
- Toolformer 6.7B > GPT-3 175B on math subsets; Atlas 11B > 540B on few-shot NQ; RETRO ≈ GPT-3 with 25× fewer parameters [abstract, recalled] — [Toolformer](https://arxiv.org/abs/2302.04761); [Atlas](https://arxiv.org/abs/2208.03299); [RETRO](https://arxiv.org/abs/2112.04426)

**Losses / limits**
- Compressed injection loses on multi-hop: xRAG HotpotQA scores 34.05 versus 38.79 for full-text RAG [verified] — [arXiv 2405.13792](https://arxiv.org/html/2405.13792v2)
- Agent RL is fragile at smaller scale. The 8B Planner-R1 collapsed under sparse rewards while 32B did not, and Search-R1's gains at 3B are ~half those at 7B [verified] — [Planner-R1](https://arxiv.org/html/2509.25779v1); [Search-R1](https://arxiv.org/html/2503.09516v5)
- Test-time scaling helps a small model only where it already has non-trivial success; for hard problems, larger pretrained models win [abstract, recalled] — [arXiv 2408.03314](https://arxiv.org/abs/2408.03314)
- KBLaM is untested for complex reasoning, and its authors say it is not deployment-ready [verified] — [Microsoft Research blog](https://www.microsoft.com/en-us/research/?p=1133691)
- TinyAgent's wins are on a closed, synthetic, self-made benchmark of 16 tools, so it may not transfer [verified] — [arXiv 2409.00608](https://arxiv.org/pdf/2409.00608)

### Inferences
- The pattern: the harness can substitute for **knowledge** (retrieval, memory, cartridges) and for **exact computation** (code, calculator). Training can substitute for **procedural skill on a fixed tool set** (TinyAgent, Planner-R1). Neither substitutes well for **compositional reasoning breadth**. A ≤500 MB model should therefore be scoped to orchestration, lookup and computation, and should escalate or ask on open-ended reasoning and code generation.
- "Beats GPT-4/GPT-5" claims should be read as "on a task distribution the small model was trained for". None of the cited works shows a small system winning on broad benchmarks.

### Gaps
- I found no rigorous head-to-head on **code quality** (e.g., SWE-bench) showing a small model plus harness approaching large models. The absence suggests it remains a loss, but that is not demonstrated here.
- No study found that evaluates the *same* small-model harness across many out-of-distribution tasks to measure how general the synergy is.

---

## Q5. Framing: "system intelligence" vs model intelligence (compound AI, cognitive core) — what is shown vs speculation

### Takeaway
The "compound AI systems" framing (BAIR, Feb 2024) is a well-argued *position* supported by examples (AlphaCode 2, AlphaGeometry, Medprompt, CoT@32) and by adoption data. It is not a theory with predictive laws. Karpathy's "cognitive core" (a few-billion-parameter model that "maximally sacrifices encyclopedic knowledge for capability") is a vision statement. The empirical results above partly support it (knowledge can be externalized; skill can be trained), but no one has shown a small core matching frontier *reasoning* once knowledge is externalized.

### Cited Findings
- BAIR (Zaharia et al., Feb 18, 2024): state-of-the-art results increasingly come from compound systems with multiple model calls, retrievers and tools, and "compound AI systems will likely be the best way to maximize AI results in the future". Databricks found 60% of LLM apps use RAG and 30% use multi-step chains. Arguments: engineering can be cheaper than scaling training, plus freshness/access control, trust and cost tuning. Open problems: non-differentiable components block end-to-end training, and design/operations get harder. DSPy is presented as the optimizer approach [verified] — [BAIR blog](https://bair.berkeley.edu/blog/2024/02/18/compound-ai-systems/)
- Karpathy's tweet as quoted: a "few billion param model that maximally sacrifices encyclopedic knowledge for capability". The page I checked gave no exact date or parameter target beyond "a few billion" [verified quote via secondary source] — [LessWrong](https://www.lesswrong.com/posts/qBsj6HswdmP6ahaGB/andrej-karpathy-on-llm-cognitive-deficits)
- Counter-view (Sean Goedecke): reasoning may depend on broad background knowledge and many parameters, so bigger models may keep winning; he compares this to the Jevons paradox (opinion) — [seangoedecke.com](https://seangoedecke.com/cognitive-core/)
- Anthropic expects "smarter models will need less prescriptive engineering over time". This implies that harness value is partly a stand-in for model weakness, which is relevant to how durable small-model harness investments are (opinion) [verified] — [Anthropic Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)

### Inferences
- **Shown:** knowledge can be moved out of weights into harness/memory with little loss on lookup tasks (RETRO, Atlas, Memory Decoder, Cartridges, KBLaM). Narrow procedural skill can be trained into small models so that they beat frontier models on fixed tool sets.
- **Not shown:** that a ~0.1–0.5B "cognitive core" retains enough reasoning to exploit those externalities on open-ended tasks. The smallest strong agent-RL results are 3B–8B, and compressed interfaces fail exactly on composition.
- A practical synthesis for the user: co-design means (1) a harness that owns knowledge, exact computation and state (files, todo recitation, KV prefix cache), and verifies outputs; (2) a model trained in that exact harness (masked tool outputs, dense rewards, learned retrieve/ask decisions); and (3) an attention-level interface (knowledge tokens / precomputed KV) for high-volume lookup, with full text kept for multi-hop.

### Gaps
- There is no formal theory of "system intelligence" with measurable scaling laws for harness + model combinations. Optimization of non-differentiable systems remains open per BAIR.
- I could not verify the date or full text of Karpathy's tweet, or any later quantitative statements by him (e.g., in podcasts).
