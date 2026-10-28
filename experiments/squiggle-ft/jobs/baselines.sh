# Eval only: bases as released (no training), on the exact eval set squiggle-ft-train used (EVAL_PLAN_V1, seed 123).
# Usage: bash jobs/baselines.sh <out>   env: BASES (default lfm25,functiongemma), EVAL_MINUTES
OUT=$1
set -x
python train.py --eval-only --no-untouched --eval-bases ${BASES:-lfm25,functiongemma} --eval-plan v1 \
  --eval-minutes ${EVAL_MINUTES:-20} --out $OUT --work work --hub-repo ""
