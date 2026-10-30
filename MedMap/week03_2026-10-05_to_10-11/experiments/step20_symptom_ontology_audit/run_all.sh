#!/usr/bin/env bash
# STEP20 전체 재실행(결정적). 원본 data/ 는 읽기만 한다. 캐시는 .cache/ (원본 크기·mtime 바뀌면 재생성)
set -euo pipefail
cd "$(dirname "$0")/scripts"
PY="${PY:-$HOME/ai_env/bin/python}"
"$PY" audit_symptom_mapping.py inventory
"$PY" audit_hpo_mapping.py
"$PY" audit_umls_mapping.py
"$PY" audit_snomed_mapping.py
"$PY" audit_symptom_mapping.py summary
