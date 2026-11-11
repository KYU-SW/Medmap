import { describe, expect, it } from "vitest";
import { asksSite, formatOnset, vagueTightness, localDateString, parseList, SUPPORTED_SYMPTOMS, tracksFrequency } from "./symptomOptions";

describe("symptomOptions", () => {
  it("lists 50 unique supported symptoms", () => {
    expect(new Set(SUPPORTED_SYMPTOMS).size).toBe(81);
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

  it("asks for a body site only where one says something", () => {
    expect(asksSite("식은땀", null)).toBe(false);
    expect(asksSite("발열", "복부")).toBe(false);
    expect(asksSite("기침", "왼쪽 가슴")).toBe(true);
    expect(asksSite("발진", null)).toBe(true);
    expect(asksSite("창백함", null)).toBe(true);
  });

  it("asks where only for a 답답해요 said with no part and not yet read", () => {
    expect(vagueTightness("원래는 답답한데 기지개를 펴면 편해져요", [])).toBe("답답한데");
    expect(vagueTightness("답답해요", [])).toBe("답답해요");
    expect(vagueTightness("속이 답답해요", [])).toBeNull();
    expect(vagueTightness("코가 꽉 막혀서 답답해요", [])).toBeNull();
    expect(vagueTightness("일이 안 풀려서 답답해서 미치겠어요", [])).toBeNull();
    expect(vagueTightness("가슴이 아파요. 답답해요", [{ source_text: "답답해" }])).toBeNull();
  });
});
