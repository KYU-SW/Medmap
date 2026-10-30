"""STEP29.3 판정·보고서·manifest 생성. 숫자는 모두 outputs/·data/ 에서 읽는다(손으로 쓰지 않음). 판정 규칙 = gates293.py(평가 전 고정).
출력: outputs/{step29_3_verdict.json, manifest.json} · docs/{step29_3_report.md, step30_readiness.md, step30_handoff.md}"""
from __future__ import annotations

import json

import s293_common as S
from evaluate_retrieval import prereg_ok
from gates293 import __doc__ as GATES_DOC
from gates293 import f1, verdict


def fmt(x):
    return "없음" if x is None else (f"{x:.4f}" if isinstance(x, float) else str(x))


def main():
    M = S.load_json(S.OUT / "eval_summary.json")["metrics"]
    pf = S.load_json(S.DATA / "policy_freeze.json")
    pre = S.load_json(S.DATA / "prereg_gates.json")
    sel = pf["SELECTED_POLICY"]
    protect = S.load_json(S.OUT / "protected_check.json")
    lat = S.load_json(S.OUT / "latency.json")
    mem = S.load_json(S.OUT / "memory.json")
    st = prereg_ok(True)
    V = verdict(M, sel, protect, lat, st)
    F, F0, H, X, W, RG = M[sel]["FROZEN29_3"], M["R0"]["FROZEN29_3"], M[sel]["STEP29_2_HOLDOUT"], M[sel]["EXPOSED"], M[sel]["WEAK"], M[sel]["REGRESSION_CASES"]
    A = lat["condition_A_low_load"]
    out = {"STEP29_3_RESULT": V["STEP29_3_RESULT"],
           "MORPHOLOGICAL_VARIANT_SUCCESS": f"{F['MORPHOLOGICAL_VARIANT_SUCCESS']}(FROZEN29_3 형태 변화 묶음 {F['morph_groups_n']}; R0 {F0['MORPHOLOGICAL_VARIANT_SUCCESS']})",
           "CONCEPT_PRECISION": f"{F['CONCEPT_AUTO_PRECISION']}(FROZEN29_3 시스템 EXISTING {F['precision_n']}; R0 {F0['CONCEPT_AUTO_PRECISION']}) · STEP29.2 HOLDOUT {H['CONCEPT_PRECISION']} · REGRESSION168 {X['reg_precision']}",
           "CONCEPT_COVERAGE": f"{F['CONCEPT_AUTO_COVERAGE']}(FROZEN29_3 필수 정답 {F['coverage_n']}; R0 {F0['CONCEPT_AUTO_COVERAGE']}) · STEP29.2 HOLDOUT {H['CONCEPT_COVERAGE']} · REGRESSION168 {X['reg_coverage']}(첫 연결 시도 기준)",
           "MULTI_SPAN_RETENTION": f"{F['MULTI_SPAN_RETENTION']}(FROZEN29_3 {F['multi_n']}; R0 {F0['MULTI_SPAN_RETENTION']}) · STEP29.2 HOLDOUT {H['MULTI_SPAN_RETENTION']}",
           "SEMANTIC_AMBIGUITY_ERRORS": f"{F['SEMANTIC_AMBIGUITY_ERRORS']}(FROZEN29_3; R0 {F0['SEMANTIC_AMBIGUITY_ERRORS']}) · 회귀 사례 위반 {RG['REGRESSION_VIOLATIONS']}/{RG['n']}",
           "WRONG_CONCEPT_AUTO_ACCEPT": f"{F['WRONG_CONCEPT_AUTO_ACCEPT']}(FROZEN29_3; R0 {F0['WRONG_CONCEPT_AUTO_ACCEPT']})",
           "UNSUPPORTED_AUTO_LINK": f"{F['UNSUPPORTED_AUTO_LINK']}(FROZEN29_3 비증상·미지원·SILVER case; R0 {F0['UNSUPPORTED_AUTO_LINK']})",
           "WEAK_NEGATIVE_AUTO_MAP": f"{W['WEAK_NEGATIVE_AUTO_MAP']}/{W['weaknon_n']}(WEAKNON903 약한 음성; R0 {M['R0']['WEAK']['WEAK_NEGATIVE_AUTO_MAP']})",
           "UNKNOWN_RATE": f"{F['UNKNOWN_RATE']}(FROZEN29_3 지원 정답 {F['supported_n']}; R0 {F0['UNKNOWN_RATE']}) · UNCERTAIN_RATE {F['UNCERTAIN_RATE']}(R0 {F0['UNCERTAIN_RATE']})",
           "SILVER_CONCEPT_PRESERVATION": f"{F['SILVER_CONCEPT_PRESERVATION']}(FROZEN29_3 SILVER {F['silver_n']}, NEW 후보로 보존 {F['silver_new_candidate']})",
           "NEGATION_SCOPE": f"{F['NEGATION_SCOPE']}(FROZEN29_3 정렬 {F['aligned_n']}) · STEP29.2 HOLDOUT {H['NEGATION_SCOPE']}",
           "TEMPORALITY": f"{F['TEMPORALITY']}(FROZEN29_3)", "EXPERIENCER": f"{F['EXPERIENCER']}(FROZEN29_3)",
           "RAW_PRESERVATION": f"{F['RAW_PRESERVATION']}(FROZEN29_3 {F['n_inputs']}) · 전 입력 G1 {V['hard_gates']['G1']}",
           "CPU_P95": f"{V['p95_ms_condition_A']} ms(조건 A 저부하, pilot 274, {sel}; R0 {A['pilot274']['R0']['p95_ms']}) · 조건 B {lat['condition_B_concurrent_load']['pilot274'][sel]['p95_ms']} ms",
           "PEAK_MEMORY": f"{mem['peak_rss_mib']} MiB(benchmark 프로세스 최대 RSS)",
           "STEP30_READINESS": V["STEP30_READINESS"], "PRODUCTION_READY": "NO", "HUMAN_VERIFIED_GOLD": 0, "SELECTED_POLICY": sel,
           "hard_gates": V["hard_gates"], "performance": V["performance"], "prereg_status": st, "rules": GATES_DOC,
           "data_classes": "NEW_SYNTHETIC_FROZEN(FROZEN29_3, 동결 후 1회) · NEW_SYNTHETIC_DEV(DEV29_3) · EXPOSED_REGRESSION(STEP29.2 HOLDOUT·pilot·계약·회귀 사례) · WEAK_EXTERNAL(WEAKNON903). 사람 검증 Gold 없음"}
    S.dump_json(S.OUT / "step29_3_verdict.json", out)
    pols = list(M)
    keys = ["CONCEPT_AUTO_PRECISION", "CONCEPT_AUTO_COVERAGE", "CONCEPT_RECALL_ON_SUPPORTED", "MULTI_SPAN_RETENTION", "MORPHOLOGICAL_VARIANT_SUCCESS",
            "MORPH_VARIANT_MENTION_SUCCESS", "SEMANTIC_AMBIGUITY_ERRORS", "WRONG_CONCEPT_AUTO_ACCEPT", "UNSUPPORTED_AUTO_LINK", "UNKNOWN_RATE", "UNCERTAIN_RATE",
            "SILVER_CONCEPT_PRESERVATION", "NEGATION_SCOPE", "TEMPORALITY", "EXPERIENCER", "SEMANTIC_VIOLATIONS", "NEG_POSITIVE", "OTHER_POSITIVE", "CASE_PASS_RATE"]
    tab = lambda st, ks: "\n".join(["| 지표 | " + " | ".join(pols) + " |", "|---" * (len(pols) + 1) + "|"] +  # noqa: E731
                                    [f"| {k} | " + " | ".join(fmt(M[p][st].get(k)) for p in pols) + " |" for k in ks])
    hk = ["CONCEPT_PRECISION", "CONCEPT_COVERAGE", "MULTI_SPAN_RETENTION", "NEGATION_SCOPE", "TEMPORALITY", "EXPERIENCER", "RESOLUTION_LINKING",
          "PUNCTUATION_PAIR_CONSISTENCY", "PROPAGATION_ERRORS", "UNSUPPORTED_AUTO_LINK", "CASE_PASS_RATE"]
    xk = ["reg_precision", "reg_coverage", "pilot_multi_retention", "pilot_assertion_agreement", "pilot_unsupported_auto", "C29_failed", "NEW42_pass", "PROS231_pass"]
    rg = "\n".join(f"| {p} | {M[p]['REGRESSION_CASES']['REGRESSION_VIOLATIONS']}/{M[p]['REGRESSION_CASES']['n']} | {M[p]['WEAK']['WEAK_NEGATIVE_AUTO_MAP']}/903 |" for p in pols)
    tr = "\n".join(f"| {p} | {fmt(f1(M[p]['FROZEN29_3']['CONCEPT_AUTO_PRECISION'], M[p]['FROZEN29_3']['CONCEPT_AUTO_COVERAGE']))} | "
                   f"{fmt(f1(M[p]['STEP29_2_HOLDOUT']['CONCEPT_PRECISION'], M[p]['STEP29_2_HOLDOUT']['CONCEPT_COVERAGE']))} | "
                   f"{fmt(f1(M[p]['EXPOSED']['reg_precision'], M[p]['EXPOSED']['reg_coverage']))} |" for p in pols)
    mv = "\n".join(f"| {v} | " + " | ".join(str(M[p]["FROZEN29_3"]["morph_by_variant"].get(v)) for p in pols) + " |" for v in M[sel]["FROZEN29_3"]["morph_by_variant"])
    selr = "\n".join(f"| {r['policy']} | {r['safe']} | {r['floor']} | {r['eligible']} | {r['dev_f1']} | {r['dev_precision']} | {r['dev_coverage']} |" for r in pf["selection_rows"])
    tax = S.load_json(S.OUT / "failure_taxonomy_summary.json")
    errs = S.load_json(S.OUT / "error_summary.json")["frozen_examples"]
    exs = "\n".join(f"- **{t}** ({len(v)}건 표시): " + " / ".join(f"`{e['text']}` → {e.get('got')}" for e in v[:4]) for t, v in errs.items()) or "- 없음"
    tests = S.load_json(S.OUT / "unit_tests.json")
    nt = sum(v["tests"] for v in tests["by_file"].values())
    nf = sum(v["failures"] + v["errors"] for v in tests["by_file"].values())
    fro = S.load_json(S.DATA / "frozen_evaluation_cases.json")
    br = S.load_json(S.OUT / "baseline_reproduction.json")
    g = " · ".join(f"{k} {v}" for k, v in V["hard_gates"].items())
    pp = " · ".join(f"{k} {v}" for k, v in V["performance"].items())
    rep = f"""# STEP29.3 — Clinical Concept Retrieval & Semantic Disambiguation 보고서

이 문서의 숫자는 build_report.py 가 outputs/ 에서 읽어 생성(손으로 쓰지 않음).

## 판정
- **STEP29_3_RESULT = {V['STEP29_3_RESULT']}** · **STEP30_READINESS = {V['STEP30_READINESS']}** · PRODUCTION_READY = NO · HUMAN_VERIFIED_GOLD = 0
- 선택 정책(DEV29_3 + 노출 자료만으로 사전 규칙 선택, FROZEN 미사용) = **{sel}**
- Hard: {g}
- Performance(FROZEN29_3, R0 대비 · P8 = STEP29.2 HOLDOUT): {pp}
- STEP29.2 baseline 재현: {json.dumps({p: r['REPRODUCED'] for p, r in br['comparison'].items()}, ensure_ascii=False)} (STEP29.2 공식 eval_summary 와 R0·R1 재계산 비교)
- STEP29.2 공식 RECOVERY_PASS 판정과 post_run_note 는 그대로 유지(이 단계는 별도 실험).

## 데이터(합성 — 사람 검증 Gold 아님, 생성기 작성자 = 검색 규칙 작성자라 완전 독립 아님)
- FROZEN29_3 {fro['n_cases']} 입력(범주 {fro['by_category']}) · 노출 중복 제외 {fro['dropped_exposed_or_dup']} · DEV↔FROZEN 겹침 {fro['split_leak_check']}
- 새 표현의 기존 노출 자료 대비 문자 3-gram 최대 Jaccard 평균 {fro['novelty_max_jaccard_to_exposed']['mean']}(≥0.8 인 입력 {fro['novelty_max_jaccard_to_exposed']['ge_0.8']}/{fro['novelty_max_jaccard_to_exposed']['n']})
- 회귀 사례 32(지시문 3절 예시 등, 노출) — 작성 중 정정 1건(기침하면 피가 같이 나와요의 허용 목록에 cough 추가, 정책 구현 전)

## FROZEN29_3 정책 비교(같은 입력)
{tab('FROZEN29_3', keys)}

형태별(필수 정답 mention 정답 연결/대상):

| 형태 | {' | '.join(pols)} |
|---{'|---' * len(pols)}|
{mv}

## STEP29.2 HOLDOUT 1,052(노출, STEP29.2 와 같은 입력·정의)
{tab('STEP29_2_HOLDOUT', hk)}

## 노출 회귀(pilot·REGRESSION168·계약)
{tab('EXPOSED', xk)}

| 정책 | 회귀 사례 위반 | WEAKNON903 자동 연결 |
|---|---|---|
{rg}

정밀도·coverage 균형(F1, β = 1):

| 정책 | FROZEN29_3 | STEP29.2 HOLDOUT | REGRESSION168 |
|---|---|---|---|
{tr}

## 정책 선택(gates293.select_policy, 평가 전 고정)
| 정책 | 안전 | 하한 | 자격 | DEV F1 | DEV precision | DEV coverage |
|---|---|---|---|---|---|---|
{selr}

## P5 실패 분해(노출 자료, outputs/failure_taxonomy.csv)
- 원인별(중복 포함): {json.dumps(tax['by_cause(중복 포함)'], ensure_ascii=False)}
- 단계별: {json.dumps(tax['by_stage'], ensure_ascii=False)} · 수정 범위: {json.dumps(tax['by_fix_scope'], ensure_ascii=False)}

## 선택 정책 FROZEN29_3 오류 사례
{exs}

## 처리 시간·메모리
- 조건 A(저부하, 측정 전 load {A['loadavg_1m_before']}): pilot 274 {json.dumps(A['pilot274'], ensure_ascii=False)}
- 단계별(조건 A, pilot 274): {json.dumps(A['stages_pilot274'], ensure_ascii=False)}
- 조건 B(동시 부하 — 바쁜 루프 2개, load {lat['condition_B_concurrent_load']['loadavg_1m_during']}): {json.dumps(lat['condition_B_concurrent_load']['pilot274'], ensure_ascii=False)}
- 초기 로딩 {lat['init_load_ms(P5 엔진·B4 라우터·KoELECTRA)']} ms · peak RSS {mem['peak_rss_mib']} MiB · GPU 사용 안 함

## 재현·보호
- 단위 테스트 {nt} · 실패 {nf} · 테스트 문자열과 FROZEN 겹침 {tests['test_strings_in_frozen']}
- 보호 G7 = {protect.get('G7')}(연구 원본 {protect.get('research_files')} 파일 변경 {len(protect.get('research_changed', []))}·추가 {len(protect.get('research_added', []))} · 제품 HEAD {protect.get('product_head_after', '')[:7]} 동일 {protect.get('product_ok')})
- 사전 고정: prereg_gates {pre['frozen_at']} · policy_freeze {pf['frozen_at']}

## 해석 주의
- 합성 정답·같은 작성자의 규칙과 데이터. 실제 환자·실제 ASR 전사문 성능 아님. 임상 정확도·안전성 주장 없음.
- '목이 아파요'(단서 없음)는 검색기의 기존 SILVER 기반 해석(인후통)을 그대로 두고 표현만 일관되게 맞춤 — 단서 없는 목 통증을 인후통으로 확정한다는 주장이 아님(정답 세트에서 optional).
- REGRESSION168 coverage 는 '첫 EXISTING 연결 시도' 비율(정답 무관).
"""
    (S.DOCS / "step29_3_report.md").write_text(rep, encoding="utf-8")
    (S.DOCS / "step30_readiness.md").write_text(f"""# STEP30 진입 판정(STEP29.3 기준)

- STEP30_READINESS = **{V['STEP30_READINESS']}** · STEP29_3_RESULT = {V['STEP29_3_RESULT']} · PRODUCTION_READY = NO
- 규칙: GO_FOR_RESEARCH = RETRIEVAL_IMPROVED · CONDITIONAL_GO = hard 전부 AND P1·P2·P5·P6·P8 AND 결과 ≠ REGRESSION · NO_GO = 그 외
- Hard: {g}
- Performance: {pp}
- STEP30 은 연구용 연결 설계부터이며 자동 실행하지 않는다(사용자 승인 필요). 제품 적용 판정은 없다.
""", encoding="utf-8")
    (S.DOCS / "step30_handoff.md").write_text(f"""# STEP30 인계(연구용 연결 설계 입력)

- 진입점: `exp/step29_3_concept_retrieval_repair/scripts/step29_2_adapter.py` 의 `analyze(text, "{sel}")` — STEP29.2 mention 스키마 + `retrieval`(via·query·tier·basis·원래 상태) ·
  `normalization`(original_phrase·lemma_candidates·core_predicate·anatomical_site·symptom_modifiers·negation) · `semantic_conflict`/`semantic_refinement` · `b4_path`.
- 판정: STEP29_3_RESULT = {V['STEP29_3_RESULT']} · STEP30_READINESS = {V['STEP30_READINESS']}. 제품·PatientState·49질환 모델 연결 금지(model_input.applied = false).
- 남은 위험: 합성 평가뿐(사람 검증 0)·규칙과 평가 데이터 작성자가 같음 · 단서 없는 '목' 통증 해석 · 검색기 사전 대응 오류(누런 가래 → 콧물 E_182 등)는 의미 규칙으로만 막음 · 실제 ASR 전사문 미평가.
""", encoding="utf-8")
    files = sorted([p for d in (S.DATA, S.OUT, S.DOCS, S.STEP / "scripts", S.STEP / "tests") for p in d.glob("*") if p.is_file()] + [S.STEP / "run_all.sh"])
    S.dump_json(S.OUT / "manifest.json", {"files": {str(p.relative_to(S.STEP)): S.sha256(p) for p in files if p.name != "manifest.json" and p.exists()},
                                          "note": "manifest.json 자신 제외. latency.json·memory.json 은 실행마다 값이 다름"})
    print(S.dumps({k: out[k] for k in ("STEP29_3_RESULT", "STEP30_READINESS", "SELECTED_POLICY", "hard_gates", "performance")}))


if __name__ == "__main__":
    main()
