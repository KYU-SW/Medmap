# EXP-01 (RG EXP-MAI-001) 구현 — 2026-10-27

정본 protocol: `.research-guardian/experiments/EXP-MAI-001/manifest.yaml` rev5, gate 4 RUN, lock `5cb245972b4d`.
실데이터 실행: **0** (학습·SELECT·FINAL 미실행).

| 모듈 | 역할 |
|---|---|
| `core.py` | 답 표현, 금지 입력 guard, 시뮬레이터, 공통 탐색 루프(예산·중복·eligibility 강제, on_step 훅) |
| `likelihood.py` | STEP16B ig_table 그대로 로드(재추정 없음), 관계 유형 SUGGESTS/ARGUES_AGAINST |
| `searchers.py` | 그래프 계열 C·PA·PB_REL·PB(τ)·PC(WD), Baseline B 전역 결정 트리, Baseline A(STEP16B MODEL_k+INTERNAL_IG 래퍼) |
| `checks.py` | 근거 집합 일치, 독립 참조 점수기(1e-9), 숨은 기록 누출, 정적 검사(금지 문자열·import) |
| `metrics.py` | 비관적 순위, 잘못된 분기 종료, ECE·Brier, bootstrap(같은 인덱스), 단측 p, 합성 p, Holm(동률=작은 순위 공유), MID·질환별 규칙 정수 비교, 라벨, 순차 채택 |
| `confirm.py` | FINAL 확인적 분석(A안 6개 합성 가설, TAU_FAIL NA) |
| `severity_eval.py` | 평가 전용 중증 17질환(conditions SHA 대조, 탐색기 import 금지) |
| `split_rules.py` | STEP16B 분할 재사용·SELECT/FINAL/SMOKE·검증·FinalGuard |
| `data.py` | 실데이터 적재(입력 SHA 대조, prior=TRAIN16 빈도) — RG RUN+승인 후 |
| `repro.py` | SELECT_SMOKE 에서 Baseline A 초기 예측을 STEP16B 02 csv 와 대조(정답 열 미열람) |
| `lockhash.py` | FINAL 실행 잠금 해시(config+코드+외부 코드+모델 SHA+~/medmap HEAD, 경로 한정 clean 확인) |
| `synth.py` | 가상 세계(테스트·SYNTHETIC) |
| `run_exp01.py` | 실행기. SYNTHETIC / SELECT_SMOKE·SELECT(--approved + RG RUN 필요) / FINAL(+잠금·FinalGuard) |

테스트: `~/ai_env/bin/python -m unittest discover -s exp/main_ai/exp01_symptom_graph/tests -v` (worktree 루트) — 40개.

SELECT_SMOKE 실행 명령(승인 후, 2분 이상 예상 → 래퍼):
```bash
cd ~/medmap-worktrees/main-ai
~/scripts/wait_for_resources.sh --check --no-gpu
TS=$(date +%Y%m%d_%H%M)
nohup ~/scripts/wait_for_resources.sh --no-gpu --log exp/main_ai/exp01_symptom_graph/logs/wait_$TS.log \
  --job-log exp/main_ai/exp01_symptom_graph/logs/smoke_$TS.log -- \
  ~/ai_env/bin/python exp/main_ai/exp01_symptom_graph/run_exp01.py --split SELECT_SMOKE --approved \
  --budgets 3,5,10 --seeds 42,43,44 --out exp/main_ai/exp01_symptom_graph/outputs/smoke_$TS > /dev/null 2>&1 &
```
