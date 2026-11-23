# Hybrid v2 P2 Clinical Evidence Safety Patch

구현 정책 검사 기록이다. 합성 문장·노출 문장으로 확인했고 임상 정확도가 아니다.

## P2 안전 정책
- **A. D-dimer 정상**: 의심 평가 단계 + 기록에서 확인된 임상 확률 + 검사법 민감도 + 판정 기준이 모두 있을 때만 WEAKEN. 고민감(ELISA 등)은 낮음·중간, 중등도 민감·현장 검사는 낮음만. 하나라도 없으면 INSUFFICIENT_EVIDENCE
- **B. 임상 단계**: CTPA 음성·CTPA 양성·관류 정상·D-dimer 정상 관계에 단계 조건 적용. 확진·치료 중·치료 후 추적 = NOT_APPLICABLE, 재발 평가 = UNCERTAIN, 단계 불명 = INSUFFICIENT_EVIDENCE
- **B. 가설 대상**: `hypothesis_target`(diagnosis_episode_id, kind, hypothesis_target_time) 와 근거 관찰 시각 연결. 과거 에피소드 판단 시점 이후 근거 = NOT_APPLICABLE, 시점 불명 = 보류, 재발 대상 = 재발 단계
- **C. 맥락 출처**: 기본 CLINICAL 모드는 RECORD·PHYSICIAN_CONFIRMED 값만 사용. 출처 미지정·가정·환자 보고 값은 사용 안 함. SYNTHETIC_ASSUMPTION 모드에서만 가정값 사용, 출력에 `output_mode`·`assumed_context_used` 표시
- 공통 스키마 무수정. 새 관계 없음(관계 ID·가설·소견·관계 종류 P1 과 동일). 추가 인용은 기존 관계의 적용 조건 근거
- 지침 인용은 OUP 공식 페이지를 WebFetch 로 읽은 발췌. 사람 원문 대조 필요

## 보존 확인
- P1·원본 코드·결과·문서(P2 시작 시 해시): 28/28 일치
- 1차 동결 사본: 5/5 일치
- 2차 동결 코드(FREEZE.json): 일치

## 회귀 테스트(코드 × 기준)
| 코드 | 기준 | 실행 | 실패 |
|---|---|---|---|
| hybrid2_p1 | test_pipeline | 48 | 0 |
| hybrid2_p1 | test_safety_patch_p1 | 44 | 0 |
| hybrid2_p2 | test_pipeline | 48 | 12 |
| hybrid2_p2 | test_safety_patch_p1 | 44 | 12 |
| hybrid2_p2 | test_safety_patch_p2 | 32 | 0 |
| hybrid2_p2 | test_pipeline (분류용 가정값 모드) | 48 | 2 |
| hybrid2_p2 | test_safety_patch_p1 (분류용 가정값 모드) | 44 | 8 |

P2 코드에서 P1 기준이 실패한 항목 분류(C = 가정값을 쓰지 않음, A = 검사 조건, B = 단계 조건):

- test_pipeline.Expressions.test_no_evidence: C — `?              ^^^^`
- test_pipeline.Labs.test_dvt_needs_proximal_ultrasound: C — `+ SUPPORT`
- test_pipeline.Labs.test_normal: C(+A) — `+ WEAKEN`
- test_pipeline.Labs.test_perfusion: C — `+ WEAKEN`
- test_pipeline.Time.test_correction_not_retroactive: C — `+ ['PE-CTPA-NEGATIVE']`
- test_pipeline.Time.test_engine_cross_check: C — `+ ['PE-CTPA-NEGATIVE']`
- test_pipeline.Time.test_new_result: C — `+ (['PE-CTPA-NEGATIVE'], True)`
- test_pipeline.Types.test_12_one_finding_many_hypotheses: C — `AssertionError: 'INSUFFICIENT_EVIDENCE' not found in ('WEAKEN', 'SUPPORT')`
- test_pipeline.Types.test_1_positive_with_level_and_context: C — `+ ('SUPPORT', 'PE-CTPA-POSITIVE')`
- test_pipeline.Types.test_1b_level_missing_no_support: C — `+ ('INSUFFICIENT_EVIDENCE', ['level'])`
- test_pipeline.Types.test_1d_low_pretest_outside_scope: C(+B) — `+ UNCERTAIN`
- test_pipeline.Types.test_2_negative_needs_pretest: C — `+ UNCERTAIN`
- test_safety_patch_p1.AbbreviationLegend.test_real_study_keeps_context: C — `+ ('SUPPORT', 'PE-CTPA-POSITIVE')`
- test_safety_patch_p1.CaseTimelinePhase.test_corrected_report_no_longer_confirms: C(+A) — `+ WEAKEN`
- test_safety_patch_p1.CaseTimelinePhase.test_result_available_later_not_retroactive: C(+A) — `+ WEAKEN`
- test_safety_patch_p1.CaseTimelinePhase.test_unavailable_document_not_used: C(+A) — `+ WEAKEN`
- test_safety_patch_p1.DdimerClinicalPhase.test_anticoagulant_without_target_holds: C(+A) — `-  ['clinical_phase', 'ddimer_assay', 'ddimer_cutoff', 'pretest']) : On warfarin, D-dimer was normal.`
- test_safety_patch_p1.DdimerClinicalPhase.test_followup_without_more_context_holds: C(+A) — `-  ['clinical_phase', 'ddimer_assay', 'ddimer_cutoff', 'pretest']) : D-dimer was normal at follow-up.`
- test_safety_patch_p1.DdimerClinicalPhase.test_high_pretest_and_point_of_care: C(+A) — `+ NOT_APPLICABLE`
- test_safety_patch_p1.DdimerClinicalPhase.test_input_phase: C — `+ ('NOT_APPLICABLE', 'UNDER_TREATMENT') : D-dimer was normal.`
- test_safety_patch_p1.DdimerClinicalPhase.test_phase_not_stated_holds: C(+A) — `-  ['clinical_phase', 'ddimer_assay', 'ddimer_cutoff', 'pretest']) : D-dimer was normal.`
- test_safety_patch_p1.DdimerClinicalPhase.test_suspected_evaluation_keeps_relation: C(+A) — `+ WEAKEN`
- test_safety_patch_p1.DdimerClinicalPhase.test_treatment_phase_decided_without_pretest: C — `-  ['clinical_phase', 'ddimer_assay', 'ddimer_cutoff', 'pretest'])`
- test_safety_patch_p1.DdimerClinicalPhase.test_under_treatment_with_followup: C — `AssertionError: False is not true`

## 노출 문장 재생(독립 평가 아님, 분모는 출력 단위)
### run1_exposed (57문장, 13문서)
| 조건 | 출력 | 방향 | 잘못된 방향 |
|---|---|---|---|
| P1_ASSUMED | 82 | {'ABSTAIN': 70, 'WEAKEN': 2, 'NO_CLEAR_EFFECT': 5, 'UNCERTAIN': 2, 'INSUFFICIENT_EVIDENCE': 3} | [] |
| P2_CLINICAL_NO_CONTEXT | 82 | {'ABSTAIN': 70, 'INSUFFICIENT_EVIDENCE': 5, 'NO_CLEAR_EFFECT': 5, 'UNCERTAIN': 2} | [] |
| P2_CLINICAL_UNSOURCED | 82 | {'ABSTAIN': 70, 'INSUFFICIENT_EVIDENCE': 5, 'NO_CLEAR_EFFECT': 5, 'UNCERTAIN': 2} | [] |
| P2_SYNTHETIC | 82 | {'ABSTAIN': 70, 'WEAKEN': 2, 'NO_CLEAR_EFFECT': 5, 'UNCERTAIN': 2, 'INSUFFICIENT_EVIDENCE': 3} | [] |
- P1 대비 바뀐 출력(P2_CLINICAL_NO_CONTEXT) 2건: 17번 PE-CTPA-NEGATIVE WEAKEN→INSUFFICIENT_EVIDENCE 원인 ['B', 'C']; 37번 PE-CTPA-NEGATIVE WEAKEN→INSUFFICIENT_EVIDENCE 원인 ['B', 'C']
- P1 대비 바뀐 출력(P2_CLINICAL_UNSOURCED) 2건: 17번 PE-CTPA-NEGATIVE WEAKEN→INSUFFICIENT_EVIDENCE 원인 ['B', 'C']; 37번 PE-CTPA-NEGATIVE WEAKEN→INSUFFICIENT_EVIDENCE 원인 ['B', 'C']
- P1 대비 바뀐 출력(P2_SYNTHETIC) 0건: 

### run2_exposed (65문장, 23문서)
| 조건 | 출력 | 방향 | 잘못된 방향 |
|---|---|---|---|
| P1_ASSUMED | 100 | {'ABSTAIN': 92, 'UNCERTAIN': 1, 'NO_CLEAR_EFFECT': 4, 'SUPPORT': 2, 'NOT_APPLICABLE': 1} | [] |
| P2_CLINICAL_NO_CONTEXT | 100 | {'ABSTAIN': 92, 'UNCERTAIN': 1, 'NO_CLEAR_EFFECT': 4, 'INSUFFICIENT_EVIDENCE': 2, 'NOT_APPLICABLE': 1} | [] |
| P2_CLINICAL_UNSOURCED | 100 | {'ABSTAIN': 92, 'UNCERTAIN': 1, 'NO_CLEAR_EFFECT': 4, 'INSUFFICIENT_EVIDENCE': 2, 'NOT_APPLICABLE': 1} | [] |
| P2_SYNTHETIC | 100 | {'ABSTAIN': 92, 'UNCERTAIN': 1, 'NO_CLEAR_EFFECT': 4, 'SUPPORT': 2, 'NOT_APPLICABLE': 1} | [] |
- P1 대비 바뀐 출력(P2_CLINICAL_NO_CONTEXT) 2건: 15번 PE-CTPA-POSITIVE SUPPORT→INSUFFICIENT_EVIDENCE 원인 ['B', 'C']; 35번 PE-CTPA-POSITIVE SUPPORT→INSUFFICIENT_EVIDENCE 원인 ['B', 'C']
- P1 대비 바뀐 출력(P2_CLINICAL_UNSOURCED) 2건: 15번 PE-CTPA-POSITIVE SUPPORT→INSUFFICIENT_EVIDENCE 원인 ['B', 'C']; 35번 PE-CTPA-POSITIVE SUPPORT→INSUFFICIENT_EVIDENCE 원인 ['B', 'C']
- P1 대비 바뀐 출력(P2_SYNTHETIC) 0건: 

- P1 기준선 재현 일치: {'run1_exposed': True, 'run2_exposed': True}

## 미해결 위험
- 실제 기록에서 임상 확률·의심 여부·검사법을 읽는 기능 없음. 기본 경로에서 SUPPORT·WEAKEN 은 사실상 나오지 않음(맥락 입력이 있을 때만)
- YEARS 는 임상 확률 범주 대신 자체 항목을 쓰지만 현재 규칙은 임상 확률 범주를 요구(보수적 보류). 나이 보정은 나이 >50 조건 미확인
- 'high-sensitivity D-dimer' 는 D-dimer 결과 창에서 'high' 로 읽혀 상충 기권. 'ELISA' 등만 고민감으로 인식, 실험실 검사명 목록 없음
- 문장 수준 단계 신호는 규칙. 'on warfarin' 처럼 치료 대상 불명은 보류. 문서·문장 간 맥락 연결 제한
- 재발 평가·치료 중 잔존 혈전의 의미에 대한 지침 문구 미확인 → 방향 없이 보류
- 가설 대상(hypothesis_target)은 입력으로만 받음. 자동 에피소드 구분 없음
- 원본 단위 테스트 48개·P1 테스트 44개 중 각 12개가 P2 코드에서 실패: 의도된 정책 변경, 테스트는 P1 역사 기준으로 보존
- P2 변이 검사는 범위 제한 지시에 따라 하지 않음
