import type { SymptomEpisode } from "./symptomEpisodes";
import type { ChangeTone, TimelineEntry } from "./timeline";

export type CalendarDay = {
  key: string;
  day: number;
  // The most notable change recorded that day, or null when nothing was recorded.
  tone: ChangeTone | null;
  inEpisode: boolean;
};

// Worse changes win over everything else so a bad day is never hidden by a better one.
const TONE_RANK: ChangeTone[] = ["worse", "new", "same", "better", "unknown"];

// Local calendar date as YYYY-MM-DD, so string order is date order.
export function dayKey(value: string | Date): string {
  const date = new Date(value);
  const pad = (number: number) => String(number).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

// One month as a Sunday-first grid; null cells pad the first week.
export function monthGrid(
  year: number,
  month: number,
  timeline: TimelineEntry[],
  episodes: SymptomEpisode[],
): (CalendarDay | null)[] {
  const tones = new Map<string, ChangeTone>();
  for (const entry of timeline) {
    const key = dayKey(entry.createdAt);
    const candidates = [tones.get(key), ...entry.symptoms.map((symptom) => symptom.tone)];
    tones.set(key, TONE_RANK.find((tone) => candidates.includes(tone)) ?? "unknown");
  }
  const spans = episodes.map((episode) => [
    dayKey(episode.startedAt),
    dayKey(episode.endedAt ?? episode.lastRecordedAt),
  ]);

  const cells: (CalendarDay | null)[] = Array(new Date(year, month, 1).getDay()).fill(null);
  const days = new Date(year, month + 1, 0).getDate();
  for (let day = 1; day <= days; day += 1) {
    const key = dayKey(new Date(year, month, day));
    cells.push({
      key,
      day,
      tone: tones.get(key) ?? null,
      inEpisode: spans.some(([start, end]) => start <= key && key <= end),
    });
  }
  return cells;
}
