"""STEP28.8 판정 + 보고서 + manifest. 숫자는 outputs/·data/ 에서 읽는다(손으로 쓰지 않음).

[게이트 — 정책 평가(evaluate_policies) 실행 전 고정, 2026-10-11. 연구용 엔지니어링 기준이며 임상 승인 아님. 판정 대상 정책 = P5]
 G1  P5 원문 보존율 = 1.0
 G2  P5 신규·하위 id 의 77 curated id 충돌 0 · 77 밖 canonical 반환 0
 G3  검사기 v3 정답 오판 0(evaluator_validation EVALUATOR_FIXED = PASS)
 G3b P5 의미 구별 위반 입력 0(v3, 전 세트)
 G4  P5 비증상 자동 연결(WEAKNON903) ≤ P2(STEP28.7 정책 D, 같은 조건 재실행)
 G5  P5 REGRESSION168 coverage ≥ P2 − 0.05
 G6  P5 REGRESSION168 auto precision(첫 auto) ≥ P2 — 별도 보고: G6_STRICT(≥ 0.95) 달성 여부·P2 대비 개선량·coverage 변화
 G7  STEP28.6·28.7 SILVER 근거·상태 보존(기존 산출물 SHA 무변경 = protect_check) + P5 격리 FAIL 양성 0
 G8  P5 CPU p95 ≤ 50 ms(목표 측정)
 G9  신규·하위·SILVER 단독 결과의 49질환 모델 사용 가능 표시 0
 G10 기존 연구 산출물·제품 저장소 무변경(protect_check)
 HELD_PRECEDENCE = PASS ⇔ P5 보류 행 원문 입력의 auto 0 AND tests/test_held_precedence 전부 통과
[판정 STEP28_8_RESULT]
 hard = G1·G2·G3·G3b·G7·G9·G10
 REGRESSION        : hard FAIL, 또는 (P5 비증상 위험 > P2 AND P5 precision < P2)
 QUALITY_IMPROVED  : G1–G10 전부 PASS + HELD PASS + P5 precision > P2 + P5 부분 문자열 오매칭 0
 PARTIAL_IMPROVEMENT: hard PASS + (P5 가 P2 대비 precision↑ · 비증상 위험↓ · 부분 문자열 오매칭↓ · 구별 위반↓ 중 하나 이상)
 NO_GAIN           : 그 외
[STEP29_READINESS]
 GO_FOR_RESEARCH : QUALITY_IMPROVED AND G6_STRICT
 CONDITIONAL_GO  : hard PASS AND HELD PASS AND G5 PASS
 NO_GO           : 그 외
PRODUCTION_READY = NO(고정). HUMAN_VERIFIED_GOLD = 0.
"""
from __future__ import annotations

import collections
import json

import s288_common as S


def main():
    ev = S.load_json(S.OUT / "eval_summary.json")["metrics"]
    val = S.load_json(S.OUT / "evaluator_validation.json")
    lat = S.load_json(S.OUT / "latency.json")
    prot = S.load_json(S.OUT / "protected_check.json") if (S.OUT / "protected_check.json").exists() else {"G10": "NOT_RUN"}
    ut = S.load_json(S.OUT / "unit_tests.json") if (S.OUT / "unit_tests.json").exists() else {"by_file": {}}
    ea = S.load_json(S.OUT / "error_summary.json") if (S.OUT / "error_summary.json").exists() else {}
    P5, P2, P0 = ev["P5"], ev["P2"], ev["P0"]
    p95 = lat["single_input_cpu"]["P5"]["p95_ms"]
    held_tests = ut["by_file"].get("test_held_precedence", {})
    g = {"G1": P5["RAW_preservation"] == 1.0,
         "G2": P5["G2_id_collision"] == 0 and P5["G2_canonical_outside_77"] == 0,
         "G3": val["EVALUATOR_FIXED"] == "PASS",
         "G3b": P5["V1_semantic_violation_inputs"] == 0,
         "G4": P5["W1_weaknon_auto_link"] <= P2["W1_weaknon_auto_link"],
         "G5": P5["R1_regression_coverage"] >= P2["R1_regression_coverage"] - 0.05,
         "G6": (P5["R2_regression_precision(first_auto)"] or 0) >= (P2["R2_regression_precision(first_auto)"] or 0),
         "G7": prot.get("G10") == "PASS" and P5["ISO_fail_positive"] == 0,
         "G8": p95 <= 50,
         "G9": P5["G9_new_or_subtype_usable"] == 0 and P5["G9_silver_only_usable"] == 0,
         "G10": prot.get("G10") == "PASS"}
    g6_strict = (P5["R2_regression_precision(first_auto)"] or 0) >= 0.95
    held = P5["HELD_auto_inputs"] == 0 and held_tests.get("failures", 1) == 0 and held_tests.get("errors", 1) == 0 and held_tests.get("tests", 0) > 0
    hard = all(g[k] for k in ("G1", "G2", "G3", "G3b", "G7", "G9", "G10"))
    better = {"precision": (P5["R2_regression_precision(first_auto)"] or 0) > (P2["R2_regression_precision(first_auto)"] or 0),
              "weaknon": P5["W1_weaknon_auto_link"] < P2["W1_weaknon_auto_link"],
              "substring": P5["SFM_substring_false_match_spans"] < P2["SFM_substring_false_match_spans"],
              "violations": P5["V1_semantic_violation_inputs"] < P2["V1_semantic_violation_inputs"]}
    if not hard or (P5["W1_weaknon_auto_link"] > P2["W1_weaknon_auto_link"] and (P5["R2_regression_precision(first_auto)"] or 0) < (P2["R2_regression_precision(first_auto)"] or 0)):
        verdict = "REGRESSION"
    elif all(g.values()) and held and better["precision"] and P5["SFM_substring_false_match_spans"] == 0:
        verdict = "QUALITY_IMPROVED"
    elif any(better.values()):
        verdict = "PARTIAL_IMPROVEMENT"
    else:
        verdict = "NO_GAIN"
    step29 = "GO_FOR_RESEARCH" if verdict == "QUALITY_IMPROVED" and g6_strict else "CONDITIONAL_GO" if hard and held and g["G5"] else "NO_GO"
    fin = {"STEP28_8_RESULT": verdict, "EVALUATOR_FIXED": val["EVALUATOR_FIXED"], "gates": {k: "PASS" if v else "FAIL" for k, v in g.items()},
           "G6_STRICT_0_95": "PASS" if g6_strict else "FAIL", "better_than_P2": better,
           "SUBSTRING_FALSE_MATCH": P5["SFM_substring_false_match_spans"], "SUBSTRING_FALSE_MATCH_P0_P2": [P0["SFM_substring_false_match_spans"], P2["SFM_substring_false_match_spans"]],
           "WEAK_NEGATIVE_AUTO_MAP": f"{P5['W1_weaknon_auto_link']}/{P5['W1_n']}", "SUPPORTED_AUTO_PRECISION": P5["R2_regression_precision(first_auto)"],
           "SUPPORTED_AUTO_COVERAGE": P5["R1_regression_coverage"], "SEMANTIC_DISTINCTION_VIOLATIONS": P5["V1_semantic_violation_inputs"],
           "WRONG_CANDIDATE_DISPLAY": P5["V2_wrong_candidate_display_inputs"], "HELD_PRECEDENCE": "PASS" if held else "FAIL",
           "RAW_PRESERVATION": P5["RAW_preservation"], "CPU_P95_MS": p95, "STEP29_READINESS": step29, "PRODUCTION_READY": "NO", "HUMAN_VERIFIED_GOLD": 0,
           "rules": __doc__}
    S.dump_json(S.OUT / "step28_8_verdict.json", fin)

    P = ("P0", "P1", "P2", "P3", "P4", "P5", "REF_A")
    keys = [k for k in ("R1_regression_coverage", "R2_regression_precision(first_auto)", "R2_n_correct", "R1_n_auto", "R3_regression_span_precision",
                        "X1_extra_span_precision", "X2_extra_primary_coverage", "X3_should_not_link_auto", "W1_weaknon_auto_link", "V1_semantic_violation_inputs",
                        "V2_wrong_candidate_display_inputs", "SFM_substring_false_match_spans", "SUP_supported12", "HELD_auto_inputs", "EXISTING_CANONICAL",
                        "EXISTING_COMPOSITE", "EXISTING_SUBTYPE", "NEWU_units", "NEWU_distinct_ids", "UNKNOWN", "UNCERTAIN", "NON", "U_unknown_uncertain_rate",
                        "RAW_preservation")]
    tbl = "| 지표 | " + " | ".join(P) + " |\n|---|" + "---|" * len(P) + "\n" + "\n".join(
        f"| {k} | " + " | ".join(str(ev[p].get(k, "—")) for p in P) + " |" for k in keys)
    lt = lat["single_input_cpu"]
    utxt = " · ".join(f"{k} {v['tests'] - v['failures'] - v['errors']}/{v['tests']}" for k, v in sorted(ut["by_file"].items()))
    vres = val["results"]
    xp = S.load_json(S.OUT / "exploratory_p5x.json") if (S.OUT / "exploratory_p5x.json").exists() else None
    if xp:
        x, o = xp["P5x"], xp["P5_official"]
        xmd = (f"- 남은 부분 문자열 오매칭 {P5['SFM_substring_false_match_spans']} 은 대부분 STEP28.5 술어 정규화 키(nkey) 일치: 의성어·부사·위치 명사를 버려 다른 의미를 같은 키로 만든다"
               f"('속이 화끈화끈해요'(gold heartburn) ↔ '속이 울렁울렁해요'(nausea), '가슴이 벌렁벌렁해요' ↔ '가슴이 콩닥콩닥해요'). 경계 일치에서도 부사가 빠져 '심장이 덜컥거립니다' → [심장] 만 남아 '심장 부분' → palpitations.\n"
               f"- P5x(nkey 는 경계 정렬될 때만 + 핵심 형태소 50% 미만 항목 제외, 모델 재실행): precision {o['R2_regression_precision(first_auto)']} → {x['R2_regression_precision(first_auto)']} · "
               f"coverage {o['R1_regression_coverage']} → {x['R1_regression_coverage']} · 비증상 {o['W1_weaknon_auto_link']} → {x['W1_weaknon_auto_link']} · SUPPORTED12 {o['SUP_supported12']} → {x['SUP_supported12']} · "
               f"PILOT_EXTRA106 span precision {o['X1_extra_span_precision']} → {x['X1_extra_span_precision']}. → nkey 를 빼면 B4·다른 경로가 대신 잡아 오답이 늘어남(예 {x['regression_wrong'][:3]}). 채택 안 함.\n"
               f"- 검사기 v3 의 빈틈: '토할 것 같아요' → vomiting(정답 nausea)은 양태 예외 때문에 위반으로 잡히지 않는다(P5x 에서 발생). 다음 검사기 버전에서 사전 보완 필요.\n"
               f"- G4 FAIL(P5 {P5['W1_weaknon_auto_link']} > P2 {P2['W1_weaknon_auto_link']})의 주원인: '흉 통' 분리 문제를 고쳐 흉통 6 이 다시 pain 으로 연결됨 — 두 LLM 작성자 모두 증상형으로 쓴 실제 증상어(약한 비증상 라벨 쪽 의심). 규칙상 FAIL 유지.")
    else:
        xmd = "- 없음"
    md = f"""# STEP28.8 — Korean Retrieval Repair & Evaluation Gate

- **STEP29 진입: {step29}** · STEP28_8_RESULT = **{verdict}** · PRODUCTION_READY = NO · HUMAN_VERIFIED_GOLD = 0
- 게이트(P5): {json.dumps(fin['gates'], ensure_ascii=False)} · G6_STRICT(≥0.95) = {fin['G6_STRICT_0_95']} · HELD_PRECEDENCE = {fin['HELD_PRECEDENCE']}
- P2(STEP28.7 D 재실행) 대비 개선: {json.dumps(better, ensure_ascii=False)}
- 규칙 고정: 검사기 `scripts/evaluator.py`(v3, SHA `{val['evaluator_sha256'][:16]}…`) · 매칭 `scripts/repair_korean_matching.py` · 정책 `scripts/policies.py` · 게이트 `scripts/build_report.py` — 모두 평가 실행 전.
- 데이터 대부분이 반복 노출된 개발·회귀 자료. 덜 노출된 보조 Gold = PILOT_EXTRA106(합성·Claude 작성). 사람 검증 임상 Gold 없음.

## 1. 최종 보고

| 항목 | 값 |
|---|---|
| STEP28_8_RESULT | {verdict} |
| EVALUATOR_FIXED | {val['EVALUATOR_FIXED']} |
| SUBSTRING_FALSE_MATCH | {fin['SUBSTRING_FALSE_MATCH']}(P0 {fin['SUBSTRING_FALSE_MATCH_P0_P2'][0]} · P2 {fin['SUBSTRING_FALSE_MATCH_P0_P2'][1]}, 전 세트 auto 구문) |
| WEAK_NEGATIVE_AUTO_MAP | {fin['WEAK_NEGATIVE_AUTO_MAP']}(P2 {P2['W1_weaknon_auto_link']}/903 · P0 {P0['W1_weaknon_auto_link']}/903) |
| SUPPORTED_AUTO_PRECISION | {fin['SUPPORTED_AUTO_PRECISION']}(REGRESSION168 첫 auto; P2 {P2['R2_regression_precision(first_auto)']} · STEP27 B4 {ev['REF_A']['R2_regression_precision(first_auto)']}) |
| SUPPORTED_AUTO_COVERAGE | {fin['SUPPORTED_AUTO_COVERAGE']}(P2 {P2['R1_regression_coverage']} · STEP27 B4 {ev['REF_A']['R1_regression_coverage']}) |
| SEMANTIC_DISTINCTION_VIOLATIONS | {fin['SEMANTIC_DISTINCTION_VIOLATIONS']}(v3, 전 세트; P2 {P2['V1_semantic_violation_inputs']}) |
| WRONG_CANDIDATE_DISPLAY | {fin['WRONG_CANDIDATE_DISPLAY']} |
| HELD_PRECEDENCE | {fin['HELD_PRECEDENCE']}(보류 원문 입력 auto P5 {P5['HELD_auto_inputs']}/{P5['HELD_inputs']} · P2 {P2['HELD_auto_inputs']}) |
| RAW_PRESERVATION | {fin['RAW_PRESERVATION']} |
| CPU_P95 | {p95} ms(p50 {lt['P5']['p50_ms']} ms, n {lt['P5']['n']}) · peak RSS {lat['peak_rss_mib']} MiB |
| STEP29_READINESS | {step29} |
| PRODUCTION_READY | NO |

## 2. 검사기(§2)

- 정답 쌍 {vres['v3']['gold_pairs']} 개(파일럿 Gold 274·STEP23 학습·STEP21 사전·T20/C57)에 대한 정답 오판: v1(STEP28.7 공식) {vres['v1_step28_7_official']['gold_pairs_flagged(false_violation)']} · v2 {vres['v2_step28_7_exploratory']['gold_pairs_flagged(false_violation)']} · **v3 {vres['v3']['gold_pairs_flagged(false_violation)']}**.
- 필수 사례: 위반 탐지 누락 {len(vres['v3']['must_flag_missed'])} · 정상 사례 오판 {len(vres['v3']['must_pass_flagged'])}. 단위 테스트: {utxt}.
- v3 은 정답 대조로 정했다(양태 '…할 것 같다·…싶다' 예외, 구토감·헛구역 예외, 오바이트 구토 단서). 같은 정답 세트로 검증했으므로 검사기 일반화 보장은 아님.

## 3. 정책 비교(§8) — 단위: 입력(R·X·W·V·HELD), 구문(EXISTING·UNKNOWN 등, SILVER442)

{tbl}

- REGRESSION168 = 합성 Gold(노출) · PILOT_EXTRA106 = 합성 Gold(덜 노출, X1–X3) · WEAKNON903·SILVER442 = 약한 라벨 — 하나의 정확도로 합치지 않음.
- REF_A = STEP27 POLICY_D(B4) 참고값(REGRESSION168·PILOT_EXTRA106 만 실행).

## 4. 오류 분석(§4·§6)

{ea.get('report_md', '- analyze_errors 미실행')}

## 5. 답(§14)

1. 검사기: {val['EVALUATOR_FIXED']} — 정답 오판 v1 {vres['v1_step28_7_official']['gold_pairs_flagged(false_violation)']} → v3 {vres['v3']['gold_pairs_flagged(false_violation)']}.
2. 부분 문자열 오매핑(auto 구문): P0 {P0['SFM_substring_false_match_spans']} · P2 {P2['SFM_substring_false_match_spans']} → P5 {P5['SFM_substring_false_match_spans']}.
3. 기존 증상 자동 처리(REGRESSION168): precision P2 {P2['R2_regression_precision(first_auto)']} → P5 {P5['R2_regression_precision(first_auto)']}(0.95 {fin['G6_STRICT_0_95']}) · coverage P2 {P2['R1_regression_coverage']} → P5 {P5['R1_regression_coverage']} · 덜 노출 PILOT_EXTRA106 span precision P2 {P2.get('X1_extra_span_precision')} → P5 {P5.get('X1_extra_span_precision')}, primary coverage {P2.get('X2_extra_primary_coverage')} → {P5.get('X2_extra_primary_coverage')} · SUPPORTED12 P2 {P2['SUP_supported12']}/12 → P5 {P5['SUP_supported12']}/12.
4. 비증상 자동 연결(WEAKNON903): P0 {P0['W1_weaknon_auto_link']} · P2 {P2['W1_weaknon_auto_link']} → P5 {P5['W1_weaknon_auto_link']}(약한 라벨 — 일부는 실제 증상어, §4).
5. 보류 우선: {fin['HELD_PRECEDENCE']} — 보류 원문 입력 auto P2 {P2['HELD_auto_inputs']} → P5 {P5['HELD_auto_inputs']}(무기력·묽은변 포함, 부정 구문은 차단 대신 확인 경로).
6. 구별(코피≠객혈·토혈 · 구토≠오심 · 떨림≠오한): P5 위반 {P5['V1_semantic_violation_inputs']} · 표시 후보 위반 {P5['V2_wrong_candidate_display_inputs']}(probe 결과 `outputs/error_analysis.csv`).
7. 신규 SILVER 개념의 모델 입력: P5 신규·하위 usable {P5['G9_new_or_subtype_usable']} · SILVER 단독 usable {P5['G9_silver_only_usable']}.
8. 남은 대표 오류: §4.
9. STEP29: **{step29}**.

## 6. 사후 발견·탐색(EXPLORATORY_POST_HOC — 공식 판정 아님, 1차 평가 결과를 본 뒤 작성)

{xmd}

## 7. 변경 기록(공개)

- 검사기 v3 은 정답 세트 대조 중 2회 수정(양태 '싶' 추가 포함) 후 정책 평가 전에 SHA 고정. 매칭·정책·게이트 규칙은 평가 후 변경 없음.
- 평가 후 추가: `scripts/evaluate_exploratory_p5x.py`(탐색, 공식 아님) · 보고서 사후 절. 테스트 파일은 평가와 같은 실행에서 처음 실행.
"""
    (S.DOCS / "step28_8_report.md").write_text(md, encoding="utf-8")
    man = {"step": "STEP28.8", "verdict": verdict, "step29": step29, "scripts": {p.name: S.sha256(p) for p in sorted((S.STEP / "scripts").glob("*.py"))},
           "tests": {p.name: S.sha256(p) for p in sorted((S.STEP / "tests").glob("*.py"))}, "evaluator_sha256": val["evaluator_sha256"],
           "outputs": {str(p.relative_to(S.STEP)): S.sha256(p) for p in sorted(list(S.OUT.glob("*")) + list(S.DATA.glob("*"))) if p.is_file() and p.name != "manifest.json"},
           "llm_calls": 0, "downloads": 0}
    S.dump_json(S.OUT / "manifest.json", man)
    print(S.dumps({k: v for k, v in fin.items() if k != "rules"}))


if __name__ == "__main__":
    main()
