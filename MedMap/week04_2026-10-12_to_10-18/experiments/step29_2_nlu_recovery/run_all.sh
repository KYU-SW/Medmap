#!/usr/bin/env bash
# STEP29.2 재실행(CPU, LLM·외부 API·다운로드·설치·재학습 없음). 기존 STEP20–29.1·제품 저장소는 읽기만(protect_check).
# 이미 있는 평가 세트·사전 고정(prereg_gates·policy_freeze)은 유지된다(덮어쓰지 않음). final 평가는 SHA 가 같을 때만 실행.
set -euo pipefail
cd "$(dirname "$0")/scripts"
PY="${PY:-$HOME/ai_env/bin/python}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-4}" PYTHONHASHSEED=0 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1
"$PY" protect_check.py snapshot
"$PY" inspect_previous_results.py
"$PY" generate_eval_pairs.py
"$PY" validate_evaluator_v6.py
"$PY" freeze_gates.py
"$PY" evaluate_nlu.py dev
"$PY" freeze_policy.py
"$PY" evaluate_nlu.py final
"$PY" run_tests.py
"$PY" benchmark_runtime.py
"$PY" analyze_errors.py
"$PY" protect_check.py compare
"$PY" build_report.py
echo RUN_ALL_DONE
