#!/usr/bin/env bash
# STEP25 재실행. 외부 원본은 ~/medmap_external_data/step25/raw/ 에 이미 있어야 함(다운로드·로그인 없음). 학습 없음, CPU.
set -euo pipefail
cd "$(dirname "$0")/scripts"
PY="${PY:-$HOME/ai_env/bin/python}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-4}" PYTHONHASHSEED=0 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
"$PY" inspect_dataset.py
"$PY" validate_external_labels.py
"$PY" evaluate_external.py
"$PY" build_report.py
