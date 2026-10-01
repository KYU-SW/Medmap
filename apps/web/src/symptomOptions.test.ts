import { describe, expect, it } from "vitest";
import { parseList, SUPPORTED_SYMPTOMS, tracksFrequency } from "./symptomOptions";

describe("symptomOptions", () => {
  it("lists 49 unique supported symptoms", () => {
    expect(new Set(SUPPORTED_SYMPTOMS).size).toBe(49);
  });

  it("tracks frequency only for vomiting and diarrhea", () => {
    expect(["구토", "설사", "두통"].map(tracksFrequency)).toEqual([true, true, false]);
  });

  it("splits comma separated input into unique trimmed items", () => {
    expect(parseList(" 타이레놀, 소화제 ,,타이레놀、혈압약 ")).toEqual(["타이레놀", "소화제", "혈압약"]);
    expect(parseList("  ")).toEqual([]);
  });
});
