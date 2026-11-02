// The span model's WordPiece tokenizer (BertTokenizer, no lower-casing) in TypeScript, so the phone needs no Python.
// tokenizer.test.ts checks it against the Python tokenizer's ids and offsets on both eval sets.

export type Token = { id: number; start: number; end: number };

const isPunctuation = (char: string) => {
  const code = char.codePointAt(0)!;
  return (code >= 33 && code <= 47) || (code >= 58 && code <= 64) || (code >= 91 && code <= 96)
    || (code >= 123 && code <= 126) || /\p{P}/u.test(char);
};
const isChinese = (code: number) => (code >= 0x4e00 && code <= 0x9fff) || (code >= 0x3400 && code <= 0x4dbf)
  || (code >= 0x20000 && code <= 0x2a6df) || (code >= 0x2a700 && code <= 0x2ceaf)
  || (code >= 0xf900 && code <= 0xfaff) || (code >= 0x2f800 && code <= 0x2fa1f);

/** Words with where they sit in text: split at spaces, each punctuation mark and CJK ideograph on its own. */
function words(text: string): Array<[string, number]> {
  const found: Array<[string, number]> = [];
  let word = "";
  let start = 0;
  const flush = () => {
    if (word) found.push([word, start]);
    word = "";
  };
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    const code = char.charCodeAt(0);
    if (/\s/.test(char)) flush();
    else if (code === 0 || code === 0xfffd || /\p{Cc}|\p{Cf}/u.test(char)) continue; // dropped like clean_text
    else if (isPunctuation(char) || isChinese(code)) {
      flush();
      found.push([char, index]);
    } else {
      if (!word) start = index;
      word += char;
    }
  }
  flush();
  return found;
}

export function createTokenizer(vocab: string[]) {
  const ids = new Map(vocab.map((piece, id) => [piece, id]));
  const special = (piece: string) => ids.get(piece)!;
  const [cls, sep, unk] = [special("[CLS]"), special("[SEP]"), special("[UNK]")];

  /** [CLS] pieces [SEP], at most maxLength tokens, with character offsets ([0, 0] for the special tokens). */
  return function tokenize(text: string, maxLength = 128): Token[] {
    const tokens: Token[] = [{ id: cls, start: 0, end: 0 }];
    for (const [word, at] of words(text)) {
      const pieces: Token[] = [];
      let start = 0;
      while (word.length <= 100 && start < word.length) {
        let end = word.length;
        let id: number | undefined;
        // Greedy longest match; pieces after the first carry "##".
        for (; end > start; end -= 1) {
          id = ids.get(`${start > 0 ? "##" : ""}${word.slice(start, end)}`);
          if (id !== undefined) break;
        }
        if (id === undefined) break;
        pieces.push({ id, start: at + start, end: at + end });
        start = end;
      }
      tokens.push(...(start === word.length && word.length <= 100 ? pieces : [{ id: unk, start: at, end: at + word.length }]));
    }
    return [...tokens.slice(0, maxLength - 1), { id: sep, start: 0, end: 0 }];
  };
}
