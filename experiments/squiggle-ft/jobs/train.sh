# The real training run on the teacher data in kealjones/squiggle-ft-data/<TAG> (comma-separated tags allowed): all three
# bases, full eval against the untouched Gemma 3 270M, RESULTS.md, and the winner exported (Q8_0 + Q4_0, checked in
# wllama 3.8.1) to the private repo kealjones/squiggle-small. Usage: bash jobs/train.sh <out>
#   env: TAG, BASES, EPOCHS, EVAL_MINUTES, LIMIT (minutes train.py may use)
OUT=$1
TAG=${TAG:-teach-v1}
set -x
DATA=""
# The teacher's episode results, re-checked here with the current checker (train.py keeps only strict, teacher-sourced ones).
for t in ${TAG//,/ }; do python hub.py down kealjones/squiggle-ft-data $t/teacher_results.jsonl.gz --to data_in; DATA="$DATA,data_in/$t/teacher_results.jsonl.gz"; done
python selftest.py ${DATA//,/ } --tokenizers unsloth/gemma-3-270m-it,LiquidAI/LFM2.5-350M > $OUT/selftest.txt 2>&1; tail -12 $OUT/selftest.txt
python train.py --data "${DATA#,}" --bases ${BASES:-gemma3,lfm25,functiongemma} \
  --epochs ${EPOCHS:-3} --eval-minutes ${EVAL_MINUTES:-15} --budget-minutes ${LIMIT:-150} --out $OUT --work work --export --hub-repo kealjones/squiggle-small
rm -rf $OUT/gguf/*.gguf
