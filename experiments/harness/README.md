# Harness, first cut

An untouched model answers Keal's 18 real messages (`tasks.json`, same as `experiments/answers`) with tools. Each turn it writes one action line, `SEARCH:`, `FETCH:`, `ASK:` or `ANSWER:`; the harness runs it and feeds the result back, up to 6 turns. Long messages are chunked first. Search (DuckDuckGo, Wikipedia fallback) and fetch results are cached by the exact query/URL in `cache.json`, so reruns are repeatable and a new query always gets a live search. `ASK` gets "Keal isn't available" in automated runs.

Compared with `experiments/answers` (same models, no tools): Qwen3 0.6B (thinking off/on), 1.7B and 4B (thinking on). Graded by hand against the same pre-written rules.
