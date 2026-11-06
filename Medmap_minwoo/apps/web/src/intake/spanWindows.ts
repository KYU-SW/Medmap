// Reads a transcript of any length with the span model, which takes at most 128 tokens at a time (spanModel.ts).
// Short input is one window, exactly as before. Longer input is read in overlapping windows over the whole text's
// tokens, so every window keeps the words around it, and the windows are stitched into one tag per token before the
// tags become spans: a symptom in an overlap is found once, and spans keep their place in the whole text.
import type { ModelSpan } from "./outsideSymptoms.ts";

export type Piece = { id: number; start: number; end: number };
/** Tags for the pieces of one window (no [CLS]/[SEP]): "O", "B-present", "I-absent", ... */
export type TagWindow = (ids: number[]) => Promise<string[]>;

export const WINDOW = 126; // 128 with [CLS] and [SEP]
export const STEP = 96; // 30 pieces of overlap
// About 2,000 Korean characters (several minutes of speech), 11 windows. Past it the rest is not read and the caller
// tells the patient so, rather than the phone running the model without limit.
export const MAX_PIECES = 1024;

/** readUpTo: the character the model read up to, so a cut-off text can say where the reading stopped. */
export type SpanResult = { spans: ModelSpan[]; truncated: boolean; windows: number; readUpTo: number };

/** Where the windows start: every STEP pieces, the last one moved back to end at the last piece. */
export function windowStarts(count: number, size = WINDOW, step = STEP): number[] {
  if (count <= size) return [0];
  const starts: number[] = [];
  for (let from = 0; from + size < count; from += step) starts.push(from);
  starts.push(count - size);
  return starts;
}

export async function tagLongText(text: string, allPieces: Piece[], tagWindow: TagWindow,
  size = WINDOW, step = STEP, maxPieces = MAX_PIECES): Promise<SpanResult> {
  const pieces = allPieces.slice(0, maxPieces);
  if (pieces.length === 0) return { spans: [], truncated: false, windows: 0, readUpTo: text.length };
  const starts = windowStarts(pieces.length, size, step);
  // One window at a time: an onnxruntime-web session must not run twice at once (a second run while one is in flight
  // fails), and the phone gains nothing from overlapping runs on one wasm thread.
  const windows: string[][] = [];
  for (const from of starts) windows.push(await tagWindow(pieces.slice(from, from + size).map((piece) => piece.id)));

  // Stitch: each overlap is cut once, at a piece both windows call outside a symptom (nearest the middle), so no
  // span is made of two windows' halves. Pieces before the cut come from the earlier window, after it the later one.
  const tags = [...windows[0]];
  for (let w = 1; w < starts.length; w += 1) {
    const from = starts[w];
    const overlapEnd = starts[w - 1] + size; // first piece the earlier window did not read
    const middle = Math.floor((from + overlapEnd) / 2);
    let cut = middle;
    let best = Infinity;
    for (let at = from; at < overlapEnd; at += 1) {
      if (tags[at] === "O" && windows[w][at - from] === "O" && Math.abs(at - middle) < best) {
        best = Math.abs(at - middle);
        cut = at;
      }
    }
    tags.length = cut;
    tags.push(...windows[w].slice(cut - from));
    // No outside piece the two agree on: a span runs across the cut. It keeps the status it started with, and an "I"
    // the later window gave the first piece after the cut still continues it.
    const before = tags[cut - 1];
    if (cut > 0 && before !== "O" && tags[cut]?.startsWith("I-")) {
      const status = before.slice(2);
      for (let at = cut; at < tags.length && tags[at].startsWith("I-"); at += 1) tags[at] = `I-${status}`;
    }
  }
  return {
    spans: spansFrom(text, pieces, tags),
    truncated: allPieces.length > maxPieces,
    windows: starts.length,
    readUpTo: allPieces.length > maxPieces ? pieces[pieces.length - 1].end : text.length,
  };
}

/** Same as spans_from in train_spans.py: a B starts a span, following I of the same status continue it. */
export function spansFrom(text: string, pieces: Array<{ start: number; end: number }>, tags: string[]): ModelSpan[] {
  const found: Array<Omit<ModelSpan, "text">> = [];
  let open = false;
  pieces.forEach(({ start, end }, index) => {
    if (start === end) return;
    if (tags[index] === "O") {
      open = false;
      return;
    }
    const [edge, status] = tags[index].split("-") as ["B" | "I", ModelSpan["status"]];
    if (edge === "I") {
      // An I with nothing to continue is a stray piece ("어요") and is dropped.
      if (open && found[found.length - 1].status === status) found[found.length - 1].end = end;
      else open = false;
      return;
    }
    found.push({ start, end, status });
    open = true;
  });
  return found.map((span) => ({ ...span, text: text.slice(span.start, span.end) }));
}
