import { describe, expect, it } from "vitest";
import { buildTimeline } from "./timeline";
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
