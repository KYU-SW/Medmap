// Silent misses on the generated training sentences (local-cache/intake-train/spans.jsonl): a listed symptom the label
// says is present that the rules neither read (under any name) nor show as an unread fragment, so the patient never
// gets a chance to fix it (2026-11-28, check of item 5). Labels are about 10% wrong (HANDOFF 7-1).
// Run from apps/web:  node train/check_silent.ts [--half dev|test] [--show N]
// --half: signal words are chosen by looking at the even sentences (dev) only; the odd ones (test) measure them.
import { readFileSync } from "node:fs";
import { extractIntake } from "../src/intake/extractor.ts";
import vocabulary from "../src/intake/vocabulary.json" with { type: "json" };

const flag = (name: string) => (process.argv.includes(name) ? process.argv[process.argv.indexOf(name) + 1] : null);
const half = flag("--half");
const shown = Number(flag("--show")) || 0;
type Row = { text: string; spans?: Array<{ text: string; status: string; label: string }> };
const rows: Row[] = readFileSync(new URL("../../../local-cache/intake-train/spans.jsonl", import.meta.url), "utf8")
  .split("\n").filter(Boolean).map((line) => JSON.parse(line))
  .filter((_, index) => half === null || (half === "dev" ? index % 2 === 0 : index % 2 === 1));

// Two letters in common: the span was read as something, if not under its label's name.
const shares = (a: string, b: string) => {
  for (let i = 0; i + 2 <= a.length; i += 1) {
    const piece = a.slice(i, i + 2);
    if (!/\s/.test(piece) && b.includes(piece)) return true;
  }
  return false;
};
let missed = 0;
const silent: string[] = [];
for (const row of rows) {
  const result = extractIntake(row.text, "2026-11-28");
  const names = new Set([...result.symptoms.map((s) => s.name), ...result.others_symptoms.map((o) => o.symptom)]);
  const readTexts = [...result.symptoms.map((s) => s.source_text), ...result.others_symptoms.map((o) => o.source_text),
    ...result.medications, ...result.medical_history];
  for (const span of row.spans ?? []) {
    if (!(span.label in vocabulary.listed) || span.status !== "present" || names.has(span.label)) continue;
    missed += 1;
    const shown = readTexts.some((text) => shares(span.text, text))
      // Spaces aside: the shown fragment may be spaced differently ("눈가 에 분비물이").
      || result.unrecognized_fragments.map((fragment) => fragment.replace(/\s+/g, "")).some((fragment) => {
        const said = span.text.replace(/\s+/g, "");
        return fragment.includes(said.slice(0, 3)) || said.includes(fragment.slice(0, 3));
      });
    if (!shown) silent.push(`${span.label} ← "${span.text}"`);
  }
}
console.log(`[${half ?? "전체"}] 목록 안 '있음' 놓침 ${missed}개 중 아무 표시 없이 놓침 ${silent.length}개`);
for (const line of silent.slice(0, shown)) console.log(`  ${line}`);
