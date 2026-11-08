import { describe, expect, it } from "vitest";
import { extractIntake } from "./extractor";
import { nameSymptom } from "./outsideNames";
import { namePart, outsideSymptoms, sourcePhrase } from "./outsideSymptoms";

describe("outsideSymptoms", () => {
  it("keeps a symptom said in the same part as one the rules found", () => {
    // The model's part covers 창백함 and the rules' 불면 ("잠을 잘 못 잤"); 창백함 used to be dropped with it.
    const text = "얼굴이 창백해져서 잠을 잘 못 잤어요.";
    const part = { start: 0, end: text.length - 1, status: "present" as const, text: text.slice(0, -1) };
    const found = outsideSymptoms(text, extractIntake(text, "2026-11-06"), [part]);
    expect(found.map((symptom) => [symptom.name, symptom.text])).toEqual([["창백함", "얼굴이 창백해져서"]]);
  });

  it("starts what is left at a whole word when the rules' evidence ends inside one", () => {
    // The rules' 두통 evidence is "머리가 아프", which ends before the "고" of "아프고".
    const text = "어제부터 머리가 아프고 얼굴이 창백해졌어요.";
    const start = text.indexOf("머리");
    const part = { start, end: text.length - 1, status: "present" as const, text: text.slice(start, -1) };
    const found = outsideSymptoms(text, extractIntake(text, "2026-11-06"), [part]);
    expect(found.map((symptom) => symptom.text)).toEqual(["얼굴이 창백해졌어요"]);
  });

  it("drops what is left of such a part when it names no symptom", () => {
    const text = "어제부터 머리가 아파요.";
    const part = { start: 0, end: text.length - 1, status: "present" as const, text: text.slice(0, -1) };
    expect(outsideSymptoms(text, extractIntake(text, "2026-11-06"), [part])).toEqual([]);
  });
});

describe("namePart", () => {
  it("names a part as a listed symptom the rules missed, not as one they already reported", () => {
    expect(namePart("기침할 때마다 피가 섞여 나와요", new Set(["기침"]))).toBe("객혈");
    expect(namePart("귀에서 이상한 소리가 계속 들려요", new Set())).toBe("이명");
    expect(namePart("손발이 자꾸 차가워져서", new Set())).toBe("손발 차가움");
    expect(namePart("코에서 조금씩 피가 나는 것 같아요", new Set())).toBe("코피");
  });

  it("does not name by color alone, nor across words", () => {
    expect(namePart("변에 붉은색이 섞여 나오긴 하는데", new Set())).not.toBe("혈변");
    expect(namePart("가슴이 가끔씩 아프기도 하구요", new Set(["흉통"]))).not.toBe("치통");
  });
});

describe("nameSymptom", () => {
  it("does not read a word across a space: 소변 색이 빨개요 is not 발진 (이빨)", () => {
    expect(nameSymptom("소변 색이 빨개요")).toBe("기타");
    expect(nameSymptom("소변이 빨개요")).toBe("기타");
    expect(nameSymptom("피부가 빨갛게 올라왔어요")).toBe("발진");
  });
});

describe("sourcePhrase", () => {
  const text = "어제부터 머리가 아프고 열이 38도까지 났어요. 기침은 없어요.";
  it("widens the rules' evidence to whole words", () => {
    expect(sourcePhrase(text, "머리가 아프")).toBe("머리가 아프고");
    expect(sourcePhrase(text, "기침은 없")).toBe("기침은 없어요");
  });
  it("takes the next word after a very short one", () => {
    expect(sourcePhrase(text, "열이 ")).toBe("열이 38도까지");
  });
  it("keeps evidence it cannot find, such as the rules' rewritten copy", () => {
    expect(sourcePhrase("배 아픔", "배 아파")).toBe("배 아파");
  });
});
