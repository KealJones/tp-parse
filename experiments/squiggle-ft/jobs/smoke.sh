# Smoke test of the whole pipeline at toy scale (one l4x1 job): teacher episodes, self-test, train all three bases
# briefly, score them, and convert the best to GGUF (no upload). Usage (from jobs/boot.py): bash jobs/smoke.sh <out>
OUT=$1
set -x
python -c "import torch, vllm, transformers; print('torch', torch.__version__, 'vllm', vllm.__version__, 'transformers', transformers.__version__, 'cuda', torch.cuda.is_available())"
python build.py teach --scale 0.03 --minutes 10 --concurrency 32 --out $OUT/teach --work work
python showcase.py $OUT/teach/teacher_results.jsonl.gz $OUT/TEACHER_EXAMPLES.md
# vLLM 0.11 needs transformers 4.x; LFM2.5's tokenizer needs 5.x. The teacher is done, so upgrade now.
pip install -q -U "transformers>=5,<6"
python selftest.py samples/samples.jsonl --tokenizers unsloth/gemma-3-270m-it,unsloth/functiongemma-270m-it,LiquidAI/LFM2.5-350M > $OUT/selftest_samples.txt 2>&1; tail -5 $OUT/selftest_samples.txt
python selftest.py $OUT/teach/train_examples.jsonl.gz --tokenizers unsloth/gemma-3-270m-it,LiquidAI/LFM2.5-350M > $OUT/selftest_teacher.txt 2>&1; tail -8 $OUT/selftest_teacher.txt
python train.py --data $OUT/teach/train_examples.jsonl.gz,samples/samples.jsonl --bases gemma3,functiongemma,lfm25 --epochs 1 --limit 400 \
  --eval-scale 0.06 --eval-minutes 4 --out $OUT/train --work work --export --hub-repo ""
ls -la $OUT/train/gguf 2>/dev/null
rm -rf $OUT/train/gguf/*.gguf
