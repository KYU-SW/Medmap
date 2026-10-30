# STEP22 — Korean Symptom Normalizer v1 (TF-IDF + LinearSVC)

- LINEAR_NORMALIZER = **NO_GO** · 판정 = **C. LINEAR_MODEL_FAILED** · BEST_MODEL = **LINEAR_CHAR** (dev 선택, view CURATED) · GPU_USED = NO
- engineering benchmark(임상 정확도 기준 아님). 평가 문장은 STEP21 Claude 작성 합성 문장(실제 환자 발화 아님).
- 학습 = 기존 MedMap 사전 표현만(새 합성 학습 데이터 0). sealed test 는 학습·선택·임계값에 미사용, 1회 평가.

## 1. 핵심 수치 (NORMALIZER_CORE sealed test)

| 항목 | 값 |
|---|---|
| classes (train / 평가 pilot) | 77 / 20 |
| train expressions (CURATED / RAW) | 276 / 294 |
| core dev / core sealed test | 59 / 109 |
| Top-1 | 35.8% |
| Recall@3 | 52.3% |
| Recall@5 | 57.8% |
| unseen-expression Top-1 (n=97) | 32.0% |
| auto-accept (dev 고정 margin) precision / coverage | 83.3% / 16.5% (n=18) |
| 참고: test 사후 최대 coverage @P≥95% (gate 미사용) | 9.2% (P 100.0%, n=10) |
| old same-subset 최고 Top-1 | DICTIONARY+FUZZY 36.7% |
| Δ Top-1 (new − old) | -0.9%p |
| Δ unseen Top-1 (vs FUZZY) | +2.1%p |

gate 규칙: NO_GO if Top-1<0.70 or R@3<0.85; GO if Top-1>=0.90 & R@3>=0.97 & unseen>=0.85 & dev-fixed auto-accept P>=0.95 with coverage>=0.30; else CONDITIONAL

판정 규칙: A if GO; B if core Top-1 and unseen Top-1 both >= +0.10 vs best old baseline (same subset); else C

## 2. SAME_SUBSET_COMPARISON (core test, 같은 분모)

STEP21 baseline 은 STEP21 예측 파일을 그대로 재채점(재채점기는 STEP21 tier_AB 수치와 일치함을 assert). `ref_tier_AB_top1` = STEP21 분모(test Tier A+B should_link 115, 복수 증상 포함) 참고값.

| system | n | top1 | recall_at_3 | recall_at_5 | unseen_n | unseen_top1 | seen_n | seen_top1 | core_dev_top1 | ref_tier_AB_top1 |
|---|---|---|---|---|---|---|---|---|---|---|
| DICTIONARY | 109 | 10.1% | 11.0% | 11.0% | 97 | 0.0% | 12 | 91.7% | 20.3% | 11.3% |
| FUZZY | 109 | 33.0% | 48.6% | 54.1% | 97 | 29.9% | 12 | 58.3% | 37.3% | 33.9% |
| DICTIONARY+FUZZY | 109 | 36.7% | 50.5% | 56.0% | 97 | 29.9% | 12 | 91.7% | 39.0% | 37.4% |
| PRODUCT_MAPPER | 109 | 27.5% | 28.4% | 28.4% | 97 | 22.7% | 12 | 66.7% | 30.5% | 27.8% |
| LINEAR_WORD[CURATED] | 109 | 35.8% | 45.0% | 53.2% | 97 | 29.9% | 12 | 83.3% | 28.8% | 35.6% |
| LINEAR_CHAR[CURATED] | 109 | 35.8% | 52.3% | 57.8% | 97 | 32.0% | 12 | 66.7% | 54.2% | 36.5% |
| LINEAR_WORD_CHAR[CURATED] | 109 | 41.3% | 56.9% | 65.1% | 97 | 36.1% | 12 | 83.3% | 49.1% | 40.9% |
| LINEAR_WORD[RAW] | 109 | 33.9% | 48.6% | 50.5% | 97 | 27.8% | 12 | 83.3% | 27.1% | 33.9% |
| LINEAR_CHAR[RAW] | 109 | 33.9% | 52.3% | 58.7% | 97 | 29.9% | 12 | 66.7% | 54.2% | 34.8% |
| LINEAR_WORD_CHAR[RAW] | 109 | 42.2% | 57.8% | 64.2% | 97 | 37.1% | 12 | 83.3% | 49.1% | 41.7% |

## 3. dev 선택 결과 (test 이전 고정)

| view | family | params | dev_top1 | dev_r3 | grid | dev_auto |
|---|---|---|---|---|---|---|
| CURATED | LINEAR_WORD | {"C": 0.25, "class_weight": null, "min_df": 1} | 28.8% | 39.0% | 10 | 없음 |
| CURATED | LINEAR_CHAR | {"ngram": [2, 4], "min_df": 2, "C": 4.0, "class_weight": null} | 54.2% | 59.3% | 80 | margin≥0.728 P 100.0% cov 23.7% |
| CURATED | LINEAR_WORD_CHAR | {"ngram": [2, 4], "min_df": 1, "C": 0.5, "class_weight": "balanced"} | 49.1% | 59.3% | 80 | 없음 |
| RAW | LINEAR_WORD | {"C": 2.0, "class_weight": null, "min_df": 1} | 27.1% | 37.3% | 10 | 없음 |
| RAW | LINEAR_CHAR | {"ngram": [2, 5], "min_df": 2, "C": 2.0, "class_weight": "balanced"} | 54.2% | 59.3% | 80 | margin≥0.734 P 100.0% cov 20.3% |
| RAW | LINEAR_WORD_CHAR | {"ngram": [2, 4], "min_df": 1, "C": 1.0, "class_weight": null} | 49.1% | 59.3% | 80 | margin≥0.859 P 100.0% cov 13.6% |

선택 규칙: dev core Top-1 > Recall@3 > Recall@5 > grid order · BEST_MODEL 규칙: PRIMARY_VIEW(CURATED) dev core Top-1 > Recall@3 > simpler family

## 4. Auto-accept (decision margin = top1 − top2 score, 확률 아님)

| rule | margin_threshold | n_accepted | AUTO_ACCEPT_COVERAGE | AUTO_ACCEPT_PRECISION |
|---|---|---|---|---|
| dev_fixed_threshold(gate) | 0.728264 | 18 | 0.1651 | 0.8333 |
| top_10pct_margin(descriptive, test-ranked) | 0.955787 | 11 | 0.1009 | 0.9091 |
| top_20pct_margin(descriptive, test-ranked) | 0.577064 | 22 | 0.2018 | 0.8182 |
| top_30pct_margin(descriptive, test-ranked) | 0.419437 | 33 | 0.3028 | 0.6667 |
| top_40pct_margin(descriptive, test-ranked) | 0.279331 | 44 | 0.4037 | 0.5682 |
| top_50pct_margin(descriptive, test-ranked) | 0.190973 | 54 | 0.4954 | 0.537 |
| top_60pct_margin(descriptive, test-ranked) | 0.141832 | 65 | 0.5963 | 0.4615 |
| top_70pct_margin(descriptive, test-ranked) | 0.098529 | 76 | 0.6972 | 0.4211 |
| top_80pct_margin(descriptive, test-ranked) | 0.063013 | 87 | 0.7982 | 0.4138 |
| top_90pct_margin(descriptive, test-ranked) | 0.034827 | 98 | 0.8991 | 0.3776 |
| top_100pct_margin(descriptive, test-ranked) | 0.004563 | 109 | 1.0 | 0.3578 |

## 5. class 별 (core test, BEST_MODEL)

| class | train_n | test_n | top1 | r3 |
|---|---|---|---|---|
| hematemesis | 3 | 1 | 100.0% | 100.0% |
| dyspnea | 8 | 10 | 90.0% | 90.0% |
| limb_weakness | 8 | 5 | 80.0% | 100.0% |
| cough | 7 | 6 | 66.7% | 66.7% |
| palpitations | 5 | 6 | 66.7% | 83.3% |
| hemoptysis | 2 | 2 | 50.0% | 50.0% |
| confusion | 3 | 5 | 40.0% | 60.0% |
| decreased_appetite | 8 | 5 | 40.0% | 40.0% |
| heartburn | 5 | 5 | 40.0% | 80.0% |
| swelling | 2 | 5 | 40.0% | 80.0% |
| vomiting | 6 | 5 | 40.0% | 60.0% |
| nausea | 4 | 6 | 33.3% | 33.3% |
| sore_throat | 2 | 5 | 20.0% | 20.0% |
| dizziness | 3 | 6 | 16.7% | 50.0% |
| loc | 3 | 6 | 16.7% | 33.3% |
| pain | 5 | 9 | 11.1% | 11.1% |
| chills | 5 | 5 | 0.0% | 60.0% |
| diarrhea | 5 | 5 | 0.0% | 0.0% |
| fatigue | 6 | 6 | 0.0% | 33.3% |
| fever | 2 | 6 | 0.0% | 33.3% |

## 6. train expression 수 구간별 (core test)

| bin | classes | n | top1 | r3 |
|---|---|---|---|---|
| 1-5 | 14 | 72 | 25.0% | 44.4% |
| 6-10 | 6 | 37 | 56.8% | 67.6% |
| 11-20 | 0 | 0 | — | — |
| 21+ | 0 | 0 | — | — |

학습 표현 재대입 Top-1 = 100.0% (모델이 학습 표현은 전부 맞힘). train ≤ 3 표현 class: confusion, dizziness, fever, hematemesis, hemoptysis, loc, sore_throat, swelling.

## 7. Top confusion pairs (BEST_MODEL)

core test 오류 70/109, 그중 pilot 밖 class(EV:*)로 간 것 29. `why` = 예측 class 쪽으로 점수를 민 상위 char n-gram.

| scope | concept_a | concept_b | count | a_to_b | b_to_a | example_text | example_gold | example_pred | why_top_features_toward_pred |
|---|---|---|---|---|---|---|---|---|---|
| core_test | pain | sore_throat | 5 | 5 | 0 | 머리가 아파요 | pain | sore_throat | ' 아' | '리가' | '리가 ' | '머리' | '머리가 ' |
| core_test | pain | palpitations | 3 | 1 | 2 | 가슴 한가운데가 묵직하게 눌리는 느낌이에요 | pain | palpitations | '슴 ' | '가슴 ' | '하게 ' | '하게' | '는 느' |
| core_test | chills | swelling | 2 | 2 | 0 | 몸이 덜덜 떨려요 | chills | swelling | '몸이 ' | '몸이' | '이 ' |
| core_test | dyspnea | sore_throat | 2 | 0 | 2 | 목이 칼칼해요 | sore_throat | dyspnea | '이 ' |
| core_test | EV:E_111 | confusion | 1 | 0 | 1 | 넋이 나간 것 같아요 | confusion | EV:E_111 | ' 것 ' | ' 것 같' | '것 ' | '것 같' | ' 같' |
| core_test | EV:E_111 | hemoptysis | 1 | 0 | 1 | 가래에 실핏줄 같은 게 보여요 | hemoptysis | EV:E_111 | ' 같' | '같은 ' | ' 같은 ' | ' 같은' | '같은' |
| core_test | EV:E_128 | fatigue | 1 | 0 | 1 | 요즘 너무 지쳐서 출근도 못 하겠어요 | fatigue | EV:E_128 | '도 못' | '도 ' | ' 못' | '못 ' | ' 못 ' |
| core_test | EV:E_129 | fever | 1 | 0 | 1 | 체온 재 보니까 38도 5부 나왔어요 | fever | EV:E_129 | '부 ' | ' 보' | '도 ' | ' 나' | '온 ' |
| core_test | EV:E_136 | chills | 1 | 0 | 1 | 이가 딱딱 부딪힐 정도로 떨려요 | chills | EV:E_136 | ' 정' | ' 부' | '가 ' |
| core_test | EV:E_157 | limb_weakness | 1 | 0 | 1 | 다리가 풀려서 자꾸 주저앉아요 | limb_weakness | EV:E_157 | ' 주' | '가 ' | '서 ' | '리가' | '리가 ' |
| core_test | EV:E_169 | nausea | 1 | 0 | 1 | 밥 먹고 나면 속이 니글니글해요 | nausea | EV:E_169 | ' 속' | '고 ' | '이 ' | ' 나' |
| core_test | EV:E_171 | fever | 1 | 0 | 1 | 몸에서 열감이 느껴져요 | fever | EV:E_171 | ' 느껴' | '느껴' | '에서' | '에서 ' | '서 ' |
| core_test | EV:E_172 | heartburn | 1 | 0 | 1 | 목까지 뜨거운 게 치밀어 올라요 | heartburn | EV:E_172 | ' 뜨' | '뜨거' | ' 뜨거' | ' 올' | '어 ' |
| core_test | EV:E_175 | fatigue | 1 | 0 | 1 | 기운이 하나도 없어요 | fatigue | EV:E_175 | '기운' | ' 없' | ' 없어' | '없어' | '하나' |
| core_test | EV:E_190 | fever | 1 | 0 | 1 | 열이 나여 | fever | EV:E_190 | '이 나' | ' 나' | '이 ' |

## 8. 주요 사례

| text | split | top3 | margin | old |
|---|---|---|---|---|
| 호흡이 딸려요 | test | dyspnea(-0.743) · swelling(-0.800) · decreased_appetite(-0.830) | 0.0572 | DICTIONARY=∅, FUZZY=∅, DICTIONARY+FUZZY=∅, PRODUCT_MAPPER=∅ |
| 토했어요 | dev | vomiting(-0.670) · fever(-0.806) · decreased_appetite(-0.931) | 0.1364 | DICTIONARY=∅, FUZZY=vomiting, DICTIONARY+FUZZY=vomiting, PRODUCT_MAPPER=nausea |
| 물만 마셔도 다 토해요 | test | vomiting(-0.707) · EV:E_156(-0.776) · hematemesis(-0.795) | 0.0686 | DICTIONARY=∅, FUZZY=∅, DICTIONARY+FUZZY=∅, PRODUCT_MAPPER=nausea |
| 숨이 벅차요 | test | dyspnea(+0.412) · EV:E_75(-0.554) · EV:E_23(-0.721) | 0.9655 | DICTIONARY=∅, FUZZY=dyspnea, DICTIONARY+FUZZY=dyspnea, PRODUCT_MAPPER=∅ |
| 가슴이 꽉 조이는 것 같아요 | 없음(추가 안 함) |  |  |  |

## 9. 학습 데이터 audit · RAW vs CURATED

audit 상태: {"SAFE": 267, "TOO_SHORT": 7, "AMBIGUOUS": 8, "CONFLICT": 12} · exact duplicate 0 · CURATED 제외 18건(사전 원문 의미 검토로 고정, test 미참조). UNSEEN_CLASS = 없음; train 전용 class 57개(비 pilot 증거 = 혼동 후보).

| expression | canonical_id | audit_status | exclusion_reason |
|---|---|---|---|
| 대변 | EV:E_150 | AMBIGUOUS | AMBIGUOUS:증상 아닌 명사 조각(STEP20: E_150 극성 반전 PARTIAL); TOO_SHORT |
| 방귀 배출 가능 여부 | EV:E_150 | AMBIGUOUS | AMBIGUOUS:질문 조각·극성 반전(STEP20 PARTIAL) |
| 힘 빠짐 | EV:E_156 | CONFLICT | CONFLICT:EV:E_156|EV:E_38; AMBIGUOUS:원 증거 맥락 없는 일반 조각(E_38 과 충돌) |
| 양다리 | EV:E_157 | AMBIGUOUS | AMBIGUOUS:신체 부위만 남은 조각(원 label 저림) |
| 양팔 | EV:E_157 | CONFLICT | CONFLICT:EV:E_157|limb_weakness; AMBIGUOUS:신체 부위만 남은 조각(원 label 저림); TOO_SHORT |
| 뜻하지 않은 체중 감소 | EV:E_174 | CONFLICT | CONFLICT:EV:E_162|EV:E_174 |
| 감각 저하 | EV:E_177 | CONFLICT | CONFLICT:EV:E_177|EV:E_93 |
| 누런 | EV:E_182 | AMBIGUOUS | AMBIGUOUS:색 수식어만 남은 조각(원 label 누런·초록 콧물); TOO_SHORT |
| 목 등 | EV:E_193 | AMBIGUOUS | AMBIGUOUS:신체 부위 열거 조각; TOO_SHORT |
| 얼굴 | EV:E_193 | CONFLICT | CONFLICT:EV:E_193|EV:E_83; AMBIGUOUS:신체 부위만 남은 조각(원 label 근육 경련 부위); TOO_SHORT |
| 힘 빠짐 | EV:E_38 | CONFLICT | CONFLICT:EV:E_156|EV:E_38; AMBIGUOUS:원 증거 맥락 없는 일반 조각(E_156 과 충돌) |
| 얼굴 | EV:E_83 | CONFLICT | CONFLICT:EV:E_193|EV:E_83; AMBIGUOUS:신체 부위만 남은 조각(원 label '얼굴·눈 근육 힘 빠짐'); TOO_SHORT |
| 림프절 | EV:E_9 | AMBIGUOUS | AMBIGUOUS:해부 구조명만 남은 조각 |
| 부음 | EV:E_9 | AMBIGUOUS | AMBIGUOUS:일반 증상어가 림프절 증거에 붙은 조각(swelling 과 혼동); TOO_SHORT |
| 통증 | EV:E_9 | CONFLICT | CONFLICT:EV:E_9|pain; AMBIGUOUS:일반 증상어가 림프절 증거에 붙은 조각(pain 과 충돌); TOO_SHORT |
| 감각 저하 | EV:E_93 | CONFLICT | CONFLICT:EV:E_177|EV:E_93 |
| 팔다리 | limb_weakness | AMBIGUOUS | AMBIGUOUS:신체 부위만 남은 조각(원 label 마비·힘 빠짐) |
| 양팔 | limb_weakness | CONFLICT | CONFLICT:EV:E_157|limb_weakness; AMBIGUOUS:신체 부위만 남은 조각(원 label 힘 빠짐); TOO_SHORT |

LINEAR_CHAR core test Top-1: CURATED 35.8% vs RAW 33.9% (+1.8%p).

## 10. 복수 증상 문장(정성, 핵심 점수 제외)

test 복수 증상 19문장: top3 안에 정답 증상 2개 이상 6, 1개 11, 0개 2. 한 문장 전체를 넣으면 한 증상으로 치우침 → span 추출 후 span 별 정규화가 필요.

## 11. 해석

- char vs word: core test Top-1 LINEAR_WORD 35.8% · LINEAR_CHAR 35.8% · LINEAR_WORD_CHAR 41.3%. dev 에서는 char 가 word 보다 높았으나(dev 54.2% vs 28.8%) test 에서 그 차이가 재현되지 않음. dev 59 문장 선택이 불안정(dev→test 하락).
- WORD_CHAR 가 test 에서 더 높지만 test 로 모델을 바꾸지 않는다(선택은 dev 에서 끝남). 참고 관찰로만 둔다.
- 모델 vs 데이터: 학습 표현 재대입 100.0%, class 당 학습 표현 2–10개(11개 이상 class 없음). 실패의 주원인은 학습 표현 부족·편향(질문형·정식 용어 위주, 구어 표현 없음)이며, 선형 모델 용량 문제로 보기 어렵다. 예: pain 학습 표현이 '가슴'·'통증' 위주라 '머리가 아파요'가 '목이 아픈가요'(sore_throat)의 '아' n-gram 에 끌림.
- 오류 상당수가 pilot 밖 증거 class(EV:*)로 감 → 77-class 혼동 공간에서 표현 수가 적은 class 끼리 표면 n-gram 경쟁.
- 다음 단계 제안은 최종 보고 참고(이 문서는 결과만).

## 12. 재현성 · 범위

- random_state=42, run_all.sh 2회 실행 후 outputs·models SHA256 비교(logs/sha1.txt·sha2.txt).
- production(MedMap mapper·Patient Companion·Doctor mode·PatientState) 미연결. UMLS/SNOMED 원문 미복사(내부 ID·MedMap label 만).
