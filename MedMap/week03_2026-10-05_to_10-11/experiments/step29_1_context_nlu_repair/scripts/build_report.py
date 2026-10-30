"""STEP29.1 판정 + 보고서 + manifest. 숫자는 outputs/ 에서 읽는다(손으로 쓰지 않음).

[정책] P0 = STEP28.8 P5 단독 · P1 = STEP29 NLU(NLU_P5) + 검사기 v4(문장 단위, STEP29 공식 방식) · P2 = P1 출력 + 검사기 v5(검사기만 변경 — NLU 개선 아님) ·
 P3 = P2 + 평가형 부정·문맥 assertion · P4 = P3 + 해소·시점 범위 · P5 = P4 + P5 의미 충돌·미지원 입력 가드. 판정 대상 = P5.
[게이트 — 평가(evaluate_nlu) 실행 전 고정, 2026-10-11. 연구용 엔지니어링 기준 — 임상 안전성 검증 아님]
Hard
 G1  원문 보존 100%(전 입력, source_text 그대로 · raw_span == source_text[start:end])
 G2  span offset 유효성 100%(전 mention)
 G3  검사기 v5 가 알려진 올바른 mention 을 위반으로 판정한 수 = 0(evaluator_validation)
 G4  검사기 v5 가 사전 정의 위험 오연결을 놓친 수 = 0(evaluator_validation)
 G5  부정·해소·가정 증상의 양성 확정 0: STEP29 계약 safety=NEG + 새 계약 safety=NEG 의 '추출됐는데 PRESENT·모델 POSITIVE' + pilot absent 대응 mention 의 같은 경우
     + 새 계약 no_model_positive 문장의 모델 POSITIVE mention
 G6  가족 증상의 환자 양성 확정 0: STEP29 계약 safety=OTHER + 새 계약 safety=OTHER + pilot 타인 대응 mention 중 PATIENT·모델 eligible
 G7  신규·하위·SILVER 단독 mention 의 모델 입력 eligible 0(전 입력)
 G8  기존 연구 원본(STEP20–29, P5·STEP29 코드 포함)·제품 저장소 무변경(protect_check)
 G9  검사기 v5·계약·전향적 합성 SHA 가 사전 기록(prereg)과 같고 동결 코드로 평가
 G10 UNCERTAIN·UNKNOWN mention 은 raw_span·사유 보존
Soft
 S1 pilot 다중 발화 mention 보존 ≥ 0.675(STEP29)       S2 REGRESSION168 precision(첫 EXISTING) ≥ 0.9333
 S3 REGRESSION168 coverage ≥ 0.625 − 0.05              S4 pilot should_link False 발화 중 EXISTING mention 있는 발화 ≤ 8(STEP29 정의)
 S5 평가형 부정: 새 계약 EVAL 통과 수 P5 > P1          S6 해소·시점: 새 계약 RES 통과 수 P5 > P1 AND 전향적 T4_RESOLVED 통과 수 P5 > P1
 S7 CPU p95 ≤ 100 ms
[판정 STEP29_1_RESULT] BLOCKED = 실행 불가 · REGRESSION = hard FAIL 또는 (S1 FAIL AND S2 FAIL) · CONTEXT_NLU_IMPROVED = hard 전부 + soft 전부 ·
 PARTIAL_IMPROVEMENT = hard PASS + (S4·S5·S6 중 하나 이상 PASS) · NO_GAIN = 그 외
[STEP30_READINESS] GO_FOR_RESEARCH = CONTEXT_NLU_IMPROVED · CONDITIONAL_GO = hard PASS AND S1 AND S3 AND (S5 OR S6) · NO_GO = 그 외
PRODUCTION_READY = NO · HUMAN_VERIFIED_GOLD = 0(고정). 데이터 구분: EXPOSED_REGRESSION(STEP29 계약 68·pilot 274·REGRESSION168) · PRE_REGISTERED_CONTRACT(새 계약 42, 개발 사용) ·
 PROSPECTIVE_SYNTHETIC(231, 동결 후 첫 실행, 템플릿 슬롯 정답) · WEAK_EXTERNAL(SILVER442·WEAKNON903).
"""
from __future__ import annotations

import json

import s291_common as S


def main():
    ev = S.load_json(S.OUT / "eval_summary.json")
    M = ev["metrics"]
    val = S.load_json(S.OUT / "evaluator_validation.json")
    lat = S.load_json(S.OUT / "latency.json")
    prot = S.load_json(S.OUT / "protected_check.json") if (S.OUT / "protected_check.json").exists() else {"G10": "NOT_RUN"}
    pre = S.load_json(S.DATA / "prereg.json")
    P, P1 = M["P5"], M["P1"]
    p95 = lat["single_input_cpu"]["P5"]["p95_ms"]
    g = {"G1": P["raw_ok_rate"] == 1.0, "G2": P["offset_valid_rate"] == 1.0, "G3": val["evaluator_false_positive"] == 0, "G4": val["evaluator_false_negative"] == 0,
         "G5": P["G5_neg_resolved_hypothetical_positive"] == 0, "G6": P["G6_other_person_positive"] == 0, "G7": P["G7_silver_or_new_model_input"] == 0,
         "G8": prot.get("G10") == "PASS", "G9": ev["prereg_ok"], "G10": P["G10_uncertain_without_reason"] == 0}
    s = {"S1": (P["pilot_multi_retention"] or 0) >= 0.675, "S2": (P["reg_precision"] or 0) >= 0.9333, "S3": P["reg_coverage"] >= 0.625 - 0.05,
         "S4": P["pilot_unsupported_auto"] <= 8, "S5": P["new_EVAL_pass"] > P1["new_EVAL_pass"],
         "S6": P["new_RES_pass"] > P1["new_RES_pass"] and P["pros_T4_RESOLVED_pass"] > P1["pros_T4_RESOLVED_pass"], "S7": p95 <= 100}
    hard = all(g.values())
    if not hard or (not s["S1"] and not s["S2"]):
        verdict = "REGRESSION"
    elif all(s.values()):
        verdict = "CONTEXT_NLU_IMPROVED"
    elif s["S4"] or s["S5"] or s["S6"]:
        verdict = "PARTIAL_IMPROVEMENT"
    else:
        verdict = "NO_GAIN"
    step30 = "GO_FOR_RESEARCH" if verdict == "CONTEXT_NLU_IMPROVED" else "CONDITIONAL_GO" if hard and s["S1"] and s["S3"] and (s["S5"] or s["S6"]) else "NO_GO"
    fin = {"STEP29_1_RESULT": verdict, "EVALUATOR_V5": val["EVALUATOR_V5"], "hard_gates": {k: "PASS" if v else "FAIL" for k, v in g.items()},
           "soft_gates": {k: "PASS" if v else "FAIL" for k, v in s.items()},
           "MULTI_SPAN_RETENTION": P["pilot_multi_retention"], "NEGATION_SCOPE": P["pilot_assertion_agreement"],
           "EVALUATIVE_NEGATION": f"새 계약 EVAL {P['new_EVAL_pass']}/{P['new_EVAL_n']}(P1 {P1['new_EVAL_pass']})",
           "TEMPORALITY": f"pilot {P['pilot_temporality_agreement']} · 새 계약 RES {P['new_RES_pass']}/{P['new_RES_n']}(P1 {P1['new_RES_pass']}) · 전향적 T4_RESOLVED {P['pros_T4_RESOLVED_pass']}/{P['pros_T4_RESOLVED_n']}(P1 {P1['pros_T4_RESOLVED_pass']})",
           "EXPERIENCER": P["pilot_experiencer_agreement"], "CONCEPT_PRECISION": P["reg_precision"], "CONCEPT_COVERAGE": P["reg_coverage"],
           "UNSUPPORTED_AUTO_LINK": f"{P['pilot_unsupported_auto']}/{P['pilot_unsupported_n']}(STEP29 정의) · 환자 양성 모델 입력 {P['pilot_unsupported_patient_positive']}",
           "SEMANTIC_VIOLATIONS": P["v5_violation_inputs"], "RAW_PRESERVATION": P["raw_ok_rate"], "CPU_P95_MS": p95, "STEP30_READINESS": step30,
           "PRODUCTION_READY": "NO", "HUMAN_VERIFIED_GOLD": 0, "rules": __doc__}
    S.dump_json(S.OUT / "step29_1_verdict.json", fin)
    pols = ("P0", "P1", "P2", "P3", "P4", "P5")
    keys = [k for k in M["P5"] if not isinstance(M["P5"][k], (dict, list))]
    tbl = "| 지표 | " + " | ".join(pols) + " |\n|---|" + "---|" * len(pols) + "\n" + "\n".join(f"| {k} | " + " | ".join(str(M[p].get(k)) for p in pols) + " |" for k in keys)
    ea = S.load_json(S.OUT / "error_summary.json") if (S.OUT / "error_summary.json").exists() else {}
    ut = S.load_json(S.OUT / "unit_tests.json")["by_file"] if (S.OUT / "unit_tests.json").exists() else {}
    utxt = " · ".join(f"{k} {v['tests'] - v['failures'] - v['errors']}/{v['tests']}" for k, v in sorted(ut.items()))
    md = f"""# STEP29.1 — Context-Aware Clinical NLU Repair(연구용)

- **STEP30_READINESS = {step30}** · STEP29_1_RESULT = **{verdict}** · EVALUATOR_V5 = {val['EVALUATOR_V5']} · PRODUCTION_READY = NO · HUMAN_VERIFIED_GOLD = 0
- hard {json.dumps(fin['hard_gates'], ensure_ascii=False)} · soft {json.dumps(fin['soft_gates'], ensure_ascii=False)}
- 고정 순서: 새 계약 42(SHA `{pre['contracts_sha256'][:16]}…`) → 전향적 합성 231(SHA `{pre['prospective_sha256'][:16]}…`, NLU 미실행) → 검사기 v5(SHA `{val['evaluator_sha256'][:16]}…`) → 게이트(이 파일) → 구현(새 계약으로만 개발) → 코드 동결 → 평가 1회.

## 1. 최종 보고

| 항목 | 값 |
|---|---|
""" + "\n".join(f"| {k} | {v} |" for k, v in fin.items() if k not in ("rules", "hard_gates", "soft_gates")) + f"""

## 2. 검사기 효과(같은 NLU 출력 — STEP29 NLU)

- 검사기 정답 대조: 정상 mention {val['known_correct_mentions']} 중 v5 오판 {val['evaluator_false_positive']} · 위험 사례 {val['known_bad']} 중 v5 누락 {val['evaluator_false_negative']} · 같은 혼합 정상 문장에 v4(문장 단위) 오판 {val['v4_sentence_level_false_positive_on_MIXED_OK']}.
- STEP29 NLU 출력의 구별 위반 입력: v4(문장 단위) {M['P1']['v4_violation_inputs']} → v5(mention 단위) {M['P2']['v5_violation_inputs']}. 이 차이는 검사기 효과이며 NLU 개선이 아니다.

## 3. 정책 비교(검사기 v5 기준 NLU 효과는 P2→P5, P0 는 참고)

{tbl}

## 4. 오류 분석

{ea.get('report_md', '- 없음')}

## 5. 단위 테스트

- {utxt}

## 6. 답(§18)

{ea.get('answers_md', '- 없음')}
"""
    (S.DOCS / "step29_1_report.md").write_text(md, encoding="utf-8")
    man = {"step": "STEP29.1", "verdict": verdict, "step30": step30, "scripts": {p.name: S.sha256(p) for p in sorted((S.STEP / "scripts").glob("*.py"))},
           "tests": {p.name: S.sha256(p) for p in sorted((S.STEP / "tests").glob("*.py"))},
           "outputs": {str(p.relative_to(S.STEP)): S.sha256(p) for p in sorted(list(S.OUT.glob("*")) + list(S.DATA.glob("*"))) if p.is_file() and p.name != "manifest.json"},
           "llm_calls": 0, "downloads": 0}
    S.dump_json(S.OUT / "manifest.json", man)
    print(S.dumps({k: v for k, v in fin.items() if k != "rules"}))


if __name__ == "__main__":
    main()
