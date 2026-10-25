# Reading test: hand grades (right paragraph given, no search, thinking on)

| model | right paragraph only | + 2 unrelated paragraphs | with real search (v3) | no tools |
|---|---|---|---|---|
| Qwen3-1.7B | 18/18 | 16/18 | 5/18 | 7/18 |
| Qwen3-0.6B | 8/18 | 8/18 | 0/18 | 2/18 |

- 1.7B: reads fine. With unrelated paragraphs mixed in it dropped #2 (left out 20 tokens/param) and #4 (said training on trillions is "impractical").
  So the search was the bottleneck for 1.7B: the right text never reached it.
- 0.6B: misreads even with the answer handed to it (`kill 8080` as the command; "CORS allows cross-origin requests";
  "you need to add CLOUDFLARE_ACCOUNT_ID" then the opposite). Reading is its limit, not search.
- The auto check over-counted 0.6B (13 and 10) and under-counted 1.7B on #5 (it said the details aren't public; the regex missed the wording).
