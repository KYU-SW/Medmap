#!/usr/bin/env bash
# 전체 결과 2회 재현: run_all 을 두 번 실행하고 결과 파일 SHA 를 비교(latency.json 은 시간 측정값이라 제외).
set -euo pipefail
D="$(cd "$(dirname "$0")" && pwd)"
F="outputs/eval_summary.json outputs/eval_errors.csv outputs/dev_policy_metrics.json outputs/dev_errors.csv outputs/evaluator_validation.json outputs/prior_results.json outputs/policy_comparison.csv outputs/b4_guard_ablation.csv outputs/punctuation_pair_results.csv outputs/negation_scope_analysis.csv outputs/resolution_analysis.csv outputs/multi_span_analysis.csv outputs/concept_error_analysis.csv outputs/unsupported_auto_link_analysis.csv outputs/error_summary.json outputs/unit_tests.json outputs/protected_check.json data/dev_pairs.json data/frozen_holdout_pairs.json data/prereg_gates.json data/policy_freeze.json"
for i in 1 2; do
  bash "$D/run_all.sh" > "$D/logs/run$i.log" 2>&1
  (cd "$D" && sha256sum $F) > "$D/logs/sha$i.txt"
done
if diff -q "$D/logs/sha1.txt" "$D/logs/sha2.txt" >/dev/null; then echo SHA_IDENTICAL; else echo SHA_DIFFERENT; diff "$D/logs/sha1.txt" "$D/logs/sha2.txt" || true; fi
