# EXP-01 사전 설계: 증상 루트 트리 vs 관계 그래프 (DDXPlus)

상태: **rev1 (2026-10-26) — RG manifest `EXP-MAI-001` 로 등록. 정본은 manifest, 이 문서는 배경.** 실행 0.
> **2026-10-26 gate 1 = NEEDS_FIX → manifest rev2 로 수정.** 이 문서의 §2 모델 정의(PB "조건 가지치기", PC WD 조건, 지표·통계)는
> rev2 에서 바뀌었다(PB = 사후확률 비율 기반 확인 질문 우선순위 하향, Holm m=6 단측, 미기록 검사 재정의 등).
> 충돌 시 `.research-guardian/experiments/EXP-MAI-001/manifest.yaml` 이 우선. 심사 원문: `.research-guardian/audits/EXP-MAI-001/gate/`.

### rev1 정정(설계 심사 중 발견한 결함과 수정)
| # | 결함(rev0) | 수정(rev1) | 검증 |
|---|---|---|---|
| R1 | WD_PLAUSIBLE_WRONG 을 DIFFERENTIAL_DIAGNOSIS 로 생성 → 시뮬레이터 감별 정보가 모델 입력(WD)으로 새어 들어감 | WD 생성에 DIFFERENTIAL 사용 금지. `WD_MODEL`(Baseline A 초기 상태 top-1) · `WD_MODEL_WRONG`(Baseline A 순위 중 정답이 아닌 최상위) · `WD_CORRECT` · `WD_RANDOM_WRONG`. PATHOLOGY 는 "오답 조건" 층 구분에만 사용 | manifest 누출 항목 |
| R2 | PA→PB 가 관계 유형 + 가지치기 2개 변수를 동시에 바꿈 | PB 를 `PB_REL`(관계 유형만) → `PB`(+조건 가지치기)로 분리. 가지치기 단독 효과 = PB − PB_REL | 제거 실험 사슬 5단계 |
| R3 | "음성·미기록 구분" 지표가 방향 정합만 봄 | **미기록 불변성 검사** 추가: 묻지 않은 근거의 숨은 값을 바꿔도 순위가 같아야 함(위반률 = 0 이 기준). 물은 음성은 반영(C 와 PA 의 차) | 지표 표 |
| R4 | 메모리 사용량 지표 없음 | 모델별 피크 RSS(MB) 측정·보고(성공 기준 아님, 90% 상한 감시) | 지표 표 |
| R5 | SELECT 1,000 의 용도 불명확 | `SELECT_SMOKE`(SELECT 중 해시 정렬 앞 1,000) = 파이프라인 점검 + EXPLORATORY 비교만, 판정·선택 안 함. 모델 선택은 SELECT 전체, 판정은 FINAL 1회 | `split_rules.py` + 테스트 |
| R6 | PB 가지치기 기준값이 미정(결과 보고 조정할 위험) | 사전 고정 격자 {1e-2, 1e-3, 1e-4}(최고 후보 대비 사후 비). SELECT 에서 "중요 누락률 ≤ PB_REL" 인 값 중 Top-5 최고, 동률이면 가장 보수적(1e-4) | manifest model_selection |
| R7 | 학습 분할과 FINAL 의 동일 프로필 중복(결정 트리 암기) 영향 미정 | FINAL 전체(주) + `FINAL_NOVEL`(TRAIN16 에 없는 프로필만) 민감도 분석 사전등록 | `split_rules.verify` 중복률 |
| R8 | 범주형 질문에 토큰이 없을 때(기본값 생략) 처리 미정 | STEP16B 규약 그대로: UNSAFE → 예외(기본값 생성 금지). 발생 수 보고, 해당 질문은 선택 불가 | STEP16B `Semantics.reconstruct` |

## 1. 문제 정의

환자가 첫 증상(`INITIAL_EVIDENCE`) + 나이·성별을 말한 뒤, 시스템이 질문 예산 Q ∈ {3, 5, 10} 안에서 질문하고 질환 후보 순위를 낸다.
답은 숨은 환자 기록에서 시뮬레이터가 준다(STEP16B 규약 재사용: 기재 = POSITIVE/VALUE, 이진 미기재 = NEGATIVE, 부모 음성 → 자식 NOT_APPLICABLE).
**[사실]** DDXPlus EVIDENCES 에는 명시적 음성 토큰이 없다(`data_access_report.json` `explicit_negative_token=false`). 따라서 "음성"은 시뮬레이터 규약이며 실제 환자의 '아니요'와 같지 않다.

## 2. 비교 모델과 통제 변수

| 모델 | 점수기 | 질문 선택 | 음성 사용 | 관계 유형·조건 | WD |
|---|---|---|---|---|---|
| Baseline A | STEP16B MODEL_k(로지스틱, 동결) | INTERNAL_IG(동결) | 모델 특징으로 | 부모-자식 eligibility | 없음 |
| Baseline B | 결정 트리 잎의 클래스 분포 | 트리 경로(깊이 = Q) | 분기로 | 없음 | 없음 |
| Baseline C | 그래프 양성 근거 점수(Σ log P(e⁺\|d)) | 상위 후보에 가장 많이 연결된 미질문 증상 | **안 씀** | 없음 | 없음 |
| Proposed A | C + 음성 우도(Σ log P(e⁻\|d)) | C 와 동일 | **씀** | 없음 | 없음 |
| Proposed B | A + 관계 유형(SUGGESTS / ARGUES_AGAINST, 증상/과거력 구분) | A + 규칙 층 eligibility, 하위 작업 비활성·재활성 | 씀 | **씀** | 없음 |
| Proposed C | B | B + WD 부분그래프 우선(WD 확인 질문 먼저) | 씀 | 씀 | **시뮬레이션 WD** |

통제(모든 모델 동일): 학습 데이터 `TRAIN16`, 평가 `SELECT`(개발)·`FINAL`(1회), 질문 예산 Q, 답변 시뮬레이터, 초기 근거, eligibility 규칙(E_134·E_152 제외 포함), 후보 표시 수(5·8), 우도표(`TRAIN16`, Laplace α=1 — STEP16B `ig_table_step16b_train.npz` 와 같은 추정).

인과 해석 가능한 비교(변수 1개만 다름): **C→PA**(음성), **PA→PB**(관계 유형+조건 가지치기), **PB→PC**(WD).
Baseline A·B 와의 비교는 점수기·선택기가 동시에 다르므로 **참조 비교**로만 보고하고 단일 원인으로 해석하지 않는다.

## 3. 결정 트리 분기 ≠ 안전한 가지치기

- 결정 트리 분기: 데이터 분할 기준. 한쪽 가지로 가면 다른 가지의 질환은 **그 경로에서 사라진다**(복원 불가).
- 안전한 가지치기(PB): 질환 규칙의 **필수 적용 조건이 명시적 NEGATIVE** 일 때 그 규칙의 하위 질문만 비활성. 질환 후보는 남고, 새 답으로 재활성된다.
- **[사실]** DDXPlus 에 임상 지침의 필수 조건은 없다. 쓸 수 있는 구조 조건은 부모-자식 질문 관계뿐이다. 따라서
  - 주 실험의 PB 가지치기 = 부모-자식 구조 조건 + 데이터 유래 "우선순위 하향"(재활성 가능)만.
  - 임상 필수 조건형 가지치기의 안전성은 **별도 합성 시나리오**(정답 규칙을 알고 주입한 가상 환자)로만 평가하고, 실제 의료적 배제로 해석하지 않는다.

## 4. WD 시뮬레이션(Proposed C)

DDXPlus 에 의사 WD 는 없다. WD 를 세 조건으로 주입하고 결과를 따로 보고한다.
- WD_CORRECT: WD = 정답 질환
- WD_PLAUSIBLE_WRONG: WD = DIFFERENTIAL_DIAGNOSIS 중 정답이 아닌 최상위(평가용 메타 사용 — 모델 입력 아님)
- WD_RANDOM_WRONG: 정답 외 무작위
핵심 안전 지표 = **오답 WD 조건의 중요 후보 누락률**(앵커링 편향). WD_CORRECT 성능만으로 PC 를 채택하지 않는다.

## 5. 지표 정의

| 지표 | 정의 |
|---|---|
| 후보 재현율@k | 종료 시 상위 k(5·8) 안에 정답 포함 비율 |
| Top-1/3/5 | 순위 정확도 |
| 감별 재현율 | DIFFERENTIAL_DIAGNOSIS 확률 질량 중 상위 8 이 덮는 비율(평가 전용) |
| 중요 후보 누락률 | 정답 severity ≤ 2(conditions.json, **평가 메타로만**) 사례에서 상위 8 밖 비율 |
| 부정 정보 반영 | (a) 음성 답 후 그 근거의 P(e\|d) ≥ 0.9 인 질환의 사후 순위가 내려간 비율(방향 정합) (b) C→PA 의 Top-5 차 |
| 질문 수 | 실제 질문 수(조기 종료 포함) |
| 탐색 노드 수 | 평가한 (질환·규칙·질문) 노드 수 |
| 추론 시간 | 사례당 ms, p50·p95, 같은 머신·단일 스레드 |
| 잘못된 분기 종료율 | 정답 질환이 활성 집합에서 빠진 뒤 종료까지 재활성 안 된 비율(B: 트리 경로에서 정답 확률 0 인 잎 도달) |
| 보정 | 확률을 내는 모델만 ECE(15 bin)·Brier — 측정만, 제품 표시 금지 계약 유지 |

통계: 사례 단위 paired bootstrap 2,000회 95% CI, 사전 지정 비교 3개(C→PA, PA→PB, PB→PC)에 Holm 보정. 결과는 Q·seed 별로 보고, 여러 seed 면 평균±std.

## 6. 성공·실패 기준(사전 고정 후보 — gate 에서 확정)

- H1(음성): PA − C, Top-5 재현율 차 CI 하한 > 0, 중요 누락률 차 CI 상한 < +0.5%p.
- H2(관계·조건): PB − PA, Top-5 비열등(−0.5%p) **그리고** 탐색 노드 수 감소 또는 잘못된 종료율 감소.
- H3(WD): WD_CORRECT 이득이 있어도 WD_PLAUSIBLE_WRONG 의 중요 누락률이 PB 대비 +1%p 를 넘으면 **채택 불가**.
- 참조: 그래프 계열 최고 vs Baseline A·B 를 함께 보고. 그래프가 A 보다 나쁘면 "그래프 구조 이득 없음"으로 기록(부정 결과 보존).

## 7. 첫 구현 단계

1. 이 worktree 에 RG 활성화 → `rg-plan` 으로 위 내용을 manifest 화 → `rg-gate`.
2. `exp01_symptom_graph/split.py`: STEP16B `split_key`·`is_holdout` 를 **import 해서** TRAIN16/holdout 재현(행 수 820,939/204,663 및 `holdout_row_index_sha256` 일치 확인) → holdout 을 새 키(`sha256("EXP01|"+row_index)`)로 SELECT/FINAL 반분. 분할 간 동일 (AGE, SEX, EVIDENCES) 중복률 보고.
3. `likelihood.py`: `ig_table_step16b_train.npz` 재사용(재학습 없이 로드) + 그래프 간선 표(질환→근거, P(e⁺\|d))로 투영.
4. `simulator.py`: STEP16B `make_view`·Semantics 재사용, 같은 답변 규약.
5. `searchers/`: 공통 인터페이스 `reset(case) / next_question() / observe(q, ans) / ranking()` 로 6개 모델.
6. `run_exp01.py --split SELECT --n 1000` 스모크(수 분) → 결과 확인 → SELECT 전체 → gate 확정 기준으로 FINAL 1회.
