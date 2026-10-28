# The real training run on the teacher data in kealjones/squiggle-ft-data/<TAG> (comma-separated tags allowed): all three
# bases, full eval against the untouched Gemma 3 270M, RESULTS.md, and the winner exported (Q8_0 + Q4_0, checked in
# wllama 3.8.1) to the private repo kealjones/squiggle-small. Usage: bash jobs/train.sh <out>
#   env: TAG, BASES, EPOCHS, EVAL_MINUTES, LIMIT (minutes train.py may use)
OUT=$1
TAG=${TAG:-teach-v1}
set -x
DATA=""
# The teacher's episode results, re-checked here with the current checker (train.py keeps only strict, teacher-sourced ones).
for t in ${TAG//,/ }; do [ "$t" = none ] && continue; python hub.py down kealjones/squiggle-ft-data $t/teacher_results.jsonl.gz --to data_in; DATA="$DATA,data_in/$t/teacher_results.jsonl.gz"; done
# Episodes kept in the repo (re-rendered on the current pin: data/rerendered/*.jsonl.gz), comma-separated.
[ -n "$DATA_LOCAL" ] && DATA="$DATA,$DATA_LOCAL"
python selftest.py ${DATA//,/ } --tokenizers unsloth/gemma-3-270m-it,LiquidAI/LFM2.5-350M > $OUT/selftest.txt 2>&1; tail -12 $OUT/selftest.txt
python train.py --data "${DATA#,}" --bases ${BASES:-lfm25,gemma3} \
  --epochs ${EPOCHS:-3} --lr-per-base ${LRS:-lfm25=2e-5,gemma3=4e-5} --dev-frac 0.05 --reuse-cap ${REUSE_CAP:-25} \
  --budget-minutes ${LIMIT:-150} --out $OUT --work work --export --hub-repo kealjones/squiggle-small \
  ${HUB_PREFIX:+--hub-prefix $HUB_PREFIX} ${EVAL_MODELS:+--eval-models $EVAL_MODELS}
rm -rf gguf
