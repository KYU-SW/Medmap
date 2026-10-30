# STEP23 — Korean Symptom Expression Expansion + Linear Re-test

- STEP23_RESULT = **LINEAR_IMPROVED_BUT_INSUFFICIENT** · DATA_EXPANSION_EFFECT = **STRONG** · LIMITATION_CASE = **DATA_BOTTLENECK_DOMINANT** · gate(FULL77 core) = **CONDITIONAL**
- BEST_MODEL = **LINEAR_CHAR**(EXPANDED dev 선택) · GPU_USED = NO · NEW_BLIND_HOLDOUT_REQUIRED = **YES**
- 평가셋 = FIXED_REGRESSION_TEST(STEP21/22 test, 이미 여러 번 결과를 봄 → 개발 방향용, 최종 성능 아님). engineering benchmark, 임상 주장 아님.
- 학습 표현 출처: 기존 MedMap 사전 + 격리 `claude -p` 작성(synthetic_paraphrase, 실제 환자 문장 아님). 격리 검사 = **PASS**.

## 1. 데이터 (학습 전 통계)

| 항목 | 값 |
|---|---|
| unique training expressions ORIGINAL → EXPANDED | 276 → 1119 |
| TARGET_20 / CONFUSER_57 (EXPANDED) | 935 / 184 |
| 생성 / VALID 채택 | 1000 / 843 |
| TARGET_20 class 당 min/median/max (ORIGINAL) | 2/5.0/8 |
| TARGET_20 class 당 min/median/max (EXPANDED) | 33/47.5/55 |
| CONFUSER_57 class 당 min/median/max | 2/3/5 |
| 77 class imbalance (max/min) ORIGINAL → EXPANDED | 4.0 → 27.5 |
| 생성 중 test 완전일치(제거 전) | 17 |
| 생성 중 test near-dup ≥0.80(제거 전) | 38 |
| 최종 학습 ↔ test 완전일치 | 0 |
| 최종 학습 ↔ test 최대 유사도 / ≥0.70 개수 | 0.7778 / 33 |

판정 집계: {"VALID": 843, "REMOVED_TEST_EXACT": 17, "REMOVED_DEV_NEAR_DUPLICATE": 29, "TOO_GENERIC": 23, "TOO_SHORT": 14, "REMOVED_TEST_NEAR_DUPLICATE": 20, "AMBIGUOUS": 42, "NEAR_DUPLICATE": 3, "NOT_SINGLE_PRESENT": 8, "CONFLICT": 1}

감사자 판정: {"VALID": 927, "TOO_GENERIC": 23, "AMBIGUOUS": 42, "NOT_SINGLE_PRESENT": 8}

## 2. ORIGINAL vs EXPANDED (FIXED_REGRESSION_TEST core 109)

| model | view | metric | original | expanded | delta |
|---|---|---|---|---|---|
| LINEAR_CHAR | FULL77 | Top-1 | 35.8% | 88.1% | +52.3%p |
| LINEAR_CHAR | FULL77 | Recall@3 | 52.3% | 95.4% | +43.1%p |
| LINEAR_CHAR | FULL77 | Recall@5 | 57.8% | 97.2% | +39.5%p |
| LINEAR_CHAR | FULL77 | Unseen Top-1 (STEP21 def, n=97) | 32.0% | 87.6% | +55.7%p |
| LINEAR_CHAR | FULL77 | Unseen Top-1 (vs condition train) | 32.6% | 88.0% | +55.4%p |
| LINEAR_CHAR | FULL77 | Macro accuracy (20 class) | 37.6% | 88.9% | +51.3%p |
| LINEAR_CHAR | FULL77 | dev core Top-1 | 54.2% | 88.1% | +33.9%p |
| LINEAR_CHAR | FULL77 | Auto-accept precision (dev-fixed) | 83.3% | 98.6% | +15.3%p |
| LINEAR_CHAR | FULL77 | Auto-accept coverage (dev-fixed) | 16.5% | 66.1% | +49.5%p |
| LINEAR_CHAR | PILOT20_RESTRICTED | Top-1 | 45.0% | 88.1% | +43.1%p |
| LINEAR_CHAR | PILOT20_RESTRICTED | Recall@3 | 62.4% | 95.4% | +33.0%p |
| LINEAR_CHAR | PILOT20_RESTRICTED | Recall@5 | 67.9% | 97.2% | +29.4%p |
| LINEAR_CHAR | PILOT20_RESTRICTED | Unseen Top-1 (STEP21 def, n=97) | 41.2% | 87.6% | +46.4%p |
| LINEAR_CHAR | PILOT20_RESTRICTED | Unseen Top-1 (vs condition train) | 41.8% | 88.0% | +46.2%p |
| LINEAR_CHAR | PILOT20_RESTRICTED | Macro accuracy (20 class) | 46.6% | 88.9% | +42.3%p |
| LINEAR_CHAR | PILOT20_RESTRICTED | dev core Top-1 | 55.9% | 88.1% | +32.2%p |
| LINEAR_WORD_CHAR | FULL77 | Top-1 | 41.3% | 89.9% | +48.6%p |
| LINEAR_WORD_CHAR | FULL77 | Recall@3 | 56.9% | 96.3% | +39.5%p |
| LINEAR_WORD_CHAR | FULL77 | Recall@5 | 65.1% | 98.2% | +33.0%p |
| LINEAR_WORD_CHAR | FULL77 | Unseen Top-1 (STEP21 def, n=97) | 36.1% | 89.7% | +53.6%p |
| LINEAR_WORD_CHAR | FULL77 | Unseen Top-1 (vs condition train) | 36.7% | 89.1% | +52.4%p |
| LINEAR_WORD_CHAR | FULL77 | Macro accuracy (20 class) | 43.1% | 90.7% | +47.7%p |
| LINEAR_WORD_CHAR | FULL77 | dev core Top-1 | 49.1% | 86.4% | +37.3%p |
| LINEAR_WORD_CHAR | FULL77 | Auto-accept precision (dev-fixed) | — | 91.0% | — |
| LINEAR_WORD_CHAR | FULL77 | Auto-accept coverage (dev-fixed) | — | 91.7% | — |
| LINEAR_WORD_CHAR | PILOT20_RESTRICTED | Top-1 | 50.5% | 89.9% | +39.5%p |
| LINEAR_WORD_CHAR | PILOT20_RESTRICTED | Recall@3 | 67.9% | 97.2% | +29.4%p |
| LINEAR_WORD_CHAR | PILOT20_RESTRICTED | Recall@5 | 70.6% | 98.2% | +27.5%p |
| LINEAR_WORD_CHAR | PILOT20_RESTRICTED | Unseen Top-1 (STEP21 def, n=97) | 46.4% | 89.7% | +43.3%p |
| LINEAR_WORD_CHAR | PILOT20_RESTRICTED | Unseen Top-1 (vs condition train) | 46.9% | 89.1% | +42.2%p |
| LINEAR_WORD_CHAR | PILOT20_RESTRICTED | Macro accuracy (20 class) | 52.4% | 90.7% | +38.3%p |
| LINEAR_WORD_CHAR | PILOT20_RESTRICTED | dev core Top-1 | 52.5% | 86.4% | +33.9%p |

FULL77 = 77 class 전체 순위(판정 기준) · PILOT20_RESTRICTED = 같은 점수에서 TARGET_20 만 남긴 순위(참고). Unseen(STEP21 def) = 원 사전 기준 새 표현 97문장(같은 subset) · Unseen(vs condition train) = 각 조건 학습 표현 stem 미포함 문장.

## 3. dev 선택

| cond | family | params | dev_top1 | dev_r3 | step22_cfg_dev_top1 | dev_auto |
|---|---|---|---|---|---|---|
| ORIGINAL | LINEAR_CHAR | {"ngram": [2, 4], "min_df": 2, "C": 4.0, "class_weight": null} | 54.2% | 59.3% | 54.2% | m≥0.728 P 100.0% cov 23.7% |
| ORIGINAL | LINEAR_WORD_CHAR | {"ngram": [2, 4], "min_df": 1, "C": 0.5, "class_weight": "balanced"} | 49.1% | 59.3% | 49.1% | 없음 |
| EXPANDED | LINEAR_CHAR | {"ngram": [2, 4], "min_df": 2, "C": 0.5, "class_weight": null} | 88.1% | 94.9% | 88.1% | m≥0.461 P 95.7% cov 79.7% |
| EXPANDED | LINEAR_WORD_CHAR | {"ngram": [2, 4], "min_df": 1, "C": 0.5, "class_weight": null} | 86.4% | 93.2% | 86.4% | m≥0.261 P 96.2% cov 88.1% |

## 4. auto-accept (decision margin, 확률 아님)

| model | condition | rule | margin_threshold | n_accepted | AUTO_ACCEPT_COVERAGE | AUTO_ACCEPT_PRECISION |
|---|---|---|---|---|---|---|
| LINEAR_CHAR | ORIGINAL | dev_fixed_threshold | 0.728264 | 18 | 0.1651 | 0.8333 |
| LINEAR_CHAR | ORIGINAL | top_10pct_margin(descriptive) | 0.955787 | 11 | 0.1009 | 0.9091 |
| LINEAR_CHAR | ORIGINAL | top_20pct_margin(descriptive) | 0.577064 | 22 | 0.2018 | 0.8182 |
| LINEAR_CHAR | ORIGINAL | top_30pct_margin(descriptive) | 0.419437 | 33 | 0.3028 | 0.6667 |
| LINEAR_CHAR | ORIGINAL | top_50pct_margin(descriptive) | 0.190973 | 54 | 0.4954 | 0.537 |
| LINEAR_CHAR | ORIGINAL | top_100pct_margin(descriptive) | 0.004563 | 109 | 1.0 | 0.3578 |
| LINEAR_WORD_CHAR | ORIGINAL | dev_fixed_threshold | NONE(dev 에 P≥0.95 구간 없음) |  |  |  |
| LINEAR_WORD_CHAR | ORIGINAL | top_10pct_margin(descriptive) | 0.682128 | 11 | 0.1009 | 1.0 |
| LINEAR_WORD_CHAR | ORIGINAL | top_20pct_margin(descriptive) | 0.415306 | 22 | 0.2018 | 0.8636 |
| LINEAR_WORD_CHAR | ORIGINAL | top_30pct_margin(descriptive) | 0.333074 | 33 | 0.3028 | 0.6364 |
| LINEAR_WORD_CHAR | ORIGINAL | top_50pct_margin(descriptive) | 0.194928 | 54 | 0.4954 | 0.5741 |
| LINEAR_WORD_CHAR | ORIGINAL | top_100pct_margin(descriptive) | 0.001626 | 109 | 1.0 | 0.4128 |
| LINEAR_CHAR | EXPANDED | dev_fixed_threshold | 0.461233 | 72 | 0.6606 | 0.9861 |
| LINEAR_CHAR | EXPANDED | top_10pct_margin(descriptive) | 1.79081 | 11 | 0.1009 | 1.0 |
| LINEAR_CHAR | EXPANDED | top_20pct_margin(descriptive) | 1.52174 | 22 | 0.2018 | 1.0 |
| LINEAR_CHAR | EXPANDED | top_30pct_margin(descriptive) | 1.350532 | 33 | 0.3028 | 1.0 |
| LINEAR_CHAR | EXPANDED | top_50pct_margin(descriptive) | 0.84669 | 54 | 0.4954 | 1.0 |
| LINEAR_CHAR | EXPANDED | top_100pct_margin(descriptive) | 0.009357 | 109 | 1.0 | 0.8807 |
| LINEAR_WORD_CHAR | EXPANDED | dev_fixed_threshold | 0.261366 | 100 | 0.9174 | 0.91 |
| LINEAR_WORD_CHAR | EXPANDED | top_10pct_margin(descriptive) | 1.771925 | 11 | 0.1009 | 1.0 |
| LINEAR_WORD_CHAR | EXPANDED | top_20pct_margin(descriptive) | 1.545438 | 22 | 0.2018 | 1.0 |
| LINEAR_WORD_CHAR | EXPANDED | top_30pct_margin(descriptive) | 1.376945 | 33 | 0.3028 | 1.0 |
| LINEAR_WORD_CHAR | EXPANDED | top_50pct_margin(descriptive) | 0.95612 | 54 | 0.4954 | 1.0 |
| LINEAR_WORD_CHAR | EXPANDED | top_100pct_margin(descriptive) | 0.033618 | 109 | 1.0 | 0.8991 |

## 5. class 별 (LINEAR_CHAR, FULL77 core)

| concept | test_n | old_train_n | new_train_n | old_top1 | new_top1 | delta |
|---|---|---|---|---|---|---|
| chills | 5 | 5 | 46 | 0.0% | 100.0% | +100.0%p |
| fever | 6 | 2 | 44 | 0.0% | 83.3% | +83.3%p |
| dizziness | 6 | 3 | 47 | 16.7% | 100.0% | +83.3%p |
| diarrhea | 5 | 5 | 50 | 0.0% | 80.0% | +80.0%p |
| sore_throat | 5 | 2 | 49 | 20.0% | 100.0% | +80.0%p |
| pain | 9 | 5 | 45 | 11.1% | 77.8% | +66.7%p |
| nausea | 6 | 4 | 44 | 33.3% | 100.0% | +66.7%p |
| fatigue | 6 | 6 | 49 | 0.0% | 66.7% | +66.7%p |
| loc | 6 | 3 | 45 | 16.7% | 83.3% | +66.7%p |
| heartburn | 5 | 5 | 48 | 40.0% | 100.0% | +60.0%p |
| decreased_appetite | 5 | 8 | 53 | 40.0% | 100.0% | +60.0%p |
| hemoptysis | 2 | 2 | 43 | 50.0% | 100.0% | +50.0%p |
| vomiting | 5 | 6 | 50 | 40.0% | 80.0% | +40.0%p |
| swelling | 5 | 2 | 44 | 40.0% | 80.0% | +40.0%p |
| limb_weakness | 5 | 8 | 48 | 80.0% | 100.0% | +20.0%p |
| confusion | 5 | 3 | 43 | 40.0% | 60.0% | +20.0%p |
| cough | 6 | 7 | 55 | 66.7% | 83.3% | +16.7%p |
| palpitations | 6 | 5 | 49 | 66.7% | 83.3% | +16.7%p |
| dyspnea | 10 | 8 | 50 | 90.0% | 100.0% | +10.0%p |
| hematemesis | 1 | 3 | 33 | 100.0% | 100.0% | +0.0%p |

## 6. learning curve (CONFUSER_57 고정, seed 42/43/44 평균)

| model | k_cap_per_target_class | mean_examples_per_target_class | n_seeds | dev_core_top1_mean | dev_core_top1_std | regression_core(descriptive)_top1_mean | regression_core(descriptive)_top1_std |
|---|---|---|---|---|---|---|---|
| LINEAR_CHAR | 5 | 5.0 | 3 | 0.4746 | 0.0138 | 0.471 | 0.0822 |
| LINEAR_CHAR | 10 | 10.0 | 3 | 0.6271 | 0.0277 | 0.6024 | 0.0087 |
| LINEAR_CHAR | 20 | 20.0 | 3 | 0.7853 | 0.016 | 0.7584 | 0.0338 |
| LINEAR_CHAR | 30 | 30.0 | 3 | 0.8136 | 0.0239 | 0.841 | 0.0189 |
| LINEAR_CHAR | 40 | 39.65 | 3 | 0.8644 | 0.0 | 0.8685 | 0.0216 |
| LINEAR_CHAR | ALL | 46.75 | 3 | 0.8814 | 0.0 | 0.8807 | 0.0 |
| LINEAR_WORD_CHAR | 5 | 5.0 | 3 | 0.5537 | 0.0288 | 0.5321 | 0.0075 |
| LINEAR_WORD_CHAR | 10 | 10.0 | 3 | 0.6836 | 0.0212 | 0.6361 | 0.0156 |
| LINEAR_WORD_CHAR | 20 | 20.0 | 3 | 0.774 | 0.0211 | 0.7829 | 0.0338 |
| LINEAR_WORD_CHAR | 30 | 30.0 | 3 | 0.8249 | 0.008 | 0.8379 | 0.0303 |
| LINEAR_WORD_CHAR | 40 | 39.65 | 3 | 0.8475 | 0.0239 | 0.8807 | 0.0075 |
| LINEAR_WORD_CHAR | ALL | 46.75 | 3 | 0.8644 | 0.0 | 0.8991 | 0.0 |

## 7. 남은 오류 분류 (LINEAR_CHAR EXPANDED, core 13건)

| category | n |
|---|---|
| semantic similarity failure | 6 |
| unseen synonym | 3 |
| body-site confusion | 2 |
| linear representation limitation | 1 |
| nausea/vomiting confusion | 1 |

규칙 순서: nausea/vomiting → fatigue/weakness → body-site → confuser dominance(EV:*) → insufficient training(<30) → semantic similarity failure(정답 top3) → unseen synonym → linear representation limitation. generic·morphological 은 자동 분류하지 않음.

## 8. 참고: STEP21 baseline (같은 core subset)

| system | top1 | r3 |
|---|---|---|
| DICTIONARY | 10.1% | 11.0% |
| FUZZY | 33.0% | 48.6% |
| DICTIONARY+FUZZY | 36.7% | 50.5% |
| PRODUCT_MAPPER | 27.5% | 28.4% |

## 8-1. 오염 민감도(해석용, 판정·선택 미사용)

core test 문장을 '같은 concept 생성 학습 표현과의 최대 유사도'로 나눈 Top-1:

| max_ratio_to_same_concept_generated | n | LINEAR_CHAR / ORIGINAL | LINEAR_WORD_CHAR / ORIGINAL | LINEAR_CHAR / EXPANDED | LINEAR_WORD_CHAR / EXPANDED |
|---|---|---|---|---|---|
| [0.00,0.50) | 23 | 26.1% | 34.8% | 60.9% | 69.6% |
| [0.50,0.60) | 29 | 44.8% | 44.8% | 93.1% | 89.7% |
| [0.60,0.70) | 31 | 35.5% | 48.4% | 96.8% | 96.8% |
| [0.70,1.00) | 26 | 34.6% | 34.6% | 96.2% | 100.0% |

생성 표현을 dev·test 와 유사도 T 이상이면 추가 제거 후 같은 하이퍼파라미터로 재학습:

| filter | gen_kept | gen_per_class(min/med/max) | LINEAR_CHAR top1 | LINEAR_WORD_CHAR top1 | LINEAR_CHAR R@3 | LINEAR_WORD_CHAR R@3 |
|---|---|---|---|---|---|---|
| T<0.70 | 791 | 30/40/45 | 85.3% | 87.2% | 93.6% | 94.5% |
| T<0.60 | 651 | 24/33/40 | 83.5% | 84.4% | 89.9% | 91.7% |
| T<0.50 | 439 | 11/23/34 | 74.3% | 74.3% | 88.1% | 89.0% |

해석: 엄격 필터에서의 하락은 학습 표현 수 감소(learning curve)와 겹쳐 있어, 전부 오염 효과로 볼 수 없다. 반대로 생성 표현과 표면이 먼 문장(최저 구간)의 정확도가 다른 구간보다 뚜렷이 낮으면, 상승분 일부가 같은 작성 분포의 표면 유사성에서 왔다는 신호다.


## 9. 격리 검사

| session | PASS | model | tool_calls | attachments | list_price_usd_estimate |
|---|---|---|---|---|---|
| audit_a1 | True | claude-opus-5-5 | 7 | {"environment": 1, "model": 1, "total_tokens_reminder": 5, "session_context": 1, "date": 1, "credential_org": 1, "prompt_snapshot": 2, "deferred_tools_record": 2} | 1.017 |
| audit_a2 | True | claude-opus-5-5 | 6 | {"environment": 1, "model": 1, "total_tokens_reminder": 4, "session_context": 1, "date": 1, "credential_org": 1, "prompt_snapshot": 2, "deferred_tools_record": 1} | 0.994 |
| author_b1 | True | claude-opus-5-5 | 4 | {"environment": 1, "model": 1, "total_tokens_reminder": 4, "session_context": 1, "date": 1, "credential_org": 1, "prompt_snapshot": 2} | 0.492 |
| author_b2 | True | claude-opus-5-5 | 4 | {"environment": 1, "model": 1, "total_tokens_reminder": 4, "session_context": 1, "date": 1, "credential_org": 1, "prompt_snapshot": 2} | 0.424 |
| author_b3 | True | claude-opus-5-5 | 4 | {"environment": 1, "model": 1, "total_tokens_reminder": 4, "session_context": 1, "date": 1, "credential_org": 1, "prompt_snapshot": 2} | 0.475 |
| author_b4 | True | claude-opus-5-5 | 4 | {"environment": 1, "model": 1, "total_tokens_reminder": 4, "session_context": 1, "date": 1, "credential_org": 1, "prompt_snapshot": 2} | 0.617 |

list_price 는 정가 환산 추정이며 실제 청구액이 아니다.

## 10. 한계

- FIXED_REGRESSION_TEST 는 blind 가 아니다. STEP21 test 와 STEP23 학습 표현 모두 Claude 계열이 작성 → 같은 분포 효과로 성능이 과대평가될 수 있다(완전일치·≥0.80 근접만 제거).
- dev 59 문장으로 선택 → 선택 분산 큼. 실제 환자 발화 0. 최종 모델 결정 전 새 blind holdout(가능하면 사람 작성·실제 발화) 필요.
- production 미연결. UMLS/SNOMED 원문 미복사.
