"""Package a healed tiny-Gemma-4 checkpoint (heal.py's ckpt/: Gemma4TextModel + pruned tokenizer.json) as a
Gemma4ForCausalLM folder llama.cpp's converter accepts:
  - weights renamed with the "model." prefix (the lm_head is tied to the embeddings, so there is none)
  - config: architectures Gemma4ForCausalLM, model_type gemma4_text
  - tokenizer files rebuilt around the pruned tokenizer.json, with E2B-it's special tokens and chat template

    python to_gguf.py CKPT_DIR OUT_DIR [BASE_MODEL]
"""
import json, os, shutil, sys

ckpt, out = sys.argv[1], sys.argv[2]
base = sys.argv[3] if len(sys.argv) > 3 else "google/gemma-4-E2B-it"
os.makedirs(out, exist_ok=True)

from safetensors.torch import load_file, save_file
sd = load_file(os.path.join(ckpt, "model.safetensors"))
save_file({("model." + k if not k.startswith("model.") else k): v.contiguous() for k, v in sd.items()},
          os.path.join(out, "model.safetensors"), metadata={"format": "pt"})

cfg = json.load(open(os.path.join(ckpt, "config.json")))
cfg["architectures"] = ["Gemma4ForCausalLM"]
cfg["model_type"] = "gemma4_text"
cfg["tie_word_embeddings"] = True
json.dump(cfg, open(os.path.join(out, "config.json"), "w"), indent=1)

from transformers import AutoTokenizer, PreTrainedTokenizerFast
from tokenizers import Tokenizer
src = AutoTokenizer.from_pretrained(base)
t = PreTrainedTokenizerFast(tokenizer_object=Tokenizer.from_file(os.path.join(ckpt, "tokenizer.json")),
                            bos_token=src.bos_token, eos_token=src.eos_token, pad_token=src.pad_token, unk_token=src.unk_token)
t.chat_template = src.chat_template
t.save_pretrained(out)
for f in ("generation_config.json",):
    try:
        from huggingface_hub import hf_hub_download
        shutil.copy(hf_hub_download(base, f), os.path.join(out, f))
    except Exception:
        pass
print("packaged", out, {k: cfg.get(k) for k in ("hidden_size", "num_hidden_layers", "num_kv_shared_layers", "intermediate_size", "vocab_size")})
