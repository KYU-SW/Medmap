import { existsSync, readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { createTokenizer } from "./tokenizer";

// Written by train/export_onnx.py from the Python tokenizer; skipped until the model has been exported.
const vocabFile = new URL("../../public/models/spans-vocab.json", import.meta.url);
const expectedFile = new URL("../../eval/predictions/tokens.json", import.meta.url);

describe.skipIf(!existsSync(vocabFile) || !existsSync(expectedFile))("span model tokenizer", () => {
  it("gives the Python tokenizer's ids and offsets on both eval sets", () => {
    const tokenize = createTokenizer(JSON.parse(readFileSync(vocabFile, "utf8")).vocab);
    const expected: Record<string, { ids: number[]; offsets: number[][] }> = JSON.parse(readFileSync(expectedFile, "utf8"));
    for (const [text, want] of Object.entries(expected)) {
      const tokens = tokenize(text);
      expect({ text, ids: tokens.map((token) => token.id), offsets: tokens.map((token) => [token.start, token.end]) })
        .toEqual({ text, ids: want.ids, offsets: want.offsets });
    }
  });
});
