# Harness v1: hand grades (same rules as experiments/answers)

| model | no tools (answers run) | with harness + tools |
|---|---|---|
| Qwen3-0.6B | 1/18 | 1/18 |
| Qwen3-0.6B, thinking | 2/18 | 0/18 |
| Qwen3-1.7B, thinking | 7/18 | 6/18 |
| Qwen3-4B, thinking | 12/18 | 11/18 |

Passes with tools: 0.6B #17; 1.7B #0 #1 #4 #9 #11 #14; 4B #0 #1 #3 #5 #9 #10 #11 #12 #14 #15 #17.

What went wrong:
- 0.6B often searched for the literal placeholder text "<a web search query>", or ASKed instead of searching, then answered with the harness's "Keal isn't available" reply.
- 1.7B looped on ASK (up to six times) for things a search would settle, e.g. "Kraggle", "services".
- Searches were often aimed wrong: "multiple tiny specific models in 3D modeling", "typical size range for models in AI or software".
- Even good results weren't used well: nobody got Chinchilla's ~20 tokens per parameter, and every model still said the Cloudflare account ID is required.
