import type { RecordGroup } from "./recordGroups";
import type { StoredIntakeRecord } from "./recordStorage";

const BACKUP_FORMAT = "medmap-backup";
const BACKUP_VERSION = 1;

export type MedMapBackup = {
  format: typeof BACKUP_FORMAT;
  version: typeof BACKUP_VERSION;
  exportedAt: string;
  groups: RecordGroup[];
  records: StoredIntakeRecord[];
};

export function createBackup(
  groups: RecordGroup[],
  records: StoredIntakeRecord[],
  exportedAt = new Date().toISOString(),
): MedMapBackup {
  return { format: BACKUP_FORMAT, version: BACKUP_VERSION, exportedAt, groups, records };
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isStringList(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function isGroup(value: unknown): value is RecordGroup {
  return isObject(value)
    && typeof value.id === "string"
    && typeof value.name === "string"
    && typeof value.createdAt === "string";
}

function isSymptom(value: unknown): boolean {
  return isObject(value)
    && typeof value.name === "string"
    && (value.status === "present" || value.status === "absent")
    && typeof value.source_text === "string";
}

function toRecord(value: unknown): StoredIntakeRecord | null {
  if (!isObject(value) || !isObject(value.intake)) return null;
  const { intake } = value;
  if (
    typeof value.id !== "string"
    || typeof value.createdAt !== "string"
    || Number.isNaN(Date.parse(value.createdAt))
    || typeof value.transcript !== "string"
    || (value.recordGroupId !== undefined && typeof value.recordGroupId !== "string")
    || !Array.isArray(intake.symptoms)
    || !intake.symptoms.every(isSymptom)
    || !isStringList(intake.medications)
    || !isStringList(intake.allergies)
    || (intake.medical_history !== undefined && !isStringList(intake.medical_history))
  ) {
    return null;
  }
  return {
    id: value.id,
    recordGroupId: value.recordGroupId as string | undefined,
    createdAt: value.createdAt,
    transcript: value.transcript,
    intake: {
      symptoms: intake.symptoms as StoredIntakeRecord["intake"]["symptoms"],
      medications: intake.medications,
      allergies: intake.allergies,
      medical_history: (intake.medical_history as string[] | undefined) ?? [],
      unrecognized_fragments: isStringList(intake.unrecognized_fragments) ? intake.unrecognized_fragments : [],
      needs_user_confirmation: false,
    },
  };
}

export function parseBackup(text: string): { groups: RecordGroup[]; records: StoredIntakeRecord[] } {
  let value: unknown;
  try {
    value = JSON.parse(text);
  } catch {
    throw new Error("백업 파일을 읽지 못했습니다. MedMap에서 내보낸 파일인지 확인해 주세요.");
  }
  if (!isObject(value) || value.format !== BACKUP_FORMAT) {
    throw new Error("MedMap 백업 파일이 아닙니다.");
  }
  if (value.version !== BACKUP_VERSION) {
    throw new Error("지원하지 않는 백업 파일 버전입니다.");
  }
  if (!Array.isArray(value.groups) || !Array.isArray(value.records)) {
    throw new Error("백업 파일의 내용이 올바르지 않습니다.");
  }
  const groups = value.groups.filter(isGroup);
  const records = value.records.map(toRecord);
  if (groups.length !== value.groups.length || records.some((record) => record === null)) {
    throw new Error("백업 파일에 올바르지 않은 기록이 있어 가져오지 않았습니다.");
  }
  return { groups, records: records as StoredIntakeRecord[] };
}
