"""STEP14-B: VALIDATION 전용 개발 분석 — S2 ablation(정보 종류별), evidence 판별력(TRAIN 통계), 오답쌍 결손 정보, coverage/reachability 전후. TEST 미사용."""
import json, time, collections, hashlib, os, re
import numpy as np, pandas as pd, scipy.sparse as sp
from sklearn.metrics import roc_auc_score, average_precision_score
O = "exp/step14_value_context_recovery"; W = "exp/step2_3_workingdx"; S5 = "exp/step5_7_discrepancy"; S8 = "exp/step8_mapping"; S9 = "exp/step9_external_knowledge"; S10 = "exp/step10_hsdn"; S11 = "exp/step11_external_expansion"
t0 = time.time(); log = lambda *a: print(f"[{time.time()-t0:5.0f}s]", *a, flush=True)
vj = json.load(open(f"{W}/vocab.json")); vocab, classes = vj["vocab"], vj["classes"]; cidx = {c: i for i, c in enumerate(classes)}; V = len(vocab)
npz = np.load(f"{S5}/cond_token_logp.npz", allow_pickle=True); logP = npz["logP"]; n_d = npz["n_d"]  # TRAIN 전용
cond = json.load(open("data/ddxplus/en/release_conditions.json")); ev = json.load(open("data/ddxplus/en/release_evidences.json"))
T = pd.read_csv(f"{O}/01_evidence_taxonomy.csv", dtype=str).fillna("").set_index("evidence_id"); EE = pd.read_csv(f"{O}/09_expanded_eligibility.csv", dtype=str).fillna("").set_index("evidence_id"); em = pd.read_csv(f"{S8}/evidence_concept_map.csv", dtype=str).fillna("").set_index("evidence_id")
tok_ev = {t: t.split("_@_")[0] for t in vocab if t.startswith("E_")}
ELIG = set(T[T.previous_eligibility == "ELIGIBLE_83"].index); EXCL = set(T[T.previous_eligibility == "EXCLUDED"].index)
def grp(types, base=EXCL): return {e for e in base if T.loc[e, "primary_type"] in types}
GROUPS = {"MEDICAL_HISTORY": grp({"MEDICAL_HISTORY"}), "LOCATION": grp({"ANATOMICAL_LOCATION"}), "TEMPORAL": grp({"TEMPORAL"}), "SEVERITY": grp({"SEVERITY"}), "RISK_EXPOSURE": grp({"EXPOSURE", "LIFESTYLE", "RISK_FACTOR", "TRAVEL", "DEMOGRAPHIC"}), "MEDICATION": grp({"MEDICATION"}), "FAMILY_HISTORY": grp({"FAMILY_HISTORY"}), "EXCLUDED_SYMPTOM_SIGN": grp({"SYMPTOM", "SIGN"}), "PROCEDURE_PREGNANCY": grp({"PROCEDURE", "PREGNANCY_REPRODUCTIVE"}), "VALUE_LEVEL_ALL": {e for e in EXCL if EE.loc[e, "expanded_eligibility"] != "UNUSABLE"}}
log({k: len(v) for k, v in GROUPS.items()})
# ---------- VALIDATION cohort (seed 42 all k + k3 seeds)
wd = pd.read_parquet(f"{W}/val_working_dx.parquet"); wd = wd[(wd.seed == 42) | (wd.k == "3")]
def tok_matrix(views, allowed_ev):
    rows, cols = [], []
    for i, v in enumerate(views):
        for t in v:
            j = vocab.get(t)
            if j is not None and tok_ev.get(t) in allowed_ev: rows.append(i); cols.append(j)
    return sp.csr_matrix((np.ones(len(rows), np.float32), (rows, cols)), shape=(len(views), V))
def s2(X, d):
    LL = X @ logP.T; own = LL[np.arange(len(d)), d]; LLm = LL.copy(); LLm[np.arange(len(d)), d] = -np.inf; return LLm.max(1) - own
ABL = {"A_ALL": set(tok_ev.values()), "B_FINDING_ONLY": ELIG}
for k, g in GROUPS.items(): ABL[f"FINDING+{k}"] = ELIG | g
for k, g in GROUPS.items(): ABL[f"ALL-{k}"] = set(tok_ev.values()) - g
abl_rows = []
for (k, seed), g in wd.groupby(["k", "seed"], sort=False):
    g = g.sort_values("idx"); views = [json.loads(s) for s in g.exposed]; d = g.working_dx.map(cidx).values; y = (g.working_dx != g.truth).astype(int).values
    base = {}
    for name, allowed in ABL.items():
        X = tok_matrix(views, allowed); s = s2(X, d); thr = np.quantile(s[y == 0], 0.9); n_tok = np.asarray(X.sum(1)).ravel()
        r = {"config": f"k{k}_s{seed}", "ablation": name, "n": len(g), "n_wrong": int(y.sum()), "auroc": round(roc_auc_score(y, s), 4), "auprc": round(average_precision_score(y, s), 4), "sens@valFPR10": round(float((s[y == 1] > thr).mean()), 4), "mean_tokens_used": round(float(n_tok.mean()), 2), "frac_patients_zero_tokens": round(float((n_tok == 0).mean()), 4)}
        base[name] = r["auroc"]; abl_rows.append(r)
    for r in abl_rows:
        if r["config"] == f"k{k}_s{seed}": r["delta_vs_ALL"] = round(r["auroc"] - base["A_ALL"], 4); r["delta_vs_FINDING_ONLY"] = round(r["auroc"] - base["B_FINDING_ONLY"], 4)
    log("ablation", k, seed)
AB = pd.DataFrame(abl_rows); AB.to_csv(f"{O}/03_validation_ablation.csv", index=False)
# ---------- evidence 판별력 (TRAIN logP) + validation 출현
P = np.exp(logP)  # 49×V
va = pd.read_csv("data/ddxplus/en/release_validate_patients", usecols=["EVIDENCES"]); occ = collections.Counter()
for s in va.EVIDENCES: 
    for t in json.loads(s.replace("'", '"')): occ[t] += 1
g3 = wd[(wd.k == "3") & (wd.seed == 42)]; wrong3 = g3[g3.working_dx != g3.truth]; top_pairs = wrong3.groupby(["truth", "working_dx"]).size().sort_values(ascending=False).head(10)
disc = []
for t, j in vocab.items():
    if not t.startswith("E_"): continue
    e = tok_ev[t]; p = P[:, j]; pair_use = np.mean([abs(logP[cidx[a], j] - logP[cidx[b], j]) for (a, b) in top_pairs.index])
    disc.append({"token": t, "evidence_id": e, "primary_type": T.loc[e, "primary_type"], "previous_eligibility": T.loc[e, "previous_eligibility"], "expanded_eligibility": EE.loc[e, "expanded_eligibility"], "validate_occurrence": occ.get(t, 0), "validate_occurrence_frac": round(occ.get(t, 0) / len(va), 4), "max_P_f_given_d": round(float(p.max()), 4), "mean_P_f_given_d": round(float(p.mean()), 4), "std_P_across_diseases": round(float(p.std()), 4), "specificity_ratio(max/mean)": round(float(p.max() / max(p.mean(), 1e-9)), 2), "n_diseases_P>0.1": int((p > 0.1).sum()), "mean_abs_logratio_top10_error_pairs": round(float(pair_use), 3)})
DV = pd.DataFrame(disc).sort_values("mean_abs_logratio_top10_error_pairs", ascending=False); DV.to_csv(f"{O}/04_evidence_discriminative_value.csv", index=False)
# ---------- 오답쌍 결손 정보 (validation top pairs, DDXPlus 정의 + TRAIN logP)
pair_rows, recov = [], []
for (a, b), n in top_pairs.items():
    ea = set(cond[a]["symptoms"]) | set(cond[a]["antecedents"]); eb = set(cond[b]["symptoms"]) | set(cond[b]["antecedents"]); diff = (ea - eb) | (eb - ea)
    strong = [(t, round(float(abs(logP[cidx[a], j] - logP[cidx[b], j])), 2)) for t, j in vocab.items() if t.startswith("E_") and abs(logP[cidx[a], j] - logP[cidx[b], j]) > 1.0]; strong.sort(key=lambda x: -x[1])
    def cls(es): return dict(collections.Counter(T.loc[e, "primary_type"] for e in es))
    sub = wrong3[(wrong3.truth == a) & (wrong3.working_dx == b)]
    pair_rows.append({"true_diagnosis": a, "working_diagnosis": b, "n_wrong_val_k3": int(n), "mean_confidence": round(float(sub.wd_prob.mean()), 3), "ddx_definition_diff_evidences": len(diff), "diff_in_83": sum(e in ELIG for e in diff), "diff_excluded": sum(e in EXCL for e in diff), "diff_by_type": json.dumps(cls(diff)), "diff_excluded_list": "; ".join(f"{e}:{em.loc[e,'concept_1']}" for e in sorted(diff) if e in EXCL)[:300],
                      "n_tokens_strong_logratio>1": len(strong), "strong_in_83": sum(tok_ev[t] in ELIG for t, _ in strong), "strong_excluded": sum(tok_ev[t] in EXCL for t, _ in strong), "top_strong_tokens": "; ".join(f"{t}({em.loc[tok_ev[t],'concept_1']},{v})" for t, v in strong[:6])})
    exp_ok = {e for e in diff if EE.loc[e, "expanded_eligibility"] in ("EXTERNAL_USABLE_FULL", "EXTERNAL_USABLE_PARTIAL")}
    recov.append({"true_diagnosis": a, "working_diagnosis": b, "n_wrong_val_k3": int(n), "distinguishing_in_83": sum(e in ELIG for e in diff), "distinguishing_excluded": sum(e in EXCL for e in diff), "distinguishing_after_value_context(FULL+PARTIAL)": len(exp_ok), "distinguishing_structured_only": sum(EE.loc[e, "expanded_eligibility"] == "STRUCTURED_ONLY" for e in diff), "key_attribute_types": json.dumps(cls(diff - ELIG)), "external_linkable_now(strict KB has concept for both diseases)": "", "note": ""})
PR = pd.DataFrame(pair_rows); PR.to_csv(f"{O}/05_error_pair_missing_information.csv", index=False)
# ---------- coverage / reachability before/after (VALIDATION, k3 s42), 외부 strict KB 재사용(step13b 관계행렬 규칙) over base concepts
m = pd.read_parquet("data/umls/mrconso_eng.parquet"); msh = m[(m.SAB == "MSH") & (m.TTY == "MH")]; cui2mesh = msh.groupby("CUI")["CODE"].agg(set).to_dict(); del m
def keys(e):
    r = em.loc[e]; ks = {"cui": set(), "hpo": set(), "mesh": set()}
    for k in (1, 2):
        c, h = r[f"concept_{k}_cui"], r[f"concept_{k}_hpo"].split(";")[0]
        if c: ks["cui"].add(c); ks["mesh"] |= cui2mesh.get(c, set())
        if h: ks["hpo"].add(h)
    return ks
USE_AFTER = sorted(EE[EE.expanded_eligibility.isin(["EXTERNAL_USABLE_FULL", "EXTERNAL_USABLE_PARTIAL"])].index); USE_BEFORE = sorted(ELIG)
EK = {e: keys(e) for e in USE_AFTER}; DIS = list(cond); di = {d: i for i, d in enumerate(DIS)}
dm = pd.read_csv(f"{S9}/01_disease_concept_map.csv", dtype=str).fillna("").set_index("ddxplus_disease"); dnames = {d: {dm.loc[d, "umls_name"].lower(), d.lower()} for d in DIS}
def fl(x):
    try: return float(x)
    except: return np.nan
Rmat = {}; 
def build(use):
    fi = {e: i for i, e in enumerate(use)}; R = np.zeros((49, len(use)), int)
    def add(d, keyset, key, ok):
        if d not in di or not ok: return
        for e in use:
            if EK[e][key] & keyset and em.loc[e, "concept_1"].lower() not in dnames[d]: R[di[d], fi[e]] = 1
    e9 = pd.read_csv(f"{S9}/02_external_disease_finding_edges.csv", dtype=str).fillna("")
    for r in e9.itertuples():
        if r.finding_hpo and r.negative_annotation != "True": add(r.ddxplus_disease, {r.finding_hpo}, "hpo", r.hpo_aspect.find("P") >= 0 and r.self_phenotype != "True" and "familial" not in r.reference_type)
    hs_dm = pd.read_csv(f"{S10}/01_hsdn_disease_map.csv", dtype=str).fillna("").set_index("ddxplus_disease")
    for r in pd.read_csv(f"{S10}/03_hsdn_disease_finding_edges.csv", dtype=str).fillna("").itertuples(): add(r.ddxplus_disease, {r.mesh_id}, "mesh", fl(r.pubmed_cooccurrence) >= 2 and hs_dm.loc[r.ddxplus_disease, "mapping_status"] in ("EXACT", "PARTIAL"))
    for r in pd.read_csv(f"{S11}/03_dismech_disease_finding_edges.csv", dtype=str).fillna("").itertuples():
        if r.finding_hpo and r.frequency_raw != "EXCLUDED": add(r.ddxplus_disease, {r.finding_hpo}, "hpo", r.has_pubmed_evidence == "True")
    for r in pd.read_csv(f"{S11}/06_medline_disease_finding_edges.csv", dtype=str).fillna("").itertuples(): add(r.ddxplus_disease, {r.finding_mesh}, "mesh", fl(r.cooccurrence) >= 2)
    for r in pd.read_csv(f"{S11}/07_wikidata_disease_finding_edges.csv", dtype=str).fillna("").itertuples():
        for k, v in {"cui": {r.finding_cui} - {""}, "hpo": {r.finding_hpo} - {""}, "mesh": {r.finding_mesh} - {""}}.items():
            if v: add(r.ddxplus_disease, v, k, r.has_reference == "True")
    for r in pd.read_csv(f"{S11}/01_umls_disease_finding_edges.csv", dtype=str).fillna("").itertuples(): add(r.ddxplus_disease, {r.finding_cui}, "cui", r.quality_class == "DIRECT_FINDING" and not r.lineage_overlap)
    return R, fi
RB, fiB = build(USE_BEFORE); RA, fiA = build(USE_AFTER)
knownB = {DIS[i] for i in np.where(RB.sum(1) > 0)[0]}; knownA = {DIS[i] for i in np.where(RA.sum(1) > 0)[0]}
cov_rows = []
for d, v in cond.items():
    rel = list(v["symptoms"]) + list(v["antecedents"])
    b_use = [e for e in rel if e in fiB]; a_use = [e for e in rel if e in fiA]
    cov_rows.append({"ddxplus_disease": d, "n_related_evidence": len(rel), "usable_before": len(b_use), "usable_after": len(a_use), "matched_before": int(sum(RB[di[d], fiB[e]] for e in b_use)), "matched_after": int(sum(RA[di[d], fiA[e]] for e in a_use)), "coverage_before(matched/usable)": round(sum(RB[di[d], fiB[e]] for e in b_use) / len(b_use), 3) if b_use else None, "coverage_after": round(sum(RA[di[d], fiA[e]] for e in a_use) / len(a_use), 3) if a_use else None, "coverage_before(matched/all_related)": round(sum(RB[di[d], fiB[e]] for e in b_use) / len(rel), 3), "coverage_after(matched/all_related)": round(sum(RA[di[d], fiA[e]] for e in a_use) / len(rel), 3), "known_before": d in knownB, "known_after": d in knownA})
CV = pd.DataFrame(cov_rows); CV.to_csv(f"{O}/10_coverage_before_after.csv", index=False)
reach_rows = []
for (k, seed), g in wd.groupby(["k", "seed"], sort=False):
    g = g.sort_values("idx"); views = [json.loads(s) for s in g.exposed]; w = g[g.working_dx != g.truth]; wv = [json.loads(s) for s in w.exposed]
    for tag, use, R, fi, known in [("before_83", USE_BEFORE, RB, fiB, knownB), ("after_value_context", USE_AFTER, RA, fiA, knownA)]:
        knownf = R.sum(0) > 0; n_ev = np.array([sum(1 for t in v if tok_ev.get(t) in fi and knownf[fi[tok_ev[t]]]) for v in views]); n_use = np.array([sum(1 for t in v if tok_ev.get(t) in fi) for v in views])
        n_evw = np.array([sum(1 for t in v if tok_ev.get(t) in fi and knownf[fi[tok_ev[t]]]) for v in wv])
        reach = (w.working_dx.isin(known) & w.truth.isin(known)).values & (n_evw > 0)
        reach_rows.append({"config": f"k{k}_s{seed}", "stage": tag, "usable_evidence": len(use), "diseases_known": len(known), "mean_usable_exposed_per_patient": round(float(n_use.mean()), 2), "mean_evaluable_per_patient": round(float(n_ev.mean()), 2), "frac_patients_evaluable0": round(float((n_ev == 0).mean()), 4), "wrong_total": len(w), "reachable": int(reach.sum()), "reachable_ceiling": round(float(reach.mean()), 4), "unreachable_wd_unknown": int((~w.working_dx.isin(known)).sum()), "unreachable_truth_unknown": int((~w.truth.isin(known)).sum()), "unreachable_patient_no_evaluable": int(((w.working_dx.isin(known) & w.truth.isin(known)).values & (n_evw == 0)).sum())})
RR = pd.DataFrame(reach_rows); RR.to_csv(f"{O}/11_reachability_validation.csv", index=False)
for r in recov:
    a, b = r["true_diagnosis"], r["working_diagnosis"]; r["external_linkable_now(strict KB has concept for both diseases)"] = (a in knownA) and (b in knownA)
    r["note"] = "both diseases have strict external relations after expansion" if r["external_linkable_now(strict KB has concept for both diseases)"] else f"unknown in strict KB: {[x for x in (a, b) if x not in knownA]}"
pd.DataFrame(recov).to_csv(f"{O}/12_error_pair_recoverability.csv", index=False)
pd.set_option("display.width", 250); print(AB[AB.config == "k3_s42"][["ablation", "auroc", "auprc", "sens@valFPR10", "mean_tokens_used", "delta_vs_ALL", "delta_vs_FINDING_ONLY"]].to_string()); print(RR.to_string()); print(PR[["true_diagnosis", "working_diagnosis", "n_wrong_val_k3", "diff_in_83", "diff_excluded", "strong_in_83", "strong_excluded", "top_strong_tokens"]].to_string()); print(pd.DataFrame(recov)[["true_diagnosis", "working_diagnosis", "distinguishing_in_83", "distinguishing_excluded", "distinguishing_after_value_context(FULL+PARTIAL)", "distinguishing_structured_only", "note"]].to_string())
print(CV[["coverage_before(matched/usable)", "coverage_after", "coverage_before(matched/all_related)", "coverage_after(matched/all_related)"]].describe().round(3).loc[["mean", "50%"]]); print("known before/after", len(knownB), len(knownA)); log("DONE")
