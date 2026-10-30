"""STEP28.7 판정 + 보고서 + manifest. 숫자는 outputs/·data/ 파일에서 읽는다(손으로 쓰지 않음).

[엔지니어링 게이트 — 평가(evaluate_mapping_safety) 실행 전 고정, 2026-10-11. 연구용 품질 게이트이며 임상 안전성 승인 조건이 아님]
 G1  D 원문 보존율 = 1.0(전 세트·probe)
 G2  D 결과의 신규·하위 ontology id 가 77 curated id 와 충돌 0 · 77 밖 canonical 반환 0
 G3  D 의미 구별 위반 입력 0(전 세트·probe, 자동 concept + 표시 후보)
 G4  D 비증상 자동 연결 위험(WEAKNON903) ≤ 8(STEP28.6 보고값)
 G4b 유용성: D SILVER442 결정률(EXISTING*/SUBTYPE/NEW/NON 구문 비율) ≥ C − 0.05 (대부분을 UNKNOWN 으로 보내 G4 를 맞추는 정책 차단)
 G5  STEP28.6 G2+ 고유 concept 33 전부 분류·사유 기록 · 보류·반려는 사유 필수(근거 없는 삭제 0)
 G6  REGRESSION168: D coverage ≥ A(STEP27 B4) coverage − 0.05 AND D auto precision ≥ 0.95
 G7  D CPU p95 ≤ 50 ms(목표 측정)
 G8  신규·하위 결과의 49질환 모델 사용 가능 표시 0 · 정제 대응표 usable_by_disease_model True 0
 G9  격리 FAIL 행이 양성 수락(ACCEPT_EXISTING·SYNONYM·SUBTYPE·NEW)으로 쓰인 결과 0 · 정제표 ISOLATION_FAIL 양성 ACCEPT 0 · LEVEL_4 0
 G10 기존 연구 산출물(exp/step20–28.6 · 격리 작업 폴더 out) SHA 무변경 · 제품 저장소 HEAD·status 무변경
[판정 STEP28_7_RESULT — 같은 시점 고정]
 hard = G1·G2·G3·G8·G9·G10
 REGRESSION          : hard 하나라도 FAIL, 또는 (D 비증상 위험 > C AND D 구별 위반 > C)
 QUALITY_GATE_PASS   : G1–G10 + G4b 전부 PASS
 PARTIAL_IMPROVEMENT : hard 전부 PASS + 안전 지표(비증상 위험·구별 위반·잘못된 후보 표시) 중 하나 이상이 C(STEP28.6)보다 엄격히 낮음 + 나머지 게이트 일부 FAIL
 NO_GAIN             : 그 외(hard PASS, C 대비 안전 지표 개선 없음, 일부 FAIL)
 STEP29 진입: hard 전부 PASS → CONDITIONAL_GO(연구 프로토타입 입력용, 부정·시점·주체 미해결) · 아니면 NO_GO.
PRODUCTION_READY = NO(고정). HUMAN_VERIFIED_GOLD = 0(인간 검토 미수행).
"""
from __future__ import annotations

import collections
import json

import s287_common as S


def main():
    ev = S.load_json(S.OUT / "eval_summary.json")["metrics"]
    reg = S.load_json(S.OUT / "regression_metrics.json")["metrics"]
    lat = S.load_json(S.OUT / "latency.json")
    ca = S.load_json(S.OUT / "concept_audit.json")
    cr = S.load_json(S.OUT / "count_reconciliation.json")
    iso = S.load_json(S.OUT / "isolation_analysis.json")
    rep = S.load_json(S.OUT / "reproduction_check.json")
    prot = S.load_json(S.OUT / "protected_check.json") if (S.OUT / "protected_check.json").exists() else {"G10": "NOT_RUN"}
    clean = S.read_csv(S.DATA / "cleaned_silver_mappings.csv")
    audited = S.read_csv(S.DATA / "audited_concepts.csv")
    na = S.read_csv(S.OUT / "non_symptom_error_analysis.csv")
    cs = S.read_csv(S.OUT / "candidate_safety_analysis.csv")
    D, C, A = ev["D_STEP28_7"], ev["C_STEP28_6"], ev["A_STEP27_B4"]
    pos_acc = ("ACCEPT_EXISTING", "ACCEPT_EXISTING_SYNONYM", "ACCEPT_SUBTYPE", "ACCEPT_NEW_CANDIDATE")
    in34 = [r for r in audited if r["in_reported_34"] == "True"]
    g = {
        "G1": D["13_raw_preservation"] == 1.0,
        "G2": D["G2_new_id_collision_with_77"] == 0 and D["G2_canonical_outside_77"] == 0,
        "G3": D["11_semantic_violation_inputs"] == 0,
        "G4": D["7_weaknon_auto_link_risk"] <= 8,
        "G4b": D["silver_decided_rate(units: EXISTING*/SUBTYPE/NEW/NON)"] >= C["silver_decided_rate(units: EXISTING*/SUBTYPE/NEW/NON)"] - 0.05,
        "G5": len(in34) == 33 and all(r["classification_reason"] for r in audited) and all(r["hold_or_reject_reason"] for r in audited if r["keep_decision"] in ("HELD", "REJECTED")),
        "G6": D["8_supported_auto_coverage"] >= A["8_supported_auto_coverage"] - 0.05 and (D["9_regression_auto_precision"] or 0) >= 0.95,
        "G7": lat["single_input_cpu"]["D_STEP28_7"]["p95_ms"] <= 50,
        "G8": D["G8_new_or_subtype_usable_by_model"] == 0 and not any(r["usable_by_disease_model"] == "True" for r in clean),
        "G9": D["G9_isolation_fail_positive"] == 0 and not any(r["isolation_status"] == "ISOLATION_FAIL" and r["mapping_decision"] in pos_acc for r in clean)
              and not any(r["evidence_level"] == "LEVEL_4" for r in clean),
        "G10": prot.get("G10") == "PASS",
    }
    hard = all(g[k] for k in ("G1", "G2", "G3", "G8", "G9", "G10"))
    better = {"weaknon_risk": D["7_weaknon_auto_link_risk"] < C["7_weaknon_auto_link_risk"],
              "semantic_violations": D["11_semantic_violation_inputs"] < C["11_semantic_violation_inputs"],
              "wrong_display": D["10_wrong_candidate_display_inputs"] < C["10_wrong_candidate_display_inputs"]}
    worse_both = D["7_weaknon_auto_link_risk"] > C["7_weaknon_auto_link_risk"] and D["11_semantic_violation_inputs"] > C["11_semantic_violation_inputs"]
    if not hard or worse_both:
        verdict = "REGRESSION"
    elif all(g.values()):
        verdict = "QUALITY_GATE_PASS"
    elif any(better.values()):
        verdict = "PARTIAL_IMPROVEMENT"
    else:
        verdict = "NO_GAIN"
    step29 = "CONDITIONAL_GO" if hard else "NO_GO"
    dec = collections.Counter(r["mapping_decision"] for r in clean)
    lv = collections.Counter(r["evidence_level"] for r in clean)
    silver_passed = sum(1 for r in audited if r["keep_decision"] in ("KEEP_NEW_CANDIDATE", "MERGE_AS_EXISTING_RELATION"))
    final = {"STEP28_7_RESULT": verdict, "gates": {k: "PASS" if v else "FAIL" for k, v in g.items()}, "safety_better_than_C": better,
             "ORIGINAL_NEW_CANDIDATES": 34, "ORIGINAL_NEW_CANDIDATES_DISTINCT": cr["distinct_G2plus_union"],
             "INDEPENDENT_NEW_CONCEPTS": ca["INDEPENDENT_NEW_CONCEPTS"], "INDEPENDENT_NEW_CONCEPT_FAMILIES": ca["independent_new_concept_families(tremor 하위 묶음)"],
             "EXISTING_SYNONYMS": ca["EXISTING_SYNONYMS"] + ca["EXISTING_COMPOSITES"], "EXISTING_SUBTYPES": ca["EXISTING_SUBTYPES"],
             "HELD_CANDIDATES": ca["HELD_CANDIDATES"], "REJECTED_CANDIDATES": ca["REJECTED_CANDIDATES"],
             "ISOLATION_UNVERIFIED_CANDIDATES": sum(1 for r in audited if "ISOLATION_UNVERIFIED" in r["isolation_flags"]),
             "ISOLATION_FAIL_CANDIDATES": ca["ISOLATION_FAIL_ONLY_CANDIDATES"] + ca["ISOLATION_MIXED_CANDIDATES"],
             "WEAK_NEGATIVE_AUTO_MAP": f"{D['7_weaknon_auto_link_risk']}/{D['7_n']}",
             "SUPPORTED_AUTO_COVERAGE": D["8_supported_auto_coverage"], "REGRESSION_AUTO_PRECISION": D["9_regression_auto_precision"],
             "WRONG_CANDIDATE_DISPLAY": D["10_wrong_candidate_display_inputs"], "SEMANTIC_DISTINCTION_VIOLATIONS": D["11_semantic_violation_inputs"],
             "RAW_PRESERVATION": D["13_raw_preservation"], "CPU_P95_MS": lat["single_input_cpu"]["D_STEP28_7"]["p95_ms"],
             "SILVER_CONCEPTS_PASSING_CHECKS": silver_passed, "HUMAN_VERIFIED_GOLD": 0, "PRODUCTION_READY": "NO", "STEP29_ENTRY": step29,
             "rules": __doc__}
    S.dump_json(S.OUT / "step28_7_verdict.json", final)

    P = ("A_STEP27_B4", "B_STEP28", "C_STEP28_6", "D_STEP28_7", "D_NO_TABLE", "D_LOO")
    keys = ["silver_units", "1_EXISTING_CANONICAL", "2_EXISTING_COMPOSITE", "3_NEW_INDEPENDENT_ontology_ids", "3b_NEW_units", "4_NEW_SUBTYPE_ontology_ids",
            "4b_SUBTYPE_units", "5_SILVER_SYNONYM_units", "6_UNCERTAIN_units", "UNKNOWN_units", "NON_units", "7_weaknon_auto_link_risk",
            "8_supported_auto_coverage", "9_regression_auto_precision", "10_wrong_candidate_display_inputs", "11_semantic_violation_inputs",
            "12_unknown_uncertain_rate(silver units)", "silver_decided_rate(units: EXISTING*/SUBTYPE/NEW/NON)", "13_raw_preservation"]
    tbl = "| 지표 | " + " | ".join(P) + " |\n|---|" + "---|" * len(P) + "\n" + "\n".join(f"| {k} | " + " | ".join(str(ev[p][k]) for p in P) + " |" for k in keys)
    # [변경 기록 — 보고서 집계만] non_symptom_error_analysis.csv 는 C·D 위험 입력의 합집합을 두 정책 모두 행으로 담는다 → 정책별 '위험 행'만 센다
    risky = lambda r: any(s in ("EXISTING_CANONICAL", "EXISTING_COMPOSITE", "EXISTING_SUBTYPE", "NEW_ONTOLOGY_CANDIDATE") for s in r["statuses"].split(";"))  # noqa: E731
    naC = collections.Counter(r["cause"] for r in na if r["policy"] == "C_STEP28_6" and risky(r))
    naD = collections.Counter(r["cause"] for r in na if r["policy"] == "D_STEP28_7" and risky(r))
    c8 = sorted({r["input"] for r in na if r["policy"] == "C_STEP28_6" and risky(r)})
    d_risk = [(r["input"], r["canonicals"] or r["ontology_ids"], r["evidence"], r["cause"]) for r in na if r["policy"] == "D_STEP28_7" and risky(r)]
    xv = S.load_json(S.OUT / "exploratory_v2.json") if (S.OUT / "exploratory_v2.json").exists() else None
    probe = {}
    for r in cs:
        probe.setdefault(r["input"], {})[r["policy"]] = (r["statuses"], r["canonicals"] or r["ontology_ids"], r["display"], r["violations_auto"] or r["violations_display"])
    ptab = "| 입력 | " + " | ".join(("A_STEP27_B4", "B_STEP28", "C_STEP28_6", "D_STEP28_7", "D_LOO")) + " | 제품 매퍼(read-only) |\n|---|---|---|---|---|---|---|\n"
    for t, d in probe.items():
        cells = [f"{d[p][0]}:{d[p][1]}{' ⚠' + d[p][3] if d[p][3] else ''}" for p in ("A_STEP27_B4", "B_STEP28", "C_STEP28_6", "D_STEP28_7", "D_LOO")]
        m = d.get("PRODUCT_MAPPER(read-only, 연구용 탐지)", ("", "", "", ""))
        ptab += f"| {t} | " + " | ".join(cells) + f" | {m[0]}{' ⚠' + m[3] if m[3] else ''} |\n"
    cls_tab = "| class | 39 전체 | 34 집합(고유 33) |\n|---|---|---|\n" + "\n".join(
        f"| {k} | {ca['by_class(all 39)'][k]} | {ca['by_class(34-set distinct 33)'][k]} |" for k in ca["by_class(all 39)"])
    ind = [r for r in audited if r["final_class"] == "D"]
    sub = [r for r in audited if r["final_class"] == "C"]
    held = [r for r in audited if r["keep_decision"] in ("HELD", "REJECTED")]
    fl = lambda rs: ", ".join(f"{r['concept_id']}({r['korean_expressions'].split(' | ')[0]})" for r in rs)  # noqa: E731
    iso_s = iso["sessions"]
    n_chg = sum(len(v["rows_changed_by_self_revision"]) for v in iso_s.values())
    regA, regD = reg["A_STEP27_B4"]["ALL"], reg["D_STEP28_7"]["ALL"]
    lt = lat["single_input_cpu"]
    ok = lambda b: "예" if b else "아니오"  # noqa: E731
    if xv:
        pp = xv["per_policy"]
        xv_md = (f"- **공식 판정 REGRESSION 의 원인 = 검사기 결함**: 사전 고정 구별 검사기에 STEP28.6 규칙에 없던 '토할·토해'(구토)와 동사 '떨려·떨리'(떨림)를 넣음 → "
                 f"REGRESSION168 의 정답 연결 2건('토할 것 같아요'=gold nausea, '몸이 덜덜 떨려요'=gold chills)을 위반으로 셈. 검색기 결함 아님. 공식 판정은 그대로 둔다.\n"
                 f"- v2 재채점(검사기만 STEP28.6 원형·명사 '떨림' 으로, 모델 재실행 없음 — `outputs/exploratory_v2.json`): 구별 위반 입력 "
                 + " · ".join(f"{p} {pp[p]['11_semantic_violation_inputs_v2']}" for p in ("A_STEP27_B4", "B_STEP28", "C_STEP28_6", "D_STEP28_7", "D_NO_TABLE", "D_LOO"))
                 + f" → **STEP28_7_RESULT_EXPLORATORY_V2 = {xv['STEP28_7_RESULT_EXPLORATORY_V2']}**(게이트 {json.dumps(xv['gates_v2'], ensure_ascii=False)}).\n"
                 f"  D_NO_TABLE(=STEP28.5 KO) 의 위반 {pp['D_NO_TABLE']['11_semantic_violation_inputs_v2']} 은 '떨림 → 오한' — 정제 대응표가 막음. C 와 동률인 이유: C 는 표 밖 입력을 처리하지 않음(REGRESSION168 coverage {C['8_supported_auto_coverage']}).\n"
                 f"- G6 FAIL 은 v2 에서도 유지: D 의 regression 오답은 D_NO_TABLE 과 같은 STEP28.5 KO 경로 오류(첫 자동 구문 기준; 진단 'gold 가 어느 자동 구문에든 있음' D {pp['D_STEP28_7']['diag_regression_gold_in_any_auto_span']} · A {pp['A_STEP27_B4']['diag_regression_gold_in_any_auto_span']}).\n"
                 f"- A(STEP27) 재현 불일치(SILVER442 {rep['A_STEP27_B4:SILVER442']['mismatch']}): STEP27 파일은 EXT 세트에 out-of-fold 비증상 점수(routing_decisions)를 쓰고 라이브는 전체 분류기 점수를 씀"
                 f"(STEP27 analyze_routing_errors.py 118–135 행 확인) → UNCERTAIN↔UNKNOWN 차이. 나머지 세트 불일치 0.")
    else:
        xv_md = "- 없음"
    md = f"""# STEP28.7 — MedMap Ontology Mapping Quality & Safety Validation

- **STEP28_7_RESULT = {verdict}** · PRODUCTION_READY = NO · STEP29 진입 = **{step29}** · HUMAN_VERIFIED_GOLD = 0 · 모든 대응·분류 = SILVER(검증 전)
- 게이트: {json.dumps(final['gates'], ensure_ascii=False)} · C(STEP28.6) 대비 안전 지표 개선: {json.dumps(better, ensure_ascii=False)}
- 판정·게이트 규칙은 평가 실행 전 `scripts/build_report.py` 문서열에 고정. 검색 규칙은 `scripts/safe_offline_retriever.py` 문서열(평가 전 고정, 변경 기록 = §12).
- 데이터는 모두 STEP21–28.6 에서 반복 관찰된 개발·회귀 자료(blind 아님). C·D 의 SILVER442·WEAKNON903·probe 수치는 **대응표가 그 입력으로 작성된 in-table 수치**다.
- 추가 LLM·외부 API·다운로드·재학습·제품 변경 0. G10(기존 산출물·제품 저장소 무변경) = {prot.get('G10')}.

## 1. 최종 보고 항목

| 항목 | 값 |
|---|---|
| ORIGINAL_NEW_CANDIDATES | 34(보고 기준 = G3 고유 {cr['recomputed_per_grade_distinct']['G3_SILVER_AUDITED']} + G2 고유 {cr['recomputed_per_grade_distinct']['G2_SILVER_AGREED']}) · 고유 concept {cr['distinct_G2plus_union']} · 전 등급 {cr['distinct_all_grades_union']} |
| INDEPENDENT_NEW_CONCEPTS | {final['INDEPENDENT_NEW_CONCEPTS']}(계열 {final['INDEPENDENT_NEW_CONCEPT_FAMILIES']} — tremor 하위 묶음) · HPO 감사 EXACT {ca['independent_new_HPO_audited_EXACT']} · SNOMED 전용 UNVERIFIED {ca['independent_new_SNOMED_only_UNVERIFIED']} |
| EXISTING_SYNONYMS | {final['EXISTING_SYNONYMS']} |
| EXISTING_SUBTYPES | {final['EXISTING_SUBTYPES']} |
| HELD_CANDIDATES | {final['HELD_CANDIDATES']} |
| REJECTED_CANDIDATES | {final['REJECTED_CANDIDATES']} |
| ISOLATION_UNVERIFIED_CANDIDATES | {final['ISOLATION_UNVERIFIED_CANDIDATES']} (격리 FAIL 조각이 지지 행에 있는 후보 {final['ISOLATION_FAIL_CANDIDATES']}) |
| WEAK_NEGATIVE_AUTO_MAP | {final['WEAK_NEGATIVE_AUTO_MAP']}(C 재계산 {C['7_weaknon_auto_link_risk']}/903, STEP28.5 49/903) |
| SUPPORTED_AUTO_COVERAGE | {final['SUPPORTED_AUTO_COVERAGE']}(REGRESSION168, precision {final['REGRESSION_AUTO_PRECISION']}; A {A['8_supported_auto_coverage']}/{A['9_regression_auto_precision']}) |
| WRONG_CANDIDATE_DISPLAY | {final['WRONG_CANDIDATE_DISPLAY']} |
| SEMANTIC_DISTINCTION_VIOLATIONS | {final['SEMANTIC_DISTINCTION_VIOLATIONS']} |
| RAW_PRESERVATION | {final['RAW_PRESERVATION']} |
| CPU_P95 | {final['CPU_P95_MS']} ms(p50 {lt['D_STEP28_7']['p50_ms']} ms, n {lt['D_STEP28_7']['n']}) · peak RSS {lat['peak_rss_mib']} MiB |
| SILVER 검사 통과 concept(신규 유지 + 기존 관계 병합) | {silver_passed} |
| HUMAN_VERIFIED_GOLD | 0 |
| PRODUCTION_READY | NO |

## 2. 34 집계 재검증(§1)

- STEP28.6 보고 34 = 등급별 고유 수의 단순 합(G3 22 + G2 12). 같은 concept 이 다른 입력에서 두 등급을 받은 경우 중복: {cr['discrepancy']['double_counted'] if cr['discrepancy'] else '없음'} → G2+ 고유 {cr['distinct_G2plus_union']}.
- G1(단일 작성자)·REJECTED 는 34 에 포함되지 않음. 단 {', '.join(c for c, gs in cr['concepts_in_multiple_grades'].items() if 'G1_SINGLE_AUTHOR' in gs)} 는 G1·G2 둘 다라 concept 으로는 34 안. 전 등급 고유 {cr['distinct_all_grades_union']}.
- SNOMED 전용(HPO 교차 없음) 후보: 전 등급 {ca['SNOMED_only(all)']} · 34 집합 {ca['SNOMED_only(34-set)']}(인수인계 문서의 '11' 과 다름 — 원본 audit_manifest NOT_AUDITED_LICENSE 기준 재계산).
- STEP28.6 산출물은 수정하지 않았다(G10).

## 3. 신규 후보 분류(§3·§4) — 분류자 = STEP28.7 Claude 세션(비인간·비독립, SILVER)

{cls_tab}

- 독립 신규(D): {fl(ind)}
- 기존 하위(C): {fl(sub)} — 부모 feature 자동 통합 금지(연구용 부모 후보만 기록)
- 보류·반려: {fl(held)}
- 우선 검토: 무기력 = UNCERTAIN(피로와 HPO 계층 DISTINCT 이나 정의가 겹침, 의식 저하와 동의어 처리 안 함) · 마른기침 = cough 하위(속성 보존, 자동 통합 금지) ·
  묽은변 = 기존 diarrhea 관련(동의어 아님, 독립 신규 집계 제외, 보류) · 떨림 = Tremor 독립 신규(Chills 와 DISTINCT — STEP28.5 떨림→오한은 오류) ·
  코피 = Epistaxis, E_178(이상 출혈) 하위로 분류(객혈·토혈과 DISTINCT) · 구토·오심 = DISTINCT(관계 파일 `outputs/priority_pair_relations.json`, LOCAL_ONLY).

## 4. SNOMED 전용 후보(§5)

- 로컬 SNOMED(2026-09-01)로 id 유효·active·clinical finding 계층·부모·자식 수·77 관계를 확인(`data/snomed_local_audit.csv`, LOCAL_ONLY). 외부 전송 0.
- concept 존재·활성은 확인되나 **한국어 대응 정확성은 UNVERIFIED**(HPO 감사 불가·인간 검토 없음). 검증 완료로 표시하지 않는다.

## 5. 격리 검사 FAIL(§6)

- FAIL 세션 {', '.join(iso['failed_sessions'])}: 모두 작성 직후 **자기 출력 파일 1–3 행을 다시 읽고 전체 재작성**. B_c04 의 Edit 은 시도됐으나 도구 차단 오류로 실패(실제 변경은 Write).
- 다른 작성자 파일 읽기 0 · 작업 폴더 밖 접근 0 · 메모리/CLAUDE.md 주입 0. 재작성으로 바뀐 행 {n_chg} 개는 모두 열 개수·비고·확신도 칸(형식 보정) — 유형·영어 용어 변경 0(`outputs/isolation_analysis.json` row_diffs).
- B_c04 실행 시점에 작성자 A 파일 6개가 out/ 에 있었음(읽은 기록 없음).
- 영향 범위: 입력 {iso['ids_with_any_author_fail']} 개(SILVER442 {iso['fail_ids_by_source']['SILVER442']} · WEAKNON903 {iso['fail_ids_by_source']['WEAKNON903']}). provenance = ISOLATION_FAIL 유지(PASS 로 바꾸지 않음).
  정제표에서 이 행들은 양성 연결에 쓰지 않음(HOLD_ISOLATION {dec['HOLD_ISOLATION']}), 비증상 판정(연결 거부 방향)만 허용.
- 재작성 비용(실행 안 함): 같은 조각 실측 정가 환산 {iso['rewrite_cost_if_needed']['llm_cost_same_chunks']} USD — 별도 과금 승인 대상.

## 6. 정제 SILVER 대응표(§7)

- `data/cleaned_silver_mappings.csv`(1,355 행) 결정: {json.dumps(dict(dec), ensure_ascii=False)}
- 근거 등급: {json.dumps(dict(lv), ensure_ascii=False)} · LEVEL_4 = 0. LEVEL_3 = A·B 일치 + opus 감사 EXACT(감사자 = 작성자 A 와 같은 모델 → 독립 검증 아님).
- usable_by_disease_model = 전부 False. 표시 허용 = ACCEPT_EXISTING·SYNONYM 만.

## 7. 정책 비교(§12) — 단위: A·B·C 입력, D 계열 구문

{tbl}

- 비증상 903·Silver 442 는 약한 라벨, REGRESSION168 은 합성(gold) — 하나의 정확도로 합치지 않음.
- REGRESSION168: A coverage {regA['coverage']}(정답 {regA['correct']}/{regA['auto']}) · D coverage {regD['coverage']}(정답 {regD['correct']}/{regD['auto']}). D 오답 예: {regD['wrong'][:5]}
- 재현 확인(A·B 라이브 ↔ 기존 파일 불일치 수): {json.dumps({k: v['mismatch'] for k, v in rep.items() if 'mismatch' in v}, ensure_ascii=False)} · C 비증상 위험 재계산 {rep['C_STEP28_6:WEAKNON903_risk_vs_reported_8']}

## 8. 비증상 자동 연결(§9)

- STEP28.6(C) 위험 입력 {len(c8)}: {', '.join(c8)} — 원인 {json.dumps(dict(naC), ensure_ascii=False)}
- STEP28.7(D) 위험 입력 {len(d_risk)}: {'; '.join(f'{a}→{b}({c})' for a, b, c, _ in d_risk)} — 원인(사전 분류) {json.dumps(dict(naD), ensure_ascii=False)}
- D 의 위험은 전부 STEP28.5 한국어 경로(KO)에서 발생: 대응표 행이 단일 작성자·충돌·격리 FAIL 보류라 KO 결과를 덮지 않음(사전 규칙). 사후 확인한 KO 색인 결함(이번 단계 미수정):
  1글자 핵어 완전일치('외 음 부 근' 의 '근' ← '가슴 두근' → palpitations) · 일반 명사 부분 일치('주위'·'이상' → dizziness·E_178) · 질환명 안 증상어('경추성 어지럼증' → dizziness) · B4 모델('양쪽 팔을들어' → limb_weakness).
  C(STEP28.6) 의 8 건(흉통 6 · 심계항진 1 · 만성기침 1)은 두 작성자 모두 증상형으로 쓴 실제 증상 용어(약한 비증상 라벨 쪽 의심). D 에서 흉통 6 은 KO 경로가 연결하지 못했고(NO_KOREAN_MATCH —
  77 지원 증상 '흉통' 의 KO 누락) 대응표 행이 격리 FAIL 보류라 UNCERTAIN, 심계항진·만성기침은 KO EXACT 로 연결(eval_rows.csv).
- 'SYMPTOM_TERM_WEAK_LABEL_CONFLICT' = 두 작성자 모두 증상형으로 쓰고 한국어 기존 검색도 증상으로 본 단어(약한 비증상 라벨 쪽 의심). 원문 문맥이 없는 단어 조각이라 증상 문맥 여부는 확인 불가.
  이 경우를 UNKNOWN 으로 돌려 수치를 맞추지 않았다.

## 9. 후보 표시 안전성(§10) — probe(사용자 지정, 이미 노출된 사례)

{ptab}
- ⚠ = 구별 위반. 제품 매퍼는 read-only 로 탐지만(제품 코드 변경 없음).
- 사후 관찰(probe, `data/eval_rows.csv` reasons): '떨림' D = UNCERTAIN(KO PHRASE chills ↔ SILVER tremor 충돌 — 오한 연결은 막았으나 tremor 도 반환 안 함) · '무기력'·'묽은변' D = fatigue·diarrhea 자동(KO PHRASE·EXACT) — concept 감사 보류(F)와 다름: 사전 규칙상 SILVER 보류는 KO 결과를 덮지 않음(사용자 결정 필요) · '오심' D = UNCERTAIN(KO 가 NON 으로 판정 ↔ SILVER nausea 충돌 — STEP28.5 KO 결함) · 제품 매퍼는 '토했어요'·'구토' → E_148(오심), '기침 억제제' → E_201(기침) 여전히 POSITIVE.

## 10. 답(§19)

1. 원래 34(고유 {cr['distinct_G2plus_union']}) 중 독립 신규 증상 후보 = {ca['by_class(34-set distinct 33)']['NEW_INDEPENDENT_CONCEPT']}(전 등급 {ca['INDEPENDENT_NEW_CONCEPTS']}, tremor 계열 묶으면 {ca['independent_new_concept_families(tremor 하위 묶음)']}). SILVER·비인간 분류.
2. 기존 77 과 겹치는 개념(동의어+속성+하위) = {ca['overlap_with_77(A+B+C)']}.
3. 기존 증상의 하위 유형 = {ca['EXISTING_SUBTYPES']}.
4. HPO 감사 일치 22 = 'A·B 두 LLM 일치 + 같은 계열 LLM 의 HPO 정의 대비 자동 감사 EXACT' = LEVEL_3 SILVER. 독립 검증·인간 Gold 아님.
5. SNOMED 전용 = id·활성·계층·77 관계까지 로컬 확인. 한국어 대응 정확성은 확인 불가(UNVERIFIED).
6. 격리 FAIL 은 자기 출력 재읽기·재작성(형식 보정만 확인)으로 교차 오염 증거는 없으나 규칙 위반 → 해당 {iso['ids_with_any_author_fail']} 입력(전부 WEAKNON903)의 양성 연결을 쓰지 않음. Silver442 신규 후보에는 영향 없음, 만성기침 1개 보류.
7. 비증상 자동 연결 8건(STEP28.6) 원인: {json.dumps(dict(naC), ensure_ascii=False)} — 전부 두 작성자가 증상형으로 쓴 실제 증상 용어(흉통·심계항진·만성기침)로 약한 비증상 라벨과 충돌. 질환·약물·부위·부분 일치 원인은 0.
8. STEP28.6 대비 안전성: 개선 아님(동률·공식 검사기로는 악화). 비증상 위험 {C['7_weaknon_auto_link_risk']} → {D['7_weaknon_auto_link_risk']}(원인 종류는 바뀜: 실제 증상어 → KO 오연결) · 구별 위반 {C['11_semantic_violation_inputs']} → {D['11_semantic_violation_inputs']}(v2 {xv['per_policy']['C_STEP28_6']['11_semantic_violation_inputs_v2'] if xv else '-'} → {xv['per_policy']['D_STEP28_7']['11_semantic_violation_inputs_v2'] if xv else '-'}) · 잘못된 후보 표시 {C['10_wrong_candidate_display_inputs']} → {D['10_wrong_candidate_display_inputs']}. 단 C 는 표 밖 입력을 처리하지 못하고, D 는 A(STEP27)·B(STEP28) 대비 구별 위반(v2)이 {xv['per_policy']['A_STEP27_B4']['11_semantic_violation_inputs_v2'] if xv else '-'}·{xv['per_policy']['B_STEP28']['11_semantic_violation_inputs_v2'] if xv else '-'} → {xv['per_policy']['D_STEP28_7']['11_semantic_violation_inputs_v2'] if xv else '-'}.
9. 기존 증상 자동 처리율(REGRESSION168): A {A['8_supported_auto_coverage']} · D {D['8_supported_auto_coverage']} · D_NO_TABLE {ev['D_NO_TABLE']['8_supported_auto_coverage']} — 감소 {ok(D['8_supported_auto_coverage'] < A['8_supported_auto_coverage'])}(A 대비).
10. 처음 보는 표현: 대응표는 사전(완전일치)이라 표 밖 표현은 STEP28.5 한국어 경로·B4 로만 처리. D_LOO(같은 원문 행 제외) Silver 결정률 {ev['D_LOO']['silver_decided_rate(units: EXISTING*/SUBTYPE/NEW/NON)']} vs D {D['silver_decided_rate(units: EXISTING*/SUBTYPE/NEW/NON)']} · 신규 id {ev['D_LOO']['3_NEW_INDEPENDENT_ontology_ids']} vs {D['3_NEW_INDEPENDENT_ontology_ids']}. → 77 밖 신규 증상은 사전 기반 표현만 가능.
11. 병원 오프라인: 런타임 LLM·네트워크 불필요(CPU p95 {lt['D_STEP28_7']['p95_ms']} ms, RSS {lat['peak_rss_mib']} MiB). 대응표 확장에는 오프라인 LLM 작성 단계(과금 승인)가 필요.
12. STEP29 인터페이스: `docs/step29_interface.md`(구문 위치·부정·시점·주체는 STEP28.5 추출값 전달, 검증 안 됨) → 공식 {step29}(사전 규칙: hard 게이트 G3 FAIL) · 탐색 v2 {xv.get('STEP29_ENTRY_EXPLORATORY_V2', '-') if xv else '-'}(검사기 결함 제외 시). 바로 쓸 수 있는 형태이나 STEP28.5 KO 경로 정밀도(G6) 문제를 안고 간다.
13. STEP29 전 필수: 인간 검토 Gold 소량(독립 신규 {ca['INDEPENDENT_NEW_CONCEPTS']}·하위 {ca['EXISTING_SUBTYPES']}·우선 보류) · 부정·시점·주체 검증 · 격리 FAIL 조각 재작성 여부 결정(과금) · 약한 비증상 라벨 정정 방법.

## 11. 사후 발견·탐색적 결과(EXPLORATORY_POST_HOC — 공식 판정 아님, 1차 결과를 본 뒤 작성)

{xv_md}

## 12. 변경 기록(공개)

- 평가 전 기능 점검(§14 예시 문장)에서 대응표 조회 키 결함: '머리가 아파' 의 명사구 '머리'(신체 부위 NON 행)가 통증 구문을 막음 → STEP28.5 qkeys 와 같은 규칙(술어가 증상을 담으면 명사구 단독 키 안 씀)으로 수정. 이 예시는 probe 에 포함되므로 그 결과는 회귀 확인용.
- concept 분류 결정(`data/concept_review_decisions.csv`)은 사실 표를 본 뒤 평가 전에 작성. 평가 후 수정 없음.
- 1차 평가 후(공식 판정 고정 뒤) 추가: `scripts/evaluate_exploratory_v2.py`(검사기 v2 재채점, 공식 판정 아님) · 보고서 집계 수정(비증상 원인 표를 정책별 위험 행만 세도록) · run_all.sh 에 v2 와 보고서 재생성 단계 추가. 검색 규칙·게이트·공식 판정 규칙은 바꾸지 않음.
"""
    (S.DOCS / "step28_7_report.md").write_text(md, encoding="utf-8")
    man = {"step": "STEP28.7", "verdict": verdict, "scripts": {p.name: S.sha256(p) for p in sorted((S.STEP / "scripts").glob("*.py"))},
           "inputs": {str(p.relative_to(S.REPO)): S.sha256(p) for p in [S.S286_DIR / "data/ontology_links.csv", S.S286_DIR / "data/silver_ko_en_table.csv",
                                                                         S.S286_DIR / "outputs/new_concept_candidates.csv", S.S286_DIR / "outputs/authoring_isolation_check.json",
                                                                         S.S28_DIR / "data/external_silver_expansion.csv", S.S28_DIR / "outputs/weak_non_check.csv",
                                                                         S.S27_DIR / "outputs/routing_features.csv", S.DATA / "concept_review_decisions.csv"]},
           "outputs": {str(p.relative_to(S.STEP)): S.sha256(p) for p in sorted(list(S.OUT.glob("*")) + list(S.DATA.glob("*"))) if p.is_file()},
           "llm_calls": 0, "downloads": 0, "local_only_files": (S.STEP / ".gitignore").read_text(encoding="utf-8").splitlines()[1:]}
    S.dump_json(S.OUT / "manifest.json", man)
    print(S.dumps({k: final[k] for k in final if k != "rules"}))


if __name__ == "__main__":
    main()
