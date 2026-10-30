# STEP24 — Lightweight Korean Encoder + Linear Hybrid Normalizer

- STEP24_RESULT = **LIGHTWEIGHT_TRANSFORMER_INSUFFICIENT** · SEMANTIC_GAIN = **FAIL** (-60.9%p) · HYBRID_GATE(HYBRID_C) = **FAIL** · SPEED(HYBRID_C) = **EXCELLENT**
- MODEL = monologg/koelectra-small-v3-discriminator@7488f8d (Apache-2.0, 56.8 MB) · GPU_USED = YES (NVIDIA GeForce RTX 4060 Ti) · NEW_BLIND_HOLDOUT_REQUIRED = YES
- 데이터 고정(STEP23 EXPANDED 1,119 · core dev 59 · FIXED_REGRESSION_TEST core 109), 모델만 변경. 선택·임계값·α 는 dev 에서만. regression test 는 blind 아님 → 모델 비교용.
- 정규화 모델일 뿐: 부정·시점·화자·복수 증상 span 은 NLU 범위. softmax 는 분류 confidence(임상 확률 아님).

## 1. 핵심 비교 (core 109)

| model | top1 | r3 | r5 | macro | low_sim_top1(n=23) | unseen(STEP21) | auto_P | auto_cov | confirm_rate | p50_ms | p95_ms | dev_top1 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| LINEAR_CHAR | 88.1% | 95.4% | 97.2% | 88.9% | 60.9% | 87.6% | 98.6% | 66.1% | 33.9% | 0.265 | 0.353 | 88.1% |
| KOELECTRA_SMALL | 4.6% | 19.3% | 36.7% | 5.0% | 0.0% | 4.1% | — | 0.0% | 100.0% | 7.584 | 13.994 | 6.8% |
| HYBRID_A | 88.1% | 93.6% | 95.4% | 88.9% | 60.9% | 87.6% | 100.0% | 4.6% | 95.4% | 10.736 | 19.239 | 88.1% |
| HYBRID_B | 67.0% | 71.6% | 78.9% | 69.1% | 34.8% | 63.9% | 98.6% | 66.1% | 33.9% | 0.389 | 19.566 | 78.0% |
| HYBRID_C | 87.2% | 95.4% | 98.2% | 88.1% | 60.9% | 86.6% | 96.7% | 82.6% | 17.4% | 10.736 | 19.239 | 88.1% |

HYBRID_B Transformer 호출률: test 33.9% · dev 20.3%. PRIMARY_HYBRID = HYBRID_C(dev 선택). HYBRID_C α = 0.5(dev).

## 2. 표면 유사도 구간별 Top-1

| bucket | n | LINEAR_CHAR | KOELECTRA_SMALL | HYBRID_A | HYBRID_B | HYBRID_C |
|---|---|---|---|---|---|---|
| <0.3 | 1 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| 0.3-0.5 | 22 | 63.6% | 0.0% | 63.6% | 36.4% | 63.6% |
| 0.5-0.7 | 60 | 95.0% | 6.7% | 95.0% | 73.3% | 93.3% |
| >=0.7 | 26 | 96.2% | 3.9% | 96.2% | 80.8% | 96.2% |

## 3. Agreement (core test)

| cell | n | low_sim_n |
|---|---|---|
| both_correct | 5 | 0 |
| both_wrong_different_label | 13 | 9 |
| linear_correct_transformer_wrong | 91 | 14 |

일치율 4.6%, 일치 시 정답률 100.0%.

## 4. 오류 분류

- LINEAR_CHAR: semantic paraphrase 7, unseen synonym 3, body-site confusion 2, nausea/vomiting 1
- KOELECTRA_SMALL: Transformer semantic confusion 87, semantic paraphrase 7, fatigue/weakness 6, unseen synonym 4
- HYBRID_C: semantic paraphrase 7, unseen synonym 4, body-site confusion 2, nausea/vomiting 1

## 5. KoELECTRA 학습 (dev 선택)

- 선택: {"epochs": 8, "lr": 5e-05, "loss": "CE"} · 고정 {"batch": 32, "weight_decay": 0.01, "warmup_ratio": 0.1, "grad_clip": 1.0, "max_length": 32, "seed": 42, "optimizer": "AdamW", "schedule": "linear"} · dev Top-1 6.8% · 재학습 일치 True
- 학습 peak VRAM alloc 483.9 MiB / reserved 514.0 MiB · 추론 peak alloc 105.7 MiB / reserved 132.0 MiB
- max_length = 32 (토큰 길이 p99 26, 최대 32)

| grid_index | epochs | lr | loss | dev_top1 | dev_recall_at_3 | train_seconds | peak_vram_alloc_mib |
|---|---|---|---|---|---|---|---|
| 0 | 3 | 2e-05 | CE | 0.0678 | 0.1864 | 8.3 | 483.9 |
| 1 | 3 | 2e-05 | CLASS_WEIGHTED_CE | 0.0 | 0.0339 | 7.0 | 483.9 |
| 2 | 3 | 3e-05 | CE | 0.0678 | 0.1864 | 6.2 | 483.9 |
| 3 | 3 | 3e-05 | CLASS_WEIGHTED_CE | 0.0 | 0.0339 | 5.3 | 483.9 |
| 4 | 3 | 5e-05 | CE | 0.0678 | 0.1864 | 5.5 | 483.9 |
| 5 | 3 | 5e-05 | CLASS_WEIGHTED_CE | 0.0339 | 0.0508 | 5.0 | 483.9 |
| 6 | 5 | 2e-05 | CE | 0.0678 | 0.1864 | 8.8 | 483.9 |
| 7 | 5 | 2e-05 | CLASS_WEIGHTED_CE | 0.0 | 0.0339 | 8.8 | 483.9 |
| 8 | 5 | 3e-05 | CE | 0.0678 | 0.2203 | 10.9 | 483.9 |
| 9 | 5 | 3e-05 | CLASS_WEIGHTED_CE | 0.0 | 0.1017 | 8.3 | 483.9 |
| 10 | 5 | 5e-05 | CE | 0.0678 | 0.1864 | 9.2 | 483.9 |
| 11 | 5 | 5e-05 | CLASS_WEIGHTED_CE | 0.0 | 0.0508 | 7.6 | 483.9 |
| 12 | 8 | 2e-05 | CE | 0.0678 | 0.1864 | 15.0 | 483.9 |
| 13 | 8 | 2e-05 | CLASS_WEIGHTED_CE | 0.0339 | 0.1356 | 14.7 | 483.9 |
| 14 | 8 | 3e-05 | CE | 0.0678 | 0.1864 | 16.5 | 483.9 |
| 15 | 8 | 3e-05 | CLASS_WEIGHTED_CE | 0.0169 | 0.0847 | 16.9 | 483.9 |
| 16 | 8 | 5e-05 | CE | 0.0678 | 0.2373 | 14.8 | 483.9 |
| 17 | 8 | 5e-05 | CLASS_WEIGHTED_CE | 0.0508 | 0.2203 | 12.8 | 483.9 |

## 6. Latency (single message, warm-up 후 327회, STT 제외)

| path | n | mean_ms | median_ms | p50_ms | p95_ms | max_ms |
|---|---|---|---|---|---|---|
| LINEAR_CHAR_CPU | 327 | 0.278 | 0.265 | 0.265 | 0.353 | 0.432 |
| KOELECTRA_GPU | 327 | 8.905 | 7.584 | 7.584 | 13.994 | 19.805 |
| KOELECTRA_CPU | 327 | 4.73 | 4.554 | 4.554 | 6.197 | 7.613 |
| HYBRID_B_fastpath | 327 | 4.647 | 0.389 | 0.389 | 19.566 | 20.524 |
| HYBRID_A_or_C_both_models | 327 | 12.646 | 10.736 | 10.736 | 19.239 | 20.287 |

batch(GPU, 109 문장): 26.518 ms/batch · 0.2433 ms/문장. CPU threads 4.

## 7. 한계

- FIXED_REGRESSION_TEST 는 blind 아님. low-similarity subset n=23(1문장 = 4.3%p) → 차이 해석 주의.
- 학습·test 모두 Claude 계열 작성 합성 문장. 실제 환자 발화 0. production 미연결.
