// Runs the span model (train/train_spans.py, exported by train/export_onnx.py) on the phone with onnxruntime-web:
// tags each token as outside or the beginning/inside of a present, absent or uncertain symptom, and returns the spans.
// Text longer than one model input is read in overlapping windows (spanWindows.ts).
import * as ort from "onnxruntime-web/wasm";
import { tagLongText, type SpanResult } from "./spanWindows.ts";
import { createTokenizer } from "./tokenizer.ts";

// One thread: a WebView page is not cross-origin isolated, so threads are not available there anyway.
ort.env.wasm.numThreads = 1;

export type SpanModel = (text: string) => Promise<SpanResult>;
/** The model, or why there is none: the file is not in this build, or it would not load. */
export type ModelLoad = { model: SpanModel } | { model: null; reason: "missing" | "failed" };

export async function createSpanModel(model: Uint8Array, vocab: string[], labels: string[]): Promise<SpanModel> {
  const session = await ort.InferenceSession.create(model);
  const tokenize = createTokenizer(vocab);
  const [cls, sep] = [vocab.indexOf("[CLS]"), vocab.indexOf("[SEP]")];
  const tagWindow = async (ids: number[]) => {
    const input = [cls, ...ids, sep];
    const tensor = (values: number[]) => new ort.Tensor("int64", BigInt64Array.from(values, BigInt), [1, values.length]);
    const { logits } = await session.run({
      input_ids: tensor(input),
      attention_mask: tensor(input.map(() => 1)),
      token_type_ids: tensor(input.map(() => 0)),
    });
    const scores = logits.data as Float32Array;
    return ids.map((_, index) => {
      const row = scores.subarray((index + 1) * labels.length, (index + 2) * labels.length);
      return labels[row.indexOf(Math.max(...row))];
    });
  };
  // Whole text's pieces without [CLS]/[SEP]; tagLongText decides how much is read.
  return (text) => tagLongText(text, tokenize(text, Infinity).slice(1, -1), tagWindow);
}

let loading: Promise<ModelLoad> | null = null;

/** The app's model, loaded once from public/models. Nothing is logged: errors could carry the patient's words. */
export function loadSpanModel(): Promise<ModelLoad> {
  loading ??= (async (): Promise<ModelLoad> => {
    let model: Response;
    try {
      model = await fetch("models/spans.onnx");
    } catch {
      return { model: null, reason: "failed" };
    }
    if (!model.ok) return { model: null, reason: model.status === 404 ? "missing" : "failed" };
    try {
      // The runtime's wasm ships inside the app (Vite copies it), as the phone may be offline.
      const [{ default: wasm }, { default: mjs }] = await Promise.all([
        import("../../node_modules/onnxruntime-web/dist/ort-wasm-simd-threaded.wasm?url"),
        import("../../node_modules/onnxruntime-web/dist/ort-wasm-simd-threaded.mjs?url"),
      ]);
      ort.env.wasm.wasmPaths = { wasm, mjs };
      const vocab = await fetch("models/spans-vocab.json").then((response) => (response.ok ? response.json() : Promise.reject()));
      return { model: await createSpanModel(new Uint8Array(await model.arrayBuffer()), vocab.vocab, vocab.labels) };
    } catch {
      return { model: null, reason: "failed" };
    }
  })();
  return loading;
}
