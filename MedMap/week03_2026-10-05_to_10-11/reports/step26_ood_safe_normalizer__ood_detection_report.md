# STEP26 — OOD Detection + UNKNOWN Handling

- STEP26_RESULT = **REJECTION_POLICY_USEFUL** (5/5) · BEST_POLICY = **B4** {"a": 0.0, "b": 0.98, "s": 0.6} · EXTERNAL_GOLD_AVAILABLE = NO · CANONICAL_ACCURACY_VALIDATED = NO · GPU_USED = NO
- EXT 지표 = 외부 NER 범주 weak-label proxy(MedMap concept 정답 아님). REG = 합성 FIXED_REGRESSION_TEST(실제 환자 성능 아님). 둘을 합친 정확도는 없다.
- HELD_OUT_EXTERNAL_EVALUATION 은 STEP25 에서 전체 예측을 이미 본 데이터 → frozen retrospective evaluation(blind 아님). 임계값·정책은 DEV(외부 dev + STEP23 core dev 59)로만 선택.

## 1. 핵심 비교

| metric | Linear | Hybrid B | New B4 |
|---|---|---|---|
| Weak-negative auto-accept rate (EVAL) | 11.4% | 21.7% | 0.5% |
| Weak-symptom auto-accept rate (EVAL) | 31.1% | 60.5% | 17.3% |
| Disagreement auto-accept count (EVAL) | 171 | 428 | 0 |
| Regression auto-accept precision | 98.6% | 95.0% | 100.0% |
| Regression auto-accept coverage | 66.1% | 90.8% | 37.6% |
| Unknown(=not auto) rate (EVAL) | 87.0% | 76.6% | 98.0% |
| CPU p95 latency (ms) | 0.366 | 10.025 | 16.773 |

판정 기준 값: {"C1_WN_rel_reduction": 0.9747, "C2_reg_precision": 1.0, "C3_reg_coverage": 0.3761, "C4_disagree_rel_reduction": 1.0, "C5_p95_ms": 16.773} · 통과 {"C1": true, "C2": true, "C3": true, "C4": true, "C5": true}

## 2. 정책 전체(HELD_OUT·REG 는 보고 전용, 선택은 DEV CV)

| policy | is_best | DEV_CV_WN_auto | DEV_CV_core_prec | DEV_CV_core_cov | EVAL_WN_auto_rate | EVAL_WS_auto_rate | EVAL_MIXED_auto_rate | EVAL_disagree_auto | REG_auto_precision | REG_auto_coverage | KMC_auto_rate | params |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| LINEAR_ONLY | False |  |  |  | 0.1141 | 0.3105 | 0.1135 | 171 | 0.9861 | 0.6606 | 0.1073 | frozen |
| HYBRID_B | False |  |  |  | 0.2171 | 0.6048 | 0.1943 | 428 | 0.9495 | 0.9083 | 0.3292 | frozen |
| B1 | False | 0.0265 | 1.0 | 0.4068 | 0.031 | 0.1734 | 0.0208 | 21 | 1.0 | 0.3578 | 0.0012 | {"t": 1.05} |
| B2 | False | 0.1164 | 0.9545 | 0.7458 | 0.1163 | 0.371 | 0.1052 | 0 | 0.9467 | 0.6881 | 0.0107 | {} |
| B3 | False | 0.0201 | 1.0 | 0.4237 | 0.0166 | 0.1774 | 0.0115 | 0 | 1.0 | 0.3303 | 0.0012 | {"a": 1.0, "b": 0.98} |
| B4 | True | 0.0021 | 0.9667 | 0.5085 | 0.0055 | 0.1734 | 0.0078 | 0 | 1.0 | 0.3761 | 0.0 | {"a": 0.0, "b": 0.98, "s": 0.6} |
| LIGHTWEIGHT_GATE | False | 0.0042 | 0.925 | 0.678 | 0.0044 | 0.1774 | 0.0094 | 4 | 0.9103 | 0.7156 | 0.0239 | {"th": 0.95} |

LIGHTWEIGHT_GATE 승격 = False(DEV CV 에서 core precision < 0.95 → feasible 아님). 규칙: policy_lib 문서열.

## 3. 상태 분포 (KNOWN / UNCERTAIN / UNKNOWN / NON)

| set | weak_label | n | KNOWN_SYMPTOM | UNCERTAIN | UNKNOWN_SYMPTOM | NON_SYMPTOM | known_correct(internal only) |
|---|---|---|---|---|---|---|---|
| EXT_DEV | WEAK_MIXED | 2064 | 28 | 862 | 206 | 968 |  |
| EXT_DEV | WEAK_NON_SYMPTOM | 945 | 1 | 48 | 0 | 896 |  |
| EXT_DEV | WEAK_SYMPTOM | 179 | 10 | 60 | 109 | 0 |  |
| EXT_EVAL | WEAK_MIXED | 1920 | 15 | 858 | 198 | 849 |  |
| EXT_EVAL | WEAK_NON_SYMPTOM | 903 | 5 | 403 | 11 | 484 |  |
| EXT_EVAL | WEAK_SYMPTOM | 248 | 43 | 136 | 43 | 26 |  |
| INT_DEV_CORE | - | 59 | 30 | 23 | 6 | 0 | 29 |
| INT_REGRESSION_CORE | - | 109 | 41 | 50 | 18 | 0 | 41 |
| KMC_COMPLEX_STRESS | - | 1677 | 0 | 1654 | 23 | 0 |  |

NON_SYMPTOM 임계값 T_non = 0.65(EXT_DEV CV weak precision ≥ 0.95, core dev NON 률 ≤ 5% 인 최소값). EXT_DEV 상태는 학습에 쓴 데이터라 in-sample.

- HELD_OUT weak-symptom 248 중 NON_SYMPTOM 26 → 증상 표현이 '증상 아님'으로 빠지는 손해(원문은 보존).
- HELD_OUT weak-non-symptom 903 중 NON 484 · UNCERTAIN 403 · UNKNOWN 11 · 자동 수락 5.
- REG 109: KNOWN 41(정답 41) · UNCERTAIN 50 · UNKNOWN 18 · NON 0.

## 4. 우선 점검 사례 (외부 데이터에 실제 존재)

| kind | text | weak_label | linear | koelectra | hybrid_b | new_auto | status | candidates |
|---|---|---|---|---|---|---|---|---|
| TERM:고혈압 | 고혈압 | WEAK_MIXED | decreased_appetite | hemoptysis | hemoptysis (auto) | False | NON_SYMPTOM |  |
| TERM:결핵 | 결핵 | WEAK_MIXED | decreased_appetite | loc | loc | False | NON_SYMPTOM |  |
| TERM:코피 | 코피가 | WEAK_SYMPTOM | hemoptysis | hemoptysis | hemoptysis (auto) | False | UNCERTAIN | hemoptysis;hematemesis;EV:E_112 |
| TERM:호흡곤란 | 호흡곤란이 | WEAK_SYMPTOM | dyspnea | dyspnea | dyspnea (auto) | True | KNOWN_SYMPTOM | dyspnea |
| TERM:기침 | 기침을 | WEAK_SYMPTOM | cough | cough | cough (auto) | True | KNOWN_SYMPTOM | cough |
| TERM:발열 | 발열의 | WEAK_SYMPTOM | decreased_appetite | fever | fever (auto) | False | UNKNOWN_SYMPTOM |  |
| TERM:오심 | 오심 | WEAK_SYMPTOM | decreased_appetite | nausea | nausea (auto) | False | UNCERTAIN |  |
| TERM:구토 | 구토 | WEAK_SYMPTOM | nausea | vomiting | vomiting (auto) | False | UNKNOWN_SYMPTOM |  |
| BODY_PART_ALONE(BD) | 눈 | WEAK_NON_SYMPTOM | decreased_appetite | EV:E_129 | EV:E_129 | False | UNCERTAIN |  |
| BODY_PART_ALONE(BD) | 뼈 | WEAK_NON_SYMPTOM | decreased_appetite | limb_weakness | limb_weakness | False | UNCERTAIN |  |
| BODY_PART_ALONE(BD) | 귀 | WEAK_NON_SYMPTOM | decreased_appetite | EV:E_157 | EV:E_157 | False | UNCERTAIN |  |
| BODY_PART_ALONE(Body) | 눈 | WEAK_NON_SYMPTOM | decreased_appetite | EV:E_129 | EV:E_129 | False | UNCERTAIN |  |
| BODY_PART_ALONE(Body) | 혈관 | WEAK_NON_SYMPTOM | decreased_appetite | sore_throat | sore_throat (auto) | False | NON_SYMPTOM |  |
| BODY_PART_ALONE(Body) | 신장 | WEAK_NON_SYMPTOM | decreased_appetite | EV:E_93 | EV:E_93 | False | NON_SYMPTOM |  |
| TREATMENT_ALONE(Treatment) | 수술 | WEAK_NON_SYMPTOM | decreased_appetite | pain | pain | False | NON_SYMPTOM |  |
| TREATMENT_ALONE(Treatment) | 약물 치료 | WEAK_NON_SYMPTOM | diarrhea | hematemesis | hematemesis | False | NON_SYMPTOM |  |
| TREATMENT_ALONE(Treatment) | 전립선 | WEAK_NON_SYMPTOM | decreased_appetite | pain | pain | False | NON_SYMPTOM |  |

## 5. Illustrative smoke (데이터에 없는 예시 — 지표·조정에 미사용)

| input | existing_hybrid_b | new_status | candidates | reason |
|---|---|---|---|---|
| 숨이 차요 | dyspnea (auto) | KNOWN_SYMPTOM | dyspnea | B4 |
| 코피가 나요 | hemoptysis (confirm) | UNCERTAIN | hemoptysis;hematemesis;cough | AGREE_LOW_CONFIDENCE |
| 고혈압 | hemoptysis (auto) | NON_SYMPTOM |  | NON_SYMPTOM_SCORE |
| 몸이 좀 이상해요 | fatigue (confirm) | UNKNOWN_SYMPTOM |  | DISAGREE_SYMPTOM_LIKE |

## 6. 속도·자원

```json
{
 "single_message_cpu": {
  "LINEAR_ONLY": {
   "n": 409,
   "mean_ms": 0.274,
   "p50_ms": 0.255,
   "p95_ms": 0.366,
   "max_ms": 0.59
  },
  "HYBRID_B": {
   "n": 409,
   "mean_ms": 4.532,
   "p50_ms": 5.016,
   "p95_ms": 10.025,
   "max_ms": 18.107
  },
  "SAFE_NORMALIZER_B4": {
   "n": 409,
   "mean_ms": 11.229,
   "p50_ms": 10.538,
   "p95_ms": 16.773,
   "max_ms": 24.819
  }
 },
 "n_inputs": 409,
 "koe_call_rate": {
  "HYBRID_B": 0.6528,
  "SAFE_NORMALIZER": 0.9584,
  "LINEAR_ONLY": 0.0
 },
 "peak_rss_mib": 800.4,
 "status_consistency_with_predictions_csv": "PASS(0 mismatch)",
 "note": "SAFE_NORMALIZER 는 COMPLEX 가 아니면 항상 KoE 실행(B2–B4 는 동의 판정 필요) + 학습 표현 1,119개와 difflib 유사도 계산 포함"
}
```

## 7. 데이터·누수

```json
{
 "n_units": 6305,
 "n_clusters": 4692,
 "weak_label_counts": {
  "WEAK_SYMPTOM": 439,
  "WEAK_NON_SYMPTOM": 1848,
  "WEAK_CONFLICT": 16,
  "WEAK_MIXED": 4002
 },
 "split_counts": {
  "HELD_OUT_EXTERNAL_EVALUATION|WEAK_SYMPTOM": 248,
  "DEVELOPMENT|WEAK_SYMPTOM": 179,
  "DEVELOPMENT|WEAK_NON_SYMPTOM": 945,
  "HELD_OUT_EXTERNAL_EVALUATION|WEAK_NON_SYMPTOM": 903,
  "DEVELOPMENT|WEAK_MIXED": 2064,
  "HELD_OUT_EXTERNAL_EVALUATION|WEAK_MIXED": 1920
 },
 "train_exact_excluded": 31,
 "gold_exact": 0,
 "conflict_excluded": 16,
 "eval_units_near_dup_ge_0.80_to_dev_same_block": 0,
 "nerko_docs_spanning_both_splits": 379,
 "nerko_docs": 525,
 "note": "cross-split near-dup 는 같은 앞 2글자 block 안에서만 검사(clustering 과 같은 범위)",
 "internal_rows": {
  "EXT_EVAL": 3071,
  "EXT_DEV": 3188,
  "INT_DEV_CORE": 59,
  "INT_REGRESSION_CORE": 109,
  "KMC_COMPLEX_STRESS": 1677
 }
}
```

## 8. 검증되지 않은 위험

- canonical 정확도: 외부 Gold 0 → 자동 수락된 외부 표현이 맞는 concept 인지 미확인.
- 미지원 증상의 확인 후보가 틀릴 수 있음: '코피가' → 자동 수락은 막혔지만 확인 후보가 객혈·토혈(77 에 비출혈 concept 없음).
- weak label 잡음: KBMC Treatment 에 '전립선' 같은 신체 부위가 섞이는 등 annotation 자체 오류 존재.
- 지원 증상 손실: REG 자동 수락 coverage 90.8%(Hybrid B) → 정책 값으로 감소, 나머지는 확인 질문으로 넘어감(UX 부담).
- COMPLEX 판정은 정규식 규칙(부정·과거·타인·연결어·40자) — 누락·과잉 판정 미검증.
