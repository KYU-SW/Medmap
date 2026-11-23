# MedMap v5-2B-Research 보고서 — PE Shadow 비교 엔진 · 합성 조건 반례 · 다질환 연구 분류

실행 run_20261109_03(이전 실행 run_20261109_01·02 보존). 수치는 outputs/run_20261109_03/*.json 에서 계산. Shadow 결과는 RESEARCH_ONLY·NOT_CLINICALLY_VALIDATED·ENGINE_ACTIVE_FALSE. 임상 성능 NOT_EVALUATED.

## 1. 구현

- `hybrid5b/shadow_catalog.py`(격리 카탈로그·정책), `clinical_context.py`(확률 관측·2단계·혈역학 명시 문구·입원·임신·항응고·YEARS), `shadow_reasoner.py`(v4 Reasoner·evaluate_one·decide 재사용 + 확률 해석 세계), `legacy_adapter.py`, `experiment_matrix.py`, `comparison.py`, `temporal.py`(v5-2A.1 그룹화·v5-2A.2 재생 연결), `multidisease.py`, `graph_flat.py`.
- 기존 코드 무수정. v4 카탈로그는 실행 전후 동일(테스트).

## 2. 핵심 수치

- PE 합성 사례 64개(그룹 A~O·U·Z) + 시간·중복·정정 6개 + MI 13 + 심낭염 6 + 다질환 2
- 판단 수: Legacy 55, Shadow 61
- 사전 고정 기대값: PE 65/65 (근거별 {'SOURCE_SUPPORTED_EXPECTATION': 30, 'UNKNOWN': 2, 'RESEARCHER_INTERPRETATION': 21, 'CLINICIAN_REVIEW_REQUIRED': 12}), 비교 분류 기대 11/11, MI 28/28, 심낭염 12/12
- P0 진리표 33행 대조: {'AGREE': 33}
- P0 반례: {'mapped': 12, 'shadow_discrepancy': 0, 'legacy_discrepancy': 7, 'not_executed': 16}
- Legacy vs Shadow 분류: {'SAME_DECISION': 36, 'DIFFERENT_MISSING_REQUIREMENTS': 6, 'LEGACY_MORE_CONSERVATIVE': 8, 'SHADOW_MORE_CONSERVATIVE': 5, 'DIFFERENT_APPLICABILITY': 4, 'SOURCE_INCOMPLETE': 1, 'SEMANTIC_REVIEW_REQUIRED': 1}
- 후보 표시: {'LEGACY_OVER_HOLD_CANDIDATE': 8, 'LEGACY_PREMATURE_CANDIDATE': 7}
- 차이 조건: {'MISSING_DIFF': 11, 'PRETEST_CONFLICT_OUTCOME_DEPENDS': 2, 'PRETEST_CONFLICT_OUTCOME_INVARIANT': 4, 'HAEMO_STABILITY_NOT_DOCUMENTED': 5, 'ASSAY_PHRASE_MAPPING': 1, 'YEARS_SEPARATE_PATH': 6, 'EXCLUSION': 3, 'SHADOW_STATUS': 2, 'TWO_LEVEL_CLASSIFICATION': 1}
- Shadow 전문의 검토 필요 판단: 16
- Graph vs Flat: {'pe_cases': 64, 'legacy_identical': 64, 'shadow_identical': 64, 'comparison_identical': 64, 'temporal_identical': True}
- 시간·중복·정정 검사: {'1_duplicate_not_independent': True, '2_no_event_dependency_unknown': True, '3_correction_vs_context_separated': True, '4_other_episode_not_applied': True, '5_no_future_results': True, '6_counterfactual_labelled': True, '7_event_vs_patient_not_confused': True, '8_shadow_follows_time_policy': True, 'conflict_same_event_detected': True, 'distinct_events_not_merged': True}
- 신규 반례 18: {'total': 18, 'shadow_discrepancy': 0, 'legacy_discrepancy': 3, 'legacy_discrepancy_ids': ['NCE-02', 'NCE-03', 'NCE-06']}
- 레지스트리: {'n': 37, 'active': 0, 'unchanged': True}

## 3. 해석(규칙 적합성 — 임상 정확도 아님)

- **Legacy 과잉 보류 후보(LEGACY_MORE_CONSERVATIVE):** 결론 불변 확률 충돌(C03·D01·D02·E02), 'high-sensitivity assay' 문구 미매핑(H02), YEARS(J01·J03), 2단계 PE-unlikely(U05).
- **Legacy 성급 판단 후보:** 혈역학 미기록(F01·F02·F03), 입원·임신 D-dimer(U07·U08), 근위부 DVT SUPPORT(U02, 의미 검토), 관류 정상 WEAKEN(U01, 출처·해석 미확정).
- **Shadow 의 보류 증가:** 혈역학 미기록 보류는 정책 C 의 결과이며 정책 A 에서는 사라짐(정책 민감도 표) — 원문이 미기록 처리를 말하지 않으므로 어느 쪽도 정답으로 두지 않음.
- **원문 부족으로 보류:** 관류 정상 방향, 충만 결손, 낮은 확률 양성 CTPA(Table 6 미확인), 2단계 + CTPA, 혈압·승압제·저관류 조합(Table 4 행 구조 미확정).
- **ACS·MI:** 급성 손상과 MI 를 분리. ECG 경로는 '새로운' 변화가 기록될 때만 Box 3 구성요소 충족으로 표시(MI 확정 아님). 단일 매우 낮은 값은 분류 경로(§14.1.3)로, 연속값 모두 기준 이하는 '기준 미충족 후보(시점 적정성 미검증)'로 따로 둠 — 두 절은 목적이 달라 모순으로 분류하지 않음.
- **심낭염:** 영상 2항목 사례(PC03)에서 정책 A=DEFINITE, B=POSSIBLE → C 보류. 비특이 흉통(PC02)은 STRICT 에서 등급 미생성. CMR 미시행 음성(PC04)은 Unlikely 로 가지 않음. 등급 → 방향 변환 없음.

## 4. 테스트·보존

| 묶음 | 실행 | 결과 |
|---|---|---|
| v5_2b_research | 14 | OK |
| v5_2a2 | 30 | OK |
| v5_2a1 | 27 | OK |
| v5_2a | 30 | OK |
| v5_1 | 32 | OK |
| v4 | 17 | OK |
| v3 | 28 | OK |
| v2 | 124 | OK |

- 기존 v1~v5-2B-P0 파일 240개 체크섬: 변경 0 · 누락 0
- git: 추가 [] · 사라짐 []

## 5. 발견·수정한 기술 결함(신규 코드 범위)

- 카탈로그: D-dimer 의 확률 게이트를 HOLD 로 두어 2단계 경로가 막힘 → BLOCK_ONLY_IF_TRUE 로 수정(경로 자체가 확률을 요구하므로 중복 보류 제거). [RULE_SEMANTIC_ERROR]
- 실행 연결: 반례 참조 키(MI08)와 사례 키(MI08_new_ecg_change) 불일치 → 접두어 매칭. [CODE_BUG]
- 시간 검사 8번: as_of 3.0(판독 공개 4.0 전)에 SUPPORT 를 기대한 검사 작성 오류 → 공개 전 판단 없음 + 5.0 SUPPORT + 8.0 WEAKEN 으로 강화(run_01 은 실패 상태로 보존). [EXPECTATION_UNSUPPORTED]
- 뮤테이션 7종 중 'ECG 새로움 무시' 미검출 → 사례 MI13 추가 후 검출(사후 추가 명시). 나머지 6종은 처음부터 검출.
- P0 진리표 9행에 대응 사례가 없어 Z01~Z09 추가(기대값 = P0 사전 등록 후보 판단) → 33/33 일치.

## 6. 남은 기술 문제

- 활력징후 기반 혈역학 판정(Table 4 행 구조 확정 필요), 확률 평가 시각은 기록 공개 시각만 사용, YEARS 항목·단위 추출은 연구용 정규식(실제 기록 표현 범위 미검증).
- MI·심낭염 연구 분류는 v5-2A 그래프 경로만 사용(Graph/Flat 동일성은 v5-2A 에서 32/32 확인된 하위 계층에 의존).
- 문맥 의존 Legacy 판단의 원인 귀속은 v5-2A.2 사건 이력에 연결 가능하나 Shadow 이력에는 아직 사건별 귀속 표를 만들지 않음.

## 7. 의학적 미검증 · 확인 수준

- 원문: UDMI5 로컬 전문(직접), ESC 2019·2025 는 OUP 발췌(요약 모델 경유), Table 4 행 구조·Table 6·권고표 미확인, 미국 지침 2종 미비교.
- 문헌 기대값도 임상 정답이 아님. 전문의 검토 전 — 모든 연구용 방향 라벨은 비활성.
