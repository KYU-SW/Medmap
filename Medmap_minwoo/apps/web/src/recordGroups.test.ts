import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  createRecordGroup,
  deleteRecordGroup,
  getCurrentRecordGroupId,
  LEGACY_RECORD_GROUP_ID,
  mergeRecordGroups,
  prepareRecordGroups,
  setCurrentRecordGroupId,
  updateRecordGroupProfile,
} from "./recordGroups";
import { record } from "./testRecords";

beforeEach(() => {
  const store = new Map<string, string>();
  vi.stubGlobal("localStorage", {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => store.set(key, value),
    removeItem: (key: string) => store.delete(key),
  });
});

const group = (id: string, createdAt: string) => ({ id, name: id, createdAt });

describe("prepareRecordGroups", () => {
  it("creates one empty group on first use", () => {
    const groups = prepareRecordGroups([]);
    expect(groups).toHaveLength(1);
    expect(prepareRecordGroups([]).map((item) => item.id)).toEqual(groups.map((item) => item.id));
  });

  it("gathers records saved before groups existed into one legacy group", () => {
    const old = { ...record("a", "2026-09-30T09:00:00.000Z", []), recordGroupId: undefined };
    const groups = prepareRecordGroups([old as never, record("b", "2026-10-01T09:00:00.000Z", [])]);
    expect(groups.map((item) => item.id)).toEqual(["group-1", LEGACY_RECORD_GROUP_ID]);
    expect(groups[1].createdAt).toBe("2026-09-30T09:00:00.000Z");
  });
});

describe("record groups", () => {
  it("adds only new groups from a backup, newest first", () => {
    mergeRecordGroups([group("a", "2026-10-01T00:00:00.000Z")]);
    const groups = mergeRecordGroups([
      { ...group("a", "2026-10-01T00:00:00.000Z"), name: "changed" },
      group("b", "2026-10-02T00:00:00.000Z"),
    ]);
    expect(groups.map((item) => [item.id, item.name])).toEqual([["b", "b"], ["a", "a"]]);
  });

  it("keeps the profile on the group it belongs to", () => {
    mergeRecordGroups([group("a", "2026-10-01T00:00:00.000Z"), group("b", "2026-10-02T00:00:00.000Z")]);
    const groups = updateRecordGroupProfile("a", { age: 34 });
    expect(groups.find((item) => item.id === "a")?.profile).toEqual({ age: 34 });
    expect(groups.find((item) => item.id === "b")?.profile).toBeUndefined();
  });

  it("falls back to the newest group when the current one was deleted", () => {
    const created = createRecordGroup();
    const groups = mergeRecordGroups([group("old", "2000-01-01T00:00:00.000Z")]);
    expect(getCurrentRecordGroupId(groups)).toBe(created.id);

    const remaining = deleteRecordGroup(created.id);
    expect(remaining.map((item) => item.id)).toEqual(["old"]);
    expect(getCurrentRecordGroupId(remaining)).toBe("old");
  });

  it("ignores a saved current id that no longer exists", () => {
    setCurrentRecordGroupId("missing");
    expect(getCurrentRecordGroupId([group("a", "2026-10-01T00:00:00.000Z")])).toBe("a");
  });
});
