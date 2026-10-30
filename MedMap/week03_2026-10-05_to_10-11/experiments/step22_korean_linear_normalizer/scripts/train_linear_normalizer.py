"""STEP22 학습 + dev 기반 hyperparameter 선택. sealed test 는 이 스크립트에서 읽지 않는다.

- TRAIN = data/train_expressions.csv (view: CURATED 주, RAW 비교)
- DEV   = data/normalizer_core_dev.csv (59, Claude 작성 합성 문장 · 사전과 누수 검사 통과, 학습에는 미사용)
- 선택 기준(사전 고정): dev core Top-1 ↓ → Recall@3 ↓ → Recall@5 ↓ → grid 순서(작은 C·None 우선)
- BEST_MODEL(family) 도 dev core Top-1 기준으로 test 이전에 고정(PRIMARY_VIEW=CURATED).
- auto-accept margin 임계값(top1 − top2 decision score): dev 에서 precision ≥ 0.95 이면서 coverage 최대인 값(수락 ≥ 5건).
출력: models/linear_{word,char,word_char}[ _raw].joblib · outputs/dev_selection_grid.csv · outputs/selection.json
      outputs/predictions_dev.csv
"""
import json

import joblib

import lin_common as L

FILE = {"LINEAR_WORD": "linear_word", "LINEAR_CHAR": "linear_char", "LINEAR_WORD_CHAR": "linear_word_char"}


def dev_rows():
    core_ids = {r["utterance_id"] for r in L.read_csv(L.DATA / "normalizer_core_dev.csv")}
    gold = [g for g in L.load_gold() if g["split"] == "dev"]     # test 행은 여기서 즉시 버림
    return [g for g in gold if g["utterance_id"] in core_ids], gold


def margin_threshold(preds: list[dict]):
    """preds: {margin, correct}. precision≥0.95 를 만족하는 최소 margin(=coverage 최대). 없으면 None."""
    best = None
    for t in sorted({p["margin"] for p in preds}):
        acc = [p for p in preds if p["margin"] >= t]
        if len(acc) < 5:
            break
        prec = sum(p["correct"] for p in acc) / len(acc)
        if prec >= 0.95:
            best = {"margin_threshold": t, "dev_precision": L.rnd(prec), "dev_coverage": L.rnd(len(acc) / len(preds)),
                    "dev_n_accepted": len(acc)}
            break
    return best


def main():
    dev, dev_all = dev_rows()
    texts = [L.norm(g["text_ko"]) for g in dev]
    grid_rows, sel = [], {"selection_rule": "dev core Top-1 > Recall@3 > Recall@5 > grid order", "views": {}}
    for view in L.VIEWS:
        X, y = L.load_train(view)
        sel["views"][view] = {"n_train": len(X), "n_classes": len(set(y)), "families": {}}
        for fam in L.FAMILIES:
            best = None
            for gi, p in enumerate(L.grid(fam)):
                m = L.build(fam, p).fit(X, y)
                tk = L.topk(m, texts)
                s = L.score(dev, {g["utterance_id"]: [c for c, _ in t] for g, t in zip(dev, tk)})
                grid_rows.append({"view": view, "family": fam, "grid_index": gi, "params": json.dumps(p),
                                  "dev_core_n": s["n"], "dev_top1": s["top1"], "dev_recall_at_3": s["recall_at_3"],
                                  "dev_recall_at_5": s["recall_at_5"]})
                key = (s["top1"], s["recall_at_3"], s["recall_at_5"], -gi)
                if best is None or key > best[0]:
                    best = (key, gi, p, s)
            _, gi, p, s = best
            m = L.build(fam, p).fit(X, y)
            suffix = "" if view == L.PRIMARY_VIEW else "_raw"
            joblib.dump(m, L.MODELS / f"{FILE[fam]}{suffix}.joblib")
            tk = L.topk(m, texts)
            pr = [{"margin": t[0][1] - t[1][1], "correct": t[0][0] == g["primary_concept"]} for g, t in zip(dev, tk)]
            sel["views"][view]["families"][fam] = {"grid_index": gi, "params": p, "dev_core": s,
                                                   "model_file": f"models/{FILE[fam]}{suffix}.joblib",
                                                   "auto_accept_dev": margin_threshold(pr), "grid_size": len(L.grid(fam))}
    fams = sel["views"][L.PRIMARY_VIEW]["families"]
    order = {f: i for i, f in enumerate(L.FAMILIES)}
    sel["BEST_MODEL"] = max(L.FAMILIES, key=lambda f: (fams[f]["dev_core"]["top1"], fams[f]["dev_core"]["recall_at_3"],
                                                       -order[f]))
    sel["best_model_rule"] = "PRIMARY_VIEW(CURATED) dev core Top-1 > Recall@3 > simpler family"
    sel["primary_view"] = L.PRIMARY_VIEW
    L.write_csv(L.OUT / "dev_selection_grid.csv", grid_rows)
    L.dump_json(L.OUT / "selection.json", sel)

    # predictions_dev.csv: 선택 모델(주 view)로 dev 전체(97) 예측, core flag 포함
    pdev = []
    for fam in L.FAMILIES:
        m = joblib.load(L.MODELS / f"{FILE[fam]}.joblib")
        for g, t in zip(dev_all, L.topk(m, [L.norm(x["text_ko"]) for x in dev_all])):
            pdev.append({"model": fam, "view": L.PRIMARY_VIEW, "utterance_id": g["utterance_id"], "is_core": str(L.is_core(g)),
                         "tier": g["tier"], "text_ko": g["text_ko"], "gold_primary": g["primary_concept"],
                         "should_link": g["should_link"], "top1": t[0][0], "top1_score": round(t[0][1], 6),
                         "margin": round(t[0][1] - t[1][1], 6), "ranked_top5": ";".join(c for c, _ in t)})
    L.write_csv(L.OUT / "predictions_dev.csv", pdev)
    for v in L.VIEWS:
        for f in L.FAMILIES:
            d = sel["views"][v]["families"][f]
            print(v, f, d["params"], d["dev_core"], d["auto_accept_dev"])
    print("BEST_MODEL", sel["BEST_MODEL"])


if __name__ == "__main__":
    main()
