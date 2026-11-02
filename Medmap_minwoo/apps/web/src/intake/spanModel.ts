// Runs the span model (train/train_spans.py, exported by train/export_onnx.py) on the phone with onnxruntime-web:
// tags each token as outside or the beginning/inside of a present, absent or uncertain symptom, and returns the spans.
import * as ort from "onnxruntime-web/wasm";
import type { ModelSpan } from "./outsideSymptoms.ts";
import { createTokenizer } from "./tokenizer.ts";

// One thread: a WebView page is not cross-origin isolated, so threads are not available there anyway.
ort.env.wasm.numThreads = 1;

export type SpanModel = (text: string) => Promise<ModelSpan[]>;

export async function createSpanModel(model: Uint8Array, vocab: string[], labels: string[]): Promise<SpanModel> {
  const session = await ort.InferenceSession.create(model);
  const tokenize = createTokenizer(vocab);
  return async (text) => {
    const tokens = tokenize(text);
    const tensor = (values: number[]) => new ort.Tensor("int64", BigInt64Array.from(values, BigInt), [1, values.length]);
    const { logits } = await session.run({
      input_ids: tensor(tokens.map((token) => token.id)),
      attention_mask: tensor(tokens.map(() => 1)),
      token_type_ids: tensor(tokens.map(() => 0)),
    });
    const scores = logits.data as Float32Array;
    const tags = tokens.map((_, index) => {
      const row = scores.subarray(index * labels.length, (index + 1) * labels.length);
      return labels[row.indexOf(Math.max(...row))];
    });
    return spansFrom(text, tokens, tags);
  };
}

/** Same as spans_from in train_spans.py: a B starts a span, following I of the same status continue it. */
function spansFrom(text: string, tokens: Array<{ start: number; end: number }>, tags: string[]): ModelSpan[] {
  const found: Array<Omit<ModelSpan, "text">> = [];
  let open = false;
  tokens.forEach(({ start, end }, index) => {
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

let loading: Promise<SpanModel | null> | null = null;

/** The app's model, loaded once from public/models; null when the model was not exported into this build. */
export function loadSpanModel(): Promise<SpanModel | null> {
  loading ??= (async () => {
    try {
      // The runtime's wasm ships inside the app (Vite copies it), as the phone may be offline.
      const [{ default: wasm }, { default: mjs }] = await Promise.all([
        import("../../node_modules/onnxruntime-web/dist/ort-wasm-simd-threaded.wasm?url"),
        import("../../node_modules/onnxruntime-web/dist/ort-wasm-simd-threaded.mjs?url"),
      ]);
      ort.env.wasm.wasmPaths = { wasm, mjs };
      const [model, vocab] = await Promise.all([
        fetch("models/spans.onnx").then((response) => (response.ok ? response.arrayBuffer() : Promise.reject())),
        fetch("models/spans-vocab.json").then((response) => (response.ok ? response.json() : Promise.reject())),
      ]);
      return await createSpanModel(new Uint8Array(model), vocab.vocab, vocab.labels);
    } catch (error) {
      console.warn("span model not loaded", error);
      return null;
    }
  })();
  return loading;
}
