"""The phone runs the GGUF's chat template (wllama renders prompts with the template llama.cpp stored in the file);
training and eval render with the Hugging Face tokenizer's template. If they differ by a byte, the phone model sees
prompts it was never trained on. This compares them.

  python template_check.py unsloth/gemma-3-270m-it LiquidAI/LFM2.5-350M       # HF template vs what the converter writes
  python template_check.py --gguf model.gguf --hf <model dir or repo>         # HF template vs a converted file
"""
import sys


def hf_template(name_or_dir):
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(name_or_dir).chat_template


def converter_template(name_or_dir):
    """The template convert_hf_to_gguf.py will write: gguf-py's SpecialVocab reads it from the model folder."""
    from pathlib import Path
    from gguf import SpecialVocab
    d = name_or_dir
    if not Path(d).exists():
        from huggingface_hub import snapshot_download
        d = snapshot_download(name_or_dir, allow_patterns=["tokenizer*", "special_tokens_map.json", "chat_template*", "*.json"])
    return SpecialVocab(d, load_merges=False).chat_template


def gguf_template(path):
    from gguf import GGUFReader
    f = GGUFReader(path).fields.get("tokenizer.chat_template")
    if f is None:
        return None
    return bytes(f.parts[f.data[0]]).decode("utf-8")


def compare(a, b):
    if a == b:
        return "identical"
    if a is None or b is None:
        return "one side has no template"
    i = next((k for k in range(min(len(a), len(b))) if a[k] != b[k]), min(len(a), len(b)))
    return f"DIFFERENT at byte {i}: {a[max(0, i - 30):i + 30]!r} vs {b[max(0, i - 30):i + 30]!r}"


def main():
    args = sys.argv[1:]
    bad = 0
    if "--gguf" in args:
        g = args[args.index("--gguf") + 1]
        h = args[args.index("--hf") + 1]
        r = compare(hf_template(h), gguf_template(g))
        print(f"{g} vs {h}: {r}")
        bad += r != "identical"
    else:
        for name in args:
            r = compare(hf_template(name), converter_template(name))
            print(f"{name}: HF template vs converter template: {r}")
            bad += r != "identical"
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
