"""STEP29.2 §12·§13·§17 판정 규칙(NLU 구현 전 고정, 2026-10-13). 숫자는 outputs/ 에서 읽는다(손으로 쓰지 않음).

[정책 선택 규칙 — DEV 세트 + 노출 pilot(개발 허용 자료)만 사용, HOLDOUT 사용 금지]
 후보 = V3_B0·V3_B1·V3_B2·V3_B3. 자격 = DEV 의 PROPAGATION_ERRORS·NEG_POSITIVE·OTHER_POSITIVE = 0 AND 노출 G5·G6·G7 = 0 AND
        DEV CONCEPT_PRECISION ≥ S29(DEV) − 0.01 AND 노출 reg_precision ≥ 0.9333 − 0.01.
 선택 = 자격 중 (DEV CONCEPT_COVERAGE + 노출 reg_coverage) 최대 → 동률이면 (DEV precision + reg_precision) 최대 → 동률이면 더 엄격한 가드(B3 > B2 > B1 > B0).
 자격 정책이 없으면 SELECTED = V3_B1(STEP29.1 엄격 가드 유지) 로 하고 보고서에 기록.

[Hard gates — 공식(HOLDOUT + 노출 + 약한 외부), 선택 정책 기준]
 G1  원문 보존: 모든 입력 RAW_PRESERVATION = 1.0
 G2  span offset 유효 = 1.0(모든 mention)
 G3  검사기 v6 정상 정답 오판 = 0(outputs/evaluator_validation.json, 사전 정의 세트)
 G4  검사기 v6 위험 연결 탐지 누락 = 0(같은 파일)
 G5  부정·해소 전파 안전 오류 = 0: HOLDOUT PROPAGATION_ERRORS + NEG_POSITIVE + 노출 G5(계약 NEG unsafe·42 MODEL_POSITIVE_FORBIDDEN·pilot absent→POSITIVE)
 G6  OTHER_PERSON 의 환자 현재 양성 자동 변환 = 0: HOLDOUT OTHER_POSITIVE + 노출 G6
 G7  신규 SILVER·하위 concept 모델 입력 eligible = 0(전 입력)
 G8  기존 연구 원본·제품 저장소 변경 0(outputs/protected_check.json)
 G9  검사기·데이터·채점·지표·판정 코드(prereg_gates.json)와 정책 코드·선택(policy_freeze.json) SHA 가 평가 시점과 같음
 G10 UNCERTAIN·UNKNOWN mention 사유·원문 보존(사유 없는 mention 0)
[Recovery — 공식 판정 기준(HOLDOUT, 같은 입력으로 S29·S291·선택 정책 재실행 비교)]
 R1 MULTI_SPAN_RETENTION(선택) ≥ S29
 R2 CONCEPT_PRECISION(선택) ≥ S29 − 0.01
 R3 CONCEPT_COVERAGE(선택) ≥ S29 − 0.02 AND ≥ S291
 R4 UNSUPPORTED_AUTO_LINK 수(선택) ≤ min(S29, S291)
 R5 NEGATION_SCOPE(선택) ≥ S291
 R6 PUNCTUATION_PAIR_CONSISTENCY(선택) ≥ 0.95 AND > S291
 R7 RESOLUTION_LINKING(선택) > S291 AND RESOLUTION_FALSE_LINK(선택) ≤ S291
 R8 CPU p95(선택, 단일 입력) ≤ 100 ms(outputs/latency.json)
[Development targets — 노출 자료의 STEP29 절대 수치(개발 목표, 공식 판정에는 STEP30 GO_FOR_RESEARCH 조건으로만 사용)]
 D1 pilot multi ≥ 0.675 · D2 REGRESSION168 precision ≥ 0.9333 · D3 coverage ≥ 0.625 · D4 pilot unsupported_auto ≤ 7(/28) · D5 pilot assertion ≥ 0.9371
[STEP29_2_RESULT] BLOCKED = 실행 불가 · REGRESSION = hard FAIL 또는 (R2 FAIL AND R3 FAIL) 또는 (R1 FAIL AND R5 FAIL) ·
 RECOVERY_PASS = hard 전부 + R1–R8 전부 · PARTIAL_IMPROVEMENT = hard 전부 + (R6 OR R7) + R1–R5 중 3개 이상 · NO_GAIN = 그 외
[STEP30_READINESS] GO_FOR_RESEARCH = RECOVERY_PASS AND D1–D5 전부 · CONDITIONAL_GO = hard 전부 AND R1 AND R2 AND R3 AND 결과 ≠ REGRESSION · NO_GO = 그 외
PRODUCTION_READY = NO · HUMAN_VERIFIED_GOLD = 0(고정). EXPLORATORY_POST_HOC 결과는 이 판정에 쓰지 않는다.
"""
from __future__ import annotations

CANDS = ("V3_B0", "V3_B1", "V3_B2", "V3_B3")
STRICT = {"V3_B3": 3, "V3_B2": 2, "V3_B1": 1, "V3_B0": 0}


def select_policy(dev: dict) -> tuple[str, list]:
    s29 = dev["S29"]["DEV"]["CONCEPT_PRECISION"]
    rows = []
    for p in CANDS:
        d, e = dev[p]["DEV"], dev[p]["EXPOSED"]
        elig = (d["PROPAGATION_ERRORS"] == 0 and d["NEG_POSITIVE"] == 0 and d["OTHER_POSITIVE"] == 0 and e["G5_exposed"] == 0 and e["G6_exposed"] == 0
                and e["G7_mentions"] == 0 and d["CONCEPT_PRECISION"] >= s29 - 0.01 and (e["reg_precision"] or 0) >= 0.9333 - 0.01)
        rows.append({"policy": p, "eligible": elig, "score_cov": round(d["CONCEPT_COVERAGE"] + e["reg_coverage"], 4),
                     "score_prec": round(d["CONCEPT_PRECISION"] + (e["reg_precision"] or 0), 4), "strict": STRICT[p]})
    ok = [r for r in rows if r["eligible"]]
    if not ok:
        return "V3_B1", rows
    ok.sort(key=lambda r: (r["score_cov"], r["score_prec"], r["strict"]), reverse=True)
    return ok[0]["policy"], rows


def verdict(M: dict, sel: str, evalv: dict, protect: dict, latency: dict, prereg: dict) -> dict:
    H = {p: M[p]["HOLDOUT"] for p in M}
    X = M[sel]["EXPOSED"]
    W = M[sel]["WEAK"]
    hs = H[sel]
    raw_all = hs["RAW_PRESERVATION"] == 1.0 and M[sel]["DEV"]["RAW_PRESERVATION"] == 1.0 and X["raw_ok"] == X["inputs"] and W["raw_ok"] == W["inputs"]
    off_all = hs["OFFSET_VALID"] == 1.0 and M[sel]["DEV"]["OFFSET_VALID"] == 1.0 and X["offset_ok"] == X["mentions"]
    g5 = hs["PROPAGATION_ERRORS"] + hs["NEG_POSITIVE"] + X["G5_exposed"]
    g6 = hs["OTHER_POSITIVE"] + X["G6_exposed"]
    g7 = X["G7_mentions"] + W["G7_mentions"]
    g10 = X["G10_mentions"] + W["G10_mentions"]
    hard = {"G1": raw_all, "G2": off_all, "G3": evalv["EVALUATOR_FALSE_POSITIVES"] == 0, "G4": evalv["EVALUATOR_FALSE_NEGATIVES"] == 0, "G5": g5 == 0,
            "G6": g6 == 0, "G7": g7 == 0, "G8": protect.get("G8") == "PASS", "G9": all(v for k, v in prereg.items() if k != "selected_policy"), "G10": g10 == 0}
    s29, s291 = H["S29"], H["S291"]
    p95 = latency["single_input_cpu"][sel]["p95_ms"]
    R = {"R1": hs["MULTI_SPAN_RETENTION"] >= s29["MULTI_SPAN_RETENTION"],
         "R2": hs["CONCEPT_PRECISION"] >= s29["CONCEPT_PRECISION"] - 0.01,
         "R3": hs["CONCEPT_COVERAGE"] >= s29["CONCEPT_COVERAGE"] - 0.02 and hs["CONCEPT_COVERAGE"] >= s291["CONCEPT_COVERAGE"],
         "R4": hs["unsupported_auto"] <= min(s29["unsupported_auto"], s291["unsupported_auto"]),
         "R5": hs["NEGATION_SCOPE"] >= s291["NEGATION_SCOPE"],
         "R6": hs["PUNCTUATION_PAIR_CONSISTENCY"] >= 0.95 and hs["PUNCTUATION_PAIR_CONSISTENCY"] > s291["PUNCTUATION_PAIR_CONSISTENCY"],
         "R7": hs["RESOLUTION_LINKING"] > s291["RESOLUTION_LINKING"] and hs["RESOLUTION_FALSE_LINK"] <= s291["RESOLUTION_FALSE_LINK"],
         "R8": p95 <= 100}
    D = {"D1": X["pilot_multi_retention"] >= 0.675, "D2": (X["reg_precision"] or 0) >= 0.9333, "D3": X["reg_coverage"] >= 0.625,
         "D4": X["pilot_unsupported_auto"] <= 7, "D5": X["pilot_assertion_agreement"] >= 0.9371}
    hp = all(hard.values())
    if not hp or (not R["R2"] and not R["R3"]) or (not R["R1"] and not R["R5"]):
        res = "REGRESSION"
    elif all(R.values()):
        res = "RECOVERY_PASS"
    elif (R["R6"] or R["R7"]) and sum(R[k] for k in ("R1", "R2", "R3", "R4", "R5")) >= 3:
        res = "PARTIAL_IMPROVEMENT"
    else:
        res = "NO_GAIN"
    if res == "RECOVERY_PASS" and all(D.values()):
        s30 = "GO_FOR_RESEARCH"
    elif hp and R["R1"] and R["R2"] and R["R3"] and res != "REGRESSION":
        s30 = "CONDITIONAL_GO"
    else:
        s30 = "NO_GO"
    pf = lambda d: {k: "PASS" if v else "FAIL" for k, v in d.items()}  # noqa: E731
    return {"STEP29_2_RESULT": res, "STEP30_READINESS": s30, "PRODUCTION_READY": "NO", "HUMAN_VERIFIED_GOLD": 0, "SELECTED_POLICY": sel,
            "hard_gates": pf(hard), "recovery_official": pf(R), "development_targets": pf(D),
            "gate_inputs": {"G5_total": g5, "G6_total": g6, "G7_total": g7, "G10_total": g10, "p95_ms": p95}}
