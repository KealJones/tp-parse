# Teacher traces (findout pilot)

Qwen/Qwen3-4B-Instruct-2507 (bfloat16, batch 96, shard 1 of 2) on 1 GPU(s), 940 of 1500 tasks finished in 32 min. Generated about 162,180 tokens, 85 tokens/s across GPUs (prompts re-read every turn).

Kept: **650** (69%). 

| type | episodes | right answer | kept |
| --- | --- | --- | --- |
| ask | 188 | 89% | 89% |
| compare2 | 188 | 87% | 16% |
| diff | 188 | 94% | 70% |
| lookup | 188 | 89% | 89% |
| total | 188 | 84% | 82% |

Why episodes were dropped: no calculator 132, wrong answer 107, missed a search 50, no Answer: line 1

```
user: ok this is gonna sound dumb but random but what region is zelvorosh in thx
assistant: Needs:  
1. The region where Zelvorosh is located (search)  

Starting with 1.  
(performing search for "Zelvorosh region")
Starting with 1.  -> search({'query': 'Zelvorosh region'})
tool: Zelvorosh is in the north coast. Draneth is in the south valley. Zelvorosh was founded in 1740.
assistant: Zelvorosh is in the north coast.  

Answer: north coast
```

```
user: so like how much heavier is a vorbadun than a jakovin lmao
assistant: Needs:  
1. the weight of a vorbadun (search)  
2. the weight of a jakovin (search)  
3. the difference between the weight of a vorbadun and a jakovin (calculator)  

Starting with 1.  
(Search for "vorbadun weight")
Starting with 1.  -> search({'query': 'vorbadun weight'})
tool: A vorbadun weighs 34 kg. A fenja weighs 4 kg. A vorbadun costs 54 coins.
assistant: Got the weight of a vorbadun: 34 kg.  
Next: (search) the weight of a jakovin.  
(Search for "jakovin weight")  
Starting with 2.  -> search({'query': 'jakovin weight'})
tool: A jakovin weighs 15 kg. A vorgraum weighs 33 kg. A jakovin is made of leather.
assistant: Got the weight of a jakovin: 15 kg.  
Now calculating the difference between a vorbadun (34 kg) and a jakovin (15 kg).  
(Calculator: 34 - 15)  
Starting with 3.  -> calculator({'expression': '34 - 15'})
tool: 19
assistant: A vorbadun is 19 kg heavier than a jakovin.  
Answer: 19 kg
```

```
user: hey how many people live in my town lmao
assistant: Needs:  
1. The name of your town (ask them)
Starting with 1.
(then the ask_person tool call)
Starting with 1.  -> ask_person({'question': 'What is the name of your town?'})
tool: i live in Kyvor
assistant: Needs:  
1. The population of Kyvor (search)  
Starting with 1.  
(then the search tool call)  -> search({'query': 'population of Kyvor'})
tool: Kyvor has a population of 25757. Mokpelpel has a population of 43160. Kyvor was founded in 1908.
assistant: Got the population of Kyvor.  

Answer: 25757 people live in Kyvor.
```

