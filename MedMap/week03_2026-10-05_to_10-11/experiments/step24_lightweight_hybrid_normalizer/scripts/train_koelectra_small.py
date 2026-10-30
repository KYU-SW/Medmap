"""STEP24 KoELECTRA-small fine-tuning(77 class). FIXED_REGRESSION_TEST 는 읽지 않는다(dev 만).

- 입력 = STEP23 EXPANDED 학습셋(norm 문자열), label map = data/label_map.json(LinearSVC classes_ 와 동일)
- AutoModelForSequenceClassification(num_labels=77), max_length = environment.json 선택값(32)
- grid(실행 전 고정): epochs {3,5,8} × lr {2e-5,3e-5,5e-5} × loss {CE, CLASS_WEIGHTED_CE} = 18 run
  batch 32 · weight_decay 0.01 · linear schedule warmup 10% · grad clip 1.0 · AdamW · seed 42(각 run 재설정)
- 선택: dev core Top-1 > R@3 > R@5 > grid 순서(작은 epoch·작은 lr·CE 우선). epoch 선택 = 이 grid(dev 기반 early stopping 대체).
- 선택 run 을 같은 설정으로 다시 학습해 models/koelectra_small/ 에 저장하고, 재학습 dev 예측이 grid 때와 같은지 확인.
- auto-accept: max softmax(분류 confidence, 확률 아님) 임계값 = dev 에서 precision ≥ 0.95 를 만족하는 최소값(수락 ≥ 5).
출력: outputs/koelectra_dev_grid.csv · outputs/koelectra_selection.json · models/koelectra_small/
"""
import json
import os
import random
import time

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
import numpy as np  # noqa: E402
import torch  # noqa: E402

import s24_common as S  # noqa: E402

EPOCHS, LRS, LOSSES = [3, 5, 8], [2e-5, 3e-5, 5e-5], ["CE", "CLASS_WEIGHTED_CE"]
BATCH, WD, WARMUP, CLIP = 32, 0.01, 0.1, 1.0


def set_seed(s):
    random.seed(s)
    np.random.seed(s)
    torch.manual_seed(s)
    torch.cuda.manual_seed_all(s)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    torch.use_deterministic_algorithms(True, warn_only=True)


def encode(tok, texts, max_len, dev):
    b = tok(texts, padding="max_length", truncation=True, max_length=max_len, return_tensors="pt")
    return {k: v.to(dev) for k, v in b.items()}


@torch.no_grad()
def predict_logits(model, tok, texts, max_len, dev, bs=64):
    model.eval()
    out = []
    for i in range(0, len(texts), bs):
        out.append(model(**encode(tok, texts[i:i + bs], max_len, dev)).logits.float().cpu())
    return torch.cat(out).numpy()


def train_one(p, X, yi, n_labels, max_len, dev, tok):
    from transformers import AutoModelForSequenceClassification, get_linear_schedule_with_warmup
    set_seed(S.SEED)
    model = AutoModelForSequenceClassification.from_pretrained(S.PRETRAINED, num_labels=n_labels).to(dev)
    counts = np.bincount(yi, minlength=n_labels)
    w = torch.tensor(len(yi) / (n_labels * np.maximum(counts, 1)), dtype=torch.float, device=dev) if p["loss"] == "CLASS_WEIGHTED_CE" else None
    lossf = torch.nn.CrossEntropyLoss(weight=w)
    nd = ["bias", "LayerNorm.weight"]
    groups = [{"params": [q for n, q in model.named_parameters() if not any(x in n for x in nd)], "weight_decay": WD},
              {"params": [q for n, q in model.named_parameters() if any(x in n for x in nd)], "weight_decay": 0.0}]
    opt = torch.optim.AdamW(groups, lr=p["lr"])
    steps = p["epochs"] * ((len(X) + BATCH - 1) // BATCH)
    sch = get_linear_schedule_with_warmup(opt, int(WARMUP * steps), steps)
    g = torch.Generator().manual_seed(S.SEED)
    y_t = torch.tensor(yi)
    for _ in range(p["epochs"]):
        model.train()
        perm = torch.randperm(len(X), generator=g).tolist()
        for i in range(0, len(X), BATCH):
            idx = perm[i:i + BATCH]
            logits = model(**encode(tok, [X[j] for j in idx], max_len, dev)).logits
            loss = lossf(logits, y_t[idx].to(dev))
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), CLIP)
            opt.step()
            sch.step()
    return model


def conf_threshold(conf, correct):
    for t in sorted(set(conf)):
        acc = [ok for x, ok in zip(conf, correct) if x >= t]
        if len(acc) < 5:
            return None
        if sum(acc) / len(acc) >= 0.95:
            return {"conf_threshold": float(t), "dev_precision": S.rnd(sum(acc) / len(acc)), "dev_coverage": S.rnd(len(acc) / len(conf)),
                    "dev_n_accepted": len(acc)}
    return None


def main():
    from transformers import AutoTokenizer
    env = S.load_json(S.OUT / "environment.json")
    max_len = env["selected_max_length"]
    lm = S.load_json(S.DATA / "label_map.json")
    inv = sorted(lm, key=lm.get)
    X, y = S.train_data()
    yi = [lm[c] for c in y]
    _, dev_rows, _ = S.eval_sets()                       # test 행은 사용하지 않음
    dtexts = [S.norm(g["text_ko"]) for g in dev_rows]
    dev = torch.device("cuda")
    tok = AutoTokenizer.from_pretrained(S.PRETRAINED)

    def dev_eval(model):
        lg = predict_logits(model, tok, dtexts, max_len, dev)
        rk = {g["utterance_id"]: [inv[i] for i in np.argsort(-row, kind="stable")[:5]] for g, row in zip(dev_rows, lg)}
        return lg, S.score(dev_rows, rk)

    rows, best = [], None
    grid = [{"epochs": e, "lr": lr, "loss": ls} for e in EPOCHS for lr in LRS for ls in LOSSES]
    for gi, p in enumerate(grid):
        torch.cuda.reset_peak_memory_stats()
        t0 = time.time()
        model = train_one(p, X, yi, len(lm), max_len, dev, tok)
        _, s = dev_eval(model)
        r = {"grid_index": gi, **p, "dev_top1": s["top1"], "dev_recall_at_3": s["recall_at_3"], "dev_recall_at_5": s["recall_at_5"],
             "train_seconds": round(time.time() - t0, 1), "peak_vram_alloc_mib": round(torch.cuda.max_memory_allocated() / 2 ** 20, 1),
             "peak_vram_reserved_mib": round(torch.cuda.max_memory_reserved() / 2 ** 20, 1)}
        rows.append(r)
        print(r, flush=True)
        key = (s["top1"], s["recall_at_3"], s["recall_at_5"], -gi)
        if best is None or key > best[0]:
            best = (key, gi, p)
        del model
        torch.cuda.empty_cache()
    S.write_csv(S.OUT / "koelectra_dev_grid.csv", rows)

    _, gi, p = best
    torch.cuda.reset_peak_memory_stats()
    model = train_one(p, X, yi, len(lm), max_len, dev, tok)
    train_peak = {"alloc_mib": round(torch.cuda.max_memory_allocated() / 2 ** 20, 1), "reserved_mib": round(torch.cuda.max_memory_reserved() / 2 ** 20, 1)}
    lg, s = dev_eval(model)
    same = (s["top1"], s["recall_at_3"]) == (rows[gi]["dev_top1"], rows[gi]["dev_recall_at_3"])
    S.FT_DIR.mkdir(exist_ok=True)
    model.save_pretrained(S.FT_DIR)
    tok.save_pretrained(S.FT_DIR)
    prob = torch.softmax(torch.tensor(lg), -1).numpy()
    conf = prob.max(1).tolist()
    correct = [inv[int(i)] == g["primary_concept"] for i, g in zip(prob.argmax(1), dev_rows)]
    sel = {"selection_rule": "dev core Top-1 > R@3 > R@5 > grid order", "grid_size": len(grid), "grid_index": gi, "params": p,
           "fixed": {"batch": BATCH, "weight_decay": WD, "warmup_ratio": WARMUP, "grad_clip": CLIP, "max_length": max_len, "seed": S.SEED,
                     "optimizer": "AdamW", "schedule": "linear"},
           "dev_core": s, "refit_matches_grid_dev": same, "training_peak_vram": train_peak,
           "auto_accept_dev": conf_threshold(conf, correct), "confidence_note": "max softmax = 분류 confidence(확률·임상 확률 아님)"}
    S.dump_json(S.OUT / "koelectra_selection.json", sel)
    print("SELECTED", json.dumps(sel, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
