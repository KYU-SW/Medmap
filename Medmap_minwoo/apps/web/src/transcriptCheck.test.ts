import { describe, expect, it } from "vitest";
import { factDifferences } from "./transcriptCheck";

const facts = (
  symptoms: Array<[string, string, string | null]>,
  medications: string[] = [],
  allergies: string[] = [],
) => ({ symptoms: symptoms.map(([name, status, onset]) => ({ name, status, onset })), medications, allergies });

describe("factDifferences", () => {
  it("is empty when the two transcripts give the same facts", () => {
    expect(factDifferences(
      facts([["두통", "present", "어제부터"]], ["타이레놀"]),
      facts([["두통", "present", "어제부터"]], ["타이레놀"]),
    )).toEqual([]);
  });

  it("names a symptom only one transcript found", () => {
    // On-device "아랫배가 크고 쑤시고" lost the abdominal pain turbo heard as "쿡쿡 쑤시고".
    expect(factDifferences(
      facts([["발열", "present", null]]),
      facts([["복통", "present", "어제 저녁부터"], ["발열", "present", null]]),
    )).toEqual(["복통: 없음 / 있음, 어제 저녁부터"]);
  });

  it("names differences in onset, presence, medicines and allergies", () => {
    expect(factDifferences(
      facts([["흉통", "present", null]], ["타이레놀"], ["페니실린"]),
      facts([["흉통", "absent", null]], [], ["페네실린"]),
    )).toEqual(["흉통: 있음 / 없음", "복용약: 타이레놀 / 없음", "알레르기: 페니실린 / 페네실린"]);
  });
});
