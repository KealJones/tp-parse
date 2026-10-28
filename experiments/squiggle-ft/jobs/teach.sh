# Teacher episodes at full scale; the big files go to the private dataset kealjones/squiggle-ft-data (not git).
# Usage (from jobs/boot.py): bash jobs/teach.sh <out>   env: MINUTES (teacher time budget), TAG (dataset folder)
OUT=$1
MINUTES=${MINUTES:-110}
TAG=${TAG:-teach-v1}
set -x
python build.py teach --minutes $MINUTES --concurrency 48 --out data_out --work work
cp data_out/TEACHER_RESULTS.md $OUT/
pip install -q -U "transformers>=5,<6"     # vLLM 0.11 needed 4.x; LFM2.5's tokenizer needs 5.x
python selftest.py data_out/train_examples.jsonl.gz --tokenizers unsloth/gemma-3-270m-it,unsloth/functiongemma-270m-it,LiquidAI/LFM2.5-350M > $OUT/selftest.txt 2>&1; tail -12 $OUT/selftest.txt
python hub.py up kealjones/squiggle-ft-data $TAG data_out/train_examples.jsonl.gz data_out/teacher_results.jsonl.gz
python showcase.py data_out/teacher_results.jsonl.gz $OUT/TEACHER_EXAMPLES.md
