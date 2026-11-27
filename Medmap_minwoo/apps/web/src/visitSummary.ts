import type { PatientProfile } from "./recordGroups";
import type { StoredIntakeRecord } from "./recordStorage";
import type { SymptomEpisode } from "./symptomEpisodes";
import { formatOnset, severeSymptoms, tracksFrequency, unsureUrgentSymptoms, urgentSymptoms } from "./symptomOptions";

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
  // Danger symptoms said with doubt and never said as present: kept for the doctor, not dropped (2026-11-27).
  unsureUrgentSymptoms: string[];
  severeSymptoms: string[];
  profile: string | null;
};

export function profileText(profile: PatientProfile | undefined): string | null {
  if (!profile) return null;
  const parts = [
    profile.age != null ? `${profile.age}세` : null,
    profile.sex === "female" ? "여성" : profile.sex === "male" ? "남성" : null,
    profile.sex === "female" && profile.pregnancy
      ? { yes: "임신 중이거나 가능성 있음", no: "임신 아님", unknown: "임신 여부 모름" }[profile.pregnancy]
      : null,
    profile.smoking ? { current: "흡연", former: "과거 흡연", never: "비흡연" }[profile.smoking] : null,
    profile.drinking ? { yes: "음주", no: "음주 안 함" }[profile.drinking] : null,
  ].filter(Boolean);
  return parts.length > 0 ? parts.join(" / ") : null;
}

function shortDate(value: string): string {
  return new Intl.DateTimeFormat("ko-KR", { month: "long", day: "numeric" }).format(new Date(value));
}

// "10월 1일부터" while it lasts, one date for a one-day episode, otherwise a range.
export function episodePeriod(episode: SymptomEpisode): string {
  const start = shortDate(episode.startedAt);
  if (!episode.endedAt) return `${start}부터`;
  const end = shortDate(episode.endedAt);
  return start === end ? start : `${start} ~ ${end}`;
}

// A symptom that would have raised the urgent notice while it lasted ("기절했었어요" still matters).
export function wasUrgent(episode: SymptomEpisode): boolean {
  return urgentSymptoms([{ name: episode.name, status: "present", severity: episode.peakSeverity }]).length > 0;
}

export function buildVisitSummary(
  records: StoredIntakeRecord[],
  episodes: SymptomEpisode[],
  profile?: PatientProfile,
): VisitSummary | null {
  if (records.length === 0) return null;
  const ordered = [...records].sort((left, right) => left.createdAt.localeCompare(right.createdAt));
  const active = episodes
    .filter((episode) => episode.status === "active")
    .map((episode) => ({ name: episode.name, status: "present", severity: episode.peakSeverity }));
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
    profile: profileText(profile),
    urgentSymptoms: urgentSymptoms(active),
    // Kept only while the latest word on it is still "not sure": a later "없어요" settles it (2026-11-28 check of item 4).
    unsureUrgentSymptoms: unsureUrgentSymptoms(ordered.flatMap((record) => record.intake.symptoms))
      .filter((name) => !episodes.some((episode) => episode.name === name))
      .filter((name) => [...ordered].reverse().flatMap((record) => record.intake.symptoms)
        .find((symptom) => symptom.name === name)?.status === "uncertain"),
    severeSymptoms: severeSymptoms(active),
  };
}

export function visitSummaryText(summary: VisitSummary): string {
  const dateFormatter = new Intl.DateTimeFormat("ko-KR", {
    dateStyle: "medium",
    timeStyle: "short",
  });
  const frequency = (symptom: SymptomEpisode) =>
    tracksFrequency(symptom.name) && symptom.frequencies.length > 0 ? ` / 횟수: ${symptom.frequencies.join(", ")}` : "";
  // Current symptoms first in full; resolved ones stay as one short line because their course still matters.
  const activeLines = summary.symptoms.filter((symptom) => symptom.status === "active").map((symptom) =>
    `- ${symptom.name}${symptom.bodySite ? `(${symptom.bodySite})` : ""}`
      + `: 시작: ${formatOnset(symptom.statedOnset, symptom.statedOnsetDate) || "확인되지 않음"}`
      + ` / 가장 심한 정도: ${symptom.peakSeverity || "확인되지 않음"}`
      + (symptom.latestTrend
        ? ` / 최근 변화: ${symptom.latestTrend === "improving" ? "호전 중" : symptom.latestTrend === "worsening" ? "악화 중" : "변화 없음"}`
        : "")
      + frequency(symptom)
      + (symptom.details.length > 0 ? ` / 특징: ${symptom.details.join(", ")}` : "")
      + ` / 기록 ${symptom.recordCount}회`,
  );
  const resolvedLines = summary.symptoms.filter((symptom) => symptom.status === "resolved").map((symptom) =>
    `- ${symptom.name}${wasUrgent(symptom) ? " (위험 증상)" : ""}: ${episodePeriod(symptom)}`
      + (symptom.peakSeverity ? ` / 가장 심한 정도: ${symptom.peakSeverity}` : "")
      + frequency(symptom),
  );
  return [
    "MedMap 진료 전 증상 요약",
    ...(summary.profile ? [`기본 정보: ${summary.profile}`] : []),
    `기록 기간: ${dateFormatter.format(new Date(summary.firstRecordedAt))} ~ ${dateFormatter.format(new Date(summary.lastRecordedAt))}`,
    ...(summary.urgentSymptoms.length > 0
      ? [`빨리 진료가 필요할 수 있는 증상: ${summary.urgentSymptoms.join(", ")}`]
      : []),
    ...(summary.unsureUrgentSymptoms.length > 0
      ? [`확실하지 않다고 했지만 확인이 필요한 위험 신호: ${summary.unsureUrgentSymptoms.join(", ")}`]
      : []),
    ...(summary.severeSymptoms.length > 0
      ? [`심하다고 한 증상: ${summary.severeSymptoms.join(", ")}`]
      : []),
    "지금 있는 증상",
    ...(activeLines.length > 0 ? activeLines : ["- 확인된 증상 없음"]),
    ...(resolvedLines.length > 0 ? ["사라진 증상", ...resolvedLines] : []),
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
