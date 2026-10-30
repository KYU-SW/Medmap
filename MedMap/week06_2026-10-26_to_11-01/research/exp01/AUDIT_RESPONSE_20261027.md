# EXP-01 독립 코드 감사(NEEDS_FIX) 대응 — 2026-10-27

감사: 읽기 전용 독립 코드 리뷰(작성 세션과 분리된 code-reviewer) — CRITICAL 0, MAJOR 6.
대응 범위: 코드 수정 + 가상 데이터·지어낸 환자 테스트만. 실데이터 SELECT·FINAL·재학습 실행 0.
사전등록: rev6(deviation 5건 — 한계 명시·M1 검증 강화). 가설·기준값·분할·평가 지표는 바꾸지 않음.

| # | 결함 | 수정 | 검증 |
|---|---|---|---|
| M1 | repro 는 STEP16B 연구 경로만 검증, 실제 평가 경로(BaselineASearcher → medmap 엔진) 미검증, A 래퍼 무테스트 | `aref.py`: 같은 pkl·ig 표로 STEP16B 연구 경로(s16b Encoder·pack_ig/ig_all·Semantics)를 따로 계산해 **매 단계** (1) 사후확률 1e-9 (2) 다음 질문(IG argmax, 동점 번호순) (3) 답 변환(엔진 상태 토큰 == 시뮬레이터 답)을 대조, 불일치 = INVALID. `run_real` 이 모든 분할에서 사용 | `tests/test_baseline_a_path.py` 5개: 인코딩 열·행렬 동일, 지어낸 환자 10명×Q3·5·10 전 단계 일치(범주형 VALUE 경로 통과 확인), 엔진 점수 오염·NEG→POS 변환 오류를 잡음 |
| M2 | confirm 이 FINAL 경로에 미연결 | `run_exp01.main`: FINAL 이면 `confirm.final_analysis` → `final_judgement.json`, `comparisons.csv`(성분 p·합성 p·rank·α*·Holm 조정 p·기각·단계 라벨·H1 라벨·사전 지정 모델) | `test_audit_fixes.TestM2M3M4FinalAnalysis` |
| M3 | τ 선택 규칙·TAU_FAIL 미구현, PC(tau=None) 행 없음 | `metrics.select_tau`(manifest 규칙 그대로), SELECT 에서 `tau_selection.json`(SMOKE·SYNTHETIC 는 EXPLORATORY 표기), `make_final_config` 는 SELECT 결과만 허용, `evaluate` 가 tau=None 이면 PB(가지치기 없음)·PC(PB_REL+WD) 행 생성 | `TestM3TauSelection` 3개, TAU_FAIL 경로 끝까지 실행 |
| M4 | 질환별 규칙 입력 생산 코드 없음, 인자 의미 모호 | `confirm.disease_counts`·`disease_fired_all`(PC 는 WD_MODEL·MODEL_WRONG·RANDOM_WRONG seed 3개 합집합, WD_CORRECT 제외), `metrics.disease_rule_fires` 는 정수 개수만 허용(비율이면 예외) | 정수 확인·비율 거부·인위 악화 탐지 테스트 |
| M5 | 산출물 1/7, 이차 지표 다수 미구현 | `artifacts.py`: split_manifest.json·metrics.csv·comparisons.csv·per_case.parquet·graph_stats.json·run_meta.json·subgroups.csv(+summary.json). 지표: ECE·Brier·macro Top-5·감별 재현율·음성 반영 방향 정합률·정답 첫 Top-5 진입 질문 번호·계산 수 중앙값·가지치기 발동률·재활성·질환별 n·누락 수·SE·AGE·SEX·사전확률 사분위·FINAL_NOVEL·WD_MODEL vs 그래프 초기 top-1 일치율·WD 정답률 혼합·응답 잡음 민감도(C·PA, Q=5)·생성기 지식표 간선 일치율 | 7개 파일 생성·열 존재·손계산 대조·근거 문자열 미저장 확인 |
| M6 | FINAL 잠금이 CLI 인자 미결속, seeds 기본 42 | 실행 인자는 설정 JSON 에서만(`--budgets/--seeds/--tau` 제거), seeds 는 42·43·44 아니면 거부, FINAL 은 `tau_selected` 필수, 잠금 파일의 config_path 와 실행 config 일치 요구, 잠금 해시 범위 = exp/main_ai(+외부 코드·모델·HEAD) | `TestM6ConfigLock` 4개(설정 1바이트 변경 → 해시 변경 포함) |

MINOR 수정: Holm 기각 = 조정 p < 0.025 로 통일 · 가지치기 발동률 분모(cand_steps) · WD 단계 활성 집합 갱신 · 정적 검사 인라인 주석 제거(tokenize) · 처리 시간에서 검사 시간 제외 · 누출 검사 결과를 PASS/NA/SKIP 로 표기(위반은 예외로 중단) · 잠금 범위 일치.
남은 MINOR: 누출 검사는 사례당 근거 1개만 뒤집음(manifest 정의 — 바꾸려면 deviation), 정적 검사는 문자열 기반(우회 가능), A 의 k 문맥은 0문항 시작에서도 Q 에 맞춘 k(STEP16B 사전등록 규칙).

## 한계(사전등록 rev6 expected_claim·potential_confounders)
C·PA·PB_REL·PB·PC 는 실제 의료 관계 그래프 추론이 아니라 **확률표(STEP16B ig_table) 기반 나이브 베이즈 사후확률 + 휴리스틱 질문 선택**이다.
그래프 순회·다중 경로·관계 유형 기반 점수·근거 출처 묶음은 쓰지 않는다. 결론은 '확률표 기반 질문 선택 구성요소의 효과' 로만 표현한다.
실제 다중 경로 그래프 추론은 `exp/main_ai/exp01b_graph_reasoning/README.md`(EXP-01b 후보)로 분리.

## 재감사·gate 5~7 추가 대응 (2026-10-27)
- 독립 재감사 NEEDS_FIX(신규 MAJOR N1·N2) + gate 5 NEEDS_FIX(설계 MAJOR 2·통계 MAJOR 1) + gate 6 NEEDS_FIX(설계 MAJOR 1) → 모두 수정 → **gate 7 RUN, protocol lock 52f81aedf22a (manifest rev7)**.
- N1: 응답 잡음 행이 확인적 분석에 섞여 FINAL 이 FinalGuard 소모 후 크래시 → `confirm._vec` 잡음 제외, `disease_counts` 잡음 거부, 잡음 포함 회귀 테스트.
- N2: SELECT·FINAL 설정에 leak_check·budgets [3,5,10]·seeds 순서·SELECT τ 격자 강제, 트리 seed 42 고정.
- 설계 gate5 MAJOR 2: 모든 실데이터 실행 run_meta 에 실행 잠금 해시(parts)·rg 상태·입력 SHA·패키지 버전, FINAL 은 τ 선택 SELECT 실행과 code·external·models·medmap_head·τ 대조.
- 설계 gate6 MAJOR: 위 대조가 JSON 왕복(튜플→리스트) 때문에 항상 거부 → 형태 통일 + 정상 경로 테스트.
- 통계 MINOR: per_case 를 확인적 분석보다 먼저 저장, τ 동률 정수 비교, ECE 정답 = argmax, 빈 부분집합 재표본 수, 질환별 Wilson 구간, 보조 보고(양측 95% CI·Holm 순위 단측 한계·P*(Δ*≥0.01)·GM 점추정·상한), aref 최대 |차| 기록.
- 내가 낸 버그 2건(숨기지 않음): (1) ECE 수정 때 dict 한 줄에 주석을 넣어 brier 항목이 주석 처리됨 → 테스트로 발견·수정 (2) 그 버그가 있는 동안 돌던 변이 재검사 결과가 오염 → 깨끗한 코드로 전체 재실행.
- 남은 MINOR: Holm 동치 변이 1개(경계 p=0.025 불가능), ECE 회귀 테스트가 동점 사례를 직접 구분하지 않음, 계산 수에 초기 근거 49 포함(보수적), 보조 보고는 final_judgement.json 에만, 피크 RSS 는 모델별이 아닌 전체, ms 워밍업 100 사례 제외 미구현, 누출 검사는 사례당 근거 1개.
