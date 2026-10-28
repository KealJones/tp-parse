"""Model backends for sqrun.Runner.

  (the teacher lives in teacher.py)
  HFStudent     a small model as the phone runs it: its chat template, sampling like engine-wllama.js (temperature 0.7,
                top_k 64, top_p 0.95, llama.cpp-style repeat penalty 1.15 over the last 64 tokens), at most 1024 new
                tokens, and a 4096-token context that fails the call when it overflows (as wllama does).

Both check the prompt against the phone's 4096-token window in Gemma 3 tokens (CtxCheck), so no training prompt is
longer than the phone could take.
"""
import asyncio, re, uuid

PHONE_CTX = 4096
MAX_OUTPUT = 1024          # engine-wllama.js MAX_OUTPUT
GEMMA_TOKENIZER = "unsloth/gemma-3-270m-it"

class CtxCheck:
    """Prompt length in Gemma 3 tokens, as the phone's llama.cpp would count it."""
    def __init__(self, tokenizer=GEMMA_TOKENIZER):
        from transformers import AutoTokenizer
        self.tok = AutoTokenizer.from_pretrained(tokenizer)

    def tokens(self, messages):
        return len(self.tok.apply_chat_template(messages, tokenize=True, add_generation_prompt=True))


class LastNRepeatPenalty:
    """llama.cpp penalty_repeat: logits of tokens seen in the last n tokens are divided (positive) or multiplied
    (negative) by the penalty. wllama passes penalty_repeat 1.15 with llama.cpp's default last_n = 64."""
    def __init__(self, penalty=1.15, last_n=64):
        self.p, self.n = penalty, last_n

    def __call__(self, input_ids, scores):
        import torch
        recent = input_ids[:, -self.n:]
        s = torch.gather(scores, 1, recent)
        s = torch.where(s > 0, s / self.p, s * self.p)
        return scores.scatter(1, recent, s)


class HFStudent:
    """Batched generation with transformers, as the phone would sample."""
    def __init__(self, model_path, dtype="auto", device="cuda", greedy=False, ctx=PHONE_CTX, batch=48):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self.tok = AutoTokenizer.from_pretrained(model_path)
        self.tok.padding_side = "left"
        if self.tok.pad_token is None:
            self.tok.pad_token = self.tok.eos_token
        dt = {"auto": (torch.bfloat16 if torch.cuda.is_available() and torch.cuda.is_bf16_supported() else torch.float32), "fp32": torch.float32}[dtype]
        self.model = AutoModelForCausalLM.from_pretrained(model_path, dtype=dt).to(device).eval()
        self.device, self.greedy, self.ctx, self.batch = device, greedy, ctx, batch
        self.stats = {"calls": 0, "too_long": 0, "out_tokens": 0}
        ends = [self.tok.eos_token_id]
        for t in ("<end_of_turn>", "<|im_end|>", "<eos>"):
            i = self.tok.convert_tokens_to_ids(t)
            if isinstance(i, int) and i >= 0 and i != self.tok.unk_token_id:
                ends.append(i)
        self.ends = sorted(set(e for e in ends if e is not None))

    def _gen(self, reqs):
        import torch
        from transformers import LogitsProcessorList
        prompts = [self.tok.apply_chat_template(r["messages"], tokenize=False, add_generation_prompt=True) for r in reqs]
        out = [None] * len(reqs)
        todo = []
        for i, p in enumerate(prompts):
            n = len(self.tok(p, add_special_tokens=False).input_ids)
            room = min(MAX_OUTPUT, reqs[i].get("max_tokens") or MAX_OUTPUT, self.ctx - n)
            if room < 16:
                self.stats["too_long"] += 1
                out[i] = {"error": f"Prompt has too many tokens for the context ({n} of {self.ctx}): exceeds the window."}
            else:
                todo.append((i, p, room))
        todo.sort(key=lambda x: x[2])
        for k in range(0, len(todo), self.batch):
            part = todo[k:k + self.batch]
            enc = self.tok([p for _, p, _ in part], return_tensors="pt", padding=True, add_special_tokens=False).to(self.device)
            room = min(r for _, _, r in part)
            kw = dict(do_sample=not self.greedy, max_new_tokens=room, eos_token_id=self.ends, pad_token_id=self.tok.pad_token_id,
                      logits_processor=LogitsProcessorList([LastNRepeatPenalty()]))
            if not self.greedy:
                kw.update(temperature=0.7, top_k=64, top_p=0.95)
            with torch.no_grad():
                g = self.model.generate(**enc, **kw)
            for (i, _, _), row in zip(part, g[:, enc.input_ids.shape[1]:]):
                ids = [t for t in row.tolist() if t != self.tok.pad_token_id]
                cut = next((j for j, t in enumerate(ids) if t in self.ends), len(ids))
                self.stats["out_tokens"] += cut
                out[i] = {"text": self.tok.decode(ids[:cut], skip_special_tokens=False).replace("<end_of_turn>", "").strip()}
        self.stats["calls"] += len(reqs)
        return out

    async def generate(self, reqs):
        return await asyncio.to_thread(self._gen, reqs)
