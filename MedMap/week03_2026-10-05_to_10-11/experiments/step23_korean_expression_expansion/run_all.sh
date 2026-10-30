#!/usr/bin/env bash
# STEP23 재실행(CPU 전용, 결정적). 격리 작성(scripts/run_isolated_authoring.sh)은 1회만 수행되었고 이 스크립트는 다시 부르지 않는다.
# 생성 원본은 data/raw_generated/ 에 복사되어 있다(격리 폴더 out/ 에서 1회 복사).
set -euo pipefail
cd "$(dirname "$0")/scripts"
PY="${PY:-$HOME/ai_env/bin/python}"
export CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONHASHSEED=0
"$PY" check_authoring_isolation.py
"$PY" audit_expression_quality.py
"$PY" build_expanded_training_data.py
"$PY" train_linear_models.py
"$PY" evaluate_regression.py
"$PY" learning_curve.py
"$PY" contamination_sensitivity.py
"$PY" build_report.py
