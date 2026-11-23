# MedMap Hybrid v3 — 의료 문맥 추출 · 개념 연결 · 그래프 기반 근거 재평가(PE 파일럿)

기술 기능 검증 기록이다. 합성 기록·노출 문장 사용, 임상 성능 검증 아님. 판단은 확률이 아니며 의사 확인 대상.

## 구성(실제 구현)
- `hybrid3/concepts.py`: P2 parser·lexicon·finding_state 재사용 + 하위형(SSPE·재발 PE·근위부 DVT)·치료(항응고·혈전용해)·CTPA 변형, 문서 약어 정의, 용어 목록 구간 제외, 사전 밖 검사명 '지원 안 함' 표시
- `hybrid3/context.py`: 기록 문장에서 임상 확률(명시 범주만)·의심/검사 목적·과거 진단 진술·치료 상태·단계 신호·D-dimer 검사법/기준·혈역학 불안정 추출. 사실마다 value·source_type·extraction_method·certainty·관찰/이용 시각·의사 확인 상태
- `hybrid3/kg.py`: EXP-01b 그래프(읽기 전용) + 덧층(검사 결과 상태 노드·검증 관계 간선). 방향은 '검사 노드 → 결과 상태 → 가설' 경로의 검증 간선 속성으로만
- `hybrid3/reasoner.py`: P2 출처 규칙·단계 판정·가설 대상·D-dimer 조건·관계 적용 재사용, 보류 원인 A~E 분류, 시간순 Case(v1 시간 정책), 템플릿 설명
- `knowledge/v3_graph_overlay.json`: 덧층 정의. 방향 간선은 P2 카탈로그(무수정)에서만 생성. 새 의학 관계 없음. 혈역학 불안정 제외 조건은 기존 Figure 5 인용 범위

## 보존 확인
- P2 코드 = P2 종료 시 차이 파일과 동일(P1 대비 diff 재생성 비교): same
- 원본·P1 코드/결과/문서 해시: 28/28 일치
- 1차 동결 사본: 5/5 일치
- 2차 동결 코드(FREEZE.json): 일치
- v2 테스트 전체(각 패키지 기준): Ran 124 tests in 2.758s OK
- git commit: 없음
- v3 시작(11-06 10:36) 이후 v2 폴더 변경 파일 수: 0
- v3 시작 이후 다른 실험 폴더 변경 파일 수: 0

## 그래프 기여(ablation, 출력 단위)
| 조건 | 바뀐 출력 | 방향 판단(전→후) |
|---|---|---|
| no_verified_relations | 18 | 8→0 |
| without_PE-CTPA-POSITIVE | 8 | 8→4 |
| without_PE-CTPA-NEGATIVE | 6 | 8→5 |
| without_base_graph | 18 | 8→0 |

- 전체 그래프 통계: {'nodes': 105, 'overlay_nodes': 11, 'edges_v3': {'HAS_RESULT_STATE': 8, 'DESCRIBES_FINDING': 2, 'SUPPORTS_HYPOTHESIS': 2, 'WEAKENS_HYPOTHESIS': 3, 'EVALUATES_HYPOTHESIS': 1, 'UNCERTAIN_RELATIONSHIP': 1, 'ASSOCIATED_WITH': 1}, 'verified_direction_edges': 8, 'disabled_relations': [], 'base_graph': True}
- 기존 그래프 SUGGESTS·공출현 간선은 표시 전용(used_for_direction=False). 기존 그래프가 판단에 주는 것은 가설·검사 노드 존재(범위)와 표시용 연관. 방향은 덧층 검증 간선에서 나옴

## P2 기본 경로(맥락 입력 없음)로 같은 사례 문서 처리: {'ABSTAIN': 29, 'INSUFFICIENT_EVIDENCE': 12, 'NOT_APPLICABLE': 3, 'UNCERTAIN': 1}

## End-to-End 사례
### CASE01_suspected_positive_ctpa @ 5.0
- 가설별 요약: {'Pulmonary embolism|E1': {'status': 'WORKING_DIAGNOSIS', 'kind': 'CURRENT_EVALUATION', 'support': ['PE-CTPA-POSITIVE'], 'weaken': [], 'held': ['SUSPICION_STATEMENT_USED_AS_CONTEXT'], 'review_candidate': False}}
- 추출 맥락: {'pretest': {'value': 'INTERMEDIATE', 'status': 'FOUND', 'from': ['n1']}, 'suspected': {'value': True, 'status': 'FOUND', 'from': ['n1']}, 'ddimer_assay': {'value': None, 'status': 'NOT_FOUND', 'from': []}, 'ddimer_cutoff': {'value': None, 'status': 'NOT_FOUND', 'from': []}, 'haemodynamic_instability': {'value': False, 'status': 'FOUND', 'from': ['n1']}, 'phase_signals': []}
  - E1 n1 `Pulmonary embolism` UNCERTAIN → **ABSTAIN** SUSPICION_STATEMENT_USED_AS_CONTEXT 부족 ['SUSPICION_STATEMENT_USED_AS_CONTEXT(NOT_A_GAP)']
  - E1 r1 `pulmonary embolism` PRESENT → **SUPPORT** PE-CTPA-POSITIVE
### CASE02a_suspected_negative_ctpa @ 5.0
- 가설별 요약: {'Pulmonary embolism|E1': {'status': 'WORKING_DIAGNOSIS', 'kind': 'CURRENT_EVALUATION', 'support': [], 'weaken': ['PE-CTPA-NEGATIVE'], 'held': ['SUSPICION_STATEMENT_USED_AS_CONTEXT'], 'review_candidate': True}}
- 추출 맥락: {'pretest': {'value': 'INTERMEDIATE', 'status': 'FOUND', 'from': ['n1']}, 'suspected': {'value': True, 'status': 'FOUND', 'from': ['n1']}, 'ddimer_assay': {'value': None, 'status': 'NOT_FOUND', 'from': []}, 'ddimer_cutoff': {'value': None, 'status': 'NOT_FOUND', 'from': []}, 'haemodynamic_instability': {'value': False, 'status': 'FOUND', 'from': ['n1']}, 'phase_signals': []}
  - E1 n1 `Pulmonary embolism` UNCERTAIN → **ABSTAIN** SUSPICION_STATEMENT_USED_AS_CONTEXT 부족 ['SUSPICION_STATEMENT_USED_AS_CONTEXT(NOT_A_GAP)']
  - E1 r1 `pulmonary embolism` NEGATED → **WEAKEN** PE-CTPA-NEGATIVE
### CASE02b_low_probability_ddimer_conditions_stated @ 3.0
- 가설별 요약: {'Pulmonary embolism|E1': {'status': 'WORKING_DIAGNOSIS', 'kind': 'CURRENT_EVALUATION', 'support': [], 'weaken': ['PE-DDIMER-NORMAL'], 'held': ['SUSPICION_STATEMENT_USED_AS_CONTEXT'], 'review_candidate': True}}
- 추출 맥락: {'pretest': {'value': 'LOW', 'status': 'FOUND', 'from': ['n1']}, 'suspected': {'value': True, 'status': 'FOUND', 'from': ['n1']}, 'ddimer_assay': {'value': 'HIGH_SENSITIVITY', 'status': 'FOUND', 'from': ['l1']}, 'ddimer_cutoff': {'value': 'AGE_ADJUSTED', 'status': 'FOUND', 'from': ['l1']}, 'haemodynamic_instability': {'value': False, 'status': 'FOUND', 'from': ['n1']}, 'phase_signals': []}
  - E1 n1 `Pulmonary embolism` UNCERTAIN → **ABSTAIN** SUSPICION_STATEMENT_USED_AS_CONTEXT 부족 ['SUSPICION_STATEMENT_USED_AS_CONTEXT(NOT_A_GAP)']
  - E1 l1 `D-dimer` PRESENT → **WEAKEN** PE-DDIMER-NORMAL
### CASE02c_ddimer_conditions_missing @ 3.0
- 가설별 요약: {'Pulmonary embolism|E1': {'status': 'WORKING_DIAGNOSIS', 'kind': 'CURRENT_EVALUATION', 'support': [], 'weaken': [], 'held': ['PE-DDIMER-NORMAL', 'SUSPICION_STATEMENT_USED_AS_CONTEXT'], 'review_candidate': False}}
- 추출 맥락: {'pretest': {'value': 'LOW', 'status': 'FOUND', 'from': ['n1']}, 'suspected': {'value': True, 'status': 'FOUND', 'from': ['n1']}, 'ddimer_assay': {'value': None, 'status': 'NOT_FOUND', 'from': []}, 'ddimer_cutoff': {'value': None, 'status': 'NOT_FOUND', 'from': []}, 'haemodynamic_instability': {'value': False, 'status': 'FOUND', 'from': ['n1']}, 'phase_signals': []}
  - E1 n1 `Pulmonary embolism` UNCERTAIN → **ABSTAIN** SUSPICION_STATEMENT_USED_AS_CONTEXT 부족 ['SUSPICION_STATEMENT_USED_AS_CONTEXT(NOT_A_GAP)']
  - E1 l1 `D-dimer` PRESENT → **INSUFFICIENT_EVIDENCE** PE-DDIMER-NORMAL 부족 ['ddimer_assay(B)', 'ddimer_cutoff(B)']
### CASE03_past_pe_followup @ 95.0
- 가설별 요약: {'Pulmonary embolism|E0': {'status': 'CONFIRMED_DIAGNOSIS', 'kind': 'PAST_EPISODE', 'support': [], 'weaken': [], 'held': ['DIAGNOSIS_MENTION_WITHOUT_TEST_SOURCE', 'HISTORICAL_FINDING', 'NO_VERIFIED_RELATION', 'PE-CTPA-NEGATIVE', 'PE-PERFUSION-NORMAL', 'TEST_NAME_WITHOUT_RESULT'], 'review_candidate': False}}
- 추출 맥락: {'pretest': {'value': None, 'status': 'NOT_FOUND', 'from': []}, 'suspected': {'value': None, 'status': 'NOT_FOUND', 'from': []}, 'ddimer_assay': {'value': None, 'status': 'NOT_FOUND', 'from': []}, 'ddimer_cutoff': {'value': None, 'status': 'NOT_FOUND', 'from': []}, 'haemodynamic_instability': {'value': None, 'status': 'NOT_FOUND', 'from': []}, 'phase_signals': ['POST_TREATMENT_FOLLOWUP', 'UNDER_TREATMENT']}
  - E0 n0 `Pulmonary embolism` PRESENT → **ABSTAIN** DIAGNOSIS_MENTION_WITHOUT_TEST_SOURCE 부족 ['DIAGNOSIS_MENTION_WITHOUT_TEST_SOURCE(B)']
  - E0 r9 `pulmonary embolism` NEGATED → **NOT_APPLICABLE** PE-CTPA-NEGATIVE
  - E0 p9 `Perfusion scan` PRESENT → **NOT_APPLICABLE** PE-PERFUSION-NORMAL
  - E0 p9 `pulmonary embolism` PRESENT → **ABSTAIN** DIAGNOSIS_MENTION_WITHOUT_TEST_SOURCE 부족 ['DIAGNOSIS_MENTION_WITHOUT_TEST_SOURCE(B)']
### CASE04_order_only @ 1.5
- 가설별 요약: {'Pulmonary embolism|E1': {'status': 'WORKING_DIAGNOSIS', 'kind': 'CURRENT_EVALUATION', 'support': [], 'weaken': [], 'held': ['NO_RESULT_YET', 'SUSPICION_STATEMENT_USED_AS_CONTEXT'], 'review_candidate': False}}
- 추출 맥락: {'pretest': {'value': 'INTERMEDIATE', 'status': 'FOUND', 'from': ['n1']}, 'suspected': {'value': True, 'status': 'FOUND', 'from': ['n1', 'o1']}, 'ddimer_assay': {'value': None, 'status': 'NOT_FOUND', 'from': []}, 'ddimer_cutoff': {'value': None, 'status': 'NOT_FOUND', 'from': []}, 'haemodynamic_instability': {'value': False, 'status': 'FOUND', 'from': ['n1']}, 'phase_signals': []}
  - E1 n1 `Pulmonary embolism` UNCERTAIN → **ABSTAIN** SUSPICION_STATEMENT_USED_AS_CONTEXT 부족 ['SUSPICION_STATEMENT_USED_AS_CONTEXT(NOT_A_GAP)']
  - E1 o1 `pulmonary embolism` PURPOSE_OR_DIFFERENTIAL → **ABSTAIN** SUSPICION_STATEMENT_USED_AS_CONTEXT 부족 ['SUSPICION_STATEMENT_USED_AS_CONTEXT(NOT_A_GAP)']
### CASE05_late_result_and_correction @ 3.0
- 가설별 요약: {'Pulmonary embolism|E1': {'status': 'WORKING_DIAGNOSIS', 'kind': 'CURRENT_EVALUATION', 'support': [], 'weaken': [], 'held': ['SUSPICION_STATEMENT_USED_AS_CONTEXT'], 'review_candidate': False}}
- 추출 맥락: {'pretest': {'value': 'INTERMEDIATE', 'status': 'FOUND', 'from': ['n1']}, 'suspected': {'value': True, 'status': 'FOUND', 'from': ['n1']}, 'ddimer_assay': {'value': None, 'status': 'NOT_FOUND', 'from': []}, 'ddimer_cutoff': {'value': None, 'status': 'NOT_FOUND', 'from': []}, 'haemodynamic_instability': {'value': False, 'status': 'FOUND', 'from': ['n1']}, 'phase_signals': []}
  - E1 n1 `Pulmonary embolism` UNCERTAIN → **ABSTAIN** SUSPICION_STATEMENT_USED_AS_CONTEXT 부족 ['SUSPICION_STATEMENT_USED_AS_CONTEXT(NOT_A_GAP)']
### CASE05_late_result_and_correction @ 4.0
- 가설별 요약: {'Pulmonary embolism|E1': {'status': 'WORKING_DIAGNOSIS', 'kind': 'CURRENT_EVALUATION', 'support': ['PE-CTPA-POSITIVE'], 'weaken': [], 'held': ['SUSPICION_STATEMENT_USED_AS_CONTEXT'], 'review_candidate': False}}
- 추출 맥락: {'pretest': {'value': 'INTERMEDIATE', 'status': 'FOUND', 'from': ['n1']}, 'suspected': {'value': True, 'status': 'FOUND', 'from': ['n1']}, 'ddimer_assay': {'value': None, 'status': 'NOT_FOUND', 'from': []}, 'ddimer_cutoff': {'value': None, 'status': 'NOT_FOUND', 'from': []}, 'haemodynamic_instability': {'value': False, 'status': 'FOUND', 'from': ['n1']}, 'phase_signals': []}
  - E1 n1 `Pulmonary embolism` UNCERTAIN → **ABSTAIN** SUSPICION_STATEMENT_USED_AS_CONTEXT 부족 ['SUSPICION_STATEMENT_USED_AS_CONTEXT(NOT_A_GAP)']
  - E1 r1 `pulmonary embolism` PRESENT → **SUPPORT** PE-CTPA-POSITIVE
### CASE05_late_result_and_correction @ 6.9
- 가설별 요약: {'Pulmonary embolism|E1': {'status': 'WORKING_DIAGNOSIS', 'kind': 'CURRENT_EVALUATION', 'support': ['PE-CTPA-POSITIVE'], 'weaken': [], 'held': ['SUSPICION_STATEMENT_USED_AS_CONTEXT'], 'review_candidate': False}}
- 추출 맥락: {'pretest': {'value': 'INTERMEDIATE', 'status': 'FOUND', 'from': ['n1']}, 'suspected': {'value': True, 'status': 'FOUND', 'from': ['n1']}, 'ddimer_assay': {'value': None, 'status': 'NOT_FOUND', 'from': []}, 'ddimer_cutoff': {'value': None, 'status': 'NOT_FOUND', 'from': []}, 'haemodynamic_instability': {'value': False, 'status': 'FOUND', 'from': ['n1']}, 'phase_signals': []}
  - E1 n1 `Pulmonary embolism` UNCERTAIN → **ABSTAIN** SUSPICION_STATEMENT_USED_AS_CONTEXT 부족 ['SUSPICION_STATEMENT_USED_AS_CONTEXT(NOT_A_GAP)']
  - E1 r1 `pulmonary embolism` PRESENT → **SUPPORT** PE-CTPA-POSITIVE
### CASE05_late_result_and_correction @ 7.0
- 가설별 요약: {'Pulmonary embolism|E1': {'status': 'WORKING_DIAGNOSIS', 'kind': 'CURRENT_EVALUATION', 'support': [], 'weaken': ['PE-CTPA-NEGATIVE'], 'held': ['SUSPICION_STATEMENT_USED_AS_CONTEXT'], 'review_candidate': True}}
- 추출 맥락: {'pretest': {'value': 'INTERMEDIATE', 'status': 'FOUND', 'from': ['n1']}, 'suspected': {'value': True, 'status': 'FOUND', 'from': ['n1']}, 'ddimer_assay': {'value': None, 'status': 'NOT_FOUND', 'from': []}, 'ddimer_cutoff': {'value': None, 'status': 'NOT_FOUND', 'from': []}, 'haemodynamic_instability': {'value': False, 'status': 'FOUND', 'from': ['n1']}, 'phase_signals': []}
  - E1 n1 `Pulmonary embolism` UNCERTAIN → **ABSTAIN** SUSPICION_STATEMENT_USED_AS_CONTEXT 부족 ['SUSPICION_STATEMENT_USED_AS_CONTEXT(NOT_A_GAP)']
  - E1 r2 `pulmonary embolism` NEGATED → **WEAKEN** PE-CTPA-NEGATIVE
### CASE06_mixed_polarity @ 5.0
- 가설별 요약: {'Pulmonary embolism|E1': {'status': 'WORKING_DIAGNOSIS', 'kind': 'CURRENT_EVALUATION', 'support': ['PE-CTPA-POSITIVE'], 'weaken': [], 'held': ['DVT_NOT_PROXIMAL_ULTRASOUND_CONFIRMED', 'SUSPICION_STATEMENT_USED_AS_CONTEXT', 'TEST_NAME_WITHOUT_RESULT'], 'review_candidate': False}}
- 추출 맥락: {'pretest': {'value': 'INTERMEDIATE', 'status': 'FOUND', 'from': ['n1']}, 'suspected': {'value': True, 'status': 'FOUND', 'from': ['n1']}, 'ddimer_assay': {'value': None, 'status': 'NOT_FOUND', 'from': []}, 'ddimer_cutoff': {'value': None, 'status': 'NOT_FOUND', 'from': []}, 'haemodynamic_instability': {'value': False, 'status': 'FOUND', 'from': ['n1']}, 'phase_signals': []}
  - E1 n1 `Pulmonary embolism` UNCERTAIN → **ABSTAIN** SUSPICION_STATEMENT_USED_AS_CONTEXT 부족 ['SUSPICION_STATEMENT_USED_AS_CONTEXT(NOT_A_GAP)']
  - E1 r1 `deep vein thrombosis` NEGATED → **ABSTAIN** DVT_NOT_PROXIMAL_ULTRASOUND_CONFIRMED 부족 ['DVT_NOT_PROXIMAL_ULTRASOUND_CONFIRMED(B)']
  - E1 r1 `pulmonary embolism` PRESENT → **SUPPORT** PE-CTPA-POSITIVE
### CASE07_synonyms_and_subtype @ 5.0
- 가설별 요약: {'Pulmonary embolism|E1': {'status': 'WORKING_DIAGNOSIS', 'kind': 'CURRENT_EVALUATION', 'support': [], 'weaken': [], 'held': ['PE-CTPA-POSITIVE', 'SUSPICION_STATEMENT_USED_AS_CONTEXT', 'TEST_NAME_WITHOUT_RESULT'], 'review_candidate': False}}
- 추출 맥락: {'pretest': {'value': 'INTERMEDIATE', 'status': 'FOUND', 'from': ['n1']}, 'suspected': {'value': True, 'status': 'FOUND', 'from': ['n1']}, 'ddimer_assay': {'value': None, 'status': 'NOT_FOUND', 'from': []}, 'ddimer_cutoff': {'value': None, 'status': 'NOT_FOUND', 'from': []}, 'haemodynamic_instability': {'value': False, 'status': 'FOUND', 'from': ['n1']}, 'phase_signals': []}
  - E1 n1 `Pulmonary embolism` UNCERTAIN → **ABSTAIN** SUSPICION_STATEMENT_USED_AS_CONTEXT 부족 ['SUSPICION_STATEMENT_USED_AS_CONTEXT(NOT_A_GAP)']
  - E1 r1 `subsegmental pulmonary embolism` PRESENT → **UNCERTAIN** PE-CTPA-POSITIVE 부족 ['PE-CTPA-POSITIVE(E)']
  - E1 r1 `SSPE` PRESENT → **UNCERTAIN** PE-CTPA-POSITIVE 부족 ['PE-CTPA-POSITIVE(E)']
  - E1 r1 `SSPE` PRESENT → **UNCERTAIN** PE-CTPA-POSITIVE 부족 ['PE-CTPA-POSITIVE(E)']
### CASE08_unsupported @ 4.0
- 가설별 요약: {'Pulmonary embolism|E1': {'status': 'WORKING_DIAGNOSIS', 'kind': 'CURRENT_EVALUATION', 'support': [], 'weaken': [], 'held': ['CONCEPT_NOT_SUPPORTED', 'NO_VERIFIED_RELATION', 'SUSPICION_STATEMENT_USED_AS_CONTEXT'], 'review_candidate': False}, 'Aortic dissection|E9': {'status': 'WORKING_DIAGNOSIS', 'kind': 'CURRENT_EVALUATION', 'support': [], 'weaken': [], 'held': ['HYPOTHESIS_NOT_IN_GRAPH'], 'review_candidate': False}}
- 추출 맥락: {'pretest': {'value': 'INTERMEDIATE', 'status': 'FOUND', 'from': ['n1']}, 'suspected': {'value': True, 'status': 'FOUND', 'from': ['n1']}, 'ddimer_assay': {'value': None, 'status': 'NOT_FOUND', 'from': []}, 'ddimer_cutoff': {'value': None, 'status': 'NOT_FOUND', 'from': []}, 'haemodynamic_instability': {'value': False, 'status': 'FOUND', 'from': ['n1']}, 'phase_signals': []}
  - E1 n1 `Pulmonary embolism` UNCERTAIN → **ABSTAIN** SUSPICION_STATEMENT_USED_AS_CONTEXT 부족 ['SUSPICION_STATEMENT_USED_AS_CONTEXT(NOT_A_GAP)']
  - E1 e1 `Echocardiography` PRESENT → **ABSTAIN** CONCEPT_NOT_SUPPORTED 부족 ['CONCEPT_NOT_SUPPORTED(D)']
  - E9 n1 `Pulmonary embolism` UNCERTAIN → **ABSTAIN** HYPOTHESIS_NOT_IN_GRAPH 부족 ['HYPOTHESIS_NOT_IN_GRAPH(D)']
  - E9 e1 `pericardial effusion` PRESENT → **ABSTAIN** HYPOTHESIS_NOT_IN_GRAPH 부족 ['HYPOTHESIS_NOT_IN_GRAPH(D)']
  - E9 e1 `Echocardiography` PRESENT → **ABSTAIN** HYPOTHESIS_NOT_IN_GRAPH 부족 ['HYPOTHESIS_NOT_IN_GRAPH(D)']
### CASE09_context_in_record @ 5.0
- 가설별 요약: {'Pulmonary embolism|E1': {'status': 'WORKING_DIAGNOSIS', 'kind': 'CURRENT_EVALUATION', 'support': [], 'weaken': ['PE-CTPA-NEGATIVE'], 'held': ['ASSOCIATION_ONLY_NO_VERIFIED_DIRECTION', 'SUSPICION_STATEMENT_USED_AS_CONTEXT'], 'review_candidate': True}}
- 추출 맥락: {'pretest': {'value': 'LOW', 'status': 'FOUND', 'from': ['n1']}, 'suspected': {'value': True, 'status': 'FOUND', 'from': ['n1']}, 'ddimer_assay': {'value': None, 'status': 'NOT_FOUND', 'from': []}, 'ddimer_cutoff': {'value': None, 'status': 'NOT_FOUND', 'from': []}, 'haemodynamic_instability': {'value': False, 'status': 'FOUND', 'from': ['n1']}, 'phase_signals': []}
  - E1 n1 `PE` PURPOSE_OR_DIFFERENTIAL → **ABSTAIN** SUSPICION_STATEMENT_USED_AS_CONTEXT 부족 ['SUSPICION_STATEMENT_USED_AS_CONTEXT(NOT_A_GAP)']
  - E1 r1 `pulmonary embolism` NEGATED → **WEAKEN** PE-CTPA-NEGATIVE
### CASE10_no_context_in_record @ 5.0
- 가설별 요약: {'Pulmonary embolism|E1': {'status': 'WORKING_DIAGNOSIS', 'kind': 'CURRENT_EVALUATION', 'support': [], 'weaken': [], 'held': ['PE-CTPA-POSITIVE', 'PE-DDIMER-NORMAL'], 'review_candidate': False}}
- 추출 맥락: {'pretest': {'value': None, 'status': 'NOT_FOUND', 'from': []}, 'suspected': {'value': None, 'status': 'NOT_FOUND', 'from': []}, 'ddimer_assay': {'value': None, 'status': 'NOT_FOUND', 'from': []}, 'ddimer_cutoff': {'value': None, 'status': 'NOT_FOUND', 'from': []}, 'haemodynamic_instability': {'value': None, 'status': 'NOT_FOUND', 'from': []}, 'phase_signals': []}
  - E1 l1 `D-dimer` PRESENT → **INSUFFICIENT_EVIDENCE** PE-DDIMER-NORMAL 부족 ['clinical_phase(B)', 'ddimer_assay(B)', 'ddimer_cutoff(B)', 'pretest(B)']
  - E1 r1 `pulmonary embolism` PRESENT → **INSUFFICIENT_EVIDENCE** PE-CTPA-POSITIVE 부족 ['clinical_phase(B)', 'pretest(B)']
### CASE11_recurrence_separate @ 203.0
- 가설별 요약: {'Pulmonary embolism|E0': {'status': 'CONFIRMED_DIAGNOSIS', 'kind': 'PAST_EPISODE', 'support': [], 'weaken': [], 'held': ['ASSOCIATION_ONLY_NO_VERIFIED_DIRECTION', 'DIAGNOSIS_MENTION_WITHOUT_TEST_SOURCE', 'NO_VERIFIED_RELATION', 'PE-CTPA-NEGATIVE', 'SUSPICION_STATEMENT_USED_AS_CONTEXT'], 'review_candidate': False}, 'Pulmonary embolism|E2': {'status': 'WORKING_DIAGNOSIS', 'kind': 'RECURRENCE', 'support': [], 'weaken': [], 'held': ['ASSOCIATION_ONLY_NO_VERIFIED_DIRECTION', 'DIAGNOSIS_MENTION_WITHOUT_TEST_SOURCE', 'NO_VERIFIED_RELATION', 'PE-CTPA-NEGATIVE', 'SUSPICION_STATEMENT_USED_AS_CONTEXT'], 'review_candidate': False}}
- 추출 맥락: {'pretest': {'value': None, 'status': 'NOT_FOUND', 'from': []}, 'suspected': {'value': None, 'status': 'NOT_FOUND', 'from': []}, 'ddimer_assay': {'value': None, 'status': 'NOT_FOUND', 'from': []}, 'ddimer_cutoff': {'value': None, 'status': 'NOT_FOUND', 'from': []}, 'haemodynamic_instability': {'value': None, 'status': 'NOT_FOUND', 'from': []}, 'phase_signals': ['RECURRENCE_EVALUATION', 'UNDER_TREATMENT']}
  - E0 n0 `Pulmonary embolism` PRESENT → **ABSTAIN** DIAGNOSIS_MENTION_WITHOUT_TEST_SOURCE 부족 ['DIAGNOSIS_MENTION_WITHOUT_TEST_SOURCE(B)']
  - E0 n2 `recurrent pulmonary embolism` UNCERTAIN → **ABSTAIN** SUSPICION_STATEMENT_USED_AS_CONTEXT 부족 ['SUSPICION_STATEMENT_USED_AS_CONTEXT(NOT_A_GAP)']
  - E0 r2 `pulmonary embolism` NEGATED → **NOT_APPLICABLE** PE-CTPA-NEGATIVE
  - E2 n0 `Pulmonary embolism` PRESENT → **ABSTAIN** DIAGNOSIS_MENTION_WITHOUT_TEST_SOURCE 부족 ['DIAGNOSIS_MENTION_WITHOUT_TEST_SOURCE(B)']
  - E2 n2 `recurrent pulmonary embolism` UNCERTAIN → **ABSTAIN** SUSPICION_STATEMENT_USED_AS_CONTEXT 부족 ['SUSPICION_STATEMENT_USED_AS_CONTEXT(NOT_A_GAP)']
  - E2 r2 `pulmonary embolism` NEGATED → **UNCERTAIN** PE-CTPA-NEGATIVE 부족 ['PE-CTPA-NEGATIVE(E)']
### CASE12_haemodynamic_instability @ 5.0
- 가설별 요약: {'Pulmonary embolism|E1': {'status': 'WORKING_DIAGNOSIS', 'kind': 'CURRENT_EVALUATION', 'support': [], 'weaken': [], 'held': ['NO_VERIFIED_RELATION', 'PE-CTPA-POSITIVE', 'SUSPICION_STATEMENT_USED_AS_CONTEXT'], 'review_candidate': False}}
- 추출 맥락: {'pretest': {'value': 'HIGH', 'status': 'FOUND', 'from': ['n1']}, 'suspected': {'value': True, 'status': 'FOUND', 'from': ['n1']}, 'ddimer_assay': {'value': None, 'status': 'NOT_FOUND', 'from': []}, 'ddimer_cutoff': {'value': None, 'status': 'NOT_FOUND', 'from': []}, 'haemodynamic_instability': {'value': True, 'status': 'FOUND', 'from': ['n1']}, 'phase_signals': []}
  - E1 n1 `Pulmonary embolism` UNCERTAIN → **ABSTAIN** SUSPICION_STATEMENT_USED_AS_CONTEXT 부족 ['SUSPICION_STATEMENT_USED_AS_CONTEXT(NOT_A_GAP)']
  - E1 r1 `pulmonary embolism` PRESENT → **NOT_APPLICABLE** PE-CTPA-POSITIVE

## 설명 출력 예(CASE01)
```
[진단 가설] Pulmonary embolism (WORKING_DIAGNOSIS, 에피소드 E1, CURRENT_EVALUATION)
[근거 문장] "Acute pulmonary embolism in the right lower lobe segmental arteries." (문서 r1, 관찰 2.0, 이용 가능 4.0)
[연결 개념] 'pulmonary embolism' → PE_DIAGNOSIS [DISEASE], 상태 PRESENT, 그래프 노드 DX:Pulmonary embolism
[판단] SUPPORT (지지)
[그래프 경로] TEST:Pulmonary_Embolism:0 -HAS_RESULT_STATE-> STATE:CTPA_REPORTS_PE -SUPPORTS_HYPOTHESIS(PE-CTPA-POSITIVE)-> DX:Pulmonary embolism
[적용 조건] 혈역학적으로 안정된 PE 의심 환자의 CTPA 판독 / 사용한 맥락 {'clinical_phase': 'SUSPECTED_ACUTE_PE_EVALUATION', 'haemodynamic_instability': False, 'level': 'SEGMENTAL_OR_PROXIMAL', 'pretest': 'INTERMEDIATE'}
[출처] 2019 ESC Guidelines for the diagnosis and management of acut Figure 5 각주 d: "CTPA is considered diagnostic of PE if it shows PE at the segmental or more proximal level."
[출처] Gallo, Valerio, Barco. The 2019 European guidelines on pulmo 진단 절: "accepting the diagnosis of PE if CTPA is positive in patients with an intermediate or high clinical probability"
[출처] 2019 ESC Guidelines for the diagnosis and management of acut §7.1 Figure 5 제목: "Diagnostic algorithm for patients with suspected pulmonary embolism without haemodynamic instability"
[임상 단계] SUSPECTED_ACUTE_PE_EVALUATION (근거 INPUT_CONTEXT)
[불확실] 아분절 단독, 낮은 임상 확률, 종양 등 유사 소견
[주의] 판단은 확률이 아니며 의사 확인 필요
```

## 노출 문장 개념 연결 비교(개발·회귀 자료, 독립 평가 아님, 단일 문장·사례 맥락 없음)
| 표본 | 버전 | 찾음/주석 | 상태 일치 | 주석에 없는 연결 | 모호 |
|---|---|---|---|---|---|
| run1_exposed | P2 | 33/34 | 33/33 | 0 | 13 |
| run1_exposed | V3 | 33/34 | 33/33 | 0 | 11 |
- run1_exposed V3 방향 {'ABSTAIN': 83, 'INSUFFICIENT_EVIDENCE': 5, 'NO_CLEAR_EFFECT': 5, 'UNCERTAIN': 2}, 보류 원인 {'D': 19, 'E': 32, 'B': 26, 'A': 4, 'C': 1, 'NOT_A_GAP': 7}, V3 미검출 [{'id': 2, 'missed': 'CTPA_STUDY'}]
| run2_exposed | P2 | 41/54 | 38/41 | 5 | 20 |
| run2_exposed | V3 | 44/54 | 41/44 | 0 | 18 |
- run2_exposed V3 방향 {'ABSTAIN': 107, 'UNCERTAIN': 2, 'NO_CLEAR_EFFECT': 4, 'INSUFFICIENT_EVIDENCE': 2, 'NOT_APPLICABLE': 1}, 보류 원인 {'B': 39, 'E': 26, 'NOT_A_GAP': 17, 'D': 25, 'C': 1, 'A': 5}, V3 미검출 [{'id': 5, 'missed': 'PE_DIAGNOSIS'}, {'id': 11, 'missed': 'PE_DIAGNOSIS'}, {'id': 21, 'missed': 'PE_DIAGNOSIS'}, {'id': 25, 'missed': 'PE_DIAGNOSIS'}, {'id': 40, 'missed': 'PE_DIAGNOSIS'}, {'id': 46, 'missed': 'PE_DIAGNOSIS'}, {'id': 49, 'missed': 'PE_DIAGNOSIS'}, {'id': 59, 'missed': 'PE_DIAGNOSIS'}, {'id': 63, 'missed': 'PE_DIAGNOSIS'}, {'id': 64, 'missed': 'DVT'}]

## 지원 범위
- PE 1개 질환, 검증 관계 8개(P2 카탈로그), 영어 문장, 규칙 기반
- 임상 확률은 기록에 범주가 명시된 경우만(점수→범주 변환 없음, 2단계 Wells·위험도 미사용)

## 지원하지 못하는 범위
- 기록에서 점수로 임상 확률 범주 계산, 검사실 메타데이터의 검사법 연결, 나이 보정 조건(>50세)
- 문장 간 대명사·생략, 문서 간 에피소드 자동 병합(가설 대상은 입력), 재발 평가·잔존 혈전의 방향 관계(지침 문구 미확인)
- 비표준 CT 표기('CT angiogram of the pulmonary vasculature' 일부), 'high-sensitivity D-dimer' 표기, 사전 밖 질환·검사 연결
- 의사 확인 시각(메타데이터 없으면 UNCONFIRMED), LLM 없음

## 임상적으로 검증되지 않은 부분
- 관계 카탈로그·적용 조건 전문가 검토 없음, 추출 정확도·판단 정확도 전문가 기준 없음, 실제 EMR 미사용
