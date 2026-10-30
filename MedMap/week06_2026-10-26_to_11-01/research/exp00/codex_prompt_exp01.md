# Codex 입력용: EXP-01 (RG EXP-MAI-001) 실행 프롬프트 — rev2 (2026-10-26)

전제: RG gate 판정이 **RUN** 이어야 4단계(SELECT_SMOKE) 이후를 실행할 수 있다. NEEDS_FIX 상태면 1~3단계(구현·가상 데이터 테스트)까지만.

**상태(2026-10-27):** gate 3 = RUN, protocol 동결 `protocol.lock.json` sha256 `f6fb369e6c65`(manifest rev4). 실데이터 실행은 아직 0.
gate 3 MINOR(판정 불변) — manifest 는 동결됐으므로 문구를 바꾸려면 `rg.py deviation` 으로 사유를 기록하고 `/rg-gate` 재심사를 받는다.
구현은 아래처럼 더 엄격한 쪽으로 맞춘다(protocol 을 완화하지 않음).
1. 실행 잠금 해시에 ~/medmap 의 medmap/diagnosis.py·next_information.py 와 s16b_core.py 의 SHA 도 포함한다.
2. IUT 판정은 p<0.025(#{귀무 방향 Δ*}≤249) 로 하고, 97.5% 한계는 보조로 기록한다.
3. τ 선택이 실패하면 PC = PB_REL+WD 로 하고, 잘못된 분기 종료 IUT 는 NA, 단계 라벨은 TAU_FAIL / NOT_ELIGIBLE 로 기록한다.
4. 사전 지정 모델이 PC 일 때 A·B 참조 비교는 WD_MODEL 을 주 보고로 하고, 나머지 조건은 병기한다.
5. SAFETY_FAIL 은 "안전 비열등 미입증", SAFETY_HOLD 는 "확정 미채택"으로 표기한다.
6. 같은 Synthea 개체가 여러 행을 만들었을 가능성을 한계로 적는다.
위 1~5 는 동결 문구와 해석이 달라질 수 있다. 구현 전에 deviation 을 기록하고 경량 재심사를 받는 것을 권장한다.

```
너는 MedMap 연구 프로젝트의 AI 연구 엔지니어다.
작업: EXP-01 (Research Guardian 실험 ID EXP-MAI-001) — 관계 그래프 탐색 구성요소 제거 실험(DDXPlus 합성).
정본 protocol = ~/medmap-worktrees/main-ai/.research-guardian/experiments/EXP-MAI-001/manifest.yaml (rev2).
manifest 와 다른 해석이 필요하면 구현하지 말고 보고하라. manifest·protocol.lock·review 필드는 직접 수정 금지(rg.py 만).

[먼저 확인]
1. cd ~/medmap-worktrees/main-ai && python3 ~/.claude/research-guardian/bin/rg.py status --exp EXP-MAI-001
   - review 가 RUN 이고 protocol 이 LOCKED 인지 확인. 아니면 1~3단계까지만 하고 멈춘다.
2. 읽을 것: manifest.yaml 전체, .research-guardian/audits/EXP-MAI-001/gate/ 최신 보고서,
   exp/main_ai/exp00_readiness/{exp01_predesign.md, protocol.md, graph_design.md},
   exp/main_ai/exp01_symptom_graph/split_rules.py(+tests), exp/main_ai/common/evidence_graph.py.

[금지]
- master·~/medmap/medmap(제품 코드)·~/medmap/exp/step*·~/medmap/data 원본 수정 금지(읽기만). 다른 worktree·브랜치 수정 금지.
  push·병합·브랜치 삭제 금지. 커밋은 사용자 지시가 있을 때만.
- ~/<restricted>/ 접근 금지(ls·sha256sum 포함).
- DDXPlus release_validate_patients·release_test_patients 열기 금지.
- release_conditions.json·severity 는 metrics(평가) 모듈만 SHA 대조 후 읽는다. searchers/·likelihood.py 는 읽지도 import 하지도 않는다.
- DIFFERENTIAL_DIAGNOSIS·PATHOLOGY 는 평가·WD 조건 정의에만. 탐색기 입력 금지.
- 외부 API·LLM 호출, 패키지 설치, 다운로드 금지. Python = ~/ai_env/bin/python, 테스트 = unittest.
- 실행하지 않은 결과를 숫자로 쓰지 말 것. 보고서 숫자는 산출 CSV/JSON 에서 생성.
- FINAL 실행 금지(이번 프롬프트 범위 밖).

[1단계 구현 — exp/main_ai/exp01_symptom_graph/ 아래]
- data.py: train 파일 읽기(입력 SHA 를 manifest dataset_version 기대값과 대조, 불일치면 중단), split_rules.assign/verify 로
  TRAIN16/SELECT/FINAL/SELECT_SMOKE 생성, 프로필 = (AGE, SEX, INITIAL_EVIDENCE, EVIDENCES). STEP16B 기대값 불일치면 중단.
- simulator.py: ~/medmap/exp/step16b_next_information_validation/s16b_core.py 의 Semantics(reconstruct·currently_eligible) import 재사용.
  탐색기에는 observe(q, answer) 로만 답 전달. UNSAFE = INVALID.
- likelihood.py: ig_table_step16b_train.npz 로드(재추정 금지), prior = TRAIN16 질환 빈도, 관계 유형(이진만) = P(POS|q,d) > P(POS|q).
- searchers/: 공통 인터페이스 reset(initial_evidence, age, sex, wd=None) / next_question() / observe(q, ans) / ranking() / stats().
  금지 키(PATHOLOGY, EVIDENCES, DIFFERENTIAL_DIAGNOSIS, severity) 전달 시 assert.
  baseline_a(~/medmap 을 sys.path 에 넣어 medmap.diagnosis·next_information 읽기 전용 import, Q→k3/k5/k10),
  baseline_b(manifest baseline 의 전역 결정 트리 규칙 그대로), graph_c, graph_pa, graph_pb_rel, graph_pb(τ), graph_pc(WD 4조건).
  각 정의는 manifest baseline·proposed_method 문장 그대로 — 임의 가중치·하이퍼파라미터 추가 금지.
- counters.py: 그래프 계열 공통 계수 함수(질문 선택 (질환, 질문) 쌍 점수 수 + 사후 갱신 (질환, 답) 수).
- checks.py: (a) 근거 집합 일치 assert (b) 숨은 기록 누출 검사(자식 없는 이진 근거 1개 뒤집기) (c) 금지 입력 정적 검사.
- metrics.py: manifest secondary_metrics·statistical_test 그대로. bootstrap B=10,000 같은 재표본 인덱스, 500회 단위 분할.
  Holm m=6 단측 α=0.025, IUT 조건, MID_H1 은 manifest 값(사용자 확정값) 사용.
- run_exp01.py --split {SELECT_SMOKE|SELECT} --budgets 3,5,10 --seeds 42[,43,44] --out outputs/<run_id>/
  (FINAL 분기는 FinalGuard 를 통과해야만 열리도록 구현하되 이번에는 실행하지 않는다.)

[2단계 테스트 — tests/ (unittest, 가상 데이터)]
- split 재현(이미 있음), 시뮬레이터 규약, 각 탐색기가 예산 초과 질문을 하지 않음, PB 가 질환을 순위에서 삭제하지 않음·재활성 로그,
  근거 집합 assert 의 변이(미기록→NEG 주입 시 실패), PATHOLOGY 주입 변이 시 실패, 정적 검사 변이(탐색기에 release_conditions 문자열
  주입 시 실패), metrics 손계산 예(단측 p·Holm·IUT), FinalGuard.
- 모든 검사는 고의 오류를 넣으면 실패하는지 변이 검사 결과를 표로 남긴다.

[3단계 정적 점검] py_compile, 금지 입력 정적 검사, 테스트 전체 통과. 여기까지는 RG 판정과 무관하게 허용.

[4단계 — RG RUN + 사용자 승인 후에만] SELECT_SMOKE(1,000) 실행
- 2분 이상 예상 시 ~/scripts/wait_for_resources.sh --check 후 nohup + ~/scripts/ram_guard.sh <PID> 90 60 <log>.
- 확인: split 기대값 일치, Baseline A 재현 대조(STEP16B 02_holdout_initial_predictions.csv), 누출·assert 위반 0.
- SELECT_SMOKE 결과는 EXPLORATORY — τ 선택·판정에 쓰지 않는다.

[보고 형식]
1. 판정: IMPLEMENTED_TESTS_PASS / SMOKE_PASS / SMOKE_FAIL / BLOCKED
2. 생성 파일과 git status
3. 테스트·변이 검사 결과표
4. (4단계 했으면) split 결과·재현 대조·검사 결과·스모크 지표표(CSV 에서 생성), 모델별 ms·피크 RSS
5. 사실 / 문헌 / 가설 / 미검증 제안 구분
6. 다음 단계 1개(SELECT 전체 실행 승인 요청)
```
