import { describe, expect, it } from "vitest";
import { createBackup, parseBackup } from "./backup";
import { buildSymptomEpisodes } from "./symptomEpisodes";
import { urgentSymptoms } from "./symptomOptions";
import { record, symptom } from "./testRecords";
import { buildTimeline } from "./timeline";
import { buildVisitSummary, visitSummaryText } from "./visitSummary";

describe("urgentSymptoms", () => {
  it("always flags red-flag symptoms that are present", () => {
    expect(urgentSymptoms([
      symptom("흉통"),
      symptom("마비"),
      symptom("객혈", { status: "absent" }),
      symptom("기절", { status: "uncertain" }),
      symptom("기침"),
    ])).toEqual(["흉통", "마비"]);
  });

  it("flags common symptoms only when they are severe", () => {
    expect(urgentSymptoms([
      symptom("호흡곤란", { severity: "경미함" }),
      symptom("복통", { severity: "8/10점" }),
      symptom("두통", { severity: "심함" }),
      symptom("호흡곤란", { severity: null }),
    ])).toEqual(["복통", "두통"]);
  });
});

describe("uncertain symptoms", () => {
  const records = [
    record("a", "2026-10-01T09:00:00.000Z", [symptom("기침")]),
    record("b", "2026-10-02T09:00:00.000Z", [symptom("기침", { status: "uncertain" }), symptom("발열", { status: "uncertain" })]),
  ];

  it("do not end or start an episode", () => {
    expect(buildSymptomEpisodes(records).map((episode) => [episode.name, episode.status, episode.recordCount]))
      .toEqual([["기침", "active", 1]]);
  });

  it("show as uncertain on the timeline without replacing the last known state", () => {
    const timeline = buildTimeline([
      ...records,
      record("c", "2026-10-03T09:00:00.000Z", [symptom("기침")]),
    ]);
    expect(timeline.map((entry) => entry.symptoms.map((item) => item.change))).toEqual([
      ["처음 기록"],
      ["확실하지 않음", "확실하지 않음"],
      ["계속 있음"],
    ]);
  });

  it("are listed separately in the visit summary", () => {
    const summary = buildVisitSummary(records, buildSymptomEpisodes(records))!;
    expect(summary.uncertainSymptoms).toEqual(["발열"]);
    expect(visitSummaryText(summary)).toContain("있는지 확실하지 않다고 한 증상: 발열");
  });
});

describe("other people and urgent notes in the visit summary", () => {
  const records = [
    record("a", "2026-10-01T09:00:00.000Z", [symptom("흉통")], {
      others_symptoms: [{ person: "남편", symptom: "기침", source_text: "기침을 해" }],
    }),
  ];

  it("keeps other people's symptoms out of the patient's episodes", () => {
    const summary = buildVisitSummary(records, buildSymptomEpisodes(records))!;
    expect(summary.symptoms.map((episode) => episode.name)).toEqual(["흉통"]);
    expect(summary.othersSymptoms).toEqual(["남편 기침"]);
    expect(summary.urgentSymptoms).toEqual(["흉통"]);
    const text = visitSummaryText(summary);
    expect(text).toContain("빨리 진료가 필요할 수 있는 증상: 흉통");
    expect(text).toContain("주변 사람에 대해 말한 내용: 남편 기침");
  });

  it("survives a backup round trip", () => {
    const groups = [{ id: "group-1", name: "기록", createdAt: "2026-10-01T09:00:00.000Z" }];
    const uncertain = [record("b", "2026-10-02T09:00:00.000Z", [symptom("발열", { status: "uncertain" })])];
    const restored = parseBackup(JSON.stringify(createBackup(groups, [...records, ...uncertain]))).records;
    expect(restored[0].intake.others_symptoms).toEqual(records[0].intake.others_symptoms);
    expect(restored[1].intake.symptoms[0].status).toBe("uncertain");
  });
});
