import { describe, expect, it } from "vitest";
import { buildSymptomHistories, buildTimeline, changeTone } from "./timeline";
import { record, symptom } from "./testRecords";

function changes(records: Parameters<typeof buildTimeline>[0]): string[][] {
  return buildTimeline(records).map((entry) => entry.symptoms.map((item) => item.change));
}

describe("buildTimeline", () => {
  it("sorts records by creation time", () => {
    const timeline = buildTimeline([
      record("b", "2026-10-02T09:00:00.000Z", [symptom("두통")]),
      record("a", "2026-10-01T09:00:00.000Z", [symptom("두통")]),
    ]);
    expect(timeline.map((entry) => entry.id)).toEqual(["a", "b"]);
  });

  it("describes first records", () => {
    expect(changes([
      record("a", "2026-10-01T09:00:00.000Z", [
        symptom("두통"),
        symptom("발열", { status: "absent" }),
      ]),
    ])).toEqual([["처음 기록", "없음으로 기록"]]);
  });

  it("describes status changes and continued absence", () => {
    expect(changes([
      record("a", "2026-10-01T09:00:00.000Z", [symptom("두통"), symptom("발열", { status: "absent" })]),
      record("b", "2026-10-02T09:00:00.000Z", [symptom("두통", { status: "absent" }), symptom("발열", { status: "absent" })]),
      record("c", "2026-10-03T09:00:00.000Z", [symptom("두통")]),
    ])).toEqual([
      ["처음 기록", "없음으로 기록"],
      ["있음 → 없음", "계속 없음"],
      ["없음 → 있음"],
    ]);
  });

  it("prefers the stated trend over severity comparison", () => {
    expect(changes([
      record("a", "2026-10-01T09:00:00.000Z", [symptom("두통", { severity: "3/10점" })]),
      record("b", "2026-10-02T09:00:00.000Z", [symptom("두통", { severity: "8/10점", trend: "improving" })]),
      record("c", "2026-10-03T09:00:00.000Z", [symptom("두통", { trend: "worsening" })]),
      record("d", "2026-10-04T09:00:00.000Z", [symptom("두통", { trend: "unchanged" })]),
    ])).toEqual([
      ["처음 기록"],
      ["이전 기록보다 호전"],
      ["이전 기록보다 악화"],
      ["이전 기록과 변화 없음"],
    ]);
  });

  it("compares word and numeric severities", () => {
    expect(changes([
      record("a", "2026-10-01T09:00:00.000Z", [symptom("복통", { severity: "경미함" })]),
      record("b", "2026-10-02T09:00:00.000Z", [symptom("복통", { severity: "9/10점" })]),
      record("c", "2026-10-03T09:00:00.000Z", [symptom("복통", { severity: "심함" })]),
      record("d", "2026-10-04T09:00:00.000Z", [symptom("복통", { severity: "3/4점" })]),
      record("e", "2026-10-05T09:00:00.000Z", [symptom("복통")]),
    ])).toEqual([
      ["처음 기록"],
      ["이전 기록보다 강함"],
      ["이전 기록보다 약함"],
      ["비슷한 정도로 지속"],
      ["계속 있음"],
    ]);
  });
});

describe("changeTone", () => {
  it("reads each change as worse, better, same, new or unknown", () => {
    expect(["처음 기록", "없음 → 있음", "있음 → 없음", "이전 기록보다 호전", "이전 기록보다 강함", "계속 있음", "확실하지 않음", "없음으로 기록"]
      .map(changeTone)).toEqual(["new", "worse", "better", "better", "worse", "same", "unknown", "same"]);
  });
});

describe("buildSymptomHistories", () => {
  const histories = buildSymptomHistories(buildTimeline([
    record("a", "2026-10-01T09:00:00.000Z", [symptom("구토", { frequency: "5회" }), symptom("두통", { severity: "심함" })]),
    record("b", "2026-10-02T09:00:00.000Z", [symptom("구토", { frequency: "2회" })]),
    record("c", "2026-10-03T09:00:00.000Z", [symptom("두통", { status: "absent" }), symptom("기침"), symptom("흉통", { status: "absent" })]),
  ]));
  const byName = Object.fromEntries(histories.map((history) => [history.name, history]));

  it("puts each symptom's records side by side, oldest first", () => {
    expect(byName["구토"].points.map((point) => point.frequency)).toEqual(["5회", "2회"]);
    expect(byName["구토"].points.map((point) => point.level)).toEqual([1, 0.4]);
  });

  it("says in words how the first record compares with the latest", () => {
    // The patient's example: "이때는 5번 했는데 지금은 2번".
    expect(byName["구토"].overall).toEqual({ tone: "better", label: "줄었어요" });
    expect(byName["두통"].overall).toEqual({ tone: "better", label: "사라졌어요" });
    expect(byName["기침"].overall).toBeNull(); // one record: nothing to compare
  });

  it("reads a then → now count by the count now", () => {
    const [diarrhoea] = buildSymptomHistories(buildTimeline([
      record("a", "2026-10-01T09:00:00.000Z", [symptom("설사", { frequency: "하루 5회 → 2회" })]),
      record("b", "2026-10-02T09:00:00.000Z", [symptom("설사", { frequency: "하루 4회" })]),
    ]));
    expect(diarrhoea.points.map((point) => point.level)).toEqual([0.5, 1]);
  });

  it("leaves out a symptom the patient never had", () => {
    expect(byName["흉통"]).toBeUndefined();
  });

  it("lists the most recently recorded symptom first", () => {
    expect(histories.map((history) => history.name)).toEqual(["두통", "기침", "구토"]);
  });
});
