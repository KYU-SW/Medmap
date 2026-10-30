#!/usr/bin/env bash
# STEP21 전체 재실행(결정적, 1분 이내). 원본·제품 코드는 읽기만 한다.
set -euo pipefail
cd "$(dirname "$0")/scripts"
PY="${PY:-$HOME/ai_env/bin/python}"
"$PY" build_pilot_dataset.py
"$PY" run_exact_baseline.py
"$PY" run_fuzzy_baseline.py
"$PY" run_mapper_baseline.py
"$PY" evaluate_entity_linking.py
