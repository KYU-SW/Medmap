import type { StoredIntakeRecord } from "./recordStorage";

type StoredSymptom = StoredIntakeRecord["intake"]["symptoms"][number];

export function symptom(
  name: string,
  overrides: Partial<StoredSymptom> = {},
): StoredSymptom {
  return {
    name,
    status: "present",
    body_site: null,
    onset: null,
    severity: null,
    source_text: name,
    ...overrides,
  };
}

export function record(
  id: string,
  createdAt: string,
  symptoms: StoredSymptom[],
  overrides: Partial<StoredIntakeRecord["intake"]> = {},
): StoredIntakeRecord {
  return {
    id,
    recordGroupId: "group-1",
    createdAt,
    transcript: symptoms.map((item) => item.source_text).join(" "),
    intake: {
      symptoms,
      medications: [],
      allergies: [],
      unrecognized_fragments: [],
      needs_user_confirmation: false,
      ...overrides,
    },
  };
}
