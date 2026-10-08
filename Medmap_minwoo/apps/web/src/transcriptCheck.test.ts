import { describe, expect, it } from "vitest";
import { describeChanges, factChanges, spokenNumbersToDigits } from "./transcriptCheck";

const facts = (
  symptoms: Array<[string, string, string | null]>,
  medications: string[] = [],
  allergies: string[] = [],
) => ({ symptoms: symptoms.map(([name, status, onset]) => ({ name, status, onset })), medications, allergies });

describe("factChanges", () => {
  it("is empty when the two transcripts give the same facts", () => {
    expect(factChanges(
      facts([["두통", "present", "어제부터"]], ["타이레놀"]),
      facts([["두통", "present", "어제부터"]], ["타이레놀"]),
    )).toEqual([]);
  });

  it("offers a symptom only turbo heard, with turbo's details", () => {
    // On-device "아랫배가 크고 쑤시고" lost the abdominal pain turbo heard as "쿡쿡 쑤시고".
    expect(factChanges(
      facts([["발열", "present", null]]),
      facts([["복통", "present", "어제 저녁부터"], ["발열", "present", null]]),
    )).toEqual([{
      kind: "symptom",
      name: "복통",
      label: "복통 추가: 있음, 어제 저녁부터",
      symptom: { name: "복통", status: "present", onset: "어제 저녁부터" },
      previous: null,
    }]);
  });

  it("offers each changed presence, medicine and allergy separately", () => {
    expect(factChanges(
      facts([["흉통", "present", null], ["두통", "present", null]], ["타일에 500mg"]),
      facts([["흉통", "absent", null]], ["타이레놀 500mg"], ["페니실린"]),
    ).map((change) => change.label)).toEqual([
      "흉통: 있음 → 없음",
      "복용약 추가: 타이레놀 500mg",
      "복용약 빼기: 타일에 500mg",
      "알레르기 추가: 페니실린",
    ]);
  });
});

describe("spokenNumbersToDigits", () => {
  it.each([
    ["체온이 삼십팔 점 오 도까지 올랐고", "체온이 38.5도까지 올랐고"],
    ["열이 삼십팔도까지 났어요", "열이 38도까지 났어요"],
    ["타이레는 오백 밀리그램을 한번에 먹었고", "타이레는 500mg을 한번에 먹었고"],
    ["타이레놀 오백밀리그램을", "타이레놀 500mg을"],
    ["이부프로펜 이백밀리그림을", "이부프로펜 200mg을"],
    ["이일 전 저녁부터", "2일 전 저녁부터"],
    ["구토는 삼회 했어요", "구토는 3회 했어요"],
    ["십점 만점에 칠점이었는데 지금은 사점 정도로", "10점 만점에 7점이었는데 지금은 4점 정도로"],
    ["삼십 팔 점 이 도였어요", "38.2도였어요"],
    ["십점 만점 육점 아니 사점 정도예요", "10점 만점 6점 아니 4점 정도예요"],
    // Not numbers: words that only look like them.
    ["이도 저도 아니에요", "이도 저도 아니에요"],
    ["오늘 사회 생활이 힘들어요", "오늘 사회 생활이 힘들어요"],
    ["일일이 확인했어요", "일일이 확인했어요"],
  ])("%s", (spoken, shown) => {
    expect(spokenNumbersToDigits(spoken)).toBe(shown);
  });
});

describe("factChanges onset wording", () => {
  it("replaces a past condition turbo heard as another name", () => {
    // on-device "위험 진단을 받았어요", turbo "위염 진단을 받았어요" (2026-10-09).
    const quick = { ...facts([]), medical_history: ["위험"] };
    const careful = { ...facts([]), medical_history: ["위염"] };
    expect(factChanges(quick, careful).map((change) => change.label)).toEqual(["과거력 추가: 위염", "과거력 빼기: 위험"]);
  });

  it("names only the onset when presence is the same", () => {
    expect(factChanges(
      facts([["기침", "present", "저녁부터"]]),
      facts([["기침", "present", "어제 저녁부터"]]),
    ).map((change) => change.label)).toEqual(["기침 시작: 저녁부터 → 어제 저녁부터"]);
  });
});

describe("describeChanges", () => {
  const symptom = (name: string, onset: string | null, source_text: string) =>
    ({ name, status: "present", onset, source_text });

  it("shows the words each recognizer heard, phone test 2026-10-07", () => {
    const quick = "어제 저녁부터 머리가 크고 기침이 심해졌어요 스타일에는 500mg을 한 번에 먹었고";
    const turbo = "어제 저녁부터 머리가 아프고 기침이 심해졌어요 타이레놀 500mg을 한번에 먹었고";
    const changes = factChanges(
      { symptoms: [symptom("기침", null, "기침이 ")], medications: [], allergies: [] },
      {
        symptoms: [symptom("두통", "어제 저녁부터", "머리가 아프"), symptom("기침", null, "기침이 ")],
        medications: ["타이레놀 500mg"],
        allergies: [],
      },
    );
    expect(describeChanges(quick, turbo, changes)).toEqual([
      "\"머리가 크고\" → \"머리가 아프고\" (두통 있음, 어제 저녁부터)",
      "\"스타일에는 500mg을\" → \"타이레놀 500mg을\"",
    ]);
  });

  it("names an onset heard differently", () => {
    const changes = factChanges(
      { symptoms: [symptom("기침", "저녁부터", "기침이 ")], medications: [], allergies: [] },
      { symptoms: [symptom("기침", "어제 저녁부터", "기침이 ")], medications: [], allergies: [] },
    );
    expect(describeChanges("어저 저녁부터 기침이 심해요", "어제 저녁부터 기침이 심해요", changes))
      .toEqual(["\"어저 저녁부터\" → \"어제 저녁부터\" (기침 시작)"]);
  });
});

describe("factChanges when turbo drops part of a long recording", () => {
  it("keeps what only the on-device text heard", () => {
    expect(factChanges(
      facts([["콧물", "present", null], ["복통", "absent", null]], ["혈압약 아침"], ["꽃가루"]),
      facts([["콧물", "present", null]], [], []),
    )).toEqual([]);
  });
});

describe("factChanges for how bad, how often and which way", () => {
  const pain = (severity: string | null, trend: string | null) =>
    ({ name: "복통", status: "present", onset: null, source_text: "배는 처음엔 많이 아팠", severity, trend });

  it("offers turbo's severity and trend, and keeps ours where turbo heard none", () => {
    // Recording 17 (2026-10-07): on-device "조금 나와줬어요" against turbo "많이 아팠는데 지금은 좀 나아졌어요".
    const changes = factChanges(
      { symptoms: [pain("경미함", null)], medications: [], allergies: [] },
      { symptoms: [pain("심함", "improving")], medications: [], allergies: [] },
    );
    expect(changes.map((change) => change.label)).toEqual(["복통 정도: 경미함 → 심함, 추세: 없음 → 좋아지는 중"]);
    expect(factChanges(
      { symptoms: [pain("심함", null)], medications: [], allergies: [] },
      { symptoms: [pain(null, null)], medications: [], allergies: [] },
    )).toEqual([]);
  });

  it("describes a change said away from the symptom's words by the change itself", () => {
    const text = "배는 처음엔 많이 아팠는데 지금은 좀 나아졌어요";
    const changes = factChanges(
      { symptoms: [pain("경미함", null)], medications: [], allergies: [] },
      { symptoms: [pain("심함", "improving")], medications: [], allergies: [] },
    );
    expect(describeChanges(text, text, changes)).toEqual(["복통 정도: 경미함 → 심함, 추세: 없음 → 좋아지는 중"]);
  });
});
