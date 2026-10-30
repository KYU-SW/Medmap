# STEP29.2 — MedMap Clinical NLU Recovery & ASR Robustness 보고서

이 문서의 숫자는 build_report.py 가 outputs/ 에서 읽어 생성(손으로 쓰지 않음).

## 판정
- **STEP29_2_RESULT = RECOVERY_PASS** · **STEP30_READINESS = CONDITIONAL_GO** · PRODUCTION_READY = NO · HUMAN_VERIFIED_GOLD = 0
- 선택 정책(DEV + 노출 pilot 만으로 사전 규칙 선택, HOLDOUT 미사용) = **V3_B0**
- Hard: G1 PASS · G2 PASS · G3 PASS · G4 PASS · G5 PASS · G6 PASS · G7 PASS · G8 PASS · G9 PASS · G10 PASS
- Recovery(공식, HOLDOUT 같은 입력 비교): R1 PASS · R2 PASS · R3 PASS · R4 PASS · R5 PASS · R6 PASS · R7 PASS · R8 PASS
- 개발 목표(노출 자료의 STEP29 절대 수치): D1 PASS · D2 FAIL · D3 FAIL · D4 PASS · D5 PASS
- EVALUATOR_V6 = PASS(정상 2805 오판 0 · 위험 35 누락 0 · 같은 세트 v5 오판 4·누락 11)
- STEP29.1 공식 REGRESSION 판정은 그대로 유지(이 단계는 별도 실험).

## 데이터(모두 합성 — 사람 검증 Gold 아님)
- HOLDOUT 1052 입력(마침표 쌍 357 묶음, 범주 {'CONFUSABLE': 10, 'EVAL_NEG': 75, 'EXPERIENCER': 120, 'HEDGE_DNEG': 40, 'MODIFIER': 14, 'MULTI2': 82, 'MULTI3': 49, 'NEG_SCOPE': 86, 'NON_SYMPTOM': 150, 'REPETITION': 35, 'RESOLUTION': 188, 'SHORT_ASR': 43, 'SILVER': 6, 'SINGLE': 32, 'TEMPORAL_CONTROL': 114, 'UNKNOWN': 8}) — 동결 후 1회 실행. DEV 405 입력 — 개발·정책 선택.
- 생성: 의미 구조(슬롯) → 문장. DEV/HOLDOUT 은 연결 틀·문맥 어휘·증상 조합이 분리(누수 검사 0 문자열·0 증상 조합 겹침,
  증상 표현을 자리표시로 바꾼 일반 나열형 틀 4종은 양쪽에 있으나 의미 구조(부정·시점 슬롯)는 다름).
- 기존 노출 자료와 문자열 중복 제외(24건). 노출 회귀: pilot 274 · STEP29 계약 68 · STEP29.1 계약 42 · 전향적 231.
- 개발 중 HOLDOUT 문장 노출: 단위 테스트 입력 2개('회전성 어지럼증이 있어요'·'기침이 나요 머리는 괜찮아요' — 지시문 예시와 같은 문장)가 HOLDOUT 과 겹쳐 개발 중 실행됨 → 동결 전 다른 문장으로 교체, 이 두 출력으로 규칙을 바꾸지 않음.

## HOLDOUT 정책 비교(같은 입력)
| 지표 | S29 | S291 | V3_B0 | V3_B1 | V3_B2 | V3_B3 |
|---|---|---|---|---|---|---|
| MULTI_SPAN_RETENTION | 0.8418 | 0.6764 | 0.9292 | 0.9043 | 0.9251 | 0.9251 |
| CONCEPT_PRECISION | 0.9874 | 0.9866 | 0.9972 | 0.9985 | 0.9986 | 0.9986 |
| CONCEPT_COVERAGE | 0.8453 | 0.7031 | 0.9085 | 0.8782 | 0.9032 | 0.9032 |
| NEGATION_SCOPE | 0.7810 | 0.8340 | 0.9987 | 0.9987 | 0.9987 | 0.9987 |
| EVALUATIVE_NEGATION | 0.0000 | 0.3333 | 0.9733 | 0.9067 | 0.9733 | 0.9733 |
| TEMPORALITY | 0.9007 | 0.9095 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| RESOLUTION_LINKING | 0.0000 | 0.2663 | 0.8967 | 0.8967 | 0.8967 | 0.8967 |
| RESOLUTION_FALSE_LINK | 0 | 0 | 0 | 0 | 0 | 0 |
| EXPERIENCER | 0.9641 | 0.9640 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| UNSUPPORTED_AUTO_LINK | 0/18 | 0/18 | 0/18 | 0/18 | 0/18 | 0/18 |
| PUNCTUATION_PAIR_CONSISTENCY | 0.5770 | 0.4930 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| SPAN_BOUNDARY_VALIDITY | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| SEMANTIC_VIOLATIONS | 0 | 0 | 0 | 0 | 0 | 0 |
| PROPAGATION_ERRORS | 186 | 245 | 0 | 0 | 0 | 0 |
| NEG_POSITIVE | 0 | 0 | 0 | 0 | 0 | 0 |
| OTHER_POSITIVE | 0 | 0 | 0 | 0 | 0 | 0 |
| OVER_SPLIT | 6 | 0 | 4 | 2 | 4 | 4 |
| B4_GUARD_CORRECT_BLOCKS | 0 | 2 | 0 | 2 | 2 | 2 |
| B4_GUARD_WRONG_BLOCKS | 0 | 25 | 0 | 48 | 8 | 8 |
| CASE_PASS_RATE | 0.4011 | 0.4259 | 0.8660 | 0.8241 | 0.8603 | 0.8603 |

문장 분리(마침표 없는 다문장 입력의 내부 경계):

| 정책 | F1 | precision | recall |
|---|---|---|---|
| S29 | 0.0 | 1.0 | 0.0 |
| S291 | 0.0 | 1.0 | 0.0 |
| V3_B0 | 0.9898 | 1.0 | 0.9798 |
| V3_B1 | 0.9898 | 1.0 | 0.9798 |
| V3_B2 | 0.9898 | 1.0 | 0.9798 |
| V3_B3 | 0.9898 | 1.0 | 0.9798 |

Metamorphic(통과/대상):

| 관계 | S29 | S291 | V3_B0 | V3_B1 | V3_B2 | V3_B3 |
|---|---|---|---|---|---|---|
| NEG_SCOPE | 0/2 | 0/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| TEMPORAL | 17/40 | 14/40 | 34/40 | 34/40 | 34/40 | 34/40 |
| EXPERIENCER | 32/32 | 32/32 | 32/32 | 32/32 | 32/32 | 32/32 |
| MULTI | 40/40 | 34/40 | 39/40 | 39/40 | 39/40 | 39/40 |
| MODIFIER | 7/7 | 5/7 | 7/7 | 6/7 | 7/7 | 7/7 |
| UNSUP | 7/7 | 7/7 | 7/7 | 7/7 | 7/7 | 7/7 |

범주별 case 통과:

| 범주 | S29 | S291 | V3_B0 | V3_B1 | V3_B2 | V3_B3 |
|---|---|---|---|---|---|---|
| CONFUSABLE | 8/10 | 6/10 | 6/10 | 6/10 | 6/10 | 6/10 |
| EVAL_NEG | 0/75 | 25/75 | 73/75 | 68/75 | 73/75 | 73/75 |
| EXPERIENCER | 51/120 | 53/120 | 118/120 | 105/120 | 118/120 | 118/120 |
| HEDGE_DNEG | 38/40 | 36/40 | 38/40 | 38/40 | 38/40 | 38/40 |
| MODIFIER | 14/14 | 10/14 | 14/14 | 12/14 | 14/14 | 14/14 |
| MULTI2 | 74/82 | 63/82 | 82/82 | 82/82 | 82/82 | 82/82 |
| MULTI3 | 22/49 | 17/49 | 45/49 | 45/49 | 45/49 | 45/49 |
| NEG_SCOPE | 14/86 | 10/86 | 61/86 | 54/86 | 61/86 | 61/86 |
| NON_SYMPTOM | 87/150 | 77/150 | 134/150 | 130/150 | 136/150 | 136/150 |
| REPETITION | 29/35 | 29/35 | 35/35 | 32/35 | 35/35 | 35/35 |
| RESOLUTION | 4/188 | 34/188 | 140/188 | 136/188 | 136/188 | 136/188 |
| SHORT_ASR | 19/43 | 11/43 | 34/43 | 31/43 | 34/43 | 34/43 |
| SILVER | 4/6 | 4/6 | 4/6 | 4/6 | 4/6 | 4/6 |
| SINGLE | 28/32 | 26/32 | 30/32 | 30/32 | 30/32 | 30/32 |
| TEMPORAL_CONTROL | 22/114 | 39/114 | 89/114 | 86/114 | 85/114 | 85/114 |
| UNKNOWN | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 |

## 노출 회귀 세트(STEP29.1 과 같은 정의, legacy view)
| 지표(노출) | S29 | S291 | V3_B0 | V3_B1 | V3_B2 | V3_B3 |
|---|---|---|---|---|---|---|
| pilot_multi_retention | 0.6750 | 0.6250 | 0.6875 | 0.6500 | 0.6875 | 0.6875 |
| pilot_assertion_agreement | 0.9066 | 0.9371 | 0.9505 | 0.9503 | 0.9500 | 0.9500 |
| pilot_temporality_agreement | 0.8846 | 0.8742 | 0.8846 | 0.8820 | 0.8833 | 0.8833 |
| pilot_experiencer_agreement | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| reg_precision | 0.9333 | 0.9302 | 0.9327 | 0.9302 | 0.9320 | 0.9505 |
| reg_coverage | 0.6250 | 0.5119 | 0.6190 | 0.5119 | 0.6131 | 0.6012 |
| pilot_unsupported_auto | 8 | 7 | 7 | 7 | 7 | 7 |
| pilot_wrong_concept_mentions | 21 | 19 | 20 | 19 | 20 | 18 |
| B4_GUARD_CORRECT_BLOCKS(pilot) | 0 | 1 | 0 | 1 | 0 | 2 |
| B4_GUARD_WRONG_BLOCKS(pilot) | 0 | 24 | 0 | 24 | 3 | 3 |
| C29_failed | 3 | 3 | 3 | 3 | 3 | 3 |
| NEW42_pass | 25 | 42 | 41 | 41 | 41 | 41 |
| PROS231_pass | 194 | 194 | 224 | 224 | 224 | 224 |
| G5_exposed | 8 | 0 | 0 | 0 | 0 | 0 |
| G6_exposed | 0 | 0 | 0 | 0 | 0 | 0 |
| G7_mentions | 0 | 0 | 0 | 0 | 0 | 0 |
| G10_mentions | 0 | 0 | 0 | 0 | 0 | 0 |

## DEV(개발 세트)
| 지표 | S29 | S291 | V3_B0 | V3_B1 | V3_B2 | V3_B3 |
|---|---|---|---|---|---|---|
| MULTI_SPAN_RETENTION | 0.8928 | 0.7246 | 0.9797 | 0.8928 | 0.9797 | 0.9797 |
| CONCEPT_PRECISION | 0.9868 | 0.9845 | 0.9965 | 0.9962 | 0.9965 | 0.9965 |
| CONCEPT_COVERAGE | 0.8891 | 0.7553 | 0.9613 | 0.9014 | 0.9613 | 0.9613 |
| NEGATION_SCOPE | 0.7512 | 0.8706 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| EVALUATIVE_NEGATION | 0.0000 | 0.4444 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| TEMPORALITY | 0.9455 | 0.9489 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| RESOLUTION_LINKING | 0.0000 | 0.3968 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| RESOLUTION_FALSE_LINK | 0 | 0 | 0 | 0 | 0 | 0 |
| EXPERIENCER | 0.9794 | 0.9792 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| UNSUPPORTED_AUTO_LINK | 0/14 | 0/14 | 0/14 | 0/14 | 0/14 | 0/14 |
| PUNCTUATION_PAIR_CONSISTENCY | 0.6319 | 0.5625 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| SPAN_BOUNDARY_VALIDITY | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| SEMANTIC_VIOLATIONS | 0 | 0 | 0 | 0 | 0 | 0 |
| PROPAGATION_ERRORS | 79 | 79 | 0 | 0 | 0 | 0 |
| NEG_POSITIVE | 0 | 0 | 0 | 0 | 0 | 0 |
| OTHER_POSITIVE | 0 | 0 | 0 | 0 | 0 | 0 |
| OVER_SPLIT | 0 | 0 | 0 | 0 | 0 | 0 |
| B4_GUARD_CORRECT_BLOCKS | 0 | 0 | 0 | 0 | 0 | 0 |
| B4_GUARD_WRONG_BLOCKS | 0 | 14 | 0 | 34 | 0 | 0 |
| CASE_PASS_RATE | 0.4346 | 0.5012 | 0.9457 | 0.8617 | 0.9457 | 0.9457 |

## 정책 선택(gates.select_policy, 평가 전 고정 규칙)
| 정책 | 자격 | DEV coverage + REG coverage | DEV precision + REG precision |
|---|---|---|---|
| V3_B0 | True | 1.5803 | 1.9292 |
| V3_B1 | True | 1.4133 | 1.9264 |
| V3_B2 | True | 1.5744 | 1.9285 |
| V3_B3 | True | 1.5625 | 1.947 |

## 선택 정책의 HOLDOUT 오류 사례(유형별 일부)
- **WRONG_CONCEPT** (8건 표시): `토하지는 않아요.` →  / `토하지는 않아요` →  / `머리가 아파요. 설사를 해요. 속은 안 쓰려요.` →  / `머리가 아파요 설사를 해요 속은 안 쓰려요` → 
- **NOT_EXTRACTED** (8건 표시): `토하지는 않아요. 이제는 다리에 힘이 없어요.` →  / `토하지는 않아요 이제는 다리에 힘이 없어요` →  / `근데 토하지는 않아요 이제는 다리에 힘이 없어요` →  / `토하지는않아요 이제는다리에 힘이 없어요` → 
- **EXTRA_WRONG_CONCEPT** (4건 표시): `목은 괜찮은지 헷갈려요.` → confusion|헷갈려 / `목은 괜찮은지 헷갈려요` → confusion|헷갈려 / `날씨가 많이 추워요.` → chills|날씨가 많이 추워 / `날씨가 많이 추워요` → chills|날씨가 많이 추워
- **UNEXPECTED_SYMPTOM** (2건 표시): `날씨가 많이 추워요.` → ["chills"] / `날씨가 많이 추워요` → ["chills"]
- **ASSERTION** (2건 표시): `밤에 잠이 안 와요.` → ABSENT / `밤에 잠이 안 와요` → ABSENT

## 지연·메모리
- outputs/latency.json(실행마다 값이 조금 다름 — 재현 SHA 비교 대상 아님). 판정 R8 은 그 파일의 V3_B0 p95 사용.

## 재현·보호
- 단위 테스트 38개 · 실패 1 · 테스트 입력과 HOLDOUT 겹침 2(기대값 문자열 포함 표시: ['오늘은 괜찮아요', '회전성 어지럼증이 있어요'])
- 보호 확인 G8 = PASS(기존 연구 737 파일·제품 저장소 HEAD 동일)
- 사전 고정: prereg_gates 2026-10-13T05:28:52 · policy_freeze 2026-10-13T05:40:35

## 해석 주의
- 모든 정답은 합성 템플릿 슬롯 정답. 실제 환자·실제 전사문 성능 아님. 임상 정확도 주장 없음.
- REGRESSION168 coverage 는 '첫 EXISTING 연결 시도' 비율(정답 여부 무관) — 오답을 막으면 낮아진다. HOLDOUT CONCEPT_COVERAGE 는 정답 concept 기준.
- 검색기(P5) 단계 모호성('토했'의 구토/토혈 충돌, '목이 아프고' 미연결 등)은 이번 범위(P5 수정 금지) 밖 — 남은 오류의 주 원인.
