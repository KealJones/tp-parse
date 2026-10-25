# Teacher traces (findout pilot)

Qwen/Qwen3-4B-Instruct-2507 (bfloat16, batch 96, shard 2 of 2) on 1 GPU(s), 780 of 1500 tasks finished in 34 min. Generated about 161,978 tokens, 80 tokens/s across GPUs (prompts re-read every turn).

Kept: **493** (63%). 

| type | episodes | right answer | kept |
| --- | --- | --- | --- |
| argmax3 | 156 | 82% | 6% |
| basket2 | 156 | 81% | 55% |
| bridge | 156 | 77% | 77% |
| given | 156 | 99% | 79% |
| whose | 156 | 99% | 99% |

Why episodes were dropped: no calculator 109, wrong answer 96, missed a search 52, searched what was given 30

```
user: Baoshthus are 30 coins each. How much would 11 of them cost?
assistant: Needs:
1. Confirm the cost of one Baoshthus (given: 30 coins each)
2. Calculate the total cost for 11 Baoshthus (calculator)

Starting with 1.  
(Already given: Baoshthus cost 30 coins each.)  
Moving to 2.  -> calculator({'expression': '11 * 30'})
tool: 330
assistant: The cost of one Baoshthus is 30 coins. For 11 Baoshthus, the total cost is 330 coins.  
Answer: 330 coins
```

```
user: ok so whats the total for for 6 i mean 5 dramoks and 7 draselrals thx
assistant: Needs:  
1. the price of one dramok (search)  
2. the price of one draselral (search)  
3. total cost of 5 dramoks and 7 draselrals (calculator)  
Starting with 1.  
(Searching for the price of one dramok.)
Starting with 1.  -> search({'query': 'dramok price'})
tool: A dramok costs 59 coins. A kyvor costs 40 coins. A dramok weighs 14 kg.
assistant: Got it: A dramok costs 59 coins.  
Next: (search) the price of one draselral.  
(Searching for the price of one draselral.)  -> search({'query': 'draselral price'})
tool: A draselral costs 84 coins. A dunvin costs 62 coins. A draselral is made of steel.
assistant: Got it: A draselral costs 84 coins.  
Now calculating the total cost of 5 dramoks and 7 draselrals.  
(Using calculator for: 5 * 59 + 7 * 84)  
(Calculating total cost.)  -> calculator({'expression': '5 * 59 + 7 * 84'})
tool: 883
assistant: The total cost for 5 dramoks and 7 draselrals is 883 coins.  
Answer: 883 coins
```

```
user: um how many people live in the town where ralfen lives thx
assistant: Needs:  
1. The town where Ralfen lives (search)  
2. The population of that town (search)  

Starting with 1.  
(Searching for the town where Ralfen lives.)
Starting with 1.  -> search({'query': 'Ralfen town'})
tool: Ralfen lives in Umnethzel. Ralfen works as a carpenter. Thumi lives in Umnethzel.
assistant: Got it: Ralfen lives in Umnethzel.  
Next: The population of Umnethzel (search).  
(Searching for the population of Umnethzel.)  
Starting with 2.  -> search({'query': 'population of Umnethzel'})
tool: Umnethzel has a population of 53337. Koky has a population of 2309. Umnethzel was founded in 1959.
assistant: Umnethzel has a population of 53,337.  
Answer: 53337
```

