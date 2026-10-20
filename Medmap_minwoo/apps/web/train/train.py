"""Train the symptom model (HANDOFF 7-1, step 3).

One sentence in, and for each of the 65 symptoms one of: not said / present / absent / uncertain.
Onset, severity and medicines stay with the rules. Trained on the EXAONE sentences (generate.ts), then run on the
hand-labeled eval set; eval/evaluate.ts scores the saved predictions (--model, --hybrid).

Run from the repo root:
  local-cache\\train-venv\\Scripts\\python.exe apps/web/train/train.py [model] [--epochs N]
  model: monologg/koelectra-small-v3-discriminator (default) or klue/roberta-small
"""
import argparse
import json
import os
import random
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault("HF_HOME", str(ROOT / "local-cache" / "huggingface"))
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

import torch  # noqa: E402
from torch import nn  # noqa: E402
from transformers import AutoModel, AutoTokenizer  # noqa: E402

STATUSES = ["none", "present", "absent", "uncertain"]
GENERATE = (ROOT / "apps" / "web" / "train" / "generate.ts").read_text(encoding="utf-8")
SYMPTOMS = re.findall(r'(?:"([^"]+)"|([가-힣]+)):\s*"', GENERATE.split("const SYMPTOMS")[1].split("};")[0])
SYMPTOMS = [quoted or bare for quoted, bare in SYMPTOMS]
assert len(SYMPTOMS) == 65, len(SYMPTOMS)


class SymptomModel(nn.Module):
    def __init__(self, name: str):
        super().__init__()
        self.encoder = AutoModel.from_pretrained(name)
        self.head = nn.Linear(self.encoder.config.hidden_size, len(SYMPTOMS) * len(STATUSES))

    def forward(self, input_ids, attention_mask):
        hidden = self.encoder(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state[:, 0]
        return self.head(hidden).view(-1, len(SYMPTOMS), len(STATUSES))


def labels_of(symptoms) -> list[int]:
    row = [0] * len(SYMPTOMS)
    for symptom in symptoms:
        if symptom["name"] in SYMPTOMS:
            row[SYMPTOMS.index(symptom["name"])] = STATUSES.index(symptom["status"])
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("model", nargs="?", default="monologg/koelectra-small-v3-discriminator")
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--data", default=str(ROOT / "local-cache" / "intake-train" / "generated.jsonl"))
    args = parser.parse_args()
    random.seed(0)
    torch.manual_seed(0)
    device = "cuda" if torch.cuda.is_available() else "cpu"

    rows = [json.loads(line) for line in open(args.data, encoding="utf-8") if line.strip()]
    # Sentences written from one plan are near copies: keep each plan on one side of the split.
    plan_of = lambda row: json.dumps([row["symptoms"], row["other"], row["medicine"], row["history"], row["style"]])
    plans = sorted({plan_of(row) for row in rows})
    random.shuffle(plans)
    held = set(plans[: len(plans) // 10])
    train = [row for row in rows if plan_of(row) not in held]
    valid = [row for row in rows if plan_of(row) in held]
    print(f"{len(rows)} sentences: train {len(train)}, valid {len(valid)}, device {device}")

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = SymptomModel(args.model).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4, weight_decay=0.01)
    loss_fn = nn.CrossEntropyLoss()

    def batches(data, size, shuffle):
        order = list(range(len(data)))
        if shuffle:
            random.shuffle(order)
        for start in range(0, len(order), size):
            chunk = [data[index] for index in order[start:start + size]]
            encoded = tokenizer([row["text"] for row in chunk], padding=True, truncation=True, max_length=128,
                                return_tensors="pt").to(device)
            yield chunk, encoded

    def predict(texts):
        model.eval()
        found = []
        with torch.no_grad():
            for chunk, encoded in batches([{"text": text} for text in texts], 64, False):
                for row in model(encoded["input_ids"], encoded["attention_mask"]).argmax(-1).tolist():
                    found.append([{"name": SYMPTOMS[i], "status": STATUSES[s]} for i, s in enumerate(row) if s])
        return found

    def exact(data):
        """Share of sentences whose every symptom and status is right."""
        guesses = predict([row["text"] for row in data])
        right = sum(labels_of(guess) == labels_of(row["symptoms"]) for guess, row in zip(guesses, data))
        return right / max(len(data), 1)

    for epoch in range(1, args.epochs + 1):
        model.train()
        total = 0.0
        for chunk, encoded in batches(train, 32, True):
            target = torch.tensor([labels_of(row["symptoms"]) for row in chunk], device=device)
            logits = model(encoded["input_ids"], encoded["attention_mask"])
            loss = loss_fn(logits.reshape(-1, len(STATUSES)), target.reshape(-1))
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            total += loss.item() * len(chunk)
        print(f"epoch {epoch}: loss {total / len(train):.4f}, valid exact {exact(valid):.1%}")

    short = args.model.split("/")[-1]
    out = ROOT / "local-cache" / "intake-model" / short
    out.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), out / "model.pt")
    tokenizer.save_pretrained(out)

    eval_rows = [json.loads(line) for line in open(ROOT / "apps" / "web" / "eval" / "intake_eval_set.jsonl", encoding="utf-8")
                 if line.strip()]
    predictions = dict(zip([row["id"] for row in eval_rows], predict([row["text"] for row in eval_rows])))
    target = ROOT / "apps" / "web" / "eval" / "predictions" / f"{short}.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(predictions, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"saved {out} and {target}")


if __name__ == "__main__":
    main()
