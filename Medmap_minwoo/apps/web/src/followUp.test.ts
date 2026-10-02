import { describe, expect, it } from "vitest";
import { followUpQuestions } from "./symptomOptions";
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
