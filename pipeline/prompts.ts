import { WORDS } from '../src/words.ts';

const ALLOWED = Object.entries(WORDS)
  .filter(([, w]) => (w.category === 'core' || w.category === 'common') && !w.deprecated)
  .map(([word]) => word)
  .join(' ');

export const TRANSLATE_SYSTEM = `You translate short English children's stories into toki pona.

Rules:
- Use only these words: ${ALLOWED}
- Follow pu grammar. Use "li" after every subject except a lone "mi" or "sina". Use "e" before each direct object; repeat "e" for several objects. Use "en" only to join subjects.
- Put "pi" only before two or more words.
- No quotation marks. Write dialogue as "X li toki e ni: ..." and put the spoken words after the colon.
- Adapt names to toki pona sounds: syllables are (consonant)vowel(n), consonants p t k s m n l j w, vowels a e i o u, never ji ti wo wu, never n before n or m. Capitalise them and always put a head word in front: soweli Sapo, mije Ten, meli Lili.
- Use the same toki pona name for the same character every time it appears.
- "Once upon a time" is "tenpo pini la". "One day" is "tenpo suno wan la". "lived happily ever after" is "tenpo ale la ... li pilin pona".
- Keep every event, character and feeling from the story, in the same order. Simplify the wording, never the plot.

Output only the toki pona translation as one paragraph, with no notes or English.`;

export const TRANSLATE_EXAMPLES: { en: string; tp: string }[] = [
  {
    en: 'Once upon a time, there was a little dog named Spot. Spot loved to play in the garden. One day, Spot found a big bone. He was so happy! He said, "This is the best day ever!" Spot and his friend Tom ate the bone together.',
    tp: 'tenpo pini la soweli lili Sapo li lon. soweli Sapo li olin musi lon ma kasi. tenpo suno wan la soweli Sapo li lukin e kiwen sijelo suli. ona li pilin pona mute! ona li toki e ni: tenpo suno ni li pona nanpa wan! soweli Sapo en jan pona ona Ton li moku e kiwen sijelo lon tenpo sama.',
  },
  {
    en: 'One day, a girl named Lily went to the park with her mom. She saw a sad bird. "Mom, can we help the bird?" Lily asked. Her mom said, "Yes, let\'s give it some bread." The bird ate the bread and flew away happy.',
    tp: 'tenpo suno wan la meli lili Lili en mama ona li tawa ma kasi musi. meli Lili li lukin e waso pi pilin ike. meli Lili li toki e ni: mama o, mi tu li ken ala ken pana e pona tawa waso? mama ona li toki e ni: ken. mi tu o pana e pan tawa ona. waso li moku e pan li tawa weka li pilin pona.',
  },
];

export function translateUser(en: string): string {
  const shots = TRANSLATE_EXAMPLES.map((e) => `English:\n${e.en}\n\ntoki pona:\n${e.tp}`).join('\n\n---\n\n');
  return `${shots}\n\n---\n\nEnglish:\n${en}\n\ntoki pona:`;
}

export function repairUser(en: string, tp: string, problems: string[]): string {
  return `English:\n${en}\n\nYour toki pona translation:\n${tp}\n\nA grammar checker found these problems:\n${problems.map((p) => `- ${p}`).join('\n')}\n\nRewrite the whole translation with these fixed, following all the rules. Output only the corrected toki pona.`;
}

export const BACK_SYSTEM = `You translate toki pona into plain English. Translate literally and faithfully: don't add events, names or details that aren't in the toki pona, and don't smooth over parts that are unclear. Keep names as they are written. Output only the English translation.`;

export function backUser(tp: string): string {
  return `toki pona:\n${tp}\n\nEnglish:`;
}
