"""Export the trained span model for the phone (HANDOFF 7-1-1): ONNX with int8 weights, plus the WordPiece vocabulary.

Writes apps/web/public/models/spans.onnx and spans-vocab.json (not in Git: run this after train_spans.py), and
apps/web/eval/predictions/tokens.json, the Python tokenizer's ids and offsets that src/intake/tokenizer.test.ts
compares the TypeScript tokenizer with.

Run from the repo root:
  local-cache\\train-venv\\Scripts\\python.exe apps/web/train/export_onnx.py [model dir]
"""
import json
import sys
from pathlib import Path

import numpy as np
import onnxruntime
import torch
from onnxruntime.quantization import QuantType, quantize_dynamic
from transformers import AutoModelForTokenClassification, AutoTokenizer

ROOT = Path(__file__).resolve().parents[3]
WEB = ROOT / "apps" / "web"
OUT = WEB / "public" / "models"


def main():
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "local-cache" / "intake-model" / "spans-koelectra-small-v3-discriminator"
    tokenizer = AutoTokenizer.from_pretrained(source)
    model = AutoModelForTokenClassification.from_pretrained(source).eval()
    OUT.mkdir(parents=True, exist_ok=True)

    sample = tokenizer(["머리가 아파요"], return_tensors="pt")
    full = OUT / "spans-fp32.onnx"
    torch.onnx.export(
        model, (sample["input_ids"], sample["attention_mask"], sample["token_type_ids"]), str(full),
        input_names=["input_ids", "attention_mask", "token_type_ids"], output_names=["logits"],
        dynamic_axes={name: {0: "batch", 1: "tokens"} for name in ["input_ids", "attention_mask", "token_type_ids", "logits"]},
        opset_version=17, dynamo=False)
    small = OUT / "spans.onnx"
    quantize_dynamic(str(full), str(small), weight_type=QuantType.QInt8)

    vocab = tokenizer.get_vocab()
    (OUT / "spans-vocab.json").write_text(
        json.dumps({"vocab": sorted(vocab, key=vocab.get), "labels": [model.config.id2label[i] for i in range(model.config.num_labels)]},
                   ensure_ascii=False), encoding="utf-8")

    # The int8 model should tag (nearly) every token as the full one does; the eval sets are the check.
    texts = [json.loads(line)["text"] for name in ("intake_eval_set.jsonl", "outside_eval_set.jsonl")
             for line in open(WEB / "eval" / name, encoding="utf-8") if line.strip()]
    sessions = [onnxruntime.InferenceSession(str(path)) for path in (full, small)]
    same = total = 0
    tokens = {}
    for text in texts:
        encoded = tokenizer([text], return_tensors="np", return_offsets_mapping=True)
        tokens[text] = {"ids": encoded["input_ids"][0].tolist(), "offsets": encoded["offset_mapping"][0].tolist()}
        feed = {k: encoded[k].astype(np.int64) for k in ("input_ids", "attention_mask", "token_type_ids")}
        with torch.no_grad():
            expected = model(**{k: torch.from_numpy(v) for k, v in feed.items()}).logits.argmax(-1).numpy()
        outputs = [session.run(None, feed)[0].argmax(-1) for session in sessions]
        assert (outputs[0] == expected).all(), f"fp32 ONNX differs from torch: {text}"
        same += int((outputs[1] == expected).sum())
        total += expected.size
    full.unlink()
    (WEB / "eval" / "predictions" / "tokens.json").write_text(json.dumps(tokens, ensure_ascii=False), encoding="utf-8")
    print(f"int8 tags match the model on {same / total:.2%} of {total} tokens; {small} {small.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
