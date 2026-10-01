export const SUPPORTED_SYMPTOMS = [
  "두통", "발열", "기침", "호흡곤란", "가슴 답답함", "흉통", "복통", "구토",
  "인후통", "콧물", "코막힘", "가래", "오한", "근육통", "요통", "어지러움",
  "메스꺼움", "설사", "변비", "발진", "피로",
];

const FREQUENCY_SYMPTOMS = new Set(["구토", "설사"]);

export function tracksFrequency(name: string): boolean {
  return FREQUENCY_SYMPTOMS.has(name);
}

export function parseList(value: string): string[] {
  return [...new Set(value.split(/[,，、\n]/).map((item) => item.trim()).filter(Boolean))];
}
