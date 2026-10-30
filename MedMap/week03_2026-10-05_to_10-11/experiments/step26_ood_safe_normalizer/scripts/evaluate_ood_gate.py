"""STEP26 상태 분류(KNOWN_SYMPTOM / UNCERTAIN / UNKNOWN_SYMPTOM / NON_SYMPTOM) + 실험용 출력 인터페이스.

자동 수락 여부 = BEST_POLICY(final_decisions.csv). 자동 수락되지 않은 입력의 상태(실행 전 고정 순서):
 1 COMPLEX_INPUT → UNCERTAIN / NEEDS_CONFIRMATION (복합 문장은 단일 증상으로 자동 수락 금지)
 2 BEST_POLICY auto → KNOWN_SYMPTOM / AUTO_ACCEPT
 3 p_non ≥ T_non → NON_SYMPTOM / DO_NOT_MAP (증상 기록과 분리, 원문 보존)
 4 Linear top1 = KoE top1 → UNCERTAIN / ASK_CONFIRMATION (후보 = 동의 concept + 각 모델 2위, 최대 3)
 5 p_non < 0.5 → UNKNOWN_SYMPTOM / NEEDS_CONFIRMATION (후보 없음, 원문 그대로 기록)
 6 그 외 → UNCERTAIN / NEEDS_CONFIRMATION
p_non: 문자 TF-IDF(2–4) + LogisticRegression(balanced, seed 42). 학습 = EXT_DEV 의 WEAK_SYMPTOM(1) ∪ STEP23 학습 표현(1)
       vs EXT_DEV WEAK_NON_SYMPTOM(0). WEAK_MIXED 미사용. 점수는 분류 점수(확률·임상 판단 아님).
T_non: grid {0.5..0.95} 중 EXT_DEV 5-fold CV 에서 NON 판정의 weak precision ≥ 0.95 이고
       INT_DEV_CORE(지원 증상 문장) NON 판정률 ≤ 0.05 인 최소값. 없으면 NON_SYMPTOM 판정을 쓰지 않음(→ UNCERTAIN).
출력: outputs/status_classifier.json · outputs/predictions.csv · outputs/status_distribution.csv
"""
import collections
import hashlib
import json

import numpy as np

import s26_common as S

GRID = [round(x, 2) for x in np.arange(0.5, 0.96, 0.05)]


def make():
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    return make_pipeline(TfidfVectorizer(analyzer="char", ngram_range=(2, 4), sublinear_tf=True),
                         LogisticRegression(C=1.0, class_weight="balanced", max_iter=3000, random_state=S.SEED))


def fold(key):
    return int(hashlib.sha256(f"st|{key}".encode()).hexdigest(), 16) % 5


def main():
    fin = S.read_csv(S.OUT / "final_decisions.csv")
    inv = {r["row_id"]: r for r in S.read_csv(S.DATA / "weak_label_inventory.csv")}
    train_expr = [S.norm(r["expression"]) for r in S.read_csv(S.S23 / "data/expanded_train_expressions.csv")]
    dev = [f for f in fin if f["set"] == "EXT_DEV" and f["weak_label"] in ("WEAK_SYMPTOM", "WEAK_NON_SYMPTOM")]
    core_dev = [f for f in fin if f["set"] == "INT_DEV_CORE"]

    # CV for T_non
    pn_cv = {}
    for k in range(5):
        tr = [f for f in dev if fold(inv[f["row_id"]]["cluster"]) != k]
        ho = [f for f in dev if fold(inv[f["row_id"]]["cluster"]) == k]
        m = make().fit([S.norm(f["text"]) for f in tr] + train_expr, [int(f["weak_label"] == "WEAK_NON_SYMPTOM") for f in tr] + [0] * len(train_expr))
        for f, p in zip(ho, m.predict_proba([S.norm(f["text"]) for f in ho])[:, 1]):
            pn_cv[f["row_id"]] = float(p)
    full = make().fit([S.norm(f["text"]) for f in dev] + train_expr, [int(f["weak_label"] == "WEAK_NON_SYMPTOM") for f in dev] + [0] * len(train_expr))
    pcore = dict(zip([f["row_id"] for f in core_dev], full.predict_proba([S.norm(f["text"]) for f in core_dev])[:, 1]))
    grid_rows, T_non = [], None
    for t in GRID:
        pred = [f for f in dev if pn_cv[f["row_id"]] >= t]
        prec = sum(f["weak_label"] == "WEAK_NON_SYMPTOM" for f in pred) / len(pred) if pred else None
        rec = sum(f["weak_label"] == "WEAK_NON_SYMPTOM" for f in pred) / max(1, sum(f["weak_label"] == "WEAK_NON_SYMPTOM" for f in dev))
        core_rate = sum(pcore[f["row_id"]] >= t for f in core_dev) / len(core_dev)
        ok = bool(prec is not None and prec >= 0.95 and core_rate <= 0.05)
        core_rate = float(core_rate)
        grid_rows.append({"t": t, "cv_weak_precision": S.rnd(prec), "cv_weak_recall": S.rnd(rec), "dev_core_non_rate(in-sample)": S.rnd(core_rate), "ok": ok})
        if ok and T_non is None:
            T_non = t
    allp = dict(zip([f["row_id"] for f in fin], full.predict_proba([S.norm(f["text"]) for f in fin])[:, 1]))
    import joblib
    (S.STEP / "models").mkdir(exist_ok=True)
    joblib.dump(full, S.STEP / "models/status_classifier.joblib")
    S.dump_json(S.OUT / "status_classifier.json", {"T_non": T_non, "grid": grid_rows, "rules": __doc__,
                                                    "n_train": {"weak_symptom": sum(f["weak_label"] == "WEAK_SYMPTOM" for f in dev),
                                                                "weak_non": sum(f["weak_label"] == "WEAK_NON_SYMPTOM" for f in dev),
                                                                "step23_train_expressions": len(train_expr)}})

    cache = np.load(S.OUT / "model_cache.npz")
    cls = list(cache["classes"])
    ri = {r: i for i, r in enumerate(cache["row_id"])}
    out = []
    for f in fin:
        i = ri[f["row_id"]]
        l2 = cls[int(np.argsort(-cache["L"][i])[1])]
        k2 = cls[int(np.argsort(-cache["P"][i])[1])]
        pn = float(allp[f["row_id"]])
        agree = f["agree"] == "True"
        if f["complex_flags"]:
            status, decision, cand, reason = "UNCERTAIN", "NEEDS_CONFIRMATION", [], "COMPLEX_INPUT:" + f["complex_flags"]
        elif f["new_auto"] == "True":
            status, decision, cand, reason = "KNOWN_SYMPTOM", "AUTO_ACCEPT", [f["new_label"]], "BEST_POLICY"
        elif T_non is not None and pn >= T_non:
            status, decision, cand, reason = "NON_SYMPTOM", "DO_NOT_MAP", [], "NON_SYMPTOM_SCORE"
        elif agree:
            cand = list(dict.fromkeys([f["lin_top1"], l2, k2]))[:3]
            status, decision, reason = "UNCERTAIN", "ASK_CONFIRMATION", "AGREE_LOW_CONFIDENCE"
        elif pn < 0.5:
            status, decision, cand, reason = "UNKNOWN_SYMPTOM", "NEEDS_CONFIRMATION", [], "DISAGREE_SYMPTOM_LIKE"
        else:
            status, decision, cand, reason = "UNCERTAIN", "NEEDS_CONFIRMATION", [], "DISAGREE_UNCLEAR"
        iface = {"status": status, "canonical_id": cand[0] if status == "KNOWN_SYMPTOM" else None, "candidate_ids": cand, "decision": decision,
                 "requires_confirmation": decision in ("ASK_CONFIRMATION", "NEEDS_CONFIRMATION"), "source_text": f["text"],
                 "model_evidence": {"linear_top1": f["lin_top1"], "linear_margin": float(f["lin_margin"]), "transformer_top1": f["koe_top1"],
                                    "transformer_score": float(f["koe_conf"]), "agreement": agree, "train_similarity": float(f["train_sim"]),
                                    "non_symptom_score": round(pn, 4)}, "reason": reason}
        out.append({**{k: f[k] for k in ("row_id", "set", "weak_label", "gold_concept", "text", "lin_top1", "koe_top1", "agree", "linear_only",
                                          "linear_only_auto", "hybrid_b", "hybrid_b_auto", "new_auto", "new_label")},
                    "non_symptom_score": round(pn, 6), "status": status, "decision": decision, "candidate_ids": ";".join(cand), "reason": reason,
                    "interface_json": json.dumps(iface, ensure_ascii=False)})
    S.write_csv(S.OUT / "predictions.csv", out)
    dist = []
    for st in ("EXT_DEV", "EXT_EVAL", "INT_DEV_CORE", "INT_REGRESSION_CORE", "KMC_COMPLEX_STRESS"):
        for w in sorted({o["weak_label"] for o in out if o["set"] == st}):
            rs = [o for o in out if o["set"] == st and o["weak_label"] == w]
            c = collections.Counter(o["status"] for o in rs)
            dist.append({"set": st, "weak_label": w or "-", "n": len(rs), **{s: c.get(s, 0) for s in ("KNOWN_SYMPTOM", "UNCERTAIN", "UNKNOWN_SYMPTOM", "NON_SYMPTOM")},
                         "known_correct(internal only)": sum(o["status"] == "KNOWN_SYMPTOM" and o["new_label"] == o["gold_concept"] for o in rs) if st.startswith("INT") else ""})
    S.write_csv(S.OUT / "status_distribution.csv", dist)
    print("T_non", T_non)
    for d in dist:
        print(d)


if __name__ == "__main__":
    main()
