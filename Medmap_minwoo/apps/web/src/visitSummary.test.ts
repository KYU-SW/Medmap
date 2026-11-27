import { describe, expect, it } from "vitest";
import { buildSymptomEpisodes } from "./symptomEpisodes";
import { buildVisitSummary, visitSummaryText } from "./visitSummary";
import { record, symptom } from "./testRecords";
import { extractIntake } from "./intake/extractor";
import { readSummary } from "./summaryView";
import { unsureUrgentSymptoms } from "./symptomOptions";

const records = [
  record("b", "2026-10-02T09:00:00.000Z", [symptom("두통", { status: "absent" }), symptom("구토", { frequency: "하루 2번" })], {
    medications: ["타이레놀", "소화제"],
  }),
  record("a", "2026-10-01T09:00:00.000Z", [symptom("두통", { onset: "그저께", severity: "심함" })], {
    medications: ["타이레놀"],
    allergies: ["페니실린"],
    medical_history: ["고혈압"],
  }),
];

describe("buildVisitSummary", () => {
  it("returns null without records", () => {
    expect(buildVisitSummary([], [])).toBeNull();
  });

  it("collects the record period, unique medications and allergies", () => {
    const summary = buildVisitSummary(records, buildSymptomEpisodes(records));
    expect(summary).toMatchObject({
      firstRecordedAt: "2026-10-01T09:00:00.000Z",
      lastRecordedAt: "2026-10-02T09:00:00.000Z",
      medications: ["타이레놀", "소화제"],
      allergies: ["페니실린"],
      medicalHistory: ["고혈압"],
    });
    expect(summary?.symptoms.map((item) => [item.name, item.status])).toEqual([
      ["구토", "active"],
      ["두통", "resolved"],
    ]);
  });
});

describe("visitSummaryText", () => {
  it("formats symptom lines and the disclaimer", () => {
    const summary = buildVisitSummary(records, buildSymptomEpisodes(records));
    const lines = visitSummaryText(summary!).split("\n");
    expect(lines).toContain("- 구토: 시작: 확인되지 않음 / 가장 심한 정도: 확인되지 않음 / 횟수: 하루 2번 / 기록 1회");
    // Resolved symptoms come after the current ones, as one short line with their period.
    expect(lines.indexOf("사라진 증상")).toBeGreaterThan(lines.indexOf("지금 있는 증상"));
    // A severe headache is worth mentioning but not a danger sign, so it is not labelled "위험 증상".
    expect(lines).toContain("- 두통: 10월 1일 ~ 10월 2일 / 가장 심한 정도: 심함");
    expect(lines).toContain("기록 기간 중 복용약: 타이레놀, 소화제");
    expect(lines).toContain("기록된 알레르기: 페니실린");
    expect(lines).toContain("과거력: 고혈압");
    expect(lines.at(-1)).toBe("이 내용은 사용자가 확인한 기록의 요약이며 진단 결과가 아닙니다.");
  });

  it("shows placeholders when nothing was confirmed", () => {
    const empty = [record("a", "2026-10-01T09:00:00.000Z", [])];
    const lines = visitSummaryText(buildVisitSummary(empty, [])!).split("\n");
    expect(lines).toContain("- 확인된 증상 없음");
    expect(lines).not.toContain("사라진 증상");
    expect(lines).toContain("기록 기간 중 복용약: 확인되지 않음");
    expect(lines).toContain("기록된 알레르기: 확인되지 않음");
    expect(lines).toContain("과거력: 확인되지 않음");
  });

  it("shows diarrhea frequency like vomiting", () => {
    const diarrhea = [record("a", "2026-10-01T09:00:00.000Z", [symptom("설사", { frequency: "하루 4회" })])];
    const text = visitSummaryText(buildVisitSummary(diarrhea, buildSymptomEpisodes(diarrhea))!);
    expect(text).toContain("- 설사: 시작: 확인되지 않음 / 가장 심한 정도: 확인되지 않음 / 횟수: 하루 4회 / 기록 1회");
  });

  it("keeps a resolved urgent symptom marked", () => {
    const fainted = [
      record("a", "2026-10-01T09:00:00.000Z", [symptom("기절")]),
      record("b", "2026-10-02T09:00:00.000Z", [symptom("기절", { status: "absent" })]),
    ];
    const summary = buildVisitSummary(fainted, buildSymptomEpisodes(fainted))!;
    expect(summary.urgentSymptoms).toEqual([]);
    expect(visitSummaryText(summary)).toContain("- 기절 (위험 증상): 10월 1일 ~ 10월 2일");
  });

  it("carries what brings a symptom on, where it spreads and how long it lasts (2026-11-27)", () => {
    const chest = [
      record("a", "2026-10-01T09:00:00.000Z", [symptom("흉통", { details: ["왼팔까지 퍼짐"] })]),
      record("b", "2026-10-02T09:00:00.000Z", [symptom("흉통", { details: ["계단 오를 때 나타남", "왼팔까지 퍼짐"] })]),
    ];
    const text = visitSummaryText(buildVisitSummary(chest, buildSymptomEpisodes(chest))!);
    expect(text).toContain(" / 특징: 왼팔까지 퍼짐, 계단 오를 때 나타남 / 기록 2회");
    expect(readSummary(text).active[0].facts).toContainEqual(["특징", "왼팔까지 퍼짐, 계단 오를 때 나타남"]);
  });

  it("keeps a danger symptom the patient was unsure of, for the doctor (2026-11-27)", () => {
    const unsure = [record("a", "2026-10-01T09:00:00.000Z", [symptom("흉통", { status: "uncertain" }), symptom("기침")])];
    const summary = buildVisitSummary(unsure, buildSymptomEpisodes(unsure))!;
    expect(summary.urgentSymptoms).toEqual([]);
    expect(summary.unsureUrgentSymptoms).toEqual(["흉통"]);
    const text = visitSummaryText(summary);
    expect(text).toContain("확실하지 않다고 했지만 확인이 필요한 위험 신호: 흉통");
    expect(readSummary(text).unsure).toEqual(["흉통"]);
  });

  it("drops an unsure danger symptom once a later record says it is not there, keeps it if later only unsure (2026-11-28)", () => {
    const settled = [
      record("a", "2026-10-01T09:00:00.000Z", [symptom("흉통", { status: "uncertain" })]),
      record("b", "2026-10-02T09:00:00.000Z", [symptom("흉통", { status: "absent" })]),
    ];
    expect(buildVisitSummary(settled, buildSymptomEpisodes(settled))!.unsureUrgentSymptoms).toEqual([]);
    const still = [
      record("a", "2026-10-01T09:00:00.000Z", [symptom("흉통", { status: "absent" })]),
      record("b", "2026-10-02T09:00:00.000Z", [symptom("흉통", { status: "uncertain" })]),
    ];
    expect(buildVisitSummary(still, buildSymptomEpisodes(still))!.unsureUrgentSymptoms).toEqual(["흉통"]);
    const present = [
      record("a", "2026-10-01T09:00:00.000Z", [symptom("흉통", { status: "uncertain" })]),
      record("b", "2026-10-02T09:00:00.000Z", [symptom("흉통")]),
    ];
    const summary = buildVisitSummary(present, buildSymptomEpisodes(present))!;
    expect(summary.unsureUrgentSymptoms).toEqual([]);
    expect(summary.urgentSymptoms).toEqual(["흉통"]);
  });

  it("finds unsure danger symptoms said in many ways (2026-11-27)", () => {
    const sentences: Array<[string, string]> = [
      ["가슴이 아픈지 잘 모르겠어요.", "흉통"],
      ["기절한 건지 잘 모르겠어요.", "기절"],
      ["말이 좀 어눌해진 것 같기도 하고 잘 모르겠어요.", "말 어눌함"],
      ["피를 토한 것 같기도 해요.", "토혈"],
      ["가래에 피가 섞인 것 같기도 한데 확실하진 않아요.", "객혈"],
      ["경련인지 그냥 떨린 건지 모르겠어요.", "경련"],
      ["한쪽 팔에 힘이 빠진 것 같기도 하고 잘 모르겠어요.", "마비"],
      // 2026-11-28 check of item 4
      ["얼굴 한쪽이 처진 것 같기도 해요.", "마비"],
      ["발음이 이상한가 싶기도 해요.", "말 어눌함"],
      ["잠깐 정신을 잃었던 것 같기도 해요.", "기절"],
      ["가슴이 아픈가 싶어요.", "흉통"],
    ];
    // Said as not there, it is neither unsure nor urgent: "가슴 통증은 확실히 없어요" was read as present before.
    for (const text of ["가슴 통증은 확실히 없어요.", "기절한 적은 정말 없어요."]) {
      const symptoms = extractIntake(text, "2026-11-28").symptoms;
      expect(symptoms.every((item) => item.status === "absent"), text).toBe(true);
    }
    for (const [text, name] of sentences) {
      expect(unsureUrgentSymptoms(extractIntake(text, "2026-11-27").symptoms), text).toContain(name);
    }
  });
});
