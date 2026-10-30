# STEP28.8 — Korean Retrieval Repair & Evaluation Gate

- **STEP29 진입: CONDITIONAL_GO** · STEP28_8_RESULT = **PARTIAL_IMPROVEMENT** · PRODUCTION_READY = NO · HUMAN_VERIFIED_GOLD = 0
- 게이트(P5): {"G1": "PASS", "G2": "PASS", "G3": "PASS", "G3b": "PASS", "G4": "FAIL", "G5": "PASS", "G6": "PASS", "G7": "PASS", "G8": "PASS", "G9": "PASS", "G10": "PASS"} · G6_STRICT(≥0.95) = FAIL · HELD_PRECEDENCE = PASS
- P2(STEP28.7 D 재실행) 대비 개선: {"precision": true, "weaknon": false, "substring": true, "violations": true}
- 규칙 고정: 검사기 `scripts/evaluator.py`(v3, SHA `03d6f68c5db7b4a2…`) · 매칭 `scripts/repair_korean_matching.py` · 정책 `scripts/policies.py` · 게이트 `scripts/build_report.py` — 모두 평가 실행 전.
- 데이터 대부분이 반복 노출된 개발·회귀 자료. 덜 노출된 보조 Gold = PILOT_EXTRA106(합성·Claude 작성). 사람 검증 임상 Gold 없음.

## 1. 최종 보고

| 항목 | 값 |
|---|---|
| STEP28_8_RESULT | PARTIAL_IMPROVEMENT |
| EVALUATOR_FIXED | PASS |
| SUBSTRING_FALSE_MATCH | 39(P0 130 · P2 91, 전 세트 auto 구문) |
| WEAK_NEGATIVE_AUTO_MAP | 10/903(P2 8/903 · P0 47/903) |
| SUPPORTED_AUTO_PRECISION | 0.9451(REGRESSION168 첫 auto; P2 0.8788 · STEP27 B4 0.9859) |
| SUPPORTED_AUTO_COVERAGE | 0.5417(P2 0.5893 · STEP27 B4 0.4226) |
| SEMANTIC_DISTINCTION_VIOLATIONS | 0(v3, 전 세트; P2 1) |
| WRONG_CANDIDATE_DISPLAY | 0 |
| HELD_PRECEDENCE | PASS(보류 원문 입력 auto P5 0/20 · P2 3) |
| RAW_PRESERVATION | 1.0 |
| CPU_P95 | 14.953 ms(p50 10.903 ms, n 442) · peak RSS 1349.2 MiB |
| STEP29_READINESS | CONDITIONAL_GO |
| PRODUCTION_READY | NO |

## 2. 검사기(§2)

- 정답 쌍 2806 개(파일럿 Gold 274·STEP23 학습·STEP21 사전·T20/C57)에 대한 정답 오판: v1(STEP28.7 공식) 33 · v2 8 · **v3 0**.
- 필수 사례: 위반 탐지 누락 0 · 정상 사례 오판 0. 단위 테스트: test_evaluator_correctness 3/3 · test_held_precedence 4/4 · test_semantic_distinctions 2/2 · test_substring_false_matches 2/2 · test_supported_symptoms 2/2.
- v3 은 정답 대조로 정했다(양태 '…할 것 같다·…싶다' 예외, 구토감·헛구역 예외, 오바이트 구토 단서). 같은 정답 세트로 검증했으므로 검사기 일반화 보장은 아님.

## 3. 정책 비교(§8) — 단위: 입력(R·X·W·V·HELD), 구문(EXISTING·UNKNOWN 등, SILVER442)

| 지표 | P0 | P1 | P2 | P3 | P4 | P5 | REF_A |
|---|---|---|---|---|---|---|---|
| R1_regression_coverage | 0.5833 | 0.5893 | 0.5893 | 0.5417 | 0.5417 | 0.5417 | 0.4226 |
| R2_regression_precision(first_auto) | 0.8776 | 0.8788 | 0.8788 | 0.9451 | 0.9451 | 0.9451 | 0.9859 |
| R2_n_correct | 86 | 87 | 87 | 86 | 86 | 86 | 70 |
| R1_n_auto | 98 | 99 | 99 | 91 | 91 | 91 | 71 |
| R3_regression_span_precision | 0.8738 | 0.875 | 0.875 | 0.9462 | 0.9462 | 0.9462 | 0.9859 |
| X1_extra_span_precision | 0.9143 | 0.9028 | 0.9028 | 0.9067 | 0.9067 | 0.9067 | 1.0 |
| X2_extra_primary_coverage | 0.5513 | 0.5513 | 0.5513 | 0.5641 | 0.5641 | 0.5641 | 0.0385 |
| X3_should_not_link_auto | 7 | 7 | 7 | 7 | 7 | 7 | 0 |
| W1_weaknon_auto_link | 47 | 13 | 8 | 10 | 10 | 10 | — |
| V1_semantic_violation_inputs | 9 | 1 | 1 | 0 | 0 | 0 | 0 |
| V2_wrong_candidate_display_inputs | 9 | 1 | 1 | 0 | 0 | 0 | 0 |
| SFM_substring_false_match_spans | 130 | 89 | 91 | 39 | 39 | 39 | 0 |
| SUP_supported12 | 9 | 12 | 11 | 12 | 12 | 12 | — |
| HELD_auto_inputs | 3 | 0 | 3 | 3 | 0 | 0 | — |
| EXISTING_CANONICAL | 127 | 148 | 154 | 141 | 139 | 139 | — |
| EXISTING_COMPOSITE | 29 | 40 | 40 | 34 | 34 | 34 | — |
| EXISTING_SUBTYPE | 0 | 0 | 6 | 6 | 6 | 6 | — |
| NEWU_units | 0 | 45 | 21 | 32 | 32 | 32 | — |
| NEWU_distinct_ids | 0 | 25 | 13 | 16 | 16 | 16 | — |
| UNKNOWN | 78 | 10 | 9 | 23 | 23 | 23 | — |
| UNCERTAIN | 180 | 112 | 125 | 116 | 118 | 118 | — |
| NON | 29 | 88 | 88 | 91 | 91 | 91 | — |
| U_unknown_uncertain_rate | 0.5824 | 0.2754 | 0.3025 | 0.3138 | 0.3183 | 0.3183 | — |
| RAW_preservation | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |

- REGRESSION168 = 합성 Gold(노출) · PILOT_EXTRA106 = 합성 Gold(덜 노출, X1–X3) · WEAKNON903·SILVER442 = 약한 라벨 — 하나의 정확도로 합치지 않음.
- REF_A = STEP27 POLICY_D(B4) 참고값(REGRESSION168·PILOT_EXTRA106 만 실행).

## 4. 오류 분석(§4·§6)

- 비증상 위험 원인: {"P0": {"SUBSTRING": 27, "BODY_PART_ONLY": 9, "OTHER": 9, "MODEL_B4": 1, "SYMPTOM_TERM_WEAK_LABEL_CONFLICT": 1}, "P2": {"MODEL_B4": 1, "SUBSTRING": 5, "SYMPTOM_TERM_WEAK_LABEL_CONFLICT": 1, "OTHER": 1}, "P5": {"SYMPTOM_TERM_WEAK_LABEL_CONFLICT": 7, "MODEL_B4": 1, "SUBSTRING": 1, "OTHER": 1}}
- P5 비증상 위험 입력: 흉통을→pain(SYMPTOM_TERM_WEAK_LABEL_CONFLICT); 흉통이→pain(SYMPTOM_TERM_WEAK_LABEL_CONFLICT); 흉통이라고→pain(SYMPTOM_TERM_WEAK_LABEL_CONFLICT); 흉통의→pain(SYMPTOM_TERM_WEAK_LABEL_CONFLICT); 양쪽 팔을들어→limb_weakness(MODEL_B4); 흉통이란→pain(SYMPTOM_TERM_WEAK_LABEL_CONFLICT); 심계항진이라고→palpitations(SUBSTRING); 흉통과→pain(SYMPTOM_TERM_WEAK_LABEL_CONFLICT); 만성기침과→cough(SYMPTOM_TERM_WEAK_LABEL_CONFLICT); 심장 부분→palpitations(OTHER)
- 오류 종류(P2 → P5): {"P2": {"SUBSTRING_FALSE_MATCH": 83, "REGRESSION_NOT_AUTO": 69, "REGRESSION_WRONG_FIRST_AUTO": 12}, "P5": {"SUBSTRING_FALSE_MATCH": 37, "REGRESSION_NOT_AUTO": 77, "REGRESSION_WRONG_FIRST_AUTO": 5}}
- P5 REGRESSION168 오답(첫 auto): 정신이 아찔해요(gold dizziness→confusion); 속이 쓰려요(gold heartburn→pain); 숨 쉴 때마다 옆구리가 찌르듯이 아파요(gold pain→dyspnea;); 누런 가래가 나오는 기침을 해요(gold cough→EV:E_182); 속이 화끈화끈해요(gold heartburn→nausea)
- P2 오답 중 P5 에서 사라진 것: 깨어 보니까 바닥에 누워 있었어요, 목이 간질간질하면서 기침이 나요, 목이 붓고 쓰라려요, 어제 밤부터 왼쪽 가슴이 쥐어짜듯 아파요, 오바이트했어요, 정신이 없고 말이 엉켜요, 헛구역질만 계속 나요

## 5. 답(§14)

1. 검사기: PASS — 정답 오판 v1 33 → v3 0.
2. 부분 문자열 오매핑(auto 구문): P0 130 · P2 91 → P5 39.
3. 기존 증상 자동 처리(REGRESSION168): precision P2 0.8788 → P5 0.9451(0.95 FAIL) · coverage P2 0.5893 → P5 0.5417 · 덜 노출 PILOT_EXTRA106 span precision P2 0.9028 → P5 0.9067, primary coverage 0.5513 → 0.5641 · SUPPORTED12 P2 11/12 → P5 12/12.
4. 비증상 자동 연결(WEAKNON903): P0 47 · P2 8 → P5 10(약한 라벨 — 일부는 실제 증상어, §4).
5. 보류 우선: PASS — 보류 원문 입력 auto P2 3 → P5 0(무기력·묽은변 포함, 부정 구문은 차단 대신 확인 경로).
6. 구별(코피≠객혈·토혈 · 구토≠오심 · 떨림≠오한): P5 위반 0 · 표시 후보 위반 0(probe 결과 `outputs/error_analysis.csv`).
7. 신규 SILVER 개념의 모델 입력: P5 신규·하위 usable 0 · SILVER 단독 usable 0.
8. 남은 대표 오류: §4.
9. STEP29: **CONDITIONAL_GO**.

## 6. 사후 발견·탐색(EXPLORATORY_POST_HOC — 공식 판정 아님, 1차 평가 결과를 본 뒤 작성)

- 남은 부분 문자열 오매칭 39 은 대부분 STEP28.5 술어 정규화 키(nkey) 일치: 의성어·부사·위치 명사를 버려 다른 의미를 같은 키로 만든다('속이 화끈화끈해요'(gold heartburn) ↔ '속이 울렁울렁해요'(nausea), '가슴이 벌렁벌렁해요' ↔ '가슴이 콩닥콩닥해요'). 경계 일치에서도 부사가 빠져 '심장이 덜컥거립니다' → [심장] 만 남아 '심장 부분' → palpitations.
- P5x(nkey 는 경계 정렬될 때만 + 핵심 형태소 50% 미만 항목 제외, 모델 재실행): precision 0.9451 → 0.908 · coverage 0.5417 → 0.5179 · 비증상 10 → 8 · SUPPORTED12 12 → 11 · PILOT_EXTRA106 span precision 0.9067 → 0.9024. → nkey 를 빼면 B4·다른 경로가 대신 잡아 오답이 늘어남(예 [['정신이 아찔해요', 'dizziness', 'confusion'], ['기침하면 피가 같이 나와요', 'hemoptysis', 'cough'], ['속이 쓰려요', 'heartburn', 'pain']]). 채택 안 함.
- 검사기 v3 의 빈틈: '토할 것 같아요' → vomiting(정답 nausea)은 양태 예외 때문에 위반으로 잡히지 않는다(P5x 에서 발생). 다음 검사기 버전에서 사전 보완 필요.
- G4 FAIL(P5 10 > P2 8)의 주원인: '흉 통' 분리 문제를 고쳐 흉통 6 이 다시 pain 으로 연결됨 — 두 LLM 작성자 모두 증상형으로 쓴 실제 증상어(약한 비증상 라벨 쪽 의심). 규칙상 FAIL 유지.

## 7. 변경 기록(공개)

- 검사기 v3 은 정답 세트 대조 중 2회 수정(양태 '싶' 추가 포함) 후 정책 평가 전에 SHA 고정. 매칭·정책·게이트 규칙은 평가 후 변경 없음.
- 평가 후 추가: `scripts/evaluate_exploratory_p5x.py`(탐색, 공식 아님) · 보고서 사후 절. 테스트 파일은 평가와 같은 실행에서 처음 실행.
