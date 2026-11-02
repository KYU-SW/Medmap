// Tags both eval sets with the phone's model and code (src/intake/spanModel.ts: int8 ONNX, TypeScript tokenizer),
// so evaluate_outside.ts can score exactly what the app runs. Run from apps/web after train/export_onnx.py:
//   node eval/predict_phone.ts && node eval/evaluate_outside.ts --spans eval/predictions/spans-phone.json
import { readFileSync, writeFileSync } from "node:fs";
import { createSpanModel } from "../src/intake/spanModel.ts";

const read = (file: string) => readFileSync(new URL(file, import.meta.url));
const { vocab, labels } = JSON.parse(read("../public/models/spans-vocab.json").toString("utf8"));
const findSpans = await createSpanModel(new Uint8Array(read("../public/models/spans.onnx")), vocab, labels);
const predictions: Record<string, unknown> = {};
for (const file of ["./intake_eval_set.jsonl", "./outside_eval_set.jsonl"]) {
  for (const line of read(file).toString("utf8").split("\n").filter((row) => row.trim())) {
    const item = JSON.parse(line);
    predictions[item.id] = await findSpans(item.text);
  }
}
writeFileSync(new URL("./predictions/spans-phone.json", import.meta.url), JSON.stringify(predictions, null, 0));
console.log(`tagged ${Object.keys(predictions).length} sentences`);
