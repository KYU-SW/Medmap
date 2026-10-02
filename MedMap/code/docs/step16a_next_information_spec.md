# STEP 16A — Next Information Selection Pilot Specification

## 1. Purpose and research question

STEP16A tests one development-validation question:

> Given a partial patient view and the current working diagnosis, does selecting the next observable clinical information with an independently frozen external disease profile help recover diagnostic errors?

The evaluated chain is: visible information → fixed diagnostic model → working diagnosis and alternatives → select one still-unasked discriminator → reveal only that answer → rerun the same model. This is not a natural-language generation study. DDXPlus `question_en` text is used without rewriting.

The experiment is a 10-disease feasibility pilot. It must not be described as final proof. The only permitted interpretation is whether a feasibility signal is or is not observed on development VALIDATION.

## 2. Immutable inputs and write boundary

Read-only inputs:

- `exp/step15_v2_blind_profile/PROFILE_FREEZE_V2.json`
- `exp/step15_v2_blind_profile/01_disease_profile_facts.csv`
- `exp/step15_v2_blind_profile/02_disease_profile_concepts.csv`
- `exp/step15_v2_blind_profile/04_external_pair_differences.csv`, secondary sensitivity analysis only
- the named mechanical mapping and audit files in `exp/step15_v2_evaluation_fix/`
- `data/ddxplus/en/release_train_patients`
- `data/ddxplus/en/release_validate_patients`, but only after the preregistration freeze gate
- `data/ddxplus/en/release_evidences.json`
- `data/ddxplus/en/release_conditions.json`, restricted to exact condition-name existence checks through `condition_name` and `cond-name-eng`; `cond-name-fr` is permitted only if an explicit alias check requires it

All STEP16A code and results are written only beneath `exp/step16a_next_information/`. Documentation is written beneath `docs/`. No Step8–15 file may be modified. Input SHA256 and mtime are captured before work and rechecked after the final audit.

## 3. Split roles and TEST lock

- TRAIN: fit the fixed diagnostic model and calculate disease-conditional answer distributions used by Internal IG. TRAIN may also be used to validate the mechanics of answer encoding.
- VALIDATION: after preregistration freeze, create evaluation views, run selectors, reveal answers, and calculate metrics.
- TEST: locked. Only a path-existence check is allowed. Opening, reading, hashing, obtaining metadata for analysis, loading, predicting, calculating statistics, or selecting features from a TEST patient file is forbidden.

Every project file access goes through an audited path guard. A TEST patient path passed to an open/load/hash/statistics function raises `STEP16A_INVALID_TEST_ACCESS`, writes the invalid state to the run ledger if possible, and stops the run. The existence check records only a Boolean and must not open the path. No code from `exp/step13_aprime/step13_prepare.py` is imported or executed because it reads TEST.

`release_conditions.json` is not a disease-feature source. Its `symptoms`, `antecedents`, evidence lists, probabilities, differential information, disease-to-evidence relationships, and other disease feature fields are forbidden for Profile contrast generation, profile mapping, candidate scoring, selector design, or question prioritization. Pathology classes come from TRAIN labels. If the condition file is opened for name verification, the exact fields read are recorded in `READ_FILES_AUDIT.txt`; the guarded reader allowlists only `condition_name`, `cond-name-eng`, and conditionally `cond-name-fr`, and rejects every other field.

## 4. Phase boundary and preregistration gate

There are four strictly ordered phases with separate human gates.

1. Implementation and synthetic verification: after design-document approval, implement Tasks 1–6, the simulator, metrics/bootstrap, and prepare/freeze code; all unit, synthetic, fixture, and integration tests must pass without real VALIDATION access.
2. Structure-only preparation: after a separate human approval, inspect definitions and TRAIN structure; determine answer semantics without computing VALIDATION accuracy, recovery, error pairs, eligibility outcomes, or selector performance.
3. Preregistration: only after the code and synthetic tests are stable, write `00_STEP16A_PREREGISTRATION.md` and `00_step16a_rules.json`; fix exact model settings, encoding, partial-view protocol, candidate pools, selector formulae, seeds, subsets, metrics, bootstrap, tie-breaks, and invalid conditions; calculate and record both SHA256 values. Then report the frozen rules, both hashes, TEST read count, and VALIDATION patient read count and stop.
4. Evaluation: only after the user separately says `STEP16A_RUN1 실행 승인` and a gate verifies both preregistration hashes may the program open `release_validate_patients` for the first time.

Any attempt to open VALIDATION patient data before the gate raises `STEP16A_INVALID_PREREGISTRATION_ORDER`. Definitions are not patient results and may be read before the gate. TRAIN-only model/statistic construction may occur before the freeze only for mechanical development; the final evaluation run rebuilds or verifies them under the frozen rules.

## 5. Answer-semantics audit

`01_answer_semantics_audit.md` records only representation facts and their evidence. It uses `release_evidences.json`, TRAIN record structure, and dataset documentation. `release_conditions.json` is not used for answer semantics except a separately audited permitted name check when strictly necessary. It does not calculate any validation result.

The audit determines separately for each DDXPlus data type:

- whether an absent binary evidence means a reproducible explicit negative or unknown/missing;
- whether categorical/multi-select values are stored as `evidence_id_@_value` tokens;
- how `default_value` is represented in patient records;
- whether a hidden answer can be reconstructed without guessing;
- which questions must be marked non-simulatable at the global question level.

An absent token is never automatically interpreted as negative. Binary negative reconstruction is permitted only when the audit establishes that the complete patient record uses closed-world binary semantics. A categorical default is permitted only when it is explicitly stored or the data definition unambiguously guarantees it.

`GLOBAL_SIMULATABLE(question_id)` is decided before any VALIDATION patient record is opened, using only evidence definitions, dataset semantics, and TRAIN structure. It is true only when every normal answer state allowed for that question can be reconstructed without guessing. The decision is frozen in preregistration. Candidate membership and partial-view sampling may consult this question-level flag only; they may not inspect a VALIDATION patient's full record, hidden-answer presence, or actual answer value. If a globally simulatable selected question unexpectedly yields an unreconstructable VALIDATION answer, the simulator records an audit failure and stops that case/run. It must not substitute another question.

## 6. Canonical answer state and feature representation

The internal state for each question is exactly one of:

- `UNASKED`: neither positive, negative, nor value feature is active;
- `BINARY_POSITIVE`: feature `Q::<evidence_id>::POS` is 1;
- `BINARY_NEGATIVE`: feature `Q::<evidence_id>::NEG` is 1;
- `CATEGORICAL_VALUE`: one feature `Q::<evidence_id>::VALUE::<value_id>` is 1 for each explicitly returned value; multi-select questions may activate multiple explicit value features.

`UNASKED` and `BINARY_NEGATIVE` are different vectors. No imputation converts one into the other. If dataset definitions/TRAIN semantics show that any normal answer state is unsupported, malformed, ambiguous, or unreconstructable, the entire question is assigned `GLOBAL_SIMULATABLE=false` before VALIDATION. After freeze, an unexpected unreconstructable selected answer is an audit failure; it never causes patient-level candidate exclusion or replacement.

Age decade and sex use the existing `AGE_<bucket>` and `SEX_<value>` features. All question-answer features are one-hot sparse columns. Already visible answers and newly revealed answers are passed through the same `AnswerState` map and the same encoder. The model is not told whether an answer came from the initial view or a follow-up question.

## 7. STEP16A_NEW_VIEW_PROTOCOL

The existing `build_working_dx.py` is reproducible but its partial view contains only observed evidence tokens; it cannot represent explicit negative versus unasked. It is therefore not copied as the STEP16A view generator. `STEP16A_NEW_VIEW_PROTOCOL` is fixed to `true`.

The new protocol preserves its useful invariants: TRAIN/VALIDATION separation, the initial evidence, configurations `k3`, `k5`, `k10`, and view seeds 42, 43, and 44. For each patient, the initial evidence answer is visible first. From the preregistered `GLOBAL_SIMULATABLE=true` question IDs, exactly `k` distinct question IDs are sampled without replacement by a deterministic RNG keyed by split, view seed, and patient index. Only after selection does the private simulator reveal each selected answer. Patient-level answer presence/value is never used to form the sampling frame. The same generated view is reused by every selector. An unexpected reconstruction failure invalidates the case/run rather than triggering replacement sampling.

TRAIN partial views use the same protocol with training seed 42. VALIDATION views are generated only after preregistration freeze. Truth labels are used to train/evaluate the diagnosis model but never included in a selector input.

## 8. Fixed diagnosis model

Three independent fixed baselines are implemented as multinomial logistic regressions over the sparse one-hot representation:

- `C=1.0`
- `max_iter=300`
- `solver="lbfgs"`
- `random_state=42`
- no VALIDATION-based hyperparameter tuning

`MODEL_k3` is trained only on TRAIN k3 partial views, `MODEL_k5` only on TRAIN k5 views, and `MODEL_k10` only on TRAIN k10 views. A VALIDATION k-config is evaluated only by its matching model. After one or three revealed answers, the same matching model is reused without retraining. Models are never pooled across k and no model is selected or tuned using VALIDATION.

The class list is the sorted TRAIN pathology list. For any visible state the matching model returns the full posterior, top1 working diagnosis, top2 primary alternative, top3 secondary alternative, and true-class rank for evaluation code outside the selector boundary. Exact settings and library versions are frozen in preregistration.

## 9. Pilot diseases and naming

The pilot consists of the ten named diseases in the request. Exact DDXPlus names are matched first. Explicit aliases may be recorded in `00_step16a_rules.json`; fuzzy matching is forbidden. An ambiguous or missing name is an invalid design input and stops before evaluation.

## 10. Candidate questions and open-world handling

A candidate has `evidence_id`, original `question_en`, data type, atomic attributes, mapping status, and pool provenance. Already asked/visible questions and repeated questions are excluded. Answers are never attached to candidates before selection.

Primary Profile eligibility is generated automatically from `01_disease_profile_facts.csv` and `02_disease_profile_concepts.csv` by applying the same general rules to every pilot disease pair. It requires one of:

- `EXPLICIT_CONTRAST`: both diseases explicitly encode the same base concept/attribute with different values, timing, situation, or progression;
- `EXPLICIT_POSITIVE_NEGATIVE`: one disease is explicitly positive and the other explicitly negative;
One-sided absence is `UNKNOWN`, not negative, and receives no profile score. `ONE_SIDED_UNKNOWN` is forbidden in the primary Profile selector.

`04_external_pair_differences.csv` and manually curated pair-feature audit rows are forbidden as Primary selector knowledge. They may be used only in a separately labeled `CURATED_PAIR_AUDIT_SECONDARY` sensitivity analysis fixed before VALIDATION.

## 11. Candidate pools

### COMMON_POOL — primary

For each current top1/top2 pair, COMMON_POOL contains the legal, unasked, globally simulatable DDXPlus questions mapped by the automatic fact/concept rules to an explicit frozen-profile discriminator for that pair. At the shared Q1 initial state, Random, Internal IG, and Primary `PROFILE_FACT_ONLY` receive exactly the same ordered candidate IDs; any difference is invalid. At Q2/Q3, identity is checked only when the serialized visible state and current top1/top2 pair are the same. Membership is computed without reading patient hidden answers.

This answers: when the same questions are available, which selector chooses better?

### FULL_POOL — secondary

FULL_POOL contains every legal, unasked, globally simulatable DDXPlus question. Random and Internal IG may select anywhere in it. Profile may select only questions supported by an explicit profile discriminator and otherwise returns `ABSTAIN`. Membership is independent of the current patient's hidden answer. FULL_POOL results measure practical coverage and are never merged with COMMON_POOL primary results.

## 12. Selectors

### RANDOM

Uniform selection from the current pool. Seeds 1000–1049 produce 50 repeated selector draws per patient × k-config × view-seed. These are Monte Carlo draws, not 50 independent patient observations. Their outcomes are averaged first into one patient/view-level expected Random outcome. Profile − Random pairs Profile's patient/view outcome with that mean. Sequential runs sample without replacement.

### INTERNAL_IG

For each question, TRAIN-only smoothed answer distributions estimate expected posterior entropy after each possible answer. Score is current entropy minus answer-probability-weighted expected entropy. The entropy formula, answer predictive-probability formula, `P(answer | disease)` estimator, Laplace smoothing value, impossible-answer handling, log base, and tie-break are all written to both preregistration files and frozen before VALIDATION is opened. Highest score wins; ties use ascending `evidence_id`.

### PROFILE_FACT_ONLY — primary

Uses only current top1, current top2, frozen profile facts/concepts, the general automatic contrast rules, and unasked candidates. Direct or attribute-level explicit contrast receives priority 2; partial explicit mapping receives priority 1; no explicit contrast receives 0 and is ineligible. Highest priority wins; ties use ascending `evidence_id`. Curated pair-difference knowledge, TRAIN conditional probabilities, truth, patient hidden answers, and case-specific overrides are forbidden.

### PROFILE_FACT_PLUS_CURATED_PAIR_AUDIT — secondary sensitivity only

Adds the preregistered curated pair-audit contrasts to the automatic fact-only contrasts. It is reported separately and cannot replace `PROFILE_FACT_ONLY` as the Primary Profile result.

### PROFILE_IG_HYBRID — secondary only

Filters to explicit profile-discriminator questions and selects the highest TRAIN-only Internal IG within that set. It is not a primary method.

## 13. Selector interface and leakage boundary

Selectors accept only an immutable `SelectorInput` containing:

- anonymized patient/view identifier;
- visible `AnswerState` entries;
- current diagnosis posterior;
- current top1/top2/top3 names;
- answer-free candidate descriptors;
- frozen profile discriminator records needed for the current pair: automatic facts/concepts only for `PROFILE_FACT_ONLY`, and separately labeled curated records only for the secondary sensitivity selector;
- TRAIN-only IG table reference for Internal IG/Hybrid;
- asked-question IDs and deterministic selector seed.

The constructor rejects unknown fields. `true_diagnosis`, `full_patient_evidence`, `hidden_answers`, `future_answer`, any TEST-derived field, and objects containing them are prohibited. A serialized pre-selection dump is schema-checked and recorded in `10_selector_input_leakage_audit.json`. Ground truth remains in a separate evaluation object unavailable to selector modules.

## 14. Reveal boundary and sequential simulation

The simulator owns hidden answers. For every step it enforces this order:

1. encode currently visible state;
2. run the fixed model;
3. build and validate `SelectorInput` without answers;
4. select or abstain;
5. record selection;
6. reveal only the selected question's reconstructable hidden answer;
7. add it to visible `AnswerState`;
8. rerun the same model without retraining.

The 1Q Primary comparison executes one cycle from a shared initial patient/view state. Random, Internal IG, and `PROFILE_FACT_ONLY` must receive identical ordered COMMON_POOL candidate IDs at that initial state.

The 3Q experiment is a secondary trajectory comparison. It executes at most three cycles, recomputing posterior, top1/top2, pool, and selector decision after each reveal. After Q1, selectors may have different answers, posteriors, top1/top2 pairs, and therefore different Q2/Q3 pools. Each selector independently applies the same preregistered pool-construction rule to its own current state. `same state + same pair` must produce the same canonical pool; `different trajectory or different pair` may legitimately produce different pools. A COMMON_POOL identity violation is invalid only when selector-specific construction produces different candidates from the same state and pair. Asked questions cannot recur. Profile stops early with `ABSTAIN` when no explicit discriminator remains.

## 15. Evaluation populations

Every validation view is labeled cumulatively:

- `ALL_VALIDATION`
- `PILOT_TRUE`: truth is one of the ten pilot diseases
- `PILOT_PAIR`: current top1 and top2 both have pilot profiles
- `PROFILE_REACHABLE`: at least one explicit frozen-profile discriminator exists for top1/top2
- `SIMULATABLE`: at least one such discriminator maps to a preregistered `GLOBAL_SIMULATABLE=true` DDXPlus question; this label is determined without inspecting the patient's hidden answer

Counts and percentages are reported at every layer. Selection bias is not hidden.

## 16. Endpoints and metrics

Primary population: COMMON_POOL ∩ initially wrong ∩ SIMULATABLE.

Primary endpoint `RECOVERY@1Q` is the fraction whose initial top1 is wrong and whose top1 becomes the true diagnosis after exactly one revealed answer. Denominators are identical across paired selectors.

Secondary metrics include `RECOVERY@3Q`; top1 accuracy before/after 1Q/3Q; true-diagnosis mean and median rank; top3 inclusion; abstention rate; question coverage; mean questions asked; truth-in-top2 and truth-in-top3 before questioning; and separately stated theoretical/empirical headroom.

For initially correct cases, the Primary harm population is COMMON_POOL ∩ initially correct ∩ SIMULATABLE. `CORRECT_TO_WRONG@1Q` and `CORRECT_TO_WRONG@3Q` are the fractions whose top1 changes from truth to non-truth in that population, and its N is always reported. This denominator is never mixed with the initially wrong recovery denominator. Net accuracy change is post-question accuracy minus initial accuracy on the stated population.

Paired bootstrap uses 1000 resamples and seed 42. It reports 95% confidence intervals for Profile − Random and Profile − Internal IG on RECOVERY@1Q. Per-view results resample patients. Pooled results use a cluster bootstrap keyed by patient ID: all k3/k5/k10 and view-seed 42/43/44 rows for a sampled patient move together. Random seeds and repeated views never count as independent sample-size increases. Random is represented by the patient/view-level mean across its 50 draws before paired differences are formed.

## 17. Abstention and unobservable information

`ABSTAIN` is a valid Profile/Hybrid outcome when no explicit supported candidate remains. It is not replaced with a random question. Externally important discriminators without a reconstructable DDXPlus question are labeled `EXTERNALLY_IMPORTANT_BUT_UNOBSERVABLE`, excluded from recovery simulation, and written to `09_unobservable_information_opportunities.csv`. Where semantics clearly support it, each is classified as `PATIENT_QUESTION`, `MEDICAL_HISTORY_LOOKUP`, `PHYSICAL_EXAM`, `LAB_TEST`, `IMAGING`, or `OTHER/REVIEW`.

## 18. Invalid and blocked conditions

The run is `STEP16A_INVALID` or the more specific named invalid state if any of these occur:

- TEST patient access beyond existence check;
- use of forbidden `release_conditions.json` disease-feature fields or failure to record permitted name-field reads;
- VALIDATION patient access before preregistration hash verification;
- VALIDATION patient access without explicit post-preregistration `STEP16A_RUN1 실행 승인`;
- hidden answer, truth, full evidence, future answer, or TEST information reaches a selector;
- hidden answer is accessed before selection;
- VALIDATION contributes to model fitting or IG statistics;
- candidate lists differ between selectors in a COMMON_POOL comparison;
- Q1 candidate lists differ at the shared initial state, or Q2/Q3 candidate lists differ despite identical current state and top1/top2 pair; different Q2/Q3 trajectories or pairs are not an identity violation;
- repeated question within a sequential run;
- one-sided missing external relation is treated as negative;
- frozen input hash or mtime changes;
- model is retrained after a question;
- score, subset, pool, endpoint, or tie-break changes after freeze;
- a required answer is guessed rather than reconstructed;
- NaN/inf, denominator mismatch, or failed direct metric recomputation remains unresolved.

An implementation/data limitation that prevents a valid run without violating the frozen rules yields `STEP16A_BLOCKED`. A design bug discovered after results preserves the run as `STEP16A_RUN1_INVALID`; a corrected experiment begins with a new preregistration and run identifier.

## 19. Required output files

Under `exp/step16a_next_information/`:

- `00_STEP16A_PREREGISTRATION.md`
- `00_step16a_rules.json`
- `00_input_integrity.json`
- `01_answer_semantics_audit.md`
- `02_validation_partial_predictions.csv`
- `03_case_eligibility.csv`
- `04_candidate_question_audit.csv`
- `05_question1_results.csv`
- `06_question3_results.csv`
- `07_selector_metrics.csv`
- `08_paired_bootstrap.csv`
- `09_unobservable_information_opportunities.csv`
- `10_selector_input_leakage_audit.json`
- `11_error_case_examples.csv`
- `12_summary.json`
- `PROVENANCE.md`
- `READ_FILES_AUDIT.txt`
- `STEP16A_REPORT.md`
- implementation modules and tests named in the implementation plan

Examples follow deterministic file order: first three Profile recovered, first three Profile not recovered, and first three Profile harm cases where available. No cherry-picking is allowed.

## 20. Final decision boundary

The report selects exactly one decision: `STEP16A_PROFILE_GO`, `STEP16A_PROFILE_PARTIAL_GO`, `STEP16A_PROFILE_NO_GO`, `STEP16A_INVALID`, or `STEP16A_BLOCKED`; and exactly one next step: `SCALE_PROFILE_TO_49`, `IMPROVE_SELECTOR`, `BUILD_REAL_FOLLOWUP_DATA`, or `STOP_PROFILE_QUESTION_ENGINE`.

Interpretation must separate pure `PROFILE_FACT_ONLY` from `PROFILE_IG_HYBRID`. If pure Profile is weaker than IG but Hybrid is stronger than IG, external profile knowledge is not declared valueless; `IMPROVE_SELECTOR` or, when coverage is the main bottleneck, `SCALE_PROFILE_TO_49` remains eligible. Only when both FACT_ONLY and Hybrid show no signal versus IG may the additional value of profile-guided question selection be characterized as weak. The experiment then stops. Profile expansion, natural-language generation, STT, TEST evaluation, and a final verifier are outside STEP16A.
