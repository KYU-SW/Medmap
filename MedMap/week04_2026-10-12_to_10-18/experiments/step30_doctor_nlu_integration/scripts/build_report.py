"""docs/step30_report.md 생성 — 숫자는 모두 outputs/ 파일에서 읽는다(손으로 쓰지 않음)."""
from __future__ import annotations

import collections

import s30_common as S


def r(x):
    v = x["value"]
    return f"{v} ({x['numerator']}/{x['denominator']})" if v is not None else f"없음 (0/{x['denominator']})"


def main():
    v = S.load_json(S.OUT / "integration_verdict.json")
    core = S.load_json(S.OUT / "evaluation_core.json")
    av = S.load_json(S.OUT / "adapter_validation.json")
    wf = S.load_json(S.OUT / "workflow_safety.json")
    lat = S.load_json(S.OUT / "latency.json")
    mem = S.load_json(S.OUT / "memory.json")
    prot = S.load_json(S.OUT / "protected_check.json")
    lic = S.load_json(S.OUT / "license_scan.json")
    tests = S.load_json(S.OUT / "unit_tests.json")
    pc = S.load_json(S.OUT / "product_contracts.json")
    ov = S.load_json(S.OUT / "case_overlap.json")
    e2e = S.load_json(S.OUT / "end_to_end_cases.json")["cases"]
    gold = S.read_csv(S.OUT / "gold_alignment.csv")
    m, mr, ms = core["metrics_integration_new"], core["metrics_regression_exposed"], core["mapping_summary"]
    cpu = lat["condition_A_low_load"]["pilot274"]
    cpuB = lat["condition_B_concurrent_load"]["pilot274"]["full_pipeline"]
    cats = av["items_by_category"]
    wrong = [g for g in gold if g["category_ok"] == "False"]
    sa_wrong = [g for g in gold if g["expected_stage_a"] == "False" and g["got_stage_a"] == "True"]
    miss = [g for g in gold if g["got_category"] == "NONE" and "NONE" not in g["expected_cats"].split("/")]
    concept_bad = [g for g in gold if g["concept_ok"] == "False"]
    reg_rows = [g for g in gold if g["set"] == "REGRESSION_EXPOSED"]
    reg_ok = sum(1 for g in reg_rows if g["category_ok"] == "True" and g["stage_a_ok"] == "True" and g["concept_ok"] != "False")
    cb = av["confirmation_policy_confirm_all"]
    gates = v["gates"]
    ex = S.load_json(S.OUT / "exploratory_g10_v2.json") if (S.OUT / "exploratory_g10_v2.json").exists() else None
    ex_txt = ("없음" if ex is None else
              f"공식 G10 FAIL 원인 = {ex['cause']}. v2 검사기(질환 예측 키는 어댑터 필드에만, 49질환 코드 값은 전체 검사)를 주입 사례 "
              f"{len(ex['checker_self_test']['rows'])}개로 먼저 확인(오판 {ex['checker_self_test']['misjudged']}) 후 공식 산출물에 적용 → v2 G10 {ex['v2_G10']}"
              f"(위반 {ex['v2_violations_total']}) → EXPLORATORY 판정 {ex['exploratory_STEP30_RESULT']} · STEP31 {ex['exploratory_STEP31_READINESS']}. "
              f"공식 판정은 바꾸지 않음. 교훈: {ex['lesson']}.")

    def lines(rows, n=40):
        return "\n".join(f"| {g['case_id']} | {g['surface']} | {g['expected_cats']} | {g['got_category']} | {g['got_canonical'] or '-'} | {g['got_stage_a']} |" for g in rows[:n]) or "| - | - | - | - | - | - |"

    reg_tbl = "\n".join(
        f"| {c['case_id']} | {c['text']} | " + " · ".join(f"'{it['raw_span']}'={it['category']}{'(STAGE_A ' + str(it['eligibility']['target_evidence']) + ')' if it['eligibility']['eligible'] else ''}"
                                                      for it in c["packet_before_confirmation"]["items"]) + " |"
        for c in e2e if c["set"] == "REGRESSION_EXPOSED")
    blocking = collections.Counter()
    for c in e2e:
        for it in c["packet_before_confirmation"]["items"]:
            if it["category"] == "A" and not it["eligibility"]["eligible"]:
                for b in it["eligibility"]["blocking_reasons"]:
                    blocking[b.split(":")[0]] += 1
    gate_tbl = "\n".join(f"| {k} | {gates[k]} | {v['gate_hit_counts'].get(k, 0)} |" for k in gates)
    txt = f"""# STEP30 — MedMap Clinical NLU ↔ Doctor 연구용 통합 결과

> 연구용 통합 시뮬레이션. 임상 정확도·안전성 검증 아님. 합성 문장, 평가 문장·규칙 작성자 동일, HUMAN_VERIFIED_GOLD = 0, PRODUCTION_READY = NO.
> 의사 확인은 dummy 시뮬레이터(confirmer = DUMMY_SIMULATOR) — 실제 의사 검증으로 세지 않음.

## 판정
- STEP30_RESULT = **{v['STEP30_RESULT']}**
- STEP31_READINESS = **{v['STEP31_READINESS']}**
- PRODUCTION_READY = NO · HUMAN_VERIFIED_GOLD = 0
- NLU_SCHEMA_VALIDITY = {v['NLU_SCHEMA_VALIDITY']}
- DOCTOR_ADAPTER_VALIDITY = {v['DOCTOR_ADAPTER_VALIDITY']}
- RAW_PRESERVATION = {v['RAW_PRESERVATION']}
- MODEL_INPUT_ISOLATION = {v['MODEL_INPUT_ISOLATION']}
- SILVER_ISOLATION = {v['SILVER_ISOLATION']}
- NEGATED_INPUT_VIOLATIONS = {v['NEGATED_INPUT_VIOLATIONS']} · HISTORICAL_INPUT_VIOLATIONS = {v['HISTORICAL_INPUT_VIOLATIONS']} · OTHER_PERSON_INPUT_VIOLATIONS = {v['OTHER_PERSON_INPUT_VIOLATIONS']} · UNKNOWN_INPUT_VIOLATIONS = {v['UNKNOWN_INPUT_VIOLATIONS']}
- EVIDENCE_MAPPING_CONFLICTS = {v['EVIDENCE_MAPPING_CONFLICTS']}
- BLIND_WORKFLOW_VIOLATIONS = {v['BLIND_WORKFLOW_VIOLATIONS']}
- MULTI_SPAN_PRESERVATION = {v['MULTI_SPAN_PRESERVATION']}
- END_TO_END_TESTS = {v['END_TO_END_TESTS']}
- CPU_P95 = {v['CPU_P95']}
- 재현성 = {v['reproducibility'].get('status')} {('(다른 파일: ' + ', '.join(v['reproducibility'].get('different', [])) + ')') if v['reproducibility'].get('different') else ''}
- 판정 규칙 = data/prereg_gates.json(평가 전 고정, SHA 는 data/prereg_freeze.json)

## EXPLORATORY(공식 판정 아님) — G10 검사기 재확인
- {ex_txt}

## Integration Safety Gate
| 게이트 | 결과 | 위반 기록 수 |
|---|---|---|
{gate_tbl}

- 위반 수(G3–G7)는 '자동 모델 입력 또는 STAGE_A 표시가 금지 속성에 붙은 경우'를 NLU 원본 속성으로 다시 센 값 + '전부 확인' dummy 정책에서 B·G·H·미지원·C·D·E·F 항목이 재분류 사유 없이 STAGE_B 가 된 경우.
- 자동 모델 입력은 구조상 0: 모든 사례 `model_input.applied=false`, 의사 확인 전 `stage_b`·`patient_state_delta` 비어 있음(G9).

## 성능(분모 명시)
### 새 통합 평가 {m['cases']}문장(INTEGRATION_NEW, 이전 단계 data 와 완전 일치 0 — 비교 문자열 {ov['prior_unique_strings']}개)
- 정상 증상 전달률 = {r(m['normal_transfer_rate'])} — 분모 = STAGE_A 기대 항목
- 불필요한 확인 요청률 = {r(m['unnecessary_confirmation_rate'])} — 같은 분모에서 F 로 가거나 A 인데 STAGE_A 가 막힘
- 누락률 = {r(m['missing_rate'])} — 분모 = '없음' 허용이 아닌 기대 항목
- 잘못된 범주 표시율 = {r(m['wrong_display_rate'])} — 분모 = 대응 item 이 있는 기대 항목
- 문맥(부정·과거·다른 사람) 보존율 = {r(m['context_preservation_rate'])}
- STAGE_A 표시 오류(기대 금지인데 STAGE_A + forbid 위반) = {m['stage_a_marking_errors']} · 범주 A 인데 기대 concept 와 다름 = {m['concept_mismatch_on_A']}
- 기대 구문과 겹치지 않는 추가 item(범주별) = {m['extra_items_by_category']} · 그중 STAGE_A = {len(m['extra_items_stage_a'])}
### 노출 회귀 {mr['cases']}문장(지시문 §11 — 독립 평가 아님)
- 기대 항목 {len(reg_rows)}개 중 범주·STAGE_A·concept 모두 맞음 {reg_ok} · 정상 전달률 {r(mr['normal_transfer_rate'])} · STAGE_A 표시 오류 {mr['stage_a_marking_errors']}

| 사례 | 문장 | item(범주, STAGE_A 대상) |
|---|---|---|
{reg_tbl}

### 기대와 다른 범주(전체 세트)
| 사례 | 기대 구문 | 허용 범주 | 결과 범주 | concept | STAGE_A |
|---|---|---|---|---|---|
{lines(wrong)}

### STAGE_A 금지 기대인데 STAGE_A 로 표시된 항목
| 사례 | 기대 구문 | 허용 범주 | 결과 범주 | concept | STAGE_A |
|---|---|---|---|---|---|
{lines(sa_wrong)}

### 누락(대응 item 없음)
| 사례 | 기대 구문 | 허용 범주 | 결과 범주 | concept | STAGE_A |
|---|---|---|---|---|---|
{lines(miss)}

### 범주 A 인데 기대 concept 와 다름
| 사례 | 기대 구문 | 허용 범주 | 결과 범주 | concept | STAGE_A |
|---|---|---|---|---|---|
{lines(concept_bad)}

## 처리 시간·메모리(CPU, OMP {lat.get('omp_num_threads')}, GPU 미사용)
- 조건 A(저부하, load {lat['condition_A_low_load']['loadavg_1m_before']}) pilot {cpu['full_pipeline']['n']}: NLU(core3) p95 {cpu['nlu_core3']['p95_ms']} ms · 검색 계층 p95 {cpu['retrieval_cpr_b4']['p95_ms']} ms · 통합 어댑터 p95 {cpu['integration_adapter']['p95_ms']} ms · JSON 직렬화 p95 {cpu['json_serialization']['p95_ms']} ms · 전체 p50 {cpu['full_pipeline']['p50_ms']} / p95 {cpu['full_pipeline']['p95_ms']} ms
- 조건 B(이 스크립트의 CPU 바쁜 루프 2개, load {lat['condition_B_concurrent_load']['loadavg_1m_during']}) 전체 p50 {cpuB['p50_ms']} / p95 {cpuB['p95_ms']} ms
- 초기 로딩 {[val for k, val in lat.items() if k.startswith('init_load_ms')][0]} ms · RSS 로딩 뒤 {mem['rss_after_init_mib']} MiB · 최대(VmHWM) {mem['peak_rss_hwm_mib']} MiB
- {lat['step29_3_reference']}. 병원 운영 성능 검증 아님.

## 기존 evidence 연결(§7)
- 기존 77 concept 중 변환 규칙 허용 {ms['existing_concepts_with_allowed_conversion']} · 변환 안 함 {len(ms['existing_concepts_without_conversion'])}({', '.join(ms['existing_concepts_without_conversion'])})
- inventory 가 가리키는 evidence {ms['evidence_ids_in_inventory']}개 / 카탈로그 {ms['catalog_evidence_total']}개 중 양성 변환 대상 {ms['evidence_ids_convertible']}개(1 evidence = 1 concept, 충돌 {len(ms['G8_conflicts'])})
- 통증 부위(E_55)·성상·강도 같은 값 질문은 변환하지 않음(의사 확인 필요). 신규·하위 SILVER concept 은 관련 evidence 가 있어도 변환 안 함(코피 → E_178 금지).
- 변환표는 엔지니어링 초안 — validation_status = ENGINEERING_DRAFT_UNVERIFIED(의사 검증 0).

## 최종 보고 질문(§19)
1. **NLU 결과를 Doctor 용 데이터로 정상 변환할 수 있는가?** — 구조 변환은 {('가능' if gates['G1'] == gates['G2'] == gates['G13'] == 'PASS' else '문제 있음')}: 사례 {av['cases']}, NLU mention {av['nlu_mentions']}개가 packet item 으로 빠짐없이 옮겨졌고(스키마 위반 {av['schema_violations_total']}) NLU 원본은 item 마다 그대로 보존. 필수 필드 중 mapping_status·provenance·uncertainty_reason 은 NLU 에 없어 어댑터가 만든다. 내용 정확도는 NLU 품질에 묶임(아래 11).
2. **기존 77 증상과 신규 SILVER 를 구별해 표시하는가?** — 범주 A(기존 지원) {cats.get('A', 0)} · B(새 표준 후보) {cats.get('B', 0)}. B 는 '새로운 표준 증상 후보(모델 미사용)' 칸에 따로 표시되고 STAGE_A·STAGE_B 모두 될 수 없음(G3 {gates['G3']}).
3. **부정 증상은 모델 입력에서 격리되는가?** — 예(위반 {v['NEGATED_INPUT_VIOLATIONS']}). 범주 C {cats.get('C', 0)}건은 STAGE_A 0, '없음 확인'을 해도 음성 evidence 로 바꾸지 않음. 의사가 '있음'으로 바꾸려면 재분류 사유가 필요(변이 확인 중 NLU 가 ABSENT 를 eligible·NEGATIVE 로 주는 것을 발견해 STAGE_A 에 양성 조건 추가).
4. **과거·해소 증상은 현재 양성과 분리되는가?** — 예(위반 {v['HISTORICAL_INPUT_VIOLATIONS']}). 범주 D {cats.get('D', 0)}건, 사건 시점·해소 상태를 그대로 표시. 다만 '토했어요'처럼 과거형 단독 문장도 D 가 되므로 진료 당일 현재 증상인지는 의사가 확인해야 함.
5. **가족 증상이 환자 증상으로 잘못 쓰이지 않는가?** — 자동 입력 위반 {v['OTHER_PERSON_INPUT_VIOLATIONS']}. 범주 E {cats.get('E', 0)}건. 주체가 MULTIPLE 이면 F(확인 필요)로 보냄. NLU 가 주체를 놓친 경우는 범주가 A 로 표시될 수 있음(11 참고).
6. **UNKNOWN·UNCERTAIN 은 어떻게 표시되는가?** — '추가 확인 필요' 칸(F {cats.get('F', 0)} · H {cats.get('H', 0)})에 원문 위치와 사유(가드·부위만·확실성 낮음 등)와 함께 표시, STAGE_A 불가(위반 {v['UNKNOWN_INPUT_VIOLATIONS']}).
7. **기존 223 evidence 와 연결 가능한 증상은?** — 77 concept 중 {ms['existing_concepts_with_allowed_conversion']}개가 evidence {ms['evidence_ids_convertible']}개(카탈로그 {ms['catalog_evidence_total']}개 중)로 양성 1:1 변환 가능. 나머지는 일반형 질문이 없거나 값 질문.
8. **의사 확인 이전에 자동 모델 입력이 발생하는가?** — 아니오. 모든 사례 applied=false, 자동 입력 0(G9 {gates['G9']}). STAGE_A {av['stage_a_items']}건은 표시만.
9. **블라인드 working diagnosis 흐름이 유지되는가?** — 제품 doctor_view 를 in-process 로 호출한 시뮬레이션에서 위반 {wf['violations_total']}(사례 {wf['cases']}): working diagnosis 입력 전 질환 후보·다음 질문 LOCKED, 확인 단계가 working diagnosis 를 바꾸지 않음, 공개 단계 모델 입력 = STAGE_B 확인 evidence 만. 연구 packet·Preview 에 질환 이름·점수·순위 없음.
10. **확인 전후 차이를 추적할 수 있는가?** — 예. apply_decisions 가 항목별 confirmation 변경과 patient_state_delta 추가를 diff(확인자·순서 포함)로 남기고 입력 packet 은 바꾸지 않음. Preview F 칸에 표시.
11. **기존 NLU 오류가 화면·모델 입력에 주는 영향** — 자동 모델 입력에는 영향 없음(입력 자체가 없음). 화면에는 그대로 전파: 기대와 다른 범주 {len(wrong)}건, STAGE_A 금지 기대인데 STAGE_A 표시 {len(sa_wrong)}건, 누락 {len(miss)}건, concept 다름 {len(concept_bad)}건(전체 세트). 의사가 STAGE_A 를 그대로 확인하면 잘못된 입력이 될 수 있으므로 STAGE_B 는 원문 대조 확인이 전제. '전부 확인' 오클릭 시나리오에서도 B·G·H·C·D·E·F 는 막힘(item {cb.get('confirm_all_items')} 중 STAGE_B {cb.get('confirm_all_stage_b')}).
12. **제품을 수정하지 않고 전체 흐름을 재현했는가?** — 예(G11 {prot['G11']}): master {prot['product_head_after'][:7]} 그대로, 제품 파일 {prot['product_files_checked']}개·연구 원본 {prot['research_files_checked']}개 SHA 동일, 서버 PID 동일({prot['servers_after']}). 재현 2회 = {v['reproducibility'].get('status')}.
13. **실제 제품 연결을 위해 필요한 변경** — docs/step31_handoff.md: (a) Doctor 화면에 'AI 추출 후보' 영역과 항목별 확인 UI(있음·없음·보류 + 재분류 사유) (b) 확인 결과를 PatientState 로 넣는 경로 — 현재 세션은 exact-k 시작 계약이 있어 추가 관측을 넣으면 model_context_match 가 깨짐(제품 정책 결정 필요) (c) 변환표의 의사 검토 (d) 서버 측 NLU 실행 위치·메모리(RSS {mem['rss_after_init_mib']} MiB) (e) 실제 ASR 전사문 평가 (f) 음성 evidence 정책.
14. **STEP31 연구용 제품 연동 실험을 시작할 수 있는가?** — 공식 {v['STEP31_READINESS']}(G10 검사기 오탐으로 REGRESSION). EXPLORATORY 재확인 기준 {ex['exploratory_STEP31_READINESS'] if ex else '없음'} — 다만 NLU 의미 오류가 STAGE_A 표시로 전파되는 문제(11)가 남아 있어 그대로 진행하기보다 사용자 결정 필요. 사용자 승인 전 시작하지 않음.

## 보호·라이선스
- G11 {prot['G11']} · G12 {lic['G12']}(검사 파일 {lic['files_scanned']}, 제한 ID 값 {lic['restricted_tokens_checked']}개 대조, 일치 {lic['n_hits']}, 네트워크 import {len(lic['network_imports'])}). 외부 LLM·API·다운로드·설치·재학습 없음. commit/push 없음.
- 제품: {pc['git_branch']} {pc['git_head'][:7]} · 서버 상태만 확인 {pc['servers']['listen']}.
- 단위 테스트 {tests['tests_run']}개 {'PASS' if tests['PASS'] else 'FAIL'} — 변이 확인 기록 logs/mutation_check_20261014.md.

## 한계
- 합성 문장만, 평가 문장·기대값·규칙 작성자가 같음(Claude 세션) — 사람 검증 0. 노출 회귀 10문장은 독립 평가 아님.
- 기대값의 허용 범주는 작성자 판단(예: '목이 아프고'를 인후통·통증 모두 허용). 실제 ASR 전사문 미평가.
- dummy 확인 정책 2개만 시험(STAGE_A 만 확인 / 전부 확인). 실제 의사 행동·UI 사용성은 미검증.
- 변환표(77 concept → evidence)는 질문 원문 기준 엔지니어링 초안 — 의사 검증 0.
"""
    (S.DOCS / "step30_report.md").write_text(txt, encoding="utf-8")
    print("report written", len(txt))


if __name__ == "__main__":
    main()
