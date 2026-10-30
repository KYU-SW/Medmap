# STEP24-v2 — Lightweight Korean Encoder + Linear Hybrid (PROTOCOL_DEVIATION)

- STEP24_RESULT = **LINEAR_ONLY_RETAIN** (seed 42) · 5 seed 평균 기준 = **HYBRID_RECOMMENDED** · SEMANTIC_GAIN = **FAIL** (+4.3%p; 5 seed 평균 +4.3%p) · HYBRID_GATE(HYBRID_C) = **FAIL** · SPEED(HYBRID_C) = **EXCELLENT**
- PROTOCOL_DEVIATION: v1 사전 등록 grid(lr≤5e-5, epoch≤8)에서 KoELECTRA 학습 붕괴(학습 정확도 4.3%, 단일 class) → 학습 grid 만 확장(사용자 승인). 데이터·dev·test·Hybrid 정책·판정 규칙은 v1 그대로. v1 결과 폴더는 수정하지 않음(data/v1_snapshot_sha256.txt).
- MODEL = monologg/koelectra-small-v3-discriminator@7488f8d (Apache-2.0) · GPU NVIDIA GeForce RTX 4060 Ti · IMPLEMENTATION_OK = True · NEW_BLIND_HOLDOUT_REQUIRED = YES
- FIXED_REGRESSION_TEST 는 여러 번 본 regression test → 모델 비교용, 최종 blind 성능 아님. 설정·epoch·α·임계값은 모두 dev 로만 선택.

## 1. 구현 검사 (학습셋만)

| check | PASS | detail |
|---|---|---|
| T1_tokenizer | True | {"tokenizer_class": "BertTokenizer", "vocab": 35000, "config_vocab": 35000, "unk_rate": 0.00025, "n_truncated_at_max_len": 0, "decode_roundtrip_rate": 0.9973} |
| T2_label_map | True | {"n": 77} |
| T3_pretrained_load | True | {"n_shared_tensors": 199, "all_equal": true, "newly_initialized": ["classifier.dense.bias", "classifier.dense.weight", "classifier.out_proj.bias", "classifier.o |
| T4_initial_loss | True | {"loss": 4.3407, "ln77": 4.3438} |
| T5_gradient | True | {"grad_norm": {"embeddings": 0.012818153947591782, "layer0": 0.0035977871157228947, "layer11": 0.032830093055963516, "classifier": 0.3068634569644928}} |
| T6_optimizer_step | True | {"max_abs_change": {"embeddings": 0.00020074844360351562, "layer0": 0.000202178955078125, "layer11": 0.00020164251327514648, "classifier": 0.0002001672983169555 |
| T7_overfit_64 | False | {"loss_history": [[0, 4.3382], [25, 3.8552], [50, 3.3155], [75, 2.9768], [100, 2.437], [125, 1.4237], [149, 0.9462]], "final_eval_loss": 1.195, "train_acc": 0.7 |
| T8_train_eval_mode | True | {"train_differs": true, "eval_equal": true} |
| T7b_overfit_64_600steps(post-hoc) | True | {"loss_history": [[0, 4.3382], [100, 2.437], [200, 0.6419], [300, 0.1385], [400, 0.0398], [500, 0.0281], [599, 0.0135]], "final_eval_loss": 0.0077, "train_acc": |

T1–T6·T8 PASS 그리고 (T7 또는 사후 T7b) PASS. T7 FAIL 기록은 유지. T7b 는 T7 FAIL 확인 뒤 추가한 사후 검사(같은 64문장·600 step).

## 2. 학습 grid (dev 선택, seed 42)

| grid_index | lr | epochs | loss | best_epoch | best_dev_top1 | best_dev_recall_at_3 | best_dev_loss | train_acc_at_best | min_dev_loss_epoch | final_dev_loss | dev_loss_rise_after_min | final_train_acc | final_dev_top1 | train_seconds | peak_vram_alloc_mib |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 0.0001 | 20 | CE | 20 | 0.5254 | 0.8814 | 2.01682 | 0.4861 | 20 | 2.01682 | 0.0 | 0.4861 | 0.5254 | 46.6 | 483.9 |
| 1 | 0.0001 | 20 | CLASS_WEIGHTED_CE | 20 | 0.2542 | 0.5763 | 3.08907 | 0.2985 | 20 | 3.08907 | 0.0 | 0.2985 | 0.2542 | 47.6 | 483.9 |
| 2 | 0.0001 | 40 | CE | 39 | 0.8983 | 0.9322 | 0.57682 | 0.8534 | 39 | 0.57996 | 0.00314 | 0.8534 | 0.8814 | 90.7 | 483.9 |
| 3 | 0.0001 | 40 | CLASS_WEIGHTED_CE | 36 | 0.5932 | 0.8305 | 2.29742 | 0.7274 | 40 | 2.27093 | 0.0 | 0.7337 | 0.5763 | 89.7 | 483.9 |
| 4 | 0.0002 | 20 | CE | 17 | 0.8983 | 0.8983 | 0.86236 | 0.8356 | 20 | 0.81213 | 0.0 | 0.8436 | 0.8814 | 42.1 | 483.9 |
| 5 | 0.0002 | 20 | CLASS_WEIGHTED_CE | 20 | 0.4068 | 0.6949 | 2.47942 | 0.5049 | 20 | 2.47942 | 0.0 | 0.5049 | 0.4068 | 43.5 | 483.9 |
| 6 | 0.0002 | 40 | CE | 17 | 0.8983 | 0.9661 | 0.7144 | 0.84 | 20 | 0.85871 | 0.19124 | 0.9723 | 0.8814 | 86.1 | 483.9 |
| 7 | 0.0002 | 40 | CLASS_WEIGHTED_CE | 40 | 0.8814 | 0.9492 | 0.92776 | 0.9982 | 40 | 0.92776 | 0.0 | 0.9982 | 0.8814 | 88.0 | 483.9 |
| 8 | 0.0003 | 20 | CE | 14 | 0.8983 | 0.9322 | 0.78076 | 0.8499 | 17 | 0.75419 | 0.03317 | 0.8615 | 0.8644 | 42.9 | 483.9 |
| 9 | 0.0003 | 20 | CLASS_WEIGHTED_CE | 20 | 0.339 | 0.7119 | 2.36908 | 0.462 | 19 | 2.36908 | 0.00177 | 0.462 | 0.339 | 47.3 | 483.9 |
| 10 | 0.0003 | 40 | CE | 23 | 0.9492 | 0.9661 | 0.6403 | 0.9151 | 16 | 0.7082 | 0.09558 | 0.9875 | 0.9492 | 81.8 | 483.9 |
| 11 | 0.0003 | 40 | CLASS_WEIGHTED_CE | 28 | 0.8644 | 0.9322 | 0.87627 | 0.9929 | 40 | 0.66618 | 0.0 | 1.0 | 0.8305 | 90.1 | 483.9 |

선택: grid 10 {"lr": 0.0003, "epochs": 40, "loss": "CE"} · seed 42 재학습 = grid run 일치 True. 규칙: run 안 dev best epoch, run 간 dev Top-1 > R@3 > dev loss > grid 순서.

과적합 판단: `dev_loss_rise_after_min` > 0 이면 dev loss 최저점 이후 상승(과적합 신호). checkpoint 는 학습 정확도가 아니라 dev 기준 epoch.

## 3. seed 변동성 (선택 설정 고정, seed 42–46)

| model | dev_top1 | test_top1 | test_recall_at_3 | low_sim_top1 | auto_precision | auto_coverage |
|---|---|---|---|---|---|---|
| LINEAR_CHAR | 88.1% ± 0.0 | 88.1% ± 0.0 | 95.4% ± 0.0 | 60.9% ± 0.0 | 98.6% ± 0.0 | 66.1% ± 0.0 |
| KOELECTRA_SMALL | 92.2% ± 1.7 | 83.9% ± 1.1 | 90.3% ± 0.9 | 65.2% ± 4.8 | 91.5% ± 2.6 | 83.9% ± 7.8 |
| HYBRID_A | 88.1% ± 0.0 | 88.1% ± 0.0 | 97.4% ± 0.7 | 60.9% ± 0.0 | 96.2% ± 0.5 | 81.3% ± 1.6 |
| HYBRID_B | 90.5% ± 0.8 | 88.4% ± 0.7 | 93.8% ± 0.4 | 73.0% ± 4.3 | 94.2% ± 2.1 | 90.1% ± 3.8 |
| HYBRID_C | 90.8% ± 1.4 | 90.5% ± 2.2 | 96.3% ± 0.8 | 77.4% ± 4.3 | 96.3% ± 1.5 | 83.3% ± 2.6 |

seed 별 dev Top-1: {"42": 0.9492, "43": 0.9322, "44": 0.9153, "45": 0.8983, "46": 0.9153} · best epoch: {"42": 23, "43": 25, "44": 25, "45": 11, "46": 27} · Linear 오답·KoELECTRA 정답(core): {"42": 6, "43": 6, "44": 6, "45": 7, "46": 6} · 그중 low-sim: {"42": 4, "43": 5, "44": 5, "45": 5, "46": 4} · Linear 정답·KoELECTRA 오답: {"42": 10, "43": 10, "44": 9, "45": 13, "46": 12} · PRIMARY_HYBRID: {"42": "HYBRID_C", "43": "HYBRID_B", "44": "HYBRID_C", "45": "HYBRID_B", "46": "HYBRID_C"}

## 4. 핵심 비교 (seed 42, core 109)

| model | top1 | r3 | r5 | macro | low_sim(n=23) | auto_P | auto_cov | p50_ms | p95_ms | dev_top1 |
|---|---|---|---|---|---|---|---|---|---|---|
| LINEAR_CHAR | 88.1% | 95.4% | 97.2% | 88.9% | 60.9% | 98.6% | 66.1% | 0.275 | 0.403 | 88.1% |
| KOELECTRA_SMALL | 84.4% | 89.0% | 90.8% | 85.6% | 65.2% | 92.6% | 87.2% | 10.422 | 19.686 | 94.9% |
| HYBRID_A | 88.1% | 97.2% | 99.1% | 88.9% | 60.9% | 95.6% | 82.6% | 10.543 | 19.425 | 88.1% |
| HYBRID_B | 88.1% | 93.6% | 95.4% | 88.6% | 73.9% | 95.0% | 90.8% | 0.403 | 10.981 | 91.5% |
| HYBRID_C | 87.2% | 95.4% | 98.2% | 88.8% | 69.6% | 93.8% | 88.1% | 10.543 | 19.425 | 91.5% |

HYBRID_B Transformer 호출률 test 33.9%. HYBRID_C α = 0.75(dev).

## 5. 표면 유사도 구간별 Top-1 (seed 42)

| bucket | n | LINEAR_CHAR | KOELECTRA_SMALL | HYBRID_A | HYBRID_B | HYBRID_C |
|---|---|---|---|---|---|---|
| <0.3 | 1 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| 0.3-0.5 | 22 | 63.6% | 68.2% | 63.6% | 77.3% | 72.7% |
| 0.5-0.7 | 60 | 95.0% | 85.0% | 95.0% | 88.3% | 88.3% |
| >=0.7 | 26 | 96.2% | 100.0% | 96.2% | 100.0% | 100.0% |

## 6. Agreement (seed 42, core)

| cell | n | low_sim_n |
|---|---|---|
| both_correct | 86 | 11 |
| both_wrong_different_label | 3 | 1 |
| both_wrong_same_label | 4 | 4 |
| linear_correct_transformer_wrong | 10 | 3 |
| linear_wrong_transformer_correct | 6 | 4 |

## 7. 오류 분류 (seed 42)

- LINEAR_CHAR: surface-pattern bias 5, semantic paraphrase 3, body-site confusion 2, unseen synonym 2, nausea/vomiting 1
- KOELECTRA_SMALL: Transformer semantic confusion 10, body-site confusion 2, unseen synonym 2, semantic paraphrase 2, nausea/vomiting 1
- HYBRID_C: unseen synonym 6, semantic paraphrase 5, body-site confusion 1, generic expression 1, nausea/vomiting 1

## 8. 자원 · 속도

- 학습 peak VRAM(seed 42) alloc 483.9 MiB / reserved 516.0 MiB · 추론 peak alloc 105.7 MiB / reserved 132.0 MiB
- grid 12 run 총 학습 796s
| path | n | mean_ms | median_ms | p50_ms | p95_ms | max_ms |
|---|---|---|---|---|---|---|
| LINEAR_CHAR_CPU | 327 | 0.293 | 0.275 | 0.275 | 0.403 | 0.565 |
| KOELECTRA_GPU | 327 | 11.907 | 10.422 | 10.422 | 19.686 | 22.738 |
| KOELECTRA_CPU | 327 | 5.145 | 4.947 | 4.947 | 7.084 | 10.525 |
| HYBRID_B_fastpath | 327 | 3.458 | 0.403 | 0.403 | 10.981 | 21.214 |
| HYBRID_A_or_C_both_models | 327 | 11.399 | 10.543 | 10.543 | 19.425 | 22.115 |

batch GPU 109문장: 19.81 ms. STT 제외.

## 9. 한계

- low-sim subset n=23(1문장 = 4.3%p). dev 59 로 epoch·설정을 고름 → dev 낙관 편향 가능. FIXED_REGRESSION_TEST 는 blind 아님.
- 학습·test 모두 Claude 계열 작성 합성 문장. 실제 환자 발화 0. production 미연결.
