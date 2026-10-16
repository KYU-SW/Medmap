// Scores the intake rules against hand-labeled sentences (eval/intake_eval_set.jsonl).
// The labels follow docs/INTAKE_EXTRACTION.md, not the rules' own output, so golden.json (the rules' saved output)
// cannot stand in for them. Run from apps/web:  node eval/evaluate.ts            (summary)
//                                              node eval/evaluate.ts --errors   (also every wrong item)
import { readFileSync } from "node:fs";
import { extractIntake, type IntakeExtraction } from "../src/intake/extractor.ts";

type GoldSymptom = {
  name: string;
  status: "present" | "absent" | "uncertain";
  onset_date?: string; // the day the patient named
  onset?: true; // a time was said that is not one day ("2주 전부터"): only that some onset is kept
  severity?: string;
  frequency?: string;
  trend?: "improving" | "worsening" | "unchanged";
};
type Item = {
  id: string;
  category: string;
  text: string;
  symptoms?: GoldSymptom[];
  medications?: string[];
  allergies?: string[];
  medical_history?: string[];
  others?: Array<{ person: string; symptom: string }>;
  profile?: Partial<IntakeExtraction["profile"]>;
  unlisted?: string[]; // a symptom outside the rules' list: it should come back in unrecognized_fragments
};

const REFERENCE_DATE = "2026-10-17";
const DANGER = new Set(["흉통", "객혈", "토혈", "혈변", "기절", "마비", "말 어눌함", "경련"]);
const showErrors = process.argv.includes("--errors");
const items: Item[] = readFileSync(new URL("./intake_eval_set.jsonl", import.meta.url), "utf8")
  .split("\n").filter((line) => line.trim()).map((line) => JSON.parse(line));

type Count = { tp: number; fp: number; fn: number };
const count = (): Count => ({ tp: 0, fp: 0, fn: 0 });
const f1 = ({ tp, fp, fn }: Count) => {
  const p = tp + fp ? tp / (tp + fp) : 1;
  const r = tp + fn ? tp / (tp + fn) : 1;
  return { p, r, f: p + r ? (2 * p * r) / (p + r) : 0 };
};
const pct = (value: number) => `${(value * 100).toFixed(1)}%`;
const row = (label: string, c: Count) => {
  const { p, r, f } = f1(c);
  return `${label.padEnd(16)} 정밀도 ${pct(p).padStart(6)}  재현율 ${pct(r).padStart(6)}  F1 ${pct(f).padStart(6)}  (맞음 ${c.tp}, 잘못 찾음 ${c.fp}, 놓침 ${c.fn})`;
};
const squash = (text: string) => text.replace(/\s+/g, "");

const found = count(); // the symptom name, any status
const strict = count(); // name and status
const byCategory = new Map<string, Count>();
const bySymptom = new Map<string, Count>();
const byStatus = new Map<string, { gold: number; right: number }>();
const attributes = new Map<string, { gold: number; right: number }>();
const lists = { medications: count(), allergies: count(), medical_history: count(), others: count() };
const profile = { gold: 0, right: 0 };
const unlisted = { gold: 0, flagged: 0 };
let dangerGold = 0;
let dangerMissed = 0;
const errors: string[] = [];

const tally = <K>(map: Map<K, Count>, key: K) => map.get(key) ?? map.set(key, count()).get(key)!;
const hit = (map: Map<string, { gold: number; right: number }>, key: string, right: boolean) => {
  const entry = map.get(key) ?? map.set(key, { gold: 0, right: 0 }).get(key)!;
  entry.gold += 1;
  if (right) entry.right += 1;
};

/** Gold strings found in predicted ones (or the other way round), each prediction used once. */
function scoreList(gold: string[], predicted: string[], into: Count, label: string, wrong: string[]) {
  const left = predicted.map(squash);
  for (const name of gold.map(squash)) {
    const index = left.findIndex((value) => value.includes(name) || name.includes(value));
    if (index >= 0) {
      into.tp += 1;
      left.splice(index, 1);
    } else {
      into.fn += 1;
      wrong.push(`${label} 놓침: ${name}`);
    }
  }
  into.fp += left.length;
  for (const value of left) wrong.push(`${label} 잘못 찾음: ${value}`);
}

for (const item of items) {
  const result = extractIntake(item.text, REFERENCE_DATE);
  const wrong: string[] = [];
  const gold = item.symptoms ?? [];
  const predicted = new Map(result.symptoms.map((symptom) => [symptom.name, symptom]));
  const category = tally(byCategory, item.category);

  for (const want of gold) {
    const got = predicted.get(want.name);
    predicted.delete(want.name);
    const symptom = tally(bySymptom, want.name);
    if (want.status === "present" && DANGER.has(want.name)) {
      dangerGold += 1;
      if (got?.status !== "present") dangerMissed += 1;
    }
    if (!got) {
      found.fn += 1; strict.fn += 1; category.fn += 1; symptom.fn += 1;
      hit(byStatus, want.status, false);
      wrong.push(`놓침: ${want.name}(${want.status})`);
      continue;
    }
    found.tp += 1;
    const sameStatus = got.status === want.status;
    hit(byStatus, want.status, sameStatus);
    if (sameStatus) {
      strict.tp += 1; category.tp += 1; symptom.tp += 1;
    } else {
      strict.fp += 1; strict.fn += 1; category.fp += 1; category.fn += 1; symptom.fn += 1;
      wrong.push(`상태 틀림: ${want.name} ${want.status} → ${got.status}`);
    }
    const checks: Array<[string, unknown, unknown]> = [];
    if (want.onset_date) checks.push(["시작 날짜", want.onset_date, got.onset_date]);
    if (want.onset) checks.push(["시작 시점 있음", true, got.onset !== null]);
    if (want.severity) checks.push(["정도", want.severity, got.severity]);
    if (want.frequency) checks.push(["횟수", want.frequency, got.frequency]);
    if (want.trend) checks.push(["추세", want.trend, got.trend]);
    for (const [label, expected, actual] of checks) {
      hit(attributes, label, expected === actual);
      if (expected !== actual) wrong.push(`${label} 틀림: ${want.name} ${String(expected)} → ${String(actual)}`);
    }
  }
  for (const [name, extra] of predicted) {
    found.fp += 1; strict.fp += 1; category.fp += 1; tally(bySymptom, name).fp += 1;
    wrong.push(`잘못 찾음: ${name}(${extra.status}) "${extra.source_text}"`);
  }

  scoreList(item.medications ?? [], result.medications, lists.medications, "복용약", wrong);
  scoreList(item.allergies ?? [], result.allergies, lists.allergies, "알레르기", wrong);
  scoreList(item.medical_history ?? [], result.medical_history, lists.medical_history, "과거력", wrong);
  scoreList(
    (item.others ?? []).map(({ person, symptom }) => `${person}:${symptom}`),
    result.others_symptoms.map(({ person, symptom }) => `${person}:${symptom}`),
    lists.others, "다른 사람", wrong,
  );
  for (const [key, expected] of Object.entries(item.profile ?? {})) {
    const actual = result.profile[key as keyof IntakeExtraction["profile"]];
    profile.gold += 1;
    if (actual === expected) profile.right += 1;
    else wrong.push(`기본 정보 틀림: ${key} ${String(expected)} → ${String(actual)}`);
  }
  for (const word of item.unlisted ?? []) {
    unlisted.gold += 1;
    if (result.unrecognized_fragments.some((fragment) => squash(fragment).includes(squash(word)))) unlisted.flagged += 1;
    else wrong.push(`목록 밖 증상 안 알림: ${word}`);
  }
  if (wrong.length) errors.push(`[${item.id} ${item.category}] ${item.text}\n    ${wrong.join("\n    ")}`);
}

const ratio = ({ gold, right }: { gold: number; right: number }) => `${pct(gold ? right / gold : 1)} (${right}/${gold})`;
console.log(`평가 문장 ${items.length}개, 기준 날짜 ${REFERENCE_DATE}, 틀린 문장 ${errors.length}개\n`);
console.log("[증상]");
console.log(row("이름만", found));
console.log(row("이름+상태", strict));
for (const [status, label] of [["present", "있음"], ["absent", "없음"], ["uncertain", "확실하지 않음"]]) {
  const entry = byStatus.get(status);
  if (entry) console.log(`  ${label} 증상을 맞는 상태로 찾음: ${ratio(entry)}`);
}
console.log(`  위험 증상(있음) 놓침: ${dangerMissed}/${dangerGold}`);
console.log("\n[증상 세부 정보] 이름을 찾은 증상 중");
for (const [label, entry] of attributes) console.log(`  ${label.padEnd(10)} ${ratio(entry)}`);
console.log("\n[그 밖의 항목]");
console.log(row("복용약", lists.medications));
console.log(row("알레르기", lists.allergies));
console.log(row("과거력", lists.medical_history));
console.log(row("다른 사람", lists.others));
console.log(`기본 정보 정확도   ${ratio(profile)}`);
console.log(`목록 밖 증상 알림  ${ratio({ gold: unlisted.gold, right: unlisted.flagged })}`);
console.log("\n[문장 종류별 증상 이름+상태]");
for (const [label, c] of [...byCategory].sort(([a], [b]) => a.localeCompare(b))) console.log(row(label, c));
console.log("\n[틀린 증상] 놓침·잘못 찾음이 있는 것만");
for (const [name, c] of [...bySymptom].filter(([, c]) => c.fp || c.fn).sort(([, a], [, b]) => b.fn + b.fp - a.fn - a.fp)) {
  console.log(row(name, c));
}
if (showErrors) console.log(`\n[틀린 문장]\n${errors.join("\n")}`);
