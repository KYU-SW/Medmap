# RUN_COMMANDS (SUBAGENT C, MDQ 검증) — 모두 SYNTHETIC

Python: `/home/<user>/ai_env/bin/python` (numpy, scipy 1.17.1 `milp`, pandas). 네트워크·설치 불필요. CPU 단일 스레드.
작업 폴더: `/home/<user>/medmap-gate0-parallel/C-mdq/`

| 순서 | 명령 | 출력 | 실측 시간 |
|---|---|---|---|
| 1 | `python hand_cases.py > logs/hand_cases.log 2>&1` | results_hand_cases.csv (손계산 8건) | <5초 |
| 2 | `python run_experiments.py --scen N3,N7,P6,D4 --seeds 1 --tag smoke > logs/smoke.log 2>&1` | results_*_smoke.csv (스모크) | <10초 |
| 3 | `nohup ~/scripts/run_with_done_marker.sh logs/main.done logs/run_main.log -- python run_experiments.py --seeds 10 --tag main > /dev/null 2>&1 &` | results_instances_main.csv, results_methods_main.csv (20조건×10 seed) | 약 1분 |
| 4 | `nohup ~/scripts/run_with_done_marker.sh logs/scaling.done logs/run_scaling.log -- python run_scaling.py > /dev/null 2>&1 &` | results_scaling.csv (n=6..12) | 약 1분 |
| 5 | `python validate_checks.py > logs/validate_checks.log 2>&1` | results_validation_checks.csv (라벨 표본검증·변이시험) | <30초 |
| 6 | `python struct_check.py > logs/struct_check.log 2>&1` | results_struct_hitting.csv (hitting set 제약 크기) | <30초 |
| 7 | `python analyze.py > logs/analyze.log 2>&1` | results_summary_*.csv, tables_generated.md | <5초 |
| 8 | `python build_report.py > logs/build_report.log 2>&1` | C_MDQ_REPORT.md (report_template.md + CSV 수치) | <5초 |

코드 구성
- `core.py` 합성 인스턴스 생성기, 격자 가설 모델(GridModel)
- `methods.py` 기준선 0~6, EC2, 정책트리 생성/평가, hitting set milp
- `exact_grid.py` 정답: 7 전수 일괄, 8 최악 minimax DP, 8e 기대비용 DP, AXp 하한 (methods 와 독립)
- `mdq_candidate.py` 9a/9b MDQ 후보: 연속 W 꼭짓점 인증 + AND-OR 탐색 (core.GridModel/exact_grid 미사용)
- `pair_model.py` 정확 유한 가설(연속 셀)을 GridModel 인터페이스로 감싼 어댑터 (8/7/milp 를 정확 라벨 위에서 독립 대조)
- seed: 인스턴스 seed = 1000×(조건 순번)+seed (R* 해상도 조건은 99000~99009 공통), 무작위 정책 seed = 인스턴스 seed 번호
