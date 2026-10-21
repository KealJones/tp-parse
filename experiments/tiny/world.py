"""A tiny world described in two languages, with no labels.

Every sentence comes from one meaning frame (who does what to what), written
out once in toki pona and once in English. The model never sees the frames or
any pairing between the languages; it only sees one language's sentences as a
stream of words. Any link between "telo" and "water" has to come from the two
languages describing the same world in the same patterns.

Some English words are single words where toki pona uses two:
    cake = pan suwi (sweet bread)     cat  = soweli lili (small animal)
    tree = kasi suli (big plant)      lake = telo suli (big water)
    child = jan lili (small person)
"""
import random

# concept: (toki pona phrase, English word)
NOUNS = {
    "person": ("jan", "person"),
    "child": ("jan lili", "child"),
    "dog": ("soweli", "dog"),
    "cat": ("soweli lili", "cat"),
    "bird": ("waso", "bird"),
    "fish": ("kala", "fish"),
    "bread": ("pan", "bread"),
    "cake": ("pan suwi", "cake"),
    "fruit": ("kili", "fruit"),
    "water": ("telo", "water"),
    "house": ("tomo", "house"),
    "tree": ("kasi suli", "tree"),
    "lake": ("telo suli", "lake"),
}
ADJS = {
    "big": ("suli", "big"),
    "small": ("lili", "small"),
    "good": ("pona", "good"),
    "bad": ("ike", "bad"),
    "sweet": ("suwi", "sweet"),
}

AGENTS = ["person", "child", "dog", "cat", "bird"]
FOODS = {  # who eats what (world knowledge)
    "person": ["bread", "cake", "fruit", "fish"],
    "child": ["cake", "cake", "fruit", "bread"],
    "dog": ["bread", "fish"],
    "cat": ["fish"],
    "bird": ["fruit", "bread"],
}
PLACES = {  # who goes / sleeps where
    "person": ["house", "lake"],
    "child": ["house", "tree", "lake"],
    "dog": ["house", "lake"],
    "cat": ["house", "tree"],
    "bird": ["tree", "lake"],
}
PROPS = {  # what can be described how
    "person": ["big", "good", "bad"],
    "child": ["small", "good"],
    "dog": ["big", "small", "good", "bad"],
    "cat": ["small", "good", "bad"],
    "bird": ["small"],
    "fish": ["small", "good"],
    "bread": ["good"],
    "cake": ["sweet", "good"],
    "fruit": ["sweet", "good"],
    "water": ["good"],
    "house": ["big", "small"],
    "tree": ["big"],
    "lake": ["big"],
}


def frame(r: random.Random):
    """One meaning: (kind, slots)."""
    kind = r.choice(["eat", "eat", "drink", "go", "sleep", "prop", "prop", "see", "love"])
    a = r.choice(AGENTS)
    if kind == "eat":
        return kind, (a, r.choice(FOODS[a]))
    if kind == "drink":
        return kind, (a, "water")
    if kind in ("go", "sleep"):
        return kind, (a, r.choice(PLACES[a]))
    if kind == "prop":
        x = r.choice(list(PROPS))
        return kind, (x, r.choice(PROPS[x]))
    return kind, (a, r.choice(list(NOUNS)))  # see / love: anything


def nonsense_frame(r: random.Random):
    """Same sentence shapes, but every slot filled at random: grammar with no world."""
    kind = r.choice(["eat", "eat", "drink", "go", "sleep", "prop", "prop", "see", "love"])
    if kind == "prop":
        return kind, (r.choice(list(NOUNS)), r.choice(list(ADJS)))
    return kind, (r.choice(list(NOUNS)), r.choice(list(NOUNS)))


def toki_pona(kind, slots):
    s, o = slots
    S = NOUNS[s][0]
    if kind == "eat":
        return f"{S} li moku e {NOUNS[o][0]} ."
    if kind == "drink":
        return f"{S} li moku e telo ."  # toki pona uses moku for eat and drink
    if kind == "go":
        return f"{S} li tawa {NOUNS[o][0]} ."
    if kind == "sleep":
        return f"{S} li lape lon {NOUNS[o][0]} ."
    if kind == "prop":
        return f"{S} li {ADJS[o][0]} ."
    if kind == "see":
        return f"{S} li lukin e {NOUNS[o][0]} ."
    return f"{S} li olin e {NOUNS[o][0]} ."


def english(kind, slots):
    s, o = slots
    S = NOUNS[s][1]
    if kind == "eat":
        return f"the {S} eats the {NOUNS[o][1]} ."
    if kind == "drink":
        return f"the {S} drinks the water ."
    if kind == "go":
        return f"the {S} goes to the {NOUNS[o][1]} ."
    if kind == "sleep":
        return f"the {S} sleeps in the {NOUNS[o][1]} ."
    if kind == "prop":
        return f"the {S} is {ADJS[o][1]} ."
    if kind == "see":
        return f"the {S} sees the {NOUNS[o][1]} ."
    return f"the {S} loves the {NOUNS[o][1]} ."


def corpus(lang: str, n: int, seed: int) -> list[str]:
    r = random.Random(seed)
    if lang == "tp":
        return [toki_pona(*frame(r)) for _ in range(n)]
    if lang == "en":
        return [english(*frame(r)) for _ in range(n)]
    if lang == "tp-nonsense":
        return [toki_pona(*nonsense_frame(r)) for _ in range(n)]
    if lang == "tp-random":
        vocab = sorted({w for s in corpus("tp", 500, 0) for w in s.split()} - {"."})
        return [" ".join(r.choice(vocab) for _ in range(r.randint(3, 6))) + " ." for _ in range(n)]
    raise ValueError(lang)


if __name__ == "__main__":
    for lang in ["tp", "en", "tp-nonsense", "tp-random"]:
        print(f"--- {lang}")
        for s in corpus(lang, 6, 1):
            print("  " + s)
