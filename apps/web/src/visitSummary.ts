import type { StoredIntakeRecord } from "./recordStorage";
import type { SymptomEpisode } from "./symptomEpisodes";
import { tracksFrequency, urgentSymptoms } from "./symptomOptions";

export type VisitSummary = {
  firstRecordedAt: string;
  lastRecordedAt: string;
  symptoms: SymptomEpisode[];
  medications: string[];
  allergies: string[];
  medicalHistory: string[];
  uncertainSymptoms: string[];
  othersSymptoms: string[];
  urgentSymptoms: string[];
};

export function buildVisitSummary(
  records: StoredIntakeRecord[],
  episodes: SymptomEpisode[],
): VisitSummary | null {
  if (records.length === 0) return null;
  const ordered = [...records].sort((left, right) => left.createdAt.localeCompare(right.createdAt));
  return {
    firstRecordedAt: ordered[0].createdAt,
    lastRecordedAt: ordered[ordered.length - 1].createdAt,
    symptoms: [...episodes].sort((left, right) => {
      if (left.status !== right.status) return left.status === "active" ? -1 : 1;
      return right.startedAt.localeCompare(left.startedAt);
    }),
    medications: [...new Set(ordered.flatMap((record) => record.intake.medications))],
    allergies: [...new Set(ordered.flatMap((record) => record.intake.allergies))],
    medicalHistory: [...new Set(ordered.flatMap((record) => record.intake.medical_history ?? []))],
    uncertainSymptoms: [...new Set(ordered.flatMap((record) => record.intake.symptoms
      .filter((symptom) => symptom.status === "uncertain")
      .map((symptom) => symptom.name)))]
      .filter((name) => !episodes.some((episode) => episode.name === name)),
    othersSymptoms: [...new Set(ordered.flatMap((record) => (record.intake.others_symptoms ?? [])
      .map((item) => `${item.person} ${item.symptom}`)))],
    urgentSymptoms: urgentSymptoms(episodes
      .filter((episode) => episode.status === "active")
      .map((episode) => ({ name: episode.name, status: "present", severity: episode.peakSeverity }))),
  };
}

export function visitSummaryText(summary: VisitSummary): string {
  const dateFormatter = new Intl.DateTimeFormat("ko-KR", {
    dateStyle: "medium",
    timeStyle: "short",
  });
  const symptomLines = summary.symptoms.map((symptom) =>
    `- ${symptom.name}: ${symptom.status === "active" ? "현재 있음" : "사라짐"}`
      + ` / 시작: ${symptom.statedOnset || "확인되지 않음"}`
      + ` / 가장 심한 정도: ${symptom.peakSeverity || "확인되지 않음"}`
      + (symptom.latestTrend
        ? ` / 최근 변화: ${symptom.latestTrend === "improving" ? "호전 중" : symptom.latestTrend === "worsening" ? "악화 중" : "변화 없음"}`
        : "")
      + (tracksFrequency(symptom.name) && symptom.frequencies.length > 0
        ? ` / 횟수: ${symptom.frequencies.join(", ")}`
        : "")
      + ` / 기록 ${symptom.recordCount}회`,
  );
  return [
    "MedMap 진료 전 증상 요약",
    `기록 기간: ${dateFormatter.format(new Date(summary.firstRecordedAt))} ~ ${dateFormatter.format(new Date(summary.lastRecordedAt))}`,
    ...(summary.urgentSymptoms.length > 0
      ? [`빨리 진료가 필요할 수 있는 증상: ${summary.urgentSymptoms.join(", ")}`]
      : []),
    "증상 변화",
    ...(symptomLines.length > 0 ? symptomLines : ["- 확인된 증상 없음"]),
    ...(summary.uncertainSymptoms.length > 0
      ? [`있는지 확실하지 않다고 한 증상: ${summary.uncertainSymptoms.join(", ")}`]
      : []),
    ...(summary.othersSymptoms.length > 0
      ? [`주변 사람에 대해 말한 내용: ${summary.othersSymptoms.join(", ")}`]
      : []),
    `기록 기간 중 복용약: ${summary.medications.join(", ") || "확인되지 않음"}`,
    `기록된 알레르기: ${summary.allergies.join(", ") || "확인되지 않음"}`,
    `과거력: ${summary.medicalHistory.join(", ") || "확인되지 않음"}`,
    "이 내용은 사용자가 확인한 기록의 요약이며 진단 결과가 아닙니다.",
  ].join("\n");
}
