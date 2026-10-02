# STEP13B 외부 지식 verifier NO_GO — 원인 정리와 최소 Safety Net 실험에서 바꿀 점

- 작성 2026-10-02 · 상태: 연구 문서(Phase 3) · 근거는 모두 기존 산출물 인용, 새 계산 없음
- 원문: `exp/step13b_external_verifier/STEP13B_REPORT.md`(이하 R), `00_SCORER_PREREGISTRATION.md`, `10_error_pair_analysis.csv`,
  `exp/step13_aprime/STEP13_APRIME_REPORT.md`, `exp/step12_high_confidence_error/STEP12_C1_REPORT.md`, `exp/step14*/STEP14_REPORT.md`,
  `exp/step15_v2_evaluation_fix/STEP15V2_EVALUATION_FIX_REPORT.md`, `.claude/memory/rg-audit-2026-09-21.md`

## 1. STEP13B가 실제로 검증한 것

| 항목 | 내용 |
|---|---|
| "Working diagnosis" | 의사가 아니라 **진단 모델(Step2+3 LR)의 top1**. 입력 = INITIAL + 무작위 k개 evidence(k∈{3,5,10,all}) |
| "틀린 WD" | 모델 top1 ≠ DDXPlus 정답. 혼동 쌍을 의도적으로 고른 WD 아님 |
| 표현 | COMMON 이진 finding 83개, 관계 +1 / 0(알 수 없음) / −1(명시적 NOT, 실제 0건). support = Σrel/평가가능 수, B = max_alt support − support(WD) |
| 지식원(strict) | HPO/OptimusKG · HSDN(공출현≥2) · DisMech(PMID) · MEDLINE · Wikidata(참조) · UMLS → 49×83 행렬, +544, 지식 있는 질환 32 |
| 평가 | 임계는 VALIDATION 정답군 분위수, TEST 1회 |

## 2. 결과 (R §3·§6·§7, TEST k3 seed42)

| 지표 | 값 |
|---|---|
| B_STRICT AUROC | **0.478**(우연 이하) · B_LENIENT 0.500 |
| 기준선 REF(모델 확신도) AUROC | **0.943** |
| sens@FPR10 (B) | 0.000 — 이산 점수로 임계가 1.0에 퇴화 |
| REF + B 결합 | **0.864**(REF 단독보다 악화) |
| 판정 가능 오답(reachable) 상한 | **23.3 %**(2,801 / 12,040) |
| 외부지식 0 질환이 관여한 오답 | 72.8 % |
| B 평균(오답군 vs 정답군) | 0.418 vs 0.455 — 방향 반대 |

## 3. 실패 원인 (문서화된 것만)

1. **지식 coverage**: strict 지식 질환 32/49. 상위 오답쌍 대부분이 한쪽 또는 양쪽 지식 없음(both_unknown 2,651, wd_unknown 2,237, truth_unknown 3,881).
2. **환자당 평가 가능한 소견 0~2개**: 이진 COMMON 83개만 사용 → 통증 부위·강도 값, 과거력 등 판별 정보 탈락(STEP14: FINDING_ONLY 0.668 → +LOCATION 0.749).
3. **공통 소견 상쇄**: 질환 존재 여부 점수라 두 질환에 모두 +1인 소견이 차이를 지움. 예: 불안정 → 안정형 협심증 1,072건은 reachable 851건이지만 B 탐지 0(Pain·Dyspnea·Triggered by exertion 양쪽 +1, R §8).
4. **DDXPlus에 없는 판별 정보**: 기간·발병·경과·검사(판별 feature 13개 중 관측 가능 8개, STEP15V2 evaluation fix).
5. **개념 매핑**: 상위개념 매핑(Pharyngitis)·"양쪽 FAIL"이 collision과 같은 효과.
6. **기준선 대비 증분 부재**: 모델 확신도(REF)가 이미 0.943 — 외부 점수는 증분이 없고 결합 시 악화.
7. **오답 표본 성격**: 오답 대부분이 모델 저확신 사례(STEP12 C1, k3 오답 확신도 중앙 0.551) — 고확신 오답은 1.3 %.

## 4. 혼동하면 안 되는 다른 결과

| 결과 | 실제 의미 | 아닌 것 |
|---|---|---|
| 실험 A S2 AUROC 0.917 | 같은 TRAIN의 NB가 LR top1과 다른지(모델 간 일치도, RG C2) | 외부 지식 탐지 상한 |
| STEP16B IG GO(1Q 0.459 vs RANDOM 0.053) | 합성 환자 내부 holdout에서 **모델 top1 오답이 IG 질문 답 공개 후 정답으로 회복된 비율** | 의사 WD 오류 탐지·외부·임상 검증 |
| STEP13B NO_GO | 외부 지식 + 이진 open-world 점수로 **모델 top1 오답** 탐지 신호 없음 | "외부 지식은 영원히 무용" (coverage·표현 문제로 미검증) |

## 5. 이번 최소 실험에서 다르게 할 것

| # | STEP13B | 이번 설계 |
|---|---|---|
| D1 | 49질환 전체, 지식 coverage 32/49 | **흉통군 8질환으로 닫힌 범위**, 그룹 밖 오류는 별도 층으로 보고 |
| D2 | reachable 비율을 사후에 앎(23 %) | **판정 가능 비율을 평가 전(학습 split)에 계산하고 GO 조건으로 사전등록** |
| D3 | 질환 존재 여부 점수(공통 소견 상쇄) | **쌍 판별 소견만**(WD vs 대안에서 방향이 다른 소견) + 충돌·중요 음성 역할 분리 |
| D4 | 이진 COMMON 83개 | 값·부위·유발·완화·경과 문항(E_54~E_59, E_218, E_14, E_13, E_33, E_220 등) 포함 |
| D5 | WD = 모델 top1 오답(저확신 위주) | **Correct WD = 정답 / Plausible wrong WD = 같은 군의 혼동 대안**(사전 고정 쌍 + 재학습 모델 2·3위) |
| D6 | 기준선(REF) 대비 증분 미설정 → 결합 악화 | **B0(모델 top1≠WD)·B1(WD 확률·순위) 대비 증분이 1차 endpoint**, 결합 악화 = NO_GO |
| D7 | 이산 점수로 FPR 임계 퇴화 | 학습 split에서 점수 분포·임계 퇴화 여부를 먼저 확인(퇴화 시 중단) |
| D8 | 소진된 TEST 사용 | **STEP17A DEV 안에서 새 split + 같은 레시피 재학습, 평가 1회** |
| D9 | 결과 표현 미구분 | "합성 환자·검수 전 외부 지식·시뮬레이션 WD" 범위로만 기술, 의사 오진 일반화 금지 |
