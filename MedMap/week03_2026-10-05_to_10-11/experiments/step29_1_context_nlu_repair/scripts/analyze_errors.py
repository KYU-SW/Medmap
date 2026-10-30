"""STEP29.1 오류 분석(평가 후 — 규칙 변경 없음): eval_errors.csv → 종류별 파일 + §18 답(수치 생성).
출력: outputs/{negation_analysis.csv, temporality_analysis.csv, multi_span_analysis.csv, unsupported_auto_link_analysis.csv, mapping_error_analysis.csv, error_summary.json}"""
import collections
import json

import s291_common as S


def main():
    E = S.read_csv(S.OUT / "eval_errors.csv")
    M = S.load_json(S.OUT / "eval_summary.json")["metrics"]
    val = S.load_json(S.OUT / "evaluator_validation.json")
    lat = S.load_json(S.OUT / "latency.json")
    sel = lambda f: [e for e in E if e["level"] in ("P1", "P5") and f(e)]  # noqa: E731
    S.wcsv(S.OUT / "negation_analysis.csv", sel(lambda e: e["type"] in ("NEGATION", "FORBIDDEN_ASSERTION", "MODEL_POSITIVE_FORBIDDEN")))
    S.wcsv(S.OUT / "temporality_analysis.csv", sel(lambda e: e["type"] in ("TEMPORALITY", "ONSET", "FREQUENCY", "SCOPE")))
    S.wcsv(S.OUT / "multi_span_analysis.csv", sel(lambda e: e["type"] in ("NOT_EXTRACTED", "MISSED_OR_UNMAPPED", "OVER_SPLIT", "ROLE", "UNEXPECTED_SYMPTOM")))
    S.wcsv(S.OUT / "unsupported_auto_link_analysis.csv", sel(lambda e: e["set"] == "PILOT_UNSUPPORTED"))
    S.wcsv(S.OUT / "mapping_error_analysis.csv", sel(lambda e: e["type"] in ("WRONG_NORMALIZATION", "WRONG_CONCEPT", "MUST_NOT_AUTO") or e["type"].startswith("V5_")))
    P, P1, P0 = M["P5"], M["P1"], M["P0"]
    c5 = collections.Counter((e["set"], e["type"]) for e in E if e["level"] == "P5")
    top = lambda s, t, n=5: [f"{e['text']}→{e.get('got', '')}" for e in E if e["level"] == "P5" and e["set"] == s and e["type"] == t][:n]  # noqa: E731
    un5 = [e["text"] + "→" + e["got"] for e in E if e["level"] == "P5" and e["set"] == "PILOT_UNSUPPORTED"]
    md = (f"- P5 오류(세트:종류): {json.dumps({f'{a}:{b}': v for (a, b), v in sorted(c5.items())}, ensure_ascii=False)}\n"
          f"- 전향적 실패 예(P5): NOT_EXTRACTED {top('PROS', 'NOT_EXTRACTED')} · WRONG_NORMALIZATION {top('PROS', 'WRONG_NORMALIZATION')} · NEGATION {top('PROS', 'NEGATION')} · "
          f"TEMPORALITY {top('PROS', 'TEMPORALITY')} · EXPERIENCER {top('PROS', 'EXPERIENCER')}\n"
          f"- pilot 연결 불가 발화 자동 연결(P5): {un5}\n- pilot 부정 불일치(P5): {top('PILOT', 'NEGATION', 8)}\n- pilot 시점 불일치(P5): {top('PILOT', 'TEMPORALITY', 8)}")
    pros = lambda L: f"{M[L]['pros_total_pass']}/{M[L]['pros_n']}"  # noqa: E731
    ans = f"""1. STEP29 공식 위반 2건: 검사기 v4 가 문장 전체에 규칙을 적용해, 다른 구문의 '고혈압'·'기침약' 때문에 올바른 '머리 통증'·'기침' 연결을 위반으로 셈(같은 혼합 정상 문장에서 v4 오판 {val['v4_sentence_level_false_positive_on_MIXED_OK']}, v5 0).
2. 검사기 v5: 정상 mention {val['known_correct_mentions']} 오판 {val['evaluator_false_positive']} · 위험 사례 {val['known_bad']} 누락 {val['evaluator_false_negative']}. STEP29 NLU 출력 위반 입력 v4 {P1['v4_violation_inputs']} → v5 {M['P2']['v5_violation_inputs']}(검사기 효과). P5 위반 입력 {P['v5_violation_inputs']}.
3. '입맛은 괜찮아요': 새 계약 EVAL 통과 P1 {P1['new_EVAL_pass']} → P5 {P['new_EVAL_pass']}/{P['new_EVAL_n']}(세부 negation_analysis.csv). 이 사례는 STEP29 평가에서 본 것 → 독립 개선 근거 아님.
4. '괜찮다' 과잉 부정: '이제 괜찮아요'·'검사 결과는 괜찮아요'·'괜찮지 않아요' 등 새 계약 EVAL 포함 — P5 EVAL {P['new_EVAL_pass']}/{P['new_EVAL_n']}. 전향적 세트에는 평가형 문장이 없음(검증 범위 한계).
5. 과거·해소: 새 계약 RES P1 {P1['new_RES_pass']} → P5 {P['new_RES_pass']}/{P['new_RES_n']} · 전향적 T4_RESOLVED P1 {P1.get('pros_T4_RESOLVED_pass')} → P5 {P.get('pros_T4_RESOLVED_pass')}/{P.get('pros_T4_RESOLVED_n')} · 대조 T4_CONTROL(해소 아님) P5 {P.get('pros_T4_CONTROL_pass')}/{P.get('pros_T4_CONTROL_n')} · pilot 시점 일치 {P1['pilot_temporality_agreement']} → {P['pilot_temporality_agreement']}.
6. 다중 증상: pilot 다중 보존 {P1['pilot_multi_retention']} → {P['pilot_multi_retention']} · 전향적 T2_BOTH P5 {P.get('pros_T2_BOTH_pass')}/{P.get('pros_T2_BOTH_n')} · 과분할(새 계약) {P['new_over_split']} · 중복 구간 mention {P['duplicate_span_mentions']}.
7. 혼합 질환·약물·증상: 새 계약 MIX P5 {P['new_MIX_pass']}/{P['new_MIX_n']} · 전향적 T6_DRUG_SYM {P.get('pros_T6_DRUG_SYM_pass')}/{P.get('pros_T6_DRUG_SYM_n')} · T6_DIS_SYM {P.get('pros_T6_DIS_SYM_pass')}/{P.get('pros_T6_DIS_SYM_n')} · T6_DRUG_ONLY {P.get('pros_T6_DRUG_ONLY_pass')}/{P.get('pros_T6_DRUG_ONLY_n')} · T6_DIS_ONLY {P.get('pros_T6_DIS_ONLY_pass')}/{P.get('pros_T6_DIS_ONLY_n')}.
8. 남은 P5 매핑 오류: pilot 잘못된 concept mention P0 {P0['pilot_wrong_concept_mentions']} · P1 {P1['pilot_wrong_concept_mentions']} · P5 {P['pilot_wrong_concept_mentions']} · STEP29 계약 실패 P5 {P['step29_contracts_failed']}(P5 원본 한계: '토하' 모호·생략 부위·중간 부사절).
9. 연결 불가 발화 자동 연결: P1 {P1['pilot_unsupported_auto']} → P5 {P['pilot_unsupported_auto']}/{P['pilot_unsupported_n']}(STEP29 정의) · 그중 환자 양성 모델 입력 P1 {P1['pilot_unsupported_patient_positive']} → P5 {P['pilot_unsupported_patient_positive']}. 남은 것의 다수는 가족 증상을 OTHER_PERSON 으로 올바로 추출한 경우(라벨 정의 차이).
10. 정밀도·coverage: REGRESSION168 precision {P1['reg_precision']} → {P['reg_precision']} · coverage {P1['reg_coverage']} → {P['reg_coverage']}(P0 {P0['reg_precision']}/{P0['reg_coverage']}).
11. 77·SILVER 출처·지원 상태: 신규·하위·SILVER 단독 모델 입력 {P['G7_silver_or_new_model_input']} · STEP28.7 SILVER 근거 필드 유지(evidence_level·isolation_status).
12. 독립 Gold 없음: 결론은 '노출 회귀·사전 계약·템플릿 합성(전향적 {pros('P1')} → {pros('P5')})에서 규칙이 의도대로 동작'까지. 실제 환자 발화 정확도·임상 안전성은 말할 수 없음(HUMAN_VERIFIED_GOLD 0).
13. STEP30: 판정은 step29_1_verdict.json — 연구용 제품 연결 '설계' 시작 여부만 판단, 실제 연동은 하지 않음."""
    S.dump_json(S.OUT / "error_summary.json", {"counts_P5": {f"{a}:{b}": v for (a, b), v in c5.items()}, "report_md": md, "answers_md": ans})
    print(md)


if __name__ == "__main__":
    main()
