#!/usr/bin/env bash
# STEP27 재실행(CPU 전용, 기존 모델 재학습 없음 — STEP26 비증상 점수 분류기 재료로 DEV out-of-fold 점수만 다시 계산).
# 입력은 STEP23–26 산출물(read-only). 외부 원본은 ~/medmap_external_data/step25/raw/.
set -euo pipefail
cd "$(dirname "$0")/scripts"
PY="${PY:-$HOME/ai_env/bin/python}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-4}" PYTHONHASHSEED=0 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
"$PY" inspect_previous_experiments.py
"$PY" evaluate_routing.py
"$PY" analyze_routing_errors.py
"$PY" benchmark_latency.py
"$PY" build_report.py
