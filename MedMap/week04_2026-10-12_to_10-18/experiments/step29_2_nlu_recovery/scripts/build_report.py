"""STEP29.2 판정·보고서·manifest 생성. 숫자는 모두 outputs/·data/ 파일에서 읽는다(손으로 쓰지 않음). 판정 규칙 = gates.py(평가 전 고정).
출력: outputs/{step29_2_verdict.json, manifest.json} · docs/{step29_2_report.md, step30_readiness.md, step30_handoff.md}"""
from __future__ import annotations

import json

import s292_common as S
from evaluate_nlu import prereg_ok
from gates import __doc__ as GATES_DOC
from gates import verdict


def fmt(x):
    return "없음" if x is None else (f"{x:.4f}" if isinstance(x, float) else str(x))


def main():
    ev = S.load_json(S.OUT / "eval_summary.json")
    M = ev["metrics"]
    evalv = S.load_json(S.OUT / "evaluator_validation.json")
    pre = S.load_json(S.DATA / "prereg_gates.json")
    pf = S.load_json(S.DATA / "policy_freeze.json")
    sel = pf["SELECTED_POLICY"]
    protect = S.load_json(S.OUT / "protected_check.json")
    lat = S.load_json(S.OUT / "latency.json")
    st = prereg_ok(True)
    st["evaluator_validation_same"] = S.sha256(S.OUT / "evaluator_validation.json") == pre["evaluator_validation_sha256"]
    st["eval_summary_prereg_status"] = all(v for k, v in ev["prereg_status"].items() if k != "selected_policy")
    V = verdict(M, sel, evalv, protect, lat, st)
    H, X, D = M[sel]["HOLDOUT"], M[sel]["EXPOSED"], M[sel]["DEV"]
    p95 = lat["single_input_cpu"][sel]["p95_ms"]
    out = {
        "STEP29_2_RESULT": V["STEP29_2_RESULT"], "EVALUATOR_V6": evalv["EVALUATOR_V6"],
        "ASR_SENTENCE_SEGMENTATION": f"{H['ASR_SENTENCE_SEGMENTATION']['f1']}(경계 F1, HOLDOUT 마침표 없는 다문장 입력 — tp {H['ASR_SENTENCE_SEGMENTATION']['tp']} · fp {H['ASR_SENTENCE_SEGMENTATION']['fp']} · fn {H['ASR_SENTENCE_SEGMENTATION']['fn']})",
        "PUNCTUATION_PAIR_CONSISTENCY": f"{H['PUNCTUATION_PAIR_CONSISTENCY']}(HOLDOUT 마침표 유무 쌍 {H['punct_pairs_n']})",
        "MULTI_SPAN_RETENTION": f"{H['MULTI_SPAN_RETENTION']}(HOLDOUT 다중 증상 정답 mention {H['multi_n']}) · 노출 pilot {X['pilot_multi_retention']}(분모 {X['pilot_multi_n']})",
        "NEGATION_SCOPE": f"{H['NEGATION_SCOPE']}(HOLDOUT 정렬 mention {H['aligned_n']}) · 노출 pilot assertion {X['pilot_assertion_agreement']}",
        "TEMPORALITY": f"{H['TEMPORALITY']}(HOLDOUT 사건 시점 정답 mention {H['temporality_n']})",
        "RESOLUTION_LINKING": f"{H['RESOLUTION_LINKING']}(HOLDOUT 해소·호전 정답 mention {H['resolution_n']}) · 잘못된 해소 연결 {H['RESOLUTION_FALSE_LINK']}",
        "EXPERIENCER": f"{H['EXPERIENCER']}(HOLDOUT 정렬 mention {H['aligned_n']})",
        "CONCEPT_PRECISION": f"{H['CONCEPT_PRECISION']}(HOLDOUT 시스템 EXISTING mention {H['precision_n']}) · 노출 REGRESSION168 {X['reg_precision']}",
        "CONCEPT_COVERAGE": f"{H['CONCEPT_COVERAGE']}(HOLDOUT 정답 EXISTING mention {H['coverage_n']}) · 노출 REGRESSION168 {X['reg_coverage']}(분모 {X['reg_n']}, 첫 EXISTING 시도 기준)",
        "UNSUPPORTED_AUTO_LINK": f"{H['UNSUPPORTED_AUTO_LINK']}(HOLDOUT 미지원·SILVER·혼동 None case) · 노출 pilot {X['pilot_unsupported_auto']}/{X['pilot_unsupported_n']}",
        "B4_GUARD_CORRECT_BLOCKS": f"HOLDOUT {H['B4_GUARD_CORRECT_BLOCKS']} · 노출 pilot {X['B4_GUARD_CORRECT_BLOCKS(pilot)']}(오답 차단)",
        "B4_GUARD_WRONG_BLOCKS": f"HOLDOUT {H['B4_GUARD_WRONG_BLOCKS']} · 노출 pilot {X['B4_GUARD_WRONG_BLOCKS(pilot)']}(정답 차단, STEP29.1 = 24)",
        "SEMANTIC_VIOLATIONS": f"{H['SEMANTIC_VIOLATIONS']}(HOLDOUT 검사기 v6 위반 입력 / {H['n_inputs']})",
        "RAW_PRESERVATION": f"{H['RAW_PRESERVATION']}(HOLDOUT {H['n_inputs']} 입력) · 전 입력 hard G1 {V['hard_gates']['G1']}",
        "CPU_P95": f"{p95} ms(pilot 274 단일 입력, {sel}) · peak RSS {lat['peak_rss_mib']} MiB",
        "STEP30_READINESS": V["STEP30_READINESS"], "PRODUCTION_READY": "NO", "HUMAN_VERIFIED_GOLD": 0, "SELECTED_POLICY": sel,
        "hard_gates": V["hard_gates"], "recovery_official": V["recovery_official"], "development_targets": V["development_targets"], "gate_inputs": V["gate_inputs"],
        "evaluator_validation": {k: evalv[k] for k in ("known_correct_mentions", "EVALUATOR_FALSE_POSITIVES", "known_bad", "EVALUATOR_FALSE_NEGATIVES")},
        "prereg_status": st, "rules": GATES_DOC,
        "data_classes": "NEW_SYNTHETIC_HOLDOUT(동결 후 1회, 공식) · NEW_SYNTHETIC_DEV(개발·정책 선택) · EXPOSED_REGRESSION(pilot274·계약68·계약42·전향231) · WEAK_EXTERNAL(SILVER442·WEAKNON903). 모두 사람 검증 Gold 아님"}
    S.dump_json(S.OUT / "step29_2_verdict.json", out)
    pols = list(M)
    keys = ["MULTI_SPAN_RETENTION", "CONCEPT_PRECISION", "CONCEPT_COVERAGE", "NEGATION_SCOPE", "EVALUATIVE_NEGATION", "TEMPORALITY", "RESOLUTION_LINKING",
            "RESOLUTION_FALSE_LINK", "EXPERIENCER", "UNSUPPORTED_AUTO_LINK", "PUNCTUATION_PAIR_CONSISTENCY", "SPAN_BOUNDARY_VALIDITY", "SEMANTIC_VIOLATIONS",
            "PROPAGATION_ERRORS", "NEG_POSITIVE", "OTHER_POSITIVE", "OVER_SPLIT", "B4_GUARD_CORRECT_BLOCKS", "B4_GUARD_WRONG_BLOCKS", "CASE_PASS_RATE"]
    tab = lambda st, ks: "\n".join(["| 지표 | " + " | ".join(pols) + " |", "|---" * (len(pols) + 1) + "|"] +  # noqa: E731
                                    [f"| {k} | " + " | ".join(fmt(M[p][st].get(k)) for p in pols) + " |" for k in ks])
    xkeys = ["pilot_multi_retention", "pilot_assertion_agreement", "pilot_temporality_agreement", "pilot_experiencer_agreement", "reg_precision", "reg_coverage",
             "pilot_unsupported_auto", "pilot_wrong_concept_mentions", "B4_GUARD_CORRECT_BLOCKS(pilot)", "B4_GUARD_WRONG_BLOCKS(pilot)", "C29_failed", "NEW42_pass",
             "PROS231_pass", "G5_exposed", "G6_exposed", "G7_mentions", "G10_mentions"]
    seg = "\n".join(f"| {p} | {M[p]['HOLDOUT']['ASR_SENTENCE_SEGMENTATION']['f1']} | {M[p]['HOLDOUT']['ASR_SENTENCE_SEGMENTATION']['precision']} | "
                    f"{M[p]['HOLDOUT']['ASR_SENTENCE_SEGMENTATION']['recall']} |" for p in pols)
    meta = "\n".join(f"| {k} | " + " | ".join(str(M[p]["HOLDOUT"]["metamorphic"].get(k)) for p in pols) + " |" for k in M[sel]["HOLDOUT"]["metamorphic"])
    cats = "\n".join(f"| {k} | " + " | ".join(str(M[p]["HOLDOUT"]["by_category_pass"].get(k)) for p in pols) + " |" for k in M[sel]["HOLDOUT"]["by_category_pass"])
    sel_rows = "\n".join(f"| {r['policy']} | {r['eligible']} | {r['score_cov']} | {r['score_prec']} |" for r in pf["selection_rows"])
    errs = S.load_json(S.OUT / "error_summary.json")["selected_holdout_examples"]
    exs = "\n".join(f"- **{t}** ({len(v)}건 표시): " + " / ".join(f"`{e['text']}` → {e.get('got')}" for e in v[:4]) for t, v in errs.items())
    gates = " · ".join(f"{k} {v}" for k, v in V["hard_gates"].items())
    rec = " · ".join(f"{k} {v}" for k, v in V["recovery_official"].items())
    dev = " · ".join(f"{k} {v}" for k, v in V["development_targets"].items())
    tests = S.load_json(S.OUT / "unit_tests.json")
    nt = sum(v["tests"] for v in tests["by_file"].values())
    nf = sum(v["failures"] + v["errors"] for v in tests["by_file"].values())
    hd = json.loads((S.DATA / "frozen_holdout_pairs.json").read_text(encoding="utf-8"))
    dv = json.loads((S.DATA / "dev_pairs.json").read_text(encoding="utf-8"))
    rep = f"""# STEP29.2 — MedMap Clinical NLU Recovery & ASR Robustness 보고서

이 문서의 숫자는 build_report.py 가 outputs/ 에서 읽어 생성(손으로 쓰지 않음).

## 판정
- **STEP29_2_RESULT = {V['STEP29_2_RESULT']}** · **STEP30_READINESS = {V['STEP30_READINESS']}** · PRODUCTION_READY = NO · HUMAN_VERIFIED_GOLD = 0
- 선택 정책(DEV + 노출 pilot 만으로 사전 규칙 선택, HOLDOUT 미사용) = **{sel}**
- Hard: {gates}
- Recovery(공식, HOLDOUT 같은 입력 비교): {rec}
- 개발 목표(노출 자료의 STEP29 절대 수치): {dev}
- EVALUATOR_V6 = {evalv['EVALUATOR_V6']}(정상 {evalv['known_correct_mentions']} 오판 {evalv['EVALUATOR_FALSE_POSITIVES']} · 위험 {evalv['known_bad']} 누락 {evalv['EVALUATOR_FALSE_NEGATIVES']} · 같은 세트 v5 오판 {evalv['v5_on_same_set']['false_positive']}·누락 {evalv['v5_on_same_set']['false_negative']})
- STEP29.1 공식 REGRESSION 판정은 그대로 유지(이 단계는 별도 실험).

## 데이터(모두 합성 — 사람 검증 Gold 아님)
- HOLDOUT {hd['n_cases']} 입력(마침표 쌍 {hd['n_pairs']} 묶음, 범주 {hd['by_category']}) — 동결 후 1회 실행. DEV {dv['n_cases']} 입력 — 개발·정책 선택.
- 생성: 의미 구조(슬롯) → 문장. DEV/HOLDOUT 은 연결 틀·문맥 어휘·증상 조합이 분리(누수 검사 {hd['split_leak_check']['text']} 문자열·{hd['split_leak_check']['struct_key']} 증상 조합 겹침,
  증상 표현을 자리표시로 바꾼 일반 나열형 틀 {len(hd['split_leak_check']['template(증상 표현 → <S> 치환 후 동일)'])}종은 양쪽에 있으나 의미 구조(부정·시점 슬롯)는 다름).
- 기존 노출 자료와 문자열 중복 제외({hd['dropped']['exposed_duplicate']}건). 노출 회귀: pilot 274 · STEP29 계약 68 · STEP29.1 계약 42 · 전향적 231.
- 개발 중 HOLDOUT 문장 노출: 단위 테스트 입력 2개('회전성 어지럼증이 있어요'·'기침이 나요 머리는 괜찮아요' — 지시문 예시와 같은 문장)가 HOLDOUT 과 겹쳐 개발 중 실행됨 → 동결 전 다른 문장으로 교체, 이 두 출력으로 규칙을 바꾸지 않음.

## HOLDOUT 정책 비교(같은 입력)
{tab('HOLDOUT', keys)}

문장 분리(마침표 없는 다문장 입력의 내부 경계):

| 정책 | F1 | precision | recall |
|---|---|---|---|
{seg}

Metamorphic(통과/대상):

| 관계 | {' | '.join(pols)} |
|---{'|---' * len(pols)}|
{meta}

범주별 case 통과:

| 범주 | {' | '.join(pols)} |
|---{'|---' * len(pols)}|
{cats}

## 노출 회귀 세트(STEP29.1 과 같은 정의, legacy view)
{tab('EXPOSED', xkeys).replace('| 지표 |', '| 지표(노출) |')}

## DEV(개발 세트)
{tab('DEV', keys)}

## 정책 선택(gates.select_policy, 평가 전 고정 규칙)
| 정책 | 자격 | DEV coverage + REG coverage | DEV precision + REG precision |
|---|---|---|---|
{sel_rows}

## 선택 정책의 HOLDOUT 오류 사례(유형별 일부)
{exs if exs else '- 없음'}

## 지연·메모리
- outputs/latency.json(실행마다 값이 조금 다름 — 재현 SHA 비교 대상 아님). 판정 R8 은 그 파일의 {sel} p95 사용.

## 재현·보호
- 단위 테스트 {nt}개 · 실패 {nf} · 테스트 입력과 HOLDOUT 겹침 {len(tests['test_strings_in_holdout'])}(기대값 문자열 포함 표시: {tests['test_strings_in_holdout']})
- 보호 확인 G8 = {protect.get('G8')}(기존 연구 {protect.get('n_files')} 파일·제품 저장소 HEAD 동일)
- 사전 고정: prereg_gates {pre['frozen_at']} · policy_freeze {pf['frozen_at']}

## 해석 주의
- 모든 정답은 합성 템플릿 슬롯 정답. 실제 환자·실제 전사문 성능 아님. 임상 정확도 주장 없음.
- REGRESSION168 coverage 는 '첫 EXISTING 연결 시도' 비율(정답 여부 무관) — 오답을 막으면 낮아진다. HOLDOUT CONCEPT_COVERAGE 는 정답 concept 기준.
- 검색기(P5) 단계 모호성('토했'의 구토/토혈 충돌, '목이 아프고' 미연결 등)은 이번 범위(P5 수정 금지) 밖 — 남은 오류의 주 원인.
"""
    (S.DOCS / "step29_2_report.md").write_text(rep, encoding="utf-8")
    ready = f"""# STEP30 진입 판정(STEP29.2 기준)

- STEP30_READINESS = **{V['STEP30_READINESS']}** · STEP29_2_RESULT = {V['STEP29_2_RESULT']} · PRODUCTION_READY = NO
- 규칙: GO_FOR_RESEARCH = RECOVERY_PASS AND 개발 목표 D1–D5 · CONDITIONAL_GO = hard 전부 AND R1·R2·R3 AND 결과 ≠ REGRESSION · NO_GO = 그 외
- Hard: {gates}
- Recovery: {rec}
- 개발 목표: {dev}
- STEP30 은 연구용 연결 설계부터이며 자동 실행하지 않는다(사용자 승인 필요). 제품 적용 판정은 없다.
"""
    (S.DOCS / "step30_readiness.md").write_text(ready, encoding="utf-8")
    hand = f"""# STEP30 인계(연구용 연결 설계 입력)

- 진입점: `exp/step29_2_nlu_recovery/scripts/nlu_pipeline_v3.py` 의 `analyze(text, "{sel}")` — mention 스키마는 docs/nlu_interface_v3.md.
- 판정: STEP29_2_RESULT = {V['STEP29_2_RESULT']} · STEP30_READINESS = {V['STEP30_READINESS']}. 제품·PatientState·49질환 모델 연결 금지(model_input.applied = false 표시만).
- 남은 위험: 검색기(P5) 단계 concept 모호성 · 합성 평가뿐(사람 검증 0) · B4 단독 연결 정책 선택 결과({sel}) · 실제 ASR 전사문 미평가.
- 다음 후보(사용자 결정): 실제 전사문 소량 확보·사람 검토 / 검색기 모호성 수정 실험 / STEP30 연구용 인터페이스 설계.
"""
    (S.DOCS / "step30_handoff.md").write_text(hand, encoding="utf-8")
    files = sorted([p for d in (S.DATA, S.OUT, S.DOCS, S.STEP / "scripts", S.STEP / "tests") for p in d.glob("*") if p.is_file()] + [S.STEP / "run_all.sh"])
    S.dump_json(S.OUT / "manifest.json", {"files": {str(p.relative_to(S.STEP)): S.sha256(p) for p in files if p.name != "manifest.json" and p.exists()},
                                          "note": "manifest.json 자신 제외. 재현 확인 = run_twice.sh(결과 파일 SHA 비교)"})
    print(S.dumps({k: out[k] for k in ("STEP29_2_RESULT", "STEP30_READINESS", "SELECTED_POLICY", "hard_gates", "recovery_official", "development_targets")}))


if __name__ == "__main__":
    main()
