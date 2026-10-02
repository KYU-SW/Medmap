# STEP 15 v2 EVALUATION REPORT

## Validity

- Independence violation: False
- Freeze integrity: VALID; modified files: none
- TEST patient reads: 0
- Pilot diseases present: 10/10

## Coverage

- Existing KG strict: 0.2732
- v2 BASIC strict / lenient: 0.2371 / 0.4433
- v2 VALUE strict / lenient: 0.0645 / 0.3871
- Largest strict gain: Acute laryngitis (0.4000)

## Pair observability

- Medically discriminative frozen features: 13
- Experimentally observable in DDXPlus: 6
- Missing discriminative features: 7

## Decision

**STOP_EXTERNAL_VERIFIER**

The decision used thresholds fixed in the evaluator before reading aggregate results. It does not evaluate TEST performance or a verifier score.

## Main limitation

Automated conservative mappings remain hypotheses, not clinician adjudications. Rows marked for HIGH review can change coverage and pair-observability counts; they are isolated in `11_evaluation_critical_review_queue.csv`.
