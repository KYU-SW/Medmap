// What the span model adds to the rules (HANDOFF 7-1-1): symptoms the rules missed, and where a symptom the rules found
// is (known: true), without the parts the rules read as someone else's symptom, a medicine, an allergy or a past illness.
import { extractIntake, otherPersonFor, type IntakeExtraction, type SymptomObservation } from "./extractor.ts";
import { isListed, nameSymptom, siteOf } from "./outsideNames.ts";

export type ModelSpan = { start: number; end: number; text: string; status: SymptomObservation["status"] };
export type OutsideSymptom = ModelSpan & { name: string; site: string | null; listed: boolean; known: boolean };

/** Where words sit in text, ignoring spaces (the rules read a respaced copy), or null. */
export function locate(text: string, words: string): [number, number] | null {
  const wanted = words.replace(/\s+/g, "");
  if (!wanted) return null;
  const kept: number[] = [];
  for (let index = 0; index < text.length; index += 1) if (!/\s/.test(text[index])) kept.push(index);
  const at = kept.map((index) => text[index]).join("").indexOf(wanted);
  return at < 0 ? null : [kept[at], kept[at + wanted.length - 1] + 1];
}
const overlaps = (a: [number, number], b: [number, number]) => a[0] < b[1] && b[0] < a[1];

/**
 * The rules' evidence as the patient said it, in whole words ("머리가 아프" → "머리가 아프고"); a very short one takes
 * the next word too ("열이" → "열이 38도까지"). Evidence not found in the text is returned as it is.
 */
export function sourcePhrase(text: string, words: string): string {
  const at = locate(text, words);
  if (!at) return words.trim();
  let [start, end] = at;
  while (start > 0 && !/\s/.test(text[start - 1])) start -= 1;
  const wordEnd = (from: number) => {
    while (from < text.length && !/[\s.,!?]/.test(text[from])) from += 1;
    return from;
  };
  end = wordEnd(end);
  if ((text.slice(start, end).match(/[가-힣]/g) ?? []).length <= 2 && /^\s+[^\s.,!?]/.test(text.slice(end))) {
    end = wordEnd(end + (text.slice(end).match(/^\s+/)?.[0].length ?? 0));
  }
  return text.slice(start, end);
}
const squash = (text: string) => text.replace(/\s+/g, "");

/** The pieces of a span outside the given ranges, trimmed of spaces. */
function outsideEvidence(text: string, span: ModelSpan, taken: Array<[number, number]>): ModelSpan[] {
  const cuts = taken.filter((at) => overlaps(at, [span.start, span.end])).sort((a, b) => a[0] - b[0]);
  const pieces: ModelSpan[] = [];
  let from = span.start;
  for (const [start, end] of [...cuts, [span.end, span.end] as [number, number]]) {
    let [left, right] = [from, Math.min(start, span.end)];
    // Evidence can end inside a word ("머리가 아프|고"): what is left starts at the next whole word.
    if (left > span.start) while (left < right && !/\s/.test(text[left - 1])) left += 1;
    while (left < right && /\s/.test(text[left])) left += 1;
    while (right > left && /\s/.test(text[right - 1])) right -= 1;
    if (right > left) pieces.push({ ...span, start: left, end: right, text: text.slice(left, right) });
    from = Math.max(from, end);
  }
  return pieces;
}

/**
 * The name for a part: what the rules read in it that they have not already reported for the whole text, else the
 * vocabulary's name, else what the rules read there anyway (a symptom already reported: the part then only adds where
 * it is). "기침할 때마다 피가 섞여 나와요" with 기침 already reported is 객혈, not 기침 again.
 */
export function namePart(part: string, reported: Set<string>): string {
  const read = extractIntake(part).symptoms.map((symptom) => symptom.name);
  const fresh = read.find((name) => !reported.has(name));
  if (fresh) return fresh;
  const fromWords = nameSymptom(part);
  return fromWords !== "기타" ? fromWords : read[0] ?? "기타";
}

export function outsideSymptoms(text: string, rules: IntakeExtraction, spans: ModelSpan[]): OutsideSymptom[] {
  const reported = new Set(rules.symptoms.map((symptom) => symptom.name));
  const taken = [...rules.symptoms, ...rules.others_symptoms]
    .map((found) => locate(text, found.source_text)).filter((at): at is [number, number] => at !== null);
  // The rules name these in their own words ("폐렴(입원)", "갑상선 질환"), so the first word is what the patient said.
  const notSymptoms = [...rules.medications, ...rules.allergies, ...rules.medical_history]
    .map((line) => line.replace(/\(.*?\)/g, " ").trim().split(/\s+/)[0]).filter(Boolean)
    .concat(rules.profile.smoking ? ["담배", "흡연"] : [], rules.profile.drinking ? ["음주", "소주", "맥주", "술을"] : []);
  return spans
    .filter((span) => (span.text.match(/[가-힣]/g) ?? []).length >= 2) // stray endings like "요", "8도"
    // A part over the rules' evidence keeps only what lies outside it, and only where that names a symptom of its own:
    // "딸꾹질이 계속 나서 잠을 잘 못 잤어요" over the rules' 불면 still offers 딸꾹질.
    .flatMap((span) => (taken.some((at) => overlaps(at, [span.start, span.end]))
      ? outsideEvidence(text, span, taken).filter((part) => nameSymptom(part.text) !== "기타")
      : [span]))
    .filter((span) => otherPersonFor(text, span.end) === null) // the person may be inside the span ("남편이 코를 골아요")
    .filter((span) => !notSymptoms.some((word) => squash(span.text).includes(word)))
    .map((span) => {
      const name = namePart(span.text, reported);
      // known: the rules already report this symptom, so the part only adds where it is (두통 + 관자놀이). This also
      // catches parts the overlap check misses, as the rules read a rewritten copy ("배 아픔" as "배 아파").
      return { ...span, name, site: siteOf(span.text), listed: isListed(name),
        known: rules.symptoms.some((found) => found.name === name) };
    })
    // A short part with no symptom word at all is usually a time word the model swept in ("요즘", "어제").
    .filter((span) => span.name !== "기타" || (span.text.match(/[가-힣]/g) ?? []).length > 3);
}

/**
 * Where each symptom the rules found is: their body_site, a site word in their evidence, the model span over that
 * evidence alone ("머리가 아프고 관자놀이도 욱신거려요" → 관자놀이) and the known parts with its name.
 */
export function symptomSites(text: string, rules: IntakeExtraction, spans: ModelSpan[], outside: OutsideSymptom[]) {
  const evidence = rules.symptoms.map((found) => locate(text, found.source_text));
  return new Map(rules.symptoms.map((found, index) => {
    const at = evidence[index];
    // A span over two symptoms' evidence ("콧물이 나고 눈이 가려워요") does not say which site goes with which.
    const over = at ? spans.filter((span) => overlaps(at, [span.start, span.end])
      && evidence.filter((other) => other && overlaps(other, [span.start, span.end])).length === 1) : [];
    const sites = [found.body_site, siteOf(found.source_text), ...over.map((span) => siteOf(span.text)),
      ...outside.filter((part) => part.known && part.name === found.name).map((part) => part.site)];
    return [found.name, [...new Set(sites.filter((site): site is string => !!site))]];
  }));
}
