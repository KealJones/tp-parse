# Training-side smoke: 1 epoch on each base on the teacher data in kealjones/squiggle-ft-data/<TAG>, a small eval in the
# real harness, GGUF export with the wllama 3.8.1 load check, no upload. Usage: bash jobs/train_smoke.sh <out>
OUT=$1
TAG=${TAG:-teach-smoke}
set -x
python hub.py down kealjones/squiggle-ft-data $TAG/train_examples.jsonl.gz --to data_in
python selftest.py data_in/$TAG/train_examples.jsonl.gz --tokenizers unsloth/gemma-3-270m-it,unsloth/functiongemma-270m-it,LiquidAI/LFM2.5-350M > $OUT/selftest.txt 2>&1; tail -12 $OUT/selftest.txt
python train.py --data data_in/$TAG/train_examples.jsonl.gz --bases gemma3,functiongemma,lfm25 --epochs 1 \
  --eval-scale 0.1 --eval-minutes 6 --out $OUT/train --work work --export --hub-repo ""
ls -la $OUT/train/gguf 2>/dev/null
rm -rf $OUT/train/gguf/*.gguf
