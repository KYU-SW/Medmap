# STEP 16A Next Information Selection Pilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and audit a TEST-locked, preregistered 10-disease development-validation experiment comparing Random, TRAIN-only Internal IG, and frozen external Profile next-information selectors.

**Architecture:** A guarded I/O layer separates split access; a canonical answer-state encoder keeps negative distinct from unasked; three independently reproduced k-specific TRAIN-only logistic baselines feed pure selector functions; and a simulator alone owns hidden-answer reveal. Preparation and preregistration are separate commands from VALIDATION execution, and a final audit independently recomputes the reported metrics.

**Tech Stack:** Python 3, pandas, NumPy, SciPy sparse matrices, scikit-learn LogisticRegression, pytest, standard-library dataclasses/json/hashlib/pathlib.

**Spec:** `docs/step16a_next_information_spec.md`

## Global Constraints

- Never modify any Step8–15 artifact.
- Never import or execute `exp/step13_aprime/step13_prepare.py`.
- Use pathology classes from TRAIN labels. Restrict `release_conditions.json` to `condition_name` and `cond-name-eng`, with `cond-name-fr` permitted only for an explicit alias check; forbid every other field and all disease-feature use in contrast generation, mapping, scoring, selector design, and prioritization.
- TEST patient files permit path existence checking only; any other access stops with `STEP16A_INVALID_TEST_ACCESS`.
- Do not open VALIDATION patient data until both preregistration files exist and their recorded SHA256 values verify.
- Do not compute VALIDATION accuracy, recovery, error pairs, eligibility outcomes, or selector comparisons before preregistration freeze.
- `missing != negative`; all visible and newly revealed answers use the same canonical encoder.
- Fit three independent `MODEL_k3`, `MODEL_k5`, and `MODEL_k10` baselines and Internal IG distributions from TRAIN only; do not pool models or tune against VALIDATION.
- Profile scoring treats an absent external relation as `UNKNOWN`, never negative.
- Candidate membership and view sampling use preregistered question-level `GLOBAL_SIMULATABLE` only and never inspect patient hidden answers.
- At the shared initial state, 1Q COMMON_POOL candidate IDs must be identical for Random, Internal IG, and Primary `PROFILE_FACT_ONLY`. In 3Q, identical state/pair must yield an identical pool, while different trajectories/pairs may yield different pools.
- Select first, reveal second, and never retrain the model after a question.
- Preserve invalid runs and start a new preregistration for corrected runs.

## Review Focus

- A question must be globally non-simulatable unless every normal answer state is reconstructable from definitions/TRAIN semantics; Task 2 tests mixed-state questions and Task 3 tests hidden-answer-independent sampling.
- A categorical default or empty value must not silently become a real answer; Task 2 tests explicit, default, and ambiguous cases.
- A nested forbidden field must not bypass the selector schema; Task 6 tests top-level and nested leakage.
- Sequential pool rebuilding must not reintroduce an asked question after top1/top2 changes; Task 7 tests the changing-pair case.
- At the shared Q1 state, equal COMMON_POOL membership with different ordering must canonicalize identically and unequal membership must invalidate. At Q2/Q3, same state/pair must preserve identity while different trajectories/pairs may differ; Tasks 5 and 7 test both rules.
- A forbidden `release_conditions.json` disease-feature field must be rejected and audited; Task 1 tests allowed name fields and forbidden feature fields.

---

## File map

Create under `exp/step16a_next_information/`:

- `step16a_guard.py`: audited path access, split gate, condition-file field allowlist, immutable-input fingerprints, run-invalid exceptions.
- `step16a_answers.py`: DDXPlus token parsing, semantics audit, canonical `AnswerState`, answer reconstruction, sparse encoding.
- `step16a_views.py`: deterministic STEP16A_NEW_VIEW_PROTOCOL for TRAIN and post-freeze VALIDATION.
- `step16a_model.py`: three independent fixed k-specific logistic-regression models and posterior/rank inference.
- `step16a_pools.py`: pilot-name normalization, fact/concept-only automatic contrasts, COMMON_POOL/FULL_POOL construction, curated-pair secondary sensitivity, unobservable opportunities.
- `step16a_selectors.py`: Random, Internal IG, Profile, and secondary Hybrid selectors.
- `step16a_simulator.py`: immutable selector interface, reveal boundary, 1Q/3Q state machine, result records.
- `step16a_metrics.py`: eligibility layers, endpoints, harms, ranks, coverage, paired bootstrap, deterministic examples.
- `step16a_prepare.py`: structure audit, integrity snapshot, TRAIN-only preparation, preregistration generation/freeze.
- `step16a_run.py`: post-freeze VALIDATION opening and experimental execution.
- `step16a_audit.py`: independent final verification and report/summary generation.
- `test_step16a_guard.py`, `test_step16a_answers.py`, `test_step16a_views.py`, `test_step16a_model.py`, `test_step16a_pools.py`, `test_step16a_selectors.py`, `test_step16a_simulator.py`, `test_step16a_metrics.py`, `test_step16a_end_to_end.py`.

Do not modify existing source files. Reproduce from `exp/step2_3_workingdx/build_working_dx.py` only the TRAIN-only split discipline, age/sex features, fixed LogisticRegression family, initial-evidence preservation, `k3/k5/k10`, and seeds 42/43/44. Train a separate model for each k. Do not reuse its result files. Do not reuse `step13_prepare.py` because it loads TEST. Read the Step15 frozen inputs and fixed evaluator files only through the guarded read layer. Use `04_external_pair_differences.csv` only for the labeled secondary sensitivity analysis.

## Task 1: Guarded I/O and immutable-input integrity

**Files:** Create `step16a_guard.py`, `test_step16a_guard.py`.

**Interfaces:** Produce `Step16AInvalid(code, path)`, `AccessLedger`, `assert_allowed_path(path, operation, phase)`, `test_path_exists(path)`, `read_condition_names(path, allowed_fields)`, `guarded_open(path, mode, phase)`, `fingerprint_inputs(paths)`, and `verify_preregistration_freeze(output_dir)`.

- [ ] Write failing tests proving: TEST existence returns only Boolean; TEST open/hash/statistics calls raise `STEP16A_INVALID_TEST_ACCESS`; VALIDATION patient open in phase `PRE_FREEZE` raises `STEP16A_INVALID_PREREGISTRATION_ORDER`; condition-name existence/name-alias reads are allowed and recorded field-by-field; condition `symptoms`, `antecedents`, evidence, probability, differential, and disease-feature fields are rejected; frozen-file fingerprints detect hash or mtime change; preregistration verification rejects missing/mismatched hashes.
- [ ] Run `cd ~/medmap && pytest -q exp/step16a_next_information/test_step16a_guard.py`; require failures caused by missing guard behavior, not fixture errors.
- [ ] Implement the guard with explicit normalized paths, a condition-file field allowlist, and an append-only in-memory/read-audit ledger. Keep TEST existence checking in a dedicated function that returns no size, mtime, hash, contents, or handle.
- [ ] Rerun the Task 1 test command; stop on any failure.
- [ ] Run `git diff --name-only` and stop if any Step8–15 path appears as modified.

## Task 2: Answer semantics and canonical encoding

**Files:** Create `step16a_answers.py`, `test_step16a_answers.py`; generate `01_answer_semantics_audit.md` only through `step16a_prepare.py` later.

**Interfaces:** Produce `AnswerKind`, immutable `AnswerState`, `parse_ddxplus_token(token)`, `audit_semantics(definitions, train_rows)`, `global_simulatable(question_id, semantics)`, `reconstruct_answer(question_id, full_record, semantics)`, and `AnswerEncoder.fit(train_states)/transform(states)`.

- [ ] Write failing literal-fixture tests for `E_91`, multi-value tokens such as `E_55_@_V_89`, numeric-valued tokens, explicit binary negative, unasked, ambiguous absence, malformed tokens, and categorical defaults. Assert `UNASKED` activates no POS/NEG column, `BINARY_NEGATIVE` activates only `Q::<id>::NEG`, and a question is globally simulatable only when every permitted normal state is reconstructable.
- [ ] Run `cd ~/medmap && pytest -q exp/step16a_next_information/test_step16a_answers.py`; require the expected missing-function/behavior failures.
- [ ] Implement token parsing, semantics evidence recording from `release_evidences.json` plus TRAIN structure, conservative reconstruction, and the single encoder used by old and newly revealed answers. Obtain classes from TRAIN labels and do not consume condition disease features.
- [ ] Rerun the Task 2 tests; stop if any ambiguous absence becomes negative or any default is inferred without audit support.
- [ ] Run `pytest -q exp/step16a_next_information/test_step16a_guard.py exp/step16a_next_information/test_step16a_answers.py`; stop on any failure.

## Task 3: Deterministic partial views

**Files:** Create `step16a_views.py`, `test_step16a_views.py`.

**Interfaces:** Produce `ViewConfig(k, seed)`, `stable_patient_rng(split, seed, patient_index)`, and `sample_question_ids(patient_public_id, config, global_question_ids)` plus a private simulator reveal operation. Visible states, private hidden-answer store, asked IDs, and audit events remain separate objects.

- [ ] Write failing tests proving initial evidence is visible, exactly k distinct globally simulatable question IDs are sampled before any hidden-answer read, seeds are reproducible, different view seeds can differ, patient-level answer presence/value cannot affect membership, unexpected reveal failure does not trigger replacement, truth is absent from the visible object, and all selectors reuse the same serialized view.
- [ ] Run `cd ~/medmap && pytest -q exp/step16a_next_information/test_step16a_views.py`; require expected behavioral failures.
- [ ] Implement the stable per-patient RNG and `k3/k5/k10` configurations with seeds 42/43/44. Set `STEP16A_NEW_VIEW_PROTOCOL=true` in the serializable config.
- [ ] Rerun Task 3 tests and then `pytest -q exp/step16a_next_information/test_step16a_{guard,answers,views}.py`; stop on failure.

## Task 4: Fixed k-specific TRAIN-only diagnostic models

**Files:** Create `step16a_model.py`, `test_step16a_model.py`.

**Interfaces:** Produce `ModelConfig(C=1.0,max_iter=300,solver="lbfgs",random_state=42)`, `fit_diagnosis_models({k: train_views}, labels, encoder, config)` returning exactly `MODEL_k3`, `MODEL_k5`, `MODEL_k10`, and `predict_state(model_for_k, visible_states, demographics)` returning posterior/top1/top2/top3/ranks without carrying truth into selector data.

- [ ] Write failing synthetic-data tests proving each model sees only its matching TRAIN k views, no pooled model exists, each VALIDATION config routes to its matching model, deterministic fits match, negative and unasked differ, and prediction after a reveal reuses the same model without calling fit.
- [ ] Run `cd ~/medmap && pytest -q exp/step16a_next_information/test_step16a_model.py`; require failures for the absent implementation.
- [ ] Implement the sparse multinomial logistic baseline without tuning hooks or VALIDATION inputs.
- [ ] Rerun Task 4 tests and the accumulated suite; stop on convergence failure, nondeterminism, fit-after-reveal, or any test failure.

## Task 5: Open-world discriminators and candidate pools

**Files:** Create `step16a_pools.py`, `test_step16a_pools.py`.

**Interfaces:** Produce `normalize_pilot_names(exact_names, aliases)`, `build_fact_only_contrasts(profile_facts, profile_concepts)`, `build_curated_secondary_contrasts(pair_audit)`, `build_common_pool(pair, visible, mapping, global_simulatable_ids)`, `build_full_pool(visible, evidence_defs, global_simulatable_ids)`, and `assert_common_pool_identity(selector_pools)`.

- [ ] Write failing tests for automatic fact/concept explicit contrast, explicit positive-negative, one-sided unknown, hidden-answer-independent membership, already asked exclusion, globally non-simulatable exclusion, deterministic evidence-ID ordering, shared-Q1 equal-list acceptance, shared-Q1 unequal-list invalidation, same-state/same-pair identity, different-state/different-pair divergence acceptance, and strict separation of curated secondary contrasts from Primary.
- [ ] Run `cd ~/medmap && pytest -q exp/step16a_next_information/test_step16a_pools.py`; require expected failures.
- [ ] Implement strict exact/explicit-alias name resolution, open-world contrast rules, both pools, and unobservable-opportunity records.
- [ ] Rerun Task 5 tests and accumulated suite; stop if fuzzy matching or one-sided-negative behavior appears.

## Task 6: Pure selector implementations and leakage schema

**Files:** Create `step16a_selectors.py`, `test_step16a_selectors.py`.

**Interfaces:** Produce frozen `CandidateQuestion`, frozen `SelectorInput`, `validate_selector_input(payload)`, `select_random`, `fit_train_answer_distributions`, `score_internal_ig` with all preregistered formula parameters explicit, `select_internal_ig`, `select_profile_fact_only`, `select_profile_fact_plus_curated_secondary`, and `select_hybrid`.

- [ ] Write failing tests proving top-level and nested forbidden fields are rejected; candidates contain no answer; Random stays in-pool and is seed-reproducible; IG uses only injected TRAIN distributions; Profile priority/tie-break works; one-sided unknown scores zero; Hybrid filters then uses IG; empty Profile set returns `ABSTAIN`.
- [ ] Run `cd ~/medmap && pytest -q exp/step16a_next_information/test_step16a_selectors.py`; require expected failures.
- [ ] Implement selectors as pure functions. Define the exact IG entropy formula, answer predictive probability, `P(answer | disease)` estimator, Laplace smoothing value, impossible-answer behavior, log base, and tie-break as explicit configuration fields consumed by Task 9 preregistration; prohibit fallback access to patient records.
- [ ] Rerun Task 6 tests and accumulated suite; stop on forbidden-field acceptance, out-of-pool selection, or nondeterministic ties.

## Task 7: Select-before-reveal sequential simulator

**Files:** Create `step16a_simulator.py`, `test_step16a_simulator.py`.

**Interfaces:** Produce `EvaluationCase` with truth/full answers private to simulator, `run_one_question(case, selector, model, pool_builder)`, and `run_three_questions(...)` returning audit events and posteriors.

- [ ] Write failing tests with a spy hidden-answer store proving zero reads during view sampling, pool membership, and selection; exactly one selected-answer read afterward; no truth/full evidence in selector payload; unexpected reconstruction failure records audit failure without substitute selection; posterior recomputation uses the same k-specific model; no refit; no repeated question after pair change; identical state/pair yields identical canonical pools across selectors; different Q2/Q3 trajectories may yield different pools without invalidation; and abstention stops Profile early.
- [ ] Run `cd ~/medmap && pytest -q exp/step16a_next_information/test_step16a_simulator.py`; require ordering failures before implementation.
- [ ] Implement the state machine and append-only events `MODEL_BEFORE`, `SELECTOR_INPUT`, `SELECTED`, `ANSWER_REVEALED`, `MODEL_AFTER`.
- [ ] Rerun Task 7 tests and accumulated suite; stop if event order differs or hidden-store reads precede `SELECTED`.

## Task 8: Metrics, paired bootstrap, and deterministic examples

**Files:** Create `step16a_metrics.py`, `test_step16a_metrics.py`.

**Interfaces:** Produce `label_eligibility`, `compute_selector_metrics`, `paired_bootstrap_difference(n_boot=1000,seed=42)`, `direct_recompute_checks`, and `select_examples`.

- [ ] Write failing hand-calculated fixture tests for RECOVERY@1Q/@3Q; CORRECT_TO_WRONG@1Q/@3Q on COMMON_POOL ∩ initially correct ∩ SIMULATABLE with N; net accuracy change; rank; top3; abstention; coverage; questions asked; truth-in-top2/top3; exact separate denominators; Random 50-draw patient/view averaging; per-view patient bootstrap; pooled patient-cluster bootstrap carrying all k and view-seed rows together; and first-three deterministic case selection.
- [ ] Run `cd ~/medmap && pytest -q exp/step16a_next_information/test_step16a_metrics.py`; require expected failures.
- [ ] Implement metrics without importing selector code. Average Random's 50 seeds before paired comparisons, never count Random/view repetitions as independent N, and keep COMMON_POOL/FULL_POOL rows explicitly separate. Do not introduce or change any IG formula in this task.
- [ ] Rerun Task 8 tests and accumulated suite; stop on denominator or hand-calculation mismatch.

## Task 9: Prepare code, full synthetic gate, real structure audit, and final preregistration freeze

**Files:** Create `step16a_prepare.py`, `test_step16a_end_to_end.py`; generate `00_input_integrity.json`, `01_answer_semantics_audit.md`, `00_STEP16A_PREREGISTRATION.md`, `00_step16a_rules.json`, `READ_FILES_AUDIT.txt`.

**Interfaces:** Command `python exp/step16a_next_information/step16a_prepare.py --phase structure-audit` performs definitions/TRAIN-only structure work; command `python .../step16a_prepare.py --phase freeze` writes and hashes preregistration without opening VALIDATION.

- [ ] Write a failing end-to-end fixture test whose guarded fake filesystem contains TRAIN, evidence definitions, an allowlisted condition-name fixture, forbidden condition disease-feature fields, profile inputs, evaluator inputs, VALIDATION, and a TEST sentinel. Assert preparation rejects forbidden condition fields, records permitted fields, never opens VALIDATION or TEST, emits no metric output, and produces verifiable preregistration hashes.
- [ ] Run `cd ~/medmap && pytest -q exp/step16a_next_information/test_step16a_end_to_end.py -k prepare`; require expected failures.
- [ ] Implement both prepare phases, exact k-specific model/encoding/view/global-simulatability/pool/selector/metric rules, the complete IG formula configuration from Task 6, input hash+mtime snapshot, and field-level read-file audit.
- [ ] Run the prepare fixture test and every Task 1–9 unit, synthetic, and integration test; stop unless the full suite is green with zero real VALIDATION patient reads and zero TEST reads.
- [ ] Stop and obtain the separate human approval that permits real TRAIN/definitions structure audit and preregistration preparation. This approval still does not permit VALIDATION access.
- [ ] Run `cd ~/medmap && python exp/step16a_next_information/step16a_prepare.py --phase structure-audit` using TRAIN, `release_evidences.json`, permitted condition-name fields only when necessary, frozen profile inputs, and fixed evaluator inputs.
- [ ] Review `01_answer_semantics_audit.md`; stop as `STEP16A_BLOCKED` if binary/categorical answers cannot be reconstructed for any defensible globally simulatable question set without guessing.
- [ ] Run `python exp/step16a_next_information/step16a_prepare.py --phase freeze` and then `python -m exp.step16a_next_information.step16a_guard --verify-preregistration exp/step16a_next_information`.
- [ ] Record the two preregistration SHA256 values. Confirm the entropy formula, answer predictive probability, `P(answer | disease)`, Laplace value, impossible-answer handling, log base, and tie-break appear in both frozen files. From this exact point, score formulae, encoding, model config, pools, subsets, endpoints, tie-breaks, and seeds are immutable.
- [ ] Report and then stop: answer-semantics conclusion; `GLOBAL_SIMULATABLE` question count; k-specific TRAIN model settings; exact Internal IG formula; Laplace value; candidate-pool and selector definitions; Primary population and endpoint; Random/view seeds; bootstrap method; invalid conditions; both preregistration SHA256 values; TEST read count; and VALIDATION patient read count. Require both read counts to be 0. Do not proceed until the user explicitly says `STEP16A_RUN1 실행 승인`.

## Task 10: Post-freeze VALIDATION runner

**Files:** Create `step16a_run.py`; extend `test_step16a_end_to_end.py`; generate output CSV/JSON files 02–10.

**Interfaces:** Command `python exp/step16a_next_information/step16a_run.py --run-id STEP16A_RUN1` first verifies preregistration and input integrity, then and only then opens VALIDATION.

- [ ] Extend the end-to-end fixture test so a mismatched preregistration hash prevents any VALIDATION open, while a valid hash produces all selector/view/pool result schemas and never touches the TEST sentinel.
- [ ] Run `cd ~/medmap && pytest -q exp/step16a_next_information/test_step16a_end_to_end.py -k run`; require expected failures.
- [ ] Implement the runner with 3 view seeds, Random seeds 1000–1049 aggregated at patient/view level, k-matched models, `PROFILE_FACT_ONLY` primary, curated-pair and Hybrid secondary analyses, 1Q/3Q, COMMON_POOL primary, FULL_POOL secondary, leakage dumps, and atomic run-status writing.
- [ ] Rerun the end-to-end and full STEP16A test suite. Stop on any failure.
- [ ] **First real VALIDATION open occurs here and nowhere earlier:** run `cd ~/medmap && python exp/step16a_next_information/step16a_run.py --run-id STEP16A_RUN1` only after the frozen preregistration report has been delivered, VALIDATION patient read count is confirmed as 0, and the user explicitly gives post-preregistration approval with `STEP16A_RUN1 실행 승인`. Design approval, implementation approval, or structure-audit approval is not sufficient.
- [ ] Stop immediately and preserve outputs if the runner emits any `STEP16A_INVALID_*` state.

## Task 11: Independent final audit and report

**Files:** Create `step16a_audit.py`; generate `11_error_case_examples.csv`, `12_summary.json`, `PROVENANCE.md`, `STEP16A_REPORT.md`; update only STEP16A-owned `READ_FILES_AUDIT.txt`.

**Interfaces:** Command `python exp/step16a_next_information/step16a_audit.py --run-id STEP16A_RUN1 --strict` exits nonzero on any unmet invariant.

- [ ] Add failing integration tests that deliberately inject TEST access, early reveal, truth leakage, validation-in-training, duplicate questions, changed frozen hash, NaN, row-count mismatch, denominator mismatch, and altered bootstrap seed; assert each is independently detected.
- [ ] Run `cd ~/medmap && pytest -q exp/step16a_next_information/test_step16a_end_to_end.py -k audit`; require expected failures.
- [ ] Implement audit checks and direct metric recomputation from question-level rows, not from the summary. Verify global-simulatability independence, Random aggregation, patient-cluster bootstrap, k-model routing, FACT_ONLY/curated separation, frozen IG configuration, separate harm N, and Hybrid-aware interpretation. Generate the report only after every strict check passes.
- [ ] Run `cd ~/medmap && pytest -q exp/step16a_next_information`; require zero failures.
- [ ] Run `python exp/step16a_next_information/step16a_audit.py --run-id STEP16A_RUN1 --strict`; require exit 0 and explicit zero counts for TEST reads, pre-selection hidden reads, selector truth access, validation training rows, duplicate questions, frozen changes, NaN/inf, and metric mismatches.
- [ ] Run `git status --short` and `git diff --name-only`; stop if any Step8–15 file changed.
- [ ] Verify required file presence, SHA256 manifests, patient/view/row counts, denominators, Random seed list, bootstrap reproducibility, and preregistration hashes from fresh commands before making a completion claim.

## Stage gates and stop policy

1. Gate 1 — design-document approval: no implementation or VALIDATION access is permitted until the user approves both documents.
2. Implementation/synthetic phase: Tasks 1–9 code and synthetic/fixture tests are completed without real VALIDATION access.
3. Gate 2 — code and synthetic-test approval: a separate user approval permits the real TRAIN/definitions structure audit and final preregistration freeze; it does not permit VALIDATION access.
4. Gate 3 — frozen preregistration review: after both preregistration SHA256 values verify, report answer semantics, global-simulatable count, k-model settings, exact IG formula and Laplace value, pools/selectors, primary population/endpoint, seeds, bootstrap, invalid conditions, both hashes, TEST read count, and VALIDATION patient read count. Require both counts to be 0 and stop.
5. Evaluation approval: only the explicit post-preregistration phrase `STEP16A_RUN1 실행 승인` permits the first real VALIDATION open in Task 10.
6. Final audit gate: no report decision is valid unless Task 11 strict audit exits 0.

At every task boundary, inspect the access ledger and modified-file list. Any TEST access, early VALIDATION access, leakage, frozen-input change, or Step8–15 modification stops the work without attempting recovery in the same run.
