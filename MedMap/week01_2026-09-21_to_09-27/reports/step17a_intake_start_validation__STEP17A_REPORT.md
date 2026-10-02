# STEP17A — INTAKE START-STATE VALIDATION 결과 (2026-09-24)

**판정: NATURAL_INTAKE_K3_GO** (사전등록 gate A·B·C·D1 모두 PASS, primary clean holdout)

## Validity
- 사전등록: PREREG.md SHA `ef3e2c50…`
  - stage 1: split 생성 전 고정 (커밋 d2cd315)
  - stage 1b: split manifest 추가 (6ccb1dd)
  - stage 2: 모델·IG table·코드 13개 파일 고정 (cc62d76)
- `s17a_run.py`가 FREEZE 두 파일을 모두 검증한 뒤 holdout을 열었다. 결과를 본 뒤 규칙·gate·cohort 변경은 없다. smoke 후 코드 수정도 없다.
- 읽은 파일은 `release_train_patients`, `release_evidences.json`뿐이다. 원본 VALIDATION 0, TEST 0, conditions 0.
- STEP16B_HOLDOUT 204,663행은 소속만 판정하고 즉시 제거했다(행 수와 row_index SHA로 검증). 토큰·라벨 사용 0.
- smoke는 dev 200명에서만 했다. holdout은 최종 평가에서 처음 열었다.
- UNSAFE 답 상태 0, invalid start 0(전 조건), 선택 전 hidden answer 접근 0(reveal은 선택 확정 후).

## Split / 모델
- STEP16B_TRAIN 820,939 → **DEV 656,593 / HOLDOUT 164,346 (0.2002)**. 규칙: `sha256("step17a|"+key16)`, `[:8] % 5 == 0`.
- recipe 모델: dev 전용 MODEL_k3(STEP16B 레시피, train acc 0.4339)와 dev 전용 IG table.
- secondary: 제품 `model_k3.pkl`과 STEP16B IG table을 같은 holdout 행에 적용. 이 행들은 제품 모델 학습 데이터에 포함되므로 **IN_SAMPLE_DESCRIPTIVE**이며 판정에 쓰지 않는다.

## 초기 진단 (HO_ALL 164,346명 × seed 3)
| 조건 | top1 | top3 | log loss | rank 평균 |
|---|---|---|---|---|
| R0 random | 0.4283 | 0.6669 | 1.678 | 4.44 |
| R1 positive-heavy | 0.9421 | 0.9972 | 0.135 | 1.08 |
| R2 fixed-bootstrap | 0.5216 | 0.7830 | 1.287 | 2.86 |
| **R3 hybrid** | **0.8489** | **0.9755** | 0.379 | 1.26 |
| R3-MASK (보조) | 0.7958 | 0.9511 | 0.512 | 1.46 |

R3 − R0 차이(환자 cluster bootstrap 1000회):
- top3: **+0.3086 [+0.3066, +0.3108]**
- top1: +0.4206 [+0.4182, +0.4230]

한국어 initial 27개 subset(116,984명, 보조):
- R0 top1 0.297, R2 0.395, R3 0.811, R3-MASK 0.742

## 시작 이후 IG (SIM 10,000명)
| 조건 | Recovery@1Q RANDOM → IG | IG−RANDOM [95% CI] | Recovery@3Q R → IG | C→W@3Q R → IG | C→W@3Q 차이 [95% CI] |
|---|---|---|---|---|---|
| R0 | 0.054 → 0.433 | +0.379 [0.369, 0.390] | 0.124 → 0.867 | 0.070 → 0.015 | −0.056 [−0.060, −0.051] |
| R2 | 0.071 → 0.756 | +0.685 [0.672, 0.697] | 0.156 → 0.940 | 0.058 → 0.003 | −0.055 [−0.060, −0.051] |
| **R3** | 0.115 → 0.784 | **+0.670 [0.650, 0.689]** | 0.209 → 0.918 | 0.018 → 0.0006 | **−0.017 [−0.020, −0.015]** |
| R3-MASK | 0.102 → 0.796 | +0.694 [0.679, 0.709] | 0.200 → 0.931 | 0.023 → 0.001 | −0.022 [−0.023, −0.020] |

R3 모집단 크기: 초기 오답 4,537뷰(2,061명), 초기 정답 25,463뷰(8,917명).

## Gate
| | 규칙 | 값 | 판정 |
|---|---|---|---|
| A | R3−R0 top3 CI 하한 > −0.05 | +0.3066 | PASS |
| B | R3 IG−RANDOM Recovery@1Q CI 하한 > +0.10 | +0.6498 | PASS |
| C | R3 IG−RANDOM C→W@3Q CI 상한 ≤ 0 | −0.0155 | PASS |
| D1 | R3 exact-k 완성률 ≥ 0.95 | 1.000 | PASS |

## Secondary (제품 가중치, in-sample 기술)
Primary와 차이가 0.01 이내다.
- R3 top1 0.855, top3 0.979
- R3−R0 top3 +0.311
- R3 IG−RANDOM Recovery@1Q +0.672

in-sample 효과는 작아 보이나, 판정에는 쓰지 않는다.

## Fixed bootstrap 감사 (dev, 순서 불변)
| | POS 비율 | initial과 같은 비율 | I(answer;disease) bits | P(POS\|d) 상위 |
|---|---|---|---|---|
| E_91 열 | 0.211 | 0.041 | 0.441 | Bronchiolitis 0.99, HIV 0.84, Influenza 0.80 |
| E_53 통증 | 0.768 | 0.184 | 0.739 | 여러 질환 1.00 |
| E_66 숨참 | 0.390 | 0.084 | 0.435 | Bronchiolitis 1.00, 천식 악화 0.86 |
| E_201 기침(예비) | 0.311 | 0.074 | 0.532 | 결핵 1.00 |
| E_175(예비) | 0.041 | 0.006 | 0.187 | |
| E_88(예비) | 0.069 | 0.010 | 0.270 | |

- 모두 top-level binary다. parent/gate, NA, missing 문제 없음.
- E_53은 initial과 겹치는 비율이 18.4%라 예비 문항 사용이 잦다.

## Coverage (dev)
- initial 고유값 96개(전부 binary, 과거력 0). 한국어 27개 coverage **0.7122**.
- 빈도순 추가 번역 필요량: 80% → +8, 90% → +27, 95% → +42, 99% → +58. 상위 후보는 E_82, E_97, E_144, E_76, E_217(`02_initial_coverage_dev.json`).
- 제품 localization backlog이며 gate가 아니다(D2).

## 해석 — 반드시 같이 읽을 것
1. **gate A는 "악화 감지"용인데, 결과는 대폭 개선이다.**
   - DDXPlus 시뮬레이션 환자의 양성 증상은 질환 프로필에서 생성된다.
   - 그래서 "실제 양성 3개"는 "무작위 질문 3개의 답(대부분 음성)"보다 훨씬 많은 정보를 담는다.
   - 이것은 시뮬레이터의 성질이다. **R3의 top1 0.85를 제품 진단 성능으로 인용하면 안 된다.**
2. **R3는 사용자가 진짜 양성만, 오류 없이 확인한다고 가정한다.**
   - 잘못 확인된 양성(매퍼 FP 약 3.7% 중 사용자가 걸러내지 못한 것, 오해, 질환과 무관한 증상)에 대한 강건성은 **검증하지 않았다.**
   - 양성 정보의 영향이 이렇게 크므로, 잘못된 양성도 크게 작용할 수 있다.
3. 이 결과가 보여주는 것:
   - 같은 k3 레시피는 양성 위주 시작 상태에서 무너지지 않는다(분포 이동에 의한 붕괴 없음).
   - 그 상태에서도 IG 질문은 RANDOM보다 크게 낫다.
   - IG는 정답 사례를 RANDOM보다 덜 망친다.
4. D1 = 1.0은 구조적 결과다. 고정 목록 6개 중 initial과 겹치는 것은 최대 1개라 항상 3개를 채운다.
5. R3는 POSITIVE만 사용한다. 매퍼의 SAFE NEGATIVE 확인과 "모름"(UNKNOWN) 답이 섞인 시작 상태는 미검증이다.

## 산출물
- JSON(추적): `P_summary.json`(17196aa2…), `S_summary.json`(1ff680d0…)
- 대용량 CSV(추적 제외, SHA 기록): `P_initial.csv.gz` 8cac9b17…, `P_sim.csv.gz` 71bfe4b0…, `S_initial.csv.gz` 9b83ab0f…, `S_sim.csv.gz` 1da30526…
- 로그: `logs/`
