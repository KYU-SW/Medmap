"""STEP27 1단계 — 기존 실험 산출물 확인·B4 재현·label map 검증(read-only 입력, 출력은 STEP27 폴더에만).

검사:
 I1 입력 파일 SHA256 기록(STEP23 학습 표현·STEP24-v2 KoE config·STEP25 외부 예측·STEP26 산출물 전부)
 I2 label map: STEP26 cache classes == LinearSVC classes_ == STEP24 label_map(사전순) == KoE config id2label 개수(LABEL_i 순서 = label_map)
 I3 B4 재현: features.csv 에 policy_lib.decide('B4', policy_selection 파라미터) 적용 == final_decisions.csv new_auto(전 행)
 I4 STEP26 상태 재현: final_decisions + predictions.non_symptom_score 에 STEP26 순서 규칙 적용 == predictions.csv status(전 행)
 I5 Linear decision score 재계산: 무작위 아닌 앞 200 행 Linear decision_function == cache L(최대 절대차 기록)
 I6 STEP26 판정·임계값(T_non) 기록
출력: outputs/previous_inspection.json · data/evaluation_manifest.csv(집합·weak label·split·STEP26 노출 여부)
"""
import collections

import numpy as np

import s27_common as S

S26 = S.S26


def main():
    o = S26.OUT
    files = [S.S23 / "data/expanded_train_expressions.csv", S26.KOE_DIR / "config.json", S26.KOE_DIR / "model.safetensors",
             S26.S25_DIR / "outputs/external_predictions.csv", S26.S25_DIR / "data/eligible_external_examples.csv",
             S26.DATA / "weak_label_inventory.csv", S26.STEP / "models/status_classifier.joblib"] + sorted(o.glob("*.csv")) + sorted(o.glob("*.json")) + [o / "model_cache.npz"]
    sha = {str(f.relative_to(S.REPO)): (S.sha256(f) if f.exists() else "MISSING") for f in files}

    cache = np.load(o / "model_cache.npz")
    cls = [str(c) for c in cache["classes"]]
    lin, _ = S26.S24.linear_model()
    lm = S26.S24.label_map()
    koe_cfg = S.load_json(S26.KOE_DIR / "config.json")
    i2 = {"cache_eq_linear": cls == list(lin.classes_), "cache_eq_label_map": cls == sorted(lm, key=lm.get),
          "koe_n_labels": len(koe_cfg["id2label"]), "n_classes": len(cls)}

    feats = {r["row_id"]: r for r in S.P26.load_rows()}
    fin = S.read_csv(o / "final_decisions.csv")
    sel = S.load_json(o / "policy_selection.json")
    p = sel["policies"]["B4"]["params"]
    mism_b4 = [f["row_id"] for f in fin if S.P26.decide("B4", p, feats[f["row_id"]])[1] != (f["new_auto"] == "True")]

    pred = {r["row_id"]: r for r in S.read_csv(o / "predictions.csv")}
    T_non = S.load_json(o / "status_classifier.json")["T_non"]
    mism_st = []
    for f in fin:
        pn = float(pred[f["row_id"]]["non_symptom_score"])
        if f["complex_flags"]:
            st = "UNCERTAIN"
        elif f["new_auto"] == "True":
            st = "KNOWN_SYMPTOM"
        elif pn >= T_non:
            st = "NON_SYMPTOM"
        elif f["agree"] == "True":
            st = "UNCERTAIN"
        elif pn < 0.5:
            st = "UNKNOWN_SYMPTOM"
        else:
            st = "UNCERTAIN"
        if st != pred[f["row_id"]]["status"]:
            mism_st.append(f["row_id"])

    ri = {r: i for i, r in enumerate(cache["row_id"])}
    head = fin[:200]
    L = np.atleast_2d(lin.decision_function([S.norm(f["text"]) for f in head]))
    i5 = float(np.abs(L - cache["L"][[ri[f["row_id"]] for f in head]]).max())

    inv = {r["row_id"]: r for r in S.read_csv(S26.DATA / "weak_label_inventory.csv")}
    pri = {S.nospace(r["text"]) for r in S.read_csv(o / "priority_cases.csv")}
    man = [{"row_id": f["row_id"], "set": f["set"], "weak_label": f["weak_label"], "gold_concept": f["gold_concept"], "text": f["text"],
            "cluster": inv.get(f["row_id"], {}).get("cluster", ""), "role": {"EXT_DEV": "SELECTION", "INT_DEV_CORE": "SELECTION"}.get(f["set"], "REPORT_ONLY"),
            "step26_priority_case_exposed": S.nospace(f["text"]) in pri} for f in fin]
    S.write_csv(S.DATA / "evaluation_manifest.csv", man)

    out = {"I1_input_sha256": sha, "I2_label_map": i2, "I3_b4_reproduction": {"params": p, "n_rows": len(fin), "mismatch": len(mism_b4), "examples": mism_b4[:5]},
           "I4_step26_status_reproduction": {"T_non": T_non, "mismatch": len(mism_st), "examples": mism_st[:5]},
           "I5_linear_score_recompute_max_abs_diff(200 rows)": i5,
           "I6_step26_verdict": S.load_json(o / "step26_verdict.json"),
           "set_counts": dict(collections.Counter(f["set"] for f in fin)),
           "manifest_exposed_priority_rows": sum(m["step26_priority_case_exposed"] for m in man)}
    ok = all([i2["cache_eq_linear"], i2["cache_eq_label_map"], i2["koe_n_labels"] == 77, not mism_b4, not mism_st, i5 < 1e-6,
              "MISSING" not in sha.values()])
    out["ALL_CHECKS_PASS"] = ok
    S.dump_json(S.OUT / "previous_inspection.json", out)
    print(S.dumps({k: v for k, v in out.items() if k != "I1_input_sha256"}))
    assert ok, "기존 산출물 검증 실패 — STEP27 중단"


if __name__ == "__main__":
    main()
