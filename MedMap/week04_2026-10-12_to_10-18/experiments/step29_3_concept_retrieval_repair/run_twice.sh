#!/usr/bin/env bash
# 전체 결과 2회 재현: run_all 두 번 → 결과 파일 SHA 비교(latency.json·memory.json 은 측정값이라 제외).
set -euo pipefail
D="$(cd "$(dirname "$0")" && pwd)"
F="outputs/eval_summary.json outputs/eval_errors.csv outputs/regression_cases_result.csv outputs/dev_policy_metrics.json outputs/dev_errors.csv outputs/baseline_reproduction.json outputs/failure_taxonomy.csv outputs/failure_taxonomy_summary.json outputs/policy_comparison.csv outputs/normalization_ablation.csv outputs/precision_coverage_tradeoff.csv outputs/semantic_disambiguation.csv outputs/unsupported_input_analysis.csv outputs/multi_span_regression.csv outputs/error_summary.json outputs/unit_tests.json outputs/protected_check.json data/development_cases.json data/frozen_evaluation_cases.json data/regression_cases.json data/prereg_gates.json data/policy_freeze.json"
for i in 1 2; do
  bash "$D/run_all.sh" > "$D/logs/run$i.log" 2>&1
  (cd "$D" && sha256sum $F) > "$D/logs/sha$i.txt"
done
if diff -q "$D/logs/sha1.txt" "$D/logs/sha2.txt" >/dev/null; then echo SHA_IDENTICAL; else echo SHA_DIFFERENT; diff "$D/logs/sha1.txt" "$D/logs/sha2.txt" || true; fi
