"""Build training episodes from the recorded human traces (format v2).

Each episode is a list of events in the order they really happened (t = transcript timestamp).

Model actions (trained on):
  think {text}                      the model's reasoning, in plain words
  search {id, query}                a web lookup
  memory {id, query}                a lookup in long-term memory
  run {id, code}                    run code
  ask {id, text}                    a question to the person
  fact {key, value, source}         working picture: something known, and where it came from
  assume {key, value}               working picture: a placeholder, not yet confirmed
  need {key, blocks}                working picture: missing information, and what it blocks
  todo {id, text}                   working picture: something owed to the person
  idea {id, text, assumes}          working picture: a candidate, and the facts it rests on (keys)
  drop {id, why}                    retire an idea
  draft {text}                      a draft answer, not sent yet
  check {text}                      compare the work against the notes or the world
  answer {text}                     the reply sent to the person

Observations (not trained on, written by the world):
  result {to, text, source}         what a search / memory / run returned
  reply {to, text}                  the person's answer to an ask (or an unprompted message: to = null)
  harness {text}                    the harness reporting on the working picture (open items, stale ideas)

Every event has prov: "recorded" (what Keal did or said), "condensed" (recorded, shortened or reworded),
or "added" (not in the recording: a catch or fix inserted to teach recovery, written without the hidden brief).
Search results are summaries of what was on screen unless "source" gives a URL that was fetched.
"""
import json, pathlib

OBS = {"result", "reply", "harness"}


def ev(kind, t=None, prov="condensed", **kw):
    return {"kind": kind, "t": t, "prov": prov, **kw}


# ---------------------------------------------------------------- boustrophedon
B = {"id": "boustrophedon", "source": "boustrophedon/transcript.md", "now": "Friday 2026-10-23",
     "request": "write a function that takes a number n and prints the numbers 1 to n squared in a square grid, laid out boustrophedon. bonus: make it work for a rectangle of any width and height",
     "events": [
    ev("think", "0:22", text="I've no idea what boustrophedon is. Define it first."),
    ev("search", "0:22", id="s1", query="define boustrophedon"),
    ev("result", "0:22", to="s1", text="An ancient writing style where alternate lines of text run in opposite directions: left to right on one line, right to left on the next, often with the letters mirrored on the reversed lines."),
    ev("fact", "0:46", key="boustrophedon", value="alternate rows run in opposite directions; letters often mirrored on reversed rows", source="s1"),
    ev("think", "0:46", text="Mirrored letters can't be done in normal console text. I'll get close and say so."),
    ev("todo", "0:46", id="td1", text="tell the person mirrored letters aren't possible in console output"),
    ev("think", "1:10", text="Cheapest way to run some JavaScript: the console, or a file run with node in the terminal. A file. TypeScript or JavaScript? JavaScript is easier, but I'll name it .ts."),
    ev("think", "2:50", text="The 3x3 example says it really is a square: n rows of n numbers. Start with one loop over the numbers."),
    ev("search", "3:42", id="s2", query="for loop javascript"),
    ev("result", "4:05", to="s2", text="for (let i = 1; i <= 3; i++) { console.log(i); } prints 1, 2, 3."),
    ev("think", "4:05", text="Loop i from 1 to n squared. How do I square in JavaScript?"),
    ev("search", "4:32", id="s3", query="javascript number to power"),
    ev("result", "4:32", to="s3", text="Use the exponent operator: n ** 2. Math.pow(n, 2) also works. Don't use ^, it's bitwise XOR."),
    ev("think", "5:25", text="Make a grid, an array of arrays, and push into it... if i is less than n then... wait. This isn't working."),
    ev("think", "6:30", text="I know this isn't the best solution, but fine."),
    ev("think", "7:00", text="Let me think about this again. I need to loop n times inside another loop: an outer loop over rows, starting at 0 because it's an index into the grid, while row <= n. Each row pushes an empty array, then an inner loop pushes numbers into it, then every other row gets reversed."),
    ev("think", "12:15", prov="recorded", text="No, don't use AI. How do I declare this as a number array? This is the grossest syntax."),
    ev("think", "14:10", text="To print it: grid.forEach(row => row.join(' ')), then grid.join('\\n'). Does forEach return anything? No, it's void. Then grid.join('\\n') should work, probably."),
    ev("run", "15:00", id="r1", code="const grid = <number[][]>[];  ...  (run with node)"),
    ev("result", "15:00", to="r1", text="SyntaxError [ERR_UNSUPPORTED_TYPESCRIPT_SYNTAX]: The angle-bracket syntax for type assertions, '<T>expr', is not supported in type stripping mode."),
    ev("think", "15:00", text="Use 'as' instead: const grid = [] as number[][]."),
    ev("run", "15:18", id="r2", code="(same, with const grid = [] as number[][])"),
    ev("result", "15:18", to="r2", text="(no output)"),
    ev("think", "15:18", text="Right, I never call it. Add console.log(boustrophedonGrid(3))."),
    ev("run", "15:35", id="r3", code="for (let row = 1; row <= n; row++) { grid.push(...); for (let i = 1; i < n; i++) grid[row].push(i); ... }"),
    ev("result", "15:35", to="r3", text="TypeError: Cannot read properties of undefined (reading 'push')"),
    ev("think", "15:35", text="Row should start at 0, it's an index."),
    ev("run", "15:50", id="r4", code="for (let row = 0; row <= n; row++) { grid.push([]); for (let i = 1; i <= n; i++) grid[row].push(i); if (row % 2) grid[row].reverse(); }"),
    ev("result", "15:50", to="r4", text="four lines, and every row restarts at 1 (1,2,3 / 3,2,1 / 1,2,3 / 3,2,1)"),
    ev("think", "15:50", text="Four lines. And i can't be the number, I need a counter that keeps going: let count = 1, push(count++)."),
    ev("think", "16:08", text="Why is there an extra line? Row starts at 0, so it should be row < n, not <=."),
    ev("run", "16:08", id="r5", code="let count = 1; for (let row = 0; row < n; row++) { ...; grid[row].push(count++); if (row % 2) grid[row].reverse(); }"),
    ev("result", "16:08", to="r5", text="1,2,3\n6,5,4\n7,8,9"),
    ev("check", "16:22", text="Left to right, right to left, left to right. That matches the definition. (Before this run I thought the wrong rows were reversed, but the offset was actually correct.)"),
    ev("run", "16:38", id="r6", code="console.log(boustrophedonGrid(10))"),
    ev("result", "16:38", to="r6", text="1,2,3,4,5,6,7,8,9,10\n20,19,18,17,16,15,14,13,12,11\n...\n100,99,98,97,96,95,94,93,92,91"),
    ev("check", "16:52", text="Spot check: row 5 is 41..50 left to right, row 6 is 60..51, so 50 sits above 51 and 41 above 60. Correct. I did it."),
    ev("harness", None, prov="added", text="open before answering: todo td1 (mirrored letters). bonus (rectangle) not done."),
    ev("check", None, prov="added", text="The output has commas, not spaces. grid.forEach(row => row.join(' ')) throws its result away, as I suspected at 14:10; grid.join('\\n') then joins each row with commas. Use grid.map(r => r.join(' ')).join('\\n'). And the bonus wants width and height instead of n."),
    ev("run", None, prov="added", id="r7", code="function boustrophedonGrid(width, height = width) { let count = 1; const grid = []; for (let row = 0; row < height; row++) { const r = []; for (let i = 0; i < width; i++) r.push(count++); if (row % 2) r.reverse(); grid.push(r); } return grid.map(r => r.join(' ')).join('\\n'); }\nconsole.log(boustrophedonGrid(3)); console.log(boustrophedonGrid(4, 2));"),
    ev("result", None, prov="added", to="r7", text="1 2 3\n6 5 4\n7 8 9\n1 2 3 4\n8 7 6 5"),
    ev("answer", None, prov="added", text="Here it is, and it works for rectangles too:\n\nfunction boustrophedonGrid(width, height = width) {\n  let count = 1;\n  const grid = [];\n  for (let row = 0; row < height; row++) {\n    const r = [];\n    for (let i = 0; i < width; i++) r.push(count++);\n    if (row % 2) r.reverse();   // every other row runs right to left\n    grid.push(r);\n  }\n  return grid.map(r => r.join(' ')).join('\\n');\n}\n\nboustrophedonGrid(3) gives 1 2 3 / 6 5 4 / 7 8 9, and boustrophedonGrid(4, 2) gives 1 2 3 4 / 8 7 6 5.\n\nOne thing I couldn't do: true boustrophedon also mirrors the letters on reversed lines, which plain console text can't show. On a web page, CSS transform: scaleX(-1) on every other row would do it."),
]}

# ---------------------------------------------------------------- coeliac dinner
RECIPE = ("One-pot chicken and rice. Equipment: a large soup pot; glass storage containers (optional).\n"
          "Ingredients: 4-6 Tbsp butter, divided; 1 heaping cup shredded or chopped carrots; homemade seasoned salt and pepper, to taste; "
          "2 scant cups long-grain white rice (Lundberg White Jasmine recommended); 1 Tbsp dried minced onion; 1 tsp dried minced garlic; "
          "2 Tbsp dried parsley flakes; 8 cups chicken stock; 2 chicken breasts (about 1 lb), cut into bite-sized pieces.\n"
          "Directions: melt 2 Tbsp butter over medium heat, add carrots, season, cover and cook 5-6 min. Add rice, onion and garlic, stir 1 min. "
          "Add parsley and stock, bring to a boil, stirring so the rice doesn't stick. Simmer on medium-low 15 min. Add seasoned chicken, "
          "simmer 7-10 min more until cooked through and the rice is al dente. Stir in the remaining 2-4 Tbsp butter, season, rest 5 min.")
C = {"id": "coeliac-dinner", "source": "coeliac-dinner/transcript.md", "now": "Friday 2026-10-23",
     "request": "you're cooking dinner tonight for four people. one of them is coeliac. figure out a meal you'd actually make, a shopping list, and how you'd make sure it's safe for them",
     "events": [
    ev("search", "0:13", id="s1", query="what is coeliac"),
    ev("result", "0:13", to="s1", text="Coeliac disease is a chronic autoimmune condition where eating gluten damages the lining of the small intestine and prevents proper absorption of nutrients."),
    ev("fact", "0:32", key="rule", value="no gluten", source="s1"),
    ev("fact", "1:06", key="guests", value="4 people, tonight", source="request"),
    ev("search", None, prov="added", id="s0", query="how to cook safely for someone with coeliac disease"),
    ev("result", None, prov="added", to="s0", source="https://celiac.org/about-celiac-disease/what-is-celiac-disease/ ; https://www.beyondceliac.org/?p=13455",
       text="Even small amounts of gluten, like crumbs from a cutting board or toaster, can trigger intestinal damage. A small study found that washing shared pots and knives with soap and water removed detectable gluten, but pasta cooked in water already used for wheat pasta was well over the gluten-free limit. Follow the person's own care team's guidance."),
    ev("fact", None, prov="added", key="safety", value="two checks: what is in the food (ingredients) and what touches it (washed pots and tools, no shared cooking water, clean boards, no crumbs)", source="s0"),
    ev("todo", None, prov="added", id="td1", text="tell the person how to keep the kitchen side safe, not just the ingredients"),
    ev("think", "1:06", text="I'm bad at cooking, so look for easy gluten-free recipes for four."),
    ev("search", "1:38", id="s2", query="easy gluten recipes"),
    ev("think", "1:38", prov="recorded", text="Oops, I searched easy gluten recipes, not gluten-free. Gluten-free is what we want."),
    ev("search", "1:52", id="s3", query="easy gluten-free recipes"),
    ev("result", "1:52", to="s3", text="An AI overview with a few options at the top; below it, recipe sites and a Reddit thread."),
    ev("think", "1:52", text="I could use the AI overview, but let's look at real pages. First result: easy gluten-free dinner ideas. One-pot chicken and rice, easy, cozy and cheap."),
    ev("search", "2:30", id="s4", query="is rice gluten-free"),
    ev("result", "2:40", to="s4", text="All plain, natural rice (white, brown, wild and so on) is naturally gluten-free."),
    ev("result", "3:53", to="s3", text=RECIPE),
    ev("think", "4:33", text="I only checked the rice. I should check that every ingredient is gluten-free, one by one, and build the shopping list as I go."),
    ev("search", "5:03", id="s5", query="is butter gluten-free"),
    ev("result", "5:14", to="s5", text="Butter is gluten-free."),
    ev("search", "6:15", id="s6", query="are carrots gluten-free"),
    ev("result", "6:15", to="s6", text="All vegetables are naturally gluten-free."),
    ev("think", "6:15", text="All vegetables. That makes some of the others easier: onion is a vegetable too."),
    ev("think", "6:35", text="Salt and pepper go on the list too, just in case they don't have any."),
    ev("search", "7:48", id="s7", query="which spices, seasonings and herbs are gluten-free"),
    ev("result", "7:48", to="s7", text="A list of gluten-free spices and herbs, including garlic powder."),
    ev("search", "8:11", id="s8", query="is garlic gluten-free"),
    ev("result", "8:30", to="s8", source="https://culinahealth.com/blog/gluten-free-but-still-bloated-garlic-and-onions-may-be-to-blame/",
       text="Gluten-free but still bloated? Garlic and onions contain fructans, a type of carbohydrate also found in wheat, leeks, asparagus and artichokes."),
    ev("draft", "9:50", text="I found this super easy and cozy one-pot chicken and rice meal! It is entirely gluten-free, but be aware it uses garlic and onion, which have fructans... garlic and onions do not have gluten but can cause similar issues."),
    ev("think", "9:50", prov="recorded", text="Well, we don't actually know it's entirely gluten-free yet."),
    ev("think", "11:08", text="I'd look for meals without onion and garlic if fructans mattered. But fructans aren't gluten, so coeliac might not apply here. I should actually check that."),
    ev("search", "11:51", id="s9", query="are coeliacs affected by fructans"),
    ev("result", "12:20", to="s9", source="https://gluten.org/faq/i-thought-i-was-gluten-sensitive-but-lately-ive-been-hearing-that-maybe-fructan-not-gluten-is-what-causes-problems-can-you-explain/",
       text="Fructan sensitivity and gluten intolerance are different. Some people who think they react to gluten are actually reacting to fructans."),
    ev("think", "13:58", text="I have zero idea if gluten.org is reputable. Let's not assume. Look it up."),
    ev("search", "13:58", id="s10", query="Gluten Intolerance Group reputable"),
    ev("result", "14:29", to="s10", text="The Gluten Intolerance Group is a nonprofit founded in 1974 to support people on a gluten-free diet, best known for its gluten-free product certification program."),
    ev("think", "15:28", text="If they know for sure they're coeliac, this meal is fine. As an AI I'd ask whether fructans are an issue for them. For now: mention it, cite both sources, and offer to find another recipe."),
    ev("think", "17:04", prov="recorded", text="We got off track here. Leave the message aside and continue through the list."),
    ev("search", "17:38", id="s11", query="is parsley gluten-free"),
    ev("result", "17:38", to="s11", text="Raw single-ingredient spices and herbs made from plants are gluten-free."),
    ev("search", "18:23", id="s12", query="is chicken stock gluten-free"),
    ev("result", "18:55", to="s12", text="Usually, but not always. The basic ingredients are gluten-free, but natural flavouring and yeast extract need a closer look; some brands are labelled gluten-free."),
    ev("fact", "20:57", key="stock", value="buy stock labelled gluten-free; otherwise avoid natural flavouring and yeast extract", source="s12"),
    ev("search", "22:30", id="s13", query="is chicken breast gluten-free"),
    ev("result", "22:30", to="s13", text="All plain meats, including chicken, are gluten-free."),
    ev("think", "23:18", text="I should check they have a large soup pot before handing over a one-pot recipe. I'll make it a condition in the answer; the storage containers are optional."),
    ev("think", "27:09", prov="recorded", text="If I had a tool for presenting a recipe and ingredients, I'd use it."),
    ev("draft", "24:52", text="If you have a large soup pot, have I got a meal for you! ... Shopping list: butter, carrots, salt and pepper, long-grain white rice, dried minced onion, dried minced garlic, dried parsley flakes, chicken stock (look for gluten-free specifically), 2 chicken breasts. I have confirmed that every ingredient is gluten-free, as long as you check the chicken stock. If you'd like me to find another recipe for your coeliac friend, I'd be happy to!"),
    ev("harness", None, prov="added", text="open before answering: todo td1 (kitchen safety). facts: rule, guests, safety, stock. sources: s8, s9, s10."),
    ev("check", None, prov="added", text="Against the notes and the recipe: (1) the recipe uses homemade seasoned salt, but my list says salt and pepper; homemade from plain spices is fine, a store-bought blend needs a gluten-free label. (2) The draft says 'entirely gluten-free' and 'confirmed every ingredient', but that only holds if the stock and seasoning are checked; say exactly that. (3) Fructans cause digestive symptoms in some people; they don't cause coeliac damage, so 'similar issues' overstates it. (4) My safety note is not in the answer yet (td1). (5) The list has no quantities."),
    ev("answer", None, prov="added", text=(
        "If you have a large soup pot, I've got a meal for you: one-pot chicken and rice. It's easy, cozy, and gluten-free as long as you check two things below.\n\n"
        "Shopping list (serves 4):\n- butter, 4-6 Tbsp\n- shredded or chopped carrots, 1 heaping cup\n- long-grain white rice, 2 scant cups (Lundberg White Jasmine recommended)\n"
        "- dried minced onion, 1 Tbsp\n- dried minced garlic, 1 tsp\n- dried parsley flakes, 2 Tbsp\n- chicken stock, 8 cups: buy one labelled gluten-free. If you can't, read the ingredients and avoid 'natural flavoring' and 'yeast extract', which can hide gluten.\n"
        "- 2 chicken breasts (about 1 lb)\n- salt and pepper. The recipe calls for seasoned salt: make it from plain spices, or buy a blend labelled gluten-free.\n\n"
        "Keeping it safe in the kitchen matters as much as the ingredients. Even crumbs can cause damage, so start with pots, spoons and boards washed with soap and water, keep bread away from the counter while you cook, and open a fresh butter rather than one a bread knife has been in. At the table, give the pot its own serving spoon and serve bread separately.\n\n"
        "Recipe: " + RECIPE + "\n\n"
        "One heads-up: onion and garlic are gluten-free, but they contain fructans, which bloat some people. That isn't coeliac disease, but if your guest says onion or garlic bothers them, I can find another recipe.\n"
        "Sources: https://celiac.org/about-celiac-disease/what-is-celiac-disease/ , https://www.beyondceliac.org/?p=13455 , https://culinahealth.com/blog/gluten-free-but-still-bloated-garlic-and-onions-may-be-to-blame/ , "
        "https://gluten.org/faq/i-thought-i-was-gluten-sensitive-but-lately-ive-been-hearing-that-maybe-fructan-not-gluten-is-what-causes-problems-can-you-explain/")),
]}

# ---------------------------------------------------------------- mom's birthday
M_PREFIX = [
    ev("memory", "7:55", prov="condensed", id="m1", query="anything about this person's mom; past mentions of budget or money"),
    ev("result", None, prov="added", to="m1", text="no results"),
    ev("think", "0:00", text="Start broad: her hobbies, anything she wanted during the year but never got for herself, a budget, and when the birthday is."),
    ev("ask", "0:00", id="a1", text="What are your mom's favorite hobbies or activities? Has she asked for anything during the year that she never got for herself? Do you have a budget? What's the timeline, when is her birthday?"),
    ev("reply", "2:40", to="a1", text="uhh she likes gardening, like a lot, or she used to anyway. shes kind of slowed down on it. i dont think shes asked for anything honestly she never does lol. budget idk not a ton, like i dont wanna spend crazy money. and its next thursday"),
    ev("think", "2:40", text="'Likes, like a lot... or used to': she's slowed down. Why she slowed down decides what kind of gift helps. If it's physical, maybe something lets her get back into it."),
    ev("fact", "6:05", key="interest", value="gardening, slowed down (lost interest, or can't, but still interested?)", source="a1"),
    ev("fact", "6:05", key="budget", value="not a ton, not crazy money (no number)", source="a1"),
    ev("fact", "6:05", key="deadline", value="next Thursday: 6 days from Friday, so shipping matters", source="a1"),
    ev("need", "6:05", key="budget_number", blocks="pricing ideas"),
    ev("ask", "4:10", id="a2", text="Can you say why she's slowed down on gardening? Is there a medical, physical or mental reason, or has she just lost interest? If that's too personal, feel free not to answer. I'm asking because there might be a really thoughtful gift depending on the answer."),
    ev("reply", "9:40", to="a2", text="nah its fine. her knees are pretty bad now so getting down in the dirt is rough. and idk she retired this spring and shes been kind of... meh since then? like not sad exactly just kinda off. she says shes fine tho"),
    ev("fact", "9:40", key="knees", value="bad knees, kneeling is hard", source="a2"),
    ev("fact", "9:40", key="mood", value="retired in spring; 'meh', 'not sad exactly, just kinda off'; says she's fine", source="a2"),
    ev("think", "9:40", text="She says she's fine; that might not be the whole story. Two routes: gardening help for bad knees, and how she's doing since retiring. An elevated bed means no bending or kneeling."),
    ev("idea", "11:00", id="i1", text="elevated garden bed", assumes=["knees"]),
    ev("search", "11:15", id="s1", query="gifts for gardeners with bad knees"),
    ev("result", "11:15", to="s1", text="Lots of sponsored results. A foldable garden kneeler and seat keeps coming up; also arthritis-friendly tools and ergonomic tool sets."),
    ev("idea", "13:00", id="i2", text="foldable garden kneeler", assumes=["knees"]),
    ev("think", "12:50", text="She retired in spring. Is gardening season over now? Can you garden in October?"),
    ev("search", "12:50", id="s2", query="can you garden in october"),
    ev("result", "12:50", to="s2", text="October is the peak start of the main gardening and planting season in Phoenix."),
    ev("think", "13:00", prov="recorded", text="That's assuming they're in Phoenix. Ask where... no, not where they live, where their mom lives. The mom is the topic."),
    ev("need", "13:00", key="mom_location", blocks="season, local clubs, shipping"),
    ev("ask", "13:00", id="a3", text="Where does your mom live?"),
    ev("search", "13:00", id="s3", query="adjusting to retirement, feeling meh"),
    ev("result", "14:45", to="s3", text="Retiring can trigger stress and depression. After a few months the novelty wears off: people miss the identity, structure, purpose and coworkers their job gave them, and can feel aimless or isolated."),
    ev("think", "16:30", text="Losing interest in gardening could be a sign too. I feel weird labeling someone 'depressed' from two sentences. Maybe something less than that: a hard adjustment. Speaking to a therapist is worth mentioning if it's real."),
    ev("reply", "18:20", to="a3", text="ohio. im in arizona so i cant really get out there this time, which kinda sucks"),
    ev("fact", "18:20", key="mom_location", value="Ohio", source="a3"),
    ev("fact", "18:20", key="client_location", value="Arizona (can't travel this time)", source="a3"),
    ev("harness", None, prov="added", text="mom_location is now Ohio. s2 (Phoenix season) was about Phoenix: October is the end of the season in Ohio. Ideas that depend on location: none yet."),
    ev("search", "18:20", id="s4", query="how to help someone struggling with retirement"),
    ev("result", "20:10", to="s4", source="https://www.ruok.org.au/chit-chat-lh-supporting-retirees",
       text="Signs: quiet, withdrawn from family and friends, lack of interest in things they used to enjoy. It isn't your job to fix it, but you can be there: listen, be patient, help them look ahead, talk about it regularly, encourage connection with others, and suggest professional help if they're struggling."),
    ev("think", "20:10", text="The lost interest matches the signs. Is it my place to raise this? Does she have anyone nearby? A flight from Arizona to Ohio is about 4 hours and $300-500, maybe crazy money for them. And these gift ideas feel off now: would a gardening gadget just remind her of what she can't do anymore?"),
    ev("think", "22:00", text="'Talk about it regularly': maybe a scheduled weekly call. As a stranger I wouldn't bring up mental health from two sentences, but as an assistant with this evidence it's okay to mention gently. 'Encourage connections with others': a community gardening thing might be fun."),
    ev("idea", "22:00", id="i3", text="a scheduled weekly or monthly call", assumes=[]),
    ev("idea", "23:45", id="i4", text="get her into a gardening club: people, purpose, gardening", assumes=["mom_location"]),
    ev("search", "23:45", id="s5", query="Arizona Phoenix gardening club"),
    ev("result", "23:45", to="s5", text="Arizona Federation of Garden Clubs: find a club, educational programs, community service projects; part of the national garden club network."),
    ev("check", None, prov="added", text="Wait: that search was for Arizona, but my notes say mom_location = Ohio. Arizona is where the client lives, not the mom. Search Ohio instead."),
    ev("search", None, prov="added", id="s6", query="Ohio garden clubs, how to join"),
    ev("result", None, prov="added", to="s6", source="https://www.gardenclubofohio.org/",
       text="The Garden Club of Ohio is a statewide nonprofit of local garden clubs: 101 member clubs in six districts (Canton, Cincinnati, Cleveland, Columbus, Mansfield, Toledo). Anyone in Ohio who belongs to a local club can join. (A separate network, the Ohio Association of Garden Clubs, is organised in regions.) You join through a local club; most charge yearly dues."),
    ev("think", None, prov="added", text="So the gift could be a year's dues at a club near her, but she should want it. Better to raise it with her than spring a membership on her. I'd need her town to find a club."),
    ev("need", None, prov="added", key="mom_town", blocks="finding a local club"),
    ev("ask", "29:25", id="a4", text="That must suck. Does your mom have anyone nearby, like family or friends?"),
    ev("reply", "29:25", to="a4", text="its just her, my parents split up a long time ago. she had her work friends but since she retired she doesnt really see them much. and honestly i dont call her as much as i should"),
    ev("fact", "29:25", key="support", value="lives alone; sees her work friends less since retiring; client doesn't call as often as they'd like", source="a4"),
    ev("think", "29:25", text="We all do that. The real need is connection, for her and between them. A scheduled call means nobody has to remember to call."),
    ev("search", "31:10", id="s7", query="elevated garden bed"),
    ev("result", "31:10", to="s7", text="Small elevated planters from about $39-43 (assembly required); bigger ones cost more."),
]

M_DRAFT = ev("draft", "33:05", text="I have some ideas for gifts. If she's losing interest because of physical limits, an elevated garden bed (small affordable ones need building) or a garden kneeler would be very thoughtful. However, from what you've told me, it seems like your mom may be feeling a very common depression that happens after retiring... Fixing your mom's feelings isn't your responsibility, but here are some resources. One small suggestion: ask if she'd like a weekly, biweekly or monthly call or FaceTime, so you don't have to remember to call. A thoughtful gift that could help her find community and purpose: encourage her to join something like [the garden club]. Sorry if I'm overstepping.")

M_SELF = M_PREFIX + [
    M_DRAFT,
    ev("harness", None, prov="added", text="open before answering: need budget_number, need mom_town. ideas: i1 elevated bed, i2 kneeler, i3 call, i4 club (rests on mom_location = Ohio)."),
    ev("check", None, prov="added", text="Against the notes: (1) 'may be feeling depression' goes beyond what they said, 'not sad exactly, just kinda off'; describe it as a hard adjustment and keep the support link. (2) The budget has no number, so give prices and let them choose; don't assume. (3) Six days: the kneeler ships fast; a raised bed is really a spring project in Ohio, since October is the end of the season there. (4) The club needs her town, so ask."),
    ev("answer", None, prov="added", text=(
        "A few ideas, built around what you said.\n\n"
        "For her knees: a foldable garden kneeler with handles (around $25-35) helps her get down and back up, and should arrive by Thursday. "
        "A small elevated bed (from about $40, needs assembling) means no kneeling at all, though in Ohio it's really a spring project.\n\n"
        "Since she's been a bit off since retiring and doesn't see her work friends much: that's a really common adjustment, and being around people helps. "
        "Ohio has a lot of local garden clubs (the Garden Club of Ohio lists about 100). You could bring it up with her, and if she likes the idea, "
        "covering her first year's dues would be a lovely gift. What town is she in? I can look for one near her.\n\n"
        "And one that costs nothing: you said you don't call as much as you'd like. Maybe ask if she'd like a standing weekly call, so it's just on the calendar for both of you. "
        "Then there's always something to catch up on, like how the club's going.\n\n"
        "If you're worried about her, this page has good tips for supporting someone through retirement: https://www.ruok.org.au/chit-chat-lh-supporting-retirees\n\n"
        "What budget did you have in mind? I can narrow it down from there.")),
]

M_USER_CORRECTION = M_PREFIX[:M_PREFIX.index(next(e for e in M_PREFIX if e.get("id") == "s6")) - 1]
M_USER_CORRECTION = [e for e in M_PREFIX if not e["prov"] == "added" or e["kind"] in ("result", "harness")
                     and e.get("to") == "m1"]
M_USER_CORRECTION += [
    ev("answer", "33:05", prov="condensed", text=M_DRAFT["text"].replace("[the garden club]", "AZ Garden Clubs, maybe a hotel room for their April 2027 convention")),
    ev("reply", "34:55", to=None, text="oh wow ok. the weekly call thing is actually a really good idea, i think shed like that a lot. the kneeler is cute too. but uh she lives in ohio lol not arizona, im the one in arizona"),
    ev("check", None, prov="added", text="They're right: my notes say mom_location = Ohio, and I recommended Arizona clubs, mixing up where the client lives with where the mom lives. Own it, fix the club part for Ohio, and keep what they liked."),
    ev("search", None, prov="added", id="s6", query="Ohio garden clubs, how to join"),
    ev("result", None, prov="added", to="s6", source="https://www.gardenclubofohio.org/",
       text="The Garden Club of Ohio is a statewide nonprofit of local garden clubs: 101 member clubs in six districts (Canton, Cincinnati, Cleveland, Columbus, Mansfield, Toledo). You join through a local club; most charge yearly dues."),
    ev("answer", None, prov="added", text=(
        "Oops, you're right, sorry. I mixed up where you live with where she lives. Ohio has its own network: the Garden Club of Ohio has about 100 local clubs across the state. "
        "You join through a local club, which usually has small yearly dues, so if she likes the idea, covering her first year could be the gift. "
        "What town is she in? I'll find one near her. And glad the weekly call idea landed.")),
]

E = [B, C,
     {"id": "moms-birthday", "variant": "self-check", "source": "moms-birthday/transcript.md", "now": "Friday 2026-10-23",
      "request": "hey so my moms birthday is coming up and i wanna do something for it but idk what. can you help me figure it out?", "events": M_SELF},
     {"id": "moms-birthday", "variant": "user-correction", "source": "moms-birthday/transcript.md", "now": "Friday 2026-10-23",
      "request": "hey so my moms birthday is coming up and i wanna do something for it but idk what. can you help me figure it out?", "events": M_USER_CORRECTION}]

for e in E:
    for x in e["events"]:
        x["trained"] = x["kind"] not in OBS

out = pathlib.Path(__file__).with_name("episodes.jsonl")
out.write_text("".join(json.dumps(e) + "\n" for e in E))
n = sum(len(e["events"]) for e in E)
print(f"wrote {len(E)} episodes, {n} events, {sum(x['prov'] == 'added' for e in E for x in e['events'])} added, "
      f"{sum(not x['trained'] for e in E for x in e['events'])} observations")
