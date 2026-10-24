# Harness v2 (native Qwen3 tool calls): hand grades, same rules

| model | no tools | v1 (made-up format) | v2 (native format) | tool calls in v2 |
|---|---|---|---|---|
| Qwen3-0.6B | 1/18 | 1/18 | 1/18 | none |
| Qwen3-0.6B, thinking | 2/18 | 0/18 | 0/18 | 5 searches, 1 ask |
| Qwen3-1.7B | – | – | 2/18 | none |
| Qwen3-1.7B, thinking | 7/18 | 6/18 | 7/18 | 11 searches |

Passes: 0.6B #17; 1.7B #14 #17; 1.7B thinking #3 #10 #11 #12 #14 #15 #17.

- The native format fixed the mechanics: no malformed calls, no searching for placeholder text.
- With thinking off, neither model called a tool even once; they refused, asked for clarification, or guessed.
- 1.7B with thinking searched well (e.g. "Chinchilla insight", "Opus 5.5") but didn't turn results into right answers:
  it found Chinchilla but not the 20 tokens per parameter, and it suggested `git reset --hard` as an "alternative".
