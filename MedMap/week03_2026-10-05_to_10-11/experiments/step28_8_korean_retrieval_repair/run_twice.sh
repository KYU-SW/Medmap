#!/usr/bin/env bash
# STEP28.8 2회 재현 — 결정적 산출물 SHA 비교(latency·manifest·verdict·report 제외).
set -euo pipefail
D="$(cd "$(dirname "$0")" && pwd)"
DET="outputs/evaluator_validation.json data/index_core_tokens.csv data/held_keys.csv data/eval_rows.csv outputs/policy_comparison.csv outputs/coverage_precision_tradeoff.csv outputs/eval_summary.json outputs/unit_tests.json outputs/supported12_detail.json outputs/error_analysis.csv outputs/negative_risk_analysis.csv outputs/error_summary.json outputs/protected_check.json"
for i in 1 2; do
  bash "$D/run_all.sh" > "$D/logs/run$i.log" 2>&1
  (cd "$D" && sha256sum $DET > "logs/sha$i.txt")
done
if cmp -s "$D/logs/sha1.txt" "$D/logs/sha2.txt"; then echo SHA_IDENTICAL >> "$D/logs/run2.log"; else echo SHA_DIFF >> "$D/logs/run2.log"; diff "$D/logs/sha1.txt" "$D/logs/sha2.txt" >> "$D/logs/run2.log" || true; fi
echo DONE >> "$D/logs/run2.log"
