#!/usr/bin/env bash
# STEP28.5 재실행(CPU, 재학습·다운로드 없음). STEP28 색인(index/ontology_index.sqlite)·검증기를 읽기만 한다. index/ 는 LOCAL_ONLY_LICENSED.
set -euo pipefail
cd "$(dirname "$0")/scripts"
PY="${PY:-$HOME/ai_env/bin/python}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-4}" PYTHONHASHSEED=0 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
"$PY" extract_symptom_spans.py
"$PY" build_korean_index.py          # 자원 목록(inspect_existing_resources) 포함
"$PY" build_bilingual_links.py
"$PY" evaluate_multilingual_model_gate.py
"$PY" validate_concepts.py
"$PY" evaluate_retrieval.py
"$PY" benchmark_latency.py
"$PY" build_report.py
