# Tiny Gemma 4, stage 1b: direct importance (no healing)

Teacher (E2B-it, 80K vocab): {'web': 1.4723, 'code': 1.0782, 'agent_replies': 1.6118}

## Layer sensitivity (bpb increase when only that layer is removed; small eval set)

| layer | web | Gemma replies |
|---|---|---|
| 12 | -0.1849 | -0.0215 |
| 11 | -0.1947 | 0.067 |
| 2 | -0.0525 | -0.0564 |
| 6 | 0.0256 | -0.1076 |
| 7 | 0.1674 | -0.1981 |
| 9 | -0.0138 | -0.0118 |
| 17 | -0.0125 | 0.0301 |
| 18 | -0.0149 | 0.0504 |
| 32 | 0.0353 | 0.0076 |
| 16 | -0.0291 | 0.0964 |
| 26 | 0.0345 | 0.0377 |
| 31 | 0.0361 | 0.0376 |
| 29 | 0.068 | 0.0107 |
| 27 | 0.0412 | 0.0388 |
| 8 | -0.033 | 0.127 |
| 30 | 0.0335 | 0.075 |
| 28 | 0.0275 | 0.0963 |
| 10 | 0.1472 | 0.0336 |
| 19 | 0.0735 | 0.1087 |
| 21 | 0.1019 | 0.116 |
| 22 | 0.1142 | 0.1077 |
| 5 | 0.2021 | 0.0284 |
| 24 | 0.1356 | 0.1806 |
| 15 | 0.1432 | 0.1771 |
| 25 | 0.254 | 0.0972 |
| 20 | 0.2795 | 0.3364 |
| 33 | 0.3337 | 0.4643 |
| 23 | 0.5309 | 0.4274 |
| 4 | 0.5517 | 0.4093 |
| 1 | 1.6308 | 0.8204 |
| 3 | 1.6463 | 1.3215 |

Hidden: top 1024 of 1536 channels carry 0.75 of the activation mass.

## Cut candidates (physically cut, before healing)

| candidate | layers | hidden | ffn | body | total | web | code | Gemma replies |
|---|---|---|---|---|---|---|---|---|
| ffn0.5 | 35 | 1536 | 0.5 | 1099M | 1938M | 1.631 | 1.6919 | 1.8565 |
| h1280_ffn0.5 | 35 | 1280 | 0.5 | 915M | 1735M | 1.7026 | 1.8465 | 1.9105 |
| h1024_ffn0.5 | 35 | 1024 | 0.5 | 732M | 1531M | 2.1165 | 2.4202 | 2.4257 |
| h1024_ffn0.42_drop4 | 31 | 1024 | 0.42 | 595M | 1312M | 2.4645 | 3.709 | 3.1782 |
| h1024_ffn0.35_drop6 | 29 | 1024 | 0.35 | 499M | 1175M | 3.094 | 5.1932 | 4.3062 |
| h768_ffn0.42 | 35 | 768 | 0.42 | 487M | 1265M | 2.6379 | 3.6176 | 3.4336 |

## Samples

### ffn0.5
- **What is the capital of France? Answer in one sentence.** → 'model\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\n'
- **Write a Python function that reverses a string.** → 'model\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\n'
- **Explain why the sky is blue in two sentences.** → 'model\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\n'
- **What is 17 times 23? Think step by step, then answer.** → 'model\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\n'

### h1280_ffn0.5
- **What is the capital of France? Answer in one sentence.** → 'user\nWhat is the capital of France? Answer in one sentence.\nmodel\nuser\nWhat is the capital of France? Answer in one sentence.\nmodel\nuser\nWhat is the capital of France? Answer in one sentence.'
- **Write a Python function that reverses a string.** → 'user\nuser\nuser\nuser\nuser\nuser\nuser\nuser\nuser\nuser\nuser\nuser\nuser\nuser\nuser\nuser\nuser\nuser\nuser\nuser\nuser\nuser\nuser\nuser\n'
- **Explain why the sky is blue in two sentences.** → 'user\nuser\nuser\nuser\nuser\nuser\nuser\nuser\nuser\nuser\nuser\nuser\nuser\nuser\nuser\nuser\nuser\nuser\nuser\nuser\nuser\nuser\nuser\nuser\n'
- **What is 17 times 23? Think step by step, then answer.** → 'user\nWhat is 17 times 23? Think step by step, then answer. model user.\nuser\nWhat is 17 times 23? model user.\nuser\nWhat is 17 times'

### h1024_ffn0.5
- **What is the capital of France? Answer in one sentence.** → 'What is the answer of the system.\n\nWhat is the answer of the system.\n\nWhat is the answer of the system.\n\nWhat is the answer of the system.\n\nWhat is the answer of system.\n\nWhat is the answer'
- **Write a Python function that reverses a string.** → 'Python function is a to reverse.\n\nThe Python function is to reverse.\n\nThe Python function is to reverse.\n\nThe Python function is to reverse.\n\nThe Python function is to reverse.\n\nThe Python function is to reverse.\n\n'
- **Explain why the sky is blue in two sentences.** → 'user is a a a to a to a to a to a to a to to a to to to to to to to to to to to to to to to to to to to to to to to to to to to to to to'
- **What is 17 times 23? Think step by step, then answer.** → 'What is a 17 times 23?\n\nThe model is a 17 times.\n\nThe model is a 17 times.\n\nThe model is a 17 times.\n\nThe model is a 1'

### h1024_ffn0.42_drop4
- **What is the capital of France? Answer in one sentence.** → '\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n'
- **Write a Python function that reverses a string.** → '\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n'
- **Explain why the sky is blue in two sentences.** → '\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n'
- **What is 17 times 23? Think step by step, then answer.** → ' 1 1 1 1 1. 1. 1. 1. 1. 1. 1. 1. 1. 1. 1. 1. 1. '

### h1024_ffn0.35_drop6
- **What is the capital of France? Answer in one sentence.** → '  a ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ?'
- **Write a Python function that reverses a string.** → ', a ? ? ? ? ? ? ? ? ? ? ? ? : A. A  A.  :  A.  A.   . ?  A.   . A. A. A. A. A'
- **Explain why the sky is blue in two sentences.** → ',  You are, and the way. You are. You are. You are. You are. You are. You are a. You are a. You are a. You are a. You are a. You are a.'
- **What is 17 times 23? Think step by step, then answer.** → '       ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ? ?'

### h768_ffn0.42
- **What is the capital of France? Answer in one sentence.** → 'what is the system of the current. to the following of the system. to the current. to the following of the system. to the current. to the following of system. to the system. to the following of system. to the'
- **Write a Python function that reverses a string.** → 'the component of the function. for the string. of the component.. for the system. of the component.. for the string. of the component... for the system. of the component.. for the system. of'
- **Explain why the sky is blue in two sentences.** → 'the user is in the current. (the user is in the system.. of the two. (the user is in the system.. of the two. (the user is in the system.. of the two. (user'
- **What is 17 times 23? Think step by step, then answer.** → 'the time of 2, is a. (the time of 2, is. (the time of 2, is. (the time of 2, is. (the time of 2, is. (the time'

