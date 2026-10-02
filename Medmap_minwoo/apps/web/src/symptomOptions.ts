export const SUPPORTED_SYMPTOMS = [
  "두통", "발열", "기침", "호흡곤란", "가슴 답답함", "흉통", "복통", "구토",
  "인후통", "콧물", "코막힘", "가래", "오한", "근육통", "요통", "어지러움",
  "메스꺼움", "설사", "변비", "발진", "피로",
  "두근거림", "저림", "소화불량", "속쓰림", "식욕부진", "불면", "부종",
  "귀 통증", "눈 통증", "치통", "식은땀",
  "가려움", "시야 이상", "떨림", "이명", "코피", "객혈", "토혈", "혈변", "혈뇨",
  "배뇨통", "빈뇨", "기절", "마비", "말 어눌함", "쉰 목소리", "체중 감소", "경련", "관절 통증",
];

// The patient's local calendar date, which the server uses to turn "어제부터" into a date.
export function localDateString(now = new Date()): string {
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

// Body sites that only repeat what the symptom name already says (두통 → 머리).
const DEFAULT_SITES = new Set(["머리", "복부", "가슴", "목", "코", "귀", "눈", "허리", "피부", "치아", "관절"]);

export function detailedSite(site: string | null | undefined): string | null {
  return site && !DEFAULT_SITES.has(site) ? site : null;
}

export function formatOnset(onset: string | null | undefined, onsetDate?: string | null): string | null {
  if (!onset) return null;
  const date = onsetDate?.match(/^\d{4}-(\d{2})-(\d{2})$/);
  return date ? `${onset} (${Number(date[1])}월 ${Number(date[2])}일)` : onset;
}

const FREQUENCY_SYMPTOMS = new Set(["구토", "설사"]);

// Where exactly it hurts, offered when the record only has the default site (복통 → 복부).
export const SITE_CHOICES: Record<string, string[]> = {
  복통: ["윗배", "명치", "아랫배", "오른쪽 아랫배", "왼쪽 아랫배", "오른쪽 옆구리", "왼쪽 옆구리", "배 전체"],
  두통: ["앞머리", "뒷머리", "정수리", "오른쪽 머리", "왼쪽 머리", "머리 전체"],
  흉통: ["가슴 가운데", "왼쪽 가슴", "오른쪽 가슴"],
  요통: ["허리 가운데", "오른쪽 허리", "왼쪽 허리"],
  "관절 통증": ["무릎", "어깨", "발목", "손목", "팔꿈치", "고관절"],
};
const SEVERITY_QUESTION_SYMPTOMS = new Set([
  ...Object.keys(SITE_CHOICES), "인후통", "귀 통증", "눈 통증", "치통", "호흡곤란", "가슴 답답함",
]);

export type FollowUpQuestion = {
  key: string;
  symptom: string;
  field: "onset" | "body_site" | "severity" | "frequency";
  question: string;
  choices?: string[];
};

// Pre-visit questions for what the patient has not said yet: when it started, where exactly, how bad, how often.
export function followUpQuestions(
  symptoms: Array<{
    name: string;
    status: string;
    onset: string | null;
    body_site: string | null;
    severity: string | null;
    frequency?: string | null;
  }>,
): FollowUpQuestion[] {
  return symptoms.filter((symptom) => symptom.status === "present" && symptom.name).flatMap((symptom) => {
    const questions: FollowUpQuestion[] = [];
    const ask = (field: FollowUpQuestion["field"], question: string, choices?: string[]) =>
      questions.push({ key: `${symptom.name}:${field}`, symptom: symptom.name, field, question, choices });
    if (!symptom.onset) ask("onset", `${symptom.name} 증상은 언제부터 있었나요?`);
    if (SITE_CHOICES[symptom.name] && !detailedSite(symptom.body_site)) {
      ask("body_site", `${symptom.name}: 정확히 어디가 아픈가요?`, SITE_CHOICES[symptom.name]);
    }
    if (SEVERITY_QUESTION_SYMPTOMS.has(symptom.name) && !symptom.severity) {
      ask("severity", `${symptom.name}: 얼마나 심한가요?`, ["경미함", "중간", "심함"]);
    }
    if (tracksFrequency(symptom.name) && !symptom.frequency) {
      ask("frequency", `${symptom.name}: 하루에 몇 번 했나요?`, ["하루 1회", "하루 2회", "하루 3회", "하루 4회 이상"]);
    }
    return questions;
  });
}

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
