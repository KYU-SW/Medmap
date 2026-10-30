"""STEP24 Linear ↔ KoELECTRA agreement + 오류 분류(core test, 예측 파일만 읽음).

오류 분류 규칙(순서 고정, 모델별 오류 문장마다 1개):
 nausea/vomiting → fatigue/weakness → body-site(pain·sore_throat·palpitations·heartburn) →
 surface-pattern bias(Linear 오류인데 KoELECTRA 정답) → Transformer semantic confusion(KoELECTRA 오류인데 Linear 정답) →
 insufficient training(정답 class 학습 표현 < 30) → semantic paraphrase(학습 유사도 < 0.5) →
 generic expression(공백 제거 6자 이하) → unseen synonym(그 외)
출력: outputs/agreement_analysis.csv · outputs/agreement_summary.json · outputs/error_analysis.csv
"""
import collections

import s24_common as S

NV, FW, SITE = {"nausea", "vomiting"}, {"fatigue", "limb_weakness"}, {"pain", "sore_throat", "palpitations", "heartburn"}


def main():
    gold, _, core_test = S.eval_sets()
    G = {g["utterance_id"]: g for g in core_test}
    lin = {r["utterance_id"]: r for r in S.read_csv(S.OUT / "predictions_linear.csv") if r["utterance_id"] in G}
    koe = {r["utterance_id"]: r for r in S.read_csv(S.OUT / "predictions_transformer.csv") if r["utterance_id"] in G}
    hyb = [r for r in S.read_csv(S.OUT / "predictions_hybrid.csv") if r["utterance_id"] in G]
    primary = S.load_json(S.OUT / "hybrid_metrics.json")["PRIMARY_HYBRID"]
    sim = S.test_similarity(core_test)
    cnt = collections.Counter(r["canonical_id"] for r in S.read_csv(S.S23 / "data/expanded_train_expressions.csv"))

    rows, cats = [], collections.Counter()
    for u, g in G.items():
        lc, kc = lin[u]["top1_correct"] == "True", koe[u]["top1_correct"] == "True"
        cell = ("both_correct" if lc and kc else "linear_correct_transformer_wrong" if lc else
                "linear_wrong_transformer_correct" if kc else
                "both_wrong_same_label" if lin[u]["top1"] == koe[u]["top1"] else "both_wrong_different_label")
        rows.append({"utterance_id": u, "gold": g["primary_concept"], "linear_top1": lin[u]["top1"], "koelectra_top1": koe[u]["top1"],
                     "cell": cell, "sim_bucket": S.sim_bucket(sim[u]), "sim_max_generated": round(sim[u], 4)})
    S.write_csv(S.OUT / "agreement_analysis.csv", rows)
    summ = {"core_test": dict(collections.Counter(r["cell"] for r in rows)),
            "low_similarity_lt_0.5": dict(collections.Counter(r["cell"] for r in rows if r["sim_max_generated"] < 0.5)),
            "agree_rate": S.rnd(sum(r["linear_top1"] == r["koelectra_top1"] for r in rows) / len(rows)),
            "agree_precision": S.rnd(sum(r["cell"] == "both_correct" for r in rows) /
                                     max(1, sum(r["linear_top1"] == r["koelectra_top1"] for r in rows)))}

    err = []
    preds = {"LINEAR_CHAR": {u: r["top1"] for u, r in lin.items()}, "KOELECTRA_SMALL": {u: r["top1"] for u, r in koe.items()},
             primary: {r["utterance_id"]: r["top1"] for r in hyb if r["model"] == primary}}
    for name, p in preds.items():
        for u, g in G.items():
            gc, pc = g["primary_concept"], p[u]
            if pc == gc:
                continue
            pair = {gc, pc}
            lc, kc = lin[u]["top1"] == gc, koe[u]["top1"] == gc
            cat = ("nausea/vomiting" if pair == NV else "fatigue/weakness" if pair <= FW else "body-site confusion" if pair <= SITE else
                   "surface-pattern bias" if (name == "LINEAR_CHAR" and kc) else
                   "Transformer semantic confusion" if (name == "KOELECTRA_SMALL" and lc) else
                   "insufficient training" if cnt[gc] < 30 else "semantic paraphrase" if sim[u] < 0.5 else
                   "generic expression" if len(S.nospace(g["text_ko"])) <= 6 else "unseen synonym")
            cats[(name, cat)] += 1
            err.append({"model": name, "utterance_id": u, "text_ko": g["text_ko"], "gold": gc, "pred": pc, "sim_max_generated": round(sim[u], 4),
                        "linear_top1": lin[u]["top1"], "koelectra_top1": koe[u]["top1"], "category": cat})
    S.write_csv(S.OUT / "error_analysis.csv", err)
    summ["error_categories"] = {n: {c: v for (m, c), v in cats.items() if m == n} for n in preds}
    S.dump_json(S.OUT / "agreement_summary.json", summ)
    print(summ)


if __name__ == "__main__":
    main()
