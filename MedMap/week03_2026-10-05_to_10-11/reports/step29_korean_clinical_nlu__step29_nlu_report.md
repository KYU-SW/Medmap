# STEP29 — Korean Clinical NLU(연구용)

- **STEP30_READINESS = NO_GO** · STEP29_RESULT = **REGRESSION** · PRODUCTION_READY = NO · HUMAN_VERIFIED_GOLD = 0
- hard: {"G1": "PASS", "G2": "PASS", "G3": "FAIL", "G4": "FAIL", "G5": "PASS", "G6": "PASS", "G7": "PASS", "G8": "PASS", "G9": "PASS"} · soft: {"S1": "PASS", "S2": "PASS", "S3": "PASS", "S4": "PASS", "S5": "PASS"} · S3 {"assertion": "PASS", "temporality": "PASS", "experiencer": "PASS"}
- 규칙 고정 순서: 계약 68(SHA `bd02a437fa1ef9d8…`) → 검사기 v4(SHA `75f3bf53481eb78e…`) → 게이트(이 파일) → 구현(계약으로만 개발) → 코드 동결(`data/prereg.json`) → 평가 1회.
- 데이터: pilot_gold 274(합성·Claude 작성·STEP21–28.8 반복 노출, 부정·시점·주체 라벨) · REGRESSION168(그 부분집합) · SILVER442·WEAKNON903(약한 라벨) · 계약 68·metamorphic(개발용, 규칙 작성자가 작성). 사람 검증 Gold 없음 → 임상 정확도 아님.

## 1. 최종 보고

| 항목 | 값 |
|---|---|
| STEP29_RESULT | REGRESSION |
| MULTI_SPAN_RETENTION | 0.675(NLU_P0 0.525, pilot_gold 다중 발화 mention 80) |
| SPAN_BOUNDARY_VALIDITY | 1.0 |
| NEGATION_SCOPE_RESULT | pilot assertion 일치 0.9066(n 182) · 계약 assertion 통과 1.0 |
| TEMPORALITY_RESULT | pilot 시점 일치 0.8846 · 계약 시점 통과 1.0 |
| EXPERIENCER_RESULT | pilot 주체 일치 1.0 · 계약 주체 통과 1.0 |
| CONCEPT_MAPPING_RESULT | REGRESSION168 precision 0.9333 · coverage 0.625 · pilot 잘못된 concept mention 21 |
| SEMANTIC_VIOLATIONS | 2 |
| UNSUPPORTED_CONCEPT_PRESERVATION | should_link False 발화 auto 8/28 · 원문 보존 1.0 |
| RAW_PRESERVATION | 1.0 |
| CPU_P95_MS | 43.769 |
| STEP30_READINESS | NO_GO |
| PRODUCTION_READY | NO |
| HUMAN_VERIFIED_GOLD | 0 |

## 2. 정책 비교(NLU_P0 = STEP28.8 P5 단독 · P1 구문 분해 · P2 +부정 · P3 +시점 · P4 +주체 · P5 +의미 충돌 검증·SILVER)

| 지표 | NLU_P0 | NLU_P1 | NLU_P2 | NLU_P3 | NLU_P4 | NLU_P5 |
|---|---|---|---|---|---|---|
| n_inputs | 1687 | 1687 | 1687 | 1687 | 1687 | 1687 |
| n_mentions | 1759 | 1774 | 1774 | 1774 | 1774 | 1774 |
| G1_raw_ok_rate | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| G2_offset_valid_rate | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| G3_semantic_violation_inputs | 4 | 4 | 4 | 4 | 4 | 2 |
| G4_neg_safety_errors | 1 | 25 | 1 | 1 | 1 | 1 |
| G5_other_safety_errors | 1 | 16 | 16 | 15 | 0 | 0 |
| G6_silver_or_new_model_input | 0 | 0 | 0 | 0 | 0 | 0 |
| G9_uncertain_without_reason | 4 | 0 | 0 | 0 | 0 | 0 |
| contract_mentions | 78 | 78 | 78 | 78 | 78 | 78 |
| contract_extracted | 72 | 78 | 78 | 78 | 78 | 78 |
| contract_failed_cases | 46 | 47 | 34 | 11 | 6 | 3 |
| err1_not_extracted | 6 | 0 | 0 | 0 | 0 | 0 |
| err2_wrong_normalization | 11 | 5 | 5 | 5 | 5 | 3 |
| err3_negation | 4 | 19 | 0 | 0 | 0 | 0 |
| err4_temporality | 27 | 29 | 29 | 0 | 0 | 0 |
| err5_experiencer | 1 | 5 | 5 | 5 | 0 | 0 |
| err_other(attr/onset/freq/scope/role/must_not) | 15 | 6 | 6 | 1 | 1 | 0 |
| contract_assertion_pass | 0.9444 | 0.7564 | 1.0 | 1.0 | 1.0 | 1.0 |
| contract_temporality_pass | 0.625 | 0.6282 | 0.6282 | 1.0 | 1.0 | 1.0 |
| contract_experiencer_pass | 0.9861 | 0.9359 | 0.9359 | 0.9359 | 1.0 | 1.0 |
| pilot_gold_mentions | 293 | 293 | 293 | 293 | 293 | 293 |
| pilot_matched | 153 | 185 | 185 | 185 | 185 | 182 |
| pilot_retention | 0.5222 | 0.6314 | 0.6314 | 0.6314 | 0.6314 | 0.6212 |
| pilot_multi_n | 80 | 80 | 80 | 80 | 80 | 80 |
| pilot_multi_retention | 0.525 | 0.675 | 0.675 | 0.675 | 0.675 | 0.675 |
| pilot_assertion_agreement | 0.9346 | 0.9243 | 0.9081 | 0.9081 | 0.9081 | 0.9066 |
| pilot_temporality_agreement | 0.9346 | 0.9351 | 0.9351 | 0.8811 | 0.8811 | 0.8846 |
| pilot_experiencer_agreement | 0.9935 | 0.9351 | 0.9351 | 0.9351 | 1.0 | 1.0 |
| pilot_wrong_concept_mentions | 12 | 22 | 22 | 22 | 22 | 21 |
| pilot_unsupported_auto | 7 | 8 | 8 | 8 | 8 | 8 |
| pilot_unsupported_n | 28 | 28 | 28 | 28 | 28 | 28 |
| reg_coverage | 0.5417 | 0.6429 | 0.6429 | 0.6429 | 0.6429 | 0.625 |
| reg_precision | 0.9451 | 0.9259 | 0.9259 | 0.9259 | 0.9259 | 0.9333 |
| silver_mentions | 423 | 413 | 413 | 413 | 413 | 413 |
| silver_unknown_uncertain_rate | 0.2861 | 0.2591 | 0.2591 | 0.2591 | 0.2591 | 0.2591 |
| weaknon_positive_inputs | 10 | 18 | 18 | 18 | 18 | 17 |
| weaknon_positive_present_inputs | 10 | 18 | 18 | 18 | 18 | 17 |
| model_input_eligible_mentions | 337 | 408 | 403 | 362 | 347 | 340 |
| metamorphic_pass | 46/54 | 36/54 | 42/54 | 48/54 | 54/54 | 54/54 |

## 3. 오류 분석(별도 집계)

- NLU_P5 오류 수(세트, 종류): {":WRONG_NORMALIZATION": 3, "PILOT274:MISSED_OR_UNMAPPED": 111, "PILOT274:NEGATION": 17, "PILOT274:TEMPORALITY": 21, "PILOT274:WRONG_CONCEPT": 21}
- 1 추출·연결 실패(pilot): ['아까부터 명치 쪽이 콕콕 쑤셔요(pain→None:UNCERTAIN)', '머리가 지끈지끈해요(pain→None:UNKNOWN_SYMPTOM)', '허리가 끊어질 것 같아요(pain→None:UNKNOWN_SYMPTOM)', '머리가 깨질 것 같아요(pain→None:UNKNOWN_SYMPTOM)', '배가 꼬이는 것처럼 아파요(pain→None:UNKNOWN_SYMPTOM)', '가슴 한가운데가 묵직하게 눌리는 느낌이에요(pain→palpitations:EXISTING_CANONICAL)']
- 2 잘못된 concept(pilot): ['가슴 한가운데가 묵직하게 눌리는 느낌이에요(pain→palpitations|가슴)', '노란 물 같은 걸 토했어요(vomiting→diarrhea|물 같)', '정신이 아찔해요(dizziness→confusion|정신이 아찔해)', '깨어 보니까 바닥에 누워 있었어요(loc→fatigue|바닥)', '기침하면 피가 같이 나와요(hemoptysis→cough|기침)', '기침하다가 피를 뱉었어요(cough;hemoptysis→fatigue|피)']
- 3 부정: ['머리는 안 아픈데 배가 아파요(pain:present:patient→ABSENT|CURRENT|PATIENT|머리는 안 아픈)', '해열제를 먹어도 열이 안 떨어져요(fever:present:patient→ABSENT|CURRENT|PATIENT|열)', '밤마다 기침 때문에 잠을 못 자요(cough:present:patient→ABSENT|CURRENT|PATIENT|기침)', '구토가 멈추질 않아요(vomiting:present:patient→ABSENT|CURRENT|PATIENT|구토가 멈추)', '기력이 없어요(fatigue:present:patient→ABSENT|CURRENT|PATIENT|기력)', '피곤하고 입맛도 없어요(decreased_appetite:present:patient→ABSENT|CURRENT|PATIENT|입맛도 없)']
- 4 시점: ['토했어요(vomiting:present:patient→PRESENT|PAST|PATIENT|토했)', '아침부터 세 번이나 토했어요(vomiting:present:patient→PRESENT|PAST|PATIENT|번이나 토했)', '먹은 걸 다 게워냈어요(vomiting:present:patient→PRESENT|PAST|PATIENT|먹)', '기침하다가 토했어요(vomiting:present:patient→PRESENT|PAST|PATIENT|토했)', '웩웩거리면서 토했어요(vomiting:present:patient→PRESENT|PAST|PATIENT|토했)', '변이 묽어졌어요(diarrhea:present:patient→PRESENT|PAST|PATIENT|변이 묽)']
- 5 주체: []
- 계약 미추출: [] · 계약 정규화: ['토하지 않았어요(→None)', '지난주에 가슴이 아팠는데 지금은 안 아파요(→None)', '숨 쉴 때마다 옆구리가 찌르듯이 아파요(→None)']

## 4. Metamorphic(규칙 일관성 — 임상 정확도 아님)

- {"base_has_concept": "6/6", "neg_concept_stable": "6/6", "neg_absent": "6/6", "past_concept_stable": "6/6", "past_temporality": "6/6", "other_concept_stable": "6/6", "other_experiencer": "6/6", "plus_retains_base": "6/6", "irrelevant_span_stable": "6/6"}

## 5. 단위 테스트

- test_experiencer 3/3 · test_metamorphic 1/1 · test_multi_span 3/3 · test_negation_scope 2/2 · test_p5_adapter 2/2 · test_provenance 2/2 · test_semantic_distinctions 3/3 · test_span_offsets 1/1 · test_temporality 3/4

## 6. 답(§23)

1. 여러 증상 추출: pilot_gold 다중 발화 mention 회수율 NLU_P5 0.675(NLU_P0 0.525, 분모 80) · 전체 회수율 0.6212(P0 0.5222).
2. 첫 증상만 선택: NLU 는 절·단위마다 P5 를 따로 호출해 mention 을 모두 반환(STEP28.8 의 '첫 auto' 는 지표 정의였음). 계약 다중 사례 결과 = 계약 실패 사례 3/68 중 MULTI 범주는 eval_errors.csv.
3. 부정 범위: pilot assertion 일치 0.9066(P0 0.9346, 대응 mention 182) · 계약 1.0 · 부정 안전 오류(G4) 1.
4. 과거·현재: pilot 시점 일치 0.8846(P0 0.9346 — P0 는 시점 미분석) · 계약 1.0.
5. 환자·가족: pilot 주체 일치 1.0(P0 0.9935) · 계약 1.0 · 타인 안전 오류(G5) 0.
6. 의성어·양상: mention attributes 로 원문 보존(계약 ATTRIBUTE 오류는 eval_errors). 정규화 손실 충돌은 IDEOPHONE_MISMATCH 가드로 UNCERTAIN 처리(P5 nkey 는 그대로).
7. P5 오매핑 영향: pilot 잘못된 concept mention NLU_P5 21(P0 12) · REGRESSION168 precision 0.9333/coverage 0.625(P0 0.9451/0.5417, STEP28.8 0.9451/0.5417).
8. 77 + 신규 SILVER 동시 처리: 같은 문장 mention 별로 기록(SILVER 근거·등급·격리 상태 보존) · 신규·SILVER 단독의 모델 입력 표시(G6) 0.
9. 부정·가족 증상의 모델 입력 위험: 사전 정의 안전 회귀에서 G4 1 · G5 0(제한된 회귀 기준 — 임상 안전성 보장 아님). 주체 생략은 PATIENT 가정(ASSUMED_INTAKE_DEFAULT 표시).
10. 처리 못 하는 유형: 생략된 대상('지금은 안 아파요' 의 부위) · 중간 부사절('찌르듯이') · P5 모호('토하') · 연결 불가 발화 auto 8/28 · 세부는 오류 분석.
11. 오프라인: LLM·네트워크 없음, CPU p95 43.769 ms · peak RSS 1347.5 MiB.
12. STEP30 전 필요: 사람 검증 Gold(부정·시점·주체 포함) · 주체 기본값 정책(가정 PATIENT) 결정 · P5 nkey 손실·B4 오연결 처리 · PatientState 입력 규칙(PAST·POSSIBLE 처리) 설계 · 실제 음성 전사 문장 평가.

## 7. 사후 발견·탐색 v2(EXPLORATORY_POST_HOC — 공식 판정 아님)

- 공식 REGRESSION 원인 ① G3 2건 = **검사기 v4 결함**(문장 단위 적용): '고혈압이 있고 머리가 아파요'·'기침약을 먹었는데 기침이 계속 나요' 는 NLU 가 비증상(고혈압·기침약)과 증상(머리 통증·기침)을 올바로 분리했으나 문장에 고혈압·기침약이 있어 위반으로 셈. 검사기 정답 대조에 다중 구문 문장을 넣지 않은 실수.
- ② G4 1건 = **실제 NLU 오류**: '입맛은 괜찮아요'(pilot gold decreased_appetite absent) → 부정 표지가 없어 PRESENT.
- v2(동결 파일 무수정, 실행 중 덮어쓰기): 검사기를 mention 단위로 적용 + '괜찮' 평가형 부정 → {"G3_sentence_level(v4 공식 방식)": 2, "G3_mention_level(v2)": 0, "G4_neg_safety_errors": 0, "contract_failed_cases": 3, "pilot_retention": 0.6212, "pilot_assertion_agreement": 0.9121, "reg_precision": 0.9333, "reg_coverage": 0.625}
  → hard {"G1": "PASS", "G2": "PASS", "G3": "PASS", "G4": "PASS", "G5": "PASS", "G6": "PASS", "G7": "PASS", "G8": "PASS", "G9": "PASS"} → **NLU_FEASIBLE / GO_FOR_RESEARCH(탐색)**. '괜찮' 규칙은 평가 세트 오류를 보고 만든 것 → 일반화 근거 아님. 다음 단계에서 사전 고정 후 새 자료로 재검증 필요.
- 단위 테스트 실패(공식 실행): {"test_temporality": ["Traceback (most recent call last):\n  File \"/home/<user>/medmap-worktrees/symptom-ontology/exp/step29_korean_clinical_nlu/tests/test_temporality.py\", line 14, in test_past_and_resolved\n    self.assertEqual(find(\"어제는 숨이 찼는데 오늘은 괜찮아요\", \"숨\")[\"temporality\"], \"RESOLVED\")\nAssertionError: 'PAST' != 'RESOLVED'\n- PAST\n+ RESOLVED\n\n"]} — '어제는 숨이 찼는데 오늘은 괜찮아요' 가 RESOLVED 대신 PAST('오늘은 괜찮아요' 절이 mention 으로 남아 해소 단서로 쓰이지 않음). 계약은 PAST 도 허용해 통과.
- 계약 실패 3(P5 한계, 모두 '미연결'로 안전): '토하지 않았어요'(P5 '토하' 모호) · '지금은 안 아파요'(생략된 부위) · '숨 쉴 때마다 옆구리가 찌르듯이 아파요'(중간 부사절 → pain 미연결, dyspnea 오연결은 없음).
