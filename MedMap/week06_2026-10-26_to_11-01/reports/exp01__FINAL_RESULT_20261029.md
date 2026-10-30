# EXP-01 FINAL 결과(자동 생성, 사전등록 기준)

- run `exp/main_ai/exp01_symptom_graph/outputs/final_20261029_0925` · 기록 4496932 · 총 8351.92 s · 부모 피크 RSS 5574 MB · 상태 기록 ['STARTED', 'EVALUATED', 'COMPLETED'] · τ 0.0001 (SELECTED)
- FINAL 잠금 {'lock_sha256': 'ee8ef094a9acbf5400afcecccef46b38bd0441024c877aedc7d77398da979e08', 'external_clean': True} · 실행 잠금 ee8ef094a9ac · RG {'review_status': 'RUN', 'lock': {'locked': True, 'state': 'OK', 'changed_fields': [], 'frozen_at': '2026-10-27T15:18:06', 'sha256': '52f81aedf22a7da0c2d8089e1d69a34cfff4906b16a30743b6255f6c4479ec40'}}
- 검증 장치: aref 2146263회 최대 |차| 0.0, 참조 점수기 26368374회, 누출 PASS 3679308·NA 0

## 1. 가설별 판정(Holm m=6, 단측 α 0.025, 판정 = 조정 합성 p < 0.025)

| 가설 | 합성 p | Holm 순위 | α* | 조정 p | 기각 | 성분 p |
|---|---|---|---|---|---|---|
| H1 | 9.999e-05 | 1 | 0.0041667 | 0.00059994 | True | {"top5": 9.999000099990002e-05, "severe_miss": 9.999000099990002e-05} |
| H2a | 0.0010999 | 3 | 0.00625 | 0.0043996 | True | {"top5_ni": 9.999000099990002e-05, "severe_miss": 0.0010998900109989002} |
| H2b | 9.999e-05 | 1 | 0.0041667 | 0.00059994 | True | {"severe_miss": 9.999000099990002e-05, "wrong_term": 9.999000099990002e-05, "efficiency": 9.999000099990002e-05} |
| H3a | 1 | 4 | 0.0083333 | 1 | False | {"severe_miss": 1.0, "wrong_term": 9.999000099990002e-05} |
| H3b | 1 | 4 | 0.0083333 | 1 | False | {"severe_miss@42": 1.0, "wrong_term@42": 9.999000099990002e-05, "severe_miss@43": 1.0, "wrong_term@43": 9.999000099990002e-05, "severe_miss@44": 1.0, "wrong_term@44": 9.999000099990002e-05} |
| H3c | 1 | 4 | 0.0083333 | 1 | False | {"top5_ni": 1.0, "severe_miss": 1.0, "wrong_term": 9.999000099990002e-05} |

- **H1 라벨: SAFETY_HOLD** · 효과 {"H1_delta": 0.12137608485073824, "H1_mid_met": true}
- 단계 라벨: PB_REL=NOT_ELIGIBLE(안전 SAFETY_HOLD, 조건부 SAFETY_HOLD); PB=NOT_ELIGIBLE(안전 PASS, 조건부 ADOPTED); PC=NOT_ELIGIBLE(안전 SAFETY_FAIL, 조건부 SAFETY_FAIL)
- **사전 지정 채택 모델(순차 채택): C**
- 질환별 악화 규칙 발동(n≥100, (Δk)·50>n): {"PA": ["Pulmonary embolism"], "PB_REL": ["Acute pulmonary edema", "Croup", "PSVT", "Spontaneous pneumothorax"], "PB": [], "PC": ["Anaphylaxis", "Boerhaave", "Croup", "Epiglottitis", "Myocarditis", "PSVT", "Possible NSTEMI / STEMI", "Pulmonary embolism", "Spontaneous pneumothorax", "Stable angina", "Unstable angina"]}

## 2. 보조 보고(판정 아님): 성분 점추정·Holm 순위 수준 단측 한계·95% CI

| 성분 | 점추정 | 단측 한계(α*) | 95% CI | 빈 재표본 |
|---|---|---|---|---|
| H1:top5 | 0.12138 | 0.11815 | None | 0 |
| H1:severe_miss | -0.15018 | -0.14426 | None | 0 |
| H2a:top5_ni | 0.0058707 | 0.0042758 | None | 0 |
| H2a:severe_miss | 0.0019001 | 0.0044366 | None | 0 |
| H2b:efficiency | 0.60162 | 0.60472 | None | 0 |
| H2b:severe_miss | 0 | 0 | None | 0 |
| H2b:wrong_term | 0 | 0 | None | 0 |
| H3a:severe_miss | 0.043948 | 0.048058 | None | 0 |
| H3a:wrong_term | 0 | 0 | None | 0 |
| H3b:severe_miss@42 | 0.038248 | 0.041841 | None | 0 |
| H3b:wrong_term@42 | 0 | 0 | None | 0 |
| H3b:severe_miss@43 | 0.037579 | 0.041141 | None | 0 |
| H3b:wrong_term@43 | 0 | 0 | None | 0 |
| H3b:severe_miss@44 | 0.037192 | 0.040688 | None | 0 |
| H3b:wrong_term@44 | 0 | 0 | None | 0 |
| H3c:top5_ni | -0.036418 | -0.038636 | None | 0 |
| H3c:severe_miss | 0.043948 | 0.048058 | None | 0 |
| H3c:wrong_term | 0 | 0 | None | 0 |

## 3. 모델별 성능(Q=5, 잡음 없음, FINAL, 기술 통계)

| 모델 | WD | seed | τ | n | Top-1 | Top-3 | Top-5 | 재현율@8 | 중증 누락 | macro Top-5 | 평균 질문 | 계산 수 중앙값 | ECE | Brier |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A |  |  |  | 102203 | 0.9713 | 0.9938 | 0.9985 | 0.9996 | 0.0004 | 0.9820 | 5.00 |  | 0.0029 | 0.0399 |
| B |  |  |  | 102203 | 0.4966 | 0.7035 | 0.7991 | 0.8910 | 0.1165 | 0.7231 | 4.87 | 11 | 0.0245 | 0.5895 |
| C |  |  |  | 102203 | 0.5022 | 0.7467 | 0.8130 | 0.8800 | 0.1873 | 0.7603 | 5.00 | 8494 | 0.0533 | 0.5650 |
| PA |  |  |  | 102203 | 0.6494 | 0.8787 | 0.9344 | 0.9678 | 0.0372 | 0.9232 | 5.00 | 8494 | 0.0200 | 0.4239 |
| PB |  |  | 0.0001 | 102203 | 0.7239 | 0.8950 | 0.9402 | 0.9672 | 0.0391 | 0.9187 | 5.00 | 12994 | 0.0122 | 0.3395 |
| PB_REL |  |  |  | 102203 | 0.6694 | 0.8926 | 0.9402 | 0.9672 | 0.0391 | 0.9196 | 5.00 | 16694 | 0.0155 | 0.4070 |
| PC | WD_CORRECT | 42 | 0.0001 | 102203 | 0.8620 | 0.9479 | 0.9678 | 0.9785 | 0.0210 | 0.9672 | 5.00 | 3159 | 0.0348 | 0.1666 |
| PC | WD_MODEL | 42 | 0.0001 | 102203 | 0.6861 | 0.8536 | 0.9038 | 0.9383 | 0.0830 | 0.8801 | 5.00 | 7651 | 0.0098 | 0.3647 |
| PC | WD_MODEL_WRONG | 42 | 0.0001 | 102203 | 0.6868 | 0.8508 | 0.9039 | 0.9382 | 0.0830 | 0.8798 | 5.00 | 8469 | 0.0263 | 0.3774 |
| PC | WD_RANDOM_WRONG | 42 | 0.0001 | 102203 | 0.6712 | 0.8594 | 0.9155 | 0.9506 | 0.0773 | 0.8923 | 5.00 | 8063 | 0.0101 | 0.3937 |
| PC | WD_RANDOM_WRONG | 43 | 0.0001 | 102203 | 0.6692 | 0.8587 | 0.9147 | 0.9504 | 0.0766 | 0.8877 | 5.00 | 8063 | 0.0098 | 0.3945 |
| PC | WD_RANDOM_WRONG | 44 | 0.0001 | 102203 | 0.6701 | 0.8583 | 0.9145 | 0.9502 | 0.0762 | 0.8903 | 5.00 | 8061 | 0.0109 | 0.3939 |

Q=3 Top-5: A 0.9930, B 0.6339, C 0.7683, PA 0.8726, PB(τ0.0001) 0.8864, PB_REL 0.8860

Q=10 Top-5: A 0.9996, B 0.9300, C 0.8805, PA 0.9871, PB(τ0.0001) 0.9863, PB_REL 0.9863

## 4. 중증 질환별 누락(Q=5, 잡음 없음; n·누락 수)

| 질환 | n | C | PA | PB_REL | PB | PC@WD_MODEL | A | B |
|---|---|---|---|---|---|---|---|---|
| Acute dystonic reactions | 2512 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Acute pulmonary edema | 1850 | 0 | 1 | 71 | 71 | 51 | 0 | 1 |
| Anaphylaxis | 2818 | 0 | 4 | 2 | 2 | 199 | 0 | 0 |
| Boerhaave | 1471 | 625 | 0 | 0 | 0 | 141 | 0 | 0 |
| Croup | 292 | 82 | 0 | 8 | 8 | 0 | 0 | 241 |
| Ebola | 67 | 16 | 1 | 3 | 3 | 4 | 11 | 17 |
| Epiglottitis | 1769 | 723 | 123 | 80 | 80 | 156 | 0 | 0 |
| Guillain-Barré syndrome | 2303 | 304 | 0 | 0 | 0 | 0 | 0 | 0 |
| Larygospasm | 1048 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Myocarditis | 1098 | 425 | 161 | 65 | 65 | 199 | 0 | 832 |
| PSVT | 1828 | 376 | 7 | 143 | 143 | 355 | 1 | 18 |
| Possible NSTEMI / STEMI | 2154 | 919 | 203 | 228 | 228 | 367 | 0 | 567 |
| Pulmonary embolism | 2666 | 0 | 144 | 114 | 114 | 101 | 0 | 290 |
| Scombroid food poisoning | 1771 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Spontaneous pneumothorax | 1037 | 278 | 60 | 88 | 88 | 371 | 0 | 206 |
| Stable angina | 1664 | 932 | 244 | 266 | 266 | 158 | 0 | 530 |
| Unstable angina | 2072 | 644 | 108 | 42 | 42 | 257 | 0 | 608 |
