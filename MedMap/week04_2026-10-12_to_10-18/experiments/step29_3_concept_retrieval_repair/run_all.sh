#!/usr/bin/env bash
# STEP29.3 재실행(CPU, LLM·외부 API·다운로드·설치·재학습 없음). 기존 STEP20–29.2·제품 저장소는 읽기만(protect_check).
# 이미 있는 평가 세트·회귀 사례·사전 고정(prereg_gates·policy_freeze)은 유지(덮어쓰지 않음). final 평가는 SHA 가 같을 때만 실행.
set -euo pipefail
cd "$(dirname "$0")/scripts"
PY="${PY:-$HOME/ai_env/bin/python}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-4}" PYTHONHASHSEED=0 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1
"$PY" protect_check.py snapshot
"$PY" generate_eval_cases.py
"$PY" make_regression_cases.py
"$PY" freeze_gates.py
"$PY" analyze_p5_failures.py
"$PY" evaluate_retrieval.py dev
"$PY" freeze_policy.py
"$PY" evaluate_retrieval.py final
"$PY" inspect_prior_results.py
"$PY" run_tests.py
"$PY" benchmark_runtime.py
"$PY" analyze_results.py
"$PY" protect_check.py compare
"$PY" build_report.py
echo RUN_ALL_DONE
