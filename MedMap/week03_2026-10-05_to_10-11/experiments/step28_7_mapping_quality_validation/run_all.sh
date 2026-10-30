#!/usr/bin/env bash
# STEP28.7 재실행(CPU, LLM·다운로드·재학습 없음). 기존 STEP20–28.6 산출물·제품 저장소는 읽기만(G10 으로 확인).
set -euo pipefail
cd "$(dirname "$0")/scripts"
PY="${PY:-$HOME/ai_env/bin/python}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-4}" PYTHONHASHSEED=0 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
"$PY" protect_check.py snapshot
"$PY" audit_new_concepts.py
"$PY" analyze_isolation_failures.py
"$PY" deduplicate_concepts.py
"$PY" clean_silver_mappings.py
"$PY" evaluate_mapping_safety.py
"$PY" benchmark_runtime.py
"$PY" protect_check.py compare
"$PY" build_report.py
"$PY" evaluate_exploratory_v2.py   # [변경 기록] 1차 평가 후 추가 — 탐색적 v2(공식 판정 아님)
"$PY" build_report.py             # v2 절을 넣어 보고서 재생성(판정 규칙 동일)
echo RUN_ALL_DONE
