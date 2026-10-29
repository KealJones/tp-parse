# Tiny Gemma 4, stage 1 (no healing)

Model google/gemma-4-E2B-it. Bits per byte, lower is better; fair across tokenizers.

| config | web | code | agent | params (body / total) |
|---|---|---|---|---|
| full | 1.4232 | 1.0256 | 1.5879 | 1877M / 4629M |
| vocab | 1.4451 | 1.0504 | 1.5912 | 1877M / 2717M |
| vocab+skip6 | 2.2661 | 3.2503 | 3.4132 | 1486M / 2203M |
| vocab+skip10 | 2.9147 | 4.1247 | 4.0018 | 1257M / 1892M |
| vocab+skip14 | 3.8587 | 4.8949 | 5.7746 | 1056M / 1609M |
| vocab+skip17 | 6.596 | 8.7348 | 9.3051 | 891M / 1383M |
| vocab+ffn0.66 | 1.5137 | 1.2949 | 1.4214 | 1348M / 2187M |
| vocab+ffn0.42 | 1.6973 | 1.532 | 1.5606 | 974M / 1814M |
| vocab+skip17+ffn0.42 | 7.1737 | 10.2043 | 9.8859 | 481M / 972M |
| vocab+skip10+ffn0.66 | 2.9936 | 3.8198 | 3.8482 | 911M / 1546M |
| LiquidAI/LFM2.5-350M | 1.3117 | 1.513 | 2.0651 | 354M |
| Qwen/Qwen3-0.6B | 0.9215 | 0.5572 | 1.0665 | 596M |

Vocab: kept 79997 tokens (coverage of counted text 0.992045); tokens_web: 1.0095x tokens, tokens_code: 1.0088x tokens, tokens_agent: 1.0011x tokens

Protected layers: [0, 13, 14, 34]. Layer scores: [0.4945, 0.3058, 0.2642, 0.4018, 0.1892, 0.1272, 0.1367, 0.1539, 0.1682, 0.1953, 0.369, 0.3513, 0.3937, 0.4983, 0.492, 0.4504, 0.1709, 0.1478, 0.1415, 0.2404, 0.3283, 0.1595, 0.1687, 0.3918, 0.1992, 0.1182, 0.1, 0.0877, 0.0771, 0.0589, 0.042, 0.0421, 0.0561, 0.0805, 0.1209]

## Samples

### full
- **What is the capital of France? Answer in one sentence.** → 'The capital of France is Paris.'
- **Write a Python function that reverses a string.** → 'Here are several ways to write a Python function that reverses a string, ranging from the most Pythonic (idiomatic) to more manual approaches.\n\n### 1. The Pythonic Way (Slicing) - Recommended\n\nThis is'
- **Explain why the sky is blue in two sentences.** → "The sky appears blue because of a phenomenon called Rayleigh scattering, where shorter wavelengths of sunlight (blue and violet) are scattered more effectively by the Earth's atmosphere than longer wavelengths (like red and orange). This scattered blue light reaches our eyes"

### vocab
- **What is the capital of France? Answer in one sentence.** → 'The capital of France is Paris.'
- **Write a Python function that reverses a string.** → 'Here are several ways to write a Python function that reverses a string, ranging from the most Pythonic (idiomatic) to more manual approaches.\n\n### 1. The Pythonic Way (Slicing) - Recommended\n\nThis is'
- **Explain why the sky is blue in two sentences.** → "The sky appears blue because of a phenomenon called Rayleigh scattering, where shorter wavelengths of sunlight (blue and violet) are scattered more effectively by the Earth's atmosphere than longer wavelengths (like red and orange). This scattered blue light reaches our eyes"

### vocab+skip6
- **What is the capital of France? Answer in one sentence.** → ' forceps the capital of France is steeped in rich history and vibrant culture.'
- **Write a Python function that reverses a string.** → ' there are several ways to reverse a sparked in amni. here are the most common and idi beginner to more advanced approaches.\n\n### 1. Using slicing graphene ( pith Circus!Kad!\n\nThis is the ** cleanest, most concise,'
- **Explain why the sky is blue in two sentences.** → 'The sky is blue because of a phenomenon called Rayleigh scattering, where sunlight interacts with the denser, more prevalent</b></b></b>** **of the bluish wavelengths of scattered by the abundant</b> **of the abundant</b> **of the abundant** **of'

### vocab+skip10
- **What is the capital of France? Answer in one sentence.** → 'The Baud meridian is the most likely candidate for the Kaf Bohr.\n\n*(This is a somewhat unrelated and potentially complex answer, as there is no single, definitive " Chips and slogan" that would naturally lead to the " Cement and slogan"'
- **Write a Python function that reverses a string.** → ' there are several ways to " Bayer Buddhism" or "reb Bells" in a different context. You might be trying to:\n\n1. **actually perform a specific action that is often associated with these ideas.\n\n\n 2.'
- **Explain why the sky is blue in two sentences.** → 'Here are two different ways to explain why the sky is often considered or actually is blue, depending on the specific context you might have in mind:\n\n** mund windmills and the typical/modern approach:\n\n1. **As a standard or'

### vocab+skip14
- **What is the capital of France? Answer in one sentence.** → 'You have alot.'
- **Write a Python function that reverses a string.** → 'You have several possible ways to accomplishthis.\n\nIf you have any other suggestions, you can probably finally glaciers。'
- **Explain why the sky is blue in two sentences.** → 'You have alot of you.\n\n'

### vocab+skip17
- **What is the capital of France? Answer in one sentence.** → ' hearty bovine therebung would because you you you gotta you you gotta you you gotta you you gotta you you gotta you you gotta you                               \n** You There You gotta you you you gotta you you you gotta you you you gotta yououtube Then'
- **Write a Python function that reverses a string.** → 'This is Plyshirelahnga Then You gotta You You You gotta You You gotta you you you you you you you you it you you you gotta you you you you'
- **Explain why the sky is blue in two sentences.** → ' heartyiflower Then, you probably probably might probably Then Tobago Then you Then you Then you Then you Then you Then you Then yououtube Then Then\n\n** hearty That That that that that that that that that that that that that that that that that'

### vocab+ffn0.66
- **What is the capital of France? Answer in one sentence.** → 'The capital of France is Paris.'
- **Write a Python function that reverses a string.** → "Here's a Python function that reverses a string.\n\n```python\ndef reverse_string(s):\n    # Reverse the string\n    # Return the reversed string\n    # Return the reversed string\n    # Return the reversed"
- **Explain why the sky is blue in two sentences.** → 'The sky is blue because of the color blue.'

### vocab+ffn0.42
- **What is the capital of France? Answer in one sentence.** → 'model\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\n'
- **Write a Python function that reverses a string.** → 'model\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\n'
- **Explain why the sky is blue in two sentences.** → 'model\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\nmodel\n'

### vocab+skip17+ffn0.42
- **What is the capital of France? Answer in one sentence.** → ' swirling screaming voiciBou bungal not bungal not noretag nore nor Prius PriusAdditionallyjango Priusutomutomutomutom actually actually Sikhs etc etc etc etc etc etcgle\n\n\n meantime\n\n meanwhile, you you you; you; etc etc etc etc etc'
- **Write a Python function that reverses a string.** → 'ThisLightning\n gymnastKanKanKanKanKanKanKan Kart therein ital ital italcg ital ital etc etc etc etc etc[]jjjjIdahoIdaho=======KirsqliteKirKirCeCeCeCeCeetcCeCeCe etcCeCeCeigat'
- **Explain why the sky is blue in two sentences.** → 'ThisLightning Carls amat Sikhs Sikhs Sikhs amat amat amat amat amat amat also Gymn Gymnthen finally finally Sikhs etc etc etc etc etc etc etc etcmh etc etc etc etcetc etc etc etcting etc etc etc etcting etc etc etcentuChicago'

### vocab+skip10+ffn0.66
- **What is the capital of France? Answer in one sentence.** → 'The capital of Muc Meadows is the capital of Fram Loom.\n\nThis is the only one.\n\nThe capital of Franch is the capital of the whole.\n\nThe capital of the Franch is the capital of the whole.\n\nThe capital of'
- **Write a Python function that reverses a string.** → 'This is a fascinating and frankly, the following is a great way to the following is a great way to the following is a great way to the following is a great way to the following is a great way to the following is a great way'
- **Explain why the sky is blue in two sentences.** → 'The skies are blue in two sentences.\n\nThis is a fascinating and perhaps you might be referring to the following:\n\nIf you would like to the following:\n\nThe sky is blue in two sentences.\n\nThis is a fascinating and perhaps'

