import type { StoredIntakeRecord } from "./recordStorage";

type StoredSymptom = StoredIntakeRecord["intake"]["symptoms"][number];

export type ChangeTone = "new" | "worse" | "better" | "same" | "unknown";

export type TimelineSymptom = StoredSymptom & {
  change: string;
  tone: ChangeTone;
};

// How the change reads at a glance: worse (↑), better (↓), unchanged (=), new, or not sure.
export function changeTone(change: string): ChangeTone {
  if (change === "확실하지 않음") return "unknown";
  if (change === "처음 기록") return "new";
  if (change === "없음 → 있음") return "worse";
  if (change === "있음 → 없음" || change.includes("호전") || change.includes("약함")) return "better";
  if (change.includes("악화") || change.includes("강함")) return "worse";
  return "same";
}

export type TimelineEntry = {
  id: string;
  createdAt: string;
  symptoms: TimelineSymptom[];
};

function severityValue(severity: string | null): number | null {
  if (!severity) return null;
  if (severity === "경미함") return 0.25;
  if (severity === "중간") return 0.5;
  if (severity === "심함") return 0.75;
  // "7/10점 → 4/10점" (then → now): the latest score counts.
  const score = severity.split("→").pop()!.trim().match(/^(\d+)\/(\d+)점$/);
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
        const change = describeChange(previous, symptom);
        return { ...symptom, change, tone: changeTone(change) };
      }),
    }));
}

export type SymptomHistoryPoint = TimelineSymptom & {
  createdAt: string;
  /** 0–1 for the bar: the count against the most counted record, or how bad it was; null when unknown. */
  level: number | null;
};

export type SymptomHistory = {
  name: string;
  points: SymptomHistoryPoint[]; // oldest first
  /** First recorded state against the latest one, in words: "줄었어요", "사라졌어요", ... */
  overall: { tone: ChangeTone; label: string } | null;
};

function count(frequency: string | null | undefined): number | null {
  // "하루 5회 → 2회" (then → now) counts the latest; "3~4회" counts the upper end.
  const match = frequency?.split("→").pop()?.match(/(\d+)\s*회/);
  return match ? Number(match[1]) : null;
}

function overall(points: SymptomHistoryPoint[]): SymptomHistory["overall"] {
  const known = points.filter((point) => point.status !== "uncertain");
  if (known.length < 2) return null;
  const first = known[0];
  const last = known[known.length - 1];
  if (first.status === "present" && last.status === "absent") return { tone: "better", label: "사라졌어요" };
  if (first.status === "absent" && last.status === "present") return { tone: "worse", label: "다시 생겼어요" };
  if (last.status === "absent") return { tone: "same", label: "계속 없어요" };
  if (first.level === null || last.level === null) return { tone: "same", label: "계속 있어요" };
  if (last.level > first.level + 0.05) return { tone: "worse", label: "늘었어요" };
  if (last.level < first.level - 0.05) return { tone: "better", label: "줄었어요" };
  return { tone: "same", label: "비슷해요" };
}

/** Each symptom the patient has had, its records side by side ("구토 5회 → 2회"), most recent first. */
export function buildSymptomHistories(entries: TimelineEntry[]): SymptomHistory[] {
  const byName = new Map<string, Array<TimelineSymptom & { createdAt: string }>>();
  for (const entry of entries) {
    for (const symptom of entry.symptoms) {
      byName.set(symptom.name, [...(byName.get(symptom.name) ?? []), { ...symptom, createdAt: entry.createdAt }]);
    }
  }
  return [...byName].map(([name, records]) => {
    const most = Math.max(0, ...records.map((record) => count(record.frequency) ?? 0));
    const points = records
      .sort((left, right) => left.createdAt.localeCompare(right.createdAt))
      .map((record) => {
        const counted = count(record.frequency);
        const level = record.status === "absent" ? 0
          : counted !== null && most > 0 ? counted / most
            : severityValue(record.severity);
        return { ...record, level };
      });
    return { name, points, overall: overall(points) };
  })
    // "가슴 통증은 없어요" every time is not a symptom to follow.
    .filter((history) => history.points.some((point) => point.status === "present"))
    .sort((left, right) =>
    right.points[right.points.length - 1].createdAt.localeCompare(left.points[left.points.length - 1].createdAt));
}
