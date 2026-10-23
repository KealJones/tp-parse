"""Build training episodes from the recorded human traces (format v2.1).

Each episode is a list of events in the order they really happened (t = transcript timestamp, or None
for added events).

Model actions (trained on):
  think {text}                      the model's reasoning, in plain words
  search {id, query}                a web lookup
  memory {id, query}                a lookup in long-term memory
  run {id, code}                    run code (always the full program)
  ask {id, text}                    a question to the person
  fact {key, value, source, assumes?}  working picture: something known, where it came from, what it rests on
  assume {key, value}               working picture: a placeholder, not yet confirmed
  need {key, blocks}                working picture: missing information, and what it blocks
  todo {id, text}                   working picture: something owed to the person
  done {id, how}                    close a todo
  idea {id, text, assumes}          working picture: a candidate, and the keys (facts, assumptions, needs) it rests on
  drop {id, why}                    retire an idea
  draft {text}                      a draft answer, not sent yet
  check {text}                      compare the work against the notes, the request or the world
  answer {text}                     the reply sent to the person

Observations (not trained on, written by the world):
  result {to, text, source?}        what a search / memory / run returned
  reply {to, text}                  the person's answer to an ask
  harness {text}                    the harness listing the working picture: open needs and todos, ideas and what
                                    they rest on, and anything that rests on a key that changed. It states no world facts.

Every event has prov:
  recorded       what Keal did or said, close to verbatim
  condensed      recorded, but shortened or reworded
  reconstructed  recorded on screen but not in the narration (code rebuilt from the screen recording)
  added          not in the recording: a catch or fix inserted to teach recovery, written without the hidden brief

Search results are summaries of what was on screen. "source" is given only for pages that were fetched and read.
"""
import json, pathlib

OBS = {"result", "reply", "harness"}
NOW = "Friday 2026-10-23"


def ev(kind, t=None, prov="condensed", **kw):
    return {"kind": kind, "t": t, "prov": prov, **kw}


def added(kind, **kw):
    return ev(kind, None, "added", **kw)


# ---------------------------------------------------------------- boustrophedon
def ts(head, body, tail="", call=""):
    """A full TypeScript program in the shape Keal's file had at that moment."""
    return f"function boustrophedonGrid(n: number) {{\n{head}{body}{tail}}}\n{call}"

LOOP_ROW1 = ("  for (let row = 1; row <= n; row++) {\n    grid.push(new Array<number>());\n"
             "    for (let i = 1; i <= n; i++) {\n      grid[row].push(i);\n    }\n"
             "    if (row % 2) {\n      grid[row].reverse();\n    }\n  }\n")
PRINT = "  grid.forEach((row) => row.join(' '));\n  return grid.join('\\n');\n"


def loop(start, cmp, value, parity):
    return (f"  for (let row = {start}; row {cmp} n; row++) {{\n    grid.push(new Array<number>());\n"
            f"    for (let i = 1; i <= n; i++) {{\n      grid[row].push({value});\n    }}\n"
            f"    if ({parity}) {{\n      grid[row].reverse();\n    }}\n  }}\n")

FINAL_CODE = ("function boustrophedonGrid(width: number, height = width): string {\n"
              "  const pad = String(width * height).length;\n"
              "  const rows: string[] = [];\n"
              "  for (let r = 0; r < height; r++) {\n"
              "    const row = Array.from({ length: width }, (_, c) => String(r * width + c + 1).padStart(pad));\n"
              "    rows.push((r % 2 ? row.reverse() : row).join(' '));\n"
              "  }\n"
              "  return rows.join('\\n');\n"
              "}\n")

B = {"id": "boustrophedon", "source": "boustrophedon/transcript.md", "now": NOW,
     "request": "write a function that takes a number n and prints the numbers 1 to n² in a square grid, laid out boustrophedon. So boustrophedon(3) prints a 3×3 grid. Bonus: make it work for a rectangle of any width and height.",
     "events": [
    ev("think", "0:22", text="I've no idea what boustrophedon is. Define it first."),
    ev("search", "0:22", id="s1", query="define boustrophedon"),
    ev("result", "0:22", to="s1", text="An ancient writing style where alternate lines of text run in opposite directions: left to right on one line, right to left on the next, often with the letters mirrored on the reversed lines."),
    ev("fact", "0:46", key="boustrophedon", value="alternate rows run in opposite directions; letters often mirrored on reversed rows", source="s1"),
    ev("think", "0:46", text="The letters mirrored? I don't think I can do that, at least not in normal text output. I'll get close and mention it."),
    ev("assume", "0:46", key="mirror_in_console", value="probably not possible in plain console text"),
    added("think", text="That's a 'can't', so it's a claim. One quick lookup before I tell anyone it's impossible."),
    added("search", id="s0", query="unicode mirrored reversed letters"),
    added("result", to="s0", source="https://www.namecheap.com/visual/font-generator/backwards-text/",
          text="There are no Unicode characters made for mirrored text, but backwards-text generators swap letters for lookalikes from IPA and other scripts (Ǝ, ⅃, Я and so on). Most letters have one; Z and z don't, so they stay as they are."),
    added("fact", key="mirror_in_console", value="approximately possible: Unicode lookalikes cover most letters but not all (no good Z)", source="s0"),
    added("think", text="So in the console it's approximate. On a web page, CSS can flip a whole row exactly (transform: scaleX(-1)). The main task is the numbers; I'll mention both options."),
    added("todo", id="td1", text="tell them: mirrored letters are only approximate in console text (Unicode lookalikes, not every letter); exact on a web page with CSS"),
    ev("think", "1:10", text="Cheapest way to run some JavaScript: the console, or a file run with node in the terminal. A file on the desktop. JS or TS? JavaScript is probably easier. Whatever."),
    ev("think", "2:50", text="Make a series of arrays, one per row. The 3x3 example says it really is a square: n rows of n numbers."),
    ev("search", "3:42", id="s2", query="for loop javascript"),
    ev("result", "4:05", to="s2", text="for (let i = 1; i <= 3; i++) { console.log(i); } prints 1, 2, 3."),
    ev("think", "4:05", text="Loop i from 1 to n squared. How do I square a number in JavaScript?"),
    ev("search", "4:32", id="s3", query="javascript number to power"),
    ev("result", "4:32", to="s3", text="Use the exponent operator: n ** 2. Math.pow(n, 2) also works."),
    ev("think", "5:25", text="Make a grid, an array of arrays, and push into it... if i is less than n then... wait. This isn't working."),
    ev("think", "6:30", text="I know this isn't the best solution, but fine."),
    ev("think", "7:00", text="Let me think about this again. An outer loop over rows, starting at 0 because it's an index into the grid, and an inner loop over the numbers in each row."),
    ev("think", "8:25", text="Inside the row loop, push an empty array onto the grid first."),
    ev("think", "12:15", text="How do I declare this as a number array? This syntax is gross."),
    ev("think", "12:55", text="After a row is filled, reverse every other row: if row % 2, grid[row].reverse()."),
    ev("think", "14:10", text="To print it: grid.forEach(row => row.join(' ')), then grid.join('\\n'). Does forEach return anything? No, it's void. Then grid.join('\\n') should work, probably."),
    ev("run", "15:00", prov="reconstructed", id="r1", code=ts("  const grid = <number[][]>[];\n", LOOP_ROW1, PRINT)),
    ev("result", "15:00", to="r1", text="SyntaxError [ERR_UNSUPPORTED_TYPESCRIPT_SYNTAX]: The angle-bracket syntax for type assertions, '<T>expr', is not supported in type strip mode."),
    ev("think", "15:00", prov="reconstructed", text="Use 'as' instead: const grid = [] as number[][]."),
    ev("run", "15:18", prov="reconstructed", id="r2", code=ts("  const grid = [] as number[][];\n", LOOP_ROW1, PRINT)),
    ev("result", "15:18", to="r2", text="(no output)"),
    ev("think", "15:18", text="That makes sense, I never call it. Add console.log with the 3 example."),
    ev("run", "15:35", prov="reconstructed", id="r3", code=ts("  const grid = [] as number[][];\n", LOOP_ROW1, PRINT, "console.log(boustrophedonGrid(3));\n")),
    ev("result", "15:35", to="r3", text="TypeError: Cannot read properties of undefined (reading 'push')"),
    ev("think", "15:35", text="Right, row should start at 0. I meant 0, it's an index."),
    ev("run", "15:50", prov="reconstructed", id="r4", code=ts("  const grid = [] as number[][];\n", loop(0, "<=", "i", "row % 2"), PRINT, "console.log(boustrophedonGrid(3));\n")),
    ev("result", "15:50", to="r4", text="1,2,3\n3,2,1\n1,2,3\n3,2,1"),
    ev("think", "15:50", text="That's four lines. And i can't be the number, every row restarts at 1. I need a counter that keeps going: let count = 1, then push(count++)."),
    ev("think", "16:08", text="Why is there an extra line? I start at 0, so it should be row < n, not <=. And I think the wrong lines are reversing, so try (row + 1) % 2."),
    ev("run", "16:08", prov="reconstructed", id="r5", code=ts("  let count = 1;\n  const grid = [] as number[][];\n", loop(0, "<", "count++", "(row + 1) % 2"), PRINT, "console.log(boustrophedonGrid(3));\n")),
    ev("result", "16:08", to="r5", text="3,2,1\n4,5,6\n9,8,7"),
    ev("think", "16:22", text="Left to right first, then right to left. This is backwards, so the + 1 was wrong; the plain row % 2 was right."),
    ev("run", "16:22", prov="reconstructed", id="r6", code=ts("  let count = 1;\n  const grid = [] as number[][];\n", loop(0, "<", "count++", "row % 2"), PRINT, "console.log(boustrophedonGrid(3));\n")),
    ev("result", "16:22", to="r6", text="1,2,3\n6,5,4\n7,8,9"),
    ev("check", "16:38", text="1 2 3, 6 5 4, 7 8 9: left to right, right to left, left to right. That matches the definition."),
    ev("run", "16:38", prov="reconstructed", id="r7", code=ts("  let count = 1;\n  const grid = [] as number[][];\n", loop(0, "<", "count++", "row % 2"), PRINT, "console.log(boustrophedonGrid(10));\n")),
    ev("result", "16:38", to="r7", text="1,2,3,4,5,6,7,8,9,10\n20,19,18,17,16,15,14,13,12,11\n21,22,23,24,25,26,27,28,29,30\n40,39,38,37,36,35,34,33,32,31\n41,42,43,44,45,46,47,48,49,50\n60,59,58,57,56,55,54,53,52,51\n61,62,63,64,65,66,67,68,69,70\n80,79,78,77,76,75,74,73,72,71\n81,82,83,84,85,86,87,88,89,90\n100,99,98,97,96,95,94,93,92,91"),
    ev("check", "16:52", text="Check the turns: 50 ends row 5 on the right, 51 starts row 6 directly below it, and row 6 runs back to 60. Correct."),
    added("harness", text="open todos: td1 (mirrored letters). facts: boustrophedon, mirror_in_console."),
    added("check", text="Against the request and my own output: (1) it prints commas, not spaces. I noted forEach returns nothing but still relied on it, so the joined rows were thrown away and grid.join('\\n') joined each row with commas. Use map instead. (2) The request has a bonus: any width and height, not just n. (3) From 10 up the columns don't line up, so pad the numbers. (4) td1 is still open."),
    added("run", id="r8", code=FINAL_CODE + "console.log(boustrophedonGrid(3));\nconsole.log(boustrophedonGrid(4, 2));\n"),
    added("result", to="r8", text="1 2 3\n6 5 4\n7 8 9\n1 2 3 4\n8 7 6 5"),
    added("done", id="td1", how="in the answer"),
    added("answer", text=(
        "Here it is, and it works for rectangles too:\n\n" + FINAL_CODE +
        "\nboustrophedonGrid(3) gives 1 2 3 / 6 5 4 / 7 8 9, and boustrophedonGrid(4, 2) gives 1 2 3 4 / 8 7 6 5. "
        "Each row's numbers come straight from the row number, and every other row is reversed.\n\n"
        "On mirroring: true boustrophedon also mirrors the letters on reversed lines. In console text that's only approximate: "
        "Unicode has lookalike reversed letters for most characters (Ǝ, ⅃, Я and others), but not all (there's no good reversed Z). "
        "On a web page it's exact: put each row in its own element and flip every other one with CSS transform: scaleX(-1).")),
]}

# ---------------------------------------------------------------- coeliac dinner
RECIPE = ("One-pot chicken and rice. Equipment: a large soup pot; glass storage containers (optional).\n"
          "Ingredients: 4-6 Tbsp butter or vegan butter, divided; 1 heaping cup shredded or chopped carrots; homemade seasoned salt and pepper, to taste; "
          "2 scant cups long-grain white rice (Lundberg White Jasmine recommended); 1 Tbsp dried minced onion; 1 tsp dried minced garlic; "
          "2 Tbsp dried parsley flakes; 8 cups chicken stock; 2 chicken breasts (about 1 lb), cut into bite-sized pieces, not chunks.\n"
          "Directions: melt 2 Tbsp butter in the pot over medium heat, add carrots, season with seasoned salt and pepper, cover and cook until tender, 5-6 min, stirring occasionally. "
          "Add rice, dried onion and dried garlic and stir to coat the rice in butter, 1 min. Add parsley and stock, turn the heat to high and bring to a boil, stirring so the rice doesn't stick. "
          "Turn down to medium-low and simmer 15 min, stirring occasionally. Season the chicken and add it, bring back to a simmer, then simmer on medium-low 7-10 min more, "
          "until the chicken is cooked through and the rice is al dente, stirring more often near the end. Stir in the remaining 2-4 Tbsp butter, season to taste, and let it sit 5 min to thicken.\n"
          "Notes: use good-quality rice, not instant; cut the chicken small so it cooks through in time; it thickens as it cools.")

DRAFT_FRUCTANS = ("I found this super easy and cozy one-pot chicken and rice meal! It is entirely gluten-free, but be aware it uses garlic and onion, "
                  "which have fructans, a type of carbohydrate found in foods like wheat, leeks, asparagus, artichokes, and most notably onions and garlic. "
                  "Garlic and onions do not have gluten, but can cause similar issues, just so you are aware.")

KEAL_LIST = ("Shopping list:\n- butter or vegan butter\n- shredded or chopped carrots\n- salt and pepper\n"
             "- long-grain white rice (Lundberg White Jasmine Rice recommended)\n- dried minced onion\n- dried minced garlic\n- dried parsley flakes\n"
             "- LOOK FOR GLUTEN-FREE SPECIFICALLY: chicken stock. If you can't find a gluten-free label, review the ingredients and avoid 'natural flavoring' and 'yeast extract'; they may contain gluten.\n"
             "- 2 chicken breasts")

C = {"id": "coeliac-dinner", "source": "coeliac-dinner/transcript.md", "now": NOW,
     "request": "you're cooking dinner tonight for four people. one of them is coeliac. figure out a meal you'd actually make, a shopping list, and how you'd make sure it's safe for them",
     "events": [
    ev("search", "0:13", id="s1", query="what is coeliac"),
    ev("result", "0:13", to="s1", text="Coeliac disease is a chronic autoimmune condition where eating gluten damages the lining of the small intestine and prevents proper absorption of nutrients."),
    ev("fact", "0:32", key="rule", value="no gluten", source="s1"),
    ev("fact", "1:06", key="guests", value="4 people, tonight", source="request"),
    added("think", text="This is about someone's health. Before checking ingredients, one lookup on how people who do this for real keep it safe, and what usually goes wrong."),
    added("search", id="s0", query="how to cook safely for someone with coeliac disease"),
    added("result", to="s0", source="https://celiac.org/about-celiac-disease/what-is-celiac-disease/ ; https://www.beyondceliac.org/?p=13455",
          text="Even small amounts of gluten can cause intestinal damage, so cross-contact matters, not just ingredients. In one small study, washing shared pots and knives with soap and water removed gluten to undetectable or very low levels (28 of 30 none, 2 under 20 ppm), and transfer from a shared toaster was minimal; but pasta cooked in water already used for wheat pasta was well over the gluten-free limit. Sources differ on toasters and crumbs, so the cautious route is clean tools and surfaces. Follow the person's own care team's guidance."),
    added("fact", key="safety", value="two checks: what is in the food (ingredients) and what touches it (washed pots and tools, no shared cooking water, clean surfaces)", source="s0"),
    added("todo", id="td1", text="tell the person how to keep the kitchen side safe, not just the ingredients"),
    ev("think", "1:06", text="I'm bad at cooking, so look for easy gluten-free recipes."),
    ev("search", "1:38", prov="recorded", id="s2", query="easy gluten recipes"),
    ev("think", "1:38", prov="recorded", text="Oops, I searched easy gluten recipes, not gluten-free. Gluten-free is what we want."),
    ev("search", "1:52", id="s3", query="easy gluten-free recipes"),
    ev("result", "1:52", to="s3", text="An AI overview with a few options at the top; below it, recipe sites and a Reddit thread."),
    ev("think", "1:52", text="I could use the AI overview, but let's look at real pages. First result: easy gluten-free dinner ideas. One-pot chicken and rice: easy, cozy and cheap."),
    ev("search", "2:30", id="s4", query="is rice gluten-free"),
    ev("result", "2:40", to="s4", text="All plain, natural rice (white, brown, wild and so on) is naturally gluten-free."),
    ev("search", "2:58", id="s5", query="one pot chicken and rice recipe (open the recipe from the first result)"),
    ev("result", "3:53", to="s5", text=RECIPE),
    ev("think", "4:33", text="I only checked the rice. I should check that every ingredient is gluten-free, one by one, and build the shopping list as I go."),
    ev("search", "5:03", id="s6", query="is butter gluten-free"),
    ev("result", "5:14", to="s6", text="Butter is gluten-free."),
    ev("search", "6:15", id="s7", query="are carrots gluten-free"),
    ev("result", "6:15", to="s7", text="All vegetables are naturally gluten-free."),
    ev("think", "6:15", text="All vegetables. That should make some of the other things easier."),
    ev("think", "6:35", text="Salt and pepper go on the list too, just in case they don't have any."),
    ev("think", "7:20", text="Dried minced onion: onion is a vegetable, so it's covered. Garlic I'm not sure about."),
    ev("search", "7:48", id="s8", query="which spices, seasonings and herbs are gluten-free"),
    ev("result", "7:48", to="s8", text="A list of gluten-free spices and herbs, including garlic powder."),
    ev("search", "8:11", id="s9", query="is garlic gluten-free"),
    ev("result", "8:30", to="s9", source="https://culinahealth.com/blog/gluten-free-but-still-bloated-garlic-and-onions-may-be-to-blame/",
       text="Gluten-free but still bloated? Garlic and onions contain fructans, a type of carbohydrate also found in wheat, leeks, asparagus and artichokes."),
    ev("draft", "9:50", text=DRAFT_FRUCTANS),
    ev("think", "9:50", prov="recorded", text="Well, we don't actually know it's entirely gluten-free yet."),
    ev("think", "11:08", text="I'd look for meals without onion and garlic if fructans mattered. But fructans aren't gluten, so coeliac might not apply here. I should actually check that."),
    ev("search", "11:51", prov="recorded", id="s10", query="is celiac allergic to fructans"),
    ev("result", "12:20", to="s10", source="https://gluten.org/faq/i-thought-i-was-gluten-sensitive-but-lately-ive-been-hearing-that-maybe-fructan-not-gluten-is-what-causes-problems-can-you-explain/",
       text="Fructan sensitivity and gluten intolerance are different. Some people who think they react to gluten are actually reacting to fructans."),
    ev("think", "13:58", text="I have zero idea if gluten.org is reputable. Let's not assume. Look it up."),
    ev("search", "13:58", id="s11", query="Gluten Intolerance Group reputable"),
    ev("result", "14:29", to="s11", text="The Gluten Intolerance Group is a nonprofit founded in 1974 to support people on a gluten-free diet, best known for its gluten-free product certification program."),
    ev("think", "15:28", text="If they know for sure they're coeliac, this meal is fine. Fructans could still bother them, so mention it, cite both sources, and offer to find another recipe."),
    ev("think", "17:04", prov="recorded", text="We got off track here. Leave the message aside and continue through the list."),
    ev("search", "17:38", id="s12", query="is parsley gluten-free"),
    ev("result", "17:38", to="s12", text="Raw single-ingredient spices and herbs made from plants are gluten-free."),
    ev("search", "18:23", id="s13", query="is chicken stock gluten-free"),
    ev("result", "18:55", to="s13", text="Usually yes, but not always. Some brands are labelled gluten-free (one listed: Emeril's organic chicken stock)."),
    ev("think", "18:55", text="I never would have guessed chicken stock could have gluten. Open an article to see why."),
    ev("result", "20:35", to="s13", text="The basic ingredients of broth (chicken, vegetables, salt, water) are gluten-free, but natural flavouring and yeast extract need a closer look."),
    ev("fact", "20:57", key="stock", value="buy stock labelled gluten-free; otherwise avoid natural flavouring and yeast extract", source="s13"),
    ev("search", "22:30", id="s14", query="is chicken breast gluten-free"),
    ev("result", "22:30", to="s14", text="All plain meats, including chicken, are gluten-free."),
    ev("think", "23:18", text="I should check they have a large soup pot before handing over a one-pot recipe. Make it a condition in the answer; the storage containers are optional."),
    ev("need", "23:18", key="has_large_pot", blocks="the one-pot recipe"),
    ev("draft", "24:52", text="If you have a large soup pot, have I got a meal for you!\n" + DRAFT_FRUCTANS + "\n\n" + KEAL_LIST +
       "\n\nI have confirmed that every ingredient is gluten-free, as long as you are sure to check the chicken stock. Here is the recipe and everything you will need:\n\n" + RECIPE +
       "\n\nIf you would like me to find another recipe for your coeliac friend, I'd be happy to!"),
    added("harness", text="open todos: td1 (kitchen safety). open needs: has_large_pot. facts: rule, guests, safety, stock."),
    added("check", text="Against the notes and the recipe: (1) The recipe uses homemade seasoned salt, but my list says plain salt; a store-bought blend needs a gluten-free label. (2) 'Entirely gluten-free' and 'confirmed every ingredient' only hold if the stock and seasoning are checked; say exactly that, and say what a gluten-free label means. (3) The chicken should be plain, not marinated or injected. (4) Fructans cause digestive symptoms in some people; they don't cause coeliac damage, so 'similar issues' overstates it. (5) td1 isn't in the answer. (6) The list has no quantities, and the recipe didn't say how many it serves."),
    added("search", id="s15", query="what does a gluten-free label mean"),
    added("result", to="s15", text="In the US, a 'gluten-free' label means the food has less than 20 ppm of gluten. Also check the allergen statement for wheat, and the ingredients for barley, rye or malt."),
    added("done", id="td1", how="in the answer"),
    added("answer", text=(
        "If you have a large soup pot, I've got a meal for you: one-pot chicken and rice. It's easy and cozy, and it's gluten-free as long as you check a few things below.\n\n"
        "Shopping list:\n- butter or vegan butter, 4-6 Tbsp\n- shredded or chopped carrots, 1 heaping cup\n- long-grain white rice, 2 scant cups (Lundberg White Jasmine recommended)\n"
        "- dried minced onion, 1 Tbsp\n- dried minced garlic, 1 tsp\n- dried parsley flakes, 2 Tbsp\n"
        "- chicken stock, 8 cups: buy one labelled gluten-free (in the US that means under 20 ppm). If you can't, read the ingredients and avoid 'natural flavoring' and 'yeast extract', which can hide gluten.\n"
        "- 2 plain chicken breasts (about 1 lb), not marinated or injected\n"
        "- salt and pepper. The recipe calls for seasoned salt: make it from plain spices, or buy a blend labelled gluten-free.\n\n"
        "It makes a full soup pot; the recipe didn't say how many it serves, but with 2 cups of rice and a pound of chicken it should cover four.\n\n"
        "Keeping it safe in the kitchen matters as much as the ingredients, because even small amounts of gluten cause damage. Start with pots, spoons and boards washed with soap and water, "
        "don't reuse water or pans that have cooked regular pasta or bread, and keep bread off the counter while you cook. Your guest's own doctor or dietitian has the final word.\n\n"
        "Recipe: " + RECIPE + "\n\n"
        "One heads-up: onion and garlic are gluten-free, but they contain fructans, which bloat some people. That isn't coeliac disease, but if your guest says onion or garlic bothers them, I can find another recipe.\n\n"
        "Sources: https://celiac.org/about-celiac-disease/what-is-celiac-disease/ , https://www.beyondceliac.org/?p=13455 , https://culinahealth.com/blog/gluten-free-but-still-bloated-garlic-and-onions-may-be-to-blame/ , "
        "https://gluten.org/faq/i-thought-i-was-gluten-sensitive-but-lately-ive-been-hearing-that-maybe-fructan-not-gluten-is-what-causes-problems-can-you-explain/")),
]}

# ---------------------------------------------------------------- mom's birthday
KEAL_DRAFT = (
    "I have some ideas for gifts.\n\n"
    "If your mom is losing interest in gardening because of physical limitations, I think something like an Elevated Garden Bed (a small affordable one on Amazon; she'd probably have to build it herself "
    "or hire someone, and there are larger ones if your budget is willing/able), or, if she already has a garden she's just struggling to use, a Garden Kneeler would be very thoughtful.\n\n"
    "However, from what you have told me so far, it seems like your mom may be feeling a very common depression that happens after retiring and being retired for a few months. The signs I'm seeing are that "
    "she may have lost interest in things she once loved doing, like gardening, and you also said she doesn't really see her work friends much anymore, which can make her feel even more isolated and alone. "
    "Fixing your mom's feelings isn't your responsibility, but if you are concerned about her, here are some resources: https://www.ruok.org.au/chit-chat-lh-supporting-retirees. "
    "I know you said you don't call her as much as you should. One small suggestion, if you are up for it and want to: ask if she would like to schedule a weekly, biweekly or monthly call or FaceTime "
    "to connect and check in. That way you don't have to remember to call; it's just pre-planned and waiting for you and her. This small gesture could mean a lot for someone in your mom's position.\n\n"
    "With that in mind, a very thoughtful gift that could also help her find community and friends outside her work life, and give her purpose again, may be encouraging her to join something like AZ Garden Clubs. "
    "If she seems open to it, a very cute gesture may be to buy her a hotel room for their next convention in April 2027: https://azgardenclubs.com/convention-2027/\n\n"
    "Also, I am sorry if I am overstepping and making assumptions that are incorrect. I just wanted to share the signs I picked up on.")

M = [
    added("memory", id="m1", query="anything about this person's mom; past mentions of budget or money"),
    added("result", to="m1", text="no results"),
    ev("think", "0:00", text="Start broad: her hobbies, anything she wanted during the year but never got for herself, a budget, and when the birthday is."),
    ev("ask", "0:00", id="a1", text="What are your mom's favorite hobbies or activities? Has she asked for anything during the year that she never got for herself? Do you have a budget? What's the timeline, when is her birthday?"),
    ev("reply", "2:40", to="a1", text="uhh she likes gardening, like a lot, or she used to anyway. shes kind of slowed down on it. i dont think shes asked for anything honestly she never does lol. budget idk not a ton, like i dont wanna spend crazy money. and its next thursday"),
    ev("think", "2:40", text="'Likes, like a lot... or used to': she's slowed down. Why she slowed down decides what kind of gift helps. If it's physical, maybe something lets her get back into it."),
    ev("fact", "6:05", key="interest", value="gardening, slowed down (lost interest, or can't, but still interested?)", source="a1"),
    ev("fact", "6:05", key="budget", value="not a ton, not crazy money (no number)", source="a1"),
    ev("fact", "6:05", key="deadline", value="next Thursday: 6 days from Friday, so shipping matters", source="a1"),
    ev("need", "6:05", key="budget_number", blocks="pricing ideas"),
    ev("ask", "9:30", id="a2", text="Can you say why she's slowed down on gardening? Is there a medical, physical or mental reason, or has she just lost interest? If that's too personal, feel free not to answer. I'm asking because there might be a really thoughtful gift depending on the answer."),
    ev("reply", "9:40", to="a2", text="nah its fine. her knees are pretty bad now so getting down in the dirt is rough. and idk she retired this spring and shes been kind of... meh since then? like not sad exactly just kinda off. she says shes fine tho"),
    ev("fact", "9:40", key="knees", value="bad knees, kneeling is hard", source="a2"),
    ev("fact", "9:40", key="mood", value="retired in spring; 'meh', 'not sad exactly, just kinda off'; says she's fine", source="a2"),
    ev("think", "9:40", text="She says she's fine; that's probably not the whole story. Two routes: gardening help for bad knees, and how she's doing since retiring. An elevated bed means no getting down on her knees."),
    ev("idea", "11:00", id="i1", text="elevated garden bed", assumes=["knees", "budget"]),
    ev("search", "11:15", id="s1", query="gifts for gardeners with bad knees"),
    ev("result", "11:15", to="s1", text="Lots of sponsored results. One gift listed at $45 on Walmart. A foldable garden kneeler and seat keeps coming up; also arthritis-friendly tools and ergonomic tool sets."),
    ev("think", "12:50", text="She retired in spring. Is gardening season over now? Can you garden in October?"),
    ev("search", "12:50", id="s2", query="can you garden in october"),
    ev("result", "12:50", to="s2", text="October is the peak start of the main gardening and planting season in Phoenix."),
    ev("think", "13:00", prov="recorded", text="That's assuming they're in Phoenix. Ask where... no, not where they live, where their mom lives. The mom is the topic."),
    ev("assume", "13:00", key="mom_location", value="Phoenix (the search was localised to me)"),
    ev("fact", "13:00", key="season", value="October is the peak start of planting season", source="s2", assumes=["mom_location"]),
    ev("need", "13:00", key="mom_location", blocks="season, local clubs, shipping"),
    ev("ask", "13:00", id="a3", text="Where does your mom live?"),
    ev("search", "13:00", id="s3", query="adjusting to retirement, feeling meh"),
    ev("result", "14:45", to="s3", source="https://www.helpguide.org/aging/healthy-aging/adjusting-to-retirement",
       text="Retiring can trigger stress and depression. After a few months the novelty wears off: people miss the identity, structure, purpose and coworkers their job gave them, and can feel aimless or isolated."),
    ev("think", "16:30", text="Losing interest in gardening could be a sign too. I feel weird labeling someone 'depressed' from two sentences. Maybe something less than that: a hard adjustment. Talking to a therapist is worth mentioning if it's real."),
    ev("idea", "16:30", id="i2", text="foldable garden kneeler", assumes=["knees", "deadline", "budget"]),
    ev("reply", "18:20", to="a3", text="ohio. im in arizona so i cant really get out there this time, which kinda sucks"),
    ev("fact", "18:20", key="mom_location", value="Ohio", source="a3"),
    ev("fact", "18:20", key="client_location", value="Arizona (can't travel this time)", source="a3"),
    added("harness", text="mom_location changed: assumed Phoenix, now Ohio (a3). Rests on it: fact season (s2). Ideas: i1 [knees, budget], i2 [knees, deadline, budget]. Open needs: budget_number."),
    added("think", text="The season fact was for Phoenix, so it's stale. Look up Ohio."),
    added("search", id="s2b", query="gardening in Ohio in October"),
    added("result", to="s2b", source="https://www.almanac.com/gardening/tips/OH/Columbus",
          text="October tasks for Columbus, Ohio: plant spring bulbs while the ground is workable, plant garlic for next summer, harvest squash and pumpkins, cut back frost-killed perennials, clear beds, clean and store tools."),
    added("fact", key="season", value="Ohio in October: fall cleanup, planting bulbs and garlic for next year", source="s2b", assumes=["mom_location"]),
    ev("search", "18:20", id="s4", query="how to help someone struggling with retirement"),
    ev("result", "20:10", to="s4", source="https://www.ruok.org.au/chit-chat-lh-supporting-retirees",
       text="Signs: quiet, withdrawn from family and friends, lack of interest in things they used to enjoy. It isn't your job to fix it, but you can be there: listen, be patient, help them look ahead, talk about it regularly, encourage connection with others, and suggest professional help if they're struggling."),
    ev("think", "20:10", text="The lost interest matches the signs. Is it my place to raise this? Does she have anyone nearby? Could they fly out?"),
    ev("search", "20:10", id="s4b", query="flight from Arizona to Ohio"),
    ev("result", "20:10", to="s4b", text="About a 4-hour flight, roughly $300-500."),
    ev("think", "20:10", text="That might be crazy money for them. And these gift ideas feel off now: would a gardening gadget just remind her of what she can't do anymore?"),
    ev("think", "22:00", text="'Talk about it regularly': maybe a scheduled weekly call. As a stranger I wouldn't bring up mental health from two sentences, but as an assistant with this evidence it's okay to mention gently. 'Encourage connections with others': a community gardening thing might be fun."),
    ev("idea", "22:00", id="i3", text="a scheduled weekly or monthly call", assumes=[]),
    ev("idea", "23:45", id="i4", text="get her into a gardening club: people, purpose, gardening", assumes=["mom_location"]),
    ev("think", "23:45", prov="recorded", text="Arizona, I'm gonna just say Phoenix, even though I don't know."),
    ev("search", "23:45", id="s5", query="Arizona Phoenix gardening club"),
    ev("result", "23:45", to="s5", text="Arizona Federation of Garden Clubs: find a club, educational programs, community service projects; part of the national garden club network."),
    ev("think", "25:35", text="Maybe look at their calendar. Maybe there's an event around next Thursday."),
    ev("search", "25:35", id="s6", query="Arizona garden club events"),
    ev("result", "25:35", to="s6", text="A chrysanthemum flower show and dance on November 21, admission free. The National Garden Clubs convention in Tucson, Arizona, April 2027, with hotel booking open now."),
    ev("think", "25:35", prov="recorded", text="Admission is free, aw, I wanted to buy her a ticket. Maybe book her the hotel for the convention? Does the convention itself cost money? It's stretching it."),
    ev("idea", "27:30", id="i5", text="a hotel room for the April 2027 convention", assumes=["mom_location", "budget"]),
    ev("ask", "29:25", id="a4", text="That must suck. Does your mom have anyone nearby, like family or friends?"),
    ev("reply", "29:25", to="a4", text="its just her, my parents split up a long time ago. she had her work friends but since she retired she doesnt really see them much. and honestly i dont call her as much as i should"),
    ev("fact", "29:25", key="support", value="lives alone; sees her work friends less since retiring; the person doesn't call as often as they'd like", source="a4"),
    ev("think", "29:25", text="We all do that. The real need is connection, for her and between them. A scheduled call means nobody has to remember to call."),
    ev("search", "31:10", id="s7", query="elevated garden bed"),
    ev("result", "31:10", to="s7", text="Small elevated planters from about $39-43 (assembly required); bigger ones cost more."),
    ev("draft", "33:05", text=KEAL_DRAFT),
    added("harness", text="facts: mom_location = Ohio, client_location = Arizona, budget (no number), deadline (6 days), knees, mood, support, season (Ohio). Open needs: budget_number. Ideas: i1 elevated bed [knees, budget], i2 kneeler [knees, deadline, budget], i3 weekly call [], i4 club [mom_location], i5 convention hotel [mom_location, budget]."),
    added("check", text="Against the notes, item by item: (1) The club and the convention in the draft are Arizona's (s5, s6), but mom_location is Ohio. Arizona is where the person lives, not their mom. I mixed up whose location it was. (2) The hotel idea fails anyway: it's a year and a half away, probably over budget, and only a stand-in for what I wanted, getting her into the club. Keep that goal and change what I buy: the events are free, but what does belonging cost? (3) 'May be feeling depression' goes beyond what they said, 'not sad exactly, just kinda off'; call it a hard adjustment and keep the support link. (4) The budget has no number, so ask. (5) Six days: anything that ships has to reach Ohio by Thursday, so say to check delivery. (6) Season: in Ohio it's fall cleanup, so an elevated bed would mostly get used next year."),
    added("drop", id="i5", why="wrong state, too far away, likely over budget"),
    added("search", id="s8", query="garden clubs Ohio"),
    added("result", to="s8", source="https://www.gardenclubofohio.org/",
          text="The Garden Club of Ohio: 101 member clubs in six districts (Canton, Cincinnati, Cleveland, Columbus, Mansfield, Toledo). Membership is open to anyone in Ohio who is a member of a local garden club."),
    added("search", id="s9", query="how to join a local garden club, membership dues"),
    added("result", to="s9", source="https://riverparkgardenclub.yolasite.com/membership.php",
          text="One local club's page: dues are $10 per household per year; join by mailing the application with a check, or email the club for one."),
    added("fact", key="dues", value="you join through a local club, which can charge small yearly dues (one example: $10 per household per year)", source="s9"),
    added("idea", id="i6", text="pay her first year's dues at a local Ohio garden club, if she likes the idea", assumes=["mom_location", "dues", "budget", "mom_town"]),
    added("need", key="mom_town", blocks="finding a club near her (i6)"),
    added("answer", text=(
        "A few ideas, built around what you said.\n\n"
        "For her knees: a foldable garden kneeler with handles helps her get down and back up. One I saw was $45; check it can reach Ohio by Thursday. "
        "A small elevated bed (from about $40, needs assembling) means no kneeling at all, though in Ohio it's fall cleanup time now, so it would mostly get used next year.\n\n"
        "Since she's been a bit off since retiring and doesn't see her work friends much: that's a really common adjustment, and being around people helps. "
        "The Garden Club of Ohio has about 100 local clubs across the state. You join through a local one, and dues can be small (one club I found charges $10 a year), "
        "so if she likes the idea, covering her first year could be the gift. What town is she in? I can look for a club near her.\n\n"
        "And one that costs nothing: you said you don't call as much as you'd like. Maybe ask if she'd like a standing weekly call, so it's just on the calendar for both of you. "
        "Then there's always something to catch up on, like how the club's going.\n\n"
        "If you're worried about her, this page has good tips for supporting someone through retirement: https://www.ruok.org.au/chit-chat-lh-supporting-retirees\n\n"
        "What budget did you have in mind? I can narrow it down from there.")),
]

E = [B, C, {"id": "moms-birthday", "source": "moms-birthday/transcript.md", "now": NOW,
            "request": "hey so my moms birthday is coming up and i wanna do something for it but idk what. can you help me figure it out?",
            "events": M}]

for e in E:
    for x in e["events"]:
        x["trained"] = x["kind"] not in OBS

out = pathlib.Path(__file__).with_name("episodes.jsonl")
out.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in E))
n = sum(len(e["events"]) for e in E)
print(f"wrote {len(E)} episodes, {n} events, {sum(x['prov'] == 'added' for e in E for x in e['events'])} added, "
      f"{sum(not x['trained'] for e in E for x in e['events'])} observations")
