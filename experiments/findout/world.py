# %% [markdown]
# ## The world: made-up facts the model can't know, and tools to find them out
#
# Every episode gets a fresh random world (invented towns, creatures, items, people), so nothing can be
# memorised: the only way to answer is to look things up. Tools:
# - `<search>query</search>` returns sentences from the world's facts (with a distractor)
# - `<calc>expression</calc>` does arithmetic exactly
# - `<ask>question</ask>` goes to the person, who answers from what they know
# The model also keeps a working picture with `<fact key="k">v</fact>` and `<assume key="k">v</assume>`.
# When a fact replaces an assumption, the harness says which earlier searches rested on the old value.

# %%
import json, random, re

SYL = ["ba", "lo", "rin", "ta", "vor", "zel", "mi", "qua", "dun", "pel", "sor", "ky", "neth", "ul", "gra",
       "fen", "osh", "tir", "wex", "ja", "bri", "mok", "sel", "um", "dra", "vin", "ko", "ral", "esh", "thu"]


def name(r, n=None):
    return "".join(r.choice(SYL) for _ in range(n or r.choice((2, 3))))


COLORS = ["blue", "red", "green", "grey", "golden", "black", "white", "purple", "orange", "brown"]
FOODS = ["moss", "beetles", "seeds", "river fish", "berries", "leaves", "mushrooms", "worms", "fruit", "grass"]
HABITATS = ["marshes", "caves", "pine forests", "deserts", "lakes", "mountains", "meadows", "reefs"]
REGIONS = ["the north coast", "the eastern hills", "the south valley", "the western plains", "the high lakes", "the central basin"]
MATERIALS = ["oak", "copper", "glass", "wool", "clay", "steel", "bamboo", "leather"]
JOBS = ["baker", "teacher", "nurse", "carpenter", "pilot", "farmer", "librarian", "mechanic"]


def make_world(r):
    W = {"creature": {}, "town": {}, "item": {}, "person": {}}
    used = set()

    def name(r, n=None):            # unique, and no name contains another (so search can't confuse them)
        while True:
            x = "".join(r.choice(SYL) for _ in range(n or r.choice((2, 3))))
            if not any(x in u or u in x for u in used):
                used.add(x)
                return x
    for _ in range(4):
        W["creature"][name(r)] = {"legs": r.choice([2, 4, 6, 8, 10]), "color": r.choice(COLORS),
                                  "diet": r.choice(FOODS), "habitat": r.choice(HABITATS)}
    for _ in range(5):
        W["town"][name(r).capitalize()] = {"population": r.randrange(800, 99000), "region": r.choice(REGIONS),
                                           "founded": r.randrange(1650, 1990)}
    for _ in range(4):
        W["item"][name(r)] = {"price": r.randrange(3, 95), "material": r.choice(MATERIALS),
                              "weight": r.randrange(1, 40)}
    for _ in range(4):
        W["person"][name(r).capitalize()] = {"age": r.randrange(19, 88), "job": r.choice(JOBS)}
    return W


def fact_sentence(kind, ent, attr, val):
    if kind == "creature":
        return {"legs": f"A {ent} has {val} legs.", "color": f"The {ent} is {val}.",
                "diet": f"The {ent} eats {val}.", "habitat": f"The {ent} lives in {val}."}[attr]
    if kind == "town":
        return {"population": f"{ent} has a population of {val}.", "region": f"{ent} is in {val}.",
                "founded": f"{ent} was founded in {val}."}[attr]
    if kind == "item":
        return {"price": f"A {ent} costs {val} coins.", "material": f"A {ent} is made of {val}.",
                "weight": f"A {ent} weighs {val} grams."}[attr]
    return {"age": f"{ent} is {val} years old.", "job": f"{ent} works as a {val}."}[attr]


def search(W, query):
    """Return facts about every entity named in the query (requested attribute first), else no results."""
    q = query.lower()
    hits = []
    for kind, ents in W.items():
        for ent, attrs in ents.items():
            if re.search(r"\b" + re.escape(ent.lower()) + r"s?\b", q):
                order = sorted(attrs, key=lambda a: (a not in q and not any(s in q for s in SYN.get(a, ())), a))
                hits += [fact_sentence(kind, ent, a, attrs[a]) for a in order[:2]]
    return " ".join(hits) if hits else "no results"


SYN = {"diet": ("eat", "food"), "legs": ("leg",), "habitat": ("live", "where"), "population": ("people", "big", "size"),
       "region": ("where", "area"), "founded": ("old", "when"), "price": ("cost", "much"), "weight": ("heavy", "weigh"),
       "material": ("made",), "age": ("old",), "job": ("work", "do")}


def calc(expr):
    if not re.fullmatch(r"[\d\s+\-*/().<>=]+", expr):
        return "error: only numbers and + - * / ( ) < > allowed"
    try:
        v = eval(expr, {"__builtins__": {}})
    except Exception as e:
        return f"error: {type(e).__name__}"
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(int(v)) if float(v).is_integer() else f"{v:.2f}"


# %% [markdown]
# ## Tasks
#
# Each task builds a request, the person's hidden knowledge, a gold trajectory and a checker. `split`
# says where it's used: "train" types are trained on; "test" types are never seen in training (unfamiliar
# problems). Requests come in tidy and messy (spoken, lowercase, filler) styles; some messy phrasings are
# held out for testing.

# %%
MESSY_PRE = ["uhh ", "ok so ", "hey ", "so like ", "quick q ", "random but ", ""]
MESSY_POST = [" lol", " idk", "?", " thx", "", " if u know"]


def style(r, tidy, messy, split):
    if r.random() < 0.5:
        return tidy
    pre = r.choice(MESSY_PRE[:4] if split == "train" else MESSY_PRE[4:])
    return pre + messy + r.choice(MESSY_POST)


def S(kind, **kw):
    return dict(kind=kind, **kw)


def pick(r, W, kind):
    ent = r.choice(sorted(W[kind]))
    return ent, W[kind][ent]


def t_lookup(r, W, split):
    c, a = pick(r, W, "creature")
    attr = r.choice(["diet", "legs", "habitat", "color"])
    q = {"diet": ("What does a {c} eat?", "what do {c}s eat"), "legs": ("How many legs does a {c} have?", "how many legs does a {c} have"),
         "habitat": ("Where does the {c} live?", "where do {c}s live"), "color": ("What colour is a {c}?", "what color is a {c}")}[attr]
    req = style(r, q[0].format(c=c), q[1].format(c=c), split)
    val = a[attr]
    gold = [S("think", text=f"I don't know what a {c} is. Look it up."),
            S("search", text=f"{c} {attr}"),
            S("fact", key=f"{c}_{attr}", text=str(val)),
            S("answer", text=fact_sentence("creature", c, attr, val))]
    return dict(type="lookup", request=req, gold=gold, person={}, check=lambda ans, tr: str(val) in ans, needs_search=True)


def t_given(r, W, split):
    c, a = pick(r, W, "creature")
    attr = r.choice(["diet", "legs"])
    s = fact_sentence("creature", c, attr, a[attr])
    req = style(r, f"{s} So what does a {c} eat?" if attr == "diet" else f"{s} How many legs does a {c} have?",
                f"{s.lower()} so what does a {c} eat" if attr == "diet" else f"{s.lower()} how many legs does a {c} have", split)
    gold = [S("think", text="The answer is already in the message. No lookup needed."),
            S("answer", text=s)]
    return dict(type="given", request=req, gold=gold, person={}, check=lambda ans, tr: str(a[attr]) in ans, needs_search=False)


def t_calc(r, W, split):
    i, a = pick(r, W, "item")
    k = r.randrange(7, 99)
    known = r.random() < 0.5
    if known:
        req = style(r, f"A {i} costs {a['price']} coins. How much do {k} of them cost?", f"a {i} is {a['price']} coins, how much for {k}", split)
        gold = [S("think", text="Multiply exactly with the calculator.")]
    else:
        req = style(r, f"How much do {k} {i}s cost?", f"how much would {k} {i}s cost", split)
        gold = [S("think", text=f"I don't know the price of a {i}. Look it up, then multiply."),
                S("search", text=f"{i} price"), S("fact", key=f"{i}_price", text=str(a["price"]))]
    tot = a["price"] * k
    gold += [S("calc", text=f"{a['price']} * {k}"), S("answer", text=f"{k} {i}s cost {tot} coins.")]
    return dict(type="calc" if known else "lookup+calc", request=req, gold=gold, person={},
                check=lambda ans, tr: str(tot) in ans, needs_search=not known, needs_calc=True)


def t_compare(r, W, split):
    (t1, a1), (t2, a2) = [(t, W["town"][t]) for t in r.sample(sorted(W["town"]), 2)]
    req = style(r, f"Which is bigger, {t1} or {t2}?", f"is {t1.lower()} bigger than {t2.lower()}", split)
    big = t1 if a1["population"] > a2["population"] else t2
    gold = [S("think", text="I need both populations."),
            S("search", text=f"{t1} population"), S("fact", key=f"{t1}_population", text=str(a1["population"])),
            S("search", text=f"{t2} population"), S("fact", key=f"{t2}_population", text=str(a2["population"])),
            S("calc", text=f"{a1['population']} > {a2['population']}"),
            S("answer", text=f"{big} is bigger: {t1} has {a1['population']} people and {t2} has {a2['population']}.")]
    return dict(type="compare", request=req, gold=gold, person={}, check=lambda ans, tr: ans.strip().startswith(big) or f"{big} is bigger" in ans, needs_search=True)


def t_ask(r, W, split):
    t, a = pick(r, W, "town")
    req = style(r, "What region is my hometown in?", "what region is my hometown in", split)
    gold = [S("think", text="I don't know their hometown. Ask."),
            S("ask", text="Which town is your hometown?"),
            S("fact", key="hometown", text=t),
            S("search", text=f"{t} region"), S("fact", key=f"{t}_region", text=a["region"]),
            S("answer", text=f"{t} is in {a['region']}.")]
    return dict(type="ask", request=req, gold=gold, person={"town": t}, check=lambda ans, tr: a["region"] in ans,
                needs_search=True, needs_ask=True)


def t_stale(r, W, split):
    ta = r.choice(sorted(W["town"])); aa = W["town"][ta]
    others = [t for t in sorted(W["town"]) if W["town"][t]["region"] != aa["region"]]
    if not others:                      # every other town shares the region: move one
        others = [r.choice(sorted(set(W["town"]) - {ta}))]
        W["town"][others[0]]["region"] = r.choice([g for g in REGIONS if g != aa["region"]])
    tb = r.choice(others); ab = W["town"][tb]
    req = style(r, f"What region does my sister live in? I think she's in {ta}, but I'm not sure.",
                f"what region does my sister live in, i think shes in {ta.lower()} but not sure", split)
    gold = [S("assume", key="sister_town", text=ta),
            S("search", text=f"{ta} region"),
            S("reply_in", text=f"oh wait she moved to {tb} last year"),
            S("fact", key="sister_town", text=tb),
            S("harness_in"),
            S("think", text=f"The search for {ta} is stale now. Look up {tb}."),
            S("search", text=f"{tb} region"), S("fact", key=f"{tb}_region", text=ab["region"]),
            S("answer", text=f"She's in {tb}, which is in {ab['region']}.")]
    return dict(type="stale", request=req, gold=gold, person={"interrupt": f"oh wait she moved to {tb} last year"},
                check=lambda ans, tr: ab["region"] in ans and aa["region"] not in ans, needs_search=True)


def t_whose(r, W, split):
    (ta, aa), (tb, ab) = [(t, W["town"][t]) for t in r.sample(sorted(W["town"]), 2)]
    req = style(r, f"My brother lives in {ta} and I live in {tb}. How many people live in my brother's town?",
                f"my brother lives in {ta.lower()} and im in {tb.lower()}, how many people live in my brothers town", split)
    gold = [S("fact", key="brother_town", text=ta), S("fact", key="my_town", text=tb),
            S("search", text=f"{ta} population"), S("fact", key=f"{ta}_population", text=str(aa["population"])),
            S("check", text=f"The question is about the brother's town, {ta}, not {tb}."),
            S("answer", text=f"{ta}, your brother's town, has {aa['population']} people.")]
    return dict(type="whose", request=req, gold=gold, person={},
                check=lambda ans, tr: str(aa["population"]) in ans and str(ab["population"]) not in ans, needs_search=True)


# --- held-out task types (never trained on)
def u_cost_compare(r, W, split):
    (i1, a1), (i2, a2) = [(i, W["item"][i]) for i in r.sample(sorted(W["item"]), 2)]
    k1, k2 = r.randrange(3, 30), r.randrange(3, 30)
    c1, c2 = a1["price"] * k1, a2["price"] * k2
    while c1 == c2:
        k2 += 1; c2 = a2["price"] * k2
    more = f"{k1} {i1}s" if c1 > c2 else f"{k2} {i2}s"
    req = style(r, f"Do {k1} {i1}s cost more than {k2} {i2}s?", f"would {k1} {i1}s cost more than {k2} {i2}s", split)
    return dict(type="U:cost-compare", request=req, gold=[], person={},
                check=lambda ans, tr: (("yes" in ans.lower()[:12]) == (c1 > c2)) or more in ans, needs_search=True, needs_calc=True)


def u_three(r, W, split):
    ts = r.sample(sorted(W["town"]), 3)
    big = max(ts, key=lambda t: W["town"][t]["population"])
    req = style(r, f"Which is the biggest: {ts[0]}, {ts[1]} or {ts[2]}?", f"which is biggest out of {ts[0].lower()}, {ts[1].lower()} and {ts[2].lower()}", split)
    return dict(type="U:three-way", request=req, gold=[], person={}, check=lambda ans, tr: big in ans.split(".")[0], needs_search=True)


def u_person(r, W, split):
    p, a = pick(r, W, "person")
    req = style(r, f"How old is {p}?", f"how old is {p.lower()}", split)
    return dict(type="U:new-kind", request=req, gold=[], person={}, check=lambda ans, tr: str(a["age"]) in ans, needs_search=True)


TRAIN_TASKS = [t_lookup, t_given, t_calc, t_compare, t_ask, t_stale, t_whose]
TEST_ONLY = [u_cost_compare, u_three, u_person]


# %% [markdown]
# ## Rendering an episode as text, and the harness that runs a model's actions

# %%
SYSTEM = ("You figure things out. You know nothing about this world's towns, creatures, items or people, so look up what you need. "
          "Actions: <think>...</think> to reason; <search>query</search> to look something up; <calc>expression</calc> for arithmetic; "
          "<ask>question</ask> to ask the person; <fact key=\"k\">value</fact> to note something known; <assume key=\"k\">value</assume> to note "
          "a guess; <check>...</check> to check your answer against your notes; <answer>...</answer> to reply. "
          "If the answer is already in the message, just answer.")


class Harness:
    """Runs tools, keeps the working picture, and flags searches that rested on a replaced assumption."""
    def __init__(self, W, person):
        self.W, self.person, self.assumed, self.searches, self.log = W, person, {}, [], []
        self.interrupted = False

    def act(self, tag, attrs, body):
        """Return the observation text to insert after an action (or '' for none)."""
        self.log.append((tag, attrs, body))
        if tag == "search":
            self.searches.append(body)
            res = f"<result>{search(self.W, body)}</result>"
            if self.person.get("interrupt") and not self.interrupted:
                self.interrupted = True
                res += f"\n<reply>{self.person['interrupt']}</reply>"
            return res
        if tag == "calc":
            return f"<result>{calc(body)}</result>"
        if tag == "ask":
            t = self.person.get("town")
            return f"<reply>{t if t else 'not sure, sorry'}</reply>"
        if tag == "assume":
            self.assumed[attrs.get("key")] = body
            return ""
        if tag == "fact":
            k = attrs.get("key")
            old = self.assumed.pop(k, None)
            if old is not None and old != body:
                stale = [s for s in self.searches if old.lower() in s.lower()]
                return f"<harness>{k} changed: assumed {old}, now {body}. Rested on {old}: {', '.join(repr(s) for s in stale) or 'nothing'}.</harness>"
            return ""
        return ""


ACTION_RE = re.compile(r"<(think|search|calc|ask|fact|assume|check|answer)((?:\s+\w+=\"[^\"]*\")*)>(.*?)</\1>", re.S)
TOOL_ENDS = ("</search>", "</calc>", "</ask>", "</fact>", "</assume>", "</answer>")


def attrs_of(s):
    return dict(re.findall(r"(\w+)=\"([^\"]*)\"", s))


def render_gold(task, W):
    """Gold trajectory -> (text, mask) with observations produced by the real harness (so train and test match)."""
    H = Harness(W, task["person"])
    parts = []
    for st in task["gold"]:
        k = st["kind"]
        if k in ("reply_in", "harness_in"):
            continue                     # these arrive from the harness itself
        tag = f'<{k} key="{st["key"]}">{st["text"]}</{k}>' if k in ("fact", "assume") else f"<{k}>{st['text']}</{k}>"
        parts.append((tag, True))
        if k == "answer":
            break
        obs = H.act(k, {"key": st.get("key")} if "key" in st else {}, st["text"])
        parts.append(("\n" + obs + "\n" if obs else "\n", False))   # separators come from the harness, as in run_model
    return parts


def run_model(gen, task, W, max_steps=14, harness_on=True):
    """gen(prefix_text) -> next chunk ending at a closing tag. Returns (answer, harness)."""
    H = Harness(W, task["person"])
    text = ""
    for _ in range(max_steps):
        chunk = gen(text)
        if not chunk:
            break
        text += chunk
        m = list(ACTION_RE.finditer(chunk))
        if not m:
            break
        a = m[-1]
        tag, at, body = a.group(1), attrs_of(a.group(2)), a.group(3).strip()
        if tag == "answer":
            return body, H, text
        obs = H.act(tag, at, body)
        if obs.startswith("<harness>") and not harness_on:
            obs = ""
        text += "\n" + obs + "\n" if obs else "\n"
    return "", H, text


def score(task, answer, H):
    used = {t for t, _, _ in H.log}
    return {"type": task["type"], "ok": bool(answer) and bool(task["check"](answer, H)),
            "searched": "search" in used, "needs_search": task.get("needs_search", False),
            "calc": "calc" in used, "needs_calc": task.get("needs_calc", False),
            "asked": "ask" in used, "needs_ask": task.get("needs_ask", False), "steps": len(H.log)}


def make_split(seed, n, split, tasks):
    r = random.Random(seed)
    out = []
    for _ in range(n):
        W = make_world(r)
        out.append((r.choice(tasks)(r, W, split), W))
    return out
