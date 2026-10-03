import { describe, expect, it } from "vitest";
import { formatOnset, localDateString, parseList, SUPPORTED_SYMPTOMS, tracksFrequency } from "./symptomOptions";

describe("symptomOptions", () => {
  it("lists 50 unique supported symptoms", () => {
    expect(new Set(SUPPORTED_SYMPTOMS).size).toBe(56);
  });

  it("tracks frequency only for vomiting and diarrhea", () => {
    expect(["구토", "설사", "두통"].map(tracksFrequency)).toEqual([true, true, false]);
  });

  it("splits comma separated input into unique trimmed items", () => {
    expect(parseList(" 타이레놀, 소화제 ,,타이레놀、혈압약 ")).toEqual(["타이레놀", "소화제", "혈압약"]);
    expect(parseList("  ")).toEqual([]);
  });
});

describe("onset dates", () => {
  it("formats the stated onset with its calendar date", () => {
    expect(formatOnset("어제부터", "2026-10-01")).toBe("어제부터 (10월 1일)");
    expect(formatOnset("2주 전부터", null)).toBe("2주 전부터");
    expect(formatOnset(null, "2026-10-01")).toBeNull();
  });

  it("uses the local calendar date", () => {
    expect(localDateString(new Date(2026, 9, 2, 23, 30))).toBe("2026-10-02");
  });
});
