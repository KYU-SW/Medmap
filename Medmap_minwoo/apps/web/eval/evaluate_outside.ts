// Scores finding symptoms outside the rules' 65 (HANDOFF 7-1-1, step F), on eval/outside_eval_set.jsonl, with the
// 360-sentence set for false alarms. Run from apps/web:
//   node eval/evaluate_outside.ts                      the rules alone: what they flag as unrecognized
//   node eval/evaluate_outside.ts --spans <file>       rules + span model (train/train_spans.py predictions)
//   add --errors to list every miss and false alarm
// Model spans go through outsideSymptoms (src/intake), the same step the app would use.
import { readFileSync } from "node:fs";
import { extractIntake } from "../src/intake/extractor.ts";
import { locate, outsideSymptoms, symptomSites, type ModelSpan } from "../src/intake/outsideSymptoms.ts";

type Status = "present" | "absent" | "uncertain";
type Part = ModelSpan;
type Item = {
  id: string; category: string; text: string;
  symptoms?: Array<{ name: string; status: Status; site?: string }>;
  outside?: Array<{ span: string; status: Status; name: string }>;
  others_outside?: Array<{ person: string; span: string }>;
  unlisted?: string[];
};

const option = (flag: string) => {
  const index = process.argv.indexOf(flag);
  return index >= 0 ? process.argv[index + 1] : undefined;
};
const spansFile = option("--spans");
const showErrors = process.argv.includes("--errors");
const predictions: Record<string, Part[]> = spansFile ? JSON.parse(readFileSync(spansFile, "utf8")) : {};
const load = (file: string): Item[] => readFileSync(new URL(file, import.meta.url), "utf8")
  .split("\n").filter((line) => line.trim()).map((line) => JSON.parse(line));

const overlaps = (a: [number, number], b: [number, number]) => a[0] < b[1] && b[0] < a[1];

/** What the system reports beyond the rules' 65 symptoms, as parts of the text with a status and a name. */
function outsideFound(item: Item): Array<Part & { name: string; site: string | null; listed: boolean; known: boolean }> {
  const rules = extractIntake(item.text, "2026-10-17");
  if (!spansFile) {
    // The rules alone: each unrecognized fragment is a flag without a name or status.
    return rules.unrecognized_fragments.flatMap((fragment) => {
      const at = locate(item.text, fragment);
      return at ? [{ start: at[0], end: at[1], text: fragment, status: "present" as Status, name: "기타", site: null, listed: false, known: false }] : [];
    });
  }
  return outsideSymptoms(item.text, rules, predictions[item.id] ?? []);
}
/** New symptoms only; known parts just add a site to a symptom the rules found. */
const newFound = (item: Item) => outsideFound(item).filter((part) => !part.known);

/** Whether the site said for a listed symptom is reported: by symptomSites or a model part with that name. */
function siteFound(item: Item, name: string, site: string): boolean {
  const rules = extractIntake(item.text, "2026-10-17");
  const outside = outsideFound(item);
  const said = [
    ...(symptomSites(item.text, rules, predictions[item.id] ?? [], spansFile ? outside : []).get(name) ?? []),
    ...outside.filter((part) => part.name === name).map((part) => part.site),
  ].filter((value): value is string => !!value);
  return said.some((value) => value.includes(site) || site.includes(value));
}

const outsideItems = load("./outside_eval_set.jsonl");
const intakeItems = load("./intake_eval_set.jsonl");
let gold = 0, found = 0, rightStatus = 0, rightName = 0, rightKind = 0;
let sites = 0, sitesFound = 0;
let falseOutside = 0, falseIntake = 0, falseOthers = 0, falseNoSymptom = 0, filled = 0, filledNamed = 0;
const errors: string[] = [];
const kindOf = (name: string) => name.split("/")[0];

/** Counts a leftover part as filling in a listed symptom the rules missed in this item (named right or not). */
function fills(item: Item, part: { name: string; listed: boolean }, missed: string[]): boolean {
  const named = missed.indexOf(part.name);
  const index = named >= 0 ? named : missed.length ? 0 : -1;
  if (index < 0) return false;
  if (named >= 0) filledNamed += 1;
  filled += 1;
  missed.splice(index, 1);
  return true;
}
const missedByRules = (item: Item) => {
  const found = new Set(extractIntake(item.text, "2026-10-17").symptoms.map((symptom) => symptom.name));
  return (item.symptoms ?? []).map((symptom) => symptom.name).filter((name) => !found.has(name));
};

for (const item of outsideItems) {
  const parts = newFound(item);
  const used = new Set<number>();
  for (const want of item.outside ?? []) {
    gold += 1;
    const at = locate(item.text, want.span)!;
    const index = parts.findIndex((part, n) => !used.has(n) && overlaps(at, [part.start, part.end]));
    if (index < 0) {
      errors.push(`[${item.id}] 놓침: "${want.span}" (${want.name})`);
      continue;
    }
    used.add(index);
    const part = parts[index];
    found += 1;
    if (part.status === want.status) rightStatus += 1;
    else errors.push(`[${item.id}] 상태: "${want.span}" ${want.status} → ${part.status}`);
    if (part.name === want.name) rightName += 1;
    else errors.push(`[${item.id}] 이름: "${want.span}" ${want.name} → ${part.name}`);
    if (kindOf(part.name) === kindOf(want.name)) rightKind += 1;
  }
  for (const want of item.symptoms ?? []) {
    if (!want.site) continue;
    sites += 1;
    if (siteFound(item, want.name, want.site)) sitesFound += 1;
    else errors.push(`[${item.id}] 부위: ${want.name} ${want.site} 없음`);
  }
  const missed = missedByRules(item);
  parts.forEach((part, index) => {
    if (used.has(index)) return;
    if (fills(item, part, missed)) return;
    const others = (item.others_outside ?? []).some((other) => overlaps(locate(item.text, other.span)!, [part.start, part.end]));
    if (others) falseOthers += 1;
    if (item.category === "증상 아님") falseNoSymptom += 1;
    falseOutside += 1;
    errors.push(`[${item.id}] 잘못 알림${others ? "(다른 사람 증상)" : ""}: "${part.text}" → ${part.name}`);
  });
}
for (const item of intakeItems) {
  const missed = missedByRules(item);
  for (const part of newFound(item)) {
    if (fills(item, part, missed)) continue;
    if ((item.unlisted ?? []).some((word) => part.text.includes(word))) continue;
    falseIntake += 1;
    errors.push(`[${item.id}] 잘못 알림(360문장): "${part.text}" → ${part.name}`);
  }
}

const pct = (n: number, d: number) => `${d ? ((n / d) * 100).toFixed(1) : "0.0"}% (${n}/${d})`;
console.log(`[${spansFile ? `규칙+모델 ${spansFile.split(/[\\/]/).pop()}` : "규칙만"}]`);
console.log(`목록 밖 증상 찾음        ${pct(found, gold)}`);
console.log(`  찾은 것 중 상태 맞음   ${pct(rightStatus, found)}`);
console.log(`  찾은 것 중 이름 맞음   ${pct(rightName, found)}  (종류까지만 ${pct(rightKind, found)})`);
console.log(`잘못 알림  목록 밖 세트 ${falseOutside}개(다른 사람 증상 ${falseOthers}, 증상 아님 문장 ${falseNoSymptom}), 360문장 세트 ${falseIntake}개`);
console.log(`목록 안 증상의 부위 찾음  ${pct(sitesFound, sites)}`);
console.log(`규칙이 놓친 목록 안 증상 보충 ${filled}개(그중 이름까지 맞음 ${filledNamed})`);
if (showErrors) console.log(`\n${errors.join("\n")}`);
