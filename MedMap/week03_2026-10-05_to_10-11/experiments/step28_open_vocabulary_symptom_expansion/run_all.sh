#!/usr/bin/env bash
# STEP28 재실행(CPU 전용, 기존 모델 재학습 없음, 다운로드 없음). 원본 ontology(~/medmap/data/{hpo,umls,snomed})는 읽기만 한다.
# index/ 는 LOCAL_ONLY_LICENSED(UMLS·SNOMED 문자열) — 공개 저장소 금지. 경로 C 임베딩 캐시는 재현 확인을 위해 매번 다시 만든다.
set -euo pipefail
cd "$(dirname "$0")/scripts"
PY="${PY:-$HOME/ai_env/bin/python}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-4}" PYTHONHASHSEED=0 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
rm -f ../index/xlmr_hpo_embeddings.npz
"$PY" inspect_previous_steps.py
"$PY" build_ontology_index.py
"$PY" validate_concept_candidates.py
"$PY" evaluate_crosslingual_feasibility.py
"$PY" evaluate_expansion.py
"$PY" benchmark_latency.py
"$PY" build_report.py
