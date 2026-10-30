"""STEP29 오류 분석(평가 후 — 규칙 변경 없음). eval_errors.csv 를 종류별 파일로 나누고 §23 답 문장을 수치로 생성.
출력: outputs/{span_error_analysis.csv, negation_analysis.csv, temporality_analysis.csv, experiencer_analysis.csv, normalization_analysis.csv, error_summary.json}"""
import collections
import json

import s29_common as S


def main():
    E = S.read_csv(S.OUT / "eval_errors.csv")
    M = S.load_json(S.OUT / "eval_summary.json")["metrics"]
    meta = S.load_json(S.OUT / "metamorphic_results.json")
    lat = S.load_json(S.OUT / "latency.json")
    P, P0 = M["NLU_P5"], M["NLU_P0"]
    pick = lambda types: [e for e in E if e["level"] in ("NLU_P0", "NLU_P5") and e["type"] in types]  # noqa: E731
    S.wcsv(S.OUT / "span_error_analysis.csv", pick({"NOT_EXTRACTED", "MISSED_OR_UNMAPPED", "ROLE", "ATTRIBUTE"}))
    S.wcsv(S.OUT / "negation_analysis.csv", pick({"NEGATION"}))
    S.wcsv(S.OUT / "temporality_analysis.csv", pick({"TEMPORALITY", "ONSET", "FREQUENCY", "SCOPE"}))
    S.wcsv(S.OUT / "experiencer_analysis.csv", pick({"EXPERIENCER"}))
    S.wcsv(S.OUT / "normalization_analysis.csv", pick({"WRONG_NORMALIZATION", "WRONG_CONCEPT", "MUST_NOT_AUTO"}))
    c5 = collections.Counter((e["set"], e["type"]) for e in E if e["level"] == "NLU_P5")
    top = lambda t, n=6: [f"{e['text']}({e.get('gold', '')}→{e.get('got', '')})" for e in E if e["level"] == "NLU_P5" and e["type"] == t][:n]  # noqa: E731
    md = (f"- NLU_P5 오류 수(세트, 종류): {json.dumps({f'{a}:{b}': v for (a, b), v in sorted(c5.items())}, ensure_ascii=False)}\n"
          f"- 1 추출·연결 실패(pilot): {top('MISSED_OR_UNMAPPED')}\n- 2 잘못된 concept(pilot): {top('WRONG_CONCEPT')}\n- 3 부정: {top('NEGATION')}\n"
          f"- 4 시점: {top('TEMPORALITY')}\n- 5 주체: {top('EXPERIENCER')}\n- 계약 미추출: {top('NOT_EXTRACTED')} · 계약 정규화: {top('WRONG_NORMALIZATION')}")
    ans = f"""1. 여러 증상 추출: pilot_gold 다중 발화 mention 회수율 NLU_P5 {P['pilot_multi_retention']}(NLU_P0 {P0['pilot_multi_retention']}, 분모 {P['pilot_multi_n']}) · 전체 회수율 {P['pilot_retention']}(P0 {P0['pilot_retention']}).
2. 첫 증상만 선택: NLU 는 절·단위마다 P5 를 따로 호출해 mention 을 모두 반환(STEP28.8 의 '첫 auto' 는 지표 정의였음). 계약 다중 사례 결과 = 계약 실패 사례 {P['contract_failed_cases']}/68 중 MULTI 범주는 eval_errors.csv.
3. 부정 범위: pilot assertion 일치 {P['pilot_assertion_agreement']}(P0 {P0['pilot_assertion_agreement']}, 대응 mention {P['pilot_matched']}) · 계약 {P['contract_assertion_pass']} · 부정 안전 오류(G4) {P['G4_neg_safety_errors']}.
4. 과거·현재: pilot 시점 일치 {P['pilot_temporality_agreement']}(P0 {P0['pilot_temporality_agreement']} — P0 는 시점 미분석) · 계약 {P['contract_temporality_pass']}.
5. 환자·가족: pilot 주체 일치 {P['pilot_experiencer_agreement']}(P0 {P0['pilot_experiencer_agreement']}) · 계약 {P['contract_experiencer_pass']} · 타인 안전 오류(G5) {P['G5_other_safety_errors']}.
6. 의성어·양상: mention attributes 로 원문 보존(계약 ATTRIBUTE 오류는 eval_errors). 정규화 손실 충돌은 IDEOPHONE_MISMATCH 가드로 UNCERTAIN 처리(P5 nkey 는 그대로).
7. P5 오매핑 영향: pilot 잘못된 concept mention NLU_P5 {P['pilot_wrong_concept_mentions']}(P0 {P0['pilot_wrong_concept_mentions']}) · REGRESSION168 precision {P['reg_precision']}/coverage {P['reg_coverage']}(P0 {P0['reg_precision']}/{P0['reg_coverage']}, STEP28.8 0.9451/0.5417).
8. 77 + 신규 SILVER 동시 처리: 같은 문장 mention 별로 기록(SILVER 근거·등급·격리 상태 보존) · 신규·SILVER 단독의 모델 입력 표시(G6) {P['G6_silver_or_new_model_input']}.
9. 부정·가족 증상의 모델 입력 위험: 사전 정의 안전 회귀에서 G4 {P['G4_neg_safety_errors']} · G5 {P['G5_other_safety_errors']}(제한된 회귀 기준 — 임상 안전성 보장 아님). 주체 생략은 PATIENT 가정(ASSUMED_INTAKE_DEFAULT 표시).
10. 처리 못 하는 유형: 생략된 대상('지금은 안 아파요' 의 부위) · 중간 부사절('찌르듯이') · P5 모호('토하') · 연결 불가 발화 auto {P['pilot_unsupported_auto']}/{P['pilot_unsupported_n']} · 세부는 오류 분석.
11. 오프라인: LLM·네트워크 없음, CPU p95 {lat['single_input_cpu']['NLU_P5']['p95_ms']} ms · peak RSS {lat['peak_rss_mib']} MiB.
12. STEP30 전 필요: 사람 검증 Gold(부정·시점·주체 포함) · 주체 기본값 정책(가정 PATIENT) 결정 · P5 nkey 손실·B4 오연결 처리 · PatientState 입력 규칙(PAST·POSSIBLE 처리) 설계 · 실제 음성 전사 문장 평가."""
    S.dump_json(S.OUT / "error_summary.json", {"counts_P5": {f"{a}:{b}": v for (a, b), v in c5.items()}, "report_md": md, "answers_md": ans, "metamorphic": meta["summary"]})
    print(md)


if __name__ == "__main__":
    main()
