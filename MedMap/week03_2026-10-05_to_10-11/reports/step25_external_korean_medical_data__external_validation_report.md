# STEP25 — 외부 데이터 검증 보고

- 판정: {"STEP25_ACCESS": "PARTIAL", "EXTERNAL_GOLD_AVAILABLE": "NO", "EXTERNAL_EVALUATION": "PARTIAL(정답 없는 분석만)", "MANUAL_SENTENCE_AUTHORING_REQUIRED": "NO(문장 작성 불필요) — 단 concept 라벨링 또는 AI-Hub 승인 없이는 정확도 검증 불가", "gold_candidate_units": 0, "evaluable_canonical_concepts_with_gold": 0}
- **정답(concept) 있는 외부 문장 0 → 정확도·Top-k·macro accuracy 계산하지 않음.** 아래는 정답 없는 분석(agreement·분포·미인식·위험 자동 수락 후보)이며 정확도가 아니다.
- 고정 모델(재학습·재튜닝 없음): {"linear_model": "exp/step23_korean_expression_expansion/models/linear_char_expanded.joblib", "linear_sha256": "6eacd19ad8560753aa13e40d083374122ca7aabb39819474cf9a21ff9beda55e", "koelectra_dir": "exp/step24_v2_lightweight_hybrid_normalizer/models/koelectra_small_seed42", "koelectra_safetensors_sha256": "141797a7ea2942952665b708622dc0a68547e8bfd233fdd57550209f0c77ec5f", "T_lin": 0.4612332397014496, "T_koe": 0.9530041813850403, "alpha": 0.75, "T_fus": 1.051903419205685, "max_length": 32, "koelectra_device": "cpu", "no_training_no_tuning": true, "source": "STEP24-v2 seed42 hybrid_config (dev 결정값)"}

## 누수·독립성

| dataset | n_units | train_exact | train_near_ge_0.80 | train_near_ge_0.60 | gold_exact | gold_near_ge_0.80 | gold_near_test_ge_0.80 | silver | gold_candidate | eligible_for_unlabeled_analysis | negation_cue |
|---|---|---|---|---|---|---|---|---|---|---|---|
| BERT_NER_KO | 455 | 13 | 59 | 117 | 0 | 0 | 0 | 13 | 0 | 442 | 0 |
| KBMC | 4070 | 29 | 65 | 207 | 0 | 0 | 0 | 29 | 0 | 4041 | 49 |
| KO_MEDICAL_CHAT | 1677 | 0 |  |  | 0 | 1 | 1 | 0 | 0 | 1677 | 1104 |

외부 문장과 STEP21 gold 완전일치 0. 학습 표현과 완전일치 span 은 SILVER 로 분리(분석 집합 제외).

## 고정 모델 분석 (정답 없음)

| set | n | L-K agree | auto LINEAR_CHAR | auto KOELECTRA_SMALL | auto HYBRID_B | HB koe call | HB auto despite disagree | L pred top | HB pred top |
|---|---|---|---|---|---|---|---|---|---|
| A_NERKO_ST | 442 | 0.3326 | 0.3077 | 0.4864 | 0.5498 | 0.6923 | 110 | decreased_appetite:123 | pain:86 |
| B_NERKO_DS | 533 | 0.1201 | 0.1276 | 0.1932 | 0.272 | 0.8724 | 98 | decreased_appetite:240 | pain:123 |
| C_KBMC_DISEASE | 4041 | 0.1151 | 0.124 | 0.1257 | 0.2034 | 0.876 | 521 | decreased_appetite:1052 | EV:E_63:271 |
| D_KMC_FIRST_TURN | 1677 | 0.2582 | 0.1073 | 0.2785 | 0.3292 | 0.8927 | 286 | pain:310 | pain:311 |
| SILVER_TRAIN_EXACT | 42 | 0.8095 | 0.881 | 0.7619 | 0.9286 | 0.119 | 5 | pain:5 | pain:5 |

auto = Hybrid B 정책 기준 자동 수락(Linear margin ≥ T_lin, KoE confidence ≥ T_koe). 'unknown' = 1 − auto.

- 외부 '질병(DS)' span 에서 Hybrid B 자동 수락 145건 = 위험 자동 수락 후보(예: 고혈압→hemoptysis, 결핵→confusion, 1형 당뇨→pain). 77-class 닫힌 분류기라 '증상 아님'을 거절할 class 가 없음.
- 외부 '증상(ST)' span 442개 중 Linear top1 = decreased_appetite 123개 → 모르는 표현이 특정 class 로 몰림(sink).
- 관찰 사례(정답 아님): '코피가'→hemoptysis(코피 ≠ 객혈), '구토'→Linear nausea / KoE vomiting, '두통'→Linear decreased_appetite / KoE pain.
- 위험 범주 집계(SILVER 제외): {"MODEL_DISAGREEMENT": 5584, "AUTO_ACCEPT_DESPITE_DISAGREEMENT": 1015, "AUTO_ACCEPT_ON_EXTERNAL_DISEASE_SPAN": 145, "AUTO_ACCEPT_WITH_NEGATION_CUE": 363}
- SILVER(학습 표현과 완전일치 42 span) 규칙 concept 일치율: Linear 0.8571, KoE 0.881, Hybrid B 0.9048 — 학습 누수 집합이라 정확도 아님.

## latency (외부 ST span, single, CPU)

| path | n | mean_ms | p50_ms | p95_ms |
|---|---|---|---|---|
| LINEAR_CHAR_CPU | 442 | 0.34 | 0.335 | 0.484 |
| KOELECTRA_CPU | 442 | 5.029 | 4.655 | 7.142 |
| HYBRID_B_CPU | 442 | 4.298 | 5.002 | 8.147 |

## 해석

- 내부 regression 에서 Linear·Hybrid 의 자동 수락 정밀도 ≥95% 였던 임계값이 외부 분포에서는 모델 간 일치율이 낮은데도(ST span 33%) 절반 넘게 자동 수락 → 임계값이 외부 분포로 전이되지 않을 위험이 크다(정확도로 확인한 것은 아님).
- 외부 증상 표현에는 77 concept 밖 증상(예: 가려움·분비물 등)이 많을 것으로 보이나, concept 라벨이 없어 비율은 측정하지 못함.
## 다음 1순위

- 외부 ST span 442개(실제 의사 답변 출처, 학습·gold 와 독립)를 'MedMap concept 또는 OUT_OF_SCOPE' 로 라벨링 → 첫 외부 Gold. 문장 작성 불필요, 라벨링만 필요. 라벨러는 모델 예측을 보지 않게 한다.
- 동시에 77-class 에 OUT_OF_SCOPE/거절 경로 설계 필요(질병명 자동 수락 위험).
