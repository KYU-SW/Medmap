#!/usr/bin/env bash
# STEP24 전체 재실행. GPU 사용(KoELECTRA-small), Linear 는 CPU. 다른 세션 GPU 경합 시 wait_for_resources.sh 로 감싸 실행할 것.
# 다운로드는 하지 않는다(models/pretrained_koelectra_small_main 이 이미 있어야 함).
set -euo pipefail
cd "$(dirname "$0")/scripts"
PY="${PY:-$HOME/ai_env/bin/python}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-4}" PYTHONHASHSEED=0 CUBLAS_WORKSPACE_CONFIG=:4096:8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
"$PY" check_environment.py
"$PY" train_koelectra_small.py
"$PY" evaluate_transformer.py
"$PY" evaluate_hybrid.py
"$PY" analyze_agreement.py
"$PY" benchmark_latency.py
"$PY" build_report.py
