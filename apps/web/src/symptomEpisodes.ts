import type { StoredIntakeRecord } from "./recordStorage";

type StoredSymptom = StoredIntakeRecord["intake"]["symptoms"][number];

export type SymptomEpisode = {
  id: string;
  name: string;
  status: "active" | "resolved";
  startedAt: string;
  lastRecordedAt: string;
  endedAt: string | null;
  statedOnset: string | null;
  peakSeverity: string | null;
  frequencies: string[];
  recordCount: number;
};

function severityValue(severity: string | null): number | null {
  if (!severity) return null;
  if (severity === "경미함") return 0.25;
  if (severity === "심함") return 0.75;
  const score = severity.match(/^(\d+)\/(\d+)점$/);
  if (!score) return null;
  const maximum = Number(score[2]);
  return maximum > 0 ? Number(score[1]) / maximum : null;
}

function strongerSeverity(current: string | null, candidate: string | null): string | null {
  if (!current) return candidate;
  if (!candidate) return current;
  const currentValue = severityValue(current);
  const candidateValue = severityValue(candidate);
  if (currentValue === null) return candidate;
  if (candidateValue === null) return current;
  return candidateValue > currentValue ? candidate : current;
}

function startEpisode(
  record: StoredIntakeRecord,
  symptom: StoredSymptom,
  sequence: number,
): SymptomEpisode {
  return {
    id: `${symptom.name}-${record.id}-${sequence}`,
    name: symptom.name,
    status: "active",
    startedAt: record.createdAt,
    lastRecordedAt: record.createdAt,
    endedAt: null,
    statedOnset: symptom.onset,
    peakSeverity: symptom.severity,
    frequencies: symptom.frequency ? [symptom.frequency] : [],
    recordCount: 1,
  };
}

export function buildSymptomEpisodes(records: StoredIntakeRecord[]): SymptomEpisode[] {
  const openEpisodes = new Map<string, SymptomEpisode>();
  const completedEpisodes: SymptomEpisode[] = [];
  let sequence = 0;

  for (const record of [...records].sort((left, right) => left.createdAt.localeCompare(right.createdAt))) {
    for (const symptom of record.intake.symptoms) {
      const open = openEpisodes.get(symptom.name);
      if (symptom.status === "present") {
        if (!open) {
          openEpisodes.set(symptom.name, startEpisode(record, symptom, sequence++));
          continue;
        }
        open.lastRecordedAt = record.createdAt;
        open.recordCount += 1;
        open.peakSeverity = strongerSeverity(open.peakSeverity, symptom.severity);
        if (symptom.frequency && !open.frequencies.includes(symptom.frequency)) {
          open.frequencies.push(symptom.frequency);
        }
        if (!open.statedOnset && symptom.onset) open.statedOnset = symptom.onset;
        continue;
      }

      if (open) {
        open.status = "resolved";
        open.lastRecordedAt = record.createdAt;
        open.endedAt = record.createdAt;
        open.recordCount += 1;
        completedEpisodes.push(open);
        openEpisodes.delete(symptom.name);
      }
    }
  }

  return [...completedEpisodes, ...openEpisodes.values()].sort((left, right) =>
    right.startedAt.localeCompare(left.startedAt),
  );
}
