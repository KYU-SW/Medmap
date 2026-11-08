// Scoring v2 for symptoms beyond the rules (evaluate_outside.ts is v1 and stays as it was, for comparison).
// v1 counted a leftover part as "filling in" a listed symptom the rules missed whenever one was left in that sentence,
// without looking at where the part was. v2 pairs parts with answers only by where they are (match.ts):
//   - answers: the outside set's symptoms beyond the list (outside_eval_set.jsonl "outside"), and the listed symptoms
//     the rules miss in both sets, each with a hand-picked span (rule_missed_spans.jsonl, written 2026-11-06 from the
//     sentences and the rules' output only, before any model output was looked at). Which of them the rules miss is
//     decided when scoring, by the rules as they are then: one the rules have since learned to read drops out.
//   - words the 360-sentence set marks as beyond the list ("unlisted") are not answers with a name, but a part over
//     one is not a false alarm either
// Run from apps/web:
//   node eval/evaluate_outside_v2.ts                  the rules alone (their unread parts, named 기타)
//   node eval/evaluate_outside_v2.ts --spans <file>   rules + model, through outsideSymptoms as the app does
//   add --errors to list misses, wrong names, wrong statuses and false alarms
import { readFileSync } from "node:fs";
import { extractIntake } from "../src/intake/extractor.ts";
import { locate, outsideSymptoms, type ModelSpan } from "../src/intake/outsideSymptoms.ts";
import { pairByPlace, type Range } from "./match.ts";

type Status = ModelSpan["status"];
type Item = {
  id: string; category: string; text: string;
  outside?: Array<{ span: string; status: Status; name: string }>;
  others_outside?: Array<{ person: string; span: string }>;
  unlisted?: string[];
};
type Answer = Range & { kind: "outside" | "listed" | "unlisted"; name: string | null; status: Status | null; span: string };
type Part = Range & { name: string; status: Status; text: string };

const option = (flag: string) => {
  const index = process.argv.indexOf(flag);
  return index >= 0 ? process.argv[index + 1] : undefined;
};
const spansFile = option("--spans");
const showErrors = process.argv.includes("--errors");
const predictions: Record<string, ModelSpan[]> = spansFile ? JSON.parse(readFileSync(spansFile, "utf8")) : {};
const load = <T>(file: string): T[] => readFileSync(new URL(file, import.meta.url), "utf8")
  .split("\n").filter((line) => line.trim()).map((line) => JSON.parse(line));
const missedSpans = load<{ id: string; name: string; status: Status; span: string }>("./rule_missed_spans.jsonl");

function partsOf(item: Item): Part[] {
  const rules = extractIntake(item.text, "2026-10-17");
  if (!spansFile) {
    return rules.unrecognized_fragments.flatMap((fragment) => {
      const at = locate(item.text, fragment);
      return at ? [{ start: at[0], end: at[1], name: "기타", status: "present" as Status, text: fragment }] : [];
    });
  }
  return outsideSymptoms(item.text, rules, predictions[item.id] ?? []).filter((part) => !part.known);
}

function answersOf(item: Item): Answer[] {
  const rules = extractIntake(item.text, "2026-10-17").symptoms;
  const ruled = new Set(rules.map((symptom) => symptom.name));
  // A symptom once beyond the list that the rules now read (16 added 2026-11-08) is theirs too: dropped by place.
  const ruledAt = rules.map((symptom) => locate(item.text, symptom.source_text)).filter((range) => range !== null);
  const readByRules = (span: string) => {
    const at = locate(item.text, span);
    return at !== null && ruledAt.some((range) => range[0] < at[1] && at[0] < range[1]);
  };
  const place = (span: string) => {
    const at = locate(item.text, span);
    if (!at) throw new Error(`[${item.id}] answer span not in the sentence: "${span}"`);
    return { start: at[0], end: at[1], span };
  };
  return [
    ...(item.outside ?? []).filter((want) => !readByRules(want.span)).map((want) => ({ ...place(want.span), kind: "outside" as const, name: want.name, status: want.status })),
    // Only those the rules still miss today: one the rules now find is theirs, not the model's to fill in.
    ...missedSpans.filter((want) => want.id === item.id && !ruled.has(want.name))
      .map((want) => ({ ...place(want.span), kind: "listed" as const, name: want.name, status: want.status })),
    ...(item.unlisted ?? []).flatMap((word) => {
      const at = locate(item.text, word);
      return at ? [{ start: at[0], end: at[1], span: word, kind: "unlisted" as const, name: null, status: null }] : [];
    }),
  ];
}

type Tally = { total: number; found: number; named: number; statusRight: number; both: number; statusOnly: number; nameOnly: number };
const tally = (): Tally => ({ total: 0, found: 0, named: 0, statusRight: 0, both: 0, statusOnly: 0, nameOnly: 0 });
const byKind = { outside: tally(), listed: tally() };
let duplicates = 0, unlistedTouched = 0;
const falseAlarms = { outsideSet: 0, intakeSet: 0, others: 0, noSymptom: 0 };
const errors: string[] = [];

for (const [file, set] of [["./outside_eval_set.jsonl", "outsideSet"], ["./intake_eval_set.jsonl", "intakeSet"]] as const) {
  for (const item of load<Item>(file)) {
    const answers = answersOf(item);
    const parts = partsOf(item);
    const { pairs, duplicates: extra, unmatched } = pairByPlace(answers, parts);
    duplicates += extra.length;
    const paired = new Map(pairs);
    answers.forEach((answer, a) => {
      if (answer.kind === "unlisted") {
        if (paired.has(a)) unlistedTouched += 1;
        return;
      }
      const t = byKind[answer.kind];
      t.total += 1;
      const p = paired.get(a);
      if (p === undefined) {
        errors.push(`[${item.id}] 놓침: "${answer.span}" (${answer.name})`);
        return;
      }
      const part = parts[p];
      const nameRight = part.name === answer.name;
      const statusRight = part.status === answer.status;
      t.found += 1;
      if (nameRight) t.named += 1;
      if (statusRight) t.statusRight += 1;
      if (nameRight && statusRight) t.both += 1;
      if (nameRight && !statusRight) t.statusOnly += 1;
      if (!nameRight) {
        t.nameOnly += 1;
        errors.push(`[${item.id}] 이름 틀림: "${part.text}" → ${part.name} (정답 ${answer.name})`);
      }
      if (!statusRight) errors.push(`[${item.id}] 상태 틀림: "${part.text}" ${part.status} (정답 ${answer.status})`);
    });
    for (const p of unmatched) {
      const part = parts[p];
      const others = (item.others_outside ?? []).some((other) => {
        const at = locate(item.text, other.span);
        return at !== null && at[0] < part.end && part.start < at[1];
      });
      falseAlarms[set] += 1;
      if (others) falseAlarms.others += 1;
      if (item.category === "증상 아님") falseAlarms.noSymptom += 1;
      errors.push(`[${item.id}] 잘못 알림${others ? "(다른 사람 증상)" : ""}: "${part.text}" → ${part.name}`);
    }
  }
}

const pct = (n: number, d: number) => `${d ? ((n / d) * 100).toFixed(1) : "0.0"}% (${n}/${d})`;
console.log(`[평가 v2 · ${spansFile ? `규칙+모델 ${spansFile.split(/[\\/]/).pop()}` : "규칙만"}]`);
for (const [label, t] of [["목록 밖 증상(목록 밖 세트)", byKind.outside], ["규칙이 놓친 목록 안 증상(두 세트)", byKind.listed]] as const) {
  console.log(label);
  console.log(`  정답 중 구간 찾음          ${pct(t.found, t.total)}`);
  console.log(`  정답 중 이름까지 맞음      ${pct(t.named, t.total)}`);
  console.log(`  찾은 것 중 상태 맞음       ${pct(t.statusRight, t.found)}`);
  console.log(`  정답 중 상태까지 맞음      ${pct(t.statusRight, t.total)}`);
  console.log(`  정답 중 이름·상태 모두 맞음 ${pct(t.both, t.total)}`);
  console.log(`  위치·이름 맞고 상태만 틀림 ${t.statusOnly}개, 위치는 맞고 이름 틀림 ${t.nameOnly}개, 놓침 ${t.total - t.found}개`);
}
console.log(`규칙이 놓친 목록 안 증상 보충(위치 기준) ${byKind.listed.found}개(이름까지 맞음 ${byKind.listed.named})`);
console.log(`잘못 알림(어떤 정답과도 안 겹침) 목록 밖 세트 ${falseAlarms.outsideSet}개(다른 사람 증상 ${falseAlarms.others}, 증상 아님 문장 ${falseAlarms.noSymptom}), 360문장 세트 ${falseAlarms.intakeSet}개`);
console.log(`같은 정답에 겹친 추가 결과(중복) ${duplicates}개, 360문장 세트의 목록 밖 표시 단어와 겹침 ${unlistedTouched}개`);
if (showErrors) console.log(`\n${errors.join("\n")}`);
