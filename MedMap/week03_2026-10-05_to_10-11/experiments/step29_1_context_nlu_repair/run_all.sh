#!/usr/bin/env bash
# STEP29.1 재실행(CPU, LLM·다운로드·설치·재학습 없음). 기존 STEP20–29·제품 저장소는 읽기만(protect_check).
set -euo pipefail
cd "$(dirname "$0")/scripts"
PY="${PY:-$HOME/ai_env/bin/python}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-4}" PYTHONHASHSEED=0 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
"$PY" protect_check.py snapshot
"$PY" inspect_prior_results.py
"$PY" make_prospective_synthetic.py
"$PY" validate_evaluator_v5.py
"$PY" freeze.py
"$PY" evaluate_nlu.py
"$PY" run_tests.py
"$PY" benchmark_runtime.py
"$PY" analyze_errors.py
"$PY" protect_check.py compare
"$PY" build_report.py
echo RUN_ALL_DONE
