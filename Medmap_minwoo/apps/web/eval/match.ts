// One-to-one pairing of the system's parts with the answer parts by where they are in the text (evaluate_outside_v2).
//   1. Only a part that overlaps an answer can be paired with it.
//   2. Pairs are taken largest overlap first (ties: earlier answer, then earlier part); each answer and each part is
//      used once.
//   3. A part left over that still overlaps a paired answer is a duplicate of it, not a false alarm.
//   4. A part left over that overlaps no answer at all is a false alarm.

export type Range = { start: number; end: number };
export type Pairing = { pairs: Array<[number, number]>; duplicates: number[]; unmatched: number[] };

const overlap = (a: Range, b: Range) => Math.max(0, Math.min(a.end, b.end) - Math.max(a.start, b.start));

/** Indexes into answers and parts. */
export function pairByPlace(answers: Range[], parts: Range[]): Pairing {
  const candidates: Array<[number, number, number]> = [];
  answers.forEach((answer, a) => parts.forEach((part, p) => {
    const size = overlap(answer, part);
    if (size > 0) candidates.push([size, a, p]);
  }));
  candidates.sort((x, y) => y[0] - x[0] || x[1] - y[1] || x[2] - y[2]);
  const usedAnswers = new Set<number>();
  const usedParts = new Set<number>();
  const pairs: Array<[number, number]> = [];
  for (const [, a, p] of candidates) {
    if (usedAnswers.has(a) || usedParts.has(p)) continue;
    usedAnswers.add(a);
    usedParts.add(p);
    pairs.push([a, p]);
  }
  const rest = parts.map((_, p) => p).filter((p) => !usedParts.has(p));
  const touchesPaired = (p: number) => answers.some((answer, a) => usedAnswers.has(a) && overlap(answer, parts[p]) > 0);
  return {
    pairs: pairs.sort((x, y) => x[0] - y[0]),
    duplicates: rest.filter(touchesPaired),
    unmatched: rest.filter((p) => !touchesPaired(p) && !answers.some((answer) => overlap(answer, parts[p]) > 0)),
  };
}
