# STEP 12 — C1 검증: S2는 기본 진단모델 confidence의 재표현인가? (2026-09-21)

기존 산출물만 사용(model.pkl 추론, scores.parquet, cond_token_logp.npz, DDXPlus 공식 PATHOLOGY/DIFFERENTIAL). 학습·다운로드·LLM 라벨 없음. 기존 파일 무수정. validate 132,448명 × (k∈{3,5,10,all} × seed{42,43,44}) = 1,324,480행. 재추론 확률이 저장된 working_dx·wd_prob와 일치함을 assert로 확인.

## 판정: **C1_PARTIAL**

## 1. 오답의 confidence 분포 (`02_confidence_strata.csv`, seed 42)
| k | 오답 수 | 오답 conf 중앙값 | 정답 conf 중앙값 | 오답 conf≥0.8 | ≥0.9 | ≥0.95 |
|---|---|---|---|---|---|---|
| 3 | 12,012 | 0.551 | 0.997 | 750 (6.2%) | 157 (1.3%) | 19 (0.2%) |
| 5 | 5,161 | 0.639 | 1.000 | 386 (7.5%) | 152 (2.9%) | 73 (1.4%) |
| 10 | 1,990 | 0.717 | 1.000 | 442 (22%) | 13 | 1 |
| all | 436 | 0.803 | 1.000 | 223 (51%) | 74 | 47 |
→ Reviewer C1 지적 재확인: NATURAL_ERROR의 대부분은 모델이 스스로 확신하지 못한 사례. 고신뢰(≥0.9) 오답은 k3·k5에서 seed당 140~157건(3 seed 일관), k10·k≥0.95는 표본 부족.

## 2. 층별 오답 탐지 (`03_method_comparison.csv`, seed 3개 평균)
| k | 층 | conf AUROC / TPR@FPR5 | margin | entropy | **S2** AUROC / TPR@FPR5 |
|---|---|---|---|---|---|
| 3 | ALL | **0.943** / 0.55 | 0.942 / 0.54 | 0.930 / 0.48 | 0.917 / 0.34 |
| 3 | conf≥0.9 (n_wrong 155) | 0.966 / 0.79 | 0.972 / 0.86 | 0.951 / 0.65 | **0.978 / 0.99** |
| 5 | ALL | **0.970** / 0.79 | 0.970 / 0.79 | 0.967 / 0.76 | 0.956 / 0.59 |
| 5 | conf≥0.9 (n_wrong 144) | 0.976 / 0.87 | 0.976 / 0.87 | 0.974 / 0.86 | **0.983 / 1.00** |
| 10 | ALL | 0.986 / 1.0 | 0.986 | 0.986 | 0.981 / 1.0 |
| 10 | conf≥0.9 | n_wrong 13~26 → 표본 부족(seed 43만 계산: conf 0.998, S2 0.997) |
| all | conf≥0.9 (n_wrong 74) | 0.991 / 1.0 | 0.991 | 0.991 | 0.990 / 1.0 |
| 3,5 | conf≥0.95 | k3 n_wrong 19 → 부족; k5 73: conf 0.978, S2 0.987 |
(층 내부 TPR@FPR은 그 층의 정답군으로 FPR을 잡은 in-stratum 값)

## 3. confidence 대비 S2의 증분 (`07_incremental_over_confidence.csv`)
| 층 | rank-average(conf,S2) AUROC − conf AUROC | conf@FPR5가 놓친 오답 중 S2@층내FPR5가 잡는 수 |
|---|---|---|
| ALL k3 | **−0.004** (S2 추가가 오히려 손해) | 5,497 중 1,021 (19%, 단 FPR은 최대 10%로 누적) |
| ALL k5 | −0.002 | 1,053 중 329 |
| conf≥0.9 k3 (3 seed) | **+0.016 / +0.016 / +0.016** | 36→35, 29→28, 32→28 |
| conf≥0.9 k5 (3 seed) | **+0.011 / +0.012 / +0.011** | 20→20, 21→21, 17→17 |
| conf≥0.9 k10, all | +0.001, 0.000 | 0 |

## 4. 고신뢰 오답 표 (`04_high_confidence_errors.csv`, 오답 ∧ conf≥0.9)
- **운영 임계값(ALL 정답군 FPR 5%로 잡은 S2 전역 임계)** 으로 S2가 경고한 비율: k3 19/157·13/153·15/155 (**~10%**), k5 83/152·90/142·71/137 (~55%), k10 13/13·26/26·19/19, all 74/74.
- 층 내부 FPR5 임계로는 k3 99%, k5 100% — 두 수치의 차이는 고신뢰 정답군의 S2가 매우 낮아 층 내부 임계가 훨씬 낮게 잡히기 때문. 실제 배포에선 전역 임계를 쓰므로 **k3 고신뢰 오답의 90%는 S2도 놓친다**.
- k3 고신뢰 오답 상위 쌍: Influenza→URTI 33, Pneumonia→Bronchitis 21, Influenza→Viral pharyngitis 14, HIV(initial)→URTI 8 — 노출 소견 4개로는 두 질환이 구분되지 않는 쌍. 가장 확신 높은 오답(Ebola→URTI 0.999, Myocarditis→PSVT 0.998)에서 S2는 음수(대안이 더 못 설명) → 정보 부족형 오류.

## 5. STRESS_ERROR (`05_stress_errors.csv`, NATURAL과 분리)
DDXPlus differential(full-evidence)에서 정답 아닌 최상위 후보를 working dx로 강제(123,608건) vs 정답을 working dx로 둔 경우(132,448건). baseline = 그 working dx에 대한 모델 확률.
| k | model_prob AUROC / TPR@FPR5 | S2 AUROC / TPR@FPR5 | Spearman(S2, −prob) |
|---|---|---|---|
| 3 | **0.995** / 0.96 | 0.989 / 0.93 | 0.979 |
| 5 | 0.999 / 0.99 | 0.997 / 0.97 | 0.975 |
| 10 | 1.000 | 0.999 | 0.955 |
→ 강한 대안이라도 부분 소견 위에선 모델·S2 모두 거의 완벽히 구분하고, S2가 앞서는 구간 없음. stress 오답 중 모델 확률≥0.9는 k3 52건뿐(진짜 "확신 있는 오답" 표본이 DDXPlus엔 거의 없음).

## 6. 상관 (`06_correlations.csv`, seed 42)
| 층 | Spearman(S2, −conf) | Pearson | Spearman(S2, entropy) |
|---|---|---|---|
| k3 ALL | **0.913** | 0.718 | 0.907 |
| k3 conf≥0.9 | 0.827 | 0.566 | 0.824 |
| k5 ALL / ≥0.9 | 0.886 / 0.840 | 0.589 / 0.445 | |
| k10 ALL / ≥0.9 | 0.744 / 0.692 | | |
| all ALL | 0.547 | 0.205 | 0.966 |

## 7. 두 질문에 대한 직접 답
**Q1. confidence가 이미 오류를 거의 완벽히 구분하는가?** 예에 가깝다. ALL 층에서 max-confidence가 모든 k·모든 지표에서 S2보다 높고(k3 AUROC 0.943 vs 0.917, TPR@FPR5 0.55 vs 0.34), S2를 rank-average로 섞어도 개선 없음(−0.004~−0.001). S2–confidence Spearman 0.91(k3)·0.89(k5).
**Q2. conf≥0.9 어려운 오답에서 S2가 추가 신호를 주는가?** 부분적으로 예. k3·k5의 conf≥0.9 층(오답 137~157/seed)에서 S2 AUROC가 conf보다 높고(0.978 vs 0.966, 0.983 vs 0.976), rank-average 증분 +0.011~+0.016이 3 seed 모두 같은 방향·같은 크기. 층 내부에선 S2가 오답의 99~100%를 FPR5로 잡는 반면 conf는 79~87%. **그러나** (a) 전역 운영 임계로는 k3 고신뢰 오답의 10%만 경고, (b) 이 층에서도 Spearman 0.83으로 여전히 강한 재표현, (c) STRESS 세트에선 모델 확률이 S2보다 우위, (d) k10·all 층은 표본 부족 또는 차이 0.

## 8. 판정 근거 (사전 임계값 없음, 실측 기반)
- C1_FAIL 아님: 고신뢰 층에서 seed-일관된 양의 증분(+0.011~0.016 AUROC, in-stratum TPR@FPR5 +0.13~0.20)이 있고 표본(≥137 양성 × 3 seed)이 통계적으로 무의미하지 않다.
- C1_PASS 아님: 전체 층에서는 S2가 confidence의 재표현(ρ 0.91, 결합 이득 없음)이고, 증분은 전체 오답의 1~3%에 해당하는 좁은 층에서만 나타나며 전역 임계로는 실현되지 않는다. STRESS에서도 우위 없음.
→ **C1_PARTIAL**. 현재 S2는 "단순 모델 불확실성 이상의 정보"를 **고신뢰 층에 한해 작게** 준다.

## 9. 다음 단계
C1_PARTIAL이므로 A′ 설계로 바로 가지 않고, 먼저 S2를 **confidence 조건부 신호**로 재정의하는 쪽이 맞다: (1) 고신뢰 층 전용 임계(또는 conf-조건부 캘리브레이션)로 운영 임계 문제를 해결하고, (2) 그 정의로 A′(83 적격 소견 제한 내부 NB)를 만든 뒤 실험 B와 동일 입력에서 비교. S2 자체의 정보 부족형 오류(Ebola→URTI 등)는 어떤 지식원으로도 못 잡는다는 점을 v5 §9 프레이밍 수정(M8)에 반영.

## 생성 파일
01_sample_table.csv(1,324,480행) · 02_confidence_strata.csv · 03_method_comparison.csv · 04_high_confidence_errors.csv · 05_stress_errors.csv(2,560,560행) · 06_correlations.csv · 07_incremental_over_confidence.csv · summary.json · c1_check.py
