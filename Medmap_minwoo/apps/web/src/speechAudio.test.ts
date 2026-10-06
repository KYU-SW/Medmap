import { describe, expect, it } from "vitest";
import { hasSpeech, joinChunks, tidyCaption, trimSilence } from "./speechAudio";

const RATE = 16_000;

// Builds audio from [seconds, amplitude] parts: a 200 Hz tone stands in for speech, near zero for silence.
function audio(...parts: [number, number][]): Float32Array {
  return joinChunks(parts.map(([seconds, amplitude]) => {
    const chunk = new Float32Array(Math.round(seconds * RATE));
    for (let i = 0; i < chunk.length; i++) chunk[i] = amplitude * Math.sin((2 * Math.PI * 200 * i) / RATE) + 0.001;
    return chunk;
  }));
}

describe("speech in a recording", () => {
  it("tells speech from room noise", () => {
    expect(hasSpeech(audio([2, 0]))).toBe(false);
    expect(hasSpeech(audio([2, 0], [1, 0.3]))).toBe(true);
  });

  it("drops silence before and after the speech, keeping a short margin", () => {
    const trimmed = trimSilence(audio([1.5, 0], [2, 0.3], [3, 0]));
    expect(trimmed.length / RATE).toBeGreaterThan(2.4);
    expect(trimmed.length / RATE).toBeLessThan(2.9);
  });

  it("keeps a pause between words", () => {
    const trimmed = trimSilence(audio([1, 0.3], [1.5, 0], [1, 0.3]));
    expect(trimmed.length / RATE).toBeGreaterThan(3.4);
  });
});

describe("tidyCaption", () => {
  it("folds a phrase the small model repeated", () => {
    expect(tidyCaption("2일 전 전역부터 2일 전 전역부터 2일 전 전역부터 2")).toBe("2일 전 전역부터 2");
    expect(tidyCaption("그리고 타이리의 농을 2정포경을 2정포경을 2정포경을")).toBe("그리고 타이리의 농을 2정포경을");
  });

  it("leaves a normal caption alone", () => {
    expect(tidyCaption("어제부터 복통이 너무 심하고, 구토는 3회했어요.")).toBe("어제부터 복통이 너무 심하고, 구토는 3회했어요.");
  });
});
