#!/usr/bin/env bash
# STEP22 전체 재실행(CPU 전용, 결정적, 수 분 이내). STEP21·제품 코드는 읽기만 한다.
set -euo pipefail
cd "$(dirname "$0")/scripts"
PY="${PY:-$HOME/ai_env/bin/python}"
export CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONHASHSEED=0
"$PY" build_training_inventory.py
"$PY" train_linear_normalizer.py
"$PY" evaluate_linear_normalizer.py
"$PY" analyze_confusions.py
"$PY" build_report.py
