# %% [markdown]
# ## Scenarios: requests that leave out what matters, and a person who only says it if asked
#
# Every scenario has a vague request, a hidden brief and a checker. The simulated person answers only the
# topics a question actually asks about, vaguely, and keeps the deep reason (why she slowed down, how he's
# been) back until the model pulls on the clue it gave. A search tool knows how to adapt a hobby to an injury,
# how people get through loneliness, what has hidden gluten, and how to fix common code errors. The checker
# scores whether the answer meets the real need and catches contradictions: meat in a vegetarian meal, a place
# in the asker's state instead of the recipient's, a price over budget, an oven when there isn't one.
#
# Families: gift, dinner, code (trained), trip (held out), plus "given": everything is in the request, so the
# right move is not to ask. Keal's three recorded tasks are encoded as fixed held-out scenarios.

# %%
import random, re

STATES = ["Ohio", "Arizona", "Texas", "Maine", "Oregon", "Florida", "Michigan", "Colorado", "Georgia", "Vermont",
          "Nevada", "Iowa", "Utah", "Kansas", "Montana", "Alabama"]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
KIN = {"mom": "she", "dad": "he", "grandma": "she", "grandpa": "he", "sister": "she", "brother": "he",
       "aunt": "she", "uncle": "he", "best friend": "she"}

# hobby -> {obstacle: (adapted gift, price)}
HOBBY = {
    "gardening": {"knees": ("a raised garden bed on legs, so she can garden standing up instead of kneeling", 55),
                  "back": ("a raised garden bed on legs plus long-handled tools, so there's no bending", 58),
                  "hands": ("a set of easy-grip, ergonomic garden tools made for arthritis", 32),
                  "eyes": ("a bright headlamp and large-print seed labels", 28)},
    "fishing": {"knees": ("a padded folding fishing chair with a back, so she can fish sitting down", 45),
                "back": ("a lightweight carbon rod and a seat with back support", 59),
                "hands": ("an easy-grip reel with a large handle, made for arthritis", 38),
                "eyes": ("a lighted, high-visibility bobber set and magnifying clip-on glasses", 24)},
    "painting": {"knees": ("a tabletop easel and a comfortable seat, so she can paint sitting down", 42),
                 "back": ("a tabletop easel at seated height with a lumbar cushion", 48),
                 "hands": ("ergonomic, thick-handled easy-grip brushes", 26),
                 "eyes": ("a daylight lamp with a magnifier for close work", 39)},
    "baking": {"knees": ("a padded anti-fatigue mat and a tall kitchen stool, so she can bake seated", 44),
               "back": ("a stand mixer on a counter-height cart, so there's no lifting or bending", 59),
               "hands": ("easy-grip, ergonomic utensils and a jar opener for arthritis", 29),
               "eyes": ("a large-print digital kitchen scale with a bright display", 27)},
    "knitting": {"knees": ("a cozy seat cushion and a yarn bowl, so knitting stays comfy", 30),
                 "back": ("a supportive lumbar cushion and a lap knitting stand", 36),
                 "hands": ("ergonomic, easy-grip knitting needles made for arthritis", 25),
                 "eyes": ("a magnifier lamp and bright, high-contrast yarn", 38)},
    "hiking": {"knees": ("a pair of lightweight trekking poles to take strain off the knees", 40),
               "back": ("a lightweight daypack with back support and hip belt", 55),
               "hands": ("trekking poles with large, easy-grip cork handles", 45),
               "eyes": ("a bright headlamp and a large-print trail map", 30)},
    "woodworking": {"knees": ("a rolling shop stool, so she can work seated", 49),
                    "back": ("a workbench riser to bring work to standing height, no bending", 57),
                    "hands": ("ergonomic, easy-grip carving tools and anti-vibration gloves", 35),
                    "eyes": ("a bright magnifier task lamp for the bench", 42)},
    "birdwatching": {"knees": ("a lightweight folding seat with a back for long sits", 39),
                     "back": ("lightweight compact binoculars and a harness instead of a neck strap", 58),
                     "hands": ("lightweight binoculars with an easy-grip, large focus wheel", 52),
                     "eyes": ("bright, high-contrast binoculars and a large-print field guide", 56)},
}
OBSTACLE = {
    "knees": ("her knees are pretty bad now", "bad knees", ["raised", "seat", "sitting", "stool", "standing", "kneel", "poles"]),
    "back": ("her back's been bad", "bad back", ["lightweight", "support", "bending", "lifting", "raised", "riser", "seat"]),
    "hands": ("her hands hurt, arthritis i think", "arthritis in the hands", ["easy-grip", "ergonomic", "grip", "large handle", "arthritis"]),
    "eyes": ("her eyesight's getting worse", "worsening eyesight", ["large-print", "magnif", "bright", "high-contrast", "high-visibility", "lamp", "lighted"]),
}
DEEP = [  # (what the person says when asked how they've been, short note, advice found by searching)
    ("she retired in the spring and honestly she's been kind of down since. lonely i think", "lonely and down since retiring",
     "lonely after retirement", "People who feel down after retiring are helped most by regular contact and something to look forward to: a standing weekly call, visits, or an activity done together."),
    ("since dad passed she's been pretty lonely tbh", "lonely since losing her partner",
     "lonely after losing a partner", "After losing a partner, regular contact matters more than any gift: a standing weekly call or visit, and doing something together."),
    ("she moved to a new town last year and doesn't really know anyone there", "isolated after moving somewhere new",
     "lonely after moving", "People who move somewhere new feel isolated until they find people: a local club or group helps, and so does regular contact with family, like a weekly call."),
    ("she's been really stressed and kinda isolated since the baby", "stressed and isolated since the new baby",
     "isolated new parent", "New parents often feel isolated: time with people they love helps most, like a regular call, a visit, or an afternoon together."),
]
GUILT = ["i dont call as much as i should", "i havent really visited in a while", "we havent talked much lately honestly"]
CONNECT = ["call", "visit", "together", "video", "facetime", "phone"]


def he_she(text, pron):
    if pron == "she":
        return text
    return re.sub(r"\bshe's\b", "he's", re.sub(r"\bher\b", "his", re.sub(r"\bshe\b", "he", text)))


def money(ans):
    return [int(m) for m in re.findall(r"\$\s?(\d{1,4})", ans)]


def lower(s):
    return s.lower()


# %% [markdown]
# ### The simulated person: answers the topics a question asks about, nothing else

# %%
TOPIC_WORDS = {
    "interest": ["like", "love", "enjoy", "hobb", "interest", "into", "fun", "free time", "favorite", "favourite", "passion", "spend her time", "spend his time"],
    "budget": ["budget", "spend", "money", "cost", "price", "afford", "$", "how much"],
    "when": ["when", "date", "timeline", "how soon", "deadline", "how long", "what day"],
    "where": ["where", "live", "located", "city", "state", "near", "far", "in person", "nearby"],
    "deep": ["why", "what happened", "slowed", "how come", "reason", "how has", "how's she", "how's he", "how is she",
             "how is he", "been doing", "been feeling", "lately", "holding up", "doing okay", "going on"],
    "wish": ["asked for", "wished", "wanted", "mentioned wanting", "on her list", "on his list"],
    "diet": ["diet", "allerg", "restrict", "vegetarian", "vegan", "gluten", "eat", "intoleran", "can't have", "cannot have", "avoid"],
    "kitchen": ["kitchen", "oven", "stove", "equipment", "cook with", "appliance", "time do you have", "how long do you have", "tools"],
    "taste": ["cuisine", "prefer", "favorite food", "taste", "flavor", "spicy", "type of food", "kind of food", "what do they like"],
    "occasion": ["occasion", "special", "what's it for", "what is it for", "celebrat", "who's coming", "who is coming", "who are"],
    "error": ["error", "message", "traceback", "exception", "what does it say", "output", "stack"],
    "goal": ["trying to", "supposed to", "expect", "should it", "what do you want", "goal", "meant to"],
    "change": ["change", "update", "worked before", "used to work", "different", "new"],
    "language": ["language", "python", "javascript", "js", "which version"],
    "who": ["who", "with you", "going with", "travel with", "people", "kids", "anyone"],
    "from": ["from", "where are you", "starting", "leaving"],
    "trip_why": ["why", "occasion", "reason", "special", "what's it for", "celebrat", "looking for", "kind of trip", "vibe"],
}


class Person:
    def __init__(self, brief):
        self.b, self.revealed = brief, set()

    def reply(self, q):
        ql = q.lower()
        parts = []
        for topic in self.b["order"]:
            if topic in self.revealed and topic != "deep":
                continue
            info = self.b["topics"].get(topic)
            if info is None or not any(w in ql for w in TOPIC_WORDS[info.get("words", topic)]):
                continue
            need = info.get("requires")
            if need and need not in self.revealed:
                continue
            if topic in self.revealed:
                continue
            parts.append(info["say"]); self.revealed.add(topic)
        if not parts:
            return self.b.get("dunno", "idk what you mean lol")
        return " ".join(p if p.rstrip()[-1:] in ".?!" else p + "." for p in parts)


# %% [markdown]
# ### Search: a small knowledge base, matched on words

# %%
KB = [
    (["boustrophedon"], "Boustrophedon: writing where alternate lines run in opposite directions, left to right then right to left, often with letters mirrored on the reversed lines."),
    (["coeliac", "celiac"], "Coeliac disease: an autoimmune reaction to gluten (wheat, barley, rye). Even crumbs cause harm. Hidden gluten is common in stock, soy sauce, gravy and sauces, so check labels for 'gluten-free'. Avoid cross-contact: clean pans and boards, and a separate toaster."),
    (["gluten"], "Gluten is in wheat, barley and rye: bread, pasta, flour, most soy sauce and many stocks. Naturally gluten-free: rice, potatoes, corn, meat, fish, eggs, vegetables. Check stock and sauce labels."),
    (["vegetarian"], "Vegetarian means no meat or fish: no chicken, beef, pork, turkey, ham, bacon, fish or seafood, and no meat stock. Eggs and dairy are fine."),
    (["vegan"], "Vegan means no animal products: no meat, fish, eggs, dairy (milk, butter, cheese, cream) or honey. Watch for butter, cheese and stock."),
    (["nut", "peanut"], "Nut allergy: avoid nuts and anything labelled 'may contain nuts'; check pesto, sauces and baked goods; use clean utensils to avoid cross-contact."),
    (["lactose", "dairy"], "Lactose intolerance: avoid milk, cream, soft cheese and butter, or use lactose-free versions. Olive oil works instead of butter."),
    (["retire", "retirement"], DEEP[0][3]),
    (["lost", "losing", "passed", "partner", "widow", "grief"], DEEP[1][3]),
    (["moved", "new town", "moving"], DEEP[2][3]),
    (["baby", "new parent", "new mom", "new dad"], DEEP[3][3]),
    (["lonely", "loneliness", "down", "depress", "isolat", "sad"], "Loneliness is helped most by regular contact: a standing weekly call or visits, and doing things together, more than by any gift. Gently checking in matters."),
    (["wheelchair", "accessib", "mobility"], "For a wheelchair user, choose step-free, accessible places: accessible rooms, ramps, flat paths and accessible restaurants. Call ahead to confirm."),
    (["toddler", "kid", "child", "baby"], "Travelling with a toddler: pick kid-friendly, short trips with a nap break, a family room, and somewhere with space to play."),
    (["dog", "pet"], "Travelling with a dog: book pet-friendly (dog-friendly) places, and plan walks and parks."),
    (["burnout", "quiet", "relax", "stress"], "To recover from burnout, a quiet, slow trip helps most: somewhere calm, little driving, nothing scheduled."),
    (["anniversary"], "For an anniversary, a trip that feels special helps: a nice dinner, a scenic spot, time just the two of you."),
    (["keyerror"], "KeyError means the dictionary has no such key. Fix: check the key exists, or use dict.get('key') with a default."),
    (["undefined", "reading 'map'", "cannot read properties"], "TypeError 'Cannot read properties of undefined (reading map)': the array is undefined, often before data loads. Fix: give it a default ([]) or check it exists before calling .map."),
    (["indentationerror", "indentation"], "IndentationError: mixed or wrong indentation. Fix: use 4 spaces consistently and line up the block."),
    (["modulenotfounderror", "no module named"], "ModuleNotFoundError: the package isn't installed in this environment. Fix: pip install the package (in the same environment that runs the code)."),
    (["unexpected token", "syntaxerror"], "SyntaxError Unexpected token: often a missing bracket, comma or quote, or JSON that isn't valid. Fix: check the line it points to and the one before it."),
]
for h, opts in HOBBY.items():
    for ob, (gift, price) in opts.items():
        KB.append(([h, OBSTACLE[ob][1].split()[-1]], f"{h.capitalize()} with {OBSTACLE[ob][1]}: try {re.split(r', so |, made| plus ', gift)[0]} (around ${price})."))


def search(query):
    q = query.lower()
    best, score = None, 0
    for keys, text in KB:
        s = sum(1 for k in keys if k in q)
        if s > score:
            best, score = text, s
    return best or "no results"


# %% [markdown]
# ### Scenario builders. Each returns a brief, a gold trajectory and a checker.

# %%
def S(kind, **kw):
    return dict(kind=kind, **kw)


def gift(r, kin=None, hobby=None, ob=None, deep_i=None, states=None, budget=None, days=None, given=False):
    kin = kin or r.choice(list(KIN))
    pron = KIN[kin]
    hobby = hobby or r.choice(list(HOBBY))
    ob = ob or r.choice(list(HOBBY[hobby]))
    if deep_i is None:
        deep_i = r.choice([1, 2, 3] if kin in ("sister", "brother", "best friend") else [0, 1, 2])
    there, here = states or r.sample(STATES, 2)
    budget = budget or r.choice([40, 50, 60, 75, 100])
    days = days or r.randrange(4, 10)
    day = DAYS[(r.randrange(7))]
    item, price = HOBBY[hobby][ob]
    if price > budget:
        budget = price + r.choice([5, 10, 20])
    hs = lambda t: he_she(t, pron)
    deep_say, deep_note, deep_q, deep_adv = DEEP[deep_i]
    if deep_i == 1:
        partner = {"mom": "dad", "dad": "mom", "grandma": "grandpa", "grandpa": "grandma", "aunt": "my uncle", "uncle": "my aunt"}.get(kin, "her husband" if pron == "she" else "his wife")
        deep_say = deep_say.replace("dad", partner)
    guilt = r.choice(GUILT)
    topics = {
        "interest": dict(say=hs(r.choice([f"uhh {pron} likes {hobby}, like a lot, or {pron} used to anyway. {pron}'s kind of slowed down on it",
                                          f"{hobby} i guess? {pron} used to be really into it but not so much lately",
                                          f"oh {pron} loves {hobby}. well used to, {pron} doesn't do it as much now"])), note=f"{hobby} (used to, slowed down)"),
        "budget": dict(say=r.choice([f"not a ton, like ${budget} maybe", f"idk like ${budget}? money's kinda tight", f"under ${budget} ideally"]), note=f"about ${budget}"),
        "when": r.choice([dict(say=f"its next {day}", note=f"next {day}"), dict(say=f"in like {days} days", note=f"{days} days away")]),
        "where": dict(say=hs(r.choice([f"{pron} lives in {there}, im in {here}", f"{there}. im in {here} so i cant really go"])), note=f"{kin} in {there}; asker in {here}"),
        "deep": dict(say=hs(f"{OBSTACLE[ob][0]}. and {deep_say}. {guilt}"), requires="interest", note=f"{OBSTACLE[ob][1]}; {deep_note}; asker: {guilt}"),
        "wish": dict(say=hs(f"{pron} never asks for anything lol"), note="never asks for anything"),
    }
    request = r.choice([f"hey so my {kin}s birthday is coming up and i wanna do something for it but idk what. can you help me figure it out?",
                        f"need a gift idea for my {kin}, birthday's soon. ideas?",
                        f"what should i get my {kin} for {('her' if pron == 'she' else 'his')} birthday",
                        f"my {kin}'s bday is coming up, help me pick something"])
    brief = dict(topics=topics, order=["interest", "budget", "when", "where", "wish", "deep"])
    if given:
        request = hs(f"my {kin} lives in {there} (i'm in {here}). {pron} loves {hobby} but {OBSTACLE[ob][0]}. {deep_say}, and {guilt}. "
                     f"budget about ${budget}, birthday is in {days} days. what should i get {('her' if pron == 'she' else 'him')}?")
    pos = "her" if pron == "she" else "his"
    them = "her" if pron == "she" else "him"
    gold = []
    if not given:
        gold += [S("think", text=f"I don't know anything about your {kin} yet. Start broad: what {pron} likes, budget, when, and where {pron} lives."),
                 S("ask", text=r.choice([f"What does your {kin} like doing? What's your budget, when's the birthday, and where does {pron} live?",
                                         f"Happy to help! What is your {kin} into, how much do you want to spend, when is it, and does {pron} live near you?"])),
                 S("fact", key="interest", value=topics["interest"]["note"]), S("fact", key="budget", value=topics["budget"]["note"]),
                 S("fact", key="when", value=topics["when"]["note"]), S("fact", key="where", value=topics["where"]["note"]),
                 S("think", text=f"'Used to': {pron} slowed down. Why {pron} slowed down decides what kind of gift helps, so ask, gently."),
                 S("ask", text=r.choice([f"You said {pron} used to love {hobby}. Do you know what slowed {them} down? And how has {pron} been lately? Totally fine if you'd rather not say.",
                                         f"Can I ask why {pron} does less {hobby} now, and how {pron}'s been doing lately? It helps me pick something that fits."])),
                 S("fact", key="why", value=topics["deep"]["note"])]
    else:
        gold += [S("think", text=f"Everything I need is in the message: {hobby}, {OBSTACLE[ob][1]}, {deep_note}, ${budget}, {days} days, {kin} in {there}. No need to ask.")]
    gold += [S("search", text=f"{hobby} with {OBSTACLE[ob][1]}"),
             S("search", text=deep_q),
             S("think", text=f"A gift that keeps {hobby} possible with {OBSTACLE[ob][1]}, plus something that connects them, since {pron}'s {deep_note}. Keep it under ${budget}, in time, for {there}."),
             S("check", text=f"for {kin} in {there} (not {here}); under ${budget}; arrives within {days} days; {OBSTACLE[ob][1]}; {deep_note}"),
             S("answer", text=hs(f"Here's what I'd do. Get {item} (around ${price}), so {pron} can keep {hobby} going. Order it today and ship it straight to {pos} place in {there} "
                                 f"so it arrives in time. The bigger thing: since {pron}'s been {deep_note}, pair it with something that connects you. Set up a standing weekly call, same day every week, "
                                 f"so it doesn't depend on remembering, and maybe do a video call when it arrives and set it up together. That's what will mean the most."))]
    def check(ans, person):
        a = ans.lower()
        found = given or "deep" in person.revealed
        adapted = any(k in a for k in OBSTACLE[ob][2])
        connect = any(k in a for k in CONNECT)
        wrong_place = [s for s in STATES if re.search(r"\b" + s.lower() + r"\b", a) and s != there]
        over = [m for m in money(ans) if m > budget]
        parts = dict(found_need=found, adapted=adapted, connect=connect, no_wrong_place=not wrong_place, in_budget=not over)
        return all(parts.values()), parts
    return dict(family="gift", given=given, request=request, brief=brief, gold=gold, check=check, needs_ask=not given)


DISHES = [  # name, ingredients, needs oven, contains
    ("one-pot chicken and rice", ["chicken breast", "long grain rice", "carrots", "onion", "garlic", "chicken stock", "butter"], False, {"meat", "dairy", "stock"}),
    ("vegetable stir-fry with rice", ["rice", "broccoli", "bell peppers", "carrots", "garlic", "ginger", "soy sauce", "oil"], False, {"soy"}),
    ("chickpea and spinach curry", ["chickpeas", "spinach", "onion", "garlic", "canned tomatoes", "curry spices", "coconut milk", "rice"], False, set()),
    ("baked salmon with potatoes", ["salmon fillets", "potatoes", "lemon", "olive oil", "green beans"], True, {"fish"}),
    ("pasta with tomato sauce", ["pasta", "canned tomatoes", "garlic", "olive oil", "parmesan", "basil"], False, {"gluten", "dairy"}),
    ("beef tacos", ["ground beef", "corn tortillas", "lettuce", "tomato", "cheese", "salsa"], False, {"meat", "dairy"}),
    ("roast vegetables and quinoa", ["quinoa", "sweet potatoes", "zucchini", "red onion", "olive oil", "lemon"], True, set()),
    ("black bean chili", ["black beans", "kidney beans", "onion", "peppers", "canned tomatoes", "chili spices", "vegetable stock"], False, {"stock"}),
    ("pesto pasta", ["pasta", "pesto", "parmesan", "cherry tomatoes"], False, {"gluten", "dairy", "nuts"}),
]
CONSTRAINT = {  # name: (how the person says it, forbidden words in the answer, a safety point the answer should make, search query)
    "coeliac": ("oh one of them is coeliac", ["pasta", "bread", "flour", "wheat", "barley", "breadcrumbs", "couscous"], ["label", "gluten-free stock", "cross-contact", "separate", "clean"], "coeliac"),
    "vegetarian": ("one of them is vegetarian", ["chicken", "beef", "pork", "turkey", "ham", "bacon", "salmon", "fish", "tuna", "shrimp", "sausage", "meat stock", "chicken stock"], ["vegetable stock", "no meat"], "vegetarian"),
    "vegan": ("one of them is vegan", ["chicken", "beef", "pork", "turkey", "salmon", "fish", "cheese", "butter", "parmesan", "cream", "egg", "honey"], ["vegetable stock", "no dairy", "no animal"], "vegan"),
    "nut allergy": ("my friend has a bad nut allergy", ["pesto", "peanut", "almond", "cashew", "walnut"], ["label", "may contain", "clean"], "nut allergy"),
    "lactose": ("one of them is lactose intolerant", ["cheese", "butter", "cream", "parmesan"], ["lactose-free", "olive oil"], "lactose"),
}
BAD = {"coeliac": {"gluten", "soy"}, "vegetarian": {"meat", "fish"}, "vegan": {"meat", "fish", "dairy"}, "nut allergy": {"nuts"}, "lactose": {"dairy"}}


def safe_dishes(con, oven):
    return [d for d in DISHES if not (d[3] & BAD[con]) and (oven or not d[2])]


def dinner(r, con=None, oven=None, n=None, given=False, request=None):
    con = con or r.choice(list(CONSTRAINT))
    oven = r.random() < 0.5 if oven is None else oven
    n = n or r.choice([3, 4, 5, 6])
    day = r.choice(["tonight", "tomorrow", "saturday", "friday night"])
    say, forbid, safety, sq = CONSTRAINT[con]
    name, ingredients, needs_oven, contains = r.choice(safe_dishes(con, oven))
    ingredients = [("gluten-free " + i if con == "coeliac" and i in ("chicken stock", "vegetable stock", "soy sauce") else
                    "vegetable stock" if con in ("vegetarian", "vegan") and i == "chicken stock" else
                    "olive oil" if con in ("vegan", "lactose") and i == "butter" else i) for i in ingredients]
    topics = {
        "diet": dict(say=say, note=con),
        "kitchen": dict(say=r.choice(["i have an oven and a stove, like an hour", "full kitchen, oven and everything"]) if oven else
                        r.choice(["no oven, just a stovetop. like an hour", "only a stove, my oven's broken"]), note="oven" if oven else "no oven, stovetop only"),
        "taste": dict(say=r.choice(["they like comfort food mostly", "nothing too fancy, they like simple stuff", "they're into hearty stuff"]), note="simple, comforting"),
        "occasion": dict(say=r.choice(["just friends hanging out", "its my partner's parents, first time meeting them, kinda nervous"]), note="who's coming"),
    }
    brief = dict(topics=topics, order=["diet", "kitchen", "taste", "occasion"])
    if request is None:
        request = r.choice([f"cooking dinner {day} for {n} people, what should i make? need a shopping list too",
                            f"having {n} people over for dinner {day}, help me plan a meal and what to buy",
                            f"what should i cook for {n} people {day}"])
        if given:
            request = f"cooking dinner {day} for {n} people and {say.replace('oh ', '')}. {topics['kitchen']['say']}. what should i make, and give me a shopping list"
    gold = []
    if not given:
        gold += [S("think", text="Before picking a dish: does anyone have dietary needs, and what kitchen and time are there?"),
                 S("ask", text=r.choice(["Does anyone have allergies or dietary restrictions? And what do you have to cook with, oven or just a stove?",
                                         "Any allergies or foods anyone can't eat? What kitchen equipment do you have, and how much time?"])),
                 S("fact", key="diet", value=con), S("fact", key="kitchen", value=topics["kitchen"]["note"])]
    else:
        gold += [S("think", text=f"The message says: {con}, {topics['kitchen']['note']}. I don't need to ask.")]
    gold += [S("search", text=sq),
             S("think", text=f"Pick something with nothing {con} rules out" + ("" if oven else ", and nothing that needs an oven") + ", then check every ingredient."),
             S("check", text=f"{con}: none of {', '.join(forbid[:5])}; " + ("oven available" if oven else "no oven") + f"; {n} people"),
             S("answer", text=f"Make {name}" + ("" if needs_oven else " on the stove") + f". Shopping list for {n}: " + ", ".join(ingredients) + ". "
               + {"coeliac": "Keeping it safe: buy stock and sauces labelled gluten-free (stock often hides gluten), and avoid cross-contact: clean pans and boards, and keep it apart from anything with gluten.",
                  "vegetarian": "It's fully vegetarian: no meat or fish, and use vegetable stock, not chicken stock.",
                  "vegan": "It's vegan: no meat, no dairy, no animal products, and use vegetable stock and olive oil instead of butter.",
                  "nut allergy": "For the nut allergy: check every label for 'may contain nuts' and use clean utensils.",
                  "lactose": "For the lactose intolerance: no butter, cream or cheese; cook with olive oil, or use lactose-free versions."}[con])]

    def check(ans, person):
        a = ans.lower()
        found = given or "diet" in person.revealed
        bad = [w for w in forbid if w in a and not re.search(r"(no|not|avoid|without|instead of|free)\W+(\w+\W+){0,3}" + re.escape(w.strip()), a)]
        oven_bad = (not oven) and any(w in a for w in ("oven", "bake", "baked", "roast"))
        safe = any(s in a for s in safety)
        parts = dict(found_need=found, nothing_forbidden=not bad, fits_kitchen=not oven_bad, safety_note=safe)
        return all(parts.values()), parts
    return dict(family="dinner", given=given, request=request, brief=brief, gold=gold, check=check, needs_ask=not given)


ERRORS = [
    ("python", "KeyError: 'name'", "keyerror", ["get(", "exists", "check"], "reading user records from a dict"),
    ("javascript", "TypeError: Cannot read properties of undefined (reading 'map')", "cannot read properties undefined", ["default", "[]", "exists", "?."], "rendering a list from an API"),
    ("python", "IndentationError: unexpected indent", "indentationerror", ["indent", "spaces"], "a function that adds up totals"),
    ("python", "ModuleNotFoundError: No module named 'requests'", "modulenotfounderror", ["pip install", "install"], "a script that downloads a page"),
    ("javascript", "SyntaxError: Unexpected token '}'", "unexpected token syntaxerror", ["bracket", "brace", "comma", "missing"], "a config object"),
]


def code(r, err_i=None):
    lang, err, sq, fix, goal = ERRORS[r.randrange(len(ERRORS)) if err_i is None else err_i]
    topics = {
        "error": dict(say=r.choice([f"it says {err}", f"uh the error is like '{err}'", f"{err} on line {r.randrange(4, 60)}"]), note=err),
        "goal": dict(say=f"its {goal}", note=goal),
        "language": dict(say=lang, note=lang),
        "change": dict(say=r.choice(["it worked yesterday, i changed some stuff", "i didnt change anything i think"]), note="recent change"),
    }
    brief = dict(topics=topics, order=["error", "goal", "language", "change"])
    request = r.choice(["my code is broken can you help", "this script wont run, what's wrong", "help my code doesnt work", "getting an error and idk why"])
    gold = [S("think", text="I can't fix it without seeing what goes wrong. Ask for the exact error and what it's meant to do."),
            S("ask", text=r.choice(["What's the exact error message, and what is the code supposed to do?", "Can you paste the error it shows, and tell me what it's trying to do and which language?"])),
            S("fact", key="error", value=err), S("fact", key="goal", value=goal),
            S("search", text=sq),
            S("check", text=f"the fix addresses '{err}'"),
            S("answer", text=f"{search(sq)} In your code for {goal}, start with the line the error points to.")]

    def check(ans, person):
        a = ans.lower()
        found = "error" in person.revealed
        fixed = any(f in a for f in fix)
        parts = dict(found_need=found, fix=fixed)
        return all(parts.values()), parts
    return dict(family="code", given=False, request=request, brief=brief, gold=gold, check=check, needs_ask=True)


TRIP = {  # who: (how they say it, keywords the answer needs, search)
    "wheelchair": ("my grandma's coming, she uses a wheelchair", ["accessible", "step-free", "ramp", "wheelchair"], "wheelchair accessible"),
    "toddler": ("me and my wife and our 2 year old", ["kid-friendly", "toddler", "nap", "family"], "toddler trip"),
    "dog": ("just me and my dog", ["pet-friendly", "dog-friendly", "dog"], "dog trip"),
}
TRIP_WHY = {"burnout": ("honestly i'm super burnt out, i just need a break", ["quiet", "calm", "relax", "slow"], "burnout quiet"),
            "anniversary": ("its our anniversary actually", ["anniversary", "special", "dinner", "romantic"], "anniversary")}


def trip(r):
    who = r.choice(list(TRIP))
    why = r.choice(list(TRIP_WHY))
    home = r.choice(STATES)
    budget = r.choice([200, 300, 500])
    topics = {"who": dict(say=TRIP[who][0], note=who), "from": dict(say=f"from {home}", note=home),
              "budget": dict(say=f"like ${budget} total", note=f"${budget}"), "trip_why": dict(say=TRIP_WHY[why][0], note=why),
              "when": dict(say="next weekend", note="next weekend")}
    brief = dict(topics=topics, order=["who", "from", "budget", "when", "trip_why"])
    request = r.choice(["help me plan a weekend trip", "i want to get away for a weekend, ideas?", "plan me a quick trip somewhere"])

    def check(ans, person):
        a = ans.lower()
        parts = dict(found_who="who" in person.revealed, found_why="trip_why" in person.revealed,
                     fits_who=any(k in a for k in TRIP[who][1]), fits_why=any(k in a for k in TRIP_WHY[why][1]),
                     in_budget=not [m for m in money(ans) if m > budget])
        return all(parts.values()), parts
    return dict(family="trip", given=False, request=request, brief=brief, gold=[], check=check, needs_ask=True)


# %% [markdown]
# ### Keal's three recorded tasks, as fixed test scenarios

# %%
def keal_mom(r):
    s = gift(r, kin="mom", hobby="gardening", ob="knees", deep_i=0, states=("Ohio", "Arizona"), budget=60, days=6)
    s["request"] = "hey so my moms birthday is coming up and i wanna do something for it but idk what. can you help me figure it out?"
    t = s["brief"]["topics"]
    t["interest"]["say"] = "uhh she likes gardening, like a lot, or she used to anyway. shes kind of slowed down on it"
    t["wish"]["say"] = "i dont think shes asked for anything honestly she never does lol"
    t["budget"]["say"] = "budget idk not a ton, like i dont wanna spend crazy money. like $60 maybe, money's kinda tight this month"
    t["when"]["say"] = "its next thursday"
    t["where"]["say"] = "she lives in ohio, im in arizona so i cant really go this time"
    t["deep"]["say"] = ("her knees are pretty bad now. and she retired in the spring and she's been kind of down since, lonely i think. "
                        "i dont call as much as i should. last year i sent flowers and it felt kind of impersonal")
    s["family"] = "keal-mom"
    return s


def keal_coeliac(r):
    s = dinner(r, con="coeliac", oven=True, n=4, given=True,
               request="you're cooking dinner tonight for four people. one of them is coeliac. figure out a meal you'd actually make, a shopping list, and how you'd make sure it's safe for them")
    s["family"] = "keal-coeliac"
    return s


def keal_boustrophedon(r):
    req = ("write a function that takes a number n and prints the numbers 1 to n² in a square grid, laid out boustrophedon. "
           "So boustrophedon(3) prints a 3×3 grid. Bonus: make it work for a rectangle of any width and height.")

    def check(ans, person):
        a = ans.lower()
        parts = dict(has_code=("function" in a or "def " in a or "=>" in a), reverses=("reverse" in a or "[::-1]" in a or "% 2" in a))
        return all(parts.values()), parts
    return dict(family="keal-boustrophedon", given=True, request=req, brief=dict(topics={}, order=[], dunno="whatever you think is right"),
                gold=[], check=check, needs_ask=False)


TRAIN_FAMILIES = {"gift": lambda r: gift(r), "dinner": lambda r: dinner(r), "code": lambda r: code(r),
                  "gift-given": lambda r: gift(r, given=True), "dinner-given": lambda r: dinner(r, given=True)}
TEST_FAMILIES = {"gift": lambda r: gift(r), "dinner": lambda r: dinner(r), "code": lambda r: code(r),
                 "given": lambda r: (gift if r.random() < 0.5 else dinner)(r, given=True), "trip (unseen)": trip}
KEAL = {"keal-mom": keal_mom, "keal-coeliac": keal_coeliac, "keal-boustrophedon": keal_boustrophedon}


# %% [markdown]
# ### The harness: tools, the working notes, and the check

# %%
SYSTEM = ("You help people get what they actually need. Find out before you answer. Tools: <ask>question</ask> asks the person "
          "(they reply in <reply>); <search>query</search> looks something up (<result>); <fact key=\"k\">value</fact> notes what you "
          "learned; <check>what the answer must satisfy</check> shows your notes so you can compare before answering; "
          "<think>...</think> to reason; <answer>...</answer> is your reply to the person. If the message already says what you need, don't ask.")
ACTION_RE = re.compile(r"<(think|ask|search|fact|check|answer)((?:\s+\w+=\"[^\"]*\")*)>(.*?)</\1>", re.S)
STOPS = [f"</{t}>" for t in ("think", "ask", "search", "fact", "check", "answer")]


def attrs_of(s):
    return dict(re.findall(r'(\w+)="([^"]*)"', s or ""))


class Harness:
    def __init__(self, sc):
        self.sc, self.person, self.notes, self.log = sc, Person(sc["brief"]), {}, []

    def act(self, tag, attrs, body):
        self.log.append(tag)
        if tag == "ask":
            return f"<reply>{self.person.reply(body)}</reply>"
        if tag == "search":
            return f"<result>{search(body)}</result>"
        if tag == "fact":
            self.notes[attrs.get("key") or f"note{len(self.notes) + 1}"] = body
            return ""
        if tag == "check":
            notes = "; ".join(f"{k}: {v}" for k, v in self.notes.items()) or "nothing noted"
            return f"<notes>{notes}</notes>"
        return ""


def step_text(s):
    if s["kind"] == "fact":
        return f'<fact key="{s["key"]}">{s["value"]}</fact>'
    return f"<{s['kind']}>{s['text']}</{s['kind']}>"


def render_gold(sc):
    """Gold trajectory -> [(text, trained)], observations from the real harness so train and test match. Returns pieces, harness, answer."""
    H, out, ans = Harness(sc), [], None
    for s in sc["gold"]:
        t = step_text(s)
        if s["kind"] == "answer":
            out.append((t, True))
            ans = s["text"]
            break
        out.append((t + "\n", True))           # the newline is the model's: the closing '>' shares a token with it
        obs = H.act(s["kind"], {"key": s.get("key")}, s.get("text") or s.get("value"))
        if obs:
            out.append((obs + "\n", False))
    return out, H, ans


def score(sc, ans, H):
    ok, parts = sc["check"](ans or "", H.person)
    asked = H.log.count("ask")
    return dict(ok=bool(ans) and ok, parts=parts, asked=asked, first_ask=bool(H.log) and "ask" in H.log[:3],
                searched=H.log.count("search"), checked="check" in H.log, no_answer=not ans,
                deep="deep" in H.person.revealed or "trip_why" in H.person.revealed or "diet" in H.person.revealed or "error" in H.person.revealed)


if __name__ == "__main__":       # every gold trajectory must pass its own checker, through the real harness
    r = random.Random(0)
    n = bad = 0
    for name, f in TRAIN_FAMILIES.items():
        for _ in range(400):
            sc = f(r)
            pieces, H, ans = render_gold(sc)
            res = score(sc, ans, H)
            n += 1
            if not res["ok"]:
                bad += 1
                if bad <= 5:
                    print("FAIL", name, res["parts"], "\n ", sc["request"], "\n ", ans)
    print(f"{n - bad}/{n} gold trajectories pass")
    sc = keal_mom(r)
    print("".join(p for p, _ in render_gold(sc)[0]))
