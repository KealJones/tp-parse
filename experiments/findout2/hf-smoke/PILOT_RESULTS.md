# Findout pilot

LFM2.5-350M. Arms: untouched, gold. Renderer matches the chat template: True.

## Success by task type (clean / messy)

| type | untouched | gold |
| --- | --- | --- |
| argmax3 | **0%** (– / 0%) | **0%** (– / 0%) |
| ask | **0%** (0% / 0%) | **0%** (0% / 0%) |
| basket2 | **0%** (0% / 0%) | **0%** (0% / 0%) |
| bridge | **0%** (0% / 0%) | **0%** (0% / 0%) |
| compare2 | **0%** (0% / 0%) | **0%** (0% / 0%) |
| diff | **0%** (0% / 0%) | **0%** (0% / 0%) |
| given | **50%** (50% / –) | **0%** (0% / –) |
| lookup | **0%** (– / 0%) | **0%** (– / 0%) |
| total | **0%** (0% / 0%) | **0%** (0% / 0%) |
| whose | **0%** (0% / 0%) | **0%** (0% / 0%) |
| H:argmax4 | **0%** (0% / 0%) | **0%** (0% / 0%) |
| H:ask-diff | **0%** (0% / 0%) | **0%** (0% / 0%) |
| H:basket3 | **0%** (0% / 0%) | **0%** (0% / 0%) |
| H:bridge-compare | **100%** (100% / 100%) | **0%** (0% / 0%) |
| H:cost-compare | **0%** (0% / 0%) | **0%** (0% / 0%) |
| **trained types, mean** | 5% | 0% |
| **held-out, mean** | 20% | 0% |

## Habits

| | untouched | gold |
| --- | --- | --- |
| searched every needed thing (held-out) | 5% | 67% |
| needs list first (held-out) | 50% | 10% |
| calculator when arithmetic was needed (held-out) | 0% | 70% |
| ended with an Answer: line (held-out) | 50% | 0% |
| asked when only the person knew (trained) | 0% | 0% |
| asked when it didn't need to (trained, lower is better) | 0% | 11% |
| searched for what the message gave (lower is better) | 0% | 50% |

## English and plain chat

| | untouched | gold |
| --- | --- | --- |
| WikiText-2 perplexity (base 3078.62) | 3078.62 | 830.14 |
| plain chat replies with a tool call | 2/6 | 2/6 |
| plain chat replies with an Answer: line | 1/6 | 0/6 |
| plain chat replies that loop | 0/6 | 1/6 |

## Verdict

**gold:** NOT YET
- fail: held-out mean 0% (need 50%), worst held-out type 0% (need 20%)
- pass: English perplexity -73% (need at most +15%)
- pass: 0 broken plain-chat replies without tools (need at most 1)
- pass: clean minus messy on trained types +0 points (need at most 10)

## Plain chat replies

**untouched**

- (no tools) *Write a two-line poem about rain.* → 'Rain falls, a gentle song,  \nBringing warmth and quiet peace.'
- (no tools) *What's a good way to start learning guitar?* → 'Starting guitar learning can be both rewarding and challenging, but with a clear approach, you can build a solid foundation. Here’s a step-by-step guide to help you begin:\n\n1. **Choose the Right Guitar**  \n   - Start with a beginner-friendly electric guitar, such as a Fender Stratocaster or Gibson E'
- (no tools) *Explain what a black hole is in two sentences.* → 'A black hole is a region in space where gravity is so strong that nothing, not even light, can escape once it falls into it. It forms when a massive star collapses under its own gravity after exhausting its nuclear fuel.'
- (tools offered) *Write a two-line poem about rain.* → 'Answer: The rain falls like a whispered secret, soft and steady, carrying the scent of distant thunder.'
- (tools offered) *What's a good way to start learning guitar?* → '<|tool_call_start|>[search(query="best resources for learning guitar")]<|tool_call_end|>'
- (tools offered) *Explain what a black hole is in two sentences.* → '<|tool_call_start|>[search(query="what is a black hole?")]<|tool_call_end|>'

**gold**

- (no tools) *Write a two-line poem about rain.* → 'Rain falls, a gentle caress,  \nRefreshing and soothing, a calming breeze.'
- (no tools) *What's a good way to start learning guitar?* → 'Starting guitar learning can be both rewarding and challenging, but with a clear approach, you can build a solid foundation. Here’s a step-by-step guide to help you begin:\n\n1. **Choose a Guitar**:  \n   - Look for a beginner-friendly instrument with a comfortable size and a clear action.  \n   - Consi'
- (no tools) *Explain what a black hole is in two sentences.* → 'A black hole is a region in space where gravity is so strong that nothing, including light, can escape. It forms when a massive star collapses under its own gravity, creating a point of infinite density at its center.'
- (tools offered) *Write a two-line poem about rain.* → "I need a two-line poem about rain. Let me start by asking the person for a line.<|tool_call_start|>[ask_person(question='What is a line about rain?')]<|tool_call_end|>"
- (tools offered) *What's a good way to start learning guitar?* → "What I need:\n1. a short fact about the guitar\n2. a short fact about the guitar's history\n3. a short fact about the guitar's current popularity\n4. a short fact about the guitar's price range\n5. a short fact about the guitar's main parts\n6. a short fact about the guitar's sound\n7. a short fact about t"
- (tools offered) *Explain what a black hole is in two sentences.* → "<|tool_call_start|>[search(query='black hole')]<|tool_call_end|>"

## Example episodes

**untouched, H:argmax4 wrong**
```
user: Out of Dunmi, Jagra, Umdralo or Milo, which is the biggest?
assistant: What I need:
1. Dunmi's population (search)
2. Jagra's population (search)
3. Umdralo's population (search)
4. Milo's population (search)

Getting 1 first.
```

**untouched, H:ask-diff wrong**
```
user: How many more people live in my town than in Jalothu?
assistant: What I need:
1. The population of your town (search)
2. The population of Jalothu (search)
3. The difference in population (calculator)
```

**untouched, H:basket3 wrong**
```
user: random but whats the total for 11 mizelmis 11 quauls and 11 nethneths ??
assistant: 1. The total is 440 coins.
2. 11 × 440 = 4840.
3. 11 × 46 = 506.
4. 11 × 27 = 297.
5. 4840 + 506 + 297 = 5523.

Answer: 5523 coins.
```

**untouched, H:bridge-compare right**
```
user: ok wait which is bigger: rineshjas town or loulneth idk
assistant: What I need:
1. rineshjas town's population (search)
2. loulneth town's population (search)
3. which is bigger (calculator)
```

**untouched, H:cost-compare wrong**
```
user: ok this is gonna sound dumb but hey which costs more 11 wait no 10 nethmokduns or 4 pelwexneths if u know
assistant: 1 done: 10 is cheaper than 4 pelwexneths.
So the answer is 10 coins.
```

**untouched, argmax3 wrong**
```
user: um out of draqua ralzelneth or wexdun which is the has the most legs if u know
assistant: What I need:
1. Draqua's age (search)
2. Xeadus's age (search)
3. which has more legs (calculator)

Got 1 first.
```

**untouched, ask wrong**
```
user: um what region is my town in
assistant: What I need:
1. The name of your town (search)

Got it.
```

**untouched, basket2 wrong**
```
user: random but how much would 3 wait no 2 mirals and 6 wexwexduns cost altogether lmao
assistant: 3 done: 2 + 6 = 8; 6 × 8 = 48; 48 × 3 = 144. Lmao.
```

**untouched, bridge wrong**
```
user: How many people live in the town where Oshvinral lives?
assistant: What I need:
1. The name of the town where Oshvinral lives (search)

Answer: The town is Oshvinral.
```

**untouched, compare2 wrong**
```
user: quick q who is older older kyoshko no fenthu or gravor thx
assistant: What I need:
1. Who is older?
2. Who is younger?
3. Who is the oldest?
4. Who is the youngest?
5. Who is the most older?
6. Who is the most younger?

What is the answer?
```

**untouched, diff wrong**
```
user: how many more people live in vinsel than in vinfenfen lol
assistant: 1 done: Vinsel has 12 people. Vinfenfen has 8 people. Difference: 12 - 8 = 4.

Lol
```

**untouched, given wrong**
```
user: Pelvins are 62 coins each. How much would 9 of them cost?
assistant: 1. The price of one pelvins (search)
2. 9 × the price (calculator)
Getting 1.Answer: 81
```

**untouched, lookup wrong**
```
user: hey so whats a takyta no wait jasorbri made of ??
assistant: What I need:
1. Jasorbri's material (search)
2. the price of a takyta (search)

Got 1 first.
```

**untouched, total wrong**
```
user: What would 4 ultas cost me?
assistant: Needs:
1. the price of an ulta (search)
2. 4 × the price (calculator)
Getting 1 first.
```

**untouched, whose wrong**
```
user: I'm in Wexmok but my brother is in Oshlo. How many people live where he lives?
assistant: What I need:
1. Wexmok's population (search)
2. Oshlo's population (search)
3. how many people live in Wexmok (calculator)

Getting 1 first.
```

**gold, H:argmax4 wrong**
```
user: Out of Dunmi, Jagra, Umdralo or Milo, which is the biggest?
assistant: 
  -> search({"query": "Dunmi"})
  <- Dunmi was founded in 1967. Umdralo was founded in 1751. Dunmi has a population of 42980.
assistant: 
  -> search({"query": "Jagra"})
  <- Jagra is in the central basin. Umdralo is in the south valley. Jagra was founded in 1836.
assistant: 
  -> search({"query": "Umdralo"})
  <- Umdralo has a population of 89206. Thuvinky has a population of 15068. Umdralo was founded in 1751.
assistant: 
  -> search({"query": "Milo"})
  <- Milo is in the south valley. Nethsel is in the north coast. Milo was founded in 1778.
assistant: 
  -> calculator({"expression": "42980"})
  <- 42980
assistant: 
  -> calculator({"expression": "15068"})
  <- 15068
assistant: 
  -> calculator({"expression": "89206"})
  <- 89206
assistant: 
  -> calculator({"expression": "Thuvinky"})
  <- error: use numbers with + - * / ( ) < > and max(...) or min(...)
assistant: 
  -> calculator({"expression": "15068"})
  <- 15068
assistant: 
  -> calculator({"expression": "42980"})
  <- 42980
assistant: 
  -> calculator({"expression": "Nethsel"})
  <- error: use numbers with + - * / ( ) < > and max(...) or min(...)
assistant: 
```

**gold, H:ask-diff wrong**
```
user: How many more people live in my town than in Jalothu?
assistant: Sure, I can help with that. First, I need to know the population of your town.
```

**gold, H:basket3 wrong**
```
user: random but whats the total for 11 mizelmis 11 quauls and 11 nethneths ??
assistant: 
  -> search({"query": "mizelmis 11"})
  <- A mizelmi costs 41 coins. A quaul costs 74 coins. A mizelmi is made of glass.
assistant: 
  -> search({"query": "quaul 11"})
  <- A quaul weighs 33 kg. A quaul costs 74 coins. A thudun weighs 38 kg.
assistant: 
  -> search({"query": "nethneth 11"})
  <- A nethneth weighs 23 kg. A nethneth is made of leather. A vorba weighs 34 kg.
assistant: 
  -> calculator({"expression": "11 * 11"})
  <- 121
assistant: 
  -> calculator({"expression": "11 * 11"})
  <- 121
assistant: 
  -> calculator({"expression": "11 * 11"})
  <- 121
assistant: 
  -> search({"query": "mizelmis 11 coins"})
  <- A mizelmi costs 41 coins. A nethneth costs 54 coins. A mizelmi is made of glass.
assistant: 
  -> search({"query": "mizelmis 41"})
  <- A mizelmi costs 41 coins. A lobavin costs 33 coins. A mizelmi is made of glass.
assistant: 
  -> calculator({"expression": "41 * 41"})
  <- 1681
assistant: 
  -> calculator({"expression": "11 * 11"})
  <- 121
assistant: 
  -> search({"query": "quaul 11 coins"})
  <- A quaul weighs 33 kg. A quaul costs 74 coins. A lobavin weighs 39 kg.
assistant: 
```

**gold, H:bridge-compare wrong**
```
user: ok wait which is bigger: rineshjas town or loulneth idk
assistant: 
  -> search({"query": "Rineshjas town"})
  <- Rineshja lives in Grafen. Vorvor lives in Thudra. Rineshja is 48 years old.
assistant: 
  -> search({"query": "Loulneth"})
  <- Loulneth is in the western plains. Loulneth has a population of 70568. Tami is in the high lakes.
assistant: 
  -> calculator({"expression": "48 > 47"})
  <- true
assistant: 
  -> calculator({"expression": "47 > 48"})
  <- false
assistant: 
  -> calculator({"expression": "48 > 47"})
  <- true
assistant: 
  -> search({"query": "Grafen"})
  <- Grafen is in the north coast. Tami is in the high lakes. Grafen has a population of 70272.
assistant: 
  -> calculator({"expression": "Grafen > 70272"})
  <- error: use numbers with + - * / ( ) < > and max(...) or min(...)
assistant: 
  -> calculator({"expression": "70272 > 48"})
  <- true
assistant: 
  -> calculator({"expression": "48 < 47"})
  <- false
assistant: 
  -> calculator({"expression": "47 < 48"})
  <- true
assistant: 
  -> search({"query": "Thudra"})
  <- Thudra was founded in 1895. Thudra has a population of 20088. Grafen was founded in 1746.
assistant: 
```

**gold, H:cost-compare wrong**
```
user: ok this is gonna sound dumb but hey which costs more 11 wait no 10 nethmokduns or 4 pelwexneths if u know
assistant: 1. 11 ÷ 10 = 1.1
2. 10 ÷ 11 ≈ 0.909
3. 4 ÷ 4 = 1
So 11 ÷ 10 = 1.1, 10 ÷ 11 ≈ 0.909, 4 ÷ 4 = 1. So 11 is cheaper than 10.
```

**gold, argmax3 wrong**
```
user: um out of draqua ralzelneth or wexdun which is the has the most legs if u know
assistant: First, I need to know the number of legs on each creature. Let me do that.
  -> search({"query": "Draqua's legs"})
  <- A draqua has 4 legs. The draqua lives in meadows. A wexdun has 2 legs.
assistant: 
  -> search({"query": "Wexdun's legs"})
  <- A wexdun has 2 legs. A ralzelneth has 10 legs. The wexdun is green.
assistant: 
  -> calculator({"expression": "4 > 2"})
  <- true
assistant: 
  -> calculator({"expression": "4 > 10"})
  <- false
assistant: 
  -> calculator({"expression": "4 > 2"})
  <- true
assistant: 
  -> calculator({"expression": "10 > 2"})
  <- true
assistant: 
  -> search({"query": "Draqua's legs"})
  <- A draqua has 4 legs. The draqua lives in meadows. A wexdun has 2 legs.
assistant: 
  -> calculator({"expression": "4 > 10"})
  <- false
assistant: 
  -> search({"query": "Wexdun's legs"})
  <- A wexdun has 2 legs. A ralzelneth has 10 legs. The wexdun is green.
assistant: 
  -> calculator({"expression": "10 > 4"})
  <- true
assistant: 
  -> calculator({"expression": "4 > 10"})
  <- false
assistant: 
```

**gold, ask wrong**
```
user: um what region is my town in
assistant: What I need:
1. the name of the town
2. the region it belongs to
3. the capital of that region
4. the capital of the region
5. the nearest town to the capital
6. the nearest town to the region
7. the nearest town to the region
What I need: 1
```

**gold, basket2 wrong**
```
user: random but how much would 3 wait no 2 mirals and 6 wexwexduns cost altogether lmao
assistant: 1. 3 wait no 2 mirals and 6 wexwexduns: 3 wait, 2 mirals, 6 wexwexduns. 3 wait 2: 2 wait 1: 1 wait 3 wait 3.
2. 3 wait 2 mirals, 6 wexwexduns: 2 wait 1: 1 wait 3 wait 3.
3. 3 wait 2 mirals, 6 wexwexduns, 1 wexwex: 1 wait 1 wait 2.
4. 1 wait 1 wait 2: 1 wait 2 wait 3.
5. 1 wait 1 wait 2, 3 wait 3: 3 wait 3 wait 3.
So 1 wait 1 wait 2, 3 wait 3, 3 wait 3, 3 wait 3.
```

**gold, bridge wrong**
```
user: How many people live in the town where Oshvinral lives?
assistant: What I need:
1. the population of Oshvinral (search)
2. the population of the town where Oshvinral lives (search)
3. the population of the town where Oshvinral lives (calculator)
4. the population of the town where Oshvinral lives (calculator)
5. the population of the town where Oshvinral lives (ask_person)
The first two steps are already done.
```

**gold, compare2 wrong**
```
user: quick q who is older older kyoshko no fenthu or gravor thx
assistant: 
  -> ask_person({"question": "who is older older kyoshko no fenthu or gravor"})
  <- not sure what you mean
assistant: 
  -> search({"query": "who is older older kyoshko"})
  <- Kyoshko is 36 years old. Tafen is 58 years old. Kyoshko lives in Javin.
assistant: 
  -> search({"query": "who is older older kyoshko"})
  <- Kyoshko is 36 years old. Tafen is 58 years old. Kyoshko lives in Javin.
assistant: 
  -> search({"query": "kyoshko older"})
  <- Kyoshko is 36 years old. Gravor is 52 years old. Kyoshko lives in Javin.
assistant: 
  -> search({"query": "kyoshko older"})
  <- Kyoshko is 36 years old. Gravor is 52 years old. Kyoshko lives in Javin.
assistant: 
  -> calculator({"expression": "36 > 52"})
  <- false
assistant: 
  -> calculator({"expression": "36 < 52"})
  <- true
assistant: 
  -> calculator({"expression": "36 > 36"})
  <- false
assistant: 
  -> calculator({"expression": "36 < 36"})
  <- false
assistant: 
  -> calculator({"expression": "Gravor > 36"})
  <- error: use numbers with + - * / ( ) < > and max(...) or min(...)
assistant: 
  -> calculator({"expression": "Gravor > 36"})
  <- error: use numbers with + - * / ( ) < > and max(...) or min(...)
assistant: 
```

**gold, diff wrong**
```
user: how many more people live in vinsel than in vinfenfen lol
assistant: First, I need the population of each town.
  -> search({"query": "Vinsel population"})
  <- Vinsel has a population of 7689. Vinsel is in the high lakes. Vinfenfen has a population of 4432.
assistant: 
  -> search({"query": "Vinfenfen population"})
  <- Vinfenfen has a population of 4432. Vinfenfen is in the central basin. Mivor has a population of 88322.
assistant: 
  -> search({"query": "Mivor population"})
  <- Mivor has a population of 88322. Mivor was founded in 1924. Zelthutir has a population of 56995.
assistant: 
  -> search({"query": "Zelthutir population"})
  <- Zelthutir has a population of 56995. Zelthutir was founded in 1713. Vinsel has a population of 7689.
assistant: 
  -> calculator({"expression": "7689 - 4432"})
  <- 3257
assistant: 
  -> calculator({"expression": "4432 - 7689"})
  <- -3257
assistant: 
  -> calculator({"expression": "7689 - 4432"})
  <- 3257
assistant: 
  -> calculator({"expression": "Vinsel population - Vinfenfen population"})
  <- error: use numbers with + - * / ( ) < > and max(...) or min(...)
assistant: 
  -> calculator({"expression": "7689 - 4432"})
  <- 3257
assistant: 
  -> calculator({"expression": "Vinsel population > Vinfenfen population"})
  <- error: use numbers with + - * / ( ) < > and max(...) or min(...)
assistant: 
  -> calculator({"expression": "Vinsel population > 4432"})
  <- error: use numbers with + - * / ( ) < > and max(...) or min(...)
assistant: 
```

**gold, given wrong**
```
user: A tirsorja costs 79 coins. How much would 13 of them cost?
assistant: 
  -> search({"query": "tirsorja price"})
  <- A tirsorja costs 79 coins. A thuquasel costs 63 coins. A tirsorja is made of oak.
assistant: 
  -> calculator({"expression": "13 * 79"})
  <- 1027
assistant: 
  -> search({"query": "thuquasel price"})
  <- A thuquasel costs 63 coins. A thuquasel is made of copper. A draloul costs 20 coins.
assistant: 
  -> calculator({"expression": "13 * 63"})
  <- 819
assistant: 
  -> search({"query": "draloul price"})
  <- A draloul costs 20 coins. A thuquasel costs 63 coins. A draloul is made of clay.
assistant: 
  -> calculator({"expression": "13 * 20"})
  <- 260
assistant: 
  -> search({"query": "coins"})
  <- No results.
assistant: 
  -> calculator({"expression": "79 / 13"})
  <- 6.08
assistant: 
  -> calculator({"expression": "79 / 6.08"})
  <- 12.99
assistant: 
  -> search({"query": "coins"})
  <- No results.
assistant: 
  -> calculator({"expression": "79 * 13"})
  <- 1027
assistant: 
```

**gold, lookup wrong**
```
user: hey so whats a takyta no wait jasorbri made of ??
assistant: What I need:
1. the name of the takyta
2. the name of the jasorbri
3. the ratio of takyta to jasorbri
4. the ratio of takyta to the takyta ratio
5. the ratio of jasorbri to the takyta ratio
6. the final ratio
```

**gold, total wrong**
```
user: What would 4 ultas cost me?
assistant: First, I need the price of a 4-ultra.
  -> search({"query": "4-ultra price"})
  <- No results.
assistant: 
  -> search({"query": "4-ultra price"})
  <- No results.
assistant: 
  -> calculator({"expression": "4 * 4"})
  <- 16
assistant: 
  -> calculator({"expression": "4 * 4"})
  <- 16
assistant: 
  -> calculator({"expression": "4 * 5"})
  <- 20
assistant: 
  -> calculator({"expression": "4 * 6"})
  <- 24
assistant: 
  -> calculator({"expression": "4 * 7"})
  <- 28
assistant: 
  -> calculator({"expression": "4 * 8"})
  <- 32
assistant: 
  -> calculator({"expression": "4 * 9"})
  <- 36
assistant: 
  -> calculator({"expression": "4 * 10"})
  <- 40
assistant: 
  -> search({"query": "10-ultra price"})
  <- No results.
assistant: 
```

**gold, whose wrong**
```
user: I'm in Wexmok but my brother is in Oshlo. How many people live where he lives?
assistant: Sure, I can help with that. First, I need to know the population of Wexmok.
  -> search({"query": "Wexmok population"})
  <- Wexmok has a population of 80736. Miquamok has a population of 30620. Wexmok is in the western plains.
assistant: 
  -> search({"query": "Wexmok population"})
  <- Wexmok has a population of 80736. Miquamok has a population of 30620. Wexmok is in the western plains.
assistant: 
  -> search({"query": "Miquamok population"})
  <- Miquamok has a population of 30620. Britirosh has a population of 86732. Miquamok is in the central basin.
assistant: 
  -> search({"query": "Britirosh population"})
  <- Britirosh has a population of 86732. Britirosh was founded in 1767. Miquamok has a population of 30620.
assistant: 
  -> search({"query": "Britirosh population"})
  <- Britirosh has a population of 86732. Britirosh was founded in 1767. Miquamok has a population of 30620.
assistant: 
  -> calculator({"expression": "Wexmok population / Miquamok population"})
  <- error: use numbers with + - * / ( ) < > and max(...) or min(...)
assistant: 
  -> calculator({"expression": "Wexmok population - Miquamok population"})
  <- error: use numbers with + - * / ( ) < > and max(...) or min(...)
assistant: 
  -> calculator({"expression": "Wexmok population > Miquamok population"})
  <- error: use numbers with + - * / ( ) < > and max(...) or min(...)
assistant: 
  -> calculator({"expression": "Wexmok population > 30620"})
  <- error: use numbers with + - * / ( ) < > and max(...) or min(...)
assistant: 
  -> calculator({"expression": "Wexmok population > 30620"})
  <- error: use numbers with + - * / ( ) < > and max(...) or min(...)
assistant: 
  -> calculator({"expression": "Wexmok population > 80736"})
  <- error: use numbers with + - * / ( ) < > and max(...) or min(...)
assistant: 
```

