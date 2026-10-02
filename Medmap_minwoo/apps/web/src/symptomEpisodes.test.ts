import { describe, expect, it } from "vitest";
import { buildSymptomEpisodes } from "./symptomEpisodes";
import { record, symptom } from "./testRecords";

describe("buildSymptomEpisodes", () => {
  it("merges present records into one active episode", () => {
    const [episode, ...rest] = buildSymptomEpisodes([
      record("b", "2026-10-02T09:00:00.000Z", [
        symptom("구토", { severity: "8/10점", frequency: "하루 3번", trend: "worsening", onset: "어제" }),
      ]),
      record("a", "2026-10-01T09:00:00.000Z", [symptom("구토", { severity: "경미함", frequency: "하루 1번" })]),
      record("c", "2026-10-03T09:00:00.000Z", [symptom("구토", { severity: "심함", frequency: "하루 3번" })]),
    ]);

    expect(rest).toHaveLength(0);
    expect(episode).toMatchObject({
      name: "구토",
      status: "active",
      startedAt: "2026-10-01T09:00:00.000Z",
      lastRecordedAt: "2026-10-03T09:00:00.000Z",
      endedAt: null,
      statedOnset: "어제",
      peakSeverity: "8/10점",
      frequencies: ["하루 1번", "하루 3번"],
      latestTrend: "worsening",
      recordCount: 3,
    });
  });

  it("resolves an episode on an absent record and starts a new one later", () => {
    const episodes = buildSymptomEpisodes([
      record("a", "2026-10-01T09:00:00.000Z", [symptom("두통")]),
      record("b", "2026-10-02T09:00:00.000Z", [symptom("두통", { status: "absent" })]),
      record("c", "2026-10-03T09:00:00.000Z", [symptom("두통")]),
    ]);

    expect(episodes.map((episode) => [episode.status, episode.startedAt, episode.endedAt, episode.recordCount])).toEqual([
      ["active", "2026-10-03T09:00:00.000Z", null, 1],
      ["resolved", "2026-10-01T09:00:00.000Z", "2026-10-02T09:00:00.000Z", 2],
    ]);
    expect(new Set(episodes.map((episode) => episode.id)).size).toBe(2);
  });

  it("ignores absent records without an open episode", () => {
    expect(buildSymptomEpisodes([
      record("a", "2026-10-01T09:00:00.000Z", [symptom("발열", { status: "absent" })]),
    ])).toEqual([]);
  });

  it("keeps a scored severity over an unscored one", () => {
    const [episode] = buildSymptomEpisodes([
      record("a", "2026-10-01T09:00:00.000Z", [symptom("복통", { severity: "알 수 없음" })]),
      record("b", "2026-10-02T09:00:00.000Z", [symptom("복통", { severity: "경미함" })]),
      record("c", "2026-10-03T09:00:00.000Z", [symptom("복통", { severity: "알 수 없음" })]),
    ]);
    expect(episode.peakSeverity).toBe("경미함");
  });
});
