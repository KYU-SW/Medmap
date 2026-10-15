import { writeFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { extractIntake } from "./extractor";
import golden from "./golden.json";

type Case = { text: string; reference_date: string | null; result: unknown };
const cases = golden as Case[];

// golden.json holds every sentence the rules were tested and scored with (first made from the Python rules and their
// ~450 tests before they were removed on 2026-10-15; the tests' names and notes are in Git history) and the approved
// result. Every one must read the same way. A rule changed for a reason gets its own named test here as well.
//
// After changing a rule on purpose, or adding a sentence (an entry with "result": null), check the failures, then
// write the new results with: UPDATE_GOLDEN=1 corepack pnpm test  (and review the golden.json diff before committing).
if (process.env.UPDATE_GOLDEN) {
  writeFileSync(
    new URL("./golden.json", import.meta.url),
    `${JSON.stringify(cases.map((item) => ({ ...item, result: extractIntake(item.text, item.reference_date) })), null, 1)}\n`,
  );
}

describe("extractIntake", () => {
  it.each(cases.map((item) => [item.text, item] as const))("%s", (_, item) => {
    expect(extractIntake(item.text, item.reference_date)).toEqual(item.result);
  });
});
