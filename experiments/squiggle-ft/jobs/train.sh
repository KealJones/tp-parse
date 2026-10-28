# Train the candidates on the teacher data, score them end to end, write RESULTS.md, export + upload the winner.
# Usage (from jobs/boot.py): bash jobs/train.sh <out>   env: TAG (dataset folder), BASES, EPOCHS, EVAL_MINUTES
OUT=$1
TAG=${TAG:-teach-v1}
set -x
python hub.py down kealjones/squiggle-ft-data $TAG/train_examples.jsonl.gz --to data_in
python train.py --data data_in/$TAG/train_examples.jsonl.gz,samples/samples.jsonl --bases ${BASES:-gemma3,functiongemma,lfm25} \
  --epochs ${EPOCHS:-2} --eval-minutes ${EVAL_MINUTES:-18} --out $OUT --work work --export --hub-repo kealjones/squiggle-small
rm -rf $OUT/gguf/*.gguf
