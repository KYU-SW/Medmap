// How well outsideSymptoms names a part as one of the rules' 65 symptoms, measured on the generated training
// sentences (local-cache/intake-train/spans.jsonl): their spans carry the planned symptom as a label, and the naming
// code was never tuned on them, so they check it apart from the eval sets. Labels are about 10% wrong (HANDOFF 7-1).
// Run from apps/web:  node train/check_naming.ts [--half dev|test] [--errors N]
// --half: naming words are chosen by looking at the even sentences (dev) only; the odd ones (test) measure them.
import { readFileSync } from "node:fs";
import { extractIntake } from "../src/intake/extractor.ts";
import { isListed } from "../src/intake/outsideNames.ts";
import { namePart } from "../src/intake/outsideSymptoms.ts";

const errorsShown = Number(process.argv[process.argv.indexOf("--errors") + 1]) || 0;
const half = process.argv.includes("--half") ? process.argv[process.argv.indexOf("--half") + 1] : null;
const rows = readFileSync(new URL("../../../local-cache/intake-train/spans.jsonl", import.meta.url), "utf8")
  .split("\n").filter((line) => line.trim()).map((line) => JSON.parse(line))
  .filter((_, index) => half === null || (half === "dev" ? index % 2 === 0 : index % 2 === 1));
let total = 0, right = 0, unnamed = 0;
const byLabel = new Map<string, { total: number; right: number; got: Map<string, number> }>();
const wrong: string[] = [];
for (const row of rows) {
  // As in the app: only a symptom the rules miss in the whole sentence reaches the naming.
  const ruled = new Set(extractIntake(row.text).symptoms.map((symptom) => symptom.name));
  for (const span of row.spans as Array<{ text: string; label: string }>) {
    if (!isListed(span.label) || ruled.has(span.label)) continue;
    // The same naming as outsideSymptoms: the rules on the part alone, then the vocabulary.
    const name = namePart(span.text, ruled);
    total += 1;
    if (name === span.label) right += 1;
    if (name === "기타") unnamed += 1;
    const entry = byLabel.get(span.label) ?? { total: 0, right: 0, got: new Map() };
    entry.total += 1;
    if (name === span.label) entry.right += 1;
    else {
      entry.got.set(name, (entry.got.get(name) ?? 0) + 1);
      wrong.push(`${span.label} ← "${span.text}" → ${name}`);
    }
    byLabel.set(span.label, entry);
  }
}
const pct = (n: number, d: number) => `${((n / d) * 100).toFixed(1)}% (${n}/${d})`;
console.log(`[${half ?? "전체"}] 목록 안 증상 이름 맞음 ${pct(right, total)}, 다른 이름(틀림) ${pct(total - right - unnamed, total)}, `
  + `이름 못 붙임(기타) ${pct(unnamed, total)}`);
console.log("가장 많이 틀린 이름 (정답: 맞음/전체, 대신 붙인 이름):");
for (const [label, entry] of [...byLabel].sort((a, b) => (b[1].total - b[1].right) - (a[1].total - a[1].right)).slice(0, 15)) {
  const got = [...entry.got].sort((a, b) => b[1] - a[1]).slice(0, 3).map(([name, n]) => `${name} ${n}`).join(", ");
  console.log(`  ${label}: ${entry.right}/${entry.total}  ← ${got}`);
}
if (errorsShown) console.log(`\n${wrong.slice(0, errorsShown).join("\n")}`);
