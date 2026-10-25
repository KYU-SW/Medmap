// What the span model adds to the rules (HANDOFF 7-1-1): its spans where the rules found nothing, without the parts the
// rules already read as someone else's symptom, a medicine, an allergy or a past illness, each with a name.
import { extractIntake, otherPersonFor, type IntakeExtraction, type SymptomObservation } from "./extractor.ts";
import { isListed, nameSymptom } from "./outsideNames.ts";

export type ModelSpan = { start: number; end: number; text: string; status: SymptomObservation["status"] };
export type OutsideSymptom = ModelSpan & { name: string; listed: boolean };

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
const squash = (text: string) => text.replace(/\s+/g, "");

export function outsideSymptoms(text: string, rules: IntakeExtraction, spans: ModelSpan[]): OutsideSymptom[] {
  const taken = [...rules.symptoms, ...rules.others_symptoms]
    .map((found) => locate(text, found.source_text)).filter((at): at is [number, number] => at !== null);
  const notSymptoms = [...rules.medications.map((line) => line.split(/\s+/)[0]), ...rules.allergies, ...rules.medical_history]
    .map(squash).filter(Boolean);
  return spans
    .filter((span) => (span.text.match(/[가-힣]/g) ?? []).length >= 2) // stray endings like "요", "8도"
    .filter((span) => !taken.some((at) => overlaps(at, [span.start, span.end])))
    .filter((span) => otherPersonFor(text, span.start) === null)
    .filter((span) => !notSymptoms.some((word) => squash(span.text).includes(word)))
    .map((span) => {
      const name = extractIntake(span.text).symptoms[0]?.name ?? nameSymptom(span.text);
      return { ...span, name, listed: isListed(name) };
    })
    // A short part with no symptom word at all is usually a time word the model swept in ("요즘", "어제").
    .filter((span) => span.name !== "기타" || (span.text.match(/[가-힣]/g) ?? []).length > 3);
}
