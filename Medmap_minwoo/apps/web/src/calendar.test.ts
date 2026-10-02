import { describe, expect, it } from "vitest";
import { dayKey, monthGrid } from "./calendar";
import { buildSymptomEpisodes } from "./symptomEpisodes";
import { record, symptom } from "./testRecords";
import { buildTimeline } from "./timeline";

describe("monthGrid", () => {
  const records = [
    record("a", "2026-10-01T09:00:00", [symptom("두통")]),
    record("b", "2026-10-03T09:00:00", [symptom("두통", { trend: "improving" })]),
    record("c", "2026-10-03T20:00:00", [symptom("두통", { trend: "worsening" })]),
    record("d", "2026-10-05T09:00:00", [symptom("두통", { status: "absent" })]),
  ];
  const cells = monthGrid(2026, 9, buildTimeline(records), buildSymptomEpisodes(records));
  const day = (number: number) => cells.find((cell) => cell?.day === number);

  it("pads the first week and covers the whole month", () => {
    // 2026-10-01 is a Thursday.
    expect(cells.slice(0, 4)).toEqual([null, null, null, null]);
    expect(cells.filter(Boolean)).toHaveLength(31);
    expect(day(1)?.key).toBe("2026-10-01");
  });

  it("marks each recorded day with its most notable change", () => {
    expect(day(1)?.tone).toBe("new");
    expect(day(3)?.tone).toBe("worse");
    expect(day(5)?.tone).toBe("better");
    expect(day(2)?.tone).toBeNull();
  });

  it("shades the days between a symptom's first record and its end", () => {
    expect([1, 2, 5, 6].map((number) => day(number)?.inEpisode)).toEqual([true, true, true, false]);
  });

  it("uses the local date", () => {
    expect(dayKey(new Date(2026, 0, 9, 23, 30))).toBe("2026-01-09");
  });
});
