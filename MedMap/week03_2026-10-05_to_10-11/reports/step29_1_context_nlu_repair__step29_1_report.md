# STEP29.1 — Context-Aware Clinical NLU Repair(연구용)

- **STEP30_READINESS = NO_GO** · STEP29_1_RESULT = **REGRESSION** · EVALUATOR_V5 = PASS · PRODUCTION_READY = NO · HUMAN_VERIFIED_GOLD = 0
- hard {"G1": "PASS", "G2": "PASS", "G3": "PASS", "G4": "PASS", "G5": "PASS", "G6": "PASS", "G7": "PASS", "G8": "PASS", "G9": "PASS", "G10": "PASS"} · soft {"S1": "FAIL", "S2": "FAIL", "S3": "FAIL", "S4": "PASS", "S5": "PASS", "S6": "FAIL", "S7": "PASS"}
- 고정 순서: 새 계약 42(SHA `2819213e2e8487bd…`) → 전향적 합성 231(SHA `da94d08daa33d22e…`, NLU 미실행) → 검사기 v5(SHA `8f211c90e92404f5…`) → 게이트(이 파일) → 구현(새 계약으로만 개발) → 코드 동결 → 평가 1회.

## 1. 최종 보고

| 항목 | 값 |
|---|---|
| STEP29_1_RESULT | REGRESSION |
| EVALUATOR_V5 | PASS |
| MULTI_SPAN_RETENTION | 0.625 |
| NEGATION_SCOPE | 0.9371 |
| EVALUATIVE_NEGATION | 새 계약 EVAL 12/12(P1 5) |
| TEMPORALITY | pilot 0.8742 · 새 계약 RES 8/8(P1 4) · 전향적 T4_RESOLVED 0/10(P1 0) |
| EXPERIENCER | 1.0 |
| CONCEPT_PRECISION | 0.9302 |
| CONCEPT_COVERAGE | 0.5119 |
| UNSUPPORTED_AUTO_LINK | 7/28(STEP29 정의) · 환자 양성 모델 입력 0 |
| SEMANTIC_VIOLATIONS | 4 |
| RAW_PRESERVATION | 1.0 |
| CPU_P95_MS | 48.38 |
| STEP30_READINESS | NO_GO |
| PRODUCTION_READY | NO |
| HUMAN_VERIFIED_GOLD | 0 |

## 2. 검사기 효과(같은 NLU 출력 — STEP29 NLU)

- 검사기 정답 대조: 정상 mention 2764 중 v5 오판 0 · 위험 사례 15 중 v5 누락 0 · 같은 혼합 정상 문장에 v4(문장 단위) 오판 2.
- STEP29 NLU 출력의 구별 위반 입력: v4(문장 단위) 8 → v5(mention 단위) 4. 이 차이는 검사기 효과이며 NLU 개선이 아니다.

## 3. 정책 비교(검사기 v5 기준 NLU 효과는 P2→P5, P0 는 참고)

| 지표 | P0 | P1 | P2 | P3 | P4 | P5 |
|---|---|---|---|---|---|---|
| n_inputs | 1960 | 1960 | 1960 | 1960 | 1960 | 1960 |
| n_mentions | 2218 | 2246 | 2246 | 2241 | 2220 | 2220 |
| raw_ok_rate | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| offset_valid_rate | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| v5_violation_inputs | 5 | 4 | 4 | 4 | 4 | 4 |
| v4_violation_inputs | 10 | 8 | 8 | 8 | 8 | 8 |
| G5_neg_resolved_hypothetical_positive | 11 | 8 | 8 | 2 | 2 | 0 |
| G6_other_person_positive | 1 | 0 | 0 | 0 | 0 | 0 |
| G7_silver_or_new_model_input | 0 | 0 | 0 | 0 | 0 | 0 |
| G10_uncertain_without_reason | 5 | 0 | 0 | 0 | 0 | 0 |
| pilot_multi_retention | 0.525 | 0.675 | 0.675 | 0.675 | 0.675 | 0.625 |
| pilot_retention | 0.5222 | 0.6212 | 0.6212 | 0.6212 | 0.6212 | 0.5427 |
| pilot_assertion_agreement | 0.9346 | 0.9066 | 0.9066 | 0.9505 | 0.9505 | 0.9371 |
| pilot_temporality_agreement | 0.9346 | 0.8846 | 0.8846 | 0.8846 | 0.8791 | 0.8742 |
| pilot_experiencer_agreement | 0.9935 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| pilot_wrong_concept_mentions | 12 | 21 | 21 | 21 | 21 | 19 |
| pilot_unsupported_auto | 7 | 8 | 8 | 8 | 8 | 7 |
| pilot_unsupported_n | 28 | 28 | 28 | 28 | 28 | 28 |
| pilot_unsupported_patient_positive | 2 | 2 | 2 | 2 | 2 | 0 |
| reg_precision | 0.9451 | 0.9333 | 0.9333 | 0.9333 | 0.9333 | 0.9302 |
| reg_coverage | 0.5417 | 0.625 | 0.625 | 0.625 | 0.625 | 0.5119 |
| step29_contracts_failed | 46 | 3 | 3 | 3 | 3 | 3 |
| new_EVAL_pass | 4 | 5 | 5 | 11 | 12 | 12 |
| new_EVAL_n | 12 | 12 | 12 | 12 | 12 | 12 |
| new_RES_pass | 0 | 4 | 4 | 4 | 8 | 8 |
| new_RES_n | 8 | 8 | 8 | 8 | 8 | 8 |
| new_MIX_pass | 5 | 5 | 5 | 6 | 7 | 7 |
| new_MIX_n | 7 | 7 | 7 | 7 | 7 | 7 |
| new_MULTI_pass | 2 | 4 | 4 | 4 | 4 | 4 |
| new_MULTI_n | 4 | 4 | 4 | 4 | 4 | 4 |
| new_EXP_pass | 3 | 3 | 3 | 3 | 3 | 3 |
| new_EXP_n | 3 | 3 | 3 | 3 | 3 | 3 |
| new_UNSUP_pass | 4 | 4 | 4 | 5 | 5 | 8 |
| new_UNSUP_n | 8 | 8 | 8 | 8 | 8 | 8 |
| new_total_pass | 18 | 25 | 25 | 33 | 39 | 42 |
| pros_T1_ABSENT_pass | 0 | 7 | 7 | 7 | 7 | 7 |
| pros_T1_ABSENT_n | 7 | 7 | 7 | 7 | 7 | 7 |
| pros_T1_OTHER_pass | 0 | 20 | 20 | 20 | 20 | 20 |
| pros_T1_OTHER_n | 20 | 20 | 20 | 20 | 20 | 20 |
| pros_T1_PAST_pass | 0 | 3 | 3 | 3 | 3 | 3 |
| pros_T1_PAST_n | 10 | 10 | 10 | 10 | 10 | 10 |
| pros_T1_PRESENT_pass | 0 | 5 | 5 | 5 | 5 | 5 |
| pros_T1_PRESENT_n | 5 | 5 | 5 | 5 | 5 | 5 |
| pros_T1_PRESENT_ONSET_pass | 0 | 9 | 9 | 9 | 9 | 9 |
| pros_T1_PRESENT_ONSET_n | 9 | 9 | 9 | 9 | 9 | 9 |
| pros_T2_BOTH_pass | 0 | 30 | 30 | 30 | 30 | 30 |
| pros_T2_BOTH_n | 30 | 30 | 30 | 30 | 30 | 30 |
| pros_T2_NEG_POS_pass | 0 | 30 | 30 | 30 | 30 | 30 |
| pros_T2_NEG_POS_n | 30 | 30 | 30 | 30 | 30 | 30 |
| pros_T2_PAST_NOW_pass | 0 | 25 | 25 | 25 | 25 | 25 |
| pros_T2_PAST_NOW_n | 25 | 25 | 25 | 25 | 25 | 25 |
| pros_T3_SWITCH_pass | 0 | 25 | 25 | 25 | 25 | 25 |
| pros_T3_SWITCH_n | 25 | 25 | 25 | 25 | 25 | 25 |
| pros_T4_CONTROL_pass | 0 | 0 | 0 | 0 | 0 | 0 |
| pros_T4_CONTROL_n | 20 | 20 | 20 | 20 | 20 | 20 |
| pros_T4_RESOLVED_pass | 0 | 0 | 0 | 0 | 0 | 0 |
| pros_T4_RESOLVED_n | 10 | 10 | 10 | 10 | 10 | 10 |
| pros_T6_DIS_ONLY_pass | 5 | 5 | 5 | 5 | 5 | 5 |
| pros_T6_DIS_ONLY_n | 5 | 5 | 5 | 5 | 5 | 5 |
| pros_T6_DIS_SYM_pass | 0 | 15 | 15 | 15 | 15 | 15 |
| pros_T6_DIS_SYM_n | 15 | 15 | 15 | 15 | 15 | 15 |
| pros_T6_DRUG_ONLY_pass | 5 | 5 | 5 | 5 | 5 | 5 |
| pros_T6_DRUG_ONLY_n | 5 | 5 | 5 | 5 | 5 | 5 |
| pros_T6_DRUG_SYM_pass | 0 | 15 | 15 | 15 | 15 | 15 |
| pros_T6_DRUG_SYM_n | 15 | 15 | 15 | 15 | 15 | 15 |
| pros_total_pass | 10 | 194 | 194 | 194 | 194 | 194 |
| pros_n | 231 | 231 | 231 | 231 | 231 | 231 |
| pros_err_NOT_EXTRACTED | 18 | 0 | 0 | 0 | 0 | 0 |
| pros_err_WRONG_NORMALIZATION | 0 | 8 | 8 | 8 | 8 | 14 |
| pros_err_NEGATION | 0 | 0 | 0 | 10 | 10 | 10 |
| pros_err_TEMPORALITY | 333 | 30 | 30 | 30 | 30 | 30 |
| pros_err_EXPERIENCER | 0 | 0 | 0 | 0 | 0 | 0 |
| pros_err_MODEL_POSITIVE_FORBIDDEN | 11 | 9 | 9 | 0 | 0 | 0 |
| pros_err_UNEXPECTED_SYMPTOM | 0 | 0 | 0 | 0 | 0 | 0 |
| pros_err_OVER_SPLIT | 0 | 0 | 0 | 0 | 0 | 0 |
| new_over_split | 0 | 0 | 0 | 0 | 0 | 0 |
| duplicate_span_mentions | 0 | 0 | 0 | 0 | 0 | 0 |
| silver_unknown_uncertain_rate | 0.2861 | 0.2591 | 0.2591 | 0.2591 | 0.2591 | 0.2712 |
| weaknon_positive_inputs | 10 | 17 | 17 | 17 | 17 | 16 |
| model_input_eligible_mentions | 621 | 603 | 603 | 599 | 598 | 553 |

## 4. 오류 분석

- P5 오류(세트:종류): {"C29:WRONG_NORMALIZATION": 3, "PILOT:MISSED_OR_UNMAPPED": 134, "PILOT:NEGATION": 10, "PILOT:TEMPORALITY": 20, "PILOT:WRONG_CONCEPT": 19, "PILOT_UNSUPPORTED:UNSUPPORTED_AUTO": 7, "PROS:NEGATION": 10, "PROS:TEMPORALITY": 30, "PROS:V5_NAUSEA_AS_VOMITING": 1, "PROS:WRONG_NORMALIZATION": 14, "SIL:V5_DISEASE_TERM": 2, "WN:V5_DISEASE_TERM": 1}
- 전향적 실패 예(P5): NOT_EXTRACTED [] · WRONG_NORMALIZATION ['지난주에 속이 메스꺼웠어요→None', '지난주에 구토를 했어요→None', '지난주에 숨이 찼어요→None', '지난주에 설사를 했어요→None', '지난주에 열이 났어요→None'] · NEGATION ['열이 났어요 오늘은 괜찮아요.→ABSENT', '숨이 찼어요 오늘은 괜찮아요.→ABSENT', '구토를 했어요 오늘은 괜찮아요.→ABSENT', '머리가 아팠어요 오늘은 괜찮아요.→ABSENT', '속이 메스꺼웠어요 오늘은 괜찮아요.→ABSENT'] · TEMPORALITY ['머리가 아팠어요 오늘은 설사를 해요→CURRENT', '숨이 찼어요 오늘은 어지러워요→CURRENT', '기침이 났어요 오늘은 배가 아파요→CURRENT', '열이 났어요 오늘은 속이 메스꺼워요→CURRENT', '가래가 끓었어요 오늘은 머리가 아파요→CURRENT'] · EXPERIENCER []
- pilot 연결 불가 발화 자동 연결(P5): ['남편이 기침을 심하게 해서 저도 옮았을까 걱정돼요→cough|PRESENT|OTHER_PERSON|False', '아이랑 같이 먹었는데 아이만 설사해요→diarrhea|PRESENT|OTHER_PERSON|False', '아빠가 가슴이 아프다고 하셔서 같이 왔는데 저는 괜찮아요→pain|PRESENT|OTHER_PERSON|False', '할머니가 숨이 차신대요→dyspnea|PRESENT|OTHER_PERSON|False', '아내가 피를 토해서 걱정이에요→hematemesis|PRESENT|OTHER_PERSON|False', '피곤한 건지 아픈 건지 모르겠어요→fatigue|POSSIBLE|PATIENT|False', '열이 나면 어떻게 해야 하나요→fever|UNKNOWN|PATIENT|False']
- pilot 부정 불일치(P5): ['머리는 안 아픈데 배가 아파요→pain:present→ABSENT(NEG:안)', '해열제를 먹어도 열이 안 떨어져요→fever:present→ABSENT(NEG:안)', '밤마다 기침 때문에 잠을 못 자요→cough:present→ABSENT(NEG:못)', '기침이 한번 시작하면 멈추질 않아요→cough:present→UNKNOWN(HYPOTHETICAL_CONDITIONAL)', '구토가 멈추질 않아요→vomiting:present→ABSENT(NEG:않)', '고개를 돌리면 어지러워요→dizziness:present→UNKNOWN(HYPOTHETICAL_CONDITIONAL)', '오른쪽 팔다리에 힘이 안 들어가요→limb_weakness:present→ABSENT(NEG:안)', '날짜랑 요일이 자꾸 헷갈려요→confusion:present→POSSIBLE(UNSURE_IN_CLAUSE)']
- pilot 시점 불일치(P5): ['기침이 한번 시작하면 멈추질 않아요→cough:present→RESOLVED', '토했어요→vomiting:present→PAST', '아침부터 세 번이나 토했어요→vomiting:present→PAST', '기침하다가 토했어요→vomiting:present→PAST', '웩웩거리면서 토했어요→vomiting:present→PAST', '변이 묽어졌어요→diarrhea:present→PAST', '기절했어요→loc:present→PAST', '잠깐 의식을 잃었었어요→loc:present→PAST']

## 5. 단위 테스트

- test_evaluative_negation 5/5 · test_evaluator_v5 3/3 · test_experiencer 1/1 · test_mixed_disease_symptom 2/2 · test_mixed_medication_symptom 3/3 · test_model_input_isolation 1/1 · test_multi_span 2/2 · test_negation_scope 1/1 · test_temporal_resolution 4/4 · test_unsupported_inputs 2/2

## 6. 답(§18)

1. STEP29 공식 위반 2건: 검사기 v4 가 문장 전체에 규칙을 적용해, 다른 구문의 '고혈압'·'기침약' 때문에 올바른 '머리 통증'·'기침' 연결을 위반으로 셈(같은 혼합 정상 문장에서 v4 오판 2, v5 0).
2. 검사기 v5: 정상 mention 2764 오판 0 · 위험 사례 15 누락 0. STEP29 NLU 출력 위반 입력 v4 8 → v5 4(검사기 효과). P5 위반 입력 4.
3. '입맛은 괜찮아요': 새 계약 EVAL 통과 P1 5 → P5 12/12(세부 negation_analysis.csv). 이 사례는 STEP29 평가에서 본 것 → 독립 개선 근거 아님.
4. '괜찮다' 과잉 부정: '이제 괜찮아요'·'검사 결과는 괜찮아요'·'괜찮지 않아요' 등 새 계약 EVAL 포함 — P5 EVAL 12/12. 전향적 세트에는 평가형 문장이 없음(검증 범위 한계).
5. 과거·해소: 새 계약 RES P1 4 → P5 8/8 · 전향적 T4_RESOLVED P1 0 → P5 0/10 · 대조 T4_CONTROL(해소 아님) P5 0/20 · pilot 시점 일치 0.8846 → 0.8742.
6. 다중 증상: pilot 다중 보존 0.675 → 0.625 · 전향적 T2_BOTH P5 30/30 · 과분할(새 계약) 0 · 중복 구간 mention 0.
7. 혼합 질환·약물·증상: 새 계약 MIX P5 7/7 · 전향적 T6_DRUG_SYM 15/15 · T6_DIS_SYM 15/15 · T6_DRUG_ONLY 5/5 · T6_DIS_ONLY 5/5.
8. 남은 P5 매핑 오류: pilot 잘못된 concept mention P0 12 · P1 21 · P5 19 · STEP29 계약 실패 P5 3(P5 원본 한계: '토하' 모호·생략 부위·중간 부사절).
9. 연결 불가 발화 자동 연결: P1 8 → P5 7/28(STEP29 정의) · 그중 환자 양성 모델 입력 P1 2 → P5 0. 남은 것의 다수는 가족 증상을 OTHER_PERSON 으로 올바로 추출한 경우(라벨 정의 차이).
10. 정밀도·coverage: REGRESSION168 precision 0.9333 → 0.9302 · coverage 0.625 → 0.5119(P0 0.9451/0.5417).
11. 77·SILVER 출처·지원 상태: 신규·하위·SILVER 단독 모델 입력 0 · STEP28.7 SILVER 근거 필드 유지(evidence_level·isolation_status).
12. 독립 Gold 없음: 결론은 '노출 회귀·사전 계약·템플릿 합성(전향적 194/231 → 194/231)에서 규칙이 의도대로 동작'까지. 실제 환자 발화 정확도·임상 안전성은 말할 수 없음(HUMAN_VERIFIED_GOLD 0).
13. STEP30: 판정은 step29_1_verdict.json — 연구용 제품 연결 '설계' 시작 여부만 판단, 실제 연동은 하지 않음.

## 7. 사후 발견·탐색(EXPLORATORY_POST_HOC — 공식 판정 아님)

- 공식 REGRESSION 의 원인 = P5 가드의 coverage 손실(S1·S2 동시 FAIL). hard 게이트 10 개는 전부 PASS.
- 가드별 pilot 차단(정답 concept 차단 / 오답 차단): {"EVIDENCE_IDEOPHONE_MISSING:blocked_correct": 3, "EVIDENCE_IDEOPHONE_MISSING:blocked_wrong": 1, "MODEL_ONLY_NO_CUE:blocked_correct": 24, "MODEL_ONLY_NO_CUE:blocked_wrong": 1} — 'B4 단독 + 증상 단서 없음' 이 정답 24 를 막음
  (STEP27 SYMPTOM_CUE 사전이 '몸이 펄펄 끓어요'·'게워냈어요'·'목이 칼칼해요' 같은 말바꿈을 모름).
- 규칙 하나씩 끈 변형: {"P5_official": {"reg_precision": 0.9302, "reg_coverage": 0.5119, "pilot_multi_retention": 0.625, "G5_pilot_absent+new_contract": 0}, "P5_minus_PAIN_PREDICATE_MISMATCH": {"reg_precision": 0.9302, "reg_coverage": 0.5119, "pilot_multi_retention": 0.625, "G5_pilot_absent+new_contract": 0}, "P5_minus_LEXICAL_OVERLAP_ZERO": {"reg_precision": 0.9302, "reg_coverage": 0.5119, "pilot_multi_retention": 0.625, "G5_pilot_absent+new_contract": 0}, "P5_minus_EVIDENCE_IDEOPHONE_MISSING": {"reg_precision": 0.931, "reg_coverage": 0.5179, "pilot_multi_retention": 0.6375, "G5_pilot_absent+new_contract": 0}, "P5_minus_MODEL_ONLY_NO_CUE": {"reg_precision": 0.9327, "reg_coverage": 0.619, "pilot_multi_retention": 0.6625, "G5_pilot_absent+new_contract": 0}}
  → B4 가드를 빼면 P4 수준 회복에 가까우나 precision 0.9333 바로 아래 — 채택 안 함(평가 후 변경 금지). 다음 단계에서 사전 고정 후 재평가 대상.
- P3·P4 단계 자체는 손실 없음: P4 = precision 0.9333 · coverage 0.625 · 다중 0.675, 단 P4 는 hard G5 2(가정·질문 표현 미처리) → P5 의 가정·질문 가드가 G5 를 0 으로 만듦.
- 전향적 T4_RESOLVED 0/10(모든 정책): 생성 문장 '…났어요 오늘은 괜찮아요.' 가 첫 문장 뒤 마침표 없이 한 문장으로 분석됨([[0, 'NORMAL', '기침이 났어요 오늘은 괜찮아요']]) — 문장부호 없는 입력(음성 전사)에서 문장·절 분리가 안 되는 한계. 생성기 결함이기도 함(마침표 누락).
- **새 오류(P3 도입)**: 문장부호 없는 '…했어요 오늘은 괜찮아요' 가 한 단위가 되어 '괜찮' 이 과거 증상 mention 의 술어로 잡힘 → 과거 증상 ABSENT 10 건(전향적 T4_RESOLVED 전부, P1 0).
  예 ['열이 났어요 오늘은 괜찮아요.', '숨이 찼어요 오늘은 괜찮아요.', '구토를 했어요 오늘은 괜찮아요.']. 지시문 §4 가 금지한 '괜찮다 과잉 부정' 이 문장 분리 실패와 겹쳐 발생 — 다음 단계 필수 수정(평가형 술어는 같은 절·같은 문장 안 mention 명사에만, EF 종결 기준 분리).
- 검사기 v5 위반(P5) 4: ['PROS:V5_NAUSEA_AS_VOMITING:속이 메스꺼웠어요 오늘은 구토를 해요', 'SIL:V5_DISEASE_TERM:박동성두통이', 'SIL:V5_DISEASE_TERM:회전성 어지럼증이', 'WN:V5_DISEASE_TERM:편두통성 어지럼증이'] — '박동성 두통'·'회전성 어지럼증' 은 증상 성질 수식어인데 v5 의 'X성' 진단형 규칙이 위반으로 셈(검사기 한계, 경과 수식어 목록에 성질 수식어 없음).
  '속이 메스꺼웠어요 오늘은 구토를 해요' 는 문장 미분리로 두 증상이 한 범위에 들어간 경우.
- 전향적 정상화 실패 P1 8 → P5 14(가드 영향 포함) · 모델 양성 금지 위반 P1 9 → P5 0.
