import { describe, expect, it } from "vitest";
import { runAiAssist, type AiState } from "./aiAssist";
import { extractIntake } from "./extractor";
import type { ModelLoad, SpanModel } from "./spanModel";

const text = "머리가 아프고 얼굴이 창백해졌어요.";
const rules = extractIntake(text, "2026-11-06");
async function run(load: () => Promise<ModelLoad>) {
  const states: AiState["kind"][] = [];
  const last = await runAiAssist(text, rules, load, (state) => states.push(state.kind));
  return { states, last };
}
const model = (spans: Awaited<ReturnType<SpanModel>>["spans"], extra = {}): SpanModel =>
  async () => ({ spans, truncated: false, windows: 1, readUpTo: text.length, ...extra });

describe("runAiAssist", () => {
  it("says the model is missing, not that nothing was found", async () => {
    const { states, last } = await run(async () => ({ model: null, reason: "missing" }));
    expect(states).toEqual(["loading", "unavailable"]);
    expect(last).toEqual({ kind: "unavailable", reason: "missing" });
  });

  it("says the model failed when it throws while reading", async () => {
    const broken: SpanModel = async () => { throw new Error("inference failed"); };
    const { states, last } = await run(async () => ({ model: broken }));
    expect(states).toEqual(["loading", "running", "unavailable"]);
    expect(last).toEqual({ kind: "unavailable", reason: "failed" });
  });

  it("says the model failed when loading throws", async () => {
    const { last } = await run(async () => { throw new Error("load failed"); });
    expect(last).toEqual({ kind: "unavailable", reason: "failed" });
  });

  it("finishes with no new symptoms when the model finds none", async () => {
    const { states, last } = await run(async () => ({ model: model([]) }));
    expect(states).toEqual(["loading", "running", "done"]);
    expect(last.kind === "done" && last.found).toEqual([]);
  });

  it("finishes with what the model found, and where reading stopped on a cut-off text", async () => {
    const start = text.indexOf("얼굴");
    const spans = [{ start, end: start + "얼굴이 창백해졌어요".length, status: "present" as const, text: "얼굴이 창백해졌어요" }];
    const { last } = await run(async () => ({ model: model(spans, { truncated: true, readUpTo: 12 }) }));
    expect(last.kind === "done" && last.found.map((part) => part.name)).toEqual(["창백함"]);
    expect(last.kind === "done" && last.readUpTo).toBe(12);
  });
});
