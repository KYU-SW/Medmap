# 01 연구 기준선(PHASE 1, 읽기 전용 확인 결과)

| 대상 | 실제 계약(로컬 코드 확인) | 분류 | 이번 사용 |
|---|---|---|---|
| v4 PE 카탈로그 | hybrid4.graphs.normalized_relations(): relation dict + logic.Structured(gates·required·alternatives·fallbacks·unconditional) | REUSABLE | Shadow 카탈로그를 같은 형식으로 별도 생성 |
| v4 방향 판단 | hybrid4.logic.decide(Structured, facts) — HOLD/BLOCK_ONLY_IF_TRUE 게이트, 경로 OR | REUSABLE | 그대로 호출 |
| v4 임상 조건 | hybrid4.reason.evaluate_one(ev, norm, h, agg, …) — 임상 단계(phase_fact)·D-dimer 문장 조건 | REUSABLE | 세계(확률 값)별로 호출 |
| v4 관계 조회·입력 | Reasoner(relations, mode).find_relations / episode_inputs(graph=DiseaseKG 순회, flat=FlatRuleTable·행 필터) | REUSABLE | Shadow 카탈로그로 인스턴스 생성 |
| v4 맥락 집계 | graphs.aggregate_facts — 에피소드 전체 값 합침(시각·도구 무시) | NEEDS_EXTENSION | 확률 관측(값·도구·시각) 보존 + 해석 세계 |
| v5-1 K-of-N·분류 | hybrid5.logic.eval_kofn, classification.criterion_facts_* / pericarditis_classification | REUSABLE | 심낭염 정책 A/B/C, STRICT 임상 양상 |
| v5-2A 비교 | PatientGraph52.compare / collect, evidence_linker.catalog | REUSABLE | MI·심낭염 연구 분류, 다질환 비교 |
| v5-2A.1 그룹화 | grouping.build_groups, conflict.mark_conflicts, lineage | REUSABLE | Shadow 원시 판단 그룹화 |
| v5-2A.2 시간·정정 | PatientGraph522(input_log), counterfactual.replay/fixed_context, event_history.resolve_events | REUSABLE | 정정 가상 비교·사건 해석 |
| v5-2B-P0 자료 | relation_review.json(인용 25건), condition_matrix.csv(33행), 반례 28 | REUSABLE | Shadow 출처·사전 등록 기대값 |
| ESC 2019 Table 4 행 구조 | 평탄화된 표 — 'And' 연결어는 있으나 행 배정이 발췌마다 다름(2026-11-09 재확인) | SOURCE_UNVERIFIED | 활력징후 조합 판정 안 함 |
| 입원·임신·항응고·YEARS·2단계 | v3 미추출 | RESEARCH_ONLY | 연구용 정규식(같은 기록 원문) |
| 혈역학 미기록·확률 재평가·등급→방향 | 원문 처리 문구 없음 | CLINICAL_REVIEW_REQUIRED | 정책 변수로 분리 |
