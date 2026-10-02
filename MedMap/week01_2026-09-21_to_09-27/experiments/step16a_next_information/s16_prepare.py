"""STEP16A B+C: TRAIN 뷰 → MODEL_k3/k5/k10 + IG 테이블 + profile fact→evidence 기계 매핑 + 무결성 스냅샷 + 사전등록 작성/SHA freeze. VALIDATION/TEST 미접근."""
import sys, os, json, time, pickle, hashlib, subprocess, collections
import numpy as np, pandas as pd
sys.path.insert(0, "exp/step16a_next_information"); import s16_core as c
O = c.O; t0 = time.time(); log = lambda *a: print(f"[{time.time()-t0:5.0f}s]", *a, flush=True)
sem = c.Semantics("PRE_FREEZE"); enc = c.Encoder(sem)
# ---- immutable inputs snapshot
INPUTS = ["data/ddxplus/en/release_evidences.json", "data/ddxplus/en/release_train_patients", "exp/step15_v2_blind_profile/PROFILE_FREEZE_V2.json", "exp/step15_v2_blind_profile/01_disease_profile_facts.csv", "exp/step15_v2_blind_profile/02_disease_profile_concepts.csv", "exp/step15_v2_evaluation_fix/05_pair_observability.csv", "exp/step8_mapping/evidence_concept_map.csv", "exp/step14_value_context_recovery/01_evidence_taxonomy.csv"]
integ = {p: {"sha256": c.sha(p), "mtime": os.path.getmtime(p), "size": os.path.getsize(p)} for p in INPUTS}
integ["TEST_exists_bool_only"] = c.test_exists_only(); integ["VALIDATION_opened"] = False
fz = json.load(open("exp/step15_v2_blind_profile/PROFILE_FREEZE_V2.json"))
for f, h in fz["file_sha256"].items():
    if f in ("01_disease_profile_facts.csv", "02_disease_profile_concepts.csv"): assert c.sha(f"exp/step15_v2_blind_profile/{f}") == h, "v2 freeze mismatch"
json.dump(integ, open(f"{O}/00_input_integrity.json", "w"), indent=1); log("integrity ok")
# ---- TRAIN
import glob
REUSE = all(os.path.exists(f"{O}/model_k{k}.pkl") for k in [3,5,10]) and os.path.exists(f"{O}/ig_table_train.npz")
tr = c.load_patients(c.TRAIN_PATH, "PRE_FREEZE", nrows=None if not REUSE else 5); classes = sorted(tr.PATHOLOGY.unique()); assert len(classes) == 49 or REUSE; log("train rows", len(tr), "REUSE", REUSE)
classes = sorted(json.load(open(f"{O}/00_step16a_rules.json"))["answer_semantics"] and [x for x in np.load(f"{O}/ig_table_train.npz", allow_pickle=True)["classes"]]) if REUSE else classes
ig_table, alpha = (None, float(np.load(f"{O}/ig_table_train.npz", allow_pickle=True)["alpha"])) if REUSE else c.fit_ig_table(sem, tr, classes)
if not REUSE: np.savez(f"{O}/ig_table_train.npz", **{e: ig_table[e] for e in sem.qids}, classes=np.array(classes), alpha=alpha); log("IG table done")
models = json.load(open(f"{O}/00_step16a_rules.json"))["models"]["per_k"] if REUSE else {}
for k in ([] if REUSE else [3, 5, 10]):
    views = [c.make_view(sem, t, ini, k, "train", 42, i) for i, (t, ini) in enumerate(zip(tr.tokens, tr.INITIAL_EVIDENCE))]
    X = enc.transform(views, tr.AGE.values, tr.SEX.values); log(f"k{k} views built, nnz", X.nnz, "mean visible", round(float(np.mean([len(v) for v in views])), 2))
    m = c.fit_model(X, tr.PATHOLOGY.values); acc = float((m.predict(X) == tr.PATHOLOGY.values).mean())
    pickle.dump(m, open(f"{O}/model_k{k}.pkl", "wb")); models[k] = {"train_acc": round(acc, 4), "n_iter": int(m.n_iter_[0]), "converged": bool(m.n_iter_[0] < c.MODEL_CFG["max_iter"]), "sha256": c.sha(f"{O}/model_k{k}.pkl")}; log(f"MODEL_k{k}", models[k]); del views, X
# ---- profile fact→evidence 기계 매핑 (질환 무관 규칙)
facts = pd.read_csv("exp/step15_v2_blind_profile/01_disease_profile_facts.csv", dtype=str).fillna(""); concepts = pd.read_csv("exp/step15_v2_blind_profile/02_disease_profile_concepts.csv", dtype=str).fillna("")
ev_map = pd.read_csv("exp/step8_mapping/evidence_concept_map.csv", dtype=str).fillna("").set_index("evidence_id"); tax = pd.read_csv("exp/step14_value_context_recovery/01_evidence_taxonomy.csv", dtype=str).fillna("").set_index("evidence_id")
fe = c.build_fact_evidence_map(facts, concepts, ev_map, tax); fe.to_csv(f"{O}/04_candidate_question_audit.csv", index=False); log("fact→evidence map", len(fe), "evidences", fe.evidence_id.nunique(), "direct", int((fe.match == "DIRECT").sum()))
ALIAS = {"Acute rhinosinusitis": "Acute rhinosinusitis", "Chronic rhinosinusitis": "Chronic rhinosinusitis", "Acute laryngitis": "Acute laryngitis", "Viral pharyngitis": "Viral pharyngitis", "Stable angina": "Stable angina", "Unstable angina": "Unstable angina", "HIV (initial infection)": "Acute HIV infection", "Scombroid food poisoning": "Scombroid poisoning", "Acute COPD exacerbation / infection": "Acute COPD exacerbation", "PSVT": "PSVT"}
assert set(ALIAS.values()) == set(facts.disease.unique()), set(facts.disease.unique()) ^ set(ALIAS.values()); assert all(a in classes for a in ALIAS)
fe["ddx_disease"] = fe.disease.map({v: k for k, v in ALIAS.items()})
pairs = [(a, b) for a in ALIAS for b in ALIAS if a < b]; prow = []
for a, b in pairs:
    for e in sem.qids:
        pr, why = c.contrast_priority(fe, ALIAS[a], ALIAS[b], e)
        if pr > 0: prow.append({"disease_A": a, "disease_B": b, "evidence_id": e, "priority": pr, "rule": why})
PC = pd.DataFrame(prow); PC.to_csv(f"{O}/04b_pair_contrast_table_primary.csv", index=False); log("primary contrasts", len(PC), "pairs with >=1", PC.groupby(["disease_A", "disease_B"]).size().shape[0], "/", len(pairs))
# curated secondary (05_pair_observability.csv): feature→evidence_id
cur = pd.read_csv("exp/step15_v2_evaluation_fix/05_pair_observability.csv", dtype=str).fillna(""); cur = cur[cur.ddxplus_evidence_id != ""]
inv = {v: k for k, v in ALIAS.items()}; crow = []
for r in cur.itertuples():
    for e in r.ddxplus_evidence_id.split(";"):
        e = e.strip()
        if e in sem.ev: crow.append({"disease_A": inv.get(r.disease_a, r.disease_a), "disease_B": inv.get(r.disease_b, r.disease_b), "evidence_id": e, "priority": 2 if r.mapping_status in ("DIRECT_MATCH", "ATTRIBUTE_MATCH") else 1, "rule": "CURATED_PAIR_AUDIT"})
CC = pd.DataFrame(crow).drop_duplicates(); CC.to_csv(f"{O}/04c_pair_contrast_table_curated_secondary.csv", index=False); log("curated contrasts", len(CC))
# ---- 사전등록
rules = {"version": "step16a-v1", "date": time.strftime("%Y-%m-%d"), "git_commit_before": subprocess.run("git rev-parse HEAD", shell=True, capture_output=True, text=True).stdout.strip(),
 "answer_semantics": {"binary_absence": "NEGATIVE (closed-world; TRAIN audit: binary tokens have no value form, initial evidence always present)", "categorical_multi": "value tokens explicit incl. defaults (e.g. E_204 default V_10 present in 185,197/200,000 TRAIN rows); gated child absent when parent negative → NA; parent positive but no token → default value", "global_simulatable_count": 223, "parent_conditioned_questions": sem.parent, "currently_eligible_rule": "question not yet visible AND (no parent OR visible[parent]==POS). Uses only current visible state.", "encoding": "Q::<e>::POS/NEG for binary; Q::<e>::VALUE::<v> per value; Q::<e>::NA; AGE_<decade>; SEX_<M/F>. UNASKED = no feature."},
 "view_protocol": {"name": "STEP16A_NEW_VIEW_PROTOCOL", "steps": "reveal INITIAL_EVIDENCE (always binary POS) → k sequential draws uniformly from CURRENTLY_ELIGIBLE set (children open only after parent revealed POS) → reveal each; RNG key=(split,seed,patient_index)", "k": [3, 5, 10], "train_seed": 42, "validation_seeds": [42, 43, 44], "note": "differs from Step2+3 (which sampled only positive tokens): answers are mostly NEGATIVE, so initial accuracy will be lower"},
 "models": {"config": c.MODEL_CFG, "train_rows": 1025602, "per_k": models, "no_validation_tuning": True, "no_retrain_after_question": True},
 "internal_ig": {"formula": "IG(q) = H(post) - Σ_a P(a) H(post_a); post_a(d) ∝ post(d)·P(a|d); P(a) = Σ_d post(d)P(a|d)", "P_a_given_d": "TRAIN closed-world counts, (count+α)/(n_d+α|A_q|)", "alpha": alpha, "answer_space": "binary {POS,NEG}; C/M {VALUE::v for each possible value, NA}; multi-select values counted per value", "impossible_answer": "P(a)=0 term skipped (cannot occur with α>0)", "log_base": 2, "tie_break": "ascending numeric evidence id"},
 "profile_primary": {"name": "PROFILE_FACT_ONLY", "inputs": ["v2 01_disease_profile_facts.csv", "v2 02_disease_profile_concepts.csv", "Step8 evidence_concept_map.csv (disease-independent evidence concept CUI/HPO)", "Step14 01_evidence_taxonomy.csv (evidence attribute type)"], "mapping_rule": "fact→evidence DIRECT if fact CUI or HPO equals evidence concept_1/2 CUI/HPO; PARTIAL if base concept name equals evidence concept name or one is a substring (>=5 chars) of the other (general rule, applied identically to all pairs; adopted before any VALIDATION access, superseding prereg draft hash 436daf87/f94a350f); attribute_level if fact has attribute field whose type matches evidence taxonomy type", "contrast_rule": "for pair(A,B) and evidence e: 2 if EXPLICIT_POSITIVE_NEGATIVE (A positive fact & B explicit negative fact on e) or EXPLICIT_CONTRAST (both have facts on e with different attribute values and e is attribute-level); 1 if attribute values differ but e not attribute-level; 0 if same on both or ONE_SIDED_UNKNOWN (absent relation is unknown, never negative)", "selection": "highest priority, tie → ascending evidence id; none → ABSTAIN", "curated_pair_audit_used": False, "n_primary_contrast_rows": int(len(PC))},
 "profile_secondary": {"PROFILE_WITH_CURATED_PAIR_AUDIT": "adds 04c (from evaluation_fix 05_pair_observability.csv feature→evidence rows) to primary table; reported separately", "PROFILE_ONE_SIDED_SENSITIVITY": "one-sided presence counts as priority 1; reported separately", "PROFILE_IG_HYBRID": "restrict pool to primary priority>0 then pick max IG"},
 "pools": {"FULL_POOL": "all GLOBAL_SIMULATABLE & CURRENTLY_ELIGIBLE & unasked questions (no condition→evidence lists used anywhere)", "COMMON_POOL": "FULL_POOL ∩ {e: primary priority(top1,top2,e)>0}", "identity_check": "at Q1 shared state all selectors receive identical ordered COMMON_POOL ids; Q2/Q3 identity checked only for same state+pair"},
 "selectors": {"RANDOM": "uniform over pool, 50 draws seeds 1000-1049, averaged per patient/view before pairing", "INTERNAL_IG": "argmax IG over pool", "PROFILE_FACT_ONLY": "primary", "secondary": ["PROFILE_WITH_CURATED_PAIR_AUDIT", "PROFILE_ONE_SIDED_SENSITIVITY", "PROFILE_IG_HYBRID"]},
 "simulation": {"order": "encode visible → predict (matching MODEL_k) → build SelectorInput (no answers/truth) → select or ABSTAIN → record → reveal reconstructed answer → add to visible → predict again (no retrain)", "Q1_primary": True, "Q3_secondary": True, "abstain": "no replacement question"},
 "populations": ["ALL_VALIDATION", "PILOT_TRUE (truth in 10 pilot)", "PILOT_PAIR (top1&top2 both pilot)", "PROFILE_REACHABLE (primary priority>0 exists for top1/top2)", "SIMULATABLE (>=1 such question in COMMON_POOL)"],
 "metrics": {"primary_population": "COMMON_POOL nonempty ∩ initially wrong ∩ SIMULATABLE ∩ PILOT_PAIR", "primary_endpoint": "RECOVERY@1Q = P(top1 becomes truth after exactly one revealed answer), identical denominators across paired selectors", "harm_population": "COMMON_POOL nonempty ∩ initially correct ∩ SIMULATABLE ∩ PILOT_PAIR", "harm": "CORRECT_TO_WRONG@1Q/@3Q", "secondary": ["RECOVERY@3Q", "top1 acc before/after", "truth rank mean/median", "top3 inclusion", "abstain rate", "questions asked", "truth-in-top2/top3 before", "FULL_POOL variants"], "bootstrap": {"n": 1000, "seed": 42, "unit": "patient cluster (all k/seeds of a patient move together)", "reports": ["Profile-Random", "Profile-IG", "Hybrid-IG"]}},
 "invalid_conditions": ["TEST access beyond exists()", "conditions.json opened", "VALIDATION opened before hash gate/approval", "truth/hidden/future answer in SelectorInput", "reveal before select", "retrain after question", "COMMON_POOL identity violation at shared Q1", "repeated question", "one-sided absence treated negative", "input hash/mtime change", "rule change after freeze", "NaN/inf", "denominator mismatch"],
 "test_policy": "VALIDATION opened exactly once after user approval 'STEP16A_RUN1 실행 승인'; TEST never"}
json.dump(rules, open(f"{O}/00_step16a_rules.json", "w"), indent=1, default=str)
md = "# STEP 16A 사전등록 (VALIDATION 개봉 전 고정)\n\n" + "\n".join(f"- **{k}**: {json.dumps(v, ensure_ascii=False, default=str)}" for k, v in rules.items())
open(f"{O}/00_STEP16A_PREREGISTRATION.md", "w").write(md)
h = {f: c.sha(f"{O}/{f}") for f in ["00_STEP16A_PREREGISTRATION.md", "00_step16a_rules.json"]}; json.dump(h, open(f"{O}/00_preregistration_sha256.json", "w"), indent=1)
open(f"{O}/READ_FILES_AUDIT.txt", "w").write("\n".join(f"{ph}\t{p}" for ph, p in c.READ_LOG) + "\n" + "\n".join(f"INPUT\t{p}" for p in INPUTS))
print(json.dumps({"models": models, "ig_alpha": alpha, "primary_contrast_rows": len(PC), "pairs_with_contrast": int(PC.groupby(["disease_A", "disease_B"]).size().shape[0]), "curated_rows": len(CC), "prereg_sha": h, "validation_opened": False, "test_reads": 0}, indent=1)); log("DONE")
