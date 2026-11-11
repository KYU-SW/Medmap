import { describe, expect, it } from "vitest";
import { readSummary } from "./summaryView";
import { buildSymptomEpisodes } from "./symptomEpisodes";
import { record, symptom } from "./testRecords";
import { buildVisitSummary, visitSummaryText } from "./visitSummary";

const TEXT = [
  "MedMap 진료 전 증상 요약",
  "기본 정보: 34세 / 여성",
  "기록 기간: 2026. 11. 9. 오전 9:00 ~ 2026. 11. 11. 오후 8:00",
  "빨리 진료가 필요할 수 있는 증상: 흉통",
  "심하다고 한 증상: 복통",
  "지금 있는 증상",
  "- 복통(오른쪽 아랫배): 시작: 어제부터 (11월 10일) / 가장 심한 정도: 심함 / 최근 변화: 악화 중 / 기록 2회",
  "- 기침: 시작: 확인되지 않음 / 가장 심한 정도: 확인되지 않음 / 기록 1회",
  "사라진 증상",
  "- 두통 (위험 증상): 11월 1일~11월 3일 / 가장 심한 정도: 7/10점",
  "있는지 확실하지 않다고 한 증상: 오한",
  "주변 사람에 대해 말한 내용: 남편 기침",
  "기록 기간 중 복용약: 타이레놀 500mg",
  "기록된 알레르기: 페니실린",
  "과거력: 확인되지 않음",
  "이 내용은 사용자가 확인한 기록의 요약이며 진단 결과가 아닙니다.",
].join("\n");

describe("readSummary", () => {
  it("splits the summary text into parts for the doctor screen", () => {
    const view = readSummary(TEXT);
    expect(view.fields).toEqual([["기본 정보", "34세 / 여성"], ["기록 기간", "2026. 11. 9. 오전 9:00 ~ 2026. 11. 11. 오후 8:00"]]);
    expect(view.urgent).toEqual(["흉통"]);
    expect(view.severe).toEqual(["복통"]);
    expect(view.active[0]).toEqual({
      name: "복통", site: "오른쪽 아랫배", urgent: false,
      facts: [["시작", "어제부터 (11월 10일)"], ["가장 심한 정도", "심함"], ["최근 변화", "악화 중"], ["", "기록 2회"]],
    });
    expect(view.active[1].facts).toEqual([["", "기록 1회"]]); // "확인되지 않음" is left out
    expect(view.resolved[0]).toEqual({ name: "두통", site: null, urgent: true, facts: [["기간", "11월 1일~11월 3일"], ["가장 심한 정도", "7/10점"]] });
    expect(view.lists).toContainEqual(["알레르기", "페니실린"]);
    expect(view.lists).toContainEqual(["복용약", "타이레놀 500mg"]);
    expect(view.other).toEqual([]);
  });

  it("reads the app's own summary text with no line left over", () => {
    const records = [
      record("a", "2026-10-01T09:00:00.000Z", [symptom("흉통", {}), symptom("복통", { body_site: "오른쪽 아랫배", severity: "심함" })]),
      record("b", "2026-10-03T09:00:00.000Z", [symptom("복통", { severity: "중간", trend: "improving" }), symptom("흉통", { status: "absent" })]),
    ];
    const view = readSummary(visitSummaryText(buildVisitSummary(records, buildSymptomEpisodes(records))!));
    expect(view.other).toEqual([]);
    expect(view.active.map((item) => item.name)).toContain("복통");
    expect(view.active.find((item) => item.name === "복통")?.site).toBe("오른쪽 아랫배");
  });

  it("keeps a line it does not know instead of dropping it", () => {
    expect(readSummary("처음 보는 줄").other).toEqual(["처음 보는 줄"]);
  });
});
