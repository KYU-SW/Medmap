# STEP 15 v2 EVALUATOR FIX REPORT

PREVIOUS_EVALUATION_STATUS = INVALID_FOR_DECISION_DUE_TO_EVALUATOR_BUGS

PREVIOUS_DECISION = STOP_EXTERNAL_VERIFIER

FIXED_DECISION = QUESTION_ENGINE_FIRST

## Validity

- Independence violation: False
- Freeze integrity: VALID; modified files: none
- TEST patient reads: 0
- Pilot diseases present: 10/10

## Coverage

- Existing KG strict: 0.0515
- v2 BASIC strict / lenient: 0.2268 / 0.4536
- v2 VALUE strict / lenient: 0.1127 / 0.4225
- Largest strict gain: Acute rhinosinusitis (0.3636)

## Pair observability

- Medically discriminative frozen features: 13
- Experimentally observable in DDXPlus: 8
- Missing discriminative features: 5

## Decision

**QUESTION_ENGINE_FIRST**

The repaired profile improves disease-side strict coverage over the corrected old KG, but explicit missing pair discriminators outnumber strictly observable pair attributes.

The repaired decision does not use the earlier single numeric cutoff. It combines corrected disease-side overlap with the row-level manual pair audit. It does not evaluate TEST performance or a verifier score.

## Main limitation

Automated disease-evidence mappings remain hypotheses, not clinician adjudications. Every pair feature is separately readable in `03_pair_feature_manual_audit.csv`.
