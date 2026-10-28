# The real run in one l4x1 job: teacher episodes, then train + score the candidates, then export the winner.
# Usage (from jobs/boot.py): bash jobs/real.sh <out>
#   env: LIMIT (minutes the whole job may use, < its timeout), MINUTES (teacher budget), TAG (dataset folder), BASES, EPOCHS
OUT=$1
LIMIT=${LIMIT:-162}   # boot starts after the runner's pip install (~5-8 min of the 180-min timeout)
MINUTES=${MINUTES:-80}
TAG=${TAG:-teach-v1}
T0=${SQFT_T0:-$(date +%s)}
set -x
python build.py teach --minutes $MINUTES --concurrency 48 --out data_out --work work
cp data_out/TEACHER_RESULTS.md $OUT/
python hub.py up kealjones/squiggle-ft-data $TAG data_out/train_examples.jsonl.gz data_out/teacher_results.jsonl.gz
python showcase.py data_out/teacher_results.jsonl.gz $OUT/TEACHER_EXAMPLES.md
python selftest.py data_out/train_examples.jsonl.gz --tokenizers unsloth/gemma-3-270m-it,unsloth/functiongemma-270m-it,LiquidAI/LFM2.5-350M > $OUT/selftest.txt 2>&1; tail -12 $OUT/selftest.txt
LEFT=$(( LIMIT - ($(date +%s) - T0) / 60 ))
python train.py --data data_out/train_examples.jsonl.gz,samples/samples.jsonl --bases ${BASES:-gemma3,lfm25,functiongemma} \
  --epochs ${EPOCHS:-2} --eval-minutes ${EVAL_MINUTES:-12} --budget-minutes $LEFT --out $OUT/train --work work --export --hub-repo kealjones/squiggle-small
rm -rf $OUT/train/gguf/*.gguf
