# Small story models (about 17M parameters each)

- `simple-first.gguf`: toki pona first, then a bridge, then a small English budget
- `english.gguf`: the same small English budget only
- `ceiling.gguf`: lots of fresh English (an upper bound)

They write simple English stories (trained on SimpleStories). They are not chat models:
give them the start of a story and they continue it.

    ollama create simple-first -f Modelfile.simple-first
    ollama run simple-first "Once upon a time, a girl named Kim"

`tok.model` is the SentencePiece tokenizer, and `hf-*/` holds the same models in Hugging Face format.
