# 전문의 검토 패킷(v5-2B-Research)

모든 항목 CLINICIAN_REVIEW_PENDING. 답변을 만들지 않는다. Legacy·Shadow 판단은 실제 실행 결과(run_20261109_03).

## 1. 혈역학 안정성 미기록
- 합성 상황 `F01`: n1(1.0): Pulmonary embolism is suspected. Clinical probability was assessed as low using the Wells score. / r1(5): IMPRESSION: No evidence of pulmonary embolism.
- Legacy v4: PE-CTPA-NEGATIVE=WEAKEN(DIRECTIONAL_PATH_TRUE)
- Shadow: SH-CTPA-NEG=INSUFFICIENT_EVIDENCE(DIRECTIONAL_PATH_UNKNOWN)
- 관련 지침: ESC 2019 Figure 5 제목(불안정 없는 환자), Table 4(행 구조는 평탄화 텍스트에서 확정 불가)
- 오해석 위험: 미기록을 안정으로 간주하면 실제 불안정 환자에 Figure 5 판단 적용 / 보류하면 대부분 판단 불가
- 선택지: (a) 보류 (b) 활력징후 확인 시만 (c) 적용+경고 (d) 응급 의심 평가 맥락이면 안정 간주
- 아직 확인 못 한 사실: 미기록 처리 문구, Table 4 행별 조건

## 2. CTPA 음성 + 검사 전 확률 재평가
- 합성 상황 `E01`: n1(1.0): Pulmonary embolism is suspected. Clinical probability was assessed as low using the Wells score. The patient is hemodynamically stable. / n2(3.0): Clinical probability was assessed as high using the Wells score. / r1(5): IMPRESSION: No evidence of pulmonary embolism.
- Legacy v4: PE-CTPA-NEGATIVE=INSUFFICIENT_EVIDENCE(DIRECTIONAL_PATH_CONFLICT)
- Shadow: SH-CTPA-NEG=INSUFFICIENT_EVIDENCE(PRETEST_REASSESSMENT_POLICY_UNVERIFIED)
- 관련 지침: §4.5 불일치 시 추가 검사, Figure 5 각주 e
- 오해석 위험: 재평가 전 낮음으로 배제하거나 재평가 후 높음을 무시할 위험
- 선택지: (a) 검사 직전 최신 평가 (b) 가장 높은 평가 (c) 보류 (d) 도구 우선순위
- 아직 확인 못 한 사실: 재평가 규칙

## 3. 서로 다른 도구의 낮음·중간
- 합성 상황 `D01`: n1(1.0): Pulmonary embolism is suspected. Clinical probability was assessed as low using the revised Geneva score. The patient is hemodynamically stable. / n2(1.0): Clinical probability was assessed as intermediate using the Wells score. / r1(5): IMPRESSION: No evidence of pulmonary embolism.
- Legacy v4: PE-CTPA-NEGATIVE=INSUFFICIENT_EVIDENCE(DIRECTIONAL_PATH_CONFLICT)
- Shadow: SH-CTPA-NEG=WEAKEN(DIRECTIONAL_PATH_TRUE|PRETEST_OUTCOME_INVARIANT)
- 관련 지침: §4.2(경험적 판단·예측 규칙 병용), 진단 절 '낮음·중간 CTPA 음성 배제'
- 오해석 위험: 도구 간 동등성 가정 위험 / 결론이 같은데 보류하는 과잉 보류
- 선택지: (a) 결론 불변이면 채택(Shadow) (b) 항상 보류(Legacy) (c) 특정 도구 우선
- 아직 확인 못 한 사실: 도구 간 비교 기준

## 4. 2단계 'PE unlikely' 와 D-dimer
- 합성 상황 `U05`: n1(1.0): Pulmonary embolism is suspected. PE was considered unlikely according to the Wells score. The patient is hemodynamically stable. / l1(2): Moderately sensitive D-dimer was normal, below the fixed cut-off.
- Legacy v4: PE-DDIMER-NORMAL=INSUFFICIENT_EVIDENCE(DIRECTIONAL_PATH_UNKNOWN)
- Shadow: SH-DD-NORMAL=WEAKEN(DIRECTIONAL_PATH_TRUE)
- 관련 지침: Figure 5 각주 b(중등도 민감 → 낮은 확률 또는 PE-unlikely)
- 오해석 위험: 2단계를 3단계로 섞는 위험
- 선택지: (a) 각주 b 경로만 허용(Shadow) (b) 고민감 검사에도 허용 (c) 불허
- 아직 확인 못 한 사실: 고민감 + PE-unlikely 조합, CTPA 경로에서의 의미(U06 보류)

## 5. YEARS 적용
- 합성 상황 `J01`: n1(1.0): Pulmonary embolism is suspected. The patient is hemodynamically stable. / l1(2): D-dimer was 800 µg/L. No YEARS items were present.
- Legacy v4: 판단 없음
- Shadow: SH-DD-YEARS=WEAKEN(DIRECTIONAL_PATH_TRUE)
- 관련 지침: 각주 c(항목 0 + <1000, 항목 ≥1 + <500 µg/L)
- 오해석 위험: 3단계 확률 요구(Legacy 는 판단 없음) / 단위(FEU·DDU) 오해석
- 선택지: (a) YEARS 독립 경로(Shadow) (b) 3단계도 요구 (c) 불허
- 아직 확인 못 한 사실: 단위 규정, YEARS 항목 판정 기준, 임신 적응판

## 6. 입원·임신 D-dimer
- 합성 상황 `U07`: n1(1.0): Pulmonary embolism is suspected. Clinical probability was assessed as low using the Wells score. The patient is hemodynamically stable. / n2(1.0): The patient has been hospitalized for 5 days. / l1(2): D-dimer measured by ELISA was normal, below the age-adjusted cut-off.
- Legacy v4: PE-DDIMER-NORMAL=WEAKEN(DIRECTIONAL_PATH_TRUE)
- Shadow: SH-DD-NORMAL=UNCERTAIN(EXCLUSION_GATE_TRUE)
- 관련 지침: 각주 b 'limited use', §9.2.1
- 오해석 위험: 입원·임신에서 정상 D-dimer 로 배제
- 선택지: (a) 보류(Shadow) (b) 경고만 (c) 제외
- 아직 확인 못 한 사실: 'limited use' 의 의미

## 7. 근위부 DVT
- 합성 상황 `U02`: n1(1.0): Pulmonary embolism is suspected. Clinical probability was assessed as low using the Wells score. The patient is hemodynamically stable. / u1(2): Compression ultrasound shows femoral deep vein thrombosis.
- Legacy v4: PE-PROXIMAL-DVT=SUPPORT(DIRECTIONAL_PATH_TRUE)
- Shadow: SH-PROX-DVT=NO_DIRECTION:VTE_TREATMENT_SUFFICIENT_NON_DIRECTIONAL(UNCONDITIONAL)
- 관련 지침: §4.10 '추가 검사 없이 항응고 치료에 충분'
- 오해석 위험: 치료 결정을 진단 확인으로 변환(Legacy SUPPORT)
- 선택지: (a) 비방향 VTE 치료 근거(Shadow) (b) 약한 SUPPORT (c) 현행
- 아직 확인 못 한 사실: PE 진단 의미를 직접 다룬 문구

## 8. MI 배제 경로·허혈 근거
- 관련 지침: UDMI5 §14.1.3·§14.1.5·Box 3·Box 6·§12
- 오해석 위험: 단일 매우 낮은 값(분류 경로)을 'MI 기준 미충족'으로 바꾸는 위험, 흉통만으로 허혈 증상 판정
- 선택지: (a) 분류 경로와 기준 미충족 분리(현 연구) (b) 단일 배제를 MI WEAKEN 으로
- 아직 확인 못 한 사실: 연속 측정 적정 시점·검사법 조건, 허혈 증상 조작적 정의

## 9. 심낭염 영상 계수·임상 양상
- 관련 지침: ESC 2025 Table 4, §4.4.1
- 오해석 위험: 영상 2항목으로 Definite / 비특이 흉통을 임상 양상으로
- 선택지: 정책 A/B/C, BROAD/STRICT
- 아직 확인 못 한 사실: 영상 행 계수 규칙, 임상 양상 정의

### 8번 관련 실행 결과(MI 연구 분류)
| 사례 | 급성 손상 | Box 3 | 배제 경로 | 기준 미충족 | 위험 분류 |
|---|---|---|---|---|---|
| MI01_values_no_reference | UNKNOWN | NOT_ASSESSABLE(급성 심근손상 미확정: UNKNOWN) | NOT_APPLICABLE(단일 매우 낮은 값 진술 없음) | UNKNOWN | NOT_STATED |
| MI02_reference_only | UNKNOWN | NOT_ASSESSABLE(급성 심근손상 미확정: UNKNOWN) | NOT_APPLICABLE(단일 매우 낮은 값 진술 없음) | UNKNOWN | NOT_STATED |
| MI03_serial_rise_reported | TRUE | ACUTE_INJURY_ONLY(허혈 특징 미확인 — MI 미평가) | NOT_APPLICABLE(단일 매우 낮은 값 진술 없음) | UNKNOWN | NOT_STATED |
| MI13_ecg_change_newness_unstated | TRUE | ACUTE_INJURY_ONLY(허혈 특징 미확인 — MI 미평가) | NOT_APPLICABLE(단일 매우 낮은 값 진술 없음) | UNKNOWN | NOT_STATED |
| MI04_different_assays | UNKNOWN | NOT_ASSESSABLE(급성 심근손상 미확정: UNKNOWN) | NOT_APPLICABLE(단일 매우 낮은 값 진술 없음) | UNKNOWN | NOT_STATED |
| MI05_time_unknown | UNKNOWN | NOT_ASSESSABLE(급성 심근손상 미확정: UNKNOWN) | NOT_APPLICABLE(단일 매우 낮은 값 진술 없음) | UNKNOWN | NOT_STATED |
| MI06_no_ischaemia | TRUE | ACUTE_INJURY_ONLY(허혈 특징 미확인 — MI 미평가) | NOT_APPLICABLE(단일 매우 낮은 값 진술 없음) | UNKNOWN | NOT_STATED |
| MI07_ischaemia_unknown | TRUE | ACUTE_INJURY_ONLY(허혈 특징 미확인 — MI 미평가) | NOT_APPLICABLE(단일 매우 낮은 값 진술 없음) | UNKNOWN | NOT_STATED |
| MI08_new_ecg_change | TRUE | BOX3_LIKELY_COMPONENTS_PRESENT_ECG_PATH(다른 급성 | NOT_APPLICABLE(단일 매우 낮은 값 진술 없음) | UNKNOWN | NOT_STATED |
| MI09_record_states_mi | TRUE | ACUTE_INJURY_ONLY(허혈 특징 미확인 — MI 미평가) | NOT_APPLICABLE(단일 매우 낮은 값 진술 없음) | UNKNOWN | NOT_STATED |
| MI10_rule_in_risk | TRUE | ACUTE_INJURY_ONLY(허혈 특징 미확인 — MI 미평가) | NOT_APPLICABLE(단일 매우 낮은 값 진술 없음) | UNKNOWN | RISK_STRATIFICATION_ONLY(§14 |
| MI11_single_very_low | UNKNOWN | NOT_ASSESSABLE(급성 심근손상 미확정: UNKNOWN) | SINGLE_SAMPLE_VERY_LOW_STATED → RULE_OUT_PATH | UNKNOWN | NOT_STATED |
| MI12_serial_all_below | FALSE | NOT_ASSESSABLE(급성 심근손상 미확정: FALSE) | NOT_APPLICABLE(단일 매우 낮은 값 진술 없음) | NOT_MET_CANDIDATE(모든 값 성별 99백분 | NOT_STATED |

### 9번 관련 실행 결과(심낭염 정책)
| 사례 | 임상 양상 정책 | A(5항목) | B(영상 1) | C(다르면 보류) |
|---|---|---|---|---|
| PC01_definite_both | BROAD | DEFINITE | DEFINITE | DEFINITE |
| PC01_definite_both | STRICT | DEFINITE | DEFINITE | DEFINITE |
| PC02_nonspecific_pain | BROAD | POSSIBLE_OR_DEFINITE_UNRESOLVED | POSSIBLE_OR_DEFINITE_UNRESOLVED | POSSIBLE_OR_DEFINITE_UNRE |
| PC02_nonspecific_pain | STRICT | NOT_GENERATED_PREREQUISITE_UNKNOWN | NOT_GENERATED_PREREQUISITE_UNKNOWN | NOT_GENERATED_PREREQUISIT |
| PC03_imaging_two_items | BROAD | DEFINITE | POSSIBLE | GRADE_HOLD_CRQ15(A·B 결과 다 |
| PC03_imaging_two_items | STRICT | DEFINITE | POSSIBLE | GRADE_HOLD_CRQ15(A·B 결과 다 |
| PC04_negative_no_cmr | BROAD | GRADE_UNDETERMINED | GRADE_UNDETERMINED | GRADE_UNDETERMINED |
| PC04_negative_no_cmr | STRICT | GRADE_UNDETERMINED | GRADE_UNDETERMINED | GRADE_UNDETERMINED |
| PC05_negative_with_cmr | BROAD | UNLIKELY_REJECTED | UNLIKELY_REJECTED | UNLIKELY_REJECTED |
| PC05_negative_with_cmr | STRICT | UNLIKELY_REJECTED | UNLIKELY_REJECTED | UNLIKELY_REJECTED |
| PC06_presentation_only | BROAD | GRADE_UNDETERMINED | GRADE_UNDETERMINED | GRADE_UNDETERMINED |
| PC06_presentation_only | STRICT | GRADE_UNDETERMINED | GRADE_UNDETERMINED | GRADE_UNDETERMINED |
