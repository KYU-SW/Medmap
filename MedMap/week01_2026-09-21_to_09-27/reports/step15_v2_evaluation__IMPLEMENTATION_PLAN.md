# STEP 15 v2 Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Independently compare the frozen ten-disease external profiles with original DDXPlus definitions and validation patients without opening test patients or prior interpretive reports.

**Architecture:** One deterministic Python evaluator reads only an explicit allowlist, emits every required CSV/JSON/report, records every opened file, and rechecks frozen hashes and mtimes at the end. A separate pytest module uses synthetic fixtures to pin matching, coverage, observability, and prohibited-file behavior before the evaluator is run on real data.

**Tech Stack:** Python 3 standard library, pandas if already installed, pytest if already installed.

**Spec:** User-provided evaluator brief in the current conversation.

## Global Constraints

- Write only under `exp/step15_v2_evaluation/`; do not modify frozen or existing project files.
- Never read `.claude/`, STEP13/14/15-v1 reports or summaries, prior reviewer/referee interpretations, Guardian conclusions, error-pair interpretations, or DDXPlus test patients.
- Only `exp/step14_value_context_recovery/07_evidence_value_level_map.csv` may be reused for mechanical value mapping, with path, SHA256, and used columns recorded.
- Step13B use is limited to a mechanical strict-edge relation file; if no suitable file can be identified without reading reports, record the comparison as unavailable rather than guessing.
- Mapping states are exactly `DIRECT_MATCH`, `ATTRIBUTE_MATCH`, `PARTIAL_MATCH`, `NO_MATCH`, `NOT_APPLICABLE`; partial matches never enter strict coverage.
- Do not add medical knowledge from the web or from DDXPlus into the frozen profile.
- Use validation patients only for patient-level observability; never open or hash test patient contents.
- Seed is fixed and all outputs are deterministic.

## Review Focus

- An ambiguous disease name must remain `review_needed=true`, never be fuzzy-confirmed.
- A base-concept overlap with a missing or conflicting attribute must be `PARTIAL_MATCH`, not direct or attribute.
- Denominators must exclude `NOT_APPLICABLE`, and strict numerators must exclude `PARTIAL_MATCH`.
- Pair features can be medically discriminative while experimentally unobservable.
- The file-open audit must catch any forbidden path and make the independent result invalid.

---

### Task 1: Integrity and guarded input layer

**Files:**
- Create: `exp/step15_v2_evaluation/test_step15v2_evaluate.py`
- Create: `exp/step15_v2_evaluation/step15v2_evaluate.py`
- Create: `exp/step15_v2_evaluation/00_freeze_integrity.json`

**Interfaces:**
- Produces: `AuditedReader`, `sha256_file(path)`, `verify_freeze(profile_dir, output_path)`.
- Consumes: `PROFILE_FREEZE_V2.json` and the seven required frozen CSV files.

- [ ] Write tests proving matching hashes pass, a changed byte fails with `STEP15V2_EVAL_INVALID_FREEZE`, and forbidden/test paths are rejected before opening.
- [ ] Run the focused pytest tests and confirm they fail because the implementation does not exist.
- [ ] Implement the guarded reader and freeze verification with initial SHA256 plus mtime snapshots.
- [ ] Run the focused tests and confirm they pass.
- [ ] Run real freeze verification and stop immediately if any file differs.

### Task 2: DDXPlus schema and deterministic normalization

**Files:**
- Modify: `exp/step15_v2_evaluation/test_step15v2_evaluate.py`
- Modify: `exp/step15_v2_evaluation/step15v2_evaluate.py`
- Create: `exp/step15_v2_evaluation/01_ddxplus_schema_audit.json`

**Interfaces:**
- Produces: `normalize_name`, `parse_evidence_catalog`, `audit_ddx_schema`, and explicit ten-disease name mapping.
- Consumes: English `release_conditions.json`, `release_evidences.json`, train/validate path metadata without test-patient reads.

- [ ] Add synthetic tests for binary versus categorical evidence, possible values, duplicate evidence IDs, and exact/normalized/ambiguous disease names.
- [ ] Run the focused tests and confirm the new tests fail for missing behavior.
- [ ] Implement parsing and schema audit without hardcoded dataset totals.
- [ ] Run focused tests and the complete evaluator test file.
- [ ] Audit the real DDXPlus definitions and record paths and hashes.

### Task 3: Profile mapping and coverage

**Files:**
- Modify: `exp/step15_v2_evaluation/test_step15v2_evaluate.py`
- Modify: `exp/step15_v2_evaluation/step15v2_evaluate.py`
- Create: `02_ddxplus_profile_mapping.csv`, `03_disease_coverage.csv`, `04_before_after_knowledge_coverage.csv`.

**Interfaces:**
- Produces: `classify_match`, `map_profile_to_evidence`, `summarize_coverage`, `compare_old_kg`.
- Consumes: frozen facts/concepts, structured DDXPlus evidence, optional Step14 mechanical mapping, optional Step13B strict relation matrix.

- [ ] Add hand-checked fixture tests for each mapping status, base-only versus value-level matching, and strict/lenient formulas.
- [ ] Run tests and confirm failures identify the absent classification and aggregation behavior.
- [ ] Implement conservative matching with reasons, review flags, and no fuzzy auto-confirmation.
- [ ] Run tests and inspect all real mapping rows requiring review.
- [ ] Emit mapping and coverage tables; mark old-KG fields unavailable if no eligible edge file is identifiable.

### Task 4: Pair, missing-information, and validation observability audits

**Files:**
- Modify: evaluator and tests.
- Create: `05_pair_observability.csv` through `11_evaluation_critical_review_queue.csv`.

**Interfaces:**
- Produces: `audit_pairs`, `extract_missing_features`, `validation_observability`, `prioritize_review`.
- Consumes: frozen pair differences, completed mapping, validation patients, and available k3/k5/k10/all configuration artifacts that are not reports or test outputs.

- [ ] Add tests that distinguish medically discriminative from experimentally observable features and calculate patient statistics including zero-matchable rate.
- [ ] Run tests and confirm the new tests fail.
- [ ] Implement pair/missing/question-category/revision/review-queue outputs.
- [ ] Implement validation-only patient observability; if configurations or predictions are unavailable, emit explicit unavailable rows rather than fabricate values.
- [ ] Run the full evaluator test file and validate required columns and no NaN/inf.

### Task 5: Decision, provenance, independence, and final verification

**Files:**
- Modify: evaluator and tests.
- Create: `12_summary.json`, `PROVENANCE.md`, `READ_FILES_AUDIT.txt`, `STEP15V2_EVALUATION_REPORT.md`, output hash manifest.

**Interfaces:**
- Produces: transparent one-of-three direction decision, final validation gate, and full read/output audits.
- Consumes: all generated outputs and initial freeze snapshot.

- [ ] Add tests for deterministic direction rules fixed before real result inspection, independence invalidation, required output presence, and post-run freeze drift detection.
- [ ] Run tests and confirm they fail for missing finalization behavior.
- [ ] Implement final decision and provenance/report generation, including Python version, pip freeze, command, seed, timestamp, Git state, and exact columns read from reused mechanical files.
- [ ] Run the evaluator on real inputs without test patients, then rerun the complete test file.
- [ ] Independently recalculate key counts, verify all output hashes, compare frozen pre/post SHA256 and mtimes, scan for NaN/inf and duplicates, and review mappings for exaggeration before reporting.

## Self-review

- Spec coverage: all required numbered outputs, audit files, freeze checks, validation-only constraints, and final decision are assigned above.
- Placeholder scan: no implementation placeholder is used; unavailable optional inputs must be represented explicitly and never guessed.
- Type consistency: the mapping rows feed coverage, pair observability, validation observability, review priority, summary, and report generation.
- Review-focus tests: each of the five listed failure modes is assigned to Tasks 1-5.
