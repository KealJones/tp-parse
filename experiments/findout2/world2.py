# %% [markdown]
# ## World v2: multi-step tasks built from parts, with held-out combinations
#
# Every episode gets a fresh invented world (towns, items, people, creatures), so the only way to be right is to
# find out. Tools: `search(query)`, `calculator(expression)`, `ask_person(question)`. Tasks are small plans built
# from the same parts (look up, use what's given, ask, calculate, compare, follow a link). The test set holds out
# five combinations of trained parts that never appear together in training, so we can see whether the model
# composes a new plan or snaps to the nearest one it knows.
#
# Episodes are stored model-neutrally as chat messages with tool calls; each model's renderer turns them into its
# own chat format.

# %%
import ast, json, random, re, zlib

SYL = ["ba", "lo", "rin", "ta", "vor", "zel", "mi", "qua", "dun", "pel", "sor", "ky", "neth", "ul", "gra",
       "fen", "osh", "tir", "wex", "ja", "bri", "mok", "sel", "um", "dra", "vin", "ko", "ral", "esh", "thu"]
COLORS = ["blue", "red", "green", "grey", "golden", "black", "white", "purple", "orange", "brown"]
FOODS = ["moss", "beetles", "seeds", "river fish", "berries", "leaves", "mushrooms", "worms", "fruit", "grass"]
HABITATS = ["marshes", "caves", "pine forests", "deserts", "lakes", "mountains", "meadows", "reefs"]
REGIONS = ["the north coast", "the eastern hills", "the south valley", "the western plains", "the high lakes", "the central basin"]
MATERIALS = ["oak", "copper", "glass", "wool", "clay", "steel", "bamboo", "leather"]
JOBS = ["baker", "teacher", "nurse", "carpenter", "pilot", "farmer", "librarian", "mechanic"]


def make_world(r):
    W = {"creature": {}, "town": {}, "item": {}, "person": {}}
    used = set()

    def nm(n=None):                  # unique, and no name contains another, so search can't confuse them
        while True:
            x = "".join(r.choice(SYL) for _ in range(n or r.choice((2, 3))))
            if len(x) >= 4 and not any(x in u or u in x for u in used):
                used.add(x)
                return x
    for _ in range(4):
        W["creature"][nm()] = {"legs": r.choice([2, 4, 6, 8, 10]), "color": r.choice(COLORS),
                               "diet": r.choice(FOODS), "habitat": r.choice(HABITATS)}
    pops = r.sample(range(800, 99000), 6)                      # distinct, so "bigger" always has one answer
    for p in pops:
        W["town"][nm().capitalize()] = {"population": p, "region": r.choice(REGIONS), "founded": r.randrange(1650, 1990)}
    towns = sorted(W["town"])
    for pr, wt in zip(r.sample(range(3, 95), 6), r.sample(range(1, 40), 6)):
        W["item"][nm()] = {"price": pr, "weight": wt, "material": r.choice(MATERIALS)}
    for age in r.sample(range(19, 88), 6):
        W["person"][nm().capitalize()] = {"age": age, "job": r.choice(JOBS), "home": r.choice(towns)}
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
                "weight": f"A {ent} weighs {val} kg."}[attr]
    return {"age": f"{ent} is {val} years old.", "job": f"{ent} works as a {val}.", "home": f"{ent} lives in {val}."}[attr]


SYN = {"color": r"\bcolou?r", "diet": r"\beat|\bfood|\bdiet", "legs": r"\blegs?\b", "habitat": r"\bhabitat|\bwhere\b",
       "population": r"\bpeople|\bbig|\bsize|\bpopulat", "region": r"\bwhere\b|\barea|\bregion",
       "founded": r"\bwhen\b|\bfound|\bold\b", "price": r"\bcost|\bmuch\b|\bprice|\bexpensive", "weight": r"\bheav|\bweigh",
       "material": r"\bmade\b|\bmaterial", "age": r"\bold|\bage\b", "job": r"\bwork|\bjob|\bdo\b", "home": r"\blive|\bhome|\btown"}


def kind_of(W, ent):
    for k, ents in W.items():
        if ent in ents:
            return k


def search(W, query):
    """Facts about every entity named in the query: the asked-for attribute first, then one more, plus one
    same-attribute fact about a different entity (a distractor the model has to ignore)."""
    q = query.lower().replace("_", " ")
    hits, named_ents = [], []
    for kind, ents in W.items():
        for ent, attrs in ents.items():
            if re.search(r"\b" + re.escape(ent.lower()) + r"(s|'s)?\b", q):
                named_ents.append(ent)
                asked = sorted((a for a in attrs if re.search(SYN[a], q)), key=lambda a: -len(re.findall(SYN[a], q)) - (2 if re.search(r"\b" + a, q) else 0))
                rest = sorted((a for a in attrs if a not in asked), key=lambda a: zlib.crc32(f"{ent}|{a}".encode()))
                order = (asked[:1] + rest)[:2]
                hits += [fact_sentence(kind, ent, a, attrs[a]) for a in order]
                others = sorted(e for e in ents if e != ent)
                if others:
                    o = others[zlib.crc32(f"{ent}|{q}".encode()) % len(others)]
                    a0 = order[0]
                    hits.append(fact_sentence(kind, o, a0, ents[o][a0]))
    if not hits:
        return "No results."
    seen, out = set(), []
    for h in hits:                                   # drop duplicates, keep a stable shuffle
        if h not in seen:
            seen.add(h); out.append(h)
    named = [h for h in out if any(e in h for e in named_ents)]
    return " ".join(sorted(out, key=lambda h: zlib.crc32(h.encode()) if h not in named[:1] else -1))


def calc(expr):
    e = expr.strip()
    if len(e) > 120 or "**" in e or not re.fullmatch(r"(?:[\d\s+\-*/().,<>=]|max|min)+", e):
        return "error: use numbers with + - * / ( ) < > and max(...) or min(...)"
    try:
        v = eval(e, {"__builtins__": {}}, {"max": max, "min": min})
        if isinstance(v, bool):
            return "true" if v else "false"
        return str(int(v)) if float(v).is_integer() else f"{v:.2f}"
    except Exception as ex:
        return f"error: {type(ex).__name__}"


TOOLS = [
    {"type": "function", "function": {"name": "search", "description": "Look something up. Returns a few short facts.",
     "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "what to look up"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "calculator", "description": "Exact arithmetic: numbers with + - * / ( ), < > to compare, max(...) and min(...).",
     "parameters": {"type": "object", "properties": {"expression": {"type": "string"}}, "required": ["expression"]}}},
    {"type": "function", "function": {"name": "ask_person", "description": "Ask the person something only they know.",
     "parameters": {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]}}},
]

SYSTEM = ("You figure things out for the person. You know nothing about this world's towns, items, people or creatures, "
          "so look up every fact you need with search; never guess one. Use the calculator for all arithmetic and comparisons. "
          "Ask the person only for things only they know. If the message already gives a fact, use it without searching. "
          "Start by listing what you need, then get each piece with one tool call at a time. "
          "Finish with a short reply whose last line is 'Answer: <short answer>'.")


def person_reply(person, question):
    q = question.lower()
    if person.get("town") and re.search(r"town|live|city|where|home", q):
        return person["town_reply"]
    return "not sure what you mean"


# %% [markdown]
# ### Messy requests, in Keal's style
# Restarts and self-corrections hurt models most (VocalBench-DF), so those are in the mix, not just typos and "lol".

# %%
PRE = ["ok so ", "hey ", "quick q ", "so like ", "um ", "ok wait ", "random but ", "hey so ", ""]
CHAT = ["im trying to figure something out and ", "my friend keeps asking me this so ", "ok this is gonna sound dumb but ",
        "so i was looking at stuff earlier and ", ""]
POST = [" lol", " idk", " thx", " ??", " if u know", "", " lmao", " haha"]


def messy(r, text, swaps):
    """swaps: list of (right, wrong) pairs that can be used for a false start that gets corrected."""
    s = text.rstrip("?.!")
    if swaps and r.random() < 0.4:                    # false start, then the correction
        right, wrong = r.choice(swaps)
        fix = r.choice([" no wait ", "- no sorry ", " i mean ", " wait no ", ", no, "])
        s = re.sub(r"\b" + re.escape(right) + r"\b", lambda m: wrong + fix + right, s, count=1)
    if r.random() < 0.3:                              # a repeated word or two
        w = s.split()
        if len(w) > 3:
            i = r.randrange(0, len(w) - 2); n = r.choice((1, 2))
            w = w[:i + n] + w[i:i + n] + w[i + n:]
            s = " ".join(w)
    s = s.lower() if r.random() < 0.8 else s
    s = re.sub(r"[,']", "", s) if r.random() < 0.6 else s
    s = s.replace("what is", "whats").replace("how much is", "how much is").replace("do you", "do u").replace(" you ", " u ")
    return (r.choice(CHAT) if r.random() < 0.3 else "") + r.choice(PRE) + s + r.choice(POST)


# %% [markdown]
# ### Tasks
# Each task: a request, the person's private knowledge, the gold plan (needs list + tool steps), the short answer
# and a checker. `parts` names the building blocks, so held-out tasks are provably new combinations of trained parts.

# %%
def plural(x):
    return x + ("es" if x.endswith(("s", "sh", "ch", "x")) else "s")


ATTR_Q = {  # attribute -> (question about one entity, short label, unit)
    ("town", "population"): ("How many people live in {e}?", "the population of {e}", ""),
    ("town", "region"): ("What region is {e} in?", "the region {e} is in", None),
    ("town", "founded"): ("When was {e} founded?", "when {e} was founded", ""),
    ("item", "price"): ("How much does a {e} cost?", "the price of a {e}", " coins"),
    ("item", "weight"): ("How heavy is a {e}?", "the weight of a {e}", " kg"),
    ("item", "material"): ("What is a {e} made of?", "what a {e} is made of", None),
    ("person", "age"): ("How old is {e}?", "{e}'s age", ""),
    ("person", "job"): ("What does {e} do for work?", "{e}'s job", None),
    ("creature", "diet"): ("What does a {e} eat?", "what a {e} eats", None),
    ("creature", "legs"): ("How many legs does a {e} have?", "how many legs a {e} has", ""),
    ("creature", "habitat"): ("Where does the {e} live?", "where the {e} lives", None),
}
CMP = {  # (kind, attr) -> (which-question, comparative word, superlative word)
    ("town", "population"): ("Which is bigger, {a} or {b}?", "bigger", "biggest"),
    ("person", "age"): ("Who is older, {a} or {b}?", "older", "oldest"),
    ("item", "weight"): ("Which is heavier, a {a} or a {b}?", "heavier", "heaviest"),
    ("item", "price"): ("Which costs more, a {a} or a {b}?", "more expensive", "most expensive"),
    ("creature", "legs"): ("Which has more legs, a {a} or a {b}?", "has more legs", "has the most legs"),
}


def short_val(kind, attr, v):
    unit = ATTR_Q[(kind, attr)][2]
    return f"{v}{unit}" if unit is not None else str(v)


def query_for(kind, ent, attr):
    return {"population": f"{ent} population", "region": f"{ent} region", "founded": f"{ent} founded",
            "price": f"{ent} price", "weight": f"{ent} weight", "material": f"{ent} material", "age": f"{ent} age",
            "job": f"{ent} job", "diet": f"{ent} diet", "legs": f"{ent} legs", "habitat": f"{ent} habitat",
            "home": f"where does {ent} live"}[attr]


def numbers_in(s):
    return [int(x.replace(",", "")) for x in re.findall(r"\d[\d,]*", s)]


def short_answer(text):
    m = list(re.finditer(r"answer\s*:\s*(.+)", text, re.I))
    return (m[-1].group(1).strip(), True) if m else (text.strip(), False)


def chk_number(n):
    return lambda a: n in numbers_in(a)


def _norm(s):
    return re.sub(r"\bthe\s+", "", s.lower()).strip()


def chk_text(v):
    return lambda a: _norm(v) in _norm(a)


def chk_name(win, losers):
    return lambda a: win.lower() in a.lower() and not any(l.lower() in a.lower() for l in losers)


class Task(dict):
    pass


def T(**kw):
    t = Task(kw); t.setdefault("person", {}); t.setdefault("given", []); t.setdefault("swaps", [])
    return t


# --- the steps the gold plan is made of: ("search", kind, ent, attr) | ("ask", question, slot) | ("calc", expr, label)
def t_lookup(r, W):
    kind, attr = r.choice(sorted(ATTR_Q))
    e = r.choice(sorted(W[kind])); v = W[kind][e][attr]
    others = [x for x in sorted(W[kind]) if x != e]
    return T(type="lookup", parts=["search"], request=ATTR_Q[(kind, attr)][0].format(e=e),
             needs=[("search", kind, e, attr)], short=short_val(kind, attr, v),
             check=chk_number(v) if isinstance(v, int) else chk_text(v), swaps=[(e, r.choice(others))])


def t_given(r, W):
    if r.random() < 0.5:                      # the fact is in the message: just answer
        kind, attr = r.choice([k for k in sorted(ATTR_Q) if k[1] != "material"])
        e = r.choice(sorted(W[kind])); v = W[kind][e][attr]
        f = fact_sentence(kind, e, attr, v)
        fl = f[0].lower() + f[1:] if f.startswith(("A ", "The ")) else f
        lead = r.choice([f"My friend told me {fl}", f"I read that {fl}", f"Apparently {fl}", f])
        return T(type="given", parts=["given"], request=f"{lead} {ATTR_Q[(kind, attr)][0].format(e=e)}",
                 needs=[], given=[(kind, e, attr)], short=short_val(kind, attr, v),
                 check=chk_number(v) if isinstance(v, int) else chk_text(v))
    i = r.choice(sorted(W["item"])); p = W["item"][i]["price"]; k = r.randrange(2, 16)
    lead = r.choice(["A {i} costs {p} coins.", "The shop says a {i} is {p} coins.", "{I}s are {p} coins each."]).format(i=i, I=i.capitalize(), p=p)
    return T(type="given", parts=["given", "calc"], request=f"{lead} How much would {k} of them cost?",
             needs=[("calc", f"{k} * {p}", f"{k} × the price")], given=[("item", i, "price")],
             short=f"{k * p} coins", check=chk_number(k * p), swaps=[(str(k), str(k + r.choice((1, 2, 3))))])


def t_total(r, W):
    i = r.choice(sorted(W["item"])); p = W["item"][i]["price"]; k = r.randrange(2, 16)
    req = r.choice(["How much do {k} {ii} cost?", "What would {k} {ii} cost me?", "How much for {k} {ii}?"]).format(k=k, ii=plural(i))
    return T(type="total", parts=["search", "calc"], request=req,
             needs=[("search", "item", i, "price"), ("calc", f"{k} * {p}", f"{k} × the price")],
             short=f"{k * p} coins", check=chk_number(k * p), swaps=[(str(k), str(k + r.choice((1, 2, 3))))])


def basket(r, W, n, typ):
    its = r.sample(sorted(W["item"]), n); ks = [r.randrange(2, 12) for _ in its]
    ps = [W["item"][i]["price"] for i in its]; tot = sum(k * p for k, p in zip(ks, ps))
    parts_txt = [f"{k} {plural(i)}" for k, i in zip(ks, its)]
    lst = ", ".join(parts_txt[:-1]) + " and " + parts_txt[-1]
    req = r.choice(["How much would {l} cost altogether?", "What's the total for {l}?", "If I buy {l}, how much is that in total?"]).format(l=lst)
    return T(type=typ, parts=["search"] * n + ["calc"], request=req,
             needs=[("search", "item", i, "price") for i in its] + [("calc", " + ".join(f"{k} * {p}" for k, p in zip(ks, ps)), "the total")],
             short=f"{tot} coins", check=chk_number(tot), swaps=[(str(ks[0]), str(ks[0] + 1))])


def t_basket2(r, W):
    return basket(r, W, 2, "basket2")


def compare(r, W, n, typ):
    kind, attr = r.choice(sorted(CMP))
    es = r.sample(sorted(W[kind]), n); vals = [W[kind][e][attr] for e in es]
    if len(set(vals)) < n:                           # ties (legs): resample with distinct values
        return compare(r, W, n, typ)
    win = es[vals.index(max(vals))]
    if n == 2:
        req = CMP[(kind, attr)][0].format(a=es[0], b=es[1])
    else:
        lst = ", ".join(es[:-1]) + " or " + es[-1]
        req = r.choice([f"Which is the {CMP[(kind, attr)][2]}: {{l}}?", f"Out of {{l}}, which is the {CMP[(kind, attr)][2]}?"]).format(l=lst)
        if kind == "person":
            req = req.replace("Which is", "Who is").replace("which is", "who is")
    expr = f"{vals[0]} > {vals[1]}" if n == 2 else f"max({', '.join(str(v) for v in vals)})"
    others = [x for x in sorted(W[kind]) if x not in es]
    return T(type=typ, parts=["search"] * n + ["compare"], request=req,
             needs=[("search", kind, e, attr) for e in es] + [("calc", expr, "which is " + CMP[(kind, attr)][1])],
             short=win, check=chk_name(win, [e for e in es if e != win]), swaps=[(es[0], others[0])] if others else [],
             cmp=(kind, attr, es))


def t_compare2(r, W):
    return compare(r, W, 2, "compare2")


def t_argmax3(r, W):
    return compare(r, W, 3, "argmax3")


def t_diff(r, W):
    kind, attr, word = r.choice([("town", "population", "How many more people live in {a} than in {b}?"),
                                 ("person", "age", "How much older is {a} than {b}?"),
                                 ("item", "weight", "How much heavier is a {a} than a {b}?")])
    a, b = r.sample(sorted(W[kind]), 2)
    if W[kind][a][attr] < W[kind][b][attr]:
        a, b = b, a
    d = W[kind][a][attr] - W[kind][b][attr]
    return T(type="diff", parts=["search", "search", "calc"], request=word.format(a=a, b=b),
             needs=[("search", kind, a, attr), ("search", kind, b, attr), ("calc", f"{W[kind][a][attr]} - {W[kind][b][attr]}", "the difference")],
             short=str(d), check=chk_number(d))


def t_bridge(r, W):
    p = r.choice(sorted(W["person"])); t = W["person"][p]["home"]
    attr = r.choice(["population", "region", "founded"])
    req = {"population": "How many people live in the town where {p} lives?", "region": "What region is {p}'s hometown in?",
           "founded": "When was the town {p} lives in founded?"}[attr].format(p=p)
    v = W["town"][t][attr]
    return T(type="bridge", parts=["search-link", "search"], request=req, hidden={t: f"{p}'s town"},
             needs=[("search", "person", p, "home"), ("search", "town", t, attr)], short=short_val("town", attr, v),
             check=chk_number(v) if isinstance(v, int) else chk_text(v), link=(p, t))


def t_ask(r, W):
    t = r.choice(sorted(W["town"])); attr = r.choice(["population", "region", "founded"])
    req = {"population": "How many people live in my town?", "region": "What region is my town in?",
           "founded": "When was my town founded?"}[attr]
    v = W["town"][t][attr]
    return T(type="ask", parts=["ask", "search"], request=req, hidden={t: "their town"}, person={"town": t, "town_reply": r.choice([t, f"i live in {t}", f"{t.lower()}", f"im in {t}"])},
             needs=[("ask", "Which town do you live in?", "town"), ("search", "town", t, attr)],
             short=short_val("town", attr, v), check=chk_number(v) if isinstance(v, int) else chk_text(v))


def t_whose(r, W):
    pa, pb = r.sample(sorted(W["person"]), 2)
    ta, tb = r.sample(sorted(W["town"]), 2)
    v, vb = W["town"][ta]["population"], W["town"][tb]["population"]
    req = r.choice(["My brother lives in {ta} and I live in {tb}. How many people live in my brother's town?",
                    "I'm in {tb} but my brother is in {ta}. How many people live where he lives?"]).format(ta=ta, tb=tb)
    return T(type="whose", parts=["given-link", "search"], request=req, needs=[("search", "town", ta, "population")],
             given=[("link", "brother", ta)], short=str(v), check=lambda a: v in numbers_in(a) and vb not in numbers_in(a))


# --- held out: combinations of trained parts that never appear together in training
def h_cost_compare(r, W):          # derived values compared (training only compares looked-up values)
    i1, i2 = r.sample(sorted(W["item"]), 2)
    p1, p2 = W["item"][i1]["price"], W["item"][i2]["price"]
    while True:
        k1, k2 = r.randrange(2, 13), r.randrange(2, 13)
        if k1 * p1 != k2 * p2:
            break
    win, lose = (i1, i2) if k1 * p1 > k2 * p2 else (i2, i1)
    req = r.choice(["Which costs more, {k1} {a} or {k2} {b}?", "What's more expensive: {k1} {a} or {k2} {b}?"]).format(k1=k1, a=plural(i1), k2=k2, b=plural(i2))
    return T(type="H:cost-compare", parts=["search", "search", "calc", "calc", "compare"], request=req,
             needs=[("search", "item", i1, "price"), ("search", "item", i2, "price"), ("calc", f"{k1} * {p1} > {k2} * {p2}", "which total is bigger")],
             short=f"the {plural(win)}", check=chk_name(win, [lose]), swaps=[(str(k1), str(k1 + 1))])


def h_argmax4(r, W):               # longer than any compare in training (2 and 3)
    return dict(compare(r, W, 4, "H:argmax4"))


def h_bridge_compare(r, W):        # a link followed inside a comparison
    p = r.choice(sorted(W["person"])); t = W["person"][p]["home"]
    o = r.choice([x for x in sorted(W["town"]) if x != t])
    pt, po = W["town"][t]["population"], W["town"][o]["population"]
    win = t if pt > po else o
    req = r.choice(["Is the town {p} lives in bigger than {o}?", "Which is bigger: {p}'s town or {o}?"]).format(p=p, o=o)
    return T(type="H:bridge-compare", parts=["search-link", "search", "search", "compare"], request=req, hidden={t: f"{p}'s town"},
             needs=[("search", "person", p, "home"), ("search", "town", t, "population"), ("search", "town", o, "population"),
                    ("calc", f"{pt} > {po}", "which is bigger")],
             short=win, check=chk_name(win, [x for x in (t, o) if x != win]))


def h_ask_diff(r, W):              # the person's answer feeds a calculation
    t, o = r.sample(sorted(W["town"]), 2)
    pt, po = W["town"][t]["population"], W["town"][o]["population"]
    req = r.choice(["How many more people live in my town than in {o}?", "How big is my town compared to {o}, like how many more or fewer people?"]).format(o=o)
    d = pt - po
    return T(type="H:ask-diff", parts=["ask", "search", "search", "calc"], request=req, hidden={t: "their town"},
             person={"town": t, "town_reply": r.choice([t, f"i live in {t}", f"{t.lower()}"])},
             needs=[("ask", "Which town do you live in?", "town"), ("search", "town", t, "population"), ("search", "town", o, "population"),
                    ("calc", f"{pt} - {po}", "the difference")],
             short=str(d), check=lambda a: abs(d) in [abs(x) for x in numbers_in(a)])


def h_basket3(r, W):               # three items where training has two
    return dict(basket(r, W, 3, "H:basket3"))


TRAIN_TASKS = [t_lookup, t_given, t_total, t_basket2, t_compare2, t_argmax3, t_diff, t_bridge, t_ask, t_whose]
HELD_OUT = [h_cost_compare, h_argmax4, h_bridge_compare, h_ask_diff, h_basket3]


def make_task(r, fn, style_p=0.5):
    W = make_world(r)
    t = T(**fn(r, W))
    t["world"] = W
    t["clean"] = t["request"]
    t["style"] = "messy" if r.random() < style_p else "clean"
    if t["style"] == "messy":
        t["request"] = messy(r, t["request"], t.get("swaps", []))
    return t


def make_set(seed, n, fns, style_p=0.5):
    r = random.Random(seed)
    return [make_task(r, fns[i % len(fns)], style_p) for i in range(n)]


# %% [markdown]
# ### The harness: runs tool calls, logs them, scores the episode

# %%
class Harness:
    def __init__(self, task):
        self.t, self.log = task, []

    def run(self, name, args):
        self.log.append((name, dict(args)))
        if name == "search":
            return search(self.t["world"], str(args.get("query", "")))
        if name == "calculator":
            return calc(str(args.get("expression", "")))
        if name == "ask_person":
            return person_reply(self.t["person"], str(args.get("question", "")))
        return f"error: no tool called {name}"


def score(task, final_text, H, first_content=""):
    short, has_line = short_answer(final_text or "")
    names = [n for n, _ in H.log]
    queries = [str(a.get("query", "")).lower() for n, a in H.log if n == "search"]
    req_ents = [s[2] for s in task["needs"] if s[0] == "search"]
    covered = sum(any(re.search(r"\b" + re.escape(e.lower()) + r"(s|'s)?\b", q) for q in queries) for e in req_ents)
    given_ents = [g[1] for g in task["given"] if g[0] != "link"]
    ok = bool(final_text) and bool(task["check"](short))
    cov = covered / len(req_ents) if req_ents else 1.0
    need_calc = any(s[0] == "calc" for s in task["needs"]); need_ask = any(s[0] == "ask" for s in task["needs"])
    strict = ok and cov == 1 and ("calculator" in names or not need_calc) and ("ask_person" in names or not need_ask)
    return {"type": task["type"], "style": task["style"], "ok": ok, "strict": strict,
            "answer_line": has_line, "format_fail": not final_text, "calls": len(H.log),
            "searches": names.count("search"), "needed_searches": len(req_ents),
            "coverage": covered / len(req_ents) if req_ents else 1.0,
            "searched_given": any(re.search(r"\b" + re.escape(e.lower()) + r"(s|'s)?\b", q) for e in given_ents for q in queries),
            "calc": "calculator" in names, "needs_calc": any(s[0] == "calc" for s in task["needs"]),
            "asked": "ask_person" in names, "needs_ask": any(s[0] == "ask" for s in task["needs"]),
            "needs_list": bool(re.search(r"\b(needs?|plan|steps?)\b[^\n]*\n(?:[^\n]*\n){0,2}\s*(1[.)]|-)", first_content, re.I))}


# %% [markdown]
# ### Gold episodes, written from the answer key with varied wording

# %%
NEEDS_HEAD = ["Needs:", "What I need:", "To answer this I need:", "Plan:", "I need:", "Steps:"]
GO = ["Starting with 1.", "First, 1.", "Getting 1 first.", "1 first.", ""]
NEXT = ["Next, {n}.", "Now {n}.", "On to {n}.", "{n} next.", "Then {n}."]
GOT = ["Got {i}: {f}", "{i} done: {f}", "{i}: {f}", "So {i} is done: {f}"]


def need_text(step, task):
    if step[0] == "search":
        _, kind, e, attr = step
        if attr == "home":
            return f"where {e} lives (search)"
        e = task.get("hidden", {}).get(e, e)          # not known yet: describe it, don't name it
        return ATTR_Q[(kind, attr)][1].format(e=e) + " (search)"
    if step[0] == "ask":
        return "which town they live in (ask them)"
    return f"{step[2]} (calculator)"


def gold_episode(task, r):
    """Model-neutral messages: assistant turns with content + tool_calls, tool results from the real harness."""
    H = Harness(task)
    needs = task["needs"]
    msgs = []
    if not needs:                                        # everything is in the message
        kind, e, attr = task["given"][0]
        v = task["world"][kind][e][attr]
        msgs.append({"role": "assistant", "content": r.choice(["The message already says it, so no search is needed.",
                                                              "That's given in the message, no lookup needed.",
                                                              "It's right there in what you said."])
                     + f" {fact_sentence(kind, e, attr, v)}\nAnswer: {task['short']}"})
        return msgs, H
    lines = [f"{j + 1}. {need_text(s, task)}" for j, s in enumerate(needs)]
    if task["given"]:
        g = task["given"][0]
        lines.insert(0, "Given in the message: " + (f"the price of a {g[1]}" if g[0] == "item" else f"the {g[1]} lives in {g[2]}"))
    content = r.choice(NEEDS_HEAD) + "\n" + "\n".join(lines) + ("\n" + r.choice(GO) if r.random() < 0.7 else "")
    W = task["world"]
    for j, s in enumerate(needs):
        if s[0] == "search":
            call = {"name": "search", "arguments": {"query": query_for(s[1], s[2], s[3])}}
        elif s[0] == "ask":
            call = {"name": "ask_person", "arguments": {"question": r.choice(["Which town do you live in?", "What town are you in?", "Which town is yours?"])}}
        else:
            call = {"name": "calculator", "arguments": {"expression": s[1]}}
        msgs.append({"role": "assistant", "content": content.strip(), "tool_calls": [call]})
        res = H.run(call["name"], call["arguments"])
        msgs.append({"role": "tool", "name": call["name"], "content": res})
        if s[0] == "search":
            f = fact_sentence(s[1], s[2], s[3], W[s[1]][s[2]][s[3]])
            assert f in res, (call, res)
        elif s[0] == "ask":
            f = f"they live in {task['person']['town']}."
        else:
            f = f"{s[1]} = {res}."
        content = r.choice(GOT).format(i=j + 1, f=f)
        if j + 1 < len(needs):
            content += " " + r.choice(NEXT).format(n=j + 2)
    msgs.append({"role": "assistant", "content": content + "\n" + explain(task, r) + f"\nAnswer: {task['short']}"})
    return msgs, H


def explain(task, r):
    W, ty = task["world"], task["type"]
    if task.get("cmp"):
        kind, attr, es = task["cmp"]
        vals = ", ".join(f"{e} {short_val(kind, attr, W[kind][e][attr])}" for e in es)
        return f"{task['short']} wins ({vals})."
    if ty == "bridge":
        p, t = task["link"]
        return f"{p} lives in {t}, so it's {task['short']}."
    return r.choice(["So that's {s}.", "That makes it {s}.", "So the answer is {s}."]).format(s=task["short"])


# %% [markdown]
# ### Parsing model output (each model's tool-call format)

# %%
def parse_lfm(text):
    """LFM2.5: content then <|tool_call_start|>[name(arg='v', ...)]<|tool_call_end|>."""
    text = text.split("<|im_end|>")[0]
    if "<|tool_call_start|>" not in text:
        return text.strip(), []
    content, rest = text.split("<|tool_call_start|>", 1)
    body = rest.split("<|tool_call_end|>")[0].strip()
    calls = []
    try:
        node = ast.parse(body if body.startswith("[") else f"[{body}]", mode="eval").body
        for c in node.elts:
            if isinstance(c, ast.Call) and isinstance(c.func, ast.Name):
                calls.append({"name": c.func.id, "arguments": {k.arg: ast.literal_eval(k.value) for k in c.keywords}})
    except Exception:
        m = re.match(r"\[?\s*(\w+)\((\w+)\s*=\s*['\"](.*?)['\"]\s*\)", body, re.S)
        if m:
            calls.append({"name": m[1], "arguments": {m[2]: m[3]}})
    return content.strip(), calls


def parse_qwen(text):
    """Qwen3: content then <tool_call>{"name": ..., "arguments": {...}}</tool_call>."""
    text = re.sub(r"<think>.*?</think>", "", text.split("<|im_end|>")[0], flags=re.S)
    calls = []
    for m in re.finditer(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", text, re.S):
        try:
            j = json.loads(m.group(1))
            calls.append({"name": j.get("name"), "arguments": j.get("arguments") or {}})
        except Exception:
            pass
    return text.split("<tool_call>")[0].strip(), calls


def render_lfm(msgs, system=SYSTEM, tools=TOOLS, user=None):
    """Exactly what LFM2.5's chat template produces; returns [(text, trained?)] pieces."""
    tl = ", ".join(json.dumps(t, ensure_ascii=False) for t in tools)
    out = [("<|startoftext|><|im_start|>system\n" + system + "\nList of tools: [" + tl + "]<|im_end|>\n", False)]
    if user is not None:
        out.append((f"<|im_start|>user\n{user}<|im_end|>\n", False))
    for m in msgs:
        if m["role"] == "assistant":
            out.append(("<|im_start|>assistant\n", False))
            s = m.get("content") or ""
            if m.get("tool_calls"):
                def fa(v):
                    return "'" + str(v).replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n") + "'" if isinstance(v, str) else json.dumps(v)
                s += "<|tool_call_start|>[" + ", ".join(c["name"] + "(" + ", ".join(f"{k}={fa(v)}" for k, v in c["arguments"].items()) + ")" for c in m["tool_calls"]) + "]<|tool_call_end|>"
            out.append((s + "<|im_end|>", True))
            out.append(("\n", False))
        else:
            out.append((f"<|im_start|>{m['role']}\n{m.get('content') or ''}<|im_end|>\n", False))
    return out


# %%
if __name__ == "__main__":
    import collections
    r = random.Random(0)
    bad = collections.Counter(); n = 0
    for fn in TRAIN_TASKS + HELD_OUT:
        for _ in range(300):
            t = make_task(r, fn)
            msgs, H = gold_episode(t, r)
            sc = score(t, msgs[-1]["content"], H, msgs[0]["content"])
            n += 1
            leak = any(h.lower() in msgs[0]["content"].lower() for h in t.get("hidden", {}))
            if leak or not (sc["strict"] and not sc["searched_given"]):
                bad[t["type"]] += 1
                if bad[t["type"]] < 3:
                    print("FAIL", t["type"], t["request"], sc, msgs[-1]["content"][-200:])
    print(f"{n} gold episodes replayed, failures: {dict(bad) or 'none'}")
    for fn in TRAIN_TASKS + HELD_OUT:
        t = make_task(random.Random(fn.__name__), fn, style_p=1.0)
        print(f"\n== {t['type']}  parts={t['parts']}\n  clean: {t['clean']}\n  messy: {t['request']}")
    t = make_task(random.Random(5), h_bridge_compare, 0)
    msgs, _ = gold_episode(t, random.Random(1))
    print("\n" + "".join(p for p, _ in render_lfm(msgs, user=t["request"])))
    print(parse_lfm("Needs:\n1. x<|tool_call_start|>[search(query='Kesh population')]<|tool_call_end|><|im_end|>"))
    print(parse_qwen('Plan\n<tool_call>\n{"name": "search", "arguments": {"query": "Kesh"}}\n</tool_call><|im_end|>'))
