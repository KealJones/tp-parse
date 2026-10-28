# Export only: the weights a training run uploaded to <repo>/hf -> GGUF Q8_0 + Q4_0 (llama.cpp load check, wllama 3.8.1
# check in Chromium) -> uploaded next to them, with that run's RESULTS.md as the model card.
# Usage: bash jobs/export.sh <out>   env: BASE (gemma3 | lfm25 | functiongemma), RESULTS (default hf-train/RESULTS.md), REPO
OUT=$1
set -x
python train.py --export-only ${BASE:?set BASE} --results ${RESULTS:-hf-train/RESULTS.md} --out $OUT --work work \
  --hub-repo ${REPO:-kealjones/squiggle-small}
rm -rf gguf
