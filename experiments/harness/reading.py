"""Reading test: skip search. Give the model the right paragraph for each task (written by hand) and see if it can answer.

Two conditions, thinking on:
  gold   only the right paragraph
  mixed  the right paragraph plus two paragraphs from other tasks, shuffled (can it pick the relevant one?)

  python reading.py [--pilot]     writes out/traces.json, out/AUTO.md
"""
import json, random, re, time
import torch
import harness as H

CONFIGS = [("Qwen/Qwen3-0.6B", True), ("Qwen/Qwen3-1.7B", True)]
if H.PILOT:
    CONFIGS = CONFIGS[:1]

GOLD = {
    0: "To stop whatever is listening on a TCP port on macOS or Linux, find its process ID and kill it: `lsof -ti tcp:8080 | xargs kill` (add -9 if it won't exit). On Linux, `fuser -k 8080/tcp` does the same. `npx kill-port 8080` works anywhere Node is installed.",
    1: "`git reset --soft HEAD~1` moves the branch back one commit and leaves that commit's changes staged. `git reset HEAD~1` (the default, --mixed) keeps them as unstaged changes in the working tree. `git reset --hard HEAD~1` throws the changes away.",
    2: "Chinchilla (Hoffmann et al., DeepMind, 2022) found that for a fixed compute budget, model size and training tokens should grow in equal proportion: roughly 20 training tokens per parameter. Earlier large models such as Gopher (280B parameters) were undertrained. Chinchilla, at 70B parameters trained on 1.4T tokens with the same compute, beat Gopher and is far cheaper to run.",
    3: "Frontier training runs split the work across thousands to tens of thousands of GPUs at once, using data, tensor and pipeline parallelism. Llama 3 405B was trained on up to 16,384 H100 GPUs for about two months (roughly 31 million GPU-hours) on 15.6T tokens. On a single GPU the same run would take thousands of years.",
    4: "Training a small model far past the compute-optimal point keeps improving it, but with diminishing returns: loss approaches a floor set by the model's size. SmolLM2-360M was trained on 4T tokens and Qwen3-0.6B on about 36T. Past some point a small model's limited capacity means it can't store or use everything in the data, and gains plateau.",
    5: "Anthropic has not published the parameter count, architecture, training data size or training compute for Claude Opus 5.5, as with earlier Claude models. Any outside figures are estimates.",
    6: "Recurrent and memory-network models (RNNs, LSTMs, and memory designs such as Recurrent Entity Networks) were largely replaced by the Transformer (\"Attention Is All You Need\", 2017). Every Transformer layer has two parts: a self-attention block and an MLP (feed-forward) block. Current LLMs, including Qwen3, still use this attention + MLP design.",
    7: "Mixture of experts (MoE) splits a model's MLP layers into many expert sub-networks, and a router sends each token to a few of them. Other work keeps fully separate models: Branch-Train-Merge trains independent expert language models on different domains and combines or routes between them, and router systems send each query to one specialist model.",
    8: "To let a tool or agent use Kaggle, create an API token on kaggle.com under Settings > API > Create New Token. Kaggle gives you a kaggle.json file with your username and key. Put it at ~/.kaggle/kaggle.json, or set KAGGLE_USERNAME and KAGGLE_KEY as environment variables or secrets, and the Kaggle CLI/API can then run notebooks and download data for you.",
    9: "Cloudflare Workers are small serverless functions, written in JavaScript or TypeScript, that run on Cloudflare's edge network. A Worker receives HTTP requests and returns responses, so it can act as a proxy: fetch another site server-side and return the result with CORS headers added. The free plan allows 100,000 requests a day.",
    10: "fetch() can send requests to any site, but for a cross-origin request the browser only lets the page read the response if the server allows it with Access-Control-Allow-Origin headers (CORS). Same-origin requests and APIs that enable CORS work normally; most other sites don't send these headers, so the page can't read their responses.",
    11: "CORS is enforced by the browser for all page code, including WebAssembly, Web Workers and Service Workers, which make network requests through the same fetch machinery. Getting around it needs something outside the page: a server or serverless proxy (such as a Cloudflare Worker) that fetches for you, a browser extension with host permissions, or a desktop app.",
    12: "Anything the browser receives, including JavaScript, network requests and headers, can be seen by the user in DevTools. An API key embedded in front-end code or sent from the page is not secret. Keep the key on a server or proxy that makes the call and add your own auth or rate limits, or use a key restricted to harmless actions and specific domains.",
    13: "A model's file size is roughly its parameter count times bytes per parameter: 2 bytes at 16-bit, about 0.5 bytes at 4-bit. So 200-500 MB holds about 100-250M parameters at 16-bit, or about 400M-1B parameters at 4-bit. Small models like SmolLM2-360M and Qwen3-0.6B are in or near this range and run on phones and in browsers.",
    14: "Year-over-year gains in LLMs mostly come from outside the basic block design: better and more filtered training data, more training tokens, improved recipes (optimizers, learning-rate schedules, compute-optimal scaling), distillation from larger models, post-training (RLHF, reasoning RL), and small tweaks such as RMSNorm, SwiGLU, RoPE, grouped-query attention and mixture of experts.",
    15: "Cloud GPU providers for training include AWS, Google Cloud, Microsoft Azure, Lambda, RunPod, CoreWeave, Vast.ai, Nebius, Modal and Hugging Face (Jobs and Spaces). Free options include Kaggle and Google Colab.",
    16: "Wrangler gets the account ID from CLOUDFLARE_ACCOUNT_ID, from account_id in the wrangler config, or by looking up which accounts the API token can access. If the token can access only one account, the ID isn't needed. If it can access several, wrangler can't choose, and a non-interactive CI deploy fails unless the ID is set.",
    17: "A voice-dictated or transcribed message reaches a chat assistant as plain text, with no flag saying it was spoken. The assistant can only guess from style: filler words (um, uh), run-on sentences, missing punctuation, and words the transcriber misheard.",
}
SYSTEM = ("You are a helpful assistant. Reference text is attached to the message; use whatever in it is relevant and ignore "
          "the rest. The person's message may be messy, misspelled, rambling or spoken. Reply with a short, direct answer.")


def prompt(t, cond):
    rng = random.Random(t["id"])
    if cond == "gold":
        ref = GOLD[t["id"]]
    else:
        others = rng.sample([k for k in GOLD if k != t["id"]], 2)
        ps = [GOLD[t["id"]]] + [GOLD[k] for k in others]
        rng.shuffle(ps)
        ref = "\n\n".join(f"[{i+1}] {p}" for i, p in enumerate(ps))
    body = (f"Context: {t['ctx']}\n\n" if t["ctx"] else "") + f"Reference:\n{ref}\n\nMessage: {t['msg']}"
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": body}]


def main():
    t0, out = time.time(), []
    for name, think in CONFIGS:
        r = H.Runner(name, think)
        for cond in ("gold", "mixed"):
            outs = r.reply([prompt(t, cond) for t in H.TASKS], 1536)
            for t, o in zip(H.TASKS, outs):
                ans = o.split("</think>")[-1].strip()
                out.append({"id": t["id"], "model": name, "cond": cond, "msg": t["msg"], "answer": ans,
                            "auto_pass": all(re.search(p, ans, re.I | re.S) for p in t["auto"]) and not any(re.search(p, ans, re.I) for p in t["fail_if"])})
            rows = [o for o in out if o["model"] == name and o["cond"] == cond]
            print(f"{name} {cond}: auto {sum(o['auto_pass'] for o in rows)}/{len(rows)} ({time.time()-t0:.0f}s)", flush=True)
        del r; torch.cuda.empty_cache()
        json.dump(out, open("out/traces.json", "w"), indent=1, ensure_ascii=False)
    L = ["# Reading test (gold paragraph given, thinking on): auto check (first pass; Claude grades by hand)", ""]
    for name, _ in CONFIGS:
        for cond in ("gold", "mixed"):
            rows = [o for o in out if o["model"] == name and o["cond"] == cond]
            L.append(f"- {name}, {cond}: {sum(o['auto_pass'] for o in rows)}/{len(rows)}")
    open("out/AUTO.md", "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
