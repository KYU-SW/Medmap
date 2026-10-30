#!/usr/bin/env bash
# STEP29 2회 재현 — 결정적 산출물 SHA 비교(latency·manifest·verdict·report 제외).
set -euo pipefail
D="$(cd "$(dirname "$0")" && pwd)"
DET="outputs/previous_results.json outputs/evaluator_v4_validation.json data/evaluation_manifest.csv data/eval_mentions.csv outputs/eval_errors.csv outputs/policy_comparison.csv outputs/eval_summary.json outputs/metamorphic_results.json outputs/unit_tests.json outputs/span_error_analysis.csv outputs/negation_analysis.csv outputs/temporality_analysis.csv outputs/experiencer_analysis.csv outputs/normalization_analysis.csv outputs/protected_check.json"
for i in 1 2; do
  bash "$D/run_all.sh" > "$D/logs/run$i.log" 2>&1
  (cd "$D" && sha256sum $DET > "logs/sha$i.txt")
done
if cmp -s "$D/logs/sha1.txt" "$D/logs/sha2.txt"; then echo SHA_IDENTICAL >> "$D/logs/run2.log"; else echo SHA_DIFF >> "$D/logs/run2.log"; diff "$D/logs/sha1.txt" "$D/logs/sha2.txt" >> "$D/logs/run2.log" || true; fi
echo DONE >> "$D/logs/run2.log"
