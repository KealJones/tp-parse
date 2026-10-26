# Small LMs that offload knowledge to retrieval/tools: how much size it saves, on which tasks, and how the model and harness should be co-designed

Scope note: the coordinator added an emphasis mid-task. The core question is how a small model and its harness can be designed **together** so that the pair beats a bigger standalone model, and what made that work (joint retriever+LM training, training on its own tool outputs, RL on the full loop, learned when-to-call). Sections are ordered to put that first.

Method caveat: about 20 tool calls. Most fetches returned abstract-level summaries only, so many per-table numbers could not be confirmed. Numbers recalled from memory but **not verified this session** are kept out of Cited Findings and listed under Gaps with the labels "UNVERIFIED".

## Q1. Which system designs (small model + retrieval/tools) beat much larger standalone models, and what made them work?

### Takeaway
Every documented case where a much smaller model plus retrieval/tools matches or beats a far larger standalone model comes from **training the model and the harness together**: a retriever trained end to end with the LM (REALM, Atlas), joint pretraining with retrieval (RETRO), fine-tuning on the exact tool and retrieval format (TinyAgent, RA-DIT), or RL through the live tool loop (Search-R1). The "25x" and "50x" savings are real, but they are measured on **knowledge-heavy** metrics: Pile perplexity and open-domain QA.

### Cited Findings
- **RETRO (DeepMind, 2021):** with a 2-trillion-token retrieval database, RETRO performs comparably to GPT-3 and Jurassic-1 on the Pile while using 25x fewer parameters. After fine-tuning, its performance carries over to knowledge-intensive tasks such as QA. Pretrained transformers can be "quickly" retrofitted with retrieval and still perform well, though RETRO itself is usually trained from scratch. — [Borgeaud et al., arXiv:2112.04426](https://arxiv.org/abs/2112.04426)
- **Atlas (Meta, 2022):** over 42% accuracy on Natural Questions with only 64 training examples, beating a 540B-parameter model by 3 points while using 50x fewer parameters. (The abstract does not name the 540B model; the paper body identifies it as PaLM.) Atlas jointly trains the retriever and the reader. — [Izacard et al., arXiv:2208.03299](https://arxiv.org/abs/2208.03299)
- **REALM (Google, 2020):** the retriever is pretrained without supervision, using masked language modeling as the learning signal, and gradients flow back through a retrieval step over millions of documents. After fine-tuning it beats prior SOTA on three Open-QA benchmarks by 4–16% absolute. — [Guu et al., arXiv:2002.08909](https://arxiv.org/abs/2002.08909)
- **RA-DIT (Meta, 2023), a retrofit recipe:** two separate fine-tuning steps, (1) teach the LM to use retrieved content and (2) teach the retriever to return what the LM prefers. Each step brings significant gains on its own, and combining them adds more. The 65B model beats in-context RAG baselines by up to +8.9% in the 0-shot setting and +1.4% in the 5-shot setting on average. — [Lin et al., arXiv:2310.01352](https://arxiv.org/abs/2310.01352)
- **Search-R1 (2025), RL on the full search loop:** the model learns, through outcome-reward RL, to issue multiple search queries during step-by-step reasoning with live retrieval. It improves over RAG baselines by 41% (Qwen2.5-7B) and 20% (Qwen2.5-3B) relative across seven QA datasets. Retrieved tokens are masked out of the RL loss for stable training. The abstract reports nothing below 3B. — [Jin et al., arXiv:2503.09516](https://arxiv.org/abs/2503.09516)
- **Self-RAG (2023), learned when to retrieve:** a single LM (7B/13B) generates "reflection tokens" that decide whether to retrieve on demand and critique the passages and its own output. It reportedly outperforms ChatGPT and retrieval-augmented Llama2-chat on open-domain QA, reasoning and fact verification. The abstract gives no numbers. — [Asai et al., arXiv:2310.11511](https://arxiv.org/abs/2310.11511)
- **Toolformer (2023), trained on its own tool calls:** self-supervised; from a handful of demonstrations per API the model learns which tool to call, when, with what arguments, and how to use the result (calculator, QA system, two search engines, translation, calendar). Zero-shot it is "often competitive with much larger models." — [Schick et al., arXiv:2302.04761](https://arxiv.org/abs/2302.04761)
- **TinyAgent (Berkeley, 2024), clearest ≤1.1B evidence of co-design:**
  - Fine-tuning on 80K synthetic function-calling examples raised TinyAgent-1.1B from 12.71% to 78.89% success, and the 7B from 41.25% to 83.09%. The examples were generated with GPT-4-Turbo for about $500.
  - Adding a **learned tool retriever** (fine-tuned DeBERTa-v3-small, "Tool RAG") brought the 1.1B to 80.06%, versus GPT-4-Turbo at 79.08% and GPT-3.5 at 65.04%. The prompt shrank from 2,762 to 1,397 tokens, with tool recall of 0.998.
  - Generic (untrained) tool RAG **hurt**: 74.88% for the 1.1B.
  - 4-bit quantization took the 1.1B from 2.2 GB to 0.68 GB with no accuracy loss (80.35%), thanks to quantization-aware extra fine-tuning. Latency dropped from 3.9 s to 2.9 s.
  - The task is a narrow, closed domain: 16 macOS functions with LLMCompiler-style planning.

  — [BAIR blog, TinyAgent](https://bair.berkeley.edu/blog/2024/05/29/tiny-agent/); [arXiv:2409.00608](https://arxiv.org/abs/2409.00608)

### Inferences
- The recurring recipe:
  1. Fix the tool/retrieval interface.
  2. Generate large synthetic traces in that exact format (with a strong teacher).
  3. Fine-tune the small model on them.
  4. Train the retriever or tool-selector against the small model's needs. Atlas, REALM and RA-DIT do this for passages; TinyAgent does it for tools.
  5. Optionally, RL on end-task reward through the live loop (Search-R1).

  Untrained retrieval, whether generic tool RAG or off-the-shelf passages, often **hurts** small models (TinyAgent basic RAG; see Q2).
- For a ≤500 MB browser model (about 0.5–1B at 4-bit): TinyAgent-1.1B at 0.68 GB is the nearest existence proof, and it beat GPT-4-Turbo only on a **narrow, fixed toolset**. Expect "beats a big model" results only where the harness narrows the task: few tools, retrieved tool schemas, structured outputs, verification by execution.
- Making the harness do selection, so the model sees few and relevant tools or passages, is itself a size saver. TinyAgent's learned tool retriever added accuracy while halving the prompt.

### Gaps
- UNVERIFIED (from memory; the abstract fetch didn't confirm): Atlas is 11B; Atlas-11B was about 47% on MMLU 5-shot, above GPT-3 175B.
- UNVERIFIED: REALM is about 330M and beat T5-11B on NaturalQuestions (about 40 vs 34.5 EM).
- UNVERIFIED: Toolformer uses GPT-J 6.7B and beats GPT-3 175B on some math and QA tasks. Its paper reports that useful tool-calling only emerges around 775M parameters or more. I couldn't verify this scale threshold, and it matters for a sub-1B design.
- Search-R1-style RL at ≤1B: no verified results found. Later work (R1-Searcher, ZeroSearch, etc.) wasn't fetched.
- kNN-LM: not fetched. UNVERIFIED memory: about 2.9-point perplexity gain on Wikitext-103 (18.65 to 15.79), with gains concentrated on rare factual tokens.

## Q2. Where do retrieval gains shrink or vanish (knowledge vs reasoning), and can ≤1B models even use retrieved context?

### Takeaway
Retrieval mostly buys **knowledge**, not skill. The RETRO reproduction found large gains on knowledge-intensive tasks and parity elsewhere. A 2026 study finds that sub-7B models with **standard prompting** often get *worse* with RAG, because they fail to use even gold passages. Utilization skill, which needs training, is the bottleneck for small models, not retrieval quality.

### Cited Findings
- **"Shall we pretrain autoregressive LMs with retrieval?" (NVIDIA, 2023):**
  - The study reproduces RETRO up to 9.5B parameters with a 330B-token retrieval corpus.
  - RETRO "largely outperforms" GPT on knowledge-intensive tasks.
  - It is only **on par** with GPT on the remaining LM Evaluation Harness tasks.
  - It shows less degeneration, moderately higher factuality, and slightly lower toxicity.
  - RETRO++ adds +8.6 EM on NQ over the original RETRO.

  — [Wang et al., arXiv:2304.06762](https://arxiv.org/abs/2304.06762)
- **"Can Small Language Models Use What They Retrieve?" (March 2026):** models tested were SmolLM2-360M, Qwen2.5-1.5B/3B/7B (4-bit), with Llama-3.1-8B as a check, on NQ plus HotpotQA.
  - **Gold passages barely help on questions the model didn't know.** Oracle-passage EM was 0.0% (360M), 10.0% (1.5B), 12.8% (3B) and 14.6% (7B). The authors estimate 85–100% of oracle retrievals went unused.
  - **Any context damages what the model already knew.** On questions answered correctly closed-book, EM fell to 36.0% with noisy passages and 43.0% with oracle passages (1.5B); 46.4% / 54.4% (3B); 48.8% / 58.4% (7B). At 1.5B and 3B, noisy and oracle passages did statistically similar harm.
  - **Net effect of RAG is negative at every size.** Dense retrieval minus closed-book was −11.0 pp (1.5B), −7.5 pp (3B) and −2.5 pp (7B). Llama-3.1-8B scored 24.0% closed-book versus 16.5–17.5% with retrieval.
  - **Prompt tweaks don't fix it.** On 3B, retrieval prompts scored 9–12.5% versus 19.5% closed-book.
  - **Main failure mode is ignoring the passage.** This accounted for 100% of oracle failures (360M), 64% (1.5B), 73% (3B) and 61% (7B).
  - The authors estimate robust utilization (>50% oracle EM) may need more than 7B parameters with standard prompting. They recommend RAG-aware fine-tuning and confidence-gated (adaptive) retrieval.
  - Caveats: about 2% Wikipedia corpus, exact-match scoring, 4-bit quantization, no instruction fine-tuning for RAG.

  — [arXiv:2603.11513](https://arxiv.org/html/2603.11513v1)

### Inferences
- That result is the strongest argument for **co-design**. An off-the-shelf sub-1B model with naive RAG is likely worse than closed-book. The model must be fine-tuned to read context (RA-DIT step 1, Self-RAG, ChatQA-style), and the harness should gate retrieval. "Exact-match" scoring also undercounts verbose correct answers: in that paper, counting format issues as correct raises 7B oracle EM from 14.6% to about 21%.
- Reasoning, composition, and multi-step planning don't transfer through retrieved text. The RETRO reproduction shows parity on non-knowledge tasks. Retrieved content supplies facts, not the procedure for using them.

### Gaps
- ChatQA (NVIDIA) and InstructRetro numbers weren't fetched. UNVERIFIED: InstructRetro 48B improved about 7% over instruction-tuned GPT on short-form QA.
- No ≤1B RAG-fine-tuned faithfulness benchmark was verified. The 2026 paper's 1.5B is the smallest data point with usable signal; its 360M had only 11 "Known" questions.

## Q3. Small agentic and function-calling models (≤2B): scores and training

### Takeaway
On the broad, hard BFCL v4 (multi-turn, agentic, web search, memory), sub-2B models score about 20–32% versus about 73–77% for frontier models. Small specialists win only on narrow, fixed tool sets, as TinyAgent shows.

### Cited Findings
- **BFCL v4 overall scores**, aggregated from Gorilla leaderboard imports (2026-05-28) and model cards. The aggregator warns that rows from different snapshots may not be directly comparable. — [benchmarklist.com BFCL v4](https://benchmarklist.com/benchmarks/bfcl_v4/)

  | Size band | Model | BFCL v4 overall |
  |---|---|---|
  | ≤1B | Granite-4.0-350m (FC) | 18.98% |
  | ≤1B | Hammer2.1-0.5b (FC) | 21.22% |
  | ≤1B | Qwen3-0.6B (FC) | 23.93% |
  | ≤1B | Qwen3.5-0.8B (model card) | 25.3% |
  | ≤1B | Gemma-3-1b-it (Prompt) | 7.17% |
  | ≤1B | Llama-3.2-1B-Instruct (FC) | 10.82% |
  | ≤1B | xLAM-2-1b-fc-r (FC) | 30.44% |
  | 1.5–2B | Hammer2.1-1.5b | 27.88% |
  | 1.5–2B | Qwen3-1.7B (FC) | 28.41% |
  | 1.5–2B | Arch-Agent-1.5B | 32.14% |
  | 1.5–2B | Qwen3.5-2B (model card) | 43.6% |
  | 3–4B | Qwen3-4B-Instruct-2507 | 35.68% |
  | 3–4B | xLAM-2-3b-fc-r | 41.22% |
  | 3–4B | Qwen3.5-4B | 50.3% |
  | 3–4B | Nanbeige4-3B-Thinking | 51.4% |
  | Frontier | Claude-Opus-4.5 (FC) | 77.47% |
  | Frontier | Claude-Sonnet-4.5 (FC) | 73.24% |
  | Frontier | Gemini-3-Pro-Preview (Prompt) | 72.51% |
  | Frontier | GPT-5.2 (FC) | 55.87% |

- **Specialist fine-tuning matters most at small sizes.** xLAM-2-1b (30.44%) beats general Llama-3.2-1B (10.82%) and Gemma-3-1b (7.17%) by about 3x. — [benchmarklist.com BFCL v4](https://benchmarklist.com/benchmarks/bfcl_v4/)
- **xLAM-2 training:** APIGen-MT generates multi-turn agent data via simulated agent–human interplay. The xLAM-2-fc-r models are trained on it. — [APIGen-MT, arXiv:2504.03601](https://arxiv.org/pdf/2504.03601); [xLAM, arXiv:2409.03215](https://arxiv.org/pdf/2409.03215)
- **TinyAgent-1.1B:** 80.06% vs GPT-4-Turbo 79.08% on its own 16-function benchmark (details in Q1). — [BAIR](https://bair.berkeley.edu/blog/2024/05/29/tiny-agent/)
- **IFFC (Aug 2026):** a paper reports that function calling is more accurate framed as instruction-following, and offloads function-calling logic to a separate smaller model. It claims robustness under aggressive quantization. The abstract gives no numbers. — [arXiv:2608.22472](https://arxiv.org/abs/2608.22472)

### Inferences
- Frontier-to-sub-1B gaps on general agentic BFCL are about 45–55 points. Qwen3.5-2B at 43.6% suggests rapid progress, but it is self-reported from the model card.
- For the user's harness, which supplies all context through a small, fixed tool set (search, calculator, ask-user, memory, code exec), the TinyAgent regime is the relevant one, not BFCL's open-ended one. A ≤0.6B specialist fine-tuned on traces of exactly those tools, plus a learned tool and context selector, is the evidence-backed path.

### Gaps
- No ≤1B multi-turn agent results were found where the small model beats a frontier model on a broad benchmark.
- Gorilla, NexusRaven and Octopus v2 numbers weren't verified. UNVERIFIED: Octopus v2 (2B) reported about 99.5% on its own Android-API set using functional tokens; that is an in-house, narrow benchmark.
- Hammer's training recipe (function-masking) wasn't fetched.
- No BFCL entry was found for Google's FunctionGemma (270M).

## Q4. Code: does retrieval close the gap, or is skill the bottleneck? (TypeScript relevance)

### Takeaway
For code, the bottleneck is **skill**. Small code models look decent on easy, likely contaminated benchmarks (HumanEval about 62–71%), but collapse on harder, fresher ones: LiveCodeBench 2.0–6.1%, BigCodeBench-Hard 1.4–6.8%. Repository retrieval helps completion (RepoCoder >10%), but there's no evidence it closes the synthesis gap to large models.

### Cited Findings
- **Qwen2.5-Coder instruct models, with the 3B for reference:** — [Qwen2.5-Coder tech report, arXiv:2409.12186](https://arxiv.org/html/2409.12186v3)

  | Benchmark | 0.5B | 1.5B | 3B |
  |---|---|---|---|
  | HumanEval | 61.6 | 70.7 | 84.1 |
  | HumanEval+ | 57.3 | 66.5 | 80.5 |
  | MBPP | 52.4 | 69.2 | 73.6 |
  | MBPP+ | 43.7 | 59.4 | 62.4 |
  | BigCodeBench full | 11.1 | 32.5 | 35.8 |
  | BigCodeBench hard | 1.4 | 6.8 | 14.2 |
  | LiveCodeBench | 2.0 | 6.1 | 10.8 |

  The instruct tables have no TypeScript-specific (MultiPL-E TS) score; it appears only for base models and wasn't extracted.
- Qwen2.5-Coder-32B-Instruct scores 73.7 on Aider, which Qwen describes as comparable to GPT-4o. — [Qwen blog](https://qwenlm.github.io/blog/qwen2.5-coder-family/)
- **RepoCoder:** iterative retrieval and generation over the repository improves the in-file completion baseline by over 10% in all settings, and consistently beats vanilla retrieval-augmented completion. Model sizes weren't in the abstract. — [Zhang et al., arXiv:2303.12570](https://arxiv.org/abs/2303.12570)

### Inferences
- The 0.5B model drops from 61.6 (HumanEval) to 2.0 (LiveCodeBench). That pattern is consistent with HumanEval being saturated or contaminated, and with real synthesis skill being scarce below about 3B.
- Retrieval (repo context, API docs, type definitions) helps with *what exists* (names, signatures). It doesn't help with *how to compose* it.
- For TypeScript specifically, the strongest harness lever is likely **execution and type-checking feedback** (`tsc` errors fed back to the model). That's a verifier, not retrieval. No verified small-model numbers were found for it this session.

### Gaps
- Small-model numbers for API- or documentation-retrieval code generation (e.g., DocPrompting, CodeRAG-Bench) weren't fetched.
- Qwen3 or 2026 sub-1B coder scores on LiveCodeBench weren't fetched.
- No MultiPL-E TypeScript instruct score was found for 0.5B/1.5B.
- Contamination: HumanEval and MBPP are widely believed contaminated. LiveCodeBench uses time-windowed problems to mitigate this. No contamination audit of Qwen2.5-Coder was fetched.

## Q5. Knowledge vs skill: what doesn't transfer via retrieval?

### Takeaway
The verified record is consistent:

| Task type | Does retrieval/tools substitute for parameters? | Evidence |
|---|---|---|
| Factual knowledge | Yes, and big savings (25–50x) when jointly trained | RETRO, Atlas, REALM |
| Narrow tool use | Yes, at 1.1B with fine-tuning plus learned tool selection | TinyAgent |
| General reasoning / non-knowledge tasks | No gain over a same-size model | RETRO repro parity |
| Using context at all | Not without training, below about 7B | 2026 utilization study |
| Code synthesis and broad agentic multi-turn | No; large gaps remain | LiveCodeBench, BFCL v4 |

### Cited Findings
- RETRO-style retrieval gives large gains on knowledge-intensive tasks but only parity on others. — [arXiv:2304.06762](https://arxiv.org/abs/2304.06762)
- Sub-7B models ignore gold passages in 61–100% of oracle failures. — [arXiv:2603.11513](https://arxiv.org/html/2603.11513v1)
- The small code-model collapse on LiveCodeBench and BigCodeBench-Hard (see Q4). — [arXiv:2409.12186](https://arxiv.org/html/2409.12186v3)
- The sub-2B vs frontier gap on BFCL v4 (see Q3). — [benchmarklist BFCL v4](https://benchmarklist.com/benchmarks/bfcl_v4/)

### Inferences
- A practical design rule for ≤500 MB:
  1. Spend parameters on **skills**: reading and using context, tool-call formatting, deciding when to call, TS syntax and idioms.
  2. Offload **facts** to retrieval and memory, and **arithmetic and verification** to tools (calculator, code exec, `tsc`).
  3. Train the model on traces of *its own harness*, then train the retriever or selector to the model's needs, then optionally RL through the loop.
- Expect to beat larger standalone models only on knowledge-bound or narrow-tool tasks. Expect to remain well behind on open-ended reasoning and code synthesis.

### Gaps
- No controlled study was found that isolates a "parameter-equivalent" saving for reasoning or code from retrieval. The literature measures this almost exclusively on knowledge QA and perplexity.
