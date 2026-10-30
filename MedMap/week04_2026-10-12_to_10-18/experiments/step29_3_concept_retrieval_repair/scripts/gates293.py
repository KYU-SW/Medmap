"""STEP29.3 §10·§14·§20 정책 선택·판정 규칙(검색기 구현 전 고정, 2026-10-14). 숫자는 outputs/ 에서 읽는다.

[정책 선택 — DEV29_3 + 노출 자료(회귀 사례·STEP29.2 HOLDOUT·pilot)만, FROZEN29_3 사용 금지]
 후보 = R0·R1·R2·R3·R4(단순·보수 순서 R0 < R1 < R2 < R3 < R4 — 뒤로 갈수록 구성 요소가 많음).
 1 hard 안전: DEV NEG_POSITIVE·OTHER_POSITIVE·SILVER_MODEL_INPUT·REASON_MISSING·STRING_SIM_ONLY_AUTO = 0 AND 회귀 사례 REGRESSION_VIOLATIONS = 0
   AND STEP29.2 HOLDOUT PROPAGATION_ERRORS·NEG_POSITIVE·OTHER_POSITIVE = 0 AND 노출 G5·G6 = 0
 2 하락 허용 범위(R0 대비, 사전 고정): DEV precision ≥ R0 − 0.005 · DEV coverage ≥ R0 − 0.01 ·
   STEP29.2 HOLDOUT precision ≥ R0 − 0.005 · coverage ≥ R0 − 0.005 (STEP29.2 기능 회귀 방지)
 3 균형: 자격 정책 중 DEV F1(β = 1, precision·coverage 조화평균 — 가중치 없음) 최대
 4 F1 이 최대값과 0.005 이내인 정책 중 DEV precision 최대 → 동률이면 더 단순한 정책(R0 쪽)
 자격 정책이 없으면 SELECTED = R0(STEP29.2 그대로)로 하고 기록.

[Hard gates — 공식(FROZEN29_3 + 회귀 사례 + 노출 + 약한 외부), 선택 정책 기준]
 G1 원문 보존 100%(FROZEN·DEV·STEP29.2 HOLDOUT·노출·WEAKNON 전 입력)        G2 span offset 유효 100%(같은 범위 mention)
 G3 핵심 의미 구별 위반 0: 회귀 사례 REGRESSION_VIOLATIONS = 0 AND FROZEN 검사기 v6 위반 입력 0
 G4 부정 증상의 환자 현재 양성 변환 0: FROZEN NEG_POSITIVE + STEP29.2 HOLDOUT NEG_POSITIVE·PROPAGATION_ERRORS + 노출 G5
 G5 OTHER_PERSON 환자 양성 모델 입력 0: FROZEN OTHER_POSITIVE + STEP29.2 HOLDOUT OTHER_POSITIVE + 노출 G6
 G6 신규 SILVER concept 모델 입력 0: FROZEN·DEV SILVER_MODEL_INPUT + 노출 G7 + WEAK SILVER_MODEL_INPUT
 G7 기존 연구 원본·제품 변경 0(outputs/protected_check.json G7 = research_ok AND product_ok)
 G8 검사기·평가·판정 코드(prereg_gates.json)와 정책 코드·선택(policy_freeze.json) SHA 일치
 G9 불확실 매핑 원문·사유 보존: FROZEN·노출·WEAK REASON_MISSING·G10 = 0
 G10 문자열 유사도만으로 자동 확정 0: FROZEN STRING_SIM_ONLY_AUTO = 0
[Performance — 공식(FROZEN29_3, 같은 입력 R0 대비; P8 은 STEP29.2 HOLDOUT)]
 P1 CONCEPT_AUTO_PRECISION(선택) ≥ R0 − 0.005          P2 CONCEPT_AUTO_COVERAGE(선택) ≥ R0 − 0.005
 P3 MORPHOLOGICAL_VARIANT_SUCCESS(선택) > R0 AND UNKNOWN_RATE(선택) ≤ R0
 P4 SEMANTIC_AMBIGUITY_ERRORS + WRONG_CONCEPT_AUTO_ACCEPT(선택) < R0 의 같은 합(R0 합이 0 이면 선택도 0)
 P5 MULTI_SPAN_RETENTION(선택) ≥ R0 − 0.005             P6 NEGATION_SCOPE·TEMPORALITY·EXPERIENCER(선택) 각각 ≥ R0 − 0.005
 P7 CPU p95(선택, 저부하 조건 A, pilot 274 단일 입력) ≤ 100 ms(outputs/latency.json)
 P8 STEP29.2 HOLDOUT(선택): CONCEPT_PRECISION ≥ R0 − 0.005 AND CONCEPT_COVERAGE ≥ R0 − 0.005 AND PROPAGATION_ERRORS = 0
[STEP29_3_RESULT] BLOCKED = 실행 불가 · REGRESSION = hard FAIL 또는 (P1 FAIL AND P2 FAIL) 또는 P8 FAIL ·
 RETRIEVAL_IMPROVED = hard 전부 + P1–P8 전부 · PARTIAL_IMPROVEMENT = hard 전부 + (P3 OR P4) + P1 + P5 + P6 · NO_GAIN = 그 외
[STEP30_READINESS] GO_FOR_RESEARCH = RETRIEVAL_IMPROVED · CONDITIONAL_GO = hard 전부 AND P1 AND P2 AND P5 AND P6 AND P8 AND 결과 ≠ REGRESSION · NO_GO = 그 외
PRODUCTION_READY = NO · HUMAN_VERIFIED_GOLD = 0(고정). 공식 평가 뒤 규칙 수정 결과는 EXPLORATORY 로만.
"""
from __future__ import annotations

CANDS = ("R0", "R1", "R2", "R3", "R4")


def f1(p, c):
    return 0.0 if not p or not c else 2 * p * c / (p + c)


def select_policy(M: dict) -> tuple[str, list]:
    r0 = M["R0"]
    rows = []
    for p in CANDS:
        d, h, x, rg = M[p]["DEV29_3"], M[p]["STEP29_2_HOLDOUT"], M[p]["EXPOSED"], M[p]["REGRESSION_CASES"]
        safe = (all(d[k] == 0 for k in ("NEG_POSITIVE", "OTHER_POSITIVE", "SILVER_MODEL_INPUT", "REASON_MISSING", "STRING_SIM_ONLY_AUTO"))
                and rg["REGRESSION_VIOLATIONS"] == 0 and h["PROPAGATION_ERRORS"] == 0 and h["NEG_POSITIVE"] == 0 and h["OTHER_POSITIVE"] == 0
                and x["G5_exposed"] == 0 and x["G6_exposed"] == 0)
        floor = (d["CONCEPT_AUTO_PRECISION"] >= r0["DEV29_3"]["CONCEPT_AUTO_PRECISION"] - 0.005 and d["CONCEPT_AUTO_COVERAGE"] >= r0["DEV29_3"]["CONCEPT_AUTO_COVERAGE"] - 0.01
                 and h["CONCEPT_PRECISION"] >= r0["STEP29_2_HOLDOUT"]["CONCEPT_PRECISION"] - 0.005
                 and h["CONCEPT_COVERAGE"] >= r0["STEP29_2_HOLDOUT"]["CONCEPT_COVERAGE"] - 0.005)
        rows.append({"policy": p, "safe": safe, "floor": floor, "eligible": safe and floor, "dev_f1": round(f1(d["CONCEPT_AUTO_PRECISION"], d["CONCEPT_AUTO_COVERAGE"]), 4),
                     "dev_precision": d["CONCEPT_AUTO_PRECISION"], "dev_coverage": d["CONCEPT_AUTO_COVERAGE"], "simplicity": CANDS.index(p)})
    ok = [r for r in rows if r["eligible"]]
    if not ok:
        return "R0", rows
    best = max(r["dev_f1"] for r in ok)
    near = [r for r in ok if r["dev_f1"] >= best - 0.005]
    near.sort(key=lambda r: (-r["dev_precision"], r["simplicity"]))
    return near[0]["policy"], rows


def verdict(M: dict, sel: str, protect: dict, latency: dict, prereg: dict) -> dict:
    F, F0 = M[sel]["FROZEN29_3"], M["R0"]["FROZEN29_3"]
    D, H, H0, X, W, RG = M[sel]["DEV29_3"], M[sel]["STEP29_2_HOLDOUT"], M["R0"]["STEP29_2_HOLDOUT"], M[sel]["EXPOSED"], M[sel]["WEAK"], M[sel]["REGRESSION_CASES"]
    hard = {"G1": F["RAW_PRESERVATION"] == 1.0 and D["RAW_PRESERVATION"] == 1.0 and H["RAW_PRESERVATION"] == 1.0 and X["raw_ok"] == X["inputs"] and W["raw_ok"] == W["weaknon_n"],
            "G2": F["OFFSET_VALID"] == 1.0 and D["OFFSET_VALID"] == 1.0 and H["OFFSET_VALID"] == 1.0 and X["offset_ok"] == X["mentions"],
            "G3": RG["REGRESSION_VIOLATIONS"] == 0 and F["SEMANTIC_VIOLATIONS"] == 0,
            "G4": F["NEG_POSITIVE"] + H["NEG_POSITIVE"] + H["PROPAGATION_ERRORS"] + X["G5_exposed"] == 0,
            "G5": F["OTHER_POSITIVE"] + H["OTHER_POSITIVE"] + X["G6_exposed"] == 0,
            "G6": F["SILVER_MODEL_INPUT"] + D["SILVER_MODEL_INPUT"] + X["G7_mentions"] + W["SILVER_MODEL_INPUT"] == 0,
            "G7": protect.get("G7") == "PASS",
            "G8": all(v for k, v in prereg.items() if k != "selected_policy"),
            "G9": F["REASON_MISSING"] + X["G10_mentions"] + W["REASON_MISSING"] == 0,
            "G10": F["STRING_SIM_ONLY_AUTO"] == 0}
    p95 = latency["condition_A_low_load"]["pilot274"][sel]["p95_ms"]
    P = {"P1": F["CONCEPT_AUTO_PRECISION"] >= F0["CONCEPT_AUTO_PRECISION"] - 0.005,
         "P2": F["CONCEPT_AUTO_COVERAGE"] >= F0["CONCEPT_AUTO_COVERAGE"] - 0.005,
         "P3": F["MORPHOLOGICAL_VARIANT_SUCCESS"] > F0["MORPHOLOGICAL_VARIANT_SUCCESS"] and F["UNKNOWN_RATE"] <= F0["UNKNOWN_RATE"],
         "P4": (F["SEMANTIC_AMBIGUITY_ERRORS"] + F["WRONG_CONCEPT_AUTO_ACCEPT"] < F0["SEMANTIC_AMBIGUITY_ERRORS"] + F0["WRONG_CONCEPT_AUTO_ACCEPT"])
               or (F0["SEMANTIC_AMBIGUITY_ERRORS"] + F0["WRONG_CONCEPT_AUTO_ACCEPT"] == 0 and F["SEMANTIC_AMBIGUITY_ERRORS"] + F["WRONG_CONCEPT_AUTO_ACCEPT"] == 0),
         "P5": F["MULTI_SPAN_RETENTION"] >= F0["MULTI_SPAN_RETENTION"] - 0.005,
         "P6": all(F[k] >= F0[k] - 0.005 for k in ("NEGATION_SCOPE", "TEMPORALITY", "EXPERIENCER")),
         "P7": p95 <= 100,
         "P8": H["CONCEPT_PRECISION"] >= H0["CONCEPT_PRECISION"] - 0.005 and H["CONCEPT_COVERAGE"] >= H0["CONCEPT_COVERAGE"] - 0.005 and H["PROPAGATION_ERRORS"] == 0}
    hp = all(hard.values())
    if not hp or (not P["P1"] and not P["P2"]) or not P["P8"]:
        res = "REGRESSION"
    elif all(P.values()):
        res = "RETRIEVAL_IMPROVED"
    elif (P["P3"] or P["P4"]) and P["P1"] and P["P5"] and P["P6"]:
        res = "PARTIAL_IMPROVEMENT"
    else:
        res = "NO_GAIN"
    if res == "RETRIEVAL_IMPROVED":
        s30 = "GO_FOR_RESEARCH"
    elif hp and all(P[k] for k in ("P1", "P2", "P5", "P6", "P8")) and res != "REGRESSION":
        s30 = "CONDITIONAL_GO"
    else:
        s30 = "NO_GO"
    pf = lambda d: {k: "PASS" if v else "FAIL" for k, v in d.items()}  # noqa: E731
    return {"STEP29_3_RESULT": res, "STEP30_READINESS": s30, "PRODUCTION_READY": "NO", "HUMAN_VERIFIED_GOLD": 0, "SELECTED_POLICY": sel,
            "hard_gates": pf(hard), "performance": pf(P), "p95_ms_condition_A": p95}
