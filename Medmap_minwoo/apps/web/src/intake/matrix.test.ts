// Whole classes of phrasing, not single sentences (2026-11-11, user: "하나씩 보완하지 말고 미리"): every body part ×
// particle × word in between × ending, and every onset × connector. A rule change that breaks one combination fails here.
import { describe, expect, it } from "vitest";
import { extractIntake } from "./extractor";

const hasFinalConsonant = (word: string) => (word.charCodeAt(word.length - 1) - 0xac00) % 28 !== 0;
const withParticle = (word: string, particle: "이/가" | "은/는" | "도") =>
  word + (particle === "도" ? "도" : hasFinalConsonant(word) ? particle[0] : particle[2]);
const read = (text: string, name: string) =>
  extractIntake(text, "2026-11-11").symptoms.find((symptom) => symptom.name === name);
const PARTICLES = ["이/가", "은/는", "도"] as const;
// Words said between the part and the verb, both for "아파요" and "안 아파요"; the last ones only fit a "not".
const BETWEEN = ["", "원래", "평소에", "요즘", "좀", "자주", "지금은", "아직", "가끔", "같이", "함께"];
const ONLY_NOT = ["별로", "전혀", "하나도", "딱히", "그렇게"];

function wrongOnes(cases: Array<[string, string, "present" | "absent"]>) {
  return cases.filter(([text, name, status]) => read(text, name)?.status !== status).map(([text]) => text);
}

describe("pain at a body part, however it is said", () => {
  const PARTS: Record<string, string> = {
    배: "복통", 명치: "복통", 옆구리: "복통", 머리: "두통", 허리: "요통", 목: "인후통", 가슴: "흉통",
    무릎: "관절 통증", 어깨: "관절 통증", 손목: "관절 통증", 귀: "귀 통증", 눈: "눈 통증", 이: "치통", 혀: "입안 통증",
  };
  const cases: Array<[string, string, "present" | "absent"]> = [];
  for (const [part, name] of Object.entries(PARTS)) for (const particle of PARTICLES) {
    const subject = withParticle(part, particle);
    for (const word of BETWEEN) {
      const at = `${subject} ${word ? `${word} ` : ""}`;
      for (const ending of ["아파요", "아팠어요", "아프고 열도 나요", "아픈데 참을 만해요"]) cases.push([at + ending, name, "present"]);
      for (const ending of ["안 아파요", "아프지 않아요", "안 아프고 열만 나요", "아프진 않아요"]) cases.push([at + ending, name, "absent"]);
    }
    for (const word of ONLY_NOT) for (const ending of ["안 아파요", "아프지 않아요"]) cases.push([`${subject} ${word} ${ending}`, name, "absent"]);
  }
  it(`reads all ${cases.length} as 있음 or 없음`, () => expect(wrongOnes(cases)).toEqual([]));
});

describe("other common symptoms, however they are said", () => {
  // [symptom, subject, ways of saying it is there, ways of saying it is not]
  const SAID: Array<[string, string, string[], string[]]> = [
    ["발열", "열", ["나요", "났어요"], ["안 나요", "나지 않아요", "없어요"]],
    ["기침", "기침", ["나요", "해요"], ["안 나요", "안 해요", "하지 않아요", "없어요"]],
    ["콧물", "콧물", ["나요", "흘러요"], ["안 나요", "없어요"]],
    ["가래", "가래", ["나와요", "껴요"], ["안 나와요", "없어요"]],
    ["설사", "설사", ["해요", "했어요"], ["안 해요", "하지 않았어요", "없어요"]],
    ["구토", "구토", ["했어요"], ["없어요"]],
    ["어지러움", "어지러움", ["있어요"], ["없어요"]],
    ["호흡곤란", "숨", ["차요", "가빠요"], ["안 차요", "차지 않아요"]],
    ["가려움", "몸", ["가려워요"], ["안 가려워요", "가렵지 않아요"]],
    ["메스꺼움", "속", ["메스꺼워요", "울렁거려요"], ["안 메스꺼워요", "메스껍지 않아요"]],
    ["저림", "손", ["저려요"], ["안 저려요", "저리지 않아요"]],
    ["근육통", "온몸", ["쑤셔요"], ["안 쑤셔요"]],
    ["부종", "다리", ["부었어요", "부어요"], ["안 부었어요", "붓지 않아요"]],
    ["코막힘", "코", ["막혀요"], ["안 막혀요", "막히지 않아요"]],
    ["두근거림", "가슴", ["두근거려요"], ["안 두근거려요", "두근거리지 않아요"]],
    ["불면", "잠", ["못 자요"], []],
  ];
  const cases: Array<[string, string, "present" | "absent"]> = [];
  for (const [name, subject, there, notThere] of SAID) for (const particle of PARTICLES) {
    const head = withParticle(subject, particle);
    for (const word of ["", "원래", "요즘", "좀", "지금은", "아직", "평소에", "같이"]) {
      const at = `${head} ${word ? `${word} ` : ""}`;
      for (const verb of there) if (!(word === "원래" && verb.endsWith("었어요"))) cases.push([at + verb, name, "present"]);
      for (const verb of notThere) cases.push([at + verb, name, "absent"]);
    }
    for (const word of ["별로", "전혀", "딱히"]) for (const verb of notThere) cases.push([`${head} ${word} ${verb}`, name, "absent"]);
  }
  it(`reads all ${cases.length} as 있음 or 없음`, () => expect(wrongOnes(cases)).toEqual([]));
});

describe("one onset for symptoms said together", () => {
  const FIRST = [["기침을 하", "기침"], ["열이 나", "발열"], ["머리가 아프", "두통"], ["콧물이 나", "콧물"]];
  const SECOND = [["복통이 있어요", "복통"], ["배가 아파요", "복통"], ["목도 아파요", "인후통"], ["설사를 해요", "설사"]];
  const JOINS = ["고 ", "고, ", "고요 ", "구 ", "고 그리고 ", "고 또 ", "면서 ", "며 ", "는데 "];
  const wrong: string[] = [];
  let count = 0;
  for (const onset of ["어제부터", "사흘 전부터", "오늘 아침부터", "지난주부터", "며칠 전부터", "세 시간 전부터"]) {
    for (const [first, firstName] of FIRST) for (const [second, secondName] of SECOND) for (const join of JOINS) {
      // "하는데", "나는데", "아픈데": the stem takes 는/ㄴ before 데.
      const stem = join === "는데 " ? (first.endsWith("아프") ? `${first.slice(0, -1)}픈데 ` : `${first}는데 `) : first + join;
      const text = `${onset} ${stem}${second}`;
      count += 1;
      const found = extractIntake(text, "2026-11-11").symptoms;
      const a = found.find((symptom) => symptom.name === firstName);
      const b = found.find((symptom) => symptom.name === secondName);
      if (!a?.onset || a.onset !== b?.onset) wrong.push(text);
    }
  }
  it(`gives the second symptom the same onset in all ${count}`, () => expect(wrong).toEqual([]));

  it("does not carry an onset into a new sentence or onto a long-standing symptom", () => {
    expect(read("어제부터 기침을 해요. 복통도 있어요.", "복통")?.onset).toBeNull();
    expect(read("어제부터 기침을 하고, 배는 원래 아파요", "복통")?.onset).toBe("원래부터");
    // "같이" (together) carries it even into a new sentence (2026-11-11 phone test).
    expect(read("어제부터 기침을 하고 머리가 너무 아파요 배도 같이 아팠어요", "복통")?.onset).toBe("어제부터");
  });
});
