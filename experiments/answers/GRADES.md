# Hand grades (Claude, against each task's pre-written rule in tasks.json)

Strict: an answer passes only if it does what the rule says; confidently wrong extras (e.g. `--hard`, "Chinchilla is from Alibaba") fail it.

| task | 0.6B | 0.6B think | 1.7B think | 4B think |
|---|---|---|---|---|
| 0 kill 8080 | ✗ refused | ✗ treats 8080 as a PID | ✓ | ✓ |
| 1 undo last commit, keep changes | ✗ --hard | ✗ revert | ✗ revert | ✓ reset HEAD~1 |
| 2 Chinchilla | ✗ the rodent | ✗ | ✗ "Alibaba model" | ✗ wrong lab, no 20 tokens/param |
| 3 frontier training time | ✗ | ✗ | ✗ | ✗ |
| 4 tiny model, trillions of tokens | ✗ | ✗ | ✗ | ✗ |
| 5 Opus 5.5 details | ✗ confused | ✗ made-up claims | ✓ says it doesn't know | ✓ says it can't give details |
| 6 REN vs attention, MLP | ✗ | ✗ | ✗ | ✗ |
| 7 many tiny specialist models | ✗ | ✗ "split screens" | ✓ modular nets | ✓ modular nets |
| 8 access to "kraggle" | ✗ | ✗ | ✗ | ✗ doesn't explain API token |
| 9 Cloudflare Worker | ✗ "runs in the browser" | ✗ "runs in the browser" | ✓ | ✓ |
| 10 "I use fetch all the time" | ✗ | ✗ | ✓ CORS | ✓ same-origin / CORS |
| 11 WASM/workers hack? | ✗ | ✗ | ✗ | ✓ no, use a proxy |
| 12 key visible in browser? | ✗ "use HTTPS" | ✗ | ✓ | ✓ |
| 13 200–500 MB reasonable? | ✗ thinks phone storage | ✗ thinks phone storage | ✗ "200 MB = 200M params" | ✓ |
| 14 better every 8 months? | ✗ | ✓ data + training methods | ✓ | ✓ |
| 15 GPU services | ✗ | ✗ | ✗ names no providers | ✓ AWS, GCP… |
| 16 need ACCOUNT_ID? | ✗ "yes, required" | ✓ "not mandatory" | ✗ "required" | ✗ "required" |
| 17 can you tell it was voice? | ✓ | ✗ | ✗ | ✓ |
| **total** | **1/18** | **2/18** | **7/18** | **12/18** |
