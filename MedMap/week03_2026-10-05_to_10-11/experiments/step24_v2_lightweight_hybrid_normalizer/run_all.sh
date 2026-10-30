#!/usr/bin/env bash
# STEP24-v2 (PROTOCOL_DEVIATION: KoELECTRA 학습 grid 확장). GPU 사용. 다운로드 없음(v1 의 사전학습 가중치를 읽기만 함).
set -euo pipefail
cd "$(dirname "$0")/scripts"
PY="${PY:-$HOME/ai_env/bin/python}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-4}" PYTHONHASHSEED=0 CUBLAS_WORKSPACE_CONFIG=:4096:8 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
"$PY" check_implementation.py
"$PY" -c "import json,sys; sys.exit(0 if json.load(open('../outputs/implementation_check.json'))['IMPLEMENTATION_OK'] else 9)"
"$PY" train_koelectra_small.py
for s in 42 43 44 45 46; do
  STEP24_SEED=$s "$PY" evaluate_transformer.py
  STEP24_SEED=$s "$PY" evaluate_hybrid.py
  STEP24_SEED=$s "$PY" analyze_agreement.py
done
"$PY" summarize_seeds.py
"$PY" benchmark_latency.py
"$PY" build_report.py
