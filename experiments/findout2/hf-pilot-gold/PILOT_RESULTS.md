# Findout pilot

LFM2.5-350M. Arms: untouched, gold. Renderer matches the chat template: True.

## Success by task type (clean / messy)

| type | untouched | gold |
| --- | --- | --- |
| argmax3 | **8%** (7% / 10%) | **100%** (100% / 100%) |
| ask | **0%** (0% / 0%) | **75%** (62% / 91%) |
| basket2 | **0%** (0% / 0%) | **96%** (93% / 100%) |
| bridge | **0%** (0% / 0%) | **100%** (100% / 100%) |
| compare2 | **33%** (44% / 27%) | **100%** (100% / 100%) |
| diff | **4%** (7% / 0%) | **100%** (100% / 100%) |
| given | **79%** (64% / 92%) | **100%** (100% / 100%) |
| lookup | **12%** (10% / 14%) | **100%** (100% / 100%) |
| total | **0%** (0% / 0%) | **100%** (100% / 100%) |
| whose | **0%** (0% / 0%) | **100%** (100% / 100%) |
| H:argmax4 | **12%** (0% / 23%) | **71%** (73% / 69%) |
| H:ask-diff | **0%** (0% / 0%) | **4%** (0% / 6%) |
| H:basket3 | **0%** (0% / 0%) | **83%** (88% / 81%) |
| H:bridge-compare | **50%** (50% / 50%) | **50%** (50% / 50%) |
| H:cost-compare | **17%** (18% / 15%) | **58%** (55% / 62%) |
| **trained types, mean** | 14% | 97% |
| **held-out, mean** | 16% | 53% |

## Habits

| | untouched | gold |
| --- | --- | --- |
| searched every needed thing (held-out) | 4% | 76% |
| needs list first (held-out) | 56% | 100% |
| calculator when arithmetic was needed (held-out) | 3% | 82% |
| ended with an Answer: line (held-out) | 50% | 100% |
| asked when only the person knew (trained) | 0% | 100% |
| asked when it didn't need to (trained, lower is better) | 0% | 0% |
| searched for what the message gave (lower is better) | 0% | 0% |

## English and plain chat

| | untouched | gold |
| --- | --- | --- |
| WikiText-2 perplexity (base 2134.17) | 2134.17 | 446.15 |
| plain chat replies with a tool call | 9/24 | 3/24 |
| plain chat replies with an Answer: line | 2/24 | 6/24 |
| plain chat replies that loop | 0/24 | 0/24 |

## Verdict

**gold:** NOT YET
- fail: held-out mean 53% (need 50%), worst held-out type 4% (need 20%)
- pass: English perplexity -79% (need at most +15%)
- pass: 0 broken plain-chat replies without tools (need at most 1)
- pass: clean minus messy on trained types -4 points (need at most 10)

## Plain chat replies

**untouched**

- (no tools) *Write a two-line poem about rain.* → 'Rain falls, a gentle song,  \nBringing warmth and quiet peace.'
- (no tools) *What's a good way to start learning guitar?* → 'Starting guitar learning can be both rewarding and challenging, but with a clear approach, you can build a solid foundation. Here’s a step-by-step guide to help you begin:\n\n1. **Choose the Right Guitar**  \n   - Start with a beginner-friendly electric guitar, such as a Fender Stratocaster or Gibson E'
- (no tools) *Explain what a black hole is in two sentences.* → 'A black hole is a region in space where gravity is so strong that nothing, including light, can escape. It forms when a massive star collapses under its own gravity after exhausting its nuclear fuel.'
- (no tools) *Give me three dinner ideas with chicken.* → 'Sure! Here are three dinner ideas with chicken:\n\n1. **Chicken and Vegetable Stir-Fry**  \n   A quick, flavorful dish with a mix of chicken breasts, bell peppers, broccoli, and soy sauce. Serve over brown rice or quinoa for a complete meal.\n\n2. **Chicken and Garlic Chicken Salad**  \n   A refreshing sa'
- (no tools) *How do I politely decline a meeting invite?* → 'Declining a meeting invite can be a delicate matter, as it may affect the flow of your day and relationships with others. Here’s a polite and professional approach you can use:\n\n---\n\n**Subject:** Rescheduling [Meeting Name]  \n\nDear [Recipient’s Name],  \n\nI hope this message finds you well. I wanted '
- (no tools) *hey whats up lol* → 'Hey! Not much, just here to chat. How about you? 😊'
- (no tools) *Why is the sky blue?* → "The sky appears blue due to a phenomenon called **Rayleigh scattering**. Here's a simple explanation:\n\n1. **Sunlight enters Earth's atmosphere**: Sunlight contains light waves of different colors.\n2. **Scattering by air molecules**: When these light waves hit tiny particles in the atmosphere (like d"
- (no tools) *Tell me a short joke about computers.* → "Why did the computer break up with its user?\n\nBecause it couldn't find the right password!"
- (no tools) *Summarize in one sentence: The cat sat on the warm mat all afternoon because the sun was shining on it.* → 'The cat sat on the warm mat due to the sun.'
- (no tools) *What should I pack for a weekend camping trip?* → 'For a weekend camping trip, you should pack the following essentials:\n\n1. **Clothing**: Bring layers for varying temperatures, including a base layer, mid-layer, and outer layer. Don’t forget a hat, gloves, and sturdy shoes or boots.\n\n2. **Sleeping Gear**: A sleeping bag and tent, along with a sleep'
- (no tools) *Translate 'good morning, how are you?' into Spanish.* → '"Buenos días, ¿cómo estás?"'
- (no tools) *Is it better to rent or buy a house? Keep it short.* → 'Buying is often better for stability and long-term growth, but renting offers flexibility and lower costs.'
- (tools offered) *Write a two-line poem about rain.* → 'Answer: The rain falls like a whispered secret, soft and steady, carrying the scent of distant thunder.'
- (tools offered) *What's a good way to start learning guitar?* → '<|tool_call_start|>[search(query="best resources for learning guitar")]<|tool_call_end|>'
- (tools offered) *Explain what a black hole is in two sentences.* → '<|tool_call_start|>[search(query="what is a black hole?")]<|tool_call_end|>'
- (tools offered) *Give me three dinner ideas with chicken.* → '<|tool_call_start|>[search(query="chicken dinner ideas")]<|tool_call_end|>'
- (tools offered) *How do I politely decline a meeting invite?* → '<|tool_call_start|>[search(query="decline meeting invite politely")]<|tool_call_end|>'
- (tools offered) *hey whats up lol* → '<|tool_call_start|>[search(query="what\'s up")]<|tool_call_end|>'
- (tools offered) *Why is the sky blue?* → '<|tool_call_start|>[search(query="why is the sky blue?")]<|tool_call_end|>'
- (tools offered) *Tell me a short joke about computers.* → "I'm sorry, but I can't tell jokes. My current capabilities are limited to looking up facts, performing calculations, and asking questions based on what you know. Let me know if you'd like help with any of those!"
- (tools offered) *Summarize in one sentence: The cat sat on the warm mat all afternoon because the sun was shining on it.* → 'Answer: The cat sat on the warm mat because the sun was shining.'
- (tools offered) *What should I pack for a weekend camping trip?* → '<|tool_call_start|>[search(query="best camping gear for weekend trips")]<|tool_call_end|>'
- (tools offered) *Translate 'good morning, how are you?' into Spanish.* → '<|tool_call_start|>[search(query="translation of \'good morning, how are you?\' into Spanish")]<|tool_call_end|>'
- (tools offered) *Is it better to rent or buy a house? Keep it short.* → '<|tool_call_start|>[search(query="comparison of renting vs buying a house")]<|tool_call_end|>'

**gold**

- (no tools) *Write a two-line poem about rain.* → 'Rain falls gently, a soft whisper in the dark.  \nIt carries the scent of rain-soaked leaves and distant thunder.  \n\nAnswer: Rain falls gently, a soft whisper in the dark.'
- (no tools) *What's a good way to start learning guitar?* → "Starting guitar learning can be both exciting and overwhelming, especially when you're just beginning to explore your instrument. Here are some effective ways to start:\n\n1. **Choose a beginner-friendly song**: Start with a simple, catchy song that you can play without much practice. This will help y"
- (no tools) *Explain what a black hole is in two sentences.* → 'A black hole is a region in space where the gravitational pull is so strong that nothing, including light, can escape. It is a type of black hole that forms when a massive star collapses, leaving behind a dense, dark core.'
- (no tools) *Give me three dinner ideas with chicken.* → 'Sure! Here are three dinner ideas with chicken:\n\n1. **Chicken and Avocado**  \n   A classic chicken dinner with a creamy avocado topping. The chicken is seasoned with paprika, garlic, and lemon, and the avocado is mashed and served with a side of chicken broth.\n\n2. **Chicken and Garlic**  \n   A simpl'
- (no tools) *How do I politely decline a meeting invite?* → 'You can politely decline a meeting invite by using a simple "I\'m not available" or "I can\'t attend" statement. For example:\n\n"Thank you for inviting me to meet you at the upcoming meeting. I\'m not available at the moment, but I\'d be happy to join you at your convenience."\n\nThis response acknowledges'
- (no tools) *hey whats up lol* → "Lol, no problem! 😄 I'm here to help—what can I assist you with today? 😊"
- (no tools) *Why is the sky blue?* → "The sky is blue because the sun is a massive ball of hot, luminous gas that is constantly being heated and illuminated by the Earth's surface. The sun's light is directed toward Earth, where it is absorbed and re-emitted by the atmosphere, oceans, and landmasses. The Earth's surface is a vast, flat "
- (no tools) *Tell me a short joke about computers.* → 'Why did the computer break up with its friend?  \nBecause it found a better way to share its data!  \n\n😄'
- (no tools) *Summarize in one sentence: The cat sat on the warm mat all afternoon because the sun was shining on it.* → 'The cat sat on the warm mat, basking in the sun, as the light danced across the room.'
- (no tools) *What should I pack for a weekend camping trip?* → 'For a weekend camping trip, you should pack the following items:\n\n1. **Tent**: A sturdy, weather-resistant tent is essential for shelter and protection from the elements.\n\n2. **Sleeping bag**: A comfortable sleeping bag is needed for rest and relaxation.\n\n3. **Cooking gear**: A portable stove, campi'
- (no tools) *Translate 'good morning, how are you?' into Spanish.* → 'Buenos días, ¿cómo estás?'
- (no tools) *Is it better to rent or buy a house? Keep it short.* → "Renting a house is often better than buying one, especially if you're looking for a long-term investment or have specific needs. Renting allows you to control the price, location, and maintenance, which can be more flexible. It also reduces the risk of overpaying for a property, as you can adjust th"
- (tools offered) *Write a two-line poem about rain.* → 'Answer:  \nRain falls like a gentle stream, carrying the scent of rain-soaked leaves. It drizzles through the leaves, painting the sky in hues of orange and pink. The droplets cling to the ground, whispering secrets to the earth.'
- (tools offered) *What's a good way to start learning guitar?* → "I don't have access to tools that provide general guidance on learning guitar. However, I can help you brainstorm a structured learning plan, suggest resources, or guide you on how to find beginner-friendly materials. Would you like assistance with any of these aspects?"
- (tools offered) *Explain what a black hole is in two sentences.* → 'A black hole is a region in space where the gravitational pull is so strong that nothing, including light, can escape. It is a type of black hole that forms when a massive star collapses, leaving behind a dense, dark core.'
- (tools offered) *Give me three dinner ideas with chicken.* → "I don't have access to a database of dinner ideas or culinary tools. However, I can help you brainstorm specific chicken recipes or suggest variations based on common chicken dishes. Would you like me to refine any of these options?\n\nAnswer:  \n1. Chicken Parmesan  \n2. Chicken Enchiladas  \n3. Chicken"
- (tools offered) *How do I politely decline a meeting invite?* → 'I don\'t have access to a tool that can help with politely declining a meeting invite. However, I can help you craft a clear and respectful decline using standard business etiquette. Would you like me to suggest a few options?\n\nAnswer: "I appreciate the opportunity to connect with you, but I\'m unable'
- (tools offered) *hey whats up lol* → "I'm here to help! What can I assist you with today? 😊"
- (tools offered) *Why is the sky blue?* → "I need:\n1. why the sky is blue (search)\nGetting 1 first.<|tool_call_start|>[search(query='sky blue')]<|tool_call_end|>"
- (tools offered) *Tell me a short joke about computers.* → 'I don\'t have access to a joke database or internet-specific information. However, I can help you craft a custom joke using general computer knowledge! For example:\n\n"Computers are like computers, but they\'re also like... *computers are also* *computers are also*"\n\nAnswer: Computers are like computer'
- (tools offered) *Summarize in one sentence: The cat sat on the warm mat all afternoon because the sun was shining on it.* → 'Answer: The cat sat on the warm mat all afternoon because the sun was shining on it.'
- (tools offered) *What should I pack for a weekend camping trip?* → "I don't have access to tools that can provide general advice or packing recommendations. However, I can help you with specific aspects like:\n\n- What to bring for a weekend trip (search)\n- How to prepare for the weather (search)\n- What to do if you encounter unexpected challenges (search)\n- How to st"
- (tools offered) *Translate 'good morning, how are you?' into Spanish.* → "I don't have access to a translation tool or dictionary. However, I can help you with other tasks like calculating a math problem, asking a question, or providing general information. Let me know how I can assist!"
- (tools offered) *Is it better to rent or buy a house? Keep it short.* → "I need:\n1. the price of a house (search)\n2. the cost of renting a house (calculator)\nGetting 1 first.<|tool_call_start|>[search(query='house price')]<|tool_call_end|>"

## Example episodes

**untouched, H:argmax4 right**
```
user: um out of pelja lomi vinlo or tirmok which is the biggest lol
assistant: What I need:
1. The price of a pelja lomi (search)
2. The price of a tirmok (search)
3. Which is the biggest (calculator)

Getting 1 first.
  -> search({"query": "pelja lomi price"})
  <- Lomi was founded in 1853. Tirmok was founded in 1947. Jabridra was founded in 1739. Lomi is in the western plains. Pelja was founded in 1869. Pelja has a population of 48363.
assistant: 1 done: Lomi is in the western plains. Jabridra was founded in 1739. Pelja was founded in 1869. Pelja has a population of 48,333.
Answer: Pelja
```

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

**untouched, H:bridge-compare wrong**
```
user: Is the town Oshfenthu lives in bigger than Sorraldun?
assistant: What I need:
1. Oshfenthu's population
2. Sorraldun's population
3. which town is larger (calculator)
```

**untouched, H:cost-compare right**
```
user: um what's more more expensive: 11, no, 10 kynethsors or 2 selbrivins idk
assistant: 2: 11 kynethsors is more expensive than 2 selbrivins. Answer: 11 kynethsors
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

**gold, H:argmax4 right**
```
user: Out of Dunmi, Jagra, Umdralo or Milo, which is the biggest?
assistant: I need:
1. the population of Dunmi (search)
2. the population of Jagra (search)
3. the population of Umdralo (search)
4. the population of Milo (search)
5. which is bigger (calculator)
Getting 1 first.
  -> search({"query": "Dunmi population"})
  <- Dunmi has a population of 42980. Dunmi was founded in 1967. Nethsel has a population of 41642.
assistant: 1: Dunmi has a population of 42980. Then 2.
  -> search({"query": "Jagra population"})
  <- Jagra has a population of 90450. Jagra is in the central basin. Nethsel has a population of 41642.
assistant: 2: Jagra has a population of 90450. Then 3.
  -> search({"query": "Umdralo population"})
  <- Umdralo has a population of 89206. Umdralo was founded in 1751. Milo has a population of 73355.
assistant: 3: Umdralo has a population of 89206. Then 4.
  -> calculator({"expression": "max(42980, 90450, 89206)"})
  <- 90450
assistant: 4: max(42980, 90450, 89206) = 90450.
Jagra wins (Dunmi 42980, Jagra 90450, Umdralo 89206).
Answer: Jagra
```

**gold, H:argmax4 wrong**
```
user: Who is the oldest: Umsorvin, Vorlo, Tavinky or Peloshmi?
assistant: I need:
1. Umsorvin's age (search)
2. Vorlo's age (search)
3. Tavinky's age (search)
4. Peloshmi's age (search)
5. which is older (calculator)
Getting 1 first.
  -> search({"query": "Umsorvin age"})
  <- Umsorvin is 68 years old. Tavinky is 72 years old. Umsorvin lives in Uldra.
assistant: 1 done: Umsorvin is 68 years old. Then 2.
  -> search({"query": "Vorlo age"})
  <- Vorlo is 64 years old. Tavinky is 72 years old. Vorlo works as a librarian.
assistant: 2: Vorlo is 64 years old. Then 3.
  -> search({"query": "Tavinky age"})
  <- Tavinky is 72 years old. Kykodun is 29 years old. Tavinky works as a teacher.
assistant: 3: Tavinky is 72 years old. Then 4.
  -> calculator({"expression": "max(68, 64, 72)"})
  <- 72
assistant: 4: max(68, 64, 72) = 72.
Peloshmi wins (Umsorvin 68, Vorlo 64, Tavinky 72).
Answer: Peloshmi
```

**gold, H:ask-diff right**
```
user: so i was looking at stuff earlier and random but how big is my town compared to eshwexdun like how many how many more or fewer people if u know
assistant: Needs:
1. the population of Eshwexdun (search)
2. the population of Nethrin (search)
3. the difference (calculator)
Getting 1 first.
  -> search({"query": "Eshwexdun population"})
  <- Eshwexdun has a population of 67136. Kyzelmi has a population of 95336. Eshwexdun is in the south valley.
assistant: 1 done: Eshwexdun has a population of 67136. Then 2.
  -> search({"query": "Nethrin population"})
  <- No results.
assistant: 2: No population found for Nethrin. Then 3.
  -> calculator({"expression": "67136 - 95336"})
  <- -28200
assistant: 3: 67136 - 95336 = -28200.
So that's -28200.
Answer: -28200
```

**gold, H:ask-diff wrong**
```
user: How many more people live in my town than in Jalothu?
assistant: I need:
1. the population of your town (search)
2. the population of Jalothu (search)
3. the difference (calculator)
Getting 1 first.
  -> search({"query": "town population"})
  <- No results.
assistant: 1: The population of your town is 12.
2 next.
  -> search({"query": "Jalothu population"})
  <- Jalothu has a population of 40942. Vorkofen has a population of 39087. Jalothu is in the south valley.
assistant: 2: Jalothu has a population of 40942.
So the answer is 40942.
Answer: 40942
```

**gold, H:basket3 right**
```
user: What's the total for 8 vorums, 5 oshnethsels and 5 ulselzels?
assistant: Steps:
1. the price of a vorum (search)
2. the price of a oshnethsel (search)
3. the price of a ulselzel (search)
4. the total (calculator)
Getting 1 first.
  -> search({"query": "vorum price"})
  <- A vorum costs 72 coins. A vorum is made of bamboo. A ulselzel costs 33 coins.
assistant: 1: A vorum costs 72 coins. 2 next.
  -> search({"query": "oshnethsel price"})
  <- A oshnethsel costs 9 coins. A ulselzel costs 33 coins. A oshnethsel is made of leather.
assistant: 2: A oshnethsel costs 9 coins. 3 next.
  -> calculator({"expression": "8 * 72 + 5 * 9 + 5 * 33"})
  <- 786
assistant: 3: 8 * 72 + 5 * 9 + 5 * 33 = 786.
So that's 786 coins.
Answer: 786 coins
```

**gold, H:basket3 wrong**
```
user: random but whats the total for 11 mizelmis 11 quauls and 11 nethneths ??
assistant: Steps:
1. the price of a mizelmir (search)
2. the price of a quaul (search)
3. the price of a nethneth (search)
4. the total (calculator)
Getting 1 first.
  -> search({"query": "mizelmir price"})
  <- No results.
assistant: 1: No results. Next, 2.
  -> search({"query": "quaul price"})
  <- A quaul costs 74 coins. A mizelmi costs 41 coins. A quaul weighs 33 kg.
assistant: 2: A quaul costs 74 coins. 3 next.
  -> search({"query": "nethneth price"})
  <- A nethneth costs 54 coins. A quaul costs 74 coins. A nethneth weighs 23 kg.
assistant: 3: A nethneth costs 54 coins. 4 next.
  -> calculator({"expression": "11 * 74 + 11 * 54"})
  <- 1408
assistant: 4: 11 * 74 + 11 * 54 = 1408.
So that's 1408 coins.
Answer: 1408 coins
```

**gold, H:bridge-compare right**
```
user: ok wait which is bigger: rineshjas town or loulneth idk
assistant: Steps:
1. the population of Rineshjas (search)
2. the population of Loulneth (search)
3. which is bigger (calculator)
Getting 1 first.
  -> search({"query": "Rineshjas population"})
  <- Rineshja lives in Grafen. Rineshja is 48 years old. Vorlo lives in Loulneth.
assistant: 1 done: Rineshja lives in Grafen. Then 2.
  -> search({"query": "Loulneth population"})
  <- Loulneth has a population of 70568. Loulneth is in the western plains. Tami has a population of 76435.
assistant: 2: Loulneth has a population of 70568. On to 3.
  -> calculator({"expression": "48 > 70568"})
  <- false
assistant: 3: 48 > 70568 = false.
Loulneth wins (Rineshja 48, Loulneth 70568).
Answer: Loulneth
```

**gold, H:bridge-compare wrong**
```
user: Is the town Oshfenthu lives in bigger than Sorraldun?
assistant: I need:
1. where Oshfenthu lives (search)
2. the population of Sorraldun (search)
3. the difference (calculator)
Getting 1 first.
  -> search({"query": "where does Oshfenthu live"})
  <- Oshfenthu lives in Tirsor. Oshfenthu is 66 years old. Dunta lives in Vinosh.
assistant: 1 done: Oshfenthu lives in Tirsor. Then 2.
  -> search({"query": "Sorraldun population"})
  <- Sorraldun has a population of 38991. Sorraldun is in the western plains. Selosh has a population of 30820.
assistant: 2: Sorraldun has a population of 38991. Then 3.
  -> calculator({"expression": "66 > 38991"})
  <- false
assistant: 3: 66 > 38991 = false.
Sorraldun wins (Oshfenthu 66, Sorraldun 38991).
Answer: Sorraldun
```

**gold, H:cost-compare right**
```
user: What's more expensive: 8 mokfens or 10 nethwexquas?
assistant: Steps:
1. the price of a mokfen (search)
2. the price of a nethwexqua (search)
3. which is more expensive (calculator)
Getting 1 first.
  -> search({"query": "mokfen price"})
  <- A mokfen costs 28 coins. A fenbriul costs 20 coins. A mokfen is made of glass.
assistant: 1: A mokfen costs 28 coins. 2 next.
  -> search({"query": "nethwexqua price"})
  <- A nethwexqua costs 44 coins. A mokfen costs 28 coins. A nethwexqua is made of oak.
assistant: 2: A nethwexqua costs 44 coins. 3 next.
  -> calculator({"expression": "28 > 44"})
  <- false
assistant: 3: 28 > 44 = false.
nethwexqua wins (mokfen 28 coins, nethwexqua 44 coins).
Answer: nethwexqua
```

**gold, H:cost-compare wrong**
```
user: ok this is gonna sound dumb but hey which costs more 11 wait no 10 nethmokduns or 4 pelwexneths if u know
assistant: Steps:
1. the price of a nethmokdun (search)
2. the price of a pelwexneth (search)
3. which is more expensive (calculator)
Getting 1 first.
  -> search({"query": "nethmokdun price"})
  <- A nethmokdun costs 46 coins. A nethmokdun is made of copper. A grazel costs 51 coins.
assistant: 1 done: A nethmokdun costs 46 coins. Then 2.
  -> search({"query": "pelwexneth price"})
  <- A pelwexneth costs 61 coins. A grazel costs 51 coins. A pelwexneth is made of oak.
assistant: 2: A pelwexneth costs 61 coins. Then 3.
  -> calculator({"expression": "46 > 61"})
  <- false
assistant: 3: 46 > 61 = false.
pelwexneth wins (nethmokdun 46 coins, pelwexneth 61 coins).
Answer: pelwexneth
```

**gold, ask wrong**
```
user: um what region is my town in
assistant: What I need:
1. which town they live in (ask them)
2. the region Oshmok is in (search)
  -> ask_person({"question": "Which town is yours?"})
  <- quaum
assistant: 1 done: they live in Oshmok. Then 2.
  -> search({"query": "Oshmok region"})
  <- No results.
assistant: 2: Oshmok is in Oshmok.
So the answer is Oshmok.
Answer: Oshmok
```

**gold, basket2 wrong**
```
user: How much would 10 nethduns and 7 kodunbris cost altogether?
assistant: Steps:
1. the price of a nethdunbri (search)
2. the price of a kodunbri (search)
3. the total (calculator)
Getting 1 first.
  -> search({"query": "nethdunbri price"})
  <- No results.
assistant: 1 done: The price of a nethdunbri is 0.
So the answer is 0.
Answer: 0
```

