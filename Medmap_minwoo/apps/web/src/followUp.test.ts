import { describe, expect, it } from "vitest";
import { addMedicineDetail, followUpQuestions, medicinesWithoutDose, nameMedicine, unnamedMedicines } from "./symptomOptions";
import { symptom } from "./testRecords";

const asked = (symptoms: Parameters<typeof followUpQuestions>[0]) =>
  followUpQuestions(symptoms).map((question) => question.key);

describe("followUpQuestions", () => {
  it("asks when, where and how bad for a bare stomach ache", () => {
    const questions = followUpQuestions([symptom("복통", { body_site: "복부" })]);
    expect(questions.map((question) => question.field)).toEqual(["onset", "body_site", "severity"]);
    expect(questions[1].choices).toContain("오른쪽 아랫배");
  });

  it("stops asking what the patient already said", () => {
    expect(asked([
      symptom("복통", { body_site: "오른쪽 아랫배", onset: "어제부터", severity: "심함" }),
    ])).toEqual([]);
  });

  it("asks how often only for vomiting and diarrhea, and nothing for absent or uncertain symptoms", () => {
    expect(asked([
      symptom("구토", { onset: "오늘" }),
      symptom("기침", { onset: "오늘" }),
      symptom("발열", { status: "absent" }),
      symptom("두통", { status: "uncertain" }),
    ])).toEqual(["구토:frequency"]);
  });
});

describe("unnamed medicines", () => {
  const list = "타이레놀 500mg, 이름 모르는 약 자기 전 한 알";

  it("asks for the name of a pill taken without one", () => {
    expect(unnamedMedicines(list)).toEqual(["이름 모르는 약 자기 전 한 알"]);
    expect(unnamedMedicines("타이레놀")).toEqual([]);
  });

  it("puts the name in place and keeps the dose and timing", () => {
    expect(nameMedicine(list, "이름 모르는 약 자기 전 한 알", "졸피뎀")).toBe("타이레놀 500mg, 졸피뎀 자기 전 한 알");
  });
});

describe("medicines said by name only", () => {
  it("asks how much for a name without dose or timing", () => {
    expect(medicinesWithoutDose("타이레놀, 이부프로펜 200mg, 혈압약 아침, 이름 모르는 약 한 알")).toEqual(["타이레놀"]);
  });

  it("adds the answer to that line", () => {
    expect(addMedicineDetail("타이레놀, 혈압약 아침", "타이레놀", "한 알")).toBe("타이레놀 한 알, 혈압약 아침");
  });

  it("drops the name-only line when the unnamed pill turns out to be the same medicine", () => {
    expect(nameMedicine("타이레놀, 이름 모르는 약 자기 전 한 알", "이름 모르는 약 자기 전 한 알", "타이레놀"))
      .toBe("타이레놀 자기 전 한 알");
    // A line with its own dose may be a second time of day: kept for the patient to judge.
    expect(nameMedicine("타이레놀 500mg 아침, 이름 모르는 약 자기 전 한 알", "이름 모르는 약 자기 전 한 알", "타이레놀"))
      .toBe("타이레놀 500mg 아침, 타이레놀 자기 전 한 알");
  });
});
