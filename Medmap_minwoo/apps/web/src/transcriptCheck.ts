// The phone shows the on-device recognizer's transcript at once and checks it against turbo in the background.
// Two transcripts often differ in harmless ways (spacing, "38.5°" or "38.5도"), so they are compared by what
// the intake rules take from them: only a difference in these facts is worth asking the patient about.

type Facts = {
  symptoms: Array<{ name: string; status: string; onset: string | null }>;
  medications: string[];
  allergies: string[];
};

const STATUS = { present: "있음", absent: "없음", uncertain: "확실하지 않음" } as Record<string, string>;

function symptomLines(facts: Facts): Map<string, string> {
  return new Map(facts.symptoms.map((symptom) => [
    symptom.name,
    `${STATUS[symptom.status] ?? symptom.status}${symptom.onset ? `, ${symptom.onset}` : ""}`,
  ]));
}

/** The facts on which the two transcripts disagree, in words for the patient; empty when they agree. */
export function factDifferences(quick: Facts, careful: Facts): string[] {
  const differences: string[] = [];
  const a = symptomLines(quick);
  const b = symptomLines(careful);
  for (const name of new Set([...a.keys(), ...b.keys()])) {
    if (a.get(name) !== b.get(name)) {
      differences.push(`${name}: ${a.get(name) ?? "없음"} / ${b.get(name) ?? "없음"}`);
    }
  }
  for (const [label, left, right] of [
    ["복용약", quick.medications, careful.medications],
    ["알레르기", quick.allergies, careful.allergies],
  ] as const) {
    const x = [...left].sort().join(", ");
    const y = [...right].sort().join(", ");
    if (x !== y) differences.push(`${label}: ${x || "없음"} / ${y || "없음"}`);
  }
  return differences;
}
