import { describe, expect, it } from "vitest";
import { createBackup, parseBackup } from "./backup";
import { record, symptom } from "./testRecords";

const groups = [{ id: "group-1", name: "증상 기록 1", createdAt: "2026-10-01T09:00:00.000Z" }];
const records = [
  record("a", "2026-10-01T09:00:00.000Z", [symptom("두통")], { medical_history: ["고혈압"], others_symptoms: [] }),
];

describe("backup", () => {
  it("restores what it exported", () => {
    const text = JSON.stringify(createBackup(groups, records, "2026-10-01T10:00:00.000Z"));
    expect(parseBackup(text)).toEqual({ groups, records });
  });

  it("fills fields missing from older records", () => {
    const old = structuredClone(records[0]) as Record<string, any>;
    delete old.intake.medical_history;
    delete old.intake.unrecognized_fragments;
    const { records: restored } = parseBackup(JSON.stringify({ ...createBackup(groups, []), records: [old] }));
    expect(restored[0].intake.medical_history).toEqual([]);
    expect(restored[0].intake.unrecognized_fragments).toEqual([]);
  });

  it.each([
    ["not json", "백업 파일을 읽지 못했습니다"],
    [JSON.stringify({ format: "other" }), "MedMap 백업 파일이 아닙니다"],
    [JSON.stringify({ ...createBackup(groups, records), version: 2 }), "지원하지 않는 백업 파일 버전"],
    [JSON.stringify({ ...createBackup(groups, []), records: [{ id: "x" }] }), "올바르지 않은 기록"],
    [JSON.stringify({ ...createBackup(groups, []), records: [{ ...records[0], createdAt: "어제" }] }), "올바르지 않은 기록"],
  ])("rejects invalid backups (%#)", (text, message) => {
    expect(() => parseBackup(text)).toThrow(message);
  });
});
