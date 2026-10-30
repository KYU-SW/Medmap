"""STEP24-v2 KoELECTRA-small fine-tuning — PROTOCOL_DEVIATION(사용자 승인 2026-10-09).

v1 사전 등록 grid(lr ≤ 5e-5, epochs ≤ 8)는 학습 자체가 붕괴(학습 정확도 4.3%, 단일 class 예측) → 학습 grid 만 확장.
데이터·dev·FIXED_REGRESSION_TEST·평가·Hybrid 정책·판정 규칙은 v1 그대로. FIXED_REGRESSION_TEST 는 이 스크립트에서 읽지 않는다.

grid(실행 전 고정): lr {1e-4, 2e-4, 3e-4} × epochs {20, 40} × loss {CE, CLASS_WEIGHTED_CE} = 12 run
고정: batch 32 · AdamW · weight_decay 0.01 · linear schedule warmup 10% · grad clip 1.0 · max_length 32
매 epoch 기록: train 평균 loss(학습 중) · train loss/acc(eval 모드, 전체 1,119) · dev loss/Top-1/R@3(core 59)
checkpoint 선택(run 안): dev Top-1 > R@3 > 낮은 dev loss > 이른 epoch (학습 정확도로 선택하지 않음)
설정 선택(run 간): 각 run best checkpoint 의 dev Top-1 > R@3 > 낮은 dev loss > grid 순서
seed 재검증: 선택 설정을 seed {42,43,44,45,46} 로 재학습, 각 seed 도 같은 규칙으로 dev best epoch 선택. PRIMARY_SEED=42 는 grid run 과 일치해야 함.
auto-accept: 각 seed 의 dev best checkpoint 에서 max softmax ≥ t 의 precision ≥ 0.95 인 최소 t(수락 ≥ 5) — 확률 아님.
출력: outputs/koelectra_dev_grid.csv · koelectra_epoch_curves.csv · koelectra_selection.json · seeds/seed*/koelectra_selection.json
      models/koelectra_small_seed*/
"""
import copy
import json
import os
import random
import time

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
import numpy as np  # noqa: E402
import torch  # noqa: E402

import s24_common as S  # noqa: E402

LRS, EPOCHS, LOSSES = [1e-4, 2e-4, 3e-4], [20, 40], ["CE", "CLASS_WEIGHTED_CE"]
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
def predict_logits(model, tok, texts, max_len, dev, bs=128):
    model.eval()
    out = []
    for i in range(0, len(texts), bs):
        out.append(model(**encode(tok, texts[i:i + bs], max_len, dev)).logits.float().cpu())
    return torch.cat(out).numpy()


def ce(logits, yi):
    return float(torch.nn.functional.cross_entropy(torch.tensor(logits), torch.tensor(yi)))


def train_run(p, seed, X, yi, dtexts, dyi, dev_rows, inv, max_len, dev, tok, curves, tag):
    """학습 + 매 epoch 평가. 반환: (best checkpoint state_dict(CPU), best 정보, peak VRAM)."""
    from transformers import AutoModelForSequenceClassification, get_linear_schedule_with_warmup
    set_seed(seed)
    model = AutoModelForSequenceClassification.from_pretrained(S.PRETRAINED, num_labels=len(inv)).to(dev)
    counts = np.bincount(yi, minlength=len(inv))
    w = torch.tensor(len(yi) / (len(inv) * np.maximum(counts, 1)), dtype=torch.float, device=dev) if p["loss"] == "CLASS_WEIGHTED_CE" else None
    lossf = torch.nn.CrossEntropyLoss(weight=w)
    nd = ["bias", "LayerNorm.weight"]
    groups = [{"params": [q for n, q in model.named_parameters() if not any(x in n for x in nd)], "weight_decay": WD},
              {"params": [q for n, q in model.named_parameters() if any(x in n for x in nd)], "weight_decay": 0.0}]
    opt = torch.optim.AdamW(groups, lr=p["lr"])
    steps = p["epochs"] * ((len(X) + BATCH - 1) // BATCH)
    sch = get_linear_schedule_with_warmup(opt, int(WARMUP * steps), steps)
    g = torch.Generator().manual_seed(seed)
    y_t = torch.tensor(yi)
    best, best_sd = None, None
    torch.cuda.reset_peak_memory_stats()
    for ep in range(1, p["epochs"] + 1):
        model.train()
        perm = torch.randperm(len(X), generator=g).tolist()
        run_loss, nb = 0.0, 0
        for i in range(0, len(X), BATCH):
            idx = perm[i:i + BATCH]
            loss = lossf(model(**encode(tok, [X[j] for j in idx], max_len, dev)).logits, y_t[idx].to(dev))
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), CLIP)
            opt.step()
            sch.step()
            run_loss += loss.item()
            nb += 1
        tl = predict_logits(model, tok, X, max_len, dev)
        dl = predict_logits(model, tok, dtexts, max_len, dev)
        rk = {gg["utterance_id"]: [inv[i] for i in np.argsort(-row, kind="stable")[:5]] for gg, row in zip(dev_rows, dl)}
        s = S.score(dev_rows, rk)
        row = {"tag": tag, **p, "seed": seed, "epoch": ep, "train_loss_running": round(run_loss / nb, 5), "train_loss_eval": round(ce(tl, yi), 5),
               "train_acc": round(float(np.mean(tl.argmax(1) == np.array(yi))), 4), "dev_loss": round(ce(dl, dyi), 5),
               "dev_top1": s["top1"], "dev_recall_at_3": s["recall_at_3"], "dev_recall_at_5": s["recall_at_5"]}
        curves.append(row)
        key = (s["top1"], s["recall_at_3"], -row["dev_loss"], -ep)
        if best is None or key > best[0]:
            best = (key, row, dl)
            best_sd = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
    peak = {"alloc_mib": round(torch.cuda.max_memory_allocated() / 2 ** 20, 1), "reserved_mib": round(torch.cuda.max_memory_reserved() / 2 ** 20, 1)}
    cfg = copy.deepcopy(model.config)
    del model
    torch.cuda.empty_cache()
    return best_sd, best[1], best[2], peak, cfg


def conf_threshold(conf, correct):
    for t in sorted(set(conf)):
        acc = [ok for x, ok in zip(conf, correct) if x >= t]
        if len(acc) < 5:
            return None
        if sum(acc) / len(acc) >= 0.95:
            return {"conf_threshold": float(t), "dev_precision": S.rnd(sum(acc) / len(acc)), "dev_coverage": S.rnd(len(acc) / len(conf)),
                    "dev_n_accepted": len(acc)}
    return None


def overfit_summary(rows):
    ml = min(rows, key=lambda r: (r["dev_loss"], r["epoch"]))
    last = rows[-1]
    return {"min_dev_loss_epoch": ml["epoch"], "min_dev_loss": ml["dev_loss"], "final_dev_loss": last["dev_loss"],
            "final_train_acc": last["train_acc"], "final_dev_top1": last["dev_top1"],
            "dev_loss_rise_after_min": round(last["dev_loss"] - ml["dev_loss"], 5)}


def main():
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    env = S.load_json(S.ENV_JSON)
    max_len = env["selected_max_length"]
    lm = S.load_json(S.DATA / "label_map.json")
    inv = sorted(lm, key=lm.get)
    X, y = S.train_data()
    yi = [lm[c] for c in y]
    _, dev_rows, _ = S.eval_sets()                     # test 행은 쓰지 않음
    dtexts = [S.norm(g["text_ko"]) for g in dev_rows]
    dyi = [lm[g["primary_concept"]] for g in dev_rows]
    dev = torch.device("cuda")
    tok = AutoTokenizer.from_pretrained(S.PRETRAINED)
    curves, grid_rows, best = [], [], None
    grid = [{"lr": lr, "epochs": e, "loss": ls} for lr in LRS for e in EPOCHS for ls in LOSSES]
    for gi, p in enumerate(grid):
        t0 = time.time()
        _, b, _, peak, _ = train_run(p, S.PRIMARY_SEED, X, yi, dtexts, dyi, dev_rows, inv, max_len, dev, tok, curves, f"grid{gi}")
        rows = [r for r in curves if r["tag"] == f"grid{gi}"]
        r = {"grid_index": gi, **p, "best_epoch": b["epoch"], "best_dev_top1": b["dev_top1"], "best_dev_recall_at_3": b["dev_recall_at_3"],
             "best_dev_loss": b["dev_loss"], "train_acc_at_best": b["train_acc"], "train_loss_at_best": b["train_loss_eval"],
             **overfit_summary(rows), "train_seconds": round(time.time() - t0, 1), "peak_vram_alloc_mib": peak["alloc_mib"],
             "peak_vram_reserved_mib": peak["reserved_mib"]}
        grid_rows.append(r)
        print({k: r[k] for k in ("grid_index", "lr", "epochs", "loss", "best_epoch", "best_dev_top1", "best_dev_recall_at_3", "train_acc_at_best",
                                  "min_dev_loss_epoch", "train_seconds")}, flush=True)
        key = (b["dev_top1"], b["dev_recall_at_3"], -b["dev_loss"], -gi)
        if best is None or key > best[0]:
            best = (key, gi, p)
    S.write_csv(S.OUT / "koelectra_dev_grid.csv", grid_rows)
    _, gsel, psel = best

    seeds = {}
    for seed in S.SEEDS:
        t0 = time.time()
        sd, b, dl, peak, cfg = train_run(psel, seed, X, yi, dtexts, dyi, dev_rows, inv, max_len, dev, tok, curves, f"seed{seed}")
        model = AutoModelForSequenceClassification.from_config(cfg)
        model.load_state_dict(sd)
        S.ft_dir(seed).mkdir(exist_ok=True)
        model.save_pretrained(S.ft_dir(seed))
        tok.save_pretrained(S.ft_dir(seed))
        prob = torch.softmax(torch.tensor(dl), -1).numpy()
        correct = [inv[int(i)] == gg["primary_concept"] for i, gg in zip(prob.argmax(1), dev_rows)]
        sel = {"PROTOCOL_DEVIATION": "v2 grid 확장(v1 grid 학습 붕괴)", "grid_index": gsel, "params": psel, "seed": seed,
               "best_epoch": b["epoch"], "dev_core": {"n": len(dev_rows), "top1": b["dev_top1"], "recall_at_3": b["dev_recall_at_3"],
                                                      "recall_at_5": b["dev_recall_at_5"]},
               "dev_loss_at_best": b["dev_loss"], "train_acc_at_best": b["train_acc"], "train_loss_at_best": b["train_loss_eval"],
               "training_peak_vram": peak, "train_seconds": round(time.time() - t0, 1),
               "fixed": {"batch": BATCH, "weight_decay": WD, "warmup_ratio": WARMUP, "grad_clip": CLIP, "max_length": max_len,
                         "optimizer": "AdamW", "schedule": "linear"},
               "auto_accept_dev": conf_threshold(prob.max(1).tolist(), correct), "confidence_note": "max softmax = 분류 confidence(확률·임상 확률 아님)"}
        S.dump_json(S.seed_out(seed) / "koelectra_selection.json", sel)
        seeds[seed] = sel
        print("SEED", seed, b["epoch"], sel["dev_core"], sel["auto_accept_dev"], flush=True)
    g42 = grid_rows[gsel]
    match = (seeds[S.PRIMARY_SEED]["best_epoch"], seeds[S.PRIMARY_SEED]["dev_core"]["top1"]) == (g42["best_epoch"], g42["best_dev_top1"])
    S.write_csv(S.OUT / "koelectra_epoch_curves.csv", curves)
    tops = [seeds[s]["dev_core"]["top1"] for s in S.SEEDS]
    S.dump_json(S.OUT / "koelectra_selection.json", {
        "PROTOCOL_DEVIATION": True, "deviation_reason": "v1 사전 등록 grid(lr≤5e-5, epochs≤8)에서 학습 붕괴(학습 정확도 4.3%, 단일 class)",
        "approved_by_user": "2026-10-09", "grid": grid, "selection_rule": "run 안 dev best epoch, run 간 dev Top-1 > R@3 > dev loss > grid 순서",
        "selected_grid_index": gsel, "selected_params": psel, "primary_seed": S.PRIMARY_SEED, "primary_seed_matches_grid_run": match,
        "seed_dev_top1": {s: seeds[s]["dev_core"]["top1"] for s in S.SEEDS},
        "seed_dev_top1_mean": round(float(np.mean(tops)), 4), "seed_dev_top1_std": round(float(np.std(tops)), 4),
        "seed_best_epochs": {s: seeds[s]["best_epoch"] for s in S.SEEDS}})
    print("SELECTED", gsel, psel, "seed42 match", match, "dev mean±std", round(float(np.mean(tops)), 4), round(float(np.std(tops)), 4), flush=True)


if __name__ == "__main__":
    main()
