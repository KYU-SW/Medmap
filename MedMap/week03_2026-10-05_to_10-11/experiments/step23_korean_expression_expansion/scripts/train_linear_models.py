"""STEP23 학습 + dev 선택. FIXED_REGRESSION_TEST 는 읽지 않는다.

조건 ORIGINAL / EXPANDED × 사전 등록 후보 LINEAR_CHAR / LINEAR_WORD_CHAR.
ngram·min_df = STEP22 dev 선택값 고정, C ∈ {0.5,1,2,4} × class_weight ∈ {None, balanced} 만 dev 선택(STEP22 설정 포함).
선택 기준: dev core Top-1 > Recall@3 > Recall@5 > grid 순서. BEST_MODEL = EXPANDED dev core Top-1 > R@3 > LINEAR_CHAR 우선.
auto-accept margin: dev 에서 precision ≥ 0.95 를 만족하는 최소 margin(수락 ≥ 5건), 없으면 None.
출력: models/linear_{char,word_char}_{expanded,original}.joblib · outputs/dev_selection_grid.csv · outputs/selection.json
"""
import json

import joblib

import s23_common as S

FILE = {"LINEAR_CHAR": "linear_char", "LINEAR_WORD_CHAR": "linear_word_char"}


def margin_threshold(pr):
    for t in sorted({p["margin"] for p in pr}):
        acc = [p for p in pr if p["margin"] >= t]
        if len(acc) < 5:
            return None
        prec = sum(p["correct"] for p in acc) / len(acc)
        if prec >= 0.95:
            return {"margin_threshold": t, "dev_precision": S.rnd(prec), "dev_coverage": S.rnd(len(acc) / len(pr)), "dev_n_accepted": len(acc)}
    return None


def main():
    core_ids = {r["utterance_id"] for r in S.read_csv(S.S22 / "data/normalizer_core_dev.csv")}
    dev = [g for g in S.load_gold() if g["split"] == "dev" and g["utterance_id"] in core_ids]
    texts = [S.norm(g["text_ko"]) for g in dev]
    sel, grid_rows = {"selection_rule": "dev core Top-1 > R@3 > R@5 > grid order", "conditions": {}}, []
    for cond in S.CONDITIONS:
        X, y = S.load_condition(cond)
        sel["conditions"][cond] = {"n_train": len(X), "n_classes": len(set(y)), "families": {}}
        for fam in S.FAMILIES:
            best = None
            for gi, p in enumerate(S.grid(fam)):
                m = S.build(fam, p).fit(X, y)
                tk = S.topk(m, texts)
                s = S.score(dev, {g["utterance_id"]: [c for c, _ in t] for g, t in zip(dev, tk)})
                is_s22 = p == S.S22_PARAMS[fam]
                grid_rows.append({"condition": cond, "family": fam, "grid_index": gi, "params": json.dumps(p), "is_step22_config": str(is_s22),
                                  "dev_top1": s["top1"], "dev_recall_at_3": s["recall_at_3"], "dev_recall_at_5": s["recall_at_5"]})
                key = (s["top1"], s["recall_at_3"], s["recall_at_5"], -gi)
                if best is None or key > best[0]:
                    best = (key, gi, p, s)
            _, gi, p, s = best
            m = S.build(fam, p).fit(X, y)
            mf = S.MODELS / f"{FILE[fam]}_{cond.lower()}.joblib"
            joblib.dump(m, mf)
            tk = S.topk(m, texts)
            pr = [{"margin": t[0][1] - t[1][1], "correct": t[0][0] == g["primary_concept"]} for g, t in zip(dev, tk)]
            s22 = next(r for r in grid_rows if r["condition"] == cond and r["family"] == fam and r["is_step22_config"] == "True")
            sel["conditions"][cond]["families"][fam] = {"grid_index": gi, "params": p, "dev_core": s, "model_file": str(mf.relative_to(S.STEP)),
                                                        "auto_accept_dev": margin_threshold(pr),
                                                        "step22_config_dev_top1": s22["dev_top1"]}
    fe = sel["conditions"]["EXPANDED"]["families"]
    sel["BEST_MODEL"] = max(S.FAMILIES, key=lambda f: (fe[f]["dev_core"]["top1"], fe[f]["dev_core"]["recall_at_3"], -S.FAMILIES.index(f)))
    sel["best_model_rule"] = "EXPANDED dev core Top-1 > R@3 > LINEAR_CHAR first"
    S.write_csv(S.OUT / "dev_selection_grid.csv", grid_rows)
    S.dump_json(S.OUT / "selection.json", sel)
    for c, v in sel["conditions"].items():
        for f, d in v["families"].items():
            print(c, f, d["params"], d["dev_core"], d["auto_accept_dev"])
    print("BEST_MODEL", sel["BEST_MODEL"])


if __name__ == "__main__":
    main()
