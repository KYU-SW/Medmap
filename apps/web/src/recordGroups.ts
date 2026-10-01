import type { StoredIntakeRecord } from "./recordStorage";

export const LEGACY_RECORD_GROUP_ID = "existing-records";

export type RecordGroup = {
  id: string;
  name: string;
  createdAt: string;
};

const GROUPS_KEY = "medmap-record-groups";
const CURRENT_GROUP_KEY = "medmap-current-record-group";

function defaultName(createdAt: string): string {
  return `증상 기록 ${new Intl.DateTimeFormat("ko-KR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(createdAt))}`;
}

function readSavedGroups(): RecordGroup[] {
  try {
    const value = JSON.parse(localStorage.getItem(GROUPS_KEY) || "[]");
    return Array.isArray(value) ? value : [];
  } catch {
    return [];
  }
}

function saveGroups(groups: RecordGroup[]): void {
  localStorage.setItem(GROUPS_KEY, JSON.stringify(groups));
}

export function prepareRecordGroups(records: StoredIntakeRecord[]): RecordGroup[] {
  const groups = readSavedGroups();
  const knownIds = new Set(groups.map((group) => group.id));
  if (records.some((record) => !record.recordGroupId) && !knownIds.has(LEGACY_RECORD_GROUP_ID)) {
    const oldest = [...records].sort((left, right) => left.createdAt.localeCompare(right.createdAt))[0];
    groups.push({
      id: LEGACY_RECORD_GROUP_ID,
      name: "기존 증상 기록",
      createdAt: oldest?.createdAt || new Date().toISOString(),
    });
    knownIds.add(LEGACY_RECORD_GROUP_ID);
  }
  for (const record of records) {
    if (!record.recordGroupId || knownIds.has(record.recordGroupId)) continue;
    groups.push({
      id: record.recordGroupId,
      name: defaultName(record.createdAt),
      createdAt: record.createdAt,
    });
    knownIds.add(record.recordGroupId);
  }
  if (groups.length === 0) groups.push(createRecordGroup(false));
  saveGroups(groups);
  return groups.sort((left, right) => right.createdAt.localeCompare(left.createdAt));
}

export function createRecordGroup(save = true): RecordGroup {
  const createdAt = new Date().toISOString();
  const group = { id: crypto.randomUUID(), name: defaultName(createdAt), createdAt };
  if (save) saveGroups([group, ...readSavedGroups()]);
  setCurrentRecordGroupId(group.id);
  return group;
}

export function getCurrentRecordGroupId(groups: RecordGroup[]): string {
  const saved = localStorage.getItem(CURRENT_GROUP_KEY);
  return groups.some((group) => group.id === saved) ? saved! : groups[0].id;
}

export function setCurrentRecordGroupId(id: string): void {
  localStorage.setItem(CURRENT_GROUP_KEY, id);
}
