import { describe, expect, it } from "vitest";
import { buildSymptomEpisodes } from "./symptomEpisodes";
import { record, symptom } from "./testRecords";
import { buildTimeline } from "./timeline";
import { createBackup, parseBackup } from "./backup";
import { buildVisitSummary, profileText, visitSummaryText } from "./visitSummary";

describe("record quality", () => {
  it("keeps the stated onset date on the episode and in the summary text", () => {
    const records = [
      record("a", "2026-10-02T09:00:00.000Z", [symptom("두통", { onset: "어제부터", onset_date: "2026-10-01" })]),
    ];
    const episodes = buildSymptomEpisodes(records);
    expect(episodes[0].statedOnsetDate).toBe("2026-10-01");
    expect(visitSummaryText(buildVisitSummary(records, episodes)!)).toContain("시작: 어제부터 (10월 1일)");
  });

  it("orders moderate severity between mild and severe", () => {
    const timeline = buildTimeline([
      record("a", "2026-10-01T09:00:00.000Z", [symptom("복통", { severity: "경미함" })]),
      record("b", "2026-10-02T09:00:00.000Z", [symptom("복통", { severity: "중간" })]),
      record("c", "2026-10-03T09:00:00.000Z", [symptom("복통", { severity: "심함" })]),
    ]);
    expect(timeline.map((entry) => entry.symptoms[0].change)).toEqual([
      "처음 기록",
      "이전 기록보다 강함",
      "이전 기록보다 강함",
    ]);
    const [episode] = buildSymptomEpisodes([
      record("a", "2026-10-01T09:00:00.000Z", [symptom("복통", { severity: "중간" })]),
      record("b", "2026-10-02T09:00:00.000Z", [symptom("복통", { severity: "경미함" })]),
    ]);
    expect(episode.peakSeverity).toBe("중간");
  });
});

describe("body sites", () => {
  it("keeps the most specific site on the episode and shows it in the summary", () => {
    const records = [
      record("a", "2026-10-01T09:00:00.000Z", [symptom("복통", { body_site: "복부" })]),
      record("b", "2026-10-02T09:00:00.000Z", [symptom("복통", { body_site: "오른쪽 아랫배" })]),
    ];
    const episodes = buildSymptomEpisodes(records);
    expect(episodes[0].bodySite).toBe("오른쪽 아랫배");
    expect(visitSummaryText(buildVisitSummary(records, episodes)!)).toContain("- 복통(오른쪽 아랫배): 현재 있음");
  });

  it("does not repeat the default site of a symptom", () => {
    const records = [record("a", "2026-10-01T09:00:00.000Z", [symptom("두통", { body_site: "머리" })])];
    expect(buildSymptomEpisodes(records)[0].bodySite).toBeNull();
  });
});

describe("basic patient information", () => {
  const records = [record("a", "2026-10-01T09:00:00.000Z", [symptom("두통")])];

  it("is summarized in one line, pregnancy only for women", () => {
    expect(profileText({ age: 34, sex: "female", pregnancy: "no", smoking: "never", drinking: "yes" }))
      .toBe("34세 / 여성 / 임신 아님 / 비흡연 / 음주");
    expect(profileText({ sex: "male", pregnancy: "yes" })).toBe("남성");
    expect(profileText({})).toBeNull();
  });

  it("appears in the visit summary text", () => {
    const summary = buildVisitSummary(records, buildSymptomEpisodes(records), { age: 70, smoking: "former" })!;
    expect(visitSummaryText(summary).split("\n")[1]).toBe("기본 정보: 70세 / 과거 흡연");
  });

  it("travels with the record group in a backup", () => {
    const groups = [{ id: "group-1", name: "기록", createdAt: "2026-10-01T09:00:00.000Z", profile: { age: 34, sex: "female" as const } }];
    expect(parseBackup(JSON.stringify(createBackup(groups, records))).groups).toEqual(groups);
    const broken = [{ ...groups[0], profile: { age: -1 } }];
    expect(() => parseBackup(JSON.stringify(createBackup(broken, records)))).toThrow("올바르지 않은 기록");
  });
});
