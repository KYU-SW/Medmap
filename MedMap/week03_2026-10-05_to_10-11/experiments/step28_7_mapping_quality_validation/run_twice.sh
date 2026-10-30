#!/usr/bin/env bash
# STEP28.7 2회 재현 — 결정적 산출물 SHA 비교(지연 수치 포함 파일 제외: latency.json·manifest.json·step28_7_verdict.json·report).
set -euo pipefail
D="$(cd "$(dirname "$0")" && pwd)"
DET="data/concept_facts.csv data/snomed_local_audit.csv data/row_isolation.csv data/audited_concepts.csv data/cleaned_silver_mappings.csv data/mapping_provenance.csv data/eval_rows.csv outputs/count_reconciliation.json outputs/priority_pair_relations.json outputs/isolation_analysis.json outputs/concept_audit.json outputs/independent_new_concepts.csv outputs/existing_synonyms.csv outputs/existing_subtypes.csv outputs/held_candidates.csv outputs/rejected_candidates.csv outputs/policy_comparison.csv outputs/regression_metrics.json outputs/non_symptom_error_analysis.csv outputs/candidate_safety_analysis.csv outputs/reproduction_check.json outputs/eval_summary.json outputs/protected_check.json outputs/exploratory_v2.json"
for i in 1 2; do
  bash "$D/run_all.sh" > "$D/logs/run$i.log" 2>&1
  (cd "$D" && sha256sum $DET > "logs/sha$i.txt")
done
if cmp -s "$D/logs/sha1.txt" "$D/logs/sha2.txt"; then echo SHA_IDENTICAL >> "$D/logs/run2.log"; else echo SHA_DIFF >> "$D/logs/run2.log"; diff "$D/logs/sha1.txt" "$D/logs/sha2.txt" >> "$D/logs/run2.log" || true; fi
echo DONE >> "$D/logs/run2.log"
