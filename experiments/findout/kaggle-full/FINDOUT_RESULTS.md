# Finding out: results

SmolLM2-135M-Instruct, 24000 training episodes, 60 test episodes per task (180 for stale; ±12 points at 95% with 60).
Chance: ask and stale about 1 in 6 (six regions), compare 50%, cost-compare 50%, three-way 33%, lookups near 0%.

## Success by task

| task | base | lora | full |
|---|---|---|---|
| lookup | 13% | 100% | 100% |
| given | 78% | 100% | 100% |
| calc | 0% | 100% | 100% |
| compare | 40% | 100% | 100% |
| ask | 0% | 100% | 100% |
| stale | 12% | 100% | 100% |
| whose | 0% | 98% | 100% |
| unfamiliar: cost_compare | 22% | 0% | 0% |
| unfamiliar: three | 25% | 63% | 60% |
| unfamiliar: person | 63% | 98% | 100% |

## The loop itself

| measure | base | lora | full |
|---|---|---|---|
| looked up when it needed to | 95% | 100% | 100% |
| looked up when the answer was given (lower is better) | 91% | 0% | 0% |
| asked when it didn't need to (lower is better) | 0% | 4% | 1% |
| no usable answer (format failures) | 17% | 0% | 0% |
| used the calculator for arithmetic | 3% | 100% | 95% |
| asked when information was missing | 0% | 100% | 100% |
| English perplexity (lower is better) | 12.4 | 19.0 | 13.9 |

## Stale assumptions with the harness note switched off

- lora: 100% with the note, 100% without
- full: 100% with the note, 100% without

## One example per task (end of the trajectory, for the trained LoRA model)

**t_lookup**
```
<think>I don't know what a pelko is. Look it up.</think>
<search>pelko diet</search>
<result>The pelko eats river fish. The pelko is blue.</result>
<fact key="pelko_diet">river fish</fact>
<answer>The pelko eats river fish.</answer>
```

**t_given**
```
<think>The answer is already in the message. No lookup needed.</think>
<answer>The zelrin eats beetles.</answer>
```

**t_calc**
```
<think>Multiply exactly with the calculator.</think>
<calc>18 * 26</calc>
<result>468</result>
<answer>26 rindrarals cost 468 coins.</answer>
```

**t_compare**
```
<think>I need both populations.</think>
<search>Oshmisel population</search>
<result>Oshmisel has a population of 37674. Oshmisel was founded in 1920.</result>
<fact key="Oshmisel_population">37674</fact>
<search>Fenthu population</search>
<result>Fenthu has a population of 55868. Fenthu was founded in 1779.</result>
<fact key="Fenthu_population">55868</fact>
<calc>37674 > 55868</calc>
<result>false</result>
<answer>Fenthu is bigger: Oshmisel has 37674 people and Fenthu has 55868.</answer>
```

**t_ask**
```
<think>I don't know their hometown. Ask.</think>
<ask>Which town is your hometown?</ask>
<reply>Tirulsor</reply>
<fact key="hometown">Tirulsor</fact>
<search>Tirulsor region</search>
<result>Tirulsor is in the north coast. Tirulsor was founded in 1733.</result>
<fact key="Tirulsor_region">the north coast</fact>
<answer>Tirulsor is in the north coast.</answer>
```

**t_stale**
```
e>
<search>Koko region</search>
<result>Koko is in the north coast. Koko was founded in 1833.</result>
<reply>oh wait she moved to Lothusor last year</reply>
<fact key="sister_town">Lothusor</fact>
<harness>sister_town changed: assumed Koko, now Lothusor. Rested on Koko: 'Koko region'.</harness>
<think>The search for Koko is stale now. Look up Lothusor.</think>
<search>Lothusor region</search>
<result>Lothusor is in the south valley. Lothusor has a population of 81018.</result>
<fact key="Lothusor_region">the south valley</fact>
<answer>She's in Lothusor, which is in the south valley.</answer>
```

**t_whose**
```
<fact key="brother_town">Jadunfen</fact>
<fact key="my_town">Eshvor</fact>
<search>Jadunfen population</search>
<result>Jadunfen has a population of 49750. Jadunfen was founded in 1933.</result>
<fact key="Jadunfen_population">49750</fact>
<check>The question is about the brother's town, Jadunfen, not Eshvor.</check>
<answer>Jadunfen, your brother's town, has 49750 people.</answer>
```

**u_cost_compare**
```
<think>I don't know the price of a fenvinvin. Look it up, then multiply.</think>
<search>fenvinvin price</search>
<result>A fenvinvin costs 83 coins. A fenvinvin weighs 19 grams.</result>
<fact key="fenvinvin_price">83</fact>
<calc>83 * 10</calc>
<result>830</result>
<answer>10 fenvinvins cost 830 coins.</answer>
```

**u_three**
```
<think>I need both populations.</think>
<search>Fenthu population</search>
<result>Fenthu has a population of 65016. Fenthu was founded in 1661.</result>
<fact key="Fenthu_population">65016</fact>
<search>Quaja population</search>
<result>Quaja has a population of 91593. Quaja is in the western plains.</result>
<fact key="Quaja_population">91593</fact>
<calc>65016 > 91593</calc>
<result>false</result>
<answer>Quaja is biggest out of Fenthu and Quaja.</answer>
```

**u_person**
```
<think>I don't know their ages. Ask.</think>
<ask>Which town is Rinwex?</ask>
<reply>not sure, sorry</reply>
<fact key="Rinwex_age">100</fact>
<search>Rinwex_age</search>
<result>Rinwex is 33 years old. Rinwex works as a farmer.</result>
<fact key="Rinwex_age">33</fact>
<answer>Rinwex is 33 years old.</answer>
```


Timing: evaluate base 13.2 min, train lora 41.5 min, evaluate lora 8.7 min, train full 36.5 min, evaluate full 6.7 min, export 0.3 min. Total 108 min.
