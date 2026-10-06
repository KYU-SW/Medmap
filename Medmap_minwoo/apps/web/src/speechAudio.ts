// Finds where speech is in a 16 kHz recording. Whisper invents words for silence ("감사합니다." for a quiet
// half second, "맨날 그러냐" after the last word), so the phone only transcribes the spoken part.

const SAMPLE_RATE = 16_000;
const FRAME = SAMPLE_RATE / 10; // 100 ms

function frameLevels(samples: Float32Array): number[] {
  const levels: number[] = [];
  for (let offset = 0; offset + FRAME <= samples.length; offset += FRAME) {
    let sum = 0;
    for (let i = offset; i < offset + FRAME; i++) sum += samples[i] * samples[i];
    levels.push(Math.sqrt(sum / FRAME));
  }
  return levels;
}

// Speech is clearly louder than the room: 2.5 times the quieter frames, and never below a floor.
function speechFrames(samples: Float32Array): boolean[] {
  const levels = frameLevels(samples);
  const quiet = [...levels].sort((a, b) => a - b)[Math.floor(levels.length * 0.2)] ?? 0;
  const threshold = Math.max(0.01, quiet * 2.5);
  return levels.map((level) => level >= threshold);
}

/** Whether the recording holds any speech worth sending (at least 0.3 s). */
export function hasSpeech(samples: Float32Array): boolean {
  return speechFrames(samples).filter(Boolean).length >= 3;
}

/** The recording from just before the first speech to just after the last, with 0.3 s kept on each side. */
export function trimSilence(samples: Float32Array): Float32Array {
  const speech = speechFrames(samples);
  const first = speech.indexOf(true);
  if (first < 0) return samples;
  const last = speech.lastIndexOf(true);
  const start = Math.max(0, (first - 3) * FRAME);
  const end = Math.min(samples.length, (last + 4) * FRAME);
  return samples.subarray(start, end);
}

export function joinChunks(chunks: Float32Array[]): Float32Array {
  const joined = new Float32Array(chunks.reduce((total, chunk) => total + chunk.length, 0));
  let offset = 0;
  for (const chunk of chunks) {
    joined.set(chunk, offset);
    offset += chunk.length;
  }
  return joined;
}

/** A rough caption with the small model's loops folded: "2일 전부터 2일 전부터 2일 전부터" → "2일 전부터". */
export function tidyCaption(text: string): string {
  return text.replace(/(.{3,}?)(?:\s*\1){1,}/gu, "$1").trim();
}
