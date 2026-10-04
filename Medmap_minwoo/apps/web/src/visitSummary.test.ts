import { describe, expect, it } from "vitest";
import { buildSymptomEpisodes } from "./symptomEpisodes";
import { buildVisitSummary, visitSummaryText } from "./visitSummary";
import { record, symptom } from "./testRecords";

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
    // A severe headache counts as urgent even after it went away.
    expect(lines).toContain("- 두통 (위험 증상): 10월 1일 ~ 10월 2일 / 가장 심한 정도: 심함");
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
});
