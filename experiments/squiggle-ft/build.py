"""Builds Squiggle fine-tune data: a teacher model plays the phone model inside Squiggle's real harness, with real tools,
on tasks made from real data; only episodes that pass the end-to-end checker (families.py, "strict") are kept, and every
model call in a kept episode becomes one training example (the exact prompt the phone model would get + the output).

  python build.py teach --teacher Qwen/Qwen3-30B-A3B-Thinking-2507-FP8 --plan train --out out [--scale 0.1] [--minutes 120]
  python build.py sets --plan eval                       # just write the episode list (no model)

Outputs (in --out):
  teacher_results.jsonl.gz   every episode: family, check result, replies, and (kept ones) every call
  train_examples.jsonl.gz    {"messages", "output", "family", "kind", "episode"} per model call of kept episodes
  TEACHER_RESULTS.md         keep rate per family, why episodes were dropped, cost/time
"""
import argparse, collections, gzip, json, os, random, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import families as F
import hermes
import sources as S
from sqrun import Runner

TRAIN_PLAN = {"web_fact": 200, "web_compare": 140, "math": 140, "hermes_compute": 90, "hermes_need": 70, "repo_fact": 150,
              "repo_where": 130, "repo_two": 70, "recipe_repo": 60, "need_repo": 80, "memory_repo": 50, "past_chat": 70,
              "refs": 70, "chat": 70, "chat_after": 40, "bare_link": 60}
EVAL_PLAN = {"web_fact": 16, "web_compare": 16, "math": 16, "hermes_compute": 12, "hermes_need": 12, "repo_fact": 16,
             "repo_where": 16, "repo_two": 12, "recipe_repo": 12, "need_repo": 12, "memory_repo": 10, "past_chat": 12,
             "refs": 12, "chat": 16, "chat_after": 8, "bare_link": 12,
             # held out: never in training
             "web_bridge": 30, "need_math": 30, "recipe_compare": 24}


def load_sources(work, split):
    """Disjoint slices for training and eval."""
    if split == "train":
        nq = S.nq_open(work, 1500, "validation", 0)
        hp = S.hotpot(work, 2500, "validation", 0)
        gsm = S.gsm8k(work, 800, "train", 0)
        repos = S.TRAIN_REPOS
    else:
        nq = S.nq_open(work, 600, "validation", 3000)
        hp = S.hotpot(work, 1400, "validation", 6000)
        gsm = S.gsm8k(work, 400, "test", 0)
        repos = S.EVAL_REPOS
    facts = S.repo_facts(work, repos)
    keal = S.repo_facts(work, ["KealJones/squiggle", "KealJones/tp-parse"])
    compute, need = hermes.select(S.hermes_rows(work), seed=7)
    cut_c, cut_n = int(len(compute) * 0.8), int(len(need) * 0.8)
    if split == "train":
        compute, need = compute[:cut_c], need[:cut_n]
    else:
        compute, need = compute[cut_c:], need[cut_n:]
    return {"nq": nq, "hotpot": hp, "gsm": gsm, "facts": list(facts.values()), "keal": keal, "compute": compute, "need": need}


def make_sets(src, plan, seed=0, scale=1.0):
    rng = random.Random(seed)
    nq = [r for r in src["nq"] if F.timeless(r["question"])]; rng.shuffle(nq)
    comp = [r for r in src["hotpot"] if r["type"] == "comparison"]
    bridge = [r for r in src["hotpot"] if r["type"] == "bridge"]
    rng.shuffle(comp); rng.shuffle(bridge)
    gsm = list(src["gsm"]); rng.shuffle(gsm)
    titles = sorted({t for r in src["hotpot"] for t in r["titles"]}); rng.shuffle(titles)
    facts = src["facts"]
    mem_facts = facts + [f for r, f in src["keal"].items() if r not in {x["repo"] for x in facts}]
    pools = {"nq": iter(nq), "comp": iter(comp), "bridge": iter(bridge), "gsm": iter(gsm), "titles": iter(titles),
             "compute": iter(src["compute"]), "need": iter(src["need"])}
    # recipe_compare: two comparison questions of the same shape (same first two words)
    shape = collections.defaultdict(list)
    for r in comp[len(comp) // 2:]:
        shape[" ".join(r["question"].lower().split()[:2])].append(r)
    pairs = [(g[i], g[i + 1]) for g in shape.values() for i in range(0, len(g) - 1, 2)]
    rng.shuffle(pairs)
    pools["pairs"] = iter(pairs)

    makers = {
        "web_fact": lambda i: F.make_web_fact(rng, next(pools["nq"]), i),
        "chat_after": lambda i: F.make_chat_after(rng, next(pools["nq"]), i),
        "past_chat": lambda i: F.make_past_chat(rng, next(pools["nq"]), i),
        "web_compare": lambda i: F.make_web_compare(rng, next(pools["comp"]), i),
        "web_bridge": lambda i: F.make_web_bridge(rng, next(pools["bridge"]), i),
        "recipe_compare": lambda i: F.make_recipe_compare(rng, next(pools["pairs"]), i),
        "math": lambda i: F.make_math(rng, next(pools["gsm"]), i),
        "need_math": lambda i: F.make_need_math(rng, next(pools["gsm"]), i),
        "bare_link": lambda i: F.make_bare_link(rng, next(pools["titles"]), i),
        "repo_fact": lambda i: F.make_repo_fact(rng, facts, i),
        "repo_where": lambda i: F.make_repo_where(rng, facts, i),
        "repo_two": lambda i: F.make_repo_two(rng, facts, i),
        "recipe_repo": lambda i: F.make_recipe_repo(rng, facts, i),
        "need_repo": lambda i: F.make_need_repo(rng, facts, i),
        "memory_repo": lambda i: F.make_memory_repo(rng, mem_facts, i),
        "refs": lambda i: F.make_refs(rng, facts, i),
        "chat": lambda i: F.make_chat(rng, i),
        "hermes_compute": lambda i: hermes.make_compute(rng, next(pools["compute"]), i),
        "hermes_need": lambda i: hermes.make_need(rng, next(pools["need"]), i),
    }
    eps = []
    for fam, n in plan.items():
        want = max(1, round(n * scale))
        got = tries = 0
        while got < want and tries < want * 5:
            tries += 1
            try:
                e = makers[fam](got)
            except StopIteration:
                break
            if e is None:
                continue
            e.id = f"{fam}-{got}"
            eps.append(e)
            got += 1
    rng.shuffle(eps)
    return eps


def compact(res, keep_calls):
    out = {k: res.get(k) for k in ("id", "family", "first", "gold", "meta", "error", "seconds", "check")}
    out["turns"] = [{k: t.get(k) for k in ("n", "session", "reply", "tools", "waiting", "calls")} | {"task": _task(t.get("task"))} for t in res.get("turns", [])]
    if keep_calls:
        out["calls"] = [{k: c.get(k) for k in ("kind", "messages", "output", "meta", "error")} for c in res.get("calls", [])]
    else:
        out["outputs"] = [{"kind": c.get("kind"), "output": c.get("output")} for c in res.get("calls", [])]
    return out


def _task(t):
    if not t:
        return None
    return {"goal": t.get("goal"), "steps": [{k: s.get(k) for k in ("text", "status", "result")} for s in t.get("steps", [])], "status": t.get("status")}


def examples(res, source=None):
    """One training example per model call: the prompt as the phone model gets it, and the output."""
    calls, k, turn_of = res.get("calls", []), 0, []
    for t in res.get("turns", []):
        turn_of += [k] * t.get("calls", 0)
        k += 1
    for i, c in enumerate(calls):
        if c.get("kind") in ("chat", "step", "final") and c.get("output") and not c.get("error"):
            turn = turn_of[i] if i < len(turn_of) else k
            yield {"messages": c["messages"], "output": c["output"], "family": res["family"], "kind": c["kind"], "episode": res["id"],
                   "turn": turn, "plain": (res["family"], turn) in F.PLAIN, "messy": res.get("meta", {}).get("messy", False),
                   **({"source": source} if source else {})}


def report(results, path, extra=""):
    by = collections.defaultdict(list)
    for r in results:
        by[r["family"]].append(r)
    lines = ["# Teacher episodes (squiggle-ft)", "", extra, "",
             "| family | habit | episodes | right answer | kept (strict) | examples |", "| --- | --- | --- | --- | --- | --- |"]
    tot = collections.Counter()
    why = collections.Counter()
    for fam in sorted(by):
        rs = by[fam]
        ok = sum(r["check"]["ok"] for r in rs)
        kept = [r for r in rs if r["check"]["strict"]]
        ex = sum(sum(1 for c in r.get("calls", []) if c.get("kind") in ("chat", "step", "final")) for r in kept)
        tot.update(n=len(rs), ok=ok, kept=len(kept), ex=ex)
        lines.append(f"| {fam} | {F.HABIT.get(fam, '')} | {len(rs)} | {ok} | {len(kept)} ({len(kept) / max(1, len(rs)):.0%}) | {ex} |")
        for r in rs:
            if not r["check"]["strict"]:
                for x in r["check"]["reasons"][:3]:
                    why[f"{fam}: {x[:90]}"] += 1
    lines.append(f"| **all** | | {tot['n']} | {tot['ok']} | {tot['kept']} ({tot['kept'] / max(1, tot['n']):.0%}) | {tot['ex']} |")
    lines += ["", "## Why episodes were dropped (top 40)", ""] + [f"- {n} × {k}" for k, n in why.most_common(40)]
    Path(path).write_text("\n".join(lines) + "\n")


def teach(args):
    from teacher import VLLMTeacher
    work = Path(args.work)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    plan = TRAIN_PLAN if args.plan == "train" else EVAL_PLAN
    src = load_sources(work, "train" if args.plan == "train" else "eval")
    eps = make_sets(src, plan, seed=args.seed, scale=args.scale)
    print(f"{len(eps)} episodes: {dict(collections.Counter(e.family for e in eps))}", flush=True)
    teacher = VLLMTeacher(args.teacher, max_tokens=args.max_tokens)
    source = "teacher:" + args.teacher
    runner = Runner(teacher, args.squiggle, work, concurrency=args.concurrency, max_calls=40)
    t0 = time.time()
    results = []
    fres = gzip.open(out / "teacher_results.jsonl.gz", "wt")
    fex = gzip.open(out / "train_examples.jsonl.gz", "wt")
    n_ex = 0

    def done(r):
        nonlocal n_ex
        r["check"] = F.check(r)
        r["source"] = source
        results.append(r)
        keep = r["check"]["strict"]
        fres.write(json.dumps(compact(r, True), ensure_ascii=False) + "\n")
        if keep:
            for x in examples(r, source):
                fex.write(json.dumps(x, ensure_ascii=False) + "\n")
                n_ex += 1
        if len(results) % 10 == 0:
            k = sum(x["check"]["strict"] for x in results)
            print(f"[{(time.time() - t0) / 60:.1f} min] {len(results)}/{len(eps)} episodes, kept {k}, examples {n_ex}, teacher {teacher.stats}", flush=True)
            fres.flush(); fex.flush()
    runner.run(eps, on_result=done, deadline=t0 + args.minutes * 60)
    fres.close(); fex.close()
    mins = (time.time() - t0) / 60
    tps = teacher.stats["gen_tokens"] / max(1, mins * 60)
    report(results, out / "TEACHER_RESULTS.md",
           f"Teacher {args.teacher} on {os.environ.get('ACCELERATOR', 'local')}: {len(results)} of {len(eps)} episodes in {mins:.0f} min "
           f"(deadline {args.minutes} min), {n_ex} training examples, {tps:.0f} generated tokens/s. Teacher stats: {teacher.stats}.")
    print(open(out / "TEACHER_RESULTS.md").read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["teach", "sets"])
    ap.add_argument("--teacher", default="Qwen/Qwen3-30B-A3B-Thinking-2507-FP8")
    ap.add_argument("--plan", default="train", choices=["train", "eval"])
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--minutes", type=float, default=120)
    ap.add_argument("--concurrency", type=int, default=48)
    ap.add_argument("--max-tokens", type=int, default=8192)
    ap.add_argument("--work", default=str(HERE / "work"))
    ap.add_argument("--out", default="out")
    ap.add_argument("--squiggle", default=os.environ.get("SQUIGGLE_DIR", str(HERE / "squiggle")))
    args = ap.parse_args()
    if args.cmd == "teach":
        teach(args)
    else:
        src = load_sources(Path(args.work), "train" if args.plan == "train" else "eval")
        eps = make_sets(src, TRAIN_PLAN if args.plan == "train" else EVAL_PLAN, seed=args.seed, scale=args.scale)
        for e in eps:
            print(json.dumps({"id": e.id, "family": e.family, "first": e.first, "gold": e.gold, "meta": e.meta}, ensure_ascii=False))


if __name__ == "__main__":
    main()
