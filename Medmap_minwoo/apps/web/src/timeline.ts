import type { StoredIntakeRecord } from "./recordStorage";

type StoredSymptom = StoredIntakeRecord["intake"]["symptoms"][number];

export type TimelineSymptom = StoredSymptom & {
  change: string;
};

export type TimelineEntry = {
  id: string;
  createdAt: string;
  symptoms: TimelineSymptom[];
};

function severityValue(severity: string | null): number | null {
  if (!severity) return null;
  if (severity === "경미함") return 0.25;
  if (severity === "심함") return 0.75;
  const score = severity.match(/^(\d+)\/(\d+)점$/);
  if (!score) return null;
  const value = Number(score[1]);
  const maximum = Number(score[2]);
  return maximum > 0 ? value / maximum : null;
}

function describeChange(previous: StoredSymptom | undefined, current: StoredSymptom): string {
  if (current.status === "uncertain") return "확실하지 않음";
  if (!previous) return current.status === "present" ? "처음 기록" : "없음으로 기록";
  if (previous.status !== current.status) {
    return `${previous.status === "present" ? "있음" : "없음"} → ${
      current.status === "present" ? "있음" : "없음"
    }`;
  }
  if (current.status === "absent") return "계속 없음";
  if (current.trend === "improving") return "이전 기록보다 호전";
  if (current.trend === "worsening") return "이전 기록보다 악화";
  if (current.trend === "unchanged") return "이전 기록과 변화 없음";

  const previousValue = severityValue(previous.severity);
  const currentValue = severityValue(current.severity);
  if (previousValue !== null && currentValue !== null) {
    if (currentValue > previousValue + 0.05) return "이전 기록보다 강함";
    if (currentValue < previousValue - 0.05) return "이전 기록보다 약함";
    return "비슷한 정도로 지속";
  }
  return "계속 있음";
}

export function buildTimeline(records: StoredIntakeRecord[]): TimelineEntry[] {
  const latestBySymptom = new Map<string, StoredSymptom>();
  return [...records]
    .sort((left, right) => left.createdAt.localeCompare(right.createdAt))
    .map((record) => ({
      id: record.id,
      createdAt: record.createdAt,
      symptoms: record.intake.symptoms.map((symptom) => {
        const previous = latestBySymptom.get(symptom.name);
        if (symptom.status !== "uncertain") latestBySymptom.set(symptom.name, symptom);
        return { ...symptom, change: describeChange(previous, symptom) };
      }),
    }));
}
