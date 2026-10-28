# Training-side smoke: 1 epoch on each base on the teacher data in kealjones/squiggle-ft-data/<TAG> (comma-separated
# tags allowed), a small eval in the real harness, GGUF export with the wllama 3.8.1 load check, no upload.
# Usage: bash jobs/train_smoke.sh <out>   (env: TAG, BASES, EPOCHS)
OUT=$1
TAG=${TAG:-teach-smoke,teach-smoke-2}
set -x
DATA=""
for t in ${TAG//,/ }; do python hub.py down kealjones/squiggle-ft-data $t/train_examples.jsonl.gz --to data_in; DATA="$DATA,data_in/$t/train_examples.jsonl.gz"; done
python selftest.py ${DATA//,/ } --tokenizers unsloth/gemma-3-270m-it,unsloth/functiongemma-270m-it,LiquidAI/LFM2.5-350M > $OUT/selftest.txt 2>&1; tail -12 $OUT/selftest.txt
python train.py --data "${DATA#,}" --bases ${BASES:-gemma3,functiongemma,lfm25} --epochs ${EPOCHS:-1} \
  --eval-scale 0.1 --eval-minutes 6 --out $OUT/train --work work --export --hub-repo ""
ls -la gguf 2>/dev/null
rm -rf gguf
