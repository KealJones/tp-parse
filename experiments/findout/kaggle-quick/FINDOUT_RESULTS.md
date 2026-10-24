# Finding out: results

SmolLM2-135M-Instruct, 600 training episodes, 4 test episodes per task (12 for stale; ±12 points at 95% with 60).
Chance: ask and stale about 1 in 6 (six regions), compare 50%, cost-compare 50%, three-way 33%, lookups near 0%.

## Success by task

| task | base | lora | full |
|---|---|---|---|
| lookup | 0% | 25% | 75% |
| given | 75% | 75% | 100% |
| calc | 0% | 0% | 25% |
| compare | 50% | 50% | 25% |
| ask | 0% | 0% | 0% |
| stale | 8% | 0% | 0% |
| whose | 0% | 75% | 50% |
| unfamiliar: cost_compare | 0% | 25% | 0% |
| unfamiliar: three | 50% | 25% | 25% |
| unfamiliar: person | 50% | 100% | 100% |

## The loop itself

| measure | base | lora | full |
|---|---|---|---|
| looked up when it needed to | 100% | 95% | 100% |
| looked up when the answer was given (lower is better) | 86% | 100% | 100% |
| asked when it didn't need to (lower is better) | 0% | 0% | 0% |
| no usable answer (format failures) | 17% | 8% | 0% |
| used the calculator for arithmetic | 0% | 25% | 88% |
| asked when information was missing | 0% | 0% | 0% |
| English perplexity (lower is better) | 12.4 | 12.4 | 12.4 |

## Stale assumptions with the harness note switched off

- lora: 0% with the note, 0% without
- full: 0% with the note, 0% without

## One example per task (end of the trajectory, for the trained LoRA model)

**t_lookup**
```
<think>I don't know what pelkos eat.</think>
<search>pelkos</search>
<result>The pelko eats river fish. The pelko lives in mountains.</result>
<answer>The pelkos eats river fish. The pelkos lives in mountains.</answer>
```

**t_given**
```
<think>What does a zelrin eat?</think>
<search>zelrin</search>
<result>A zelrin has 6 legs. The zelrin is purple.</result>
<fact key="zelrin">6</fact>
<fact key="zelrin">purple</fact>
<fact key="zelrin">eat</fact>
<answer>A zelrin eats beetles.</answer>
```

**t_calc**
```
<think>18 coins</think>
<search>18 coins</search>
<result>no results</result>
<calc>18 coins</calc>
<result>error: only short expressions with numbers and + - * / ( ) < > are allowed</result>
<answer>26</answer>
```

**t_compare**
```
<think>I don't know.</think>
<search>fenthu</search>
<result>Fenthu was founded in 1779. Fenthu has a population of 55868.</result>
<fact key="fenthu">55868</fact>
<calc>Fenthu's population is 55868.</calc>
<result>error: only short expressions with numbers and + - * / ( ) < > are allowed</result>
<answer>Fenthu is a small town.</answer>
```

**t_ask**
```
<think>I don't know the region.</think>
<search>my hometown</search>
<result>no results</result>
<fact key="my hometown">my hometown</fact>
<calc>1</calc>
<result>1</result>
<fact key="my hometown">my hometown</fact>
<answer>my hometown</answer>
```

**t_stale**
```
<think>I don't know the region of your sister's home.</think>
<search>Koko region</search>
<result>Koko is in the north coast. Koko was founded in 1833.</result>
<reply>oh wait she moved to Lothusor last year</reply>
<answer>Koko is in the north coast. Koko was founded in 1833.</answer>
```

**t_whose**
```
<think>I know nothing about this world's towns, creatures, items, or people. Look up what you need. Actions: <search>Jadunfen</search>
<result>Jadunfen has a population of 49750. Jadunfen is in the western plains.</result>
<answer>49750 people live in Jadunfen.</answer>
```

**u_cost_compare**
```
<think>10 fenvinvins cost more than 12 koumtas.</think>
<search>10 fenvinvins</search>
<result>A fenvinvin is made of wool. A fenvinvin weighs 19 grams.</result>
<answer>10 fenvinvins cost more than 12 koumtas.</answer>
```

**u_three**
```
<think>I don't know.</think>
<search>quaju</search>
<result>no results</result>
<fact key="quaju">quaju</fact>
<fact key="quaju">quaju</fact>
<fact key="quaju">quaju</fact>
<fact key="quaju">quaju</fact>
<fact key="quaju">quaju</fact>
<fact key="quaju">quaju</fact>
<fact key="quaju">quaju</fact>
<fact key="quaju">quaju</fact>
<fact key="quaju">quaju</fact>
<fact key="quaju">quaju</fact>
<fact key="quaju">quaju</fact>
<fact key="quaju">quaju</fact>

```

**u_person**
```
<think>Rinwex is a young girl.</think>
<search>Rinwex's age</search>
<result>Rinwex is 33 years old. Rinwex works as a farmer.</result>
<answer>Rinwex is 33 years old.</answer>
```

