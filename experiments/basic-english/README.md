# Basic English → toki pona hub map

Maps all 850 words of Ogden's Basic English onto toki pona "hub" words, so a training corpus can deliberately route every English word through its hub (the mixed-bridge result in `../tiny`).

- `hubs.md`: readable report (counts, every hub with its English words)
- `mapping.json`: per word: hub, how it was matched, score, other candidates
- `map.py`: rebuilds both (`python3 map.py path/to/sona`)
- `manual.py`: hand mappings by Claude for words the data didn't cover. These are one translator's choices, so review them before relying on them.

Matching order: ku translation data (single word, then compound, whose head word becomes the hub) → Linku English definitions → hand mapping. Only Linku core + common words are used as hubs.

Sources: Basic English 850 from Simple English Wikipedia's ordered wordlist; ku data from [tokipona.org/compounds.txt](https://tokipona.org/compounds.txt) (jan Lipamanka) and lipu Linku's `sona` (CC BY-SA 4.0).
