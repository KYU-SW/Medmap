"""STEP26 Baseline A — 기존 LINEAR_ONLY · HYBRID_B 를 설정·임계값 그대로 재평가(재학습·재튜닝 없음).
EXT 지표는 weak-label proxy(정확도 아님), INT_REGRESSION_CORE 는 합성 regression(보고 전용).
출력: outputs/baseline_metrics.json
"""
import policy_lib as P
import s26_common as S


def main():
    rows = P.load_rows()
    out = {"note": "EXT_* = weak-label proxy, canonical 정확도 아님. INT_REGRESSION_CORE = 합성 regression(보고 전용).",
           "thresholds": {"T_lin": S.T_LIN, "T_koe": S.T_KOE}}
    for name in ("LINEAR_ONLY", "HYBRID_B"):
        out[name] = {}
        for part, sets in (("DEV", ("EXT_DEV", "INT_DEV_CORE")), ("EVAL", ("EXT_EVAL", "INT_REGRESSION_CORE")), ("KMC", ("KMC_COMPLEX_STRESS",))):
            rs = [r for r in rows if r["set"] in sets]
            out[name][part] = P.metrics(rs, {r["row_id"]: P.baseline(name, r) for r in rs})
        out[name]["EVAL"]["koe_call_rate_ext_eval"] = (S.rnd(sum(r["lin_margin"] < S.T_LIN for r in rows if r["set"] == "EXT_EVAL") /
                                                      sum(r["set"] == "EXT_EVAL" for r in rows)) if name == "HYBRID_B" else 0.0)
    S.dump_json(S.OUT / "baseline_metrics.json", out)
    for n in ("LINEAR_ONLY", "HYBRID_B"):
        print(n, {k: v for k, v in out[n]["EVAL"].items() if "auto" in k or "unknown" in k})


if __name__ == "__main__":
    main()
