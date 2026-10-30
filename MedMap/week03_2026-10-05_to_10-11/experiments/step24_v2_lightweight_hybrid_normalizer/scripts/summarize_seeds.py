"""STEP24-v2 seed 변동성 집계 + PRIMARY_SEED 산출물을 outputs/ 최상위 이름으로 복사.
선행: 각 seed 에 대해 STEP24_SEED=<s> evaluate_transformer.py → evaluate_hybrid.py → analyze_agreement.py (run_all.sh).
seed 결과는 변동성 보고용이며 어떤 선택에도 쓰지 않는다(설정·checkpoint 규칙은 dev 로 이미 고정).
출력: outputs/seed_variability.json · outputs/seed_variability.csv · outputs/{transformer_metrics,hybrid_metrics,agreement_summary}.json 등 복사
"""
import shutil
import statistics

import s24_common as S

MODELS_ = ["LINEAR_CHAR", "KOELECTRA_SMALL", "HYBRID_A", "HYBRID_B", "HYBRID_C"]
COPY = ["transformer_metrics.json", "hybrid_metrics.json", "agreement_summary.json", "predictions_transformer.csv", "predictions_linear.csv",
        "predictions_hybrid.csv", "similarity_bucket_metrics.csv", "agreement_analysis.csv", "error_analysis.csv", "transformer_logits.npz"]


def ms(xs):
    xs = [x for x in xs if x is not None]
    return {"mean": round(statistics.mean(xs), 4), "std": round(statistics.pstdev(xs), 4), "min": min(xs), "max": max(xs), "n": len(xs)} if xs else None


def main():
    per, rows = {}, []
    for s in S.SEEDS:
        d = S.seed_out(s)
        hm, ag, ks = S.load_json(d / "hybrid_metrics.json"), S.load_json(d / "agreement_summary.json"), S.load_json(d / "koelectra_selection.json")
        per[s] = {"hm": hm, "ag": ag, "ks": ks}
        for m in MODELS_:
            r = hm["results"][m]
            rows.append({"seed": s, "model": m, "dev_top1": r["core_dev"]["top1"], "test_top1": r["core_test"]["top1"],
                         "test_recall_at_3": r["core_test"]["recall_at_3"], "test_recall_at_5": r["core_test"]["recall_at_5"],
                         "low_sim_top1": r["low_similarity_lt_0.5"]["top1"], "auto_precision": r["core_test"]["auto_precision"],
                         "auto_coverage": r["core_test"]["auto_coverage"], "best_epoch": ks["best_epoch"] if m != "LINEAR_CHAR" else "",
                         "primary_hybrid": hm["PRIMARY_HYBRID"]})
    S.write_csv(S.OUT / "seed_variability.csv", rows)
    summ = {m: {k: ms([r[k] for r in rows if r["model"] == m]) for k in ("dev_top1", "test_top1", "test_recall_at_3", "low_sim_top1", "auto_precision",
                                                                         "auto_coverage")} for m in MODELS_}
    lwtc = {s: per[s]["ag"]["core_test"].get("linear_wrong_transformer_correct", 0) for s in S.SEEDS}
    lctw = {s: per[s]["ag"]["core_test"].get("linear_correct_transformer_wrong", 0) for s in S.SEEDS}
    lw_low = {s: per[s]["ag"]["low_similarity_lt_0.5"].get("linear_wrong_transformer_correct", 0) for s in S.SEEDS}
    out = {"seeds": S.SEEDS, "primary_seed": S.PRIMARY_SEED, "summary": summ,
           "linear_wrong_transformer_correct": {"per_seed": lwtc, **ms(list(lwtc.values()))},
           "linear_correct_transformer_wrong": {"per_seed": lctw, **ms(list(lctw.values()))},
           "low_sim_linear_wrong_transformer_correct": {"per_seed": lw_low, **ms(list(lw_low.values()))},
           "semantic_gain_low_sim_per_seed": {s: S.rnd(per[s]["hm"]["results"]["KOELECTRA_SMALL"]["low_similarity_lt_0.5"]["top1"]
                                                    - per[s]["hm"]["results"]["LINEAR_CHAR"]["low_similarity_lt_0.5"]["top1"]) for s in S.SEEDS},
           "primary_hybrid_per_seed": {s: per[s]["hm"]["PRIMARY_HYBRID"] for s in S.SEEDS},
           "note": "seed 결과는 변동성 보고용. 선택에 쓰지 않음. FIXED_REGRESSION_TEST 는 blind 아님."}
    S.dump_json(S.OUT / "seed_variability.json", out)
    src = S.seed_out(S.PRIMARY_SEED)
    for f in COPY:
        shutil.copyfile(src / f, S.OUT / f)
    shutil.copyfile(src / "hybrid_config.json", S.MODELS / "hybrid_config.json")
    for m in MODELS_:
        print(m, {k: (v["mean"], v["std"]) for k, v in summ[m].items() if v})
    print("LW/TC", out["linear_wrong_transformer_correct"], "LC/TW", out["linear_correct_transformer_wrong"], "gain", out["semantic_gain_low_sim_per_seed"])


if __name__ == "__main__":
    main()
