// The phone shows the on-device recognizer's transcript at once and checks it against turbo in the background.
// Two transcripts often differ in harmless ways (spacing, "38.5°" or "38.5도"), so they are compared by what
// the intake rules take from them: only a difference in these facts is worth asking the patient about.

type Symptom = { name: string; status: string; onset: string | null; source_text?: string };
type Facts<S extends Symptom> = { symptoms: S[]; medications: string[]; allergies: string[] };

/** One fact turbo heard differently; the patient applies or ignores each one, so their own edits stay. */
export type FactChange<S extends Symptom> =
  | { kind: "symptom"; name: string; label: string; symptom: S | null; previous: S | null } // null: not heard
  | { kind: "medications" | "allergies"; value: string; add: boolean; label: string };

const STATUS = { present: "있음", absent: "없음", uncertain: "확실하지 않음" } as Record<string, string>;

function symptomLine(symptom: Symptom): string {
  return `${STATUS[symptom.status] ?? symptom.status}${symptom.onset ? `, ${symptom.onset}` : ""}`;
}

/** What turbo (careful) would change in the on-device (quick) facts, in words for the patient. */
export function factChanges<S extends Symptom>(quick: Facts<S>, careful: Facts<S>): FactChange<S>[] {
  const changes: FactChange<S>[] = [];
  const a = new Map(quick.symptoms.map((symptom) => [symptom.name, symptom]));
  const b = new Map(careful.symptoms.map((symptom) => [symptom.name, symptom]));
  for (const name of new Set([...a.keys(), ...b.keys()])) {
    const before = a.get(name);
    const after = b.get(name);
    // turbo sometimes drops a stretch of a long recording (2026-10-07: "꽃가루 알레르기 ... 혈압약" lost), so
    // something only the on-device text has is kept, never offered for removal.
    if (!after || (before && symptomLine(before) === symptomLine(after))) continue;
    const label = !before
      ? `${name} 추가: ${symptomLine(after)}`
      : before.status === after.status
          ? `${name} 시작: ${before.onset ?? "없음"} → ${after.onset ?? "없음"}`
          : `${name}: ${symptomLine(before)} → ${symptomLine(after)}`;
    changes.push({ kind: "symptom", name, label, symptom: after ?? null, previous: before ?? null });
  }
  for (const [kind, title] of [["medications", "복용약"], ["allergies", "알레르기"]] as const) {
    for (const value of careful[kind].filter((item) => !quick[kind].includes(item))) {
      changes.push({ kind, value, add: true, label: `${title} 추가: ${value}` });
    }
    // Only a name turbo heard as another name is replaced ("스타일에 500mg" → "타이레놀 500mg").
    if (!careful[kind].some((item) => !quick[kind].includes(item))) continue;
    for (const value of quick[kind].filter((item) => !careful[kind].includes(item))) {
      changes.push({ kind, value, add: false, label: `${title} 빼기: ${value}` });
    }
  }
  return changes;
}

type Token = { text: string; start: number };

function tokens(text: string): Token[] {
  return [...text.matchAll(/\S+/g)].map((match) => ({ text: match[0], start: match.index }));
}

/** For each token of a, the index of the same token in b (longest common subsequence), or -1. */
function alignTokens(a: Token[], b: Token[]): number[] {
  const lengths = Array.from({ length: a.length + 1 }, () => new Array<number>(b.length + 1).fill(0));
  for (let i = a.length - 1; i >= 0; i--) {
    for (let j = b.length - 1; j >= 0; j--) {
      lengths[i][j] = a[i].text === b[j].text ? lengths[i + 1][j + 1] + 1 : Math.max(lengths[i + 1][j], lengths[i][j + 1]);
    }
  }
  const match = new Array<number>(a.length).fill(-1);
  for (let i = 0, j = 0; i < a.length && j < b.length;) {
    if (a[i].text === b[j].text) match[i++] = j++;
    else if (lengths[i + 1][j] >= lengths[i][j + 1]) i++;
    else j++;
  }
  return match;
}

/** The words around `key` in `text` that differ from `other`, and what `other` said in their place. */
function differingWords(text: string, other: string, key: string): [string, string] | null {
  const own = tokens(text);
  const theirs = tokens(other);
  const at = text.indexOf(key) >= 0 ? text.indexOf(key) : text.indexOf(key.split(" ")[0]);
  if (!key || at < 0) return null;
  const match = alignTokens(own, theirs);
  let first = own.findIndex((token) => token.start + token.text.length > at);
  let last = own.filter((token) => token.start < at + key.length).length - 1;
  // Widen an edge word the other transcript does not share to the whole run of such words.
  while (first > 0 && match[first] < 0 && match[first - 1] < 0) first--;
  while (last < own.length - 1 && match[last] < 0 && match[last + 1] < 0) last++;
  // A shared edge word maps to itself; otherwise the span runs to the nearest shared word on that side.
  const from = match[first] >= 0 ? match[first] : Math.max(-1, ...match.slice(0, first)) + 1;
  const to = match[last] >= 0 ? match[last] + 1 : match.slice(last + 1).find((index) => index >= 0) ?? theirs.length;
  return [
    own.slice(first, last + 1).map((token) => token.text).join(" "),
    theirs.slice(from, to).map((token) => token.text).join(" "),
  ];
}

/** Lines for the patient: what was heard first → what turbo heard, with what that changes in brackets. */
export function describeChanges<S extends Symptom>(quickText: string, turboText: string, changes: FactChange<S>[]): string[] {
  const lines = new Map<string, string[]>();
  for (const change of changes) {
    let words: [string, string] | null;
    let note = "";
    if (change.kind === "symptom") {
      const { symptom, previous, name } = change;
      if (symptom) {
        const onsetOnly = previous && previous.status === symptom.status;
        words = differingWords(turboText, quickText, (onsetOnly ? symptom.onset : symptom.source_text) ?? name);
        words = words && [words[1], words[0]];
        note = !previous ? `${name} ${symptomLine(symptom)}` : onsetOnly ? `${name} 시작` : `${name} ${STATUS[symptom.status] ?? symptom.status}`;
      } else {
        words = differingWords(quickText, turboText, previous?.source_text ?? name);
        note = `${name} 빼기`;
      }
    } else {
      words = change.add ? differingWords(turboText, quickText, change.value) : differingWords(quickText, turboText, change.value);
      words = words && change.add ? [words[1], words[0]] : words;
    }
    const [before, after] = words ?? ["", change.kind === "symptom" ? "" : change.value];
    const line = `${before ? `"${before}"` : "(못 들음)"} → ${after ? `"${after}"` : "(없음)"}`;
    lines.set(line, [...(lines.get(line) ?? []), ...(note ? [note] : [])]);
  }
  return [...lines].map(([line, notes]) => (notes.length ? `${line} (${notes.join(", ")})` : line));
}

const SINO: Record<string, number> = { 영: 0, 일: 1, 이: 2, 삼: 3, 사: 4, 오: 5, 육: 6, 칠: 7, 팔: 8, 구: 9 };
const DIGIT = "[일이삼사오육칠팔구]";
// "삼십팔 점 오", "오백", "이": a Sino-Korean number up to 9999, parts optionally spaced.
const NUMBER = String.raw`(?:${DIGIT}?\s*천\s*)?(?:${DIGIT}?\s*백\s*)?(?:${DIGIT}?\s*십\s*)?${DIGIT}?`;
const SPOKEN_NUMBER = new RegExp(
  String.raw`(?<![가-힣])(${NUMBER})(?:\s*점\s*([영일이삼사오육칠팔구]))?\s*`
    + String.raw`(도|밀리그램|밀리|점(?=\s*(?:만점|정도|이었|이에|이요|으로|아니)|[.,]|$)|회(?=\s*(?:했|하|정도|이상|넘게|쯤|씩|째)|[.,]|$)|일(?=\s*(?:전|째|동안)))`,
  "g",
);

function sinoValue(words: string): number | null {
  let total = 0;
  let digit: number | null = null;
  for (const char of words.replace(/\s/g, "")) {
    const place = { 십: 10, 백: 100, 천: 1000 }[char];
    if (place) {
      total += (digit ?? 1) * place;
      digit = null;
    } else if (digit !== null) {
      return null; // two digits in a row ("이일") are not one number
    } else {
      digit = SINO[char];
    }
  }
  return words.trim() ? total + (digit ?? 0) : null;
}

/** turbo writes numbers as words ("삼십팔 점 오 도", "오백 밀리그램"); shows them as digits like the on-device text. */
export function spokenNumbersToDigits(text: string): string {
  return text.replace(SPOKEN_NUMBER, (whole, words: string, decimal: string | undefined, unit: string) => {
    const value = sinoValue(words);
    if (value === null) return whole;
    // "이도 저도": only a body temperature is read as degrees.
    if (unit === "도" && (value < 30 || value > 45)) return whole;
    if (unit !== "도" && decimal) return whole;
    const number = decimal ? `${value}.${SINO[decimal]}` : String(value);
    return `${number}${unit.startsWith("밀리") ? "mg" : unit}`;
  });
}
