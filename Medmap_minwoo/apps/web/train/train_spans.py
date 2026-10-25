"""Train the symptom-span model (HANDOFF 7-1-1, step D).

Tags each token: outside, or the beginning/inside of a symptom the patient says is present, absent or uncertain.
Trained on the EXAONE sentences from generate_spans.ts; then tags both eval sets and saves the spans it finds for
eval/evaluate_outside.ts.

Run from the repo root:
  local-cache\\train-venv\\Scripts\\python.exe apps/web/train/train_spans.py [model] [--epochs N]
"""
import argparse
import json
import os
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault("HF_HOME", str(ROOT / "local-cache" / "huggingface"))
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

import torch  # noqa: E402
from transformers import AutoModelForTokenClassification, AutoTokenizer  # noqa: E402

STATUSES = ["present", "absent", "uncertain"]
TAGS = ["O"] + [f"{edge}-{status}" for status in STATUSES for edge in ("B", "I")]
EVAL = ROOT / "apps" / "web" / "eval"


def tag_tokens(offsets, spans):
    """Token tags from character spans; special tokens (offset 0,0) get -100 so they are not scored."""
    tags = []
    previous = None  # the span the previous token was in
    for start, end in offsets:
        if start == end:
            tags.append(-100)
            continue
        span = next((s for s in spans if s["start"] <= start < s["end"]), None)
        tags.append(0 if span is None else TAGS.index(f"{'I' if span is previous else 'B'}-{span['status']}"))
        previous = span
    return tags


def spans_from(text, offsets, tags):
    """Character spans from predicted tags: a B starts a span, following I of the same status continue it."""
    found = []
    open_span = False  # whether the previous token was tagged, so an I may continue it
    for (start, end), tag in zip(offsets, tags):
        if start == end:
            continue
        if tag == 0:
            open_span = False
            continue
        edge, status = TAGS[tag].split("-")
        if edge == "I":
            # An I continues the span before it; one with nothing to continue is a stray piece ("어요") and is dropped.
            if open_span and found[-1]["status"] == status:
                found[-1]["end"] = end
            else:
                open_span = False
            continue
        found.append({"start": start, "end": end, "status": status})
        open_span = True
    return [{**span, "text": text[span["start"]:span["end"]]} for span in found]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("model", nargs="?", default="monologg/koelectra-small-v3-discriminator")
    parser.add_argument("--epochs", type=int, default=6)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--data", default=str(ROOT / "local-cache" / "intake-train" / "spans.jsonl"))
    args = parser.parse_args()
    random.seed(0)
    torch.manual_seed(0)
    device = "cuda" if torch.cuda.is_available() else "cpu"

    rows = [json.loads(line) for line in open(args.data, encoding="utf-8") if line.strip()]
    # Sentences written from one plan are near copies: keep each plan on one side of the split.
    plan_of = lambda row: json.dumps([[s["label"], s["status"]] for s in row["spans"]] + [row["other"], row["style"]], ensure_ascii=False)
    plans = sorted({plan_of(row) for row in rows})
    random.shuffle(plans)
    held = set(plans[: len(plans) // 10])
    train = [row for row in rows if plan_of(row) not in held]
    valid = [row for row in rows if plan_of(row) in held]
    print(f"{len(rows)} sentences: train {len(train)}, valid {len(valid)}, device {device}")

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForTokenClassification.from_pretrained(
        args.model, num_labels=len(TAGS), id2label=dict(enumerate(TAGS)), label2id={t: i for i, t in enumerate(TAGS)}).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)

    def encode(texts):
        return tokenizer(texts, padding=True, truncation=True, max_length=128, return_offsets_mapping=True, return_tensors="pt")

    def predict(texts):
        model.eval()
        out = []
        with torch.no_grad():
            for start in range(0, len(texts), 64):
                chunk = texts[start:start + 64]
                encoded = encode(chunk)
                offsets = encoded.pop("offset_mapping").tolist()
                logits = model(**{k: v.to(device) for k, v in encoded.items()}).logits
                for text, offset, tags in zip(chunk, offsets, logits.argmax(-1).tolist()):
                    out.append(spans_from(text, offset, tags))
        return out

    def span_f1(data):
        """Valid-set F1 of spans with the same status that overlap a labeled span."""
        guesses = predict([row["text"] for row in data])
        tp = fp = fn = 0
        for guess, row in zip(guesses, data):
            gold = row["spans"]
            hit = lambda a, b: a["status"] == b["status"] and a["start"] < b["end"] and b["start"] < a["end"]
            tp += sum(any(hit(g, p) for p in guess) for g in gold)
            fn += sum(not any(hit(g, p) for p in guess) for g in gold)
            fp += sum(not any(hit(g, p) for g in gold) for p in guess)
        p = tp / (tp + fp) if tp + fp else 0
        r = tp / (tp + fn) if tp + fn else 0
        return 2 * p * r / (p + r) if p + r else 0

    for epoch in range(1, args.epochs + 1):
        model.train()
        random.shuffle(train)
        total = 0.0
        for start in range(0, len(train), 32):
            chunk = train[start:start + 32]
            encoded = encode([row["text"] for row in chunk])
            offsets = encoded.pop("offset_mapping").tolist()
            labels = torch.tensor([tag_tokens(offset, row["spans"]) for offset, row in zip(offsets, chunk)])
            loss = model(**{k: v.to(device) for k, v in encoded.items()}, labels=labels.to(device)).loss
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            total += loss.item() * len(chunk)
        print(f"epoch {epoch}: loss {total / len(train):.4f}, valid span F1 {span_f1(valid):.1%}")

    short = args.model.split("/")[-1]
    out = ROOT / "local-cache" / "intake-model" / f"spans-{short}"
    model.save_pretrained(out)
    tokenizer.save_pretrained(out)
    predictions = {}
    for file in ("intake_eval_set.jsonl", "outside_eval_set.jsonl"):
        items = [json.loads(line) for line in open(EVAL / file, encoding="utf-8") if line.strip()]
        predictions.update(dict(zip([item["id"] for item in items], predict([item["text"] for item in items]))))
    target = EVAL / "predictions" / f"spans-{short}.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(predictions, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"saved {out} and {target}")


if __name__ == "__main__":
    main()
