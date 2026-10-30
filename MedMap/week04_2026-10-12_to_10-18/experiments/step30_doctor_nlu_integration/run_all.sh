#!/usr/bin/env bash
# STEP30 재실행(CPU, LLM·외부 API·다운로드·설치·재학습 없음). 제품(~/medmap master)·STEP20–29.3 원본·서버는 읽기만(protect_check).
# 사전 고정(prereg_freeze rules·code)이 있으면 덮어쓰지 않고 SHA 확인만. 변환표는 없을 때만 생성.
set -euo pipefail
cd "$(dirname "$0")/scripts"
PY="${PY:-$HOME/ai_env/bin/python}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-4}" PYTHONHASHSEED=0 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1
"$PY" protect_check.py snapshot
"$PY" inspect_product_contracts.py
"$PY" inspect_nlu_interfaces.py
"$PY" check_case_overlap.py
[ -f ../data/evidence_mapping_candidates.csv ] || "$PY" build_evidence_mapping.py
"$PY" freeze_prereg.py rules
"$PY" freeze_prereg.py code
"$PY" freeze_prereg.py verify
"$PY" evaluate_integration.py
"$PY" run_tests.py
"$PY" benchmark_runtime.py
"$PY" protect_check.py compare
"$PY" build_preview.py
"$PY" license_scan.py
"$PY" finalize_verdict.py
"$PY" build_report.py
"$PY" license_scan.py
echo RUN_ALL_DONE
