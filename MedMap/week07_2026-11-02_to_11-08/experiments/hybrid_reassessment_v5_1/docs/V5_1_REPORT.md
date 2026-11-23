# MedMap v5-1 — 다질환 근거 처리 기반(구조 구현)

A 코드 구현 완료 / B 기술 검증(합성 사례) 완료 / C 의학 해석 검증 미완료 / D 임상 성능 NOT_EVALUATED. **신규 활성 방향 관계 0건.**

## 모듈
- `hybrid5/logic.py` v4 4값 논리 재사용 + AT_LEAST_K·EXACTLY_K(최소·최대 충족 범위, 미확정 원인 UNKNOWN_ONLY/CONFLICT_ONLY/CONFLICT_AND_UNKNOWN)
- `hybrid5/concepts.py` 다질환 개념·분류 축(임상 표현/기전/경과), 진단 상태 5종, 문장 언급(미확인 후보)
- `hybrid5/observations.py` 트로포닌·CRP 수치·단위·검사법·기준값, 시계열(비교 가능성·수학적 변화량), as_of·정정
- `hybrid5/ecg.py` ECG 판독문 구조화(소견·상태·유도·분포·mm·대측·리듬·심박), 미지원 표현 표시
- `hybrid5/classification.py` 연구용 분류: 심낭염 Table 4, 급성·만성 심근손상(UDMI5 Box 1·2). 방향 판단과 분리
- `hybrid5/graphs.py`·`flat.py` v4 PatientGraph 상속 확장 / 같은 입력의 평면표, 공용 평가 함수

## 보존
- v5-0B 종료 이후 v5_1 밖 변경 파일: []
- v2 원본·P1·P2 해시: 28/28
- 1차 동결 사본: 5/5
- v4 테스트: OK
- v3 테스트: OK
- v5-1 테스트: Ran 32 tests in 0.494s OK
- v5-1 변이 시험: 4/4 검출(unknown_as_false, existential_removed, hs_mask_removed, ecg_override_removed)
- git commit: 없음

## 그래프 vs 평면표: 22개 상태 모두 동일 True

## 사례 결과
- C01_three_hypotheses@5.0 `h_acs` V5:DX:ACS [PHYSICIAN_SUSPECTED] 축 UNSPECIFIED/UNSPECIFIED | 분류 UNDETERMINED_UNKNOWN 범위 | 지지·약화 0/0
- C01_three_hypotheses@5.0 `h_pe` DX:Pulmonary embolism [PHYSICIAN_SUSPECTED] 축 UNSPECIFIED/UNSPECIFIED | LEGACY_V4 [{'evidence_id': 'EV:r1:0', 'relation_id': 'PE-CTPA-NEGATIVE', 'direction': 'WEAKEN', 'hold_reason': ''}] | 지지·약화 0/0
- C01_three_hypotheses@5.0 `h_peri` DX:Pericarditis [PHYSICIAN_SUSPECTED] 축 UNSPECIFIED/UNSPECIFIED | 분류 GRADE_UNDETERMINED 범위[0, 5] | 지지·약화 0/0
- C02_axes@2.0 `h_mi` V5:DX:MI [PHYSICIAN_CONFIRMED] 축 NSTEMI/SECONDARY | 분류 UNDETERMINED_UNKNOWN 범위 | 후보 [('V5:DX:MI', {'presentation': 'NSTEMI'}, 'AI_CANDIDATE_UNCONFIRMED'), ('V5:DX:MI', {'legacy_type': '2'}, 'AI_CANDIDATE_UNCONFIRMED')] | 지지·약화 0/0
- C03_troponin_series@4.0 `h_acs` V5:DX:ACS [PHYSICIAN_SUSPECTED] 축 UNSPECIFIED/UNSPECIFIED | 분류 UNDETERMINED_UNKNOWN 범위 | 시계열 TROPONIN_T: OBS:t0→OBS:t1 COMPUTED_MATH_ONLY(임상적 유의 변화 판, OBS:t1→OBS:t2 COMPUTED_MATH_ONLY(임상적 유의 변화 판 | 지지·약화 0/0
- C03b_troponin_series_with_reported_rise@4.0 `h_acs` V5:DX:ACS [PHYSICIAN_SUSPECTED] 축 UNSPECIFIED/UNSPECIFIED | 분류 MEETS_CRITERIA_RESEARCH 범위 | 시계열 TROPONIN_T: OBS:t0→OBS:t1 COMPUTED_MATH_ONLY(임상적 유의 변화 판, OBS:t1→OBS:t2 COMPUTED_MATH_ONLY(임상적 유의 변화 판 | 지지·약화 0/0
- C04_different_assays@3.0 `h_acs` V5:DX:ACS [UNDER_EVALUATION] 축 UNSPECIFIED/UNSPECIFIED | 분류 UNDETERMINED_UNKNOWN 범위 | 시계열 TROPONIN_T: OBS:a→OBS:c WITHHELD_ASSAY_TYPE_UNKNOWN | 지지·약화 0/0
- C05_different_units@3.0 `h_acs` V5:DX:ACS [UNDER_EVALUATION] 축 UNSPECIFIED/UNSPECIFIED | 분류 UNDETERMINED_UNKNOWN 범위 | 시계열 TROPONIN_I: OBS:l1:0:0→OBS:l2:0:0 WITHHELD_UNIT_MISMATCH(변환 규칙 없 | 지지·약화 0/0
- C06_no_reference@1.0 `h_acs` V5:DX:ACS [UNDER_EVALUATION] 축 UNSPECIFIED/UNSPECIFIED | 분류 UNDETERMINED_UNKNOWN 범위 | 지지·약화 0/0
- C07_diffuse_ste@2.0 `h_peri` DX:Pericarditis [PHYSICIAN_SUSPECTED] 축 UNSPECIFIED/UNSPECIFIED | 분류 POSSIBLE_OR_DEFINITE_UNRESOLVED 범위[1, 5] | ECG ST_ELEVATION/PRESENT/DIFFUSE, PR_DEPRESSION/PRESENT/NOT_STATED | 지지·약화 0/0
- C08_unclear_leads@2.0 `h_acs` V5:DX:ACS [UNDER_EVALUATION] 축 UNSPECIFIED/UNSPECIFIED | 분류 UNDETERMINED_UNKNOWN 범위 | ECG ST_ELEVATION/PRESENT/NOT_STATED | 지지·약화 0/0
- C10b_pericarditis_all_negative@2.0 `h_peri` DX:Pericarditis [UNDER_EVALUATION] 축 UNSPECIFIED/UNSPECIFIED | 분류 UNLIKELY_REJECTED 범위[0, 0] | ECG NORMAL_ECG/PRESENT/NOT_STATED | 지지·약화 0/0
- C10c_pericarditis_not_recorded@1.0 `h_peri` DX:Pericarditis [UNDER_EVALUATION] 축 UNSPECIFIED/UNSPECIFIED | 분류 GRADE_UNDETERMINED 범위[0, 5] | 지지·약화 0/0
- C11_conflict@2.0 `h_peri` DX:Pericarditis [UNDER_EVALUATION] 축 UNSPECIFIED/UNSPECIFIED | 분류 POSSIBLE_OR_DEFINITE_UNRESOLVED 범위[1, 5] | 지지·약화 0/0
- C12_duplicate_criterion@2.0 `h_peri` DX:Pericarditis [UNDER_EVALUATION] 축 UNSPECIFIED/UNSPECIFIED | 분류 POSSIBLE_OR_DEFINITE_UNRESOLVED 범위[1, 5] | 시계열 CRP: OBS:l1:0:0→OBS:l2:0:0 WITHHELD_ASSAY_TYPE_UNKNOWN | 지지·약화 0/0
- C13_no_presentation@2.0 `h_peri` DX:Pericarditis [UNDER_EVALUATION] 축 UNSPECIFIED/UNSPECIFIED | 분류 NOT_GENERATED_PREREQUISITE_UNKNOWN 범위 | 지지·약화 0/0
- C14_pericarditis_definite_research@2.0 `h_peri` DX:Pericarditis [PHYSICIAN_SUSPECTED] 축 UNSPECIFIED/UNSPECIFIED | 분류 DEFINITE 범위[3, 4] | ECG ST_ELEVATION/PRESENT/DIFFUSE, PR_DEPRESSION/PRESENT/NOT_STATED | 지지·약화 0/0
- C14b_pericarditis_possible_research@2.0 `h_peri` DX:Pericarditis [UNDER_EVALUATION] 축 UNSPECIFIED/UNSPECIFIED | 분류 POSSIBLE 범위[1, 1] | ECG NORMAL_ECG/PRESENT/NOT_STATED | 지지·약화 0/0
- C15_late_result@4.0 `h_acs` V5:DX:ACS [UNDER_EVALUATION] 축 UNSPECIFIED/UNSPECIFIED | 분류 CRITERIA_NOT_MET 범위 | 지지·약화 0/0
- C15_late_result@5.0 `h_acs` V5:DX:ACS [UNDER_EVALUATION] 축 UNSPECIFIED/UNSPECIFIED | 분류 UNDETERMINED_UNKNOWN 범위 | 시계열 TROPONIN_T: OBS:early→OBS:late COMPUTED_MATH_ONLY(임상적 유의 변화 판 | 지지·약화 0/0
- C16_corrected_troponin@2.0 `h_acs` V5:DX:ACS [UNDER_EVALUATION] 축 UNSPECIFIED/UNSPECIFIED | 분류 UNDETERMINED_UNKNOWN 범위 | 시계열 TROPONIN_T: OBS:v1→OBS:v2 COMPUTED_MATH_ONLY(임상적 유의 변화 판 | 지지·약화 0/0
- C16_corrected_troponin@3.0 `h_acs` V5:DX:ACS [UNDER_EVALUATION] 축 UNSPECIFIED/UNSPECIFIED | 분류 UNDETERMINED_UNKNOWN 범위 | 시계열 TROPONIN_T: OBS:v1→OBS:v2c COMPUTED_MATH_ONLY(임상적 유의 변화 판 | 지지·약화 0/0
- C17_candidates_vs_working_dx@1.0 `h_peri` DX:Pericarditis [PHYSICIAN_CONFIRMED] 축 UNSPECIFIED/UNSPECIFIED | 분류 NOT_GENERATED_PREREQUISITE_UNKNOWN 범위 | 후보 [('V5:DX:MI', {'presentation': 'NSTEMI'}, 'AI_CANDIDATE_UNCONFIRMED'), ('V5:DX:MI', {}, 'RECORD_HISTORY')] | 지지·약화 0/0
- C20_unsupported@1.0 `h_acs` V5:DX:ACS [UNDER_EVALUATION] 축 UNSPECIFIED/UNSPECIFIED | 분류 UNDETERMINED_UNKNOWN 범위 | 지지·약화 0/0
- **PURE_LOGIC_C09_C12**: `{"C09_2T_3U": {"AT_LEAST_2": {"value": "TRUE", "undetermined_reason": "", "confirmed_true_count": 2, "confirmed_false_count": 0, "unknown_count": 3, "conflict_count": 0, "minimum_true": 2, "maximum_possible_true": 5, "unresolved_conditions": ["c2", "c3", "c4"]}, "AT_LEAST_3": {"value": "UNKNOWN", "undetermined_reason": "UNKNOWN_ONLY", "confirmed_true_count": 2, "confirmed_false_count": 0, "unknown_count": 3, "conflict_count": 0, "minimum_true": 2, "maximum_possible_true": 5, "unresolved_conditions": ["c2", "c3", "c4"]}, "EXACTLY_2": {"value": "UNKNOWN", "undetermined_reason": "UNKNOWN_ONLY", "`
- **C20_unsupported_hypothesis**: `"REJECTED: 지원하지 않는 개념 DX:Aortic dissection(다른 개념에 붙이지 않음)"`
- **C02_axis_mixing**: `"REJECTED: V5:DX:MI 에 mechanism_axis=STEMI 없음"`

## v5-0B 후보 37건 호환성(엔진 비활성 유지)
- 레지스트리 sha256 `2e5393e528d79c31df2b287c2667ba941971a9a23503dad9e04c4dc13c8d026f`, 후보 37, 활성 0, v5-1 활성화 0
- 상태 빈도: {'NEEDS_CONTEXT_FIELD': 12, 'DO_NOT_ACTIVATE': 9, 'STRUCTURALLY_COMPATIBLE': 11, 'NEEDS_CLINICAL_REVIEW': 6, 'NEEDS_TEMPORAL_INPUT': 3, 'NEEDS_NUMERIC_INPUT': 1}
  - PE5-01(B): ['NEEDS_CONTEXT_FIELD'] 활력징후(SBP·승압제·저관류) 추출 없음
  - PE5-02(C): ['DO_NOT_ACTIVATE'] 근거가 흐름도 각주뿐(그림 미확인). '확인'은 고위험 PE 재관류 결정 맥락으로 진단·치료 범주 혼재. 'CTPA 불가' 조건은 연구자 추정
  - PE5-03(B): ['NEEDS_CONTEXT_FIELD'] 입원 여부 필드 없음
  - PE5-04(B): ['NEEDS_CONTEXT_FIELD'] 임신 필드 없음
  - PE5-05(C): ['DO_NOT_ACTIVATE'] 초록상 중증도·예후 분류(진단 아님)는 지지되나 범주 정의 원문 미확인
  - PE5-06(C): ['DO_NOT_ACTIVATE'] 재발 PE 진단 기준 원문 없음. 방향 관계 근거 없음(현행 UNCERTAIN 유지 근거 기록용)
  - PE5-07(A): ['STRUCTURALLY_COMPATIBLE'] 
  - PE5-08(A): ['STRUCTURALLY_COMPATIBLE'] 
  - ACS5-01(B): ['NEEDS_CLINICAL_REVIEW'] 손상 분류 구현. 상승·하강 '유의성' 기준이 원문에 없어 기록 진술만 사용
  - ACS5-02(A): ['STRUCTURALLY_COMPATIBLE'] 
  - ACS5-03(B): ['NEEDS_CONTEXT_FIELD', 'NEEDS_CLINICAL_REVIEW'] 허혈 증상 판정 필드 없음
  - ACS5-04(B): ['NEEDS_CONTEXT_FIELD'] 영상 관상동맥 병변·벽운동 필드 없음
  - ACS5-05(B): ['NEEDS_CONTEXT_FIELD', 'NEEDS_CLINICAL_REVIEW'] 
  - ACS5-06(C): ['DO_NOT_ACTIVATE'] 정의는 지지되나 시술 맥락이 v5 범위 밖
  - ACS5-07(B): ['NEEDS_CONTEXT_FIELD'] 안정 상태는 명시 문구만
  - ACS5-08(B): ['NEEDS_CONTEXT_FIELD'] 증상 양상(안정 시·악화) 필드 없음
  - ACS5-09(B): ['NEEDS_TEMPORAL_INPUT', 'NEEDS_CLINICAL_REVIEW'] 채혈 시점 기준 원문 수치 없음
  - ACS5-10(C): ['DO_NOT_ACTIVATE'] ESC 2023 은 rule-out NPV>99%, UDMI5 §14.1.5 는 알고리즘 임계값이 위험 분류용이며 진단 정의가 아니라고 명시 → 진단 WEAKEN
  - ACS5-11(A): ['NEEDS_CONTEXT_FIELD'] rule-in/out 알고리즘 결과 문구 추출 없음
  - ACS5-12(B): ['NEEDS_NUMERIC_INPUT'] 유도별 mm·성별·연령 기준 적용 안 함(mm 값만 추출)
  - ACS5-13(B): ['NEEDS_TEMPORAL_INPUT'] 지표 MI 와 재발 에피소드 연결 필요
  - ACS5-14(B): ['NEEDS_CONTEXT_FIELD'] 관상동맥 비폐쇄 판독 필드 없음
  - ACS5-15(C): ['DO_NOT_ACTIVATE'] 본문 미확인(초록만), 정정 공지 3건 내용도 미확인
  - PERI5-01(B): ['STRUCTURALLY_COMPATIBLE', 'NEEDS_CLINICAL_REVIEW'] K-of-N·등급 구현(연구용). 등급→방향 연결은 전문의 검토
  - PERI5-02(B): ['STRUCTURALLY_COMPATIBLE', 'NEEDS_CLINICAL_REVIEW'] 위와 같음
  - PERI5-03(C): ['DO_NOT_ACTIVATE'] 지침 분류 'Unlikely/rejected'를 MedMap WEAKEN 으로 바꿀 원문 근거 없음. 기준 미기록·미평가와 음성 확인 구분 필요
  - PERI5-04(B): ['STRUCTURALLY_COMPATIBLE'] 
  - PERI5-05(B): ['STRUCTURALLY_COMPATIBLE'] 
  - PERI5-06(B): ['STRUCTURALLY_COMPATIBLE'] 
  - PERI5-07(B): ['STRUCTURALLY_COMPATIBLE'] 
  - PERI5-08(B): ['STRUCTURALLY_COMPATIBLE'] 
  - PERI5-09(A): ['NEEDS_CONTEXT_FIELD'] TTE 정상 소견 추출 없음
  - PERI5-10(B): ['NEEDS_CONTEXT_FIELD'] 좌심실 기능 새 장애 필드 없음
  - PERI5-11(B): ['NEEDS_TEMPORAL_INPUT'] 경과(관해 후 재발) 시점 필드 없음
  - PERI5-12(A): ['STRUCTURALLY_COMPATIBLE'] 
  - PERI5-13(C): ['DO_NOT_ACTIVATE'] 내부 2of4 규칙이 2025 ESC Table 4 와 구조 불일치
  - PERI5-14(C): ['DO_NOT_ACTIVATE'] 비방향은 맞지만 고위험 인자 목록(Table 7 이미지) 미확인

## 한계
- 텍스트 수치 추출은 규칙 기반(같은 문장 내 분석물·값·기준). 문장 간 연결, 표 형식 검사지, 단위 변환 없음
- 상승·하강 '유의성' 기준이 원문에 없어(UDMI5 §14.1.4) 기록 진술만 사용 → 수치만 있으면 급성 손상 미결
- 심낭염 임상 양상은 흉통 HPO 개념 또는 구조화 입력만. 영상 2항목 계산(CRQ-15) 미결이라 두 방식 병기
- ECG 는 판독문 표현만(파형 없음). 유도별 mm·성별·연령 기준 적용 안 함
- 진단 언급의 언급 상태는 v3 parser 의존(같은 한계 승계)
