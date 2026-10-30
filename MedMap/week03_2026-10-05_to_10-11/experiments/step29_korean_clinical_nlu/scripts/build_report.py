"""STEP29 판정 + 보고서 + manifest. 숫자는 outputs/ 에서 읽는다.

[게이트 — 평가(evaluate_nlu) 실행 전 고정, 2026-10-11. 연구용 엔지니어링 기준 — 임상 안전성 보장 아님. 판정 대상 = NLU_P5]
Hard
 G1 원문 보존 100%(source_text 그대로 · 모든 mention raw_span == source_text[span_start:span_end])
 G2 span offset 유효성 100%(0 ≤ start < end ≤ len, 구간이 원문과 일치, 문장 범위 안)
 G3 알려진 핵심 의미 구별 위반 0(검사기 v4, 전 입력, 자동 EXISTING concept + 표시 후보)
 G4 부정 안전 회귀: 계약 safety=NEG mention + pilot_gold absent mention 중 '추출됐는데 PRESENT 이고 모델 입력 POSITIVE' 0
 G5 타인 안전 회귀: 계약 safety=OTHER mention + pilot_gold 타인 mention 중 '추출됐는데 PATIENT 이고 모델 입력 eligible' 0
 G6 신규·하위·SILVER 단독 mention 의 모델 입력 eligible 0
 G7 P5 원본(STEP28.8)·기존 산출물·제품 저장소 무변경(protect_check)
 G8 검사기 v4 EVALUATOR_FIXED=PASS 이고 SHA 가 평가 시점과 같음 · 계약 파일 SHA 가 사전 기록과 같음
 G9 UNCERTAIN·UNKNOWN mention 은 raw_span·reason 이 비어 있지 않음
Soft
 S1 단일 증상(REGRESSION168, 첫 EXISTING mention): NLU_P5 precision ≥ STEP28.8 P5(0.9451) − 0.02 AND coverage ≥ 0.5417 − 0.05
 S2 다중 증상 보존(pilot_gold 중 77 concept mention ≥2 인 발화의 mention 회수율): NLU_P5 > NLU_P0
 S3 pilot_gold 일치 mention 기준: assertion 일치 ≥ 0.85 · 시점(historical ↔ PAST/RESOLVED) 일치 ≥ 0.80 · 주체 일치 ≥ 0.90
 S4 SILVER442 mention UNKNOWN+UNCERTAIN 비율 ≤ NLU_P0 + 0.10
 S5 CPU p95 ≤ 100 ms
[판정 STEP29_RESULT]
 BLOCKED            : 파이프라인 실행 불가
 REGRESSION         : hard FAIL, 또는 (S1 FAIL AND S2 FAIL)
 NLU_FEASIBLE       : hard 전부 + soft 전부 PASS
 PARTIAL_IMPROVEMENT: hard PASS + (S2 PASS 또는 S3 중 하나 이상 PASS)
 NO_GAIN            : 그 외
[STEP30_READINESS] GO_FOR_RESEARCH = NLU_FEASIBLE · CONDITIONAL_GO = hard PASS AND S1 PASS AND (S2 또는 S3 일부 PASS) · NO_GO = 그 외
PRODUCTION_READY = NO(고정). HUMAN_VERIFIED_GOLD = 0. pilot_gold = 합성(Claude 작성)·반복 노출, 계약 = 개발용(규칙 작성에 사용).
"""
from __future__ import annotations

import json

import s29_common as S


def main():
    ev = S.load_json(S.OUT / "eval_summary.json")
    M = ev["metrics"]
    val = S.load_json(S.OUT / "evaluator_v4_validation.json")
    lat = S.load_json(S.OUT / "latency.json")
    prot = S.load_json(S.OUT / "protected_check.json") if (S.OUT / "protected_check.json").exists() else {"G10": "NOT_RUN"}
    pre = S.load_json(S.DATA / "prereg.json")
    meta = S.load_json(S.OUT / "metamorphic_results.json")
    ut = S.load_json(S.OUT / "unit_tests.json") if (S.OUT / "unit_tests.json").exists() else {"by_file": {}}
    P, P0 = M["NLU_P5"], M["NLU_P0"]
    p95 = lat["single_input_cpu"]["NLU_P5"]["p95_ms"]
    g = {"G1": P["G1_raw_ok_rate"] == 1.0, "G2": P["G2_offset_valid_rate"] == 1.0, "G3": P["G3_semantic_violation_inputs"] == 0,
         "G4": P["G4_neg_safety_errors"] == 0, "G5": P["G5_other_safety_errors"] == 0, "G6": P["G6_silver_or_new_model_input"] == 0,
         "G7": prot.get("G10") == "PASS",
         "G8": val["EVALUATOR_FIXED"] == "PASS" and val["evaluator_sha256"] == ev["evaluator_sha256"] and pre["contracts_sha256"] == ev["contracts_sha256"],
         "G9": P["G9_uncertain_without_reason"] == 0}
    s3 = {"assertion": (P["pilot_assertion_agreement"] or 0) >= 0.85, "temporality": (P["pilot_temporality_agreement"] or 0) >= 0.80,
          "experiencer": (P["pilot_experiencer_agreement"] or 0) >= 0.90}
    s = {"S1": (P["reg_precision"] or 0) >= 0.9451 - 0.02 and P["reg_coverage"] >= 0.5417 - 0.05,
         "S2": P["pilot_multi_retention"] > P0["pilot_multi_retention"], "S3": all(s3.values()),
         "S4": P["silver_unknown_uncertain_rate"] <= P0["silver_unknown_uncertain_rate"] + 0.10, "S5": p95 <= 100}
    hard = all(g.values())
    if not hard or (not s["S1"] and not s["S2"]):
        verdict = "REGRESSION"
    elif all(s.values()):
        verdict = "NLU_FEASIBLE"
    elif s["S2"] or any(s3.values()):
        verdict = "PARTIAL_IMPROVEMENT"
    else:
        verdict = "NO_GAIN"
    step30 = "GO_FOR_RESEARCH" if verdict == "NLU_FEASIBLE" else "CONDITIONAL_GO" if hard and s["S1"] and (s["S2"] or any(s3.values())) else "NO_GO"
    fin = {"STEP29_RESULT": verdict, "hard_gates": {k: "PASS" if v else "FAIL" for k, v in g.items()}, "soft_gates": {k: "PASS" if v else "FAIL" for k, v in s.items()},
           "S3_detail": {k: "PASS" if v else "FAIL" for k, v in s3.items()},
           "MULTI_SPAN_RETENTION": f"{P['pilot_multi_retention']}(NLU_P0 {P0['pilot_multi_retention']}, pilot_gold 다중 발화 mention {P['pilot_multi_n']})",
           "SPAN_BOUNDARY_VALIDITY": P["G2_offset_valid_rate"],
           "NEGATION_SCOPE_RESULT": f"pilot assertion 일치 {P['pilot_assertion_agreement']}(n {P['pilot_matched']}) · 계약 assertion 통과 {P['contract_assertion_pass']}",
           "TEMPORALITY_RESULT": f"pilot 시점 일치 {P['pilot_temporality_agreement']} · 계약 시점 통과 {P['contract_temporality_pass']}",
           "EXPERIENCER_RESULT": f"pilot 주체 일치 {P['pilot_experiencer_agreement']} · 계약 주체 통과 {P['contract_experiencer_pass']}",
           "CONCEPT_MAPPING_RESULT": f"REGRESSION168 precision {P['reg_precision']} · coverage {P['reg_coverage']} · pilot 잘못된 concept mention {P['pilot_wrong_concept_mentions']}",
           "SEMANTIC_VIOLATIONS": P["G3_semantic_violation_inputs"], "UNSUPPORTED_CONCEPT_PRESERVATION": f"should_link False 발화 auto {P['pilot_unsupported_auto']}/{P['pilot_unsupported_n']} · 원문 보존 {P['G1_raw_ok_rate']}",
           "RAW_PRESERVATION": P["G1_raw_ok_rate"], "CPU_P95_MS": p95, "STEP30_READINESS": step30, "PRODUCTION_READY": "NO", "HUMAN_VERIFIED_GOLD": 0,
           "rules": __doc__}
    S.dump_json(S.OUT / "step29_verdict.json", fin)
    pols = ("NLU_P0", "NLU_P1", "NLU_P2", "NLU_P3", "NLU_P4", "NLU_P5")
    keys = [k for k in M["NLU_P5"] if not isinstance(M["NLU_P5"][k], (dict, list))]
    tbl = "| 지표 | " + " | ".join(pols) + " |\n|---|" + "---|" * len(pols) + "\n" + "\n".join(f"| {k} | " + " | ".join(str(M[p].get(k)) for p in pols) + " |" for k in keys)
    ea = S.load_json(S.OUT / "error_summary.json") if (S.OUT / "error_summary.json").exists() else {}
    utxt = " · ".join(f"{k} {v['tests'] - v['failures'] - v['errors']}/{v['tests']}" for k, v in sorted(ut["by_file"].items()))
    md = f"""# STEP29 — Korean Clinical NLU(연구용)

- **STEP30_READINESS = {step30}** · STEP29_RESULT = **{verdict}** · PRODUCTION_READY = NO · HUMAN_VERIFIED_GOLD = 0
- hard: {json.dumps(fin['hard_gates'], ensure_ascii=False)} · soft: {json.dumps(fin['soft_gates'], ensure_ascii=False)} · S3 {json.dumps(fin['S3_detail'], ensure_ascii=False)}
- 규칙 고정 순서: 계약 68(SHA `{pre['contracts_sha256'][:16]}…`) → 검사기 v4(SHA `{val['evaluator_sha256'][:16]}…`) → 게이트(이 파일) → 구현(계약으로만 개발) → 코드 동결(`data/prereg.json`) → 평가 1회.
- 데이터: pilot_gold 274(합성·Claude 작성·STEP21–28.8 반복 노출, 부정·시점·주체 라벨) · REGRESSION168(그 부분집합) · SILVER442·WEAKNON903(약한 라벨) · 계약 68·metamorphic(개발용, 규칙 작성자가 작성). 사람 검증 Gold 없음 → 임상 정확도 아님.

## 1. 최종 보고

| 항목 | 값 |
|---|---|
""" + "\n".join(f"| {k} | {v} |" for k, v in fin.items() if k not in ("rules", "hard_gates", "soft_gates", "S3_detail")) + f"""

## 2. 정책 비교(NLU_P0 = STEP28.8 P5 단독 · P1 구문 분해 · P2 +부정 · P3 +시점 · P4 +주체 · P5 +의미 충돌 검증·SILVER)

{tbl}

## 3. 오류 분석(별도 집계)

{ea.get('report_md', '- 없음')}

## 4. Metamorphic(규칙 일관성 — 임상 정확도 아님)

- {json.dumps(meta.get('summary', {}), ensure_ascii=False)}

## 5. 단위 테스트

- {utxt}

## 6. 답(§23)

{ea.get('answers_md', '- analyze_errors 미실행')}
"""
    (S.DOCS / "step29_nlu_report.md").write_text(md, encoding="utf-8")
    man = {"step": "STEP29", "verdict": verdict, "step30": step30, "scripts": {p.name: S.sha256(p) for p in sorted((S.STEP / "scripts").glob("*.py"))},
           "tests": {p.name: S.sha256(p) for p in sorted((S.STEP / "tests").glob("*.py"))},
           "outputs": {str(p.relative_to(S.STEP)): S.sha256(p) for p in sorted(list(S.OUT.glob("*")) + list(S.DATA.glob("*"))) if p.is_file() and p.name != "manifest.json"},
           "llm_calls": 0, "downloads": 0}
    S.dump_json(S.OUT / "manifest.json", man)
    print(S.dumps({k: v for k, v in fin.items() if k != "rules"}))


if __name__ == "__main__":
    main()
