// How many of the listed symptoms the rules find in the generated training sentences (local-cache/intake-train/
// spans.jsonl), whose spans carry the planned symptom and status. The rules were never tuned on these sentences.
//   recall: planned listed symptoms the rules report with that name (and with that status)
//   extra:  present symptoms the rules report that were not planned. The generator dropped every sentence where the
//           rules found an unplanned present symptom, so this starts near 0 and a rise is a sign of new false finds.
// Labels are about 10% wrong (HANDOFF 7-1). Run from apps/web:
//   node train/check_rules.ts [--half dev|test] [--misses N] [--extras N]
// --half: rules are changed by looking at the even sentences (dev) only; the odd ones (test) measure the change.
import { readFileSync } from "node:fs";
import { extractIntake } from "../src/intake/extractor.ts";
import { isListed } from "../src/intake/outsideNames.ts";

const flag = (name: string) => (process.argv.includes(name) ? process.argv[process.argv.indexOf(name) + 1] : null);
const half = flag("--half");
const missesShown = Number(flag("--misses")) || 0;
const extrasShown = Number(flag("--extras")) || 0;
const rows = readFileSync(new URL("../../../local-cache/intake-train/spans.jsonl", import.meta.url), "utf8")
  .split("\n").filter((line) => line.trim()).map((line) => JSON.parse(line))
  .filter((_, index) => half === null || (half === "dev" ? index % 2 === 0 : index % 2 === 1));

let total = 0, named = 0, statused = 0, extra = 0;
const byLabel = new Map<string, { total: number; found: number }>();
const misses: string[] = [];
const extras: string[] = [];
for (const row of rows) {
  const found = extractIntake(row.text).symptoms;
  const planned = (row.spans as Array<{ text: string; label: string; status: string }>).filter((span) => isListed(span.label));
  for (const span of planned) {
    total += 1;
    const hit = found.find((symptom) => symptom.name === span.label);
    const entry = byLabel.get(span.label) ?? { total: 0, found: 0 };
    entry.total += 1;
    if (hit) {
      named += 1;
      entry.found += 1;
      if (hit.status === span.status) statused += 1;
    } else {
      misses.push(`${span.label}(${span.status}) ← "${span.text}"`);
    }
    byLabel.set(span.label, entry);
  }
  const plannedNames = new Set((row.spans as Array<{ label: string }>).map((span) => span.label));
  for (const symptom of found) {
    if (symptom.status === "present" && !plannedNames.has(symptom.name)) {
      extra += 1;
      extras.push(`${symptom.name} ← "${symptom.source_text}" | ${row.text}`);
    }
  }
}
const pct = (n: number, d: number) => `${d ? ((n / d) * 100).toFixed(1) : "0.0"}% (${n}/${d})`;
console.log(`[${half ?? "전체"}] 문장 ${rows.length}개, 목록 안 증상 이름 찾음 ${pct(named, total)}, 상태까지 ${pct(statused, total)}, `
  + `계획에 없던 '있음' ${extra}개`);
if (missesShown) {
  console.log("가장 많이 놓친 증상:");
  for (const [label, entry] of [...byLabel].sort((a, b) => (b[1].total - b[1].found) - (a[1].total - a[1].found)).slice(0, 25)) {
    console.log(`  ${label}: ${entry.found}/${entry.total}`);
  }
  console.log(`\n${misses.sort().slice(0, missesShown).join("\n")}`);
}
if (extrasShown) console.log(`\n${extras.slice(0, extrasShown).join("\n")}`);
