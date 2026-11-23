# RUN_COMMANDS — SUBAGENT B (JNP 계산 문제·기준선 실험), SYNTHETIC

환경: `/home/<user>/ai_env/bin/python` (Python 3, numpy 2.1.2, scipy 1.17.1 / HiGHS 1.12.0, pandas 3.0.3). 설치 작업 없음, 네트워크 호출 없음.
모든 명령은 `/home/<user>/medmap-gate0-parallel/B-jnp/` 에서 실행한다.

```bash
cd /home/<user>/medmap-gate0-parallel/B-jnp
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
PY=/home/<user>/ai_env/bin/python

# 1) 손계산 사례 대조 (수 초)
$PY handcases.py > logs/handcases.log 2>&1

# 2) 개별 방법 단독 실행 (손계산 사례 입력)
$PY exact_enum.py handcases_instances.json
$PY milp_solver.py handcases_instances.json
$PY jnp_candidate.py handcases_instances.json

# 3) 본 실험 (3개 그룹 병렬, 백그라운드; 총 약 20~40분)
TS=$(date +%Y%m%d_%H%M)
nohup bash -c "for s in nU m wcons; do $PY run_experiments.py --sweep \$s --n_inst 20 --out results_main_\$s.csv; done; echo EXIT \$? > logs/done_g1" > logs/run_g1_$TS.log 2>&1 &
nohup bash -c "for s in n rules deps; do $PY run_experiments.py --sweep \$s --n_inst 20 --out results_main_\$s.csv; done; echo EXIT \$? > logs/done_g2" > logs/run_g2_$TS.log 2>&1 &
nohup bash -c "for s in conflict missing; do $PY run_experiments.py --sweep \$s --n_inst 20 --out results_main_\$s.csv; done; $PY run_experiments.py --sweep scale --n_inst 3 --out results_scaling.csv --mem; echo EXIT \$? > logs/done_g3" > logs/run_g3_$TS.log 2>&1 &

# 완료 확인
until [ -e logs/done_g1 ] && [ -e logs/done_g2 ] && [ -e logs/done_g3 ]; do sleep 15; done; cat logs/done_g*
grep -h -E "DISAGREE|ERROR|status4" logs/run_g*_$TS.log

# 3b) 스트레스 확장성 (규칙 수 = nU, 점수수정 = nU//2; 약 1분)
nohup bash -c "$PY run_experiments.py --sweep stress --n_inst 3 --out results_stress.csv --mem; echo EXIT \$? > logs/done_stress" > logs/run_stress_$TS.log 2>&1 &

# 4) 집계 표 생성 (report_tables.md, results_summary_*.csv)
$PY make_tables.py > logs/make_tables.log 2>&1

# 5) 약한 기준선 실패 사례 추출 (results_failure_examples.csv, results_failure_breakdown.csv)
$PY find_failures.py > logs/find_failures.log 2>&1
```

seed 규칙: `seed = 100000*(sweep 순번+1) + 1000*(값 순번) + 인스턴스 번호` (run_experiments.py). 같은 seed 면 같은 인스턴스.
