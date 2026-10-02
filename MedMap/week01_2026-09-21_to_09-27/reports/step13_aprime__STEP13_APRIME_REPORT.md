# STEP 13 — A′ 공정 비교: 준비 단계 완료, 평가 **중단** (2026-09-21)

## 판정: **B_SCORER_NOT_PREREGISTERED**

§8 게이트에서 중단. 외부지식 verifier(B)의 점수식이 프로젝트 문서·코드 어디에도 사전 정의되어 있지 않다:
- v5 §9는 "현재 진단에서의 소견 가능성 vs 대안 진단에서의 소견 가능성 비교", "확률이 없는 KG에서는 연결 정도·정보량·부정 관계·관련성 점수 등을 이용"이라는 **개념 서술**뿐, 식·부재 edge 처리·최소 공출현·source 가중이 없다.
- STEP10 보고 §6 "최소 공출현 기준 필요", Reviewer#2 M5 "외부지식→P(f|d) 대체 규칙 미정", STEP11 FINAL도 규칙을 정하지 않았다.
- 따라서 §9 이후(성능·층별·증분·reachable recall·pair 분석)는 **TEST를 보기 전에** 점수식을 사전등록한 뒤에만 진행한다. TEST 성능은 이 단계에서 일절 계산·열람하지 않았다(코호트 생성 시 오답 라벨 건수만 로그에 남음).

## 역할 정의 (§0)
제품 구조는 의사 → working diagnosis → MedMap verifier. DDXPlus엔 의사의 working diagnosis가 없어 **기본 진단모델(Step 2+3 LR)이 의사 역할을 대체**하며, 기본 모델은 제품의 최종 기능이 아니다. 새 기본모델 학습 없음(기존 model.pkl 추론만).

## 사전 지정 PRIMARY / SECONDARY (§17, TEST 열람 전 고정)
- **Primary**: TEST, confidence ≥ 0.9 subset, wrong-diagnosis detection AUROC — REF(max confidence) vs A′
- **Secondary**: REF vs B_STRICT(같은 subset); TPR@FPR5(임계는 VALIDATION에서 고정)·AUPRC·reachable recall; 층 ALL/≥0.8/≥0.9/≥0.95; 전체 49질환 → EXTERNAL_REACHABLE → coverage 보유 subset 순으로 보고
- 결합 방법: STEP12에서 쓴 rank-average(REF, verifier)만 재사용, 새 결합 모델 학습 없음

## 완료한 것 (§1~§7)
| 항목 | 결과 |
|---|---|
| Ground truth | DDXPlus PATHOLOGY만. evidence_semantics.tsv·concept map은 외부 ontology 연결 보조로만 사용 |
| Split | TRAIN(1,025,602) → 내부 질환-finding 통계(`cond_token_logp.npz`, Step 5 train 전용) / VALIDATION(132,448) → 임계 결정용 / TEST(134,529) → 최종 평가용(미열람). 기존 build_working_dx.py의 seed·partial view 규칙 그대로 복원(validate 저장본과 working dx 일치 assert 통과) |
| COMMON_FINDINGS | `03_evidence_eligibility.csv`에서 재계산 **83개**(전부 binary evidence → 토큰 83). 값-수준(통증 부위·강도)·modifier·과거력은 두 verifier 모두 못 봄 |
| 01_common_input_cohort.csv | 2,669,770행 (validate 10 config + test 10 config). sample_id·pathology·working dx·confidence·margin·entropy·노출 evidence·노출 COMMON finding·개수·외부 coverage 플래그(strict/lenient, wd 및 truth). DDXPlus엔 음성 소견이 없어 n_negative_findings=0 |
| 02_aprime_internal_scores.csv | A′ = 기존 S2 식(max_{d'} Σ_f log P(f|d') − Σ_f log P(f|d))을 **COMMON 토큰만**으로 계산. 누수 테스트: 비-COMMON 토큰(E_79/E_104/E_44)을 뷰에 추가해도 A′ 불변 ✔. NaN/inf 0 |
| 02b_external_input_fixed.csv | STEP11 FINAL `08b_coverage_detail_final.csv`의 (질환, evidence) 165쌍(lenient) / 118쌍(strict), source·family·strict 플래그 보존. 질환 coverage: strict 30/49, lenient 38/49. **02b_external_scores.csv는 점수식 미등록으로 미생성** |

**입력의 얇음(중요)**: 노출 evidence 중 COMMON에 드는 것이 평균 k3 1.54개 / k5 1.94 / k10 2.79 / all 4.45개. 두 verifier가 실제로 보는 정보는 환자당 1~4개 binary 소견이다. 이는 공정 비교의 대가이며, A′ 성능 하락의 예상 원인으로 미리 기록한다.

## 제안: B 점수식 사전등록 초안 (승인 후에만 §9 진행, TEST 열람 전)
1. **B_STRICT 지식**: `02b_external_input_fixed.csv`의 `sources_strict≠""`인 (질환, finding) 쌍만 사용. 관계 존재 = 1, 부재 = 0 (빈도·TF-IDF·공출현 값은 **쓰지 않음** — 의미가 source마다 달라 합산 불가).
2. **점수**: 기존 S2와 같은 우도비 형태를 유지하되 확률 대신 고정 pseudo-log-likelihood: 관계 있음 log(1−ε), 없음 log(ε), **ε = 0.05 고정**(튜닝 금지). B = max_{d'≠d, d'∈외부지식 보유 질환} Σ_f [ℓ(f|d') − ℓ(f|d)].
3. **외부지식 없는 질환**이 working dx 또는 대안이면 B는 계산 불가 → 해당 오답은 EXTERNAL_UNREACHABLE로 표기(삭제 금지), reachable recall 분모·분자 분리 보고.
4. **CONCEPT_COLLISION**: STEP11 매핑에서 두 질환이 같은 외부 개념 또는 상위개념(PARTIAL/AMBIGUOUS로 표시된 상위개념 연결)으로 합쳐진 쌍은 STEP10 `01_hsdn_disease_map.csv`·STEP11 `02/04` map의 status·name으로 결정(사람/LLM 신규 라벨 없음).
5. **generic**: STEP9 `too_generic_flag` evidence는 두 verifier에서 동일하게 **포함**(사전 결정; strict 민감도로 제외 결과 병기).
6. **임계값**: TPR@FPR5/10의 임계는 VALIDATION 정답군에서 고정, TEST 재조정 금지. seed 3개 전부 보고.
7. **B_LENIENT**: 동일 식에 `sources_lenient` 쌍 사용, 보조 결과.

이 초안이 승인되면 그대로 코드화해 §9~§16을 실행한다. 승인 전에는 TEST 지표를 계산하지 않는다.

## 품질 검증 (§19, 이 단계 범위)
COMMON_FINDINGS 83 ✔ · A′와 B 입력 동일 집합(83 evidence) ✔ · 내부 통계 TRAIN 전용 ✔ · TEST 임계 튜닝 없음(평가 자체 미실시) ✔ · LLM 매핑 ground truth 미사용 ✔ · NaN/inf 0 ✔ · config 10개 × 2 split 행수 일치 ✔ · Step 8~12 무수정 ✔

## 생성 파일
`01_common_input_cohort.csv`, `02_aprime_internal_scores.csv`, `02b_external_input_fixed.csv`, `10_summary.json`, `step13_prepare.py`. 03~09는 사전등록 후 생성 예정.
