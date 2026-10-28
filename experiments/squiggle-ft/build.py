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
import argparse, collections, gzip, itertools, json, os, random, re, sys, time
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
# What the teacher runs at full size: the targets in teach.py (830 episodes), every trained family.
TARGET_PLAN = {"web_fact": 90, "web_compare": 70, "math": 70, "hermes_compute": 40, "hermes_need": 40, "repo_fact": 80,
               "repo_where": 70, "repo_two": 50, "recipe_repo": 40, "need_repo": 50, "memory_repo": 35, "past_chat": 40,
               "refs": 40, "chat": 50, "chat_after": 30, "bare_link": 35}
EVAL_PLAN = {"web_fact": 16, "web_compare": 16, "math": 16, "hermes_compute": 12, "hermes_need": 12, "repo_fact": 16,
             "repo_where": 16, "repo_two": 12, "recipe_repo": 12, "need_repo": 12, "memory_repo": 10, "past_chat": 12,
             "refs": 12, "chat": 16, "chat_after": 8, "bare_link": 12,
             "unknown_word": 16, "personal": 20,
             # v2 families (eval templates/words/requests, disjoint from training)
             "need_web": 12, "math_pair": 12, "lookup_then_compute": 10, "repo_chain": 10, "messy_multi": 10, "recipe_web": 10,
             "recipe_skip": 10, "near_miss": 10, "chat_mid": 10, "personal_mid": 10,
             # held out: never in training
             "web_bridge": 30, "need_math": 30, "recipe_compare": 24, "unknown_action": 16,
             "need_schedule": 12, "recipe_compute": 12}
# v2 (CORPUS_V2.md §4): new teacher episodes, attempted. Reused teach-v1 episodes come on top (re-checked with the v2
# checker, leak-filtered, repo families capped at 25 each: train.py --reuse-cap). Families marked TODO have no maker yet
# (make_sets skips them with a warning); counts are the plan the review asked for (thin cells >= 40).
V2_PLAN = {   # the trimmed plan (CORPUS_V2 §4): 815 new episodes attempted
    "web_fact": 100, "web_fact_retry": 40,
    "need_web": 50, "hermes_need": 40, "math_pair": 80,          # math_pair: 40 problems x (complete, one number missing)
    "recipe_web": 40,           # before lookup_then_compute: both draw "born first" pairs, and recipe_web is pickier
    "hermes_compute": 40, "lookup_then_compute": 40,          # + one retry each for a rejected compute episode
    "repo_chain": 20, "messy_multi": 20,                      # cut after the mini-smoke (0/3 each); low yield accepted
    "recipe_skip": 40,
    "unknown_word": 60, "near_miss": 50,
    "personal": 45, "personal_mid": 30, "personal_tool": 15, "chat_mid": 50,   # 75 personal requests, none used twice
}
# The teacher smoke before the v2 round: 3 attempted per family (51), to read keep rates and rejection reasons.
SMOKE_V2_PLAN = {k: 3 for k in V2_PLAN}
# After the smoke: only the families that kept 0 of 3, to see whether the fixes make them yield before the full run.
MINI_V2_PLAN = {k: 3 for k in ["chat_mid", "personal_mid", "hermes_compute", "lookup_then_compute", "math_pair", "messy_multi",
                               "near_miss", "repo_chain"]}
# The eval plan squiggle-ft-train used (293 episodes at seed 123): baselines on other bases are run on exactly this set.
EVAL_PLAN_V1 = {"web_fact": 16, "web_compare": 16, "math": 16, "hermes_compute": 12, "hermes_need": 12, "repo_fact": 16,
                "repo_where": 16, "repo_two": 12, "recipe_repo": 12, "need_repo": 12, "memory_repo": 10, "past_chat": 12,
                "refs": 12, "chat": 16, "chat_after": 8, "bare_link": 12,
                "web_bridge": 30, "need_math": 30, "recipe_compare": 24}
# The second data round: the families added after teach-v1 (made-up words, personal advice).
ROUND2_PLAN = {"unknown_word": 60, "personal": 70}


RETRY_FAMS = {"lookup_then_compute", "hermes_compute", "math_pair"}   # calculate is the point of v2: one retry each
V1_PLANS = {"train", "targets", "round2"}     # rebuilt exactly as they ran: no dedupe, no exclusions


BORN_MORE = HERE / "data" / "sources" / "born_more.json"          # cached so a job doesn't download 3,000 rows for ~30
EXCLUDE = HERE / "data" / "sources" / "exclude_keys.json"         # cached: rebuilding it downloads the eval sources


def born_more(work):
    if BORN_MORE.exists():
        return json.loads(BORN_MORE.read_text())
    rows = [r for r in S.hotpot(work, 3000, "validation", 2500) if r["type"] == "comparison" and F.BORN_FIRST.search(r["question"])]
    BORN_MORE.write_text(json.dumps(rows, ensure_ascii=False, indent=0))
    return rows


def exclude_keys(work):
    if EXCLUDE.exists():
        d = json.loads(EXCLUDE.read_text())
        print(f"excluded source questions: {d['note']} (cached in {EXCLUDE.name})", file=sys.stderr)
        return set(d["keys"])
    keys = compute_exclude_keys(work)
    return keys


def compute_exclude_keys(work):
    """Source questions a new training run may not use: every question of the eval sources, and the questions of
    teach-v1's kept episodes (they are reused in v2 training). teach-v1's sets are rebuilt (TARGET_PLAN, seed 0, no
    dedupe; every row-drawn episode's gold matches the stored one) to learn which row each episode used."""
    ev = load_sources(work, "eval")
    keys = {k for name in ("nq", "hotpot", "gsm", "compute", "need", "personal", "retry") for r in ev.get(name, []) for k in row_key(r)}
    n_eval = len(keys)
    p = HERE / "hf-teach-2" / "teach" / "teacher_results.jsonl.gz"
    n_v1 = 0
    if p.exists():
        kept = {r["id"]: r for r in map(json.loads, gzip.open(p, "rt")) if r["check"]["strict"]}
        for e in make_sets(load_sources(work, "train"), TARGET_PLAN, seed=0, dedupe=False):
            r = kept.get(e.id)
            if r is not None and e.meta.get("src") and json.dumps(r["gold"], sort_keys=True) == json.dumps(e.gold, sort_keys=True):
                keys.update(e.meta["src"])
                n_v1 += 1
    note = f"{n_eval} from the eval sources, those of {n_v1} kept teach-v1 episodes"
    print(f"excluded source questions: {note}", file=sys.stderr)
    EXCLUDE.write_text(json.dumps({"note": note, "keys": sorted(keys)}, ensure_ascii=False, indent=0))
    return keys


def episodes_for(args):
    plan = PLANS[args.plan]
    work = Path(args.work)
    if args.plan == "eval":
        return make_sets(load_sources(work, "eval"), plan, seed=args.seed, scale=args.scale)
    if args.plan in V1_PLANS:
        return make_sets(load_sources(work, "train"), plan, seed=args.seed, scale=args.scale, dedupe=False)
    return make_sets(load_sources(work, "train"), plan, seed=args.seed, scale=args.scale, exclude=exclude_keys(work))


def load_sources(work, split):
    """Disjoint slices for training and eval."""
    if split == "train":
        nq = S.nq_open(work, 1500, "validation", 0)
        hp = S.hotpot(work, 2500, "validation", 0)
        hp_more = born_more(work)       # hotpot rows 2500-5499: more "born first" pairs (eval starts at 6000)
        gsm = S.gsm8k(work, 800, "train", 0)
        repos = S.TRAIN_REPOS
    else:
        nq = S.nq_open(work, 600, "validation", 3000)
        hp = S.hotpot(work, 1400, "validation", 6000)
        hp_more = []
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
    return {"nq": nq, "hotpot": hp, "gsm": gsm, "facts": list(facts.values()), "keal": keal, "compute": compute, "need": need,
            "words": F.unknown_words(split), "personal": F.personal_rows(split), "split": split, "retry": F.retry_rows(split),
            "near": F.near_rows(split), "hotpot_more": hp_more, "repo_cache": str(Path(work) / "repo-cache")}


def row_key(row):
    """The source question a row is about, normalised: two episodes with the same key ask the same thing."""
    if isinstance(row, (tuple, list)):
        return [k for r in row for k in row_key(r)]
    if isinstance(row, str):
        return [F.norm(row)]
    if isinstance(row, dict):
        q = row.get("question") or row.get("request") or row.get("text")
        return [F.norm(q)] if q else []
    return []


REPEATS_OK = {"words", "near"}   # a made-up or near-miss word comes back in a different sentence on purpose


PLANS = {"train": TRAIN_PLAN, "targets": TARGET_PLAN, "round2": ROUND2_PLAN, "v2": V2_PLAN, "smoke_v2": SMOKE_V2_PLAN,
         "mini_v2": MINI_V2_PLAN, "eval": EVAL_PLAN}


def make_sets(src, plan, seed=0, scale=1.0, date_shift=True, exclude=(), dedupe=True):
    """exclude: source keys (row_key) no episode may use: questions of the eval sources and of reused teach-v1
    episodes. dedupe: no source question is used twice within the run, across families (math_pair's complete and
    incomplete twin share one on purpose). dedupe=False reproduces the sets of runs made before it existed."""
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
    r2 = random.Random(seed + 7919)     # a separate stream, so adding these pools left the v1 episode sets unchanged
    words = list(src.get("words", [])); r2.shuffle(words)
    personal = list(src.get("personal", [])); r2.shuffle(personal)
    pools["words"] = itertools.cycle(words) if words else iter(())       # a word can come back in another sentence
    pools["personal"] = iter(personal)
    # v2 pools (own random stream, after the v1 draws, so v1 episode sets don't move)
    r3 = random.Random(seed + 104729)
    split = src.get("split", "train")
    nq2 = list(nq); r3.shuffle(nq2)
    born = [r for r in comp if F.BORN_FIRST.search(r["question"])]; r3.shuffle(born)
    more = [r for r in src.get("hotpot_more", []) if r["type"] == "comparison" and F.BORN_FIRST.search(r["question"])]
    random.Random(seed + 15485863).shuffle(more)
    born += more            # after the original order, so the first draws are what they were
    retry = list(src.get("retry", [])); r3.shuffle(retry)
    near = list(src.get("near", [])); r3.shuffle(near)
    gsm2 = list(src["gsm"]); r3.shuffle(gsm2)
    pools.update({"nq2": itertools.cycle(nq2) if nq2 else iter(()), "born": itertools.cycle(born) if born else iter(()),
                  "retry": iter(retry), "near": itertools.cycle(near) if near else iter(()),
                  "personal2": itertools.cycle(personal) if personal else iter(()), "gsm2": iter(gsm2)})
    media = [r for r in nq2 if F.MEDIA.search(r["question"])]
    pools["media"] = itertools.cycle(media) if media else iter(())
    pair_state = {}

    def math_pair(i):
        if i % 2 == 0:
            pair_state["row"] = next(r for r in pools["gsm2"] if len(F.NUM_WORD.findall(r["question"])) >= 2)
        return F.make_math_pair(r3, pair_state["row"], i, incomplete=i % 2 == 1)
    # recipe_compare: two comparison questions of the same shape (same first two words)
    shape = collections.defaultdict(list)
    for r in comp[len(comp) // 2:]:
        shape[" ".join(r["question"].lower().split()[:2])].append(r)
    pairs = [(g[i], g[i + 1]) for g in shape.values() for i in range(0, len(g) - 1, 2)]
    rng.shuffle(pairs)
    pools["pairs"] = iter(pairs)

    split = src.get("split", "train")     # templated families draw eval-only templates, aliases and chat lines
    used, drawn, skipped = set(exclude), [], collections.Counter()
    # web_fact_retry's questions (teach-v1 questions whose first search missed) are kept for that family alone
    reserved = {k for r in src.get("retry", []) for k in row_key(r)} if dedupe else set()

    class Pools(dict):
        """pools[name] draws the next row whose source question hasn't been used (or excluded) yet."""
        def __getitem__(self, name):
            it = dict.__getitem__(self, name)
            return it if name in REPEATS_OK else Draw(it, name)

    class Draw:
        def __init__(self, it, name):
            self.it, self.name = it, name

        def __iter__(self):
            return self

        def __next__(self):
            for _ in range(20000):
                row = next(self.it)
                keys = row_key(row)
                if dedupe and keys and any(k in used or (k in reserved and self.name != "retry") for k in keys):
                    skipped[self.name] += 1
                    continue
                drawn.extend(keys)
                return row
            raise StopIteration

    pools = Pools(pools)
    makers = {
        "web_fact": lambda i: F.make_web_fact(rng, next(pools["nq"]), i),
        "chat_after": lambda i: F.make_chat_after(rng, next(pools["nq"]), i, split=split),
        "past_chat": lambda i: F.make_past_chat(rng, next(pools["nq"]), i),
        "web_compare": lambda i: F.make_web_compare(rng, next(pools["comp"]), i),
        "web_bridge": lambda i: F.make_web_bridge(rng, next(pools["bridge"]), i),
        "recipe_compare": lambda i: F.make_recipe_compare(rng, next(pools["pairs"]), i),
        "math": lambda i: F.make_math(rng, next(pools["gsm"]), i),
        "need_math": lambda i: F.make_need_math(rng, next(pools["gsm"]), i),
        "bare_link": lambda i: F.make_bare_link(rng, next(pools["titles"]), i),
        "repo_fact": lambda i: F.make_repo_fact(rng, facts, i),
        "repo_where": lambda i: F.make_repo_where(rng, facts, i, split=split),
        "repo_two": lambda i: F.make_repo_two(rng, facts, i),
        "recipe_repo": lambda i: F.make_recipe_repo(rng, facts, i),
        "need_repo": lambda i: F.make_need_repo(rng, facts, i, split=split),
        "memory_repo": lambda i: F.make_memory_repo(rng, mem_facts, i, split=split),
        "refs": lambda i: F.make_refs(rng, facts, i, split=split),
        "chat": lambda i: F.make_chat(rng, i, split=split),
        "hermes_compute": lambda i: hermes.make_compute(rng, next(pools["compute"]), i),
        "hermes_need": lambda i: hermes.make_need(rng, next(pools["need"]), i),
        "unknown_word": lambda i: F.make_unknown_word(rng, next(pools["words"]), i),
        "unknown_action": lambda i: F.make_unknown_action(rng, next(pools["words"]), i),
        "personal": lambda i: F.make_personal(rng, next(pools["personal"]), i),
        "web_fact_retry": lambda i: F.make_web_fact_retry(r3, next(pools["retry"]), i),
        "need_web": lambda i: F.make_need_web(r3, next(pools["nq2"]), i, split=split),
        "math_pair": math_pair,
        "lookup_then_compute": lambda i: F.make_lookup_then_compute(r3, next(pools["born"]), i, split=split),
        "repo_chain": lambda i: F.make_repo_chain(r3, facts, i, repo_cache=src.get("repo_cache"), split=split),
        "messy_multi": lambda i: F.make_messy_multi(r3, next(pools["nq2"]), facts, i, split=split),
        "recipe_web": lambda i: F.make_recipe_web(r3, next(pools["born"]), i),
        "recipe_skip": lambda i: F.make_recipe_skip(r3, facts, i),
        "near_miss": lambda i: F.make_near_miss(r3, next(pools["near"]), i, split=split),
        "chat_mid": lambda i: F.make_chat_mid(r3, next(pools["nq2"]), i, split=split),
        "personal_mid": lambda i: F.make_personal_mid(r3, next(pools["nq2"]), next(pools["personal2"]), i),
        "personal_tool": lambda i: F.make_personal_tool(r3, next(pools["media"]), i),
        "need_schedule": lambda i: F.make_need_schedule(r3, i),
        "recipe_compute": lambda i: F.make_recipe_compute(r3, next(pools["born"]), i),
    }
    eps = []
    for fam, n in plan.items():
        if fam not in makers:
            print(f"make_sets: no maker for {fam} yet, skipped ({n} planned)", file=sys.stderr)
            continue
        want = max(1, round(n * scale))
        got = tries = 0
        while got < want and tries < want * 5:
            tries += 1
            drawn.clear()
            try:
                e = makers[fam](got)
            except StopIteration:
                break
            if e is None:
                continue
            e.id = f"{fam}-{got}"
            if dedupe:
                used.update(drawn)
            if drawn or e.meta.get("src"):
                e.meta["src"] = list(dict.fromkeys(drawn)) or e.meta["src"]
            eps.append(e)
            got += 1
    if skipped:
        print(f"make_sets: skipped rows whose question was already used or excluded: {dict(skipped)}", file=sys.stderr)
    rng.shuffle(eps)
    if date_shift:      # each episode's "today" is a different day within two years of the real date (audit 7)
        for e in eps:
            e.meta["date_shift"] = random.Random(f"{seed}/{e.id}").randint(-730, 730)
    return eps


def compact(res, keep_calls):
    out = {k: res.get(k) for k in ("id", "family", "first", "gold", "meta", "error", "seconds", "check", "net", "source", "recipes")}
    out["turns"] = [{k: t.get(k) for k in ("n", "session", "reply", "tools", "waiting", "asked", "calls")} | {"task": _task(t.get("task"))} for t in res.get("turns", [])]
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
            if turn == 0 and res["family"] in F.LEAD_IN_FAMS:
                continue        # the lead-in lookup is context for the turn being taught, not trained itself
            yield {"messages": c["messages"], "output": c["output"], "family": res["family"], "kind": c["kind"], "episode": res["id"],
                   "turn": turn, "plain": F.plain_mode(res["family"], turn), "messy": res.get("meta", {}).get("messy", False), "repo": (res.get("meta") or {}).get("repo") or (res.get("gold") or {}).get("repo"),
                   **({"source": source} if source else {})}


class GzLines:
    """A .jsonl.gz written as one gzip member per flush (append mode): the file on disk is complete and readable after
    every flush, so the job's periodic upload, or a timeout, never leaves a truncated stream."""
    def __init__(self, path):
        self.path, self.buf = Path(path), []
        gzip.open(self.path, "wt").close()

    def write(self, line):
        self.buf.append(line)

    def flush(self):
        if self.buf:
            with gzip.open(self.path, "at") as f:
                f.write("".join(self.buf))
            self.buf = []


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


JUDGE_FAMS = {"web_compare", "recipe_compare", "lookup_then_compute", "recipe_web"}


def judge_turn(r):
    return 1 if r["family"] == "recipe_compare" else 0


def judge_options(r):
    """The candidates to ask the judge about, or None when the pick isn't ambiguous: an "A or B" gold (not yes/no) and a
    reply that names both candidates."""
    if r["family"] not in JUDGE_FAMS:
        return None
    gold = (r["gold"].get("second") or r["gold"]) if r["family"] == "recipe_compare" else r["gold"]
    titles = [re.sub(r"\s*\(.*?\)\s*", " ", t).strip() for t in (gold.get("titles") or [])]
    if len(titles) < 2 or str(gold.get("answer", "")).lower() in ("yes", "no"):
        return None
    rep = F.norm(F.reply_of(r, judge_turn(r)))
    named = [t for t in titles if F.first_mention(F.reply_of(r, judge_turn(r)), [t]) is not None]
    return titles if len(named) >= 2 and rep else None


def teach(args):
    from teacher import VLLMTeacher
    work = Path(args.work)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    eps = episodes_for(args)
    if args.shard:
        i, n = map(int, args.shard.split("/"))
        eps = eps[i::n]
    print(f"{len(eps)} episodes: {dict(collections.Counter(e.family for e in eps))}", flush=True)
    teacher = VLLMTeacher(args.teacher, max_tokens=args.max_tokens, max_seqs=max(64, args.concurrency), kv_fp8=args.kv_fp8)
    source = "teacher:" + args.teacher
    runner = Runner(teacher, args.squiggle, work, concurrency=args.concurrency, max_calls=40)
    runner.episode_timeout = args.episode_timeout
    t0 = time.time()
    results = []
    fres = GzLines(out / "teacher_results.jsonl.gz")
    fex = GzLines(out / "train_examples.jsonl.gz")
    fpend = GzLines(out / "judge_pending.jsonl.gz")     # kept A-or-B episodes waiting for the judge (a timeout keeps them)
    retried = collections.Counter()
    n_ex = 0
    deferred = []

    def done(r):
        nonlocal n_ex
        r["check"] = F.check(r)
        r["source"] = source
        results.append(r)
        keep = r["check"]["strict"]
        if keep and judge_options(r):
            deferred.append(r)               # written after the judge has read it (below)
            fpend.write(json.dumps(compact(r, True) | {"judge": "pending"}, ensure_ascii=False) + "\n")
            fpend.flush()
        else:
            fres.write(json.dumps(compact(r, True), ensure_ascii=False) + "\n")
            if keep:
                for x in examples(r, source):
                    fex.write(json.dumps(x, ensure_ascii=False) + "\n")
                    n_ex += 1
            fres.flush(); fex.flush()       # on disk after every episode: a job that times out keeps what it did
        if len(results) % 5 == 0:
            k = sum(x["check"]["strict"] for x in results)
            print(f"[{(time.time() - t0) / 60:.1f} min] {len(results)}/{len(eps)} episodes, kept {k}, examples {n_ex}, teacher {teacher.stats}", flush=True)
            report(results, out / "TEACHER_RESULTS.md", f"PARTIAL: {len(results)} of {len(eps)} episodes (retries included) after "
                   f"{(time.time() - t0) / 60:.0f} min ({len(deferred)} kept ones wait for the judge, in judge_pending.jsonl.gz).")
        # one retry from scratch for a rejected compute episode, with the broken rules restated (never an answer)
        if (not keep and r["family"] in RETRY_FAMS and not (r.get("meta") or {}).get("attempt")
                and "timed out" not in (r.get("error") or "")):
            import dataclasses
            from teacher import retry_hint
            ep = by_id[r["id"]]
            retried[r["family"]] += 1
            return dataclasses.replace(ep, id=ep.id + "r", meta={**ep.meta, "attempt": 2, "retry_hint": retry_hint(r["check"]["reasons"]),
                                                                 "retry_of": ep.id})
    by_id = {e.id: e for e in eps}
    runner.run(eps, on_result=done, deadline=t0 + args.minutes * 60)
    print(f"retried once: {dict(retried)}", flush=True)
    # The judge (same vLLM engine, already loaded): kept "A or B" episodes whose reply names more than one candidate.
    if deferred:
        import asyncio

        async def run_judge():
            return await asyncio.gather(*(teacher.judge(r["first"], F.reply_of(r, judge_turn(r)), judge_options(r)) for r in deferred))
        picks = asyncio.run(run_judge())
        dropped = 0
        for r, pick in zip(deferred, picks):
            gold = (r["gold"].get("second") or r["gold"]) if r["family"] == "recipe_compare" else r["gold"]
            ok = pick is not None and pick != "neither" and bool(F.same_entity(gold["answer"], [pick]) or F.norm(pick) in F.norm(gold["answer"]))
            r["check"]["judge"] = pick
            if not ok:
                r["check"]["strict"] = False
                r["check"]["reasons"].append(f"judge: the reply picks {pick!r}, not the gold")
                dropped += 1
            fres.write(json.dumps(compact(r, True), ensure_ascii=False) + "\n")
            if r["check"]["strict"]:
                for x in examples(r, source):
                    fex.write(json.dumps(x, ensure_ascii=False) + "\n")
                    n_ex += 1
        print(f"judge: {len(deferred)} ambiguous picks read, {dropped} dropped", flush=True)
    fres.flush(); fex.flush()
    mins = (time.time() - t0) / 60
    tps = teacher.stats["gen_tokens"] / max(1, mins * 60)
    report(results, out / "TEACHER_RESULTS.md",
           f"Teacher {args.teacher} on {os.environ.get('ACCELERATOR', 'local')}: {len(results)} of {len(eps)} episodes in {mins:.0f} min "
           f"(deadline {args.minutes} min), {n_ex} training examples, {tps:.0f} generated tokens/s. Teacher stats: {teacher.stats}.")
    print(open(out / "TEACHER_RESULTS.md").read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["teach", "sets"])
    ap.add_argument("--teacher", default=os.environ.get("TEACHER_MODEL", "Qwen/Qwen3-30B-A3B-Thinking-2507-FP8"))
    ap.add_argument("--plan", default="train", choices=sorted(PLANS))
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--minutes", type=float, default=120)
    ap.add_argument("--episode-timeout", type=float, default=float(os.environ.get("EPISODE_TIMEOUT", "1800")),
                    help="seconds before one episode is given up (recorded as 'episode timed out'); keeps a small job inside its cap")
    ap.add_argument("--concurrency", type=int, default=48)
    ap.add_argument("--max-tokens", type=int, default=8192)
    ap.add_argument("--shard", default="", help="i/n: run every n-th episode starting at i (split one run over several jobs)")
    ap.add_argument("--kv-fp8", type=int, default=int(os.environ.get("KV_FP8", "1")), help="fp8 KV cache (1 on L40S; 0 on A100, whose 80 GB has room for bf16)")
    ap.add_argument("--work", default=str(HERE / "work"))
    ap.add_argument("--out", default="out")
    ap.add_argument("--squiggle", default=os.environ.get("SQUIGGLE_DIR", str(HERE / "squiggle")))
    args = ap.parse_args()
    if args.cmd == "teach":
        teach(args)
    else:
        for e in episodes_for(args):
            print(json.dumps({"id": e.id, "family": e.family, "first": e.first, "gold": e.gold, "meta": e.meta}, ensure_ascii=False))


if __name__ == "__main__":
    main()
