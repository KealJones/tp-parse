# Untouched Qwen/Qwen3-0.6B + planning harness

No training. The harness lists the legal next moves; the model picks one by letter. 50 problems per cell.

| picker | clean/short | clean/long | messy/short | messy/long | filler/short | filler/long |
|---|---|---|---|---|---|---|
| random | 10% | 2% | 6% | 2% | 8% | 0% |
| qwen | 22% | 0% | 24% | 0% | 22% | 2% |

Failures:
- random: too many steps 195, wrong choice 91
- qwen: too many steps 208, wrong choice 57
