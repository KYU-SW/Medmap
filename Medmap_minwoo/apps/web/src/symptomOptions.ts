export const SUPPORTED_SYMPTOMS = [
  "두통", "발열", "기침", "호흡곤란", "가슴 답답함", "흉통", "복통", "구토",
  "인후통", "콧물", "코막힘", "가래", "오한", "근육통", "요통", "어지러움",
  "메스꺼움", "설사", "변비", "발진", "피로",
  "두근거림", "저림", "소화불량", "속쓰림", "식욕부진", "불면", "부종",
  "귀 통증", "눈 통증", "치통", "식은땀",
  "가려움", "시야 이상", "떨림", "이명", "코피", "객혈", "토혈", "혈변", "혈뇨",
  "배뇨통", "빈뇨", "기절", "마비", "말 어눌함", "쉰 목소리", "체중 감소", "경련",
];

const FREQUENCY_SYMPTOMS = new Set(["구토", "설사"]);

// Symptoms that should send the patient to care quickly, whatever the cause.
const URGENT_SYMPTOMS = new Set(["흉통", "객혈", "토혈", "혈변", "기절", "마비", "말 어눌함", "경련"]);
// Common symptoms that are urgent only when the patient says they are severe.
const URGENT_WHEN_SEVERE = new Set(["호흡곤란", "두통", "복통"]);

function isSevere(severity: string | null | undefined): boolean {
  if (!severity) return false;
  if (severity === "심함") return true;
  const score = severity.match(/^(\d+)\/(\d+)점$/);
  return Boolean(score && Number(score[2]) > 0 && Number(score[1]) / Number(score[2]) >= 0.7);
}

export function urgentSymptoms(
  symptoms: Array<{ name: string; status: string; severity?: string | null }>,
): string[] {
  return [...new Set(
    symptoms
      .filter((symptom) => symptom.status === "present")
      .filter((symptom) =>
        URGENT_SYMPTOMS.has(symptom.name)
        || (URGENT_WHEN_SEVERE.has(symptom.name) && isSevere(symptom.severity)))
      .map((symptom) => symptom.name),
  )];
}

export const URGENT_NOTICE =
  "빨리 진료가 필요할 수 있는 증상입니다. 갑자기 생겼거나 심해지고 있다면 바로 119에 연락하거나 "
  + "응급실을 찾으세요. 이 안내는 진단이 아닙니다.";

export function tracksFrequency(name: string): boolean {
  return FREQUENCY_SYMPTOMS.has(name);
}

export function parseList(value: string): string[] {
  return [...new Set(value.split(/[,，、\n]/).map((item) => item.trim()).filter(Boolean))];
}
