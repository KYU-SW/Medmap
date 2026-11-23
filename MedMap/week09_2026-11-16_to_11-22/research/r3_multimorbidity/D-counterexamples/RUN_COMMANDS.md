# RUN_COMMANDS — SUBAGENT D (모든 입력 [가상] SYNTHETIC, 외부 데이터·API 없음)

작업 폴더: `/home/<user>/medmap-multimorbidity-deep-gap/D-counterexamples/`
Python: `/home/<user>/ai_env/bin/python -I` (numpy, scipy 1.17.1 `milp`/`linprog`(HiGHS)). CPU 단일, 각 실행 < 2분.
이전 Gate0 B/C 코드는 복사·재사용하지 않음(독립 구현). `common.py` 는 이번에 새로 작성.

```bash
cd /home/<user>/medmap-multimorbidity-deep-gap/D-counterexamples
timeout 115 /home/<user>/ai_env/bin/python -I e2_highorder.py     > logs/e2_highorder.log 2>&1      # 약 3초
timeout 115 /home/<user>/ai_env/bin/python -I e3_certainty.py     > logs/e3_certainty.log 2>&1      # 약 2초
timeout 115 /home/<user>/ai_env/bin/python -I e4_dynamic.py       > logs/e4_dynamic.log 2>&1        # 약 3초
timeout 115 /home/<user>/ai_env/bin/python -I e5_pareto.py        > logs/e5_pareto.log 2>&1         # 약 75초
timeout 115 /home/<user>/ai_env/bin/python -I e6_joint_support.py > logs/e6_joint_support.log 2>&1  # 약 1초
```

| 스크립트 | 유형 | 출력 CSV | seed |
|---|---|---|---|
| e2_highorder.py | 1, 5(b) | results_e2_highorder.csv | 20261117 (N=600, n=8) |
| e3_certainty.py | 3(a) | results_e3_certainty_summary.csv | 전수(85,264 구조) |
| e4_dynamic.py | 4, (c) | results_e4_dynamic.csv | 20261117 (N=300, n=6) |
| e5_pareto.py | 5(목표충돌·부담) | results_e5_pareto.csv | 20261117 (N=60, n=7) |
| e6_joint_support.py | 6 | results_e6_joint_support.csv | 20261117 |

로그의 `HighsMipSolverData::transformNewIntegerFeasibleSolution tmpSolver.run();` 줄은 HiGHS 내부 진단 출력(오류 아님, rc=0).
