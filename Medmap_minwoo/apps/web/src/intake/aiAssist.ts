// The on-device model's part of the review screen, apart from React so its states can be tested without the model:
// it says whether the model is loading, reading, found more symptoms, found none, or could not run, and never shows
// "could not run" as "found none". The rules' result stands in every case.
import type { IntakeExtraction } from "./extractor.ts";
import { outsideSymptoms, symptomSites, type OutsideSymptom } from "./outsideSymptoms.ts";
import type { ModelLoad } from "./spanModel.ts";

export type AiState =
  | { kind: "loading" }
  | { kind: "running" }
  | { kind: "done"; found: OutsideSymptom[]; sites: Map<string, string[]>; readUpTo: number | null }
  | { kind: "unavailable"; reason: "missing" | "failed" };

/** Reports each state through onState; the last one is also returned. */
export async function runAiAssist(text: string, rules: IntakeExtraction, load: () => Promise<ModelLoad>,
  onState: (state: AiState) => void): Promise<AiState> {
  const report = (state: AiState) => {
    onState(state);
    return state;
  };
  report({ kind: "loading" });
  let loaded: ModelLoad;
  try {
    loaded = await load();
  } catch {
    return report({ kind: "unavailable", reason: "failed" });
  }
  if (!loaded.model) return report({ kind: "unavailable", reason: loaded.reason });
  report({ kind: "running" });
  try {
    const result = await loaded.model(text);
    const found = outsideSymptoms(text, rules, result.spans);
    return report({
      kind: "done",
      found,
      sites: symptomSites(text, rules, result.spans, found),
      readUpTo: result.truncated ? result.readUpTo : null,
    });
  } catch {
    return report({ kind: "unavailable", reason: "failed" });
  }
}

export const AI_MESSAGES = {
  loading: "AI 도우미를 준비하고 있어요…",
  running: "AI가 다른 증상을 찾고 있어요…",
  none: "AI가 추가로 찾은 증상은 없어요.",
  unavailable: "AI 도우미를 사용할 수 없어 기본 규칙으로만 정리했어요. 입력한 문장과 결과를 직접 확인해 주세요.",
  truncated: (characters: number) =>
    `문장이 길어 앞부분 ${characters}자까지만 AI가 읽었어요. 뒷부분은 직접 확인해 주세요.`,
};
