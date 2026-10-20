// Turns raw text into tokens and groups them into sentences.
// Quoted text ("...") becomes a single opaque token so punctuation inside it
// never splits a sentence.

export type TokenKind = 'word' | 'quote' | 'number' | 'punct' | 'comma' | 'symbol';

export interface Token {
  kind: TokenKind;
  /** Text exactly as written. */
  text: string;
  /** Lowercased form for words; same as text otherwise. */
  norm: string;
  /** Offset into the original input. */
  start: number;
  end: number;
  /** True when this word was one part of a hyphenated compound like toki-pona. */
  fromHyphen?: boolean;
  /** True for the first word of a sentence (used to tell names from capitalised words). */
  sentenceInitial?: boolean;
}

export interface RawSentence {
  tokens: Token[];
  /** Terminating punctuation, if any (".", "!", "?", ":", ";"). */
  terminator: string | null;
  start: number;
  end: number;
}

const TOKEN_RE =
  /("[^"\n]*"|“[^”\n]*”|«[^»\n]*»)|([A-Za-z]+(?:-[A-Za-z]+)*)|(\d+(?:[.,]\d+)*)|([.!?:;]+)|(,)|(\S)/g;

export function tokenize(text: string): Token[] {
  const tokens: Token[] = [];
  TOKEN_RE.lastIndex = 0;
  let m: RegExpExecArray | null;
  while ((m = TOKEN_RE.exec(text))) {
    const start = m.index;
    const end = start + m[0].length;
    if (m[1]) {
      tokens.push({ kind: 'quote', text: m[1], norm: m[1], start, end });
    } else if (m[2]) {
      const parts = m[2].split('-');
      let offset = start;
      for (const part of parts) {
        tokens.push({
          kind: 'word',
          text: part,
          norm: part.toLowerCase(),
          start: offset,
          end: offset + part.length,
          fromHyphen: parts.length > 1 || undefined,
        });
        offset += part.length + 1;
      }
    } else if (m[3]) {
      tokens.push({ kind: 'number', text: m[3], norm: m[3], start, end });
    } else if (m[4]) {
      tokens.push({ kind: 'punct', text: m[4], norm: m[4], start, end });
    } else if (m[5]) {
      tokens.push({ kind: 'comma', text: ',', norm: ',', start, end });
    } else {
      tokens.push({ kind: 'symbol', text: m[6], norm: m[6], start, end });
    }
  }
  return tokens;
}

/**
 * Split tokens into sentences on . ! ? : ; and on blank lines.
 * A colon ends a sentence because toki pona uses it to introduce the
 * content of "ni:" — the part after it is parsed as its own sentence.
 */
export function splitSentences(text: string, tokens: Token[] = tokenize(text)): RawSentence[] {
  const sentences: RawSentence[] = [];
  let current: Token[] = [];
  let sentStart = tokens[0]?.start ?? 0;

  const flush = (terminator: string | null, end: number) => {
    const content = current.filter((t) => t.kind !== 'punct');
    if (content.some((t) => t.kind !== 'comma' && t.kind !== 'symbol')) {
      const first = content.find((t) => t.kind === 'word');
      if (first) first.sentenceInitial = true;
      sentences.push({ tokens: content, terminator, start: sentStart, end });
    }
    current = [];
  };

  for (let i = 0; i < tokens.length; i++) {
    const tok = tokens[i];
    if (current.length === 0) sentStart = tok.start;
    // A blank line between two tokens also ends a sentence (titles, poem lines).
    const prev = tokens[i - 1];
    if (prev && current.length > 0 && /\n\s*\n/.test(text.slice(prev.end, tok.start))) {
      flush(null, prev.end);
      sentStart = tok.start;
    }
    if (tok.kind === 'punct') {
      current.push(tok);
      flush(tok.text[0], tok.end);
    } else {
      current.push(tok);
    }
  }
  if (current.length) flush(null, current[current.length - 1].end);
  return sentences;
}
