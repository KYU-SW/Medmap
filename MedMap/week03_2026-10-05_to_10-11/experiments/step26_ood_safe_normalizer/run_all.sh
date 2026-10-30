#!/usr/bin/env bash
# STEP26 재실행(CPU 전용, 학습 없음 — sklearn 소형 gate/상태 분류기만 적합). 외부 원본은 ~/medmap_external_data/step25/raw/.
set -euo pipefail
cd "$(dirname "$0")/scripts"
PY="${PY:-$HOME/ai_env/bin/python}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-4}" PYTHONHASHSEED=0 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
"$PY" prepare_ood_dataset.py
"$PY" evaluate_baseline.py
"$PY" evaluate_rejection_policies.py
"$PY" evaluate_ood_gate.py
"$PY" benchmark_latency.py
"$PY" analyze_errors.py
"$PY" build_report.py
