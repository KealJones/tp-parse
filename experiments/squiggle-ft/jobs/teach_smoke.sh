# Teacher smoke: the open-weights thinking teacher (teacher.py) on ~40 episodes across every family, 15-minute budget.
# Reports keep rate per family, drop reasons, tokens/s, and readable kept episodes. Usage: bash jobs/teach_smoke.sh <out>
OUT=$1
set -x
python -c "import torch, vllm, transformers; print('torch', torch.__version__, 'vllm', vllm.__version__, 'transformers', transformers.__version__)"
nvidia-smi --query-gpu=name,memory.total --format=csv
python build.py teach --scale ${SCALE:-0.025} --minutes ${MINUTES:-15} --concurrency 48 --out $OUT/teach --work work
python showcase.py $OUT/teach/teacher_results.jsonl.gz $OUT/TEACHER_EXAMPLES.md
python hub.py up kealjones/squiggle-ft-data ${TAG:-teach-smoke} $OUT/teach/train_examples.jsonl.gz $OUT/teach/teacher_results.jsonl.gz
pip install -q -U "transformers>=5,<6"     # vLLM 0.11 needed 4.x; LFM2.5's tokenizer needs 5.x
python selftest.py $OUT/teach/train_examples.jsonl.gz --tokenizers unsloth/gemma-3-270m-it,LiquidAI/LFM2.5-350M > $OUT/selftest.txt 2>&1; tail -12 $OUT/selftest.txt
