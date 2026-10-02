# STEP 13B — 외부 verifier B 사전등록 → TEST 1회 평가 (2026-09-21)

## 판정: **STEP13B_NO_GO**

사전등록 파일(SHA256): `00_SCORER_PREREGISTRATION.md` df64bebb…, `00_preregistered_generic_findings.csv` 1402a37d…, `00_preregistered_rules.json` 31ca3f3c… — TEST 열람 전 고정, 이후 점수식·임계·generic·subset 무변경. TEST 실행 1회(`14_test_once_audit.json`). Step 8~13 무수정.

## 1. 사전등록 규칙 요약
- relation_score ∈ {+1 positive, 0 unknown(open-world, **negative 아님, ε 없음**), −1 explicit NOT(HPO NOT·DisMech EXCLUDED)} — 실제 −1 관계: **0건**(positive와 겹치거나 없음)
- support(d,p) = Σ rel(d,f)/|evaluable(p)|, evaluable = 관찰 COMMON finding 중 KB에 어떤 질환과든 관계가 있는 것; 0이면 KNOWLEDGE_UNAVAILABLE(보존)
- B = max_alt support(alt) − support(wd), 후보 = 49질환(A′와 동일). source 수·TF-IDF·빈도 미사용
- B_STRICT 관계행렬(49×83): +544, 질환 32, finding 57 / B_LENIENT: +1,007, 질환 40. `00b_relation_matrix_nonzero.csv`, 계보 `13_source_genealogy.csv`
- CONCEPT_COLLISION = 동일 외부 ID 공유 → **0쌍**(급성/만성 부비동염은 둘 다 FAIL이라 collision이 아니라 both_unknown)
- 임계: VALIDATION 정답군 quantile(FPR 5/10/20%), TEST 무조정. Primary endpoint: sens@FPR10(ALL) + conf≥0.9 AUROC

## 2. 공통 입력 검증 (`01_common_input_audit.csv`)
A′·B 동일 sample_id·config·노출 COMMON finding·wd·정답·후보 49 — assert 통과. 환자당 evaluable finding(k3): 0개 24,037 / 1개 70,070 / 2개 32,368 / 3+ 8,054 → **B는 대부분 0~2개 소견으로 판단**, 점수는 {−1, 0, 0.5, 1} 근처의 이산값.

## 3. Primary (TEST, k3 seed 42; seed 43/44 동일 방향)
| 지표 (ALL 49질환) | REF conf | REF margin | A′ | B_STRICT | B_LENIENT |
|---|---|---|---|---|---|
| AUROC | **0.943** | 0.943 | 0.662 | **0.478** | 0.500 |
| AUPRC (base 0.089) | 0.542 | 0.518 | 0.135 | 0.094 | 0.092 |
| sens@FPR10 (val 임계) | 0.797 | 0.803 | 0.189 | **0.000** | 0.000 |
| sens@FPR5 | 0.551 | 0.548 | 0.083 | 0.000 | 0.000 |
| 오답 중 미채점(KNOWLEDGE_UNAVAILABLE) | 0 | 0 | 0 | 1,422 | 991 |
- B의 sens 0.000은 임계 퇴화: VALIDATION 정답군의 90% 분위가 최대값 1.0이라 어떤 표본도 넘지 못함(이산 점수). 임계 무관 지표인 AUROC 0.478은 **우연 이하** — 오답군 B 평균 0.418 vs 정답군 0.455로 방향이 반대.
- seed 3개 k3: A′ 0.662/0.668/0.666, B_STRICT 0.478/0.480/0.483. 전 config 평균: REF 0.969, A′ 0.701, B_STRICT 0.516.
- generic 제외 민감도(B_STRICT): AUROC 0.498, 미채점 5,720으로 증가.

## 4. 고확신 오답 (confidence ≥ 0.9, TEST, `08_confidence_strata.csv`)
| config | n_wrong | reachable | REF AUROC [CI] | A′ [CI] | B_STRICT [CI] |
|---|---|---|---|---|---|
| k3 s42 | 153 (전체 오답의 1.3%) | 41 | 0.961 [0.954–0.968] | 0.651 [0.617–0.682] | 0.568 [0.521–0.610] |
| k3 s43/s44 | 133 / 150 | 29 / 30 | 0.966 / 0.965 | 0.628 / 0.647 | 0.626 / 0.610 |
| k5 s42/43/44 | 143 / 145 / 144 | 36~37 | 0.972 | 0.72 / 0.69 / 0.68 | 0.59 / 0.57 / 0.59 |
| k10 | 18~29 | 12~13 | 표본 부족(s43: REF 0.996, A′ 0.726, B 0.425) | | |
| all | 61 | 43 | 0.993 | 0.762 | 0.439 |
STEP12에서 S2(전체 evidence)가 이 층에서 REF를 앞섰던(0.978 vs 0.966) 신호가 **COMMON 83개로 제한하자 사라짐**(A′ 0.63~0.72).

## 5. Reachability (`09_reachable_analysis.csv`, k3 s42)
- 전체 오답 12,040 / reachable **2,801 (ceiling 23.3%)** / unreachable 9,239 = both_unknown 2,651 + wd_unknown 2,237 + truth_unknown 3,881 + patient_knowledge_unavailable 470 / collision 0
- 외부지식 0 질환 관여 오답 8,769 (72.8%)
- B overall recall 0.000, reachable recall 0.000 (임계 퇴화); reachable subset AUROC 0.446 — reachable 안에서도 정보 없음
- 전 config reachable ceiling 11~27%

## 6. 상관 (`11_score_correlations.csv`, k3 s42)
REF↔A′ 0.437 (ALL) / 0.405 (≥0.9) · REF↔B_STRICT 0.026 / 0.070 · A′↔B_STRICT 0.065 / 0.101 · REF↔B_LENIENT 0.082. → B는 REF와 독립적이지만 **오답과도 무관**한 신호.

## 7. 증분 가치 (`12_incremental_value.csv`, z-결합 VALIDATION 고정)
| subset | REF only AUROC | REF+A′ | REF+B_STRICT |
|---|---|---|---|
| ALL k3 | 0.943 | 0.943 | **0.864 (악화)** |
| ≥0.9 k3 | 0.961 | 0.947 | 0.742 (악화) |

## 8. 오답쌍 (`10_error_pair_analysis.csv`, k3 s42 상위)
| 정답 → working dx | n | 평균 conf | reachable | A′ 탐지 | B 탐지 | B 판단불가 | 이유 |
|---|---|---|---|---|---|---|---|
| Acute → Chronic rhinosinusitis | 1,268 | 0.63 | 0 | 80 | 0 | 409 | 둘 다 외부지식 없음(both_unknown) |
| Acute laryngitis → Viral pharyngitis | 1,182 | 0.62 | 0 | 557 | 0 | 0 | wd(Pharyngitis 상위개념) strict 없음 |
| Unstable → Stable angina | 1,072 | 0.53 | 851 | 165 | 0 | 221 | reachable이나 공통 소견(Pain·Dyspnea·Triggered by exertion)이 두 질환 모두에 +1 |
| NSTEMI/STEMI → Stable angina | 602 | 0.42 | 0 | 132 | 0 | 0 | truth strict 없음 |
| Unstable angina → NSTEMI/STEMI | 409 | 0.54 | 0 | 0 | 0 | 97 | |
| URTI → Viral pharyngitis | 399 | 0.53 | 0 | 129 | 0 | 0 | |
| Viral pharyngitis → Acute otitis media | 338 | 0.39 | 0 | 193 | 0 | 0 | |
감사에서 지목된 3쌍(급/만성 부비동염, 후두염/인두염, 안정/불안정 협심증) 전부 상위 3위로 실재하며, 외부지식으로는 하나도 판별 불가.

## 9. 판정 근거 (질문별)
1. **B가 REF보다 추가 가치?** 아니오. AUROC 0.478(우연 이하), 결합 시 REF 성능 악화, 상관 0.03.
2. **conf≥0.9 오답에서 신호?** 아니오. B 0.57~0.63 [CI 하한 0.52], A′ 0.63~0.72 — 둘 다 REF(0.96)에 크게 못 미침.
3. **동일 입력에서 외부지식 유효?** 아니오. 같은 83 finding으로 내부 통계(A′)도 0.66~0.80에 그치고, 외부는 그보다 낮음. STEP5-7의 S2 0.917은 COMMON 밖 정보(통증 부위·강도 값, 과거력 113개, HPO 없는 증상 14개)에 의존했음이 드러남.
4. **원리적 도달 가능 비율?** 오답의 22~27%(all은 11%).
5. **collision/coverage로 못 잡는 오류?** 외부지식 0 질환 관여 오답 73%, 상위 오답쌍 전부 unreachable. 동일 ID collision은 0이지만 "둘 다 FAIL"·"상위개념 매핑"이 같은 효과.

→ **STEP13B_NO_GO**. 현재 외부지식(HPO+OKG+HSDN+DisMech+MEDLINE+Wikidata+UMLS strict)과 이진 open-world 점수식으로는 working diagnosis 오류 탐지 신호가 없다. 실패 주원인은 verifier 식 이전에 (a) 외부지식 coverage(reachable 23%), (b) 공통 입력의 정보량(환자당 evaluable 0~2개), (c) 상위 오답쌍이 외부 개념 수준에서 동일/미보유.

## 10. 한계
- B 임계 퇴화(이산 점수)로 sens@FPR 지표는 정보 없음 → AUROC로 판단.
- generic finding 포함이 Primary(사전 결정); 제외 민감도도 0.498.
- B_LENIENT도 0.50 → strict/lenient 차이 없음.
- 기본 진단모델이 의사 역할 대체(§0). 오답 라벨은 여전히 모델 저신뢰 사례 위주(STEP12 C1).

## 11. 생성 파일
00_SCORER_PREREGISTRATION.md · 00_preregistered_generic_findings.csv · 00_preregistered_rules.json · 00b_relation_matrix_nonzero.csv · 01_common_input_audit.csv · 02/03(validation 점수) · 04_validation_thresholds.json · 04b_validation_zparams.json · 05/06(test 점수) · 07_overall_metrics.csv · 08_confidence_strata.csv · 09_reachable_analysis.csv · 10_error_pair_analysis.csv · 11_score_correlations.csv · 12_incremental_value.csv · 13_source_genealogy.csv · 14_test_once_audit.json · step13b_run.py
