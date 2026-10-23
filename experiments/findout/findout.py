# %% [markdown]
# # Finding out: can a small borrowed model learn to look things up instead of guessing?
#
# The "Finding Out" paper's bet: a capable assistant doesn't need to know much; it needs to know how to find out.
# Here a small pretrained model (SmolLM2-135M-Instruct) keeps its English, and we teach it only the loop:
# notice a gap, search, note what it found, calculate exactly, ask the person, catch stale assumptions, check, answer.
#
# Every episode happens in a freshly invented world (made-up towns, creatures, items, people), so nothing can be
# memorised: the only way to be right is to find out. Seven task types are trained on; three are held out entirely.
#
# **Conditions**
# - `base`: SmolLM2-135M-Instruct, untrained, with two worked examples in the prompt
# - `lora`: the same model with small LoRA adapters trained on the loop (the core weights stay frozen)
# - `full`: the whole model fine-tuned (to compare how much English each approach costs)
#
# **Measures** (the paper's tests): success; looking up when needed; *not* looking up when the answer was given
# (honest gaps both ways); exact arithmetic through the calculator; asking when information is missing; catching a
# stale assumption (with the harness's note switched on and off); unfamiliar task types never trained on; and
# English kept, measured as perplexity on held-out SimpleStories.
#
# **On Kaggle**: GPU T4, Internet on. About 1 to 1.5 hours. Results go to `FINDOUT_RESULTS.md`.

# %%
import json, math, os, random, re, statistics as st, sys, time, subprocess
QUICK = "--quick" in sys.argv or os.environ.get("FINDOUT_QUICK") == "1"
try:
    import peft  # noqa
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "peft"], check=False)
import torch
import torch.nn.functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer

DEV = "cuda" if torch.cuda.is_available() else "cpu"
MODEL = "HuggingFaceTB/SmolLM2-135M-Instruct"
N_TRAIN = 600 if QUICK else 24000
N_TEST = 4 if QUICK else 60          # per task type
EPOCHS = 1 if QUICK else 2
BATCH, MAXLEN = 16, 640
T0 = time.time()


def log(*a):
    print(f"[{(time.time() - T0) / 60:5.1f} min]", *a, flush=True)


# %%
# (world.py is inlined here by make_notebook.py)
from world import *  # noqa: E402,F401  -- replaced in the notebook

# %% [markdown]
# ## Data

# %%
tok = AutoTokenizer.from_pretrained(MODEL)
tok.padding_side = "left"
if tok.pad_token is None:
    tok.pad_token = tok.eos_token
END = "<|im_end|>"


def prompt_text(request, shots=()):
    msgs = [{"role": "system", "content": SYSTEM}]
    for q, a in shots:
        msgs += [{"role": "user", "content": q}, {"role": "assistant", "content": a}]
    msgs.append({"role": "user", "content": request})
    return tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)


def encode_episode(task, W):
    """Full text with a character mask (1 = the model's own actions), tokenised with offsets."""
    p = prompt_text(task["request"])
    text, mask = p, [0] * len(p)
    for piece, trained in render_gold(task, W):
        text += piece; mask += [int(trained)] * len(piece)
    text += END; mask += [1] * len(END)
    enc = tok(text, add_special_tokens=False, return_offsets_mapping=True, truncation=True, max_length=MAXLEN)
    lab = [i if mask[s] else -100 for i, (s, e) in zip(enc["input_ids"], enc["offset_mapping"])]
    return enc["input_ids"], lab


log("building data")
train = make_split(1, N_TRAIN, "train", TRAIN_TASKS)
train_enc = [encode_episode(t, W) for t, W in train]
lens = [len(i) for i, _ in train_enc]
log(f"{len(train_enc)} training episodes, mean {st.mean(lens):.0f} tokens, max {max(lens)}")

TESTS = {}
for i, f in enumerate(TRAIN_TASKS + TEST_ONLY):
    TESTS[f.__name__] = make_split(100 + i, N_TEST, "test", [f])

SHOTS = []
for f in (t_lookup, t_stale):                    # two worked examples for the untrained baseline
    t, W = make_split(7, 1, "train", [f])[0]
    SHOTS.append((t["request"], "".join(p for p, _ in render_gold(t, W))))

# %% [markdown]
# ## Training

# %%
def load(kind):
    m = AutoModelForCausalLM.from_pretrained(MODEL, torch_dtype=torch.float32).to(DEV)
    if kind == "lora":
        from peft import LoraConfig, get_peft_model
        m = get_peft_model(m, LoraConfig(r=32, lora_alpha=64, lora_dropout=0.05, task_type="CAUSAL_LM",
                                         target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]))
    return m


def collate(batch):
    L = max(len(i) for i, _ in batch)
    ids = torch.full((len(batch), L), tok.pad_token_id)
    lab = torch.full((len(batch), L), -100)
    att = torch.zeros((len(batch), L), dtype=torch.long)
    for b, (i, l) in enumerate(batch):
        ids[b, :len(i)] = torch.tensor(i); lab[b, :len(l)] = torch.tensor(l); att[b, :len(i)] = 1
    return ids.to(DEV), lab.to(DEV), att.to(DEV)


def train_model(kind):
    m = load(kind)
    lr = 2e-4 if kind == "lora" else 5e-5
    params = [p for p in m.parameters() if p.requires_grad]
    log(f"{kind}: training {sum(p.numel() for p in params)/1e6:.2f}M of {sum(p.numel() for p in m.parameters())/1e6:.1f}M parameters")
    opt = torch.optim.AdamW(params, lr=lr, weight_decay=0.0)
    try:
        scaler = torch.amp.GradScaler("cuda", enabled=DEV == "cuda")
    except (AttributeError, TypeError):
        scaler = torch.cuda.amp.GradScaler(enabled=DEV == "cuda")
    data = sorted(train_enc, key=lambda x: len(x[0]))           # length-bucketed batches, shuffled order
    batches = [data[i:i + BATCH] for i in range(0, len(data), BATCH)]
    total = EPOCHS * len(batches)
    step = 0
    m.train()
    for ep in range(EPOCHS):
        random.Random(ep).shuffle(batches)
        for b in batches:
            frac = step / total
            for g in opt.param_groups:
                g["lr"] = lr * min(1, (step + 1) / 50) * 0.5 * (1 + math.cos(math.pi * frac))
            ids, lab, att = collate(b)
            with torch.autocast(DEV, dtype=torch.float16, enabled=DEV == "cuda"):
                out = m(input_ids=ids, attention_mask=att)
            loss = F.cross_entropy(out.logits[:, :-1].float().reshape(-1, out.logits.shape[-1]), lab[:, 1:].reshape(-1), ignore_index=-100)
            opt.zero_grad(set_to_none=True)
            scaler.scale(loss).backward(); scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(params, 1.0)
            scaler.step(opt); scaler.update()
            step += 1
            if step % 200 == 0 or step == total:
                log(f"  {kind} step {step}/{total} loss {loss.item():.3f}")
    m.eval()
    return m


# %% [markdown]
# ## Running a model in the world (batched)

# %%
CLOSE = re.compile(r"</(think|search|calc|ask|fact|assume|check|answer)>")


@torch.no_grad()
def run_batch(m, items, shots=(), harness_on=True, max_steps=14, new_tokens=72):
    """items: [(task, W)]. Returns [(answer, Harness, text)] in the same order."""
    st_ = [{"task": t, "H": Harness(W, t["person"]), "text": "", "ans": None, "done": False,
            "prompt": prompt_text(t["request"], shots)} for t, W in items]
    for _ in range(max_steps):
        live = [s for s in st_ if not s["done"]]
        if not live:
            break
        for i in range(0, len(live), 32):
            chunk = live[i:i + 32]
            enc = tok([s["prompt"] + s["text"] for s in chunk], return_tensors="pt", padding=True, add_special_tokens=False).to(DEV)
            with torch.autocast(DEV, dtype=torch.float16, enabled=DEV == "cuda"):
                out = m.generate(**enc, max_new_tokens=new_tokens, do_sample=False, pad_token_id=tok.pad_token_id)
            for s, seq in zip(chunk, out[:, enc["input_ids"].shape[1]:]):
                gen = tok.decode(seq, skip_special_tokens=True)
                c = CLOSE.search(gen)
                if not c:
                    s["done"] = True; continue
                piece = gen[:c.end()]
                s["text"] += piece
                a = list(ACTION_RE.finditer(piece))
                if not a:
                    s["done"] = True; continue
                tag, at, body = a[-1].group(1), attrs_of(a[-1].group(2)), a[-1].group(3).strip()
                if tag == "answer":
                    s["ans"], s["done"] = body, True; continue
                obs = s["H"].act(tag, at, body)
                if obs.startswith("<harness>") and not harness_on:
                    obs = ""
                s["text"] += "\n" + obs + "\n" if obs else "\n"
    return [(s["ans"] or "", s["H"], s["text"]) for s in st_]


def evaluate(m, name, shots=(), harness_on=True, only=None):
    res = {}
    for tname, items in TESTS.items():
        if only and tname not in only:
            continue
        outs = run_batch(m, items, shots, harness_on)
        res[tname] = [score(t, a, H) for (t, _), (a, H, _) in zip(items, outs)]
        res[tname + "_example"] = outs[0][2][-600:]
        ok = st.mean(r["ok"] for r in res[tname])
        log(f"  {name:14} {tname:15} success {ok*100:5.1f}%")
    return res


# %% [markdown]
# ## English kept: perplexity on held-out simple stories

# %%
def load_english(n=300):
    try:
        from datasets import load_dataset
        ds = load_dataset("SimpleStories/SimpleStories", split="test", streaming=True)
        return [r["story"] for _, r in zip(range(n), ds)]
    except Exception as e:
        log(f"could not load SimpleStories ({e}); skipping the English check")
        return []


ENGLISH = load_english(20 if QUICK else 300)


@torch.no_grad()
def perplexity(m):
    if not ENGLISH:
        return None
    tot, cnt = 0.0, 0
    for i in range(0, len(ENGLISH), 16):
        enc = tok(ENGLISH[i:i + 16], return_tensors="pt", padding=True, truncation=True, max_length=256).to(DEV)
        lab = enc["input_ids"].masked_fill(enc["attention_mask"] == 0, -100)
        with torch.autocast(DEV, dtype=torch.float16, enabled=DEV == "cuda"):
            lg = m(**enc).logits
        l = F.cross_entropy(lg[:, :-1].float().reshape(-1, lg.shape[-1]), lab[:, 1:].reshape(-1), ignore_index=-100, reduction="sum")
        tot += l.item(); cnt += (lab[:, 1:] != -100).sum().item()
    return math.exp(tot / cnt)


# %% [markdown]
# ## Run everything

# %%
def summarise(R):
    pct = lambda v: "–" if v is None else f"{v*100:.0f}%"
    rows = ["| task | " + " | ".join(R) + " |", "|---" * (len(R) + 1) + "|"]
    names = [n for n in next(iter(R.values()))["eval"] if not n.endswith("_example")]
    for n in names:
        rows.append(f"| {n.replace('t_', '').replace('u_', 'unfamiliar: ')} | " + " | ".join(pct(st.mean(x['ok'] for x in R[c]['eval'][n])) for c in R) + " |")
    L = ["# Finding out: results", "", f"SmolLM2-135M-Instruct, {N_TRAIN} training episodes, {N_TEST} test episodes per task.", "",
         "## Success by task", ""] + rows + ["", "## The loop itself", "",
         "| measure | " + " | ".join(R) + " |", "|---" * (len(R) + 1) + "|"]

    def frac(c, names_, cond, val):
        xs = [x for n in names_ for x in R[c]["eval"].get(n, []) if cond(x)]
        return st.mean(val(x) for x in xs) if xs else None
    need = [n for n in names if n != "t_given"]
    L.append("| looked up when it needed to | " + " | ".join(pct(frac(c, need, lambda x: x["needs_search"], lambda x: x["searched"])) for c in R) + " |")
    L.append("| looked up when the answer was given (lower is better) | " + " | ".join(pct(frac(c, ["t_given"], lambda x: True, lambda x: x["searched"])) for c in R) + " |")
    L.append("| used the calculator for arithmetic | " + " | ".join(pct(frac(c, names, lambda x: x["needs_calc"], lambda x: x["calc"])) for c in R) + " |")
    L.append("| asked when information was missing | " + " | ".join(pct(frac(c, ["t_ask"], lambda x: True, lambda x: x["asked"])) for c in R) + " |")
    L.append("| English perplexity (lower is better) | " + " | ".join("–" if R[c]["ppl"] is None else f"{R[c]['ppl']:.1f}" for c in R) + " |")
    if any("stale_off" in R[c] for c in R):
        L += ["", "## Stale assumptions with the harness note switched off", ""]
        for c in R:
            if "stale_off" in R[c]:
                on = st.mean(x["ok"] for x in R[c]["eval"]["t_stale"]); off = st.mean(x["ok"] for x in R[c]["stale_off"]["t_stale"])
                L.append(f"- {c}: {on*100:.0f}% with the note, {off*100:.0f}% without")
    L += ["", "## One example per task (end of the trajectory, for the trained LoRA model)", ""]
    best = "lora" if "lora" in R else list(R)[-1]
    for n in names:
        L += [f"**{n}**", "```", R[best]["eval"][n + "_example"], "```", ""]
    return "\n".join(L) + "\n"


def main():
    R = {}
    base = load("base"); base.eval()
    log("evaluating base (2 worked examples in the prompt)")
    R["base"] = {"eval": evaluate(base, "base", shots=SHOTS), "ppl": perplexity(base)}
    del base; torch.cuda.empty_cache() if DEV == "cuda" else None
    for kind in ("lora", "full"):
        m = train_model(kind)
        log(f"evaluating {kind}")
        R[kind] = {"eval": evaluate(m, kind), "ppl": perplexity(m)}
        R[kind]["stale_off"] = evaluate(m, kind + " no-harness", harness_on=False, only=["t_stale"])
        if kind == "lora":
            os.makedirs("findout_lora", exist_ok=True)
            merged = m.merge_and_unload()
            merged.save_pretrained("findout_lora/merged"); tok.save_pretrained("findout_lora/merged")
            del merged
        del m; torch.cuda.empty_cache() if DEV == "cuda" else None
        json.dump({c: {k: v for k, v in R[c].items()} for c in R}, open("findout_results.json", "w"), indent=1, default=str)
    text = summarise(R)
    open("FINDOUT_RESULTS.md", "w").write(text)
    print(text)
    export_gguf()


def export_gguf():
    """Optional: convert the merged LoRA model to GGUF for Ollama with llama.cpp's converter."""
    try:
        if not os.path.exists("llama.cpp"):
            subprocess.run(["git", "clone", "-q", "--depth", "1", "https://github.com/ggml-org/llama.cpp"], check=True)
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "gguf"], check=False)
        r = subprocess.run([sys.executable, "llama.cpp/convert_hf_to_gguf.py", "findout_lora/merged", "--outtype", "f16",
                            "--outfile", "findout.gguf"], capture_output=True, text=True)
        log("gguf:", "ok" if r.returncode == 0 else r.stderr[-800:])
        open("Modelfile", "w").write("FROM ./findout.gguf\nPARAMETER temperature 0\nPARAMETER num_ctx 2048\nPARAMETER stop </search>\nPARAMETER stop </calc>\nPARAMETER stop </ask>\nPARAMETER stop </answer>\n")
    except Exception as e:
        log(f"gguf export skipped: {e}")


# %%
if __name__ == "__main__" or "ipykernel" in sys.modules:
    main()
