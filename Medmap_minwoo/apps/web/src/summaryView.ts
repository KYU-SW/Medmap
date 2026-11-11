// Reads the visit-summary text (visitSummaryText) back into parts, so the doctor screen can lay it out for a quick look
// (2026-11-11 user: the opened QR was one hard-to-read block). The QR format stays the text (docs/QR_FORMAT.md);
// a line this does not know is kept as it is under "other", so nothing said is ever dropped.

export type SummarySymptom = { name: string; site: string | null; urgent: boolean; facts: Array<[string, string]> };
export type SummaryView = {
  fields: Array<[string, string]>; // 기본 정보, 기록 기간
  urgent: string[]; // 빨리 진료가 필요할 수 있는 증상
  severe: string[]; // 심하다고 한 증상
  active: SummarySymptom[];
  resolved: SummarySymptom[];
  lists: Array<[string, string]>; // 복용약, 알레르기, 과거력, 확실하지 않은 증상, 주변 사람
  other: string[];
};

const LIST_LABELS = ["기록 기간 중 복용약", "기록된 알레르기", "과거력", "있는지 확실하지 않다고 한 증상", "주변 사람에 대해 말한 내용"];
const FIELD_LABELS = ["기본 정보", "기록 기간"];
const NONE = "확인되지 않음";

function symptomLine(line: string, resolved: boolean): SummarySymptom {
  const body = line.replace(/^-\s*/, "");
  const cut = body.indexOf(": ");
  const head = cut < 0 ? body : body.slice(0, cut);
  const rest = cut < 0 ? "" : body.slice(cut + 2);
  const urgent = head.includes("(위험 증상)");
  const named = head.replace(/\s*\(위험 증상\)/, "").match(/^(.*?)(?:\((.*)\))?$/)!;
  const facts: Array<[string, string]> = rest.split(" / ").filter(Boolean).map((part, index) => {
    const at = part.indexOf(": ");
    if (at >= 0) return [part.slice(0, at), part.slice(at + 2)];
    // "10월 1일~10월 3일" (a resolved symptom's period) or "기록 2회".
    return resolved && index === 0 ? ["기간", part] : ["", part];
  });
  return { name: named[1].trim(), site: named[2] ?? null, urgent, facts: facts.filter(([, value]) => value !== NONE) };
}

export function readSummary(text: string): SummaryView {
  const view: SummaryView = { fields: [], urgent: [], severe: [], active: [], resolved: [], lists: [], other: [] };
  let section: "active" | "resolved" | null = null;
  for (const line of text.split("\n").map((row) => row.trim()).filter(Boolean)) {
    if (line === "MedMap 진료 전 증상 요약" || line.startsWith("이 내용은 사용자가 확인한")) continue;
    if (line === "지금 있는 증상") { section = "active"; continue; }
    if (line === "사라진 증상") { section = "resolved"; continue; }
    if (line.startsWith("- ") && section) {
      if (line !== "- 확인된 증상 없음") view[section].push(symptomLine(line, section === "resolved"));
      continue;
    }
    section = null;
    const at = line.indexOf(": ");
    const [label, value] = at < 0 ? ["", line] : [line.slice(0, at), line.slice(at + 2)];
    if (label === "빨리 진료가 필요할 수 있는 증상") view.urgent = value.split(", ");
    else if (label === "심하다고 한 증상") view.severe = value.split(", ");
    else if (FIELD_LABELS.includes(label)) view.fields.push([label, value]);
    else if (LIST_LABELS.includes(label)) view.lists.push([label.replace("기록 기간 중 ", "").replace("기록된 ", ""), value]);
    else view.other.push(line);
  }
  return view;
}
