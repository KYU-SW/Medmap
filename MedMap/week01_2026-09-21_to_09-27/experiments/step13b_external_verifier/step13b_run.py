"""STEP 13B: 사전등록 규칙(00_preregistered_rules.json) 고정 → 외부 relation 행렬(49×83) → VALIDATION 임계 → TEST 1회 평가."""
import json, hashlib, time, collections, os, sys
import numpy as np, pandas as pd
from sklearn.metrics import roc_auc_score, average_precision_score, roc_curve
from scipy.stats import spearmanr
O = "exp/step13b_external_verifier"; S8 = "exp/step8_mapping"; S9 = "exp/step9_external_knowledge"; S10 = "exp/step10_hsdn"; S11 = "exp/step11_external_expansion"; S13 = "exp/step13_aprime"
t0 = time.time(); log = lambda *a: print(f"[{time.time()-t0:5.0f}s]", *a, flush=True)
audit = {"prereg_sha256": {f: hashlib.sha256(open(f"{O}/{f}", "rb").read()).hexdigest() for f in ["00_SCORER_PREREGISTRATION.md", "00_preregistered_generic_findings.csv", "00_preregistered_rules.json"]}, "test_runs": 0, "started": time.strftime("%Y-%m-%d %H:%M:%S")}
rules = json.load(open(f"{O}/00_preregistered_rules.json"))
cond = json.load(open("data/ddxplus/en/release_conditions.json")); DIS = list(cond); di = {d: i for i, d in enumerate(DIS)}
el = pd.read_csv(f"{S9}/03_evidence_eligibility.csv", dtype=str).fillna(""); COMMON = sorted(el[el.finding_eligible == "True"].evidence_id); fi = {e: i for i, e in enumerate(COMMON)}
em = pd.read_csv(f"{S8}/evidence_concept_map.csv", dtype=str).fillna("").set_index("evidence_id"); generic = set(pd.read_csv(f"{O}/00_preregistered_generic_findings.csv", dtype=str).evidence_id)
dm = pd.read_csv(f"{S9}/01_disease_concept_map.csv", dtype=str).fillna("").set_index("ddxplus_disease")
m = pd.read_parquet("data/umls/mrconso_eng.parquet"); msh = m[(m.SAB == "MSH") & (m.TTY == "MH")]; cui2mesh = msh.groupby("CUI")["CODE"].agg(set).to_dict(); del m
EK = {}
for e in COMMON:
    r = em.loc[e]; ks = {"cui": set(), "hpo": set(), "mesh": set()}
    for k in (1, 2):
        c, h = r[f"concept_{k}_cui"], r[f"concept_{k}_hpo"].split(";")[0]
        if c: ks["cui"].add(c); ks["mesh"] |= cui2mesh.get(c, set())
        if h: ks["hpo"].add(h)
    EK[e] = ks
dnames = {d: {dm.loc[d, "umls_name"].lower(), d.lower()} for d in DIS}
# ---------- relation matrices R[d,f] ∈ {+1,0,-1}, strict / lenient
def fl(x):
    try: return float(x)
    except: return np.nan
POS = {"S": np.zeros((49, 83), int), "L": np.zeros((49, 83), int)}; NEG = np.zeros((49, 83), int); SRC = collections.defaultdict(set)
def add(d, keyset, key, src, strict_ok, negative=False):
    if d not in di: return
    for e in COMMON:
        if EK[e][key] & keyset and em.loc[e, "concept_1"].lower() not in dnames[d]:
            if negative: NEG[di[d], fi[e]] = 1; continue
            POS["L"][di[d], fi[e]] = 1; SRC[(d, e, "L")].add(src)
            if strict_ok: POS["S"][di[d], fi[e]] = 1; SRC[(d, e, "S")].add(src)
e9 = pd.read_csv(f"{S9}/02_external_disease_finding_edges.csv", dtype=str).fillna("")
for r in e9.itertuples():
    src = "OPTIMUSKG" if r.source.startswith("OptimusKG") else "HPO"
    if not r.finding_hpo: continue
    if r.negative_annotation == "True": add(r.ddxplus_disease, {r.finding_hpo}, "hpo", src, False, negative=True); continue
    add(r.ddxplus_disease, {r.finding_hpo}, "hpo", src, r.hpo_aspect.find("P") >= 0 and r.self_phenotype != "True" and "familial" not in r.reference_type)
hs_dm = pd.read_csv(f"{S10}/01_hsdn_disease_map.csv", dtype=str).fillna("").set_index("ddxplus_disease")
for r in pd.read_csv(f"{S10}/03_hsdn_disease_finding_edges.csv", dtype=str).fillna("").itertuples(): add(r.ddxplus_disease, {r.mesh_id}, "mesh", "HSDN", fl(r.pubmed_cooccurrence) >= 2 and hs_dm.loc[r.ddxplus_disease, "mapping_status"] in ("EXACT", "PARTIAL"))
for r in pd.read_csv(f"{S11}/03_dismech_disease_finding_edges.csv", dtype=str).fillna("").itertuples():
    if not r.finding_hpo: continue
    if r.frequency_raw == "EXCLUDED": add(r.ddxplus_disease, {r.finding_hpo}, "hpo", "DISMECH", False, negative=True); continue
    add(r.ddxplus_disease, {r.finding_hpo}, "hpo", "DISMECH", r.has_pubmed_evidence == "True")
for r in pd.read_csv(f"{S11}/06_medline_disease_finding_edges.csv", dtype=str).fillna("").itertuples(): add(r.ddxplus_disease, {r.finding_mesh}, "mesh", "MEDLINE", fl(r.cooccurrence) >= 2)
for r in pd.read_csv(f"{S11}/07_wikidata_disease_finding_edges.csv", dtype=str).fillna("").itertuples():
    for k, v in {"cui": {r.finding_cui} - {""}, "hpo": {r.finding_hpo} - {""}, "mesh": {r.finding_mesh} - {""}}.items():
        if v: add(r.ddxplus_disease, v, k, "WIKIDATA", r.has_reference == "True")
for r in pd.read_csv(f"{S11}/01_umls_disease_finding_edges.csv", dtype=str).fillna("").itertuples():
    if r.quality_class == "NON_FINDING": continue
    add(r.ddxplus_disease, {r.finding_cui}, "cui", f"UMLS:{r.SAB}", r.quality_class == "DIRECT_FINDING" and not r.lineage_overlap)
NEG = NEG * (POS["L"] == 0)  # positive가 하나라도 있으면 negative 무시
R = {"S": POS["S"] - NEG, "L": POS["L"] - NEG}
known_dis = {v: set(DIS[i] for i in np.where(np.abs(R[v]).sum(1) > 0)[0]) for v in "SL"}; known_f = {v: (np.abs(R[v]).sum(0) > 0) for v in "SL"}
log("relation matrix strict +:", int((R["S"] == 1).sum()), "-:", int((R["S"] == -1).sum()), "diseases", len(known_dis["S"]), "findings", int(known_f["S"].sum()), "| lenient +:", int((R["L"] == 1).sum()), "diseases", len(known_dis["L"]))
pd.DataFrame([{"ddxplus_disease": d, "evidence_id": e, "finding": em.loc[e, "concept_1"], "strict_score": int(R["S"][di[d], fi[e]]), "lenient_score": int(R["L"][di[d], fi[e]]), "sources_strict": ";".join(sorted(SRC[(d, e, "S")])), "sources_lenient": ";".join(sorted(SRC[(d, e, "L")]))} for d in DIS for e in COMMON if R["L"][di[d], fi[e]] != 0]).to_csv(f"{O}/00b_relation_matrix_nonzero.csv", index=False)
GEN = {"HSDN": "PUBMED_COOCCURRENCE", "MEDLINE": "PUBMED_COOCCURRENCE", "UMLS:MSH": "PUBMED_COOCCURRENCE", "HPO": "PHENOTYPE_ONTOLOGY", "OPTIMUSKG": "PHENOTYPE_ONTOLOGY", "UMLS:OMIM": "PHENOTYPE_ONTOLOGY", "UMLS:HPO": "PHENOTYPE_ONTOLOGY", "DISMECH": "CURATED_CLINICAL", "WIKIDATA": "COMMUNITY_KG"}
srcs_all = sorted({s for k, v in SRC.items() for s in v}); pd.DataFrame([{"source": s, "genealogy": GEN.get(s, "TERMINOLOGY_RELATION"), "n_pairs_strict": sum(1 for k, v in SRC.items() if k[2] == "S" and s in v), "n_pairs_lenient": sum(1 for k, v in SRC.items() if k[2] == "L" and s in v)} for s in srcs_all]).to_csv(f"{O}/13_source_genealogy.csv", index=False)
# ---------- collision (사전 고정: 동일 외부 ID 공유)
ids = collections.defaultdict(set)
for d in DIS:
    if hs_dm.loc[d, "mesh_id"]: ids[d].add("MESH:" + hs_dm.loc[d, "mesh_id"])
    for c in ["hpo_disease_id", "optimuskg_disease_id"]:
        for x in dm.loc[d, c].split(";"):
            if x: ids[d].add(x)
dd_ = pd.read_csv(f"{S11}/02_dismech_disease_map.csv", dtype=str).fillna("").set_index("ddxplus_disease"); md_ = pd.read_csv(f"{S11}/04_medline_disease_map.csv", dtype=str).fillna("").set_index("ddxplus_disease")
for d in DIS:
    if dd_.loc[d, "dismech_file"]: ids[d].add("DISMECH:" + dd_.loc[d, "dismech_file"])
    if md_.loc[d, "doid_code"]: ids[d].add("DOID:" + md_.loc[d, "doid_code"])
COLL = {}
for a in DIS:
    for b in DIS:
        if a != b and ids[a] & ids[b]: COLL[(a, b)] = ";".join(sorted(ids[a] & ids[b]))
log("collision pairs", len(COLL) // 2, sorted({tuple(sorted(k)) for k in COLL})[:10])
# ---------- scoring
def score(df, v):
    X = np.zeros((len(df), 83), np.int8)
    for i, s in enumerate(df["exposed_common_findings"].values):
        for t in json.loads(s):
            j = fi.get(t.split("_@_")[0]);  X[i, j] = 1 if j is not None else 0
    ev = X * known_f[v][None, :]; n_ev = ev.sum(1); wd = df["working_diagnosis"].map(di).values
    Rm = R[v].T.astype(float)  # 83×49
    S = (ev @ Rm) / np.where(n_ev > 0, n_ev, 1)[:, None]; S[n_ev == 0] = np.nan
    own = S[np.arange(len(df)), wd]; Sm = S.copy(); Sm[np.arange(len(df)), wd] = -np.inf; best = Sm.max(1)
    b = best - own; b[n_ev == 0] = np.nan
    n_sup = ((ev @ (R[v].T == 1).astype(float))[np.arange(len(df)), wd]).astype(int); n_neg = ((ev @ (R[v].T == -1).astype(float))[np.arange(len(df)), wd]).astype(int)
    return b, X.sum(1), n_ev, n_sup, n_ev - n_sup - n_neg, n_neg, [DIS[i] for i in Sm.argmax(1)]
def load(split):
    c = pd.read_csv(f"{S13}/01_common_input_cohort.csv", dtype={"k": str}); c = c[c.split == split].copy()
    a = pd.read_csv(f"{S13}/02_aprime_internal_scores.csv"); a = a[a.split == split][["sample_id", "config", "A_prime_score"]]
    c = c.merge(a, on=["sample_id", "config"]); assert not c.duplicated(["sample_id", "config"]).any(); return c
def annotate(c):
    for v, name in [("S", "bstrict"), ("L", "blenient")]:
        b, nc, ne, ns, nu, nn, alt = score(c, v); c[f"{name}_score"] = b; c[f"{name}_best_alt"] = alt; c[f"{name}_knowledge_unavailable"] = np.isnan(b)
        c[f"{name}_n_common"] = nc; c[f"{name}_n_evaluable"] = ne; c[f"{name}_n_supported"] = ns; c[f"{name}_n_unknown"] = nu; c[f"{name}_n_negative"] = nn
    c["wd_known_strict"] = c.working_diagnosis.isin(known_dis["S"]); c["truth_known_strict"] = c.pathology.isin(known_dis["S"])
    c["concept_collision"] = [(t, w) in COLL for t, w in zip(c.pathology, c.working_diagnosis)]; c["collision_reason"] = [COLL.get((t, w), "") for t, w in zip(c.pathology, c.working_diagnosis)]
    reason = np.where(~c.wd_known_strict & ~c.truth_known_strict, "both_unknown", np.where(~c.wd_known_strict, "wd_unknown", np.where(~c.truth_known_strict, "truth_unknown", np.where(c.concept_collision, "concept_collision", np.where(c.bstrict_knowledge_unavailable, "patient_knowledge_unavailable", "")))))
    c["reachability"] = np.where(reason == "", "EXTERNAL_REACHABLE", "EXTERNAL_UNREACHABLE"); c["unreachable_reason"] = reason
    c["A_prime_common_ok"] = True; return c
# ---------- VALIDATION
va = annotate(load("validate")); va.to_csv(f"{O}/02_bstrict_scores_validation.csv", index=False, columns=[x for x in va.columns if not x.startswith("blenient")]); va[["sample_id", "config", "pathology", "working_diagnosis", "wrong_label", "blenient_score", "blenient_knowledge_unavailable", "blenient_n_evaluable"]].to_csv(f"{O}/03_blenient_scores_validation.csv", index=False)
METH = {"REF_conf": lambda d: -d.model_confidence.values, "REF_margin": lambda d: -d.margin.values, "REF_entropy": lambda d: d.entropy.values, "A_prime": lambda d: d.A_prime_score.values, "B_STRICT": lambda d: d.bstrict_score.values, "B_LENIENT": lambda d: d.blenient_score.values}
FPRS = [0.05, 0.10, 0.20]; thr = {}; zp = {}
for cfg, g in va.groupby("config"):
    ok = g[g.wrong_label == 0]
    for mn, fn in METH.items():
        s = fn(ok); s = s[~np.isnan(s)]; thr[(cfg, mn)] = {f: float(np.quantile(s, 1 - f)) for f in FPRS}
        s_all = fn(g); zp[(cfg, mn)] = (float(np.nanmean(s_all)), float(np.nanstd(s_all) + 1e-9))
json.dump({f"{k[0]}|{k[1]}": v for k, v in thr.items()}, open(f"{O}/04_validation_thresholds.json", "w"), indent=1); json.dump({f"{k[0]}|{k[1]}": v for k, v in zp.items()}, open(f"{O}/04b_validation_zparams.json", "w"), indent=1)
log("validation thresholds fixed")
# ---------- TEST (exactly once)
audit["test_runs"] += 1; audit["test_opened_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
te = annotate(load("test")); te.to_csv(f"{O}/05_bstrict_scores_test.csv", index=False, columns=[x for x in te.columns if not x.startswith("blenient")]); te[["sample_id", "config", "pathology", "working_diagnosis", "wrong_label", "blenient_score", "blenient_knowledge_unavailable", "blenient_n_evaluable"]].to_csv(f"{O}/06_blenient_scores_test.csv", index=False)
ap = pd.read_csv(f"{S13}/02_aprime_internal_scores.csv"); ap = ap[ap.split == "test"]
chk = te.merge(ap, on=["sample_id", "config"], suffixes=("", "_ap")); assert (chk.pathology == chk.pathology_ap).all() and (chk.working_diagnosis == chk.working_diagnosis_ap).all() and (chk.bstrict_n_common == chk.n_common_findings_used).all(), "COMMON input mismatch A' vs B"
pd.DataFrame({"check": ["rows_test", "rows_validation", "same_patient_config_keys_A_B", "same_visible_findings_A_B", "same_wd_truth_A_B", "candidate_set_49_both", "missing_treated_as_negative", "nan_inf_scores(excluding KNOWLEDGE_UNAVAILABLE NaN)"], "value": [len(te), len(va), True, True, True, True, 0, int(np.isinf(te.bstrict_score.fillna(0)).sum())]}).to_csv(f"{O}/01_common_input_audit.csv", index=False)
def evalset(d, mn, cfg, tag, min_n=20):
    s = METH[mn](d); y = d.wrong_label.values; mask = ~np.isnan(s); s, y = s[mask], y[mask]; row = {"config": cfg, "subset": tag, "method": mn, "n": int(len(d)), "n_scored": int(mask.sum()), "n_wrong": int(y.sum()), "n_wrong_scored": int(y.sum()), "n_correct": int((1 - y).sum())}
    if y.sum() >= min_n and (1 - y).sum() >= min_n:
        row.update({"auroc": round(roc_auc_score(y, s), 4), "auprc": round(average_precision_score(y, s), 4), "auprc_baseline": round(float(y.mean()), 4)})
        for f in FPRS:
            t = thr[(cfg, mn)][f]; row[f"sens@fpr{int(f*100)}_valthr"] = round(float((s[y == 1] > t).mean()), 4); row[f"fpr@thr{int(f*100)}_test"] = round(float((s[y == 0] > t).mean()), 4)
        fpr, tpr, _ = roc_curve(y, s); row["tpr@fpr10_roc"] = round(float(np.interp(0.10, fpr, tpr)), 4)
    else: row["note"] = "insufficient sample"
    row["n_wrong_unscored(KNOWLEDGE_UNAVAILABLE)"] = int(d.wrong_label.values[~mask].sum()); return row
overall, strata, reach, corr, incr = [], [], [], [], []
BINS = [(-1, 0.5, "<0.5"), (0.5, 0.7, "0.5-0.7"), (0.7, 0.8, "0.7-0.8"), (0.8, 0.9, "0.8-0.9"), (0.9, 1.01, ">=0.9")]
rng = np.random.default_rng(0)
for cfg, g in te.groupby("config"):
    rch = g[g.reachability == "EXTERNAL_REACHABLE"]; cov_sub = g[g.wd_known_strict & g.truth_known_strict]
    for tag, d in [("ALL_49", g), ("EXTERNAL_REACHABLE", rch), ("COVERAGE_SUBSET(wd&truth known)", cov_sub), ("ALL_49_generic_excluded", g.assign(**{}))]:
        for mn in METH:
            if tag == "ALL_49_generic_excluded" and mn in ("B_STRICT",):
                # 민감도: generic finding 제외한 B (재계산)
                g2 = g.copy(); g2["exposed_common_findings"] = [json.dumps([t for t in json.loads(s) if t.split("_@_")[0] not in generic]) for s in g2.exposed_common_findings]; b, *_ = score(g2, "S"); g2["bstrict_score"] = b; overall.append(evalset(g2, mn, cfg, tag))
            elif tag != "ALL_49_generic_excluded": overall.append(evalset(d, mn, cfg, tag))
    for lo, hi, name in BINS:
        d = g[(g.model_confidence >= lo) & (g.model_confidence < hi)]
        for mn in ["REF_conf", "REF_margin", "REF_entropy", "A_prime", "B_STRICT", "B_LENIENT"]:
            r = evalset(d, mn, cfg, f"conf {name}"); r["n_wrong_reachable"] = int((d.wrong_label.values == 1).sum() and ((d.wrong_label == 1) & (d.reachability == "EXTERNAL_REACHABLE")).sum()); r["wrong_share_of_all_wrong"] = round(float(d.wrong_label.sum() / max(1, g.wrong_label.sum())), 4)
            if name == ">=0.9" and "auroc" in r:  # bootstrap CI
                s = METH[mn](d); y = d.wrong_label.values; mk = ~np.isnan(s); s, y = s[mk], y[mk]; aucs = []
                for _ in range(500):
                    ix = rng.integers(0, len(y), len(y)); 
                    if y[ix].sum() > 0 and (1 - y[ix]).sum() > 0: aucs.append(roc_auc_score(y[ix], s[ix]))
                r["auroc_ci95"] = f"{np.percentile(aucs, 2.5):.3f}-{np.percentile(aucs, 97.5):.3f}"
            strata.append(r)
    w = g[g.wrong_label == 1]; nR = int((w.reachability == "EXTERNAL_REACHABLE").sum())
    t10 = thr[(cfg, "B_STRICT")][0.10]; detB = int((w.bstrict_score > t10).sum()); detB_r = int((w[w.reachability == "EXTERNAL_REACHABLE"].bstrict_score > t10).sum()); tA = thr[(cfg, "A_prime")][0.10]; detA = int((w.A_prime_score > tA).sum())
    zero_dis = set(DIS) - known_dis["S"]
    reach.append({"config": cfg, "wrong_total": len(w), "reachable": nR, "unreachable": len(w) - nR, **{f"unreachable_{k}": int((w.unreachable_reason == k).sum()) for k in ["both_unknown", "wd_unknown", "truth_unknown", "concept_collision", "patient_knowledge_unavailable"]}, "collision_wrong": int(w.concept_collision.sum()), "wrong_involving_zero_knowledge_disease": int((w.pathology.isin(zero_dis) | w.working_diagnosis.isin(zero_dis)).sum()),
                  "reachable_ceiling": round(nR / len(w), 4), "B_detected@fpr10": detB, "B_overall_recall": round(detB / len(w), 4), "B_reachable_recall": round(detB_r / max(1, nR), 4), "A_prime_detected@fpr10": detA, "A_prime_overall_recall": round(detA / len(w), 4)})
    for tag, d in [("ALL", g), ("conf>=0.9", g[g.model_confidence >= 0.9])]:
        for a_, b_ in [("REF_conf", "A_prime"), ("REF_conf", "B_STRICT"), ("A_prime", "B_STRICT"), ("REF_conf", "B_LENIENT")]:
            x, y_ = METH[a_](d), METH[b_](d); mk = ~np.isnan(x) & ~np.isnan(y_)
            corr.append({"config": cfg, "subset": tag, "pair": f"{a_}~{b_}", "n": int(mk.sum()), "spearman": round(float(spearmanr(x[mk], y_[mk])[0]), 4) if mk.sum() > 10 else ""})
        for vname in ["A_prime", "B_STRICT"]:
            m0, s0 = zp[(cfg, "REF_conf")]; m1, s1 = zp[(cfg, vname)]; comb = 0.5 * (METH["REF_conf"](d) - m0) / s0 + 0.5 * (METH[vname](d) - m1) / s1
            dd = d.assign(comb=comb); y = dd.wrong_label.values; mk = ~np.isnan(comb)
            if y[mk].sum() >= 20:
                # 결합 임계: validation에서 동일 규칙으로 고정
                vv = va[va.config == cfg]; vv = vv[vv.model_confidence >= 0.9] if tag != "ALL" else vv; cv = 0.5 * (METH["REF_conf"](vv) - m0) / s0 + 0.5 * (METH[vname](vv) - m1) / s1; ct = np.nanquantile(cv[vv.wrong_label.values == 0], 0.9)
                incr.append({"config": cfg, "subset": tag, "verifier": vname, "n_wrong": int(y[mk].sum()), "auroc_REF_only": round(roc_auc_score(y[mk], METH["REF_conf"](d)[mk]), 4), "auroc_REF_plus": round(roc_auc_score(y[mk], comb[mk]), 4), "auprc_REF_only": round(average_precision_score(y[mk], METH["REF_conf"](d)[mk]), 4), "auprc_REF_plus": round(average_precision_score(y[mk], comb[mk]), 4), "sens@fpr10_REF_only": round(float((METH["REF_conf"](d)[mk][y[mk] == 1] > thr[(cfg, "REF_conf")][0.10]).mean()), 4), "sens@fpr10_REF_plus": round(float((comb[mk][y[mk] == 1] > ct).mean()), 4)})
pd.DataFrame(overall).to_csv(f"{O}/07_overall_metrics.csv", index=False); pd.DataFrame(strata).to_csv(f"{O}/08_confidence_strata.csv", index=False); pd.DataFrame(reach).to_csv(f"{O}/09_reachable_analysis.csv", index=False); pd.DataFrame(corr).to_csv(f"{O}/11_score_correlations.csv", index=False); pd.DataFrame(incr).to_csv(f"{O}/12_incremental_value.csv", index=False)
# ---------- pair analysis (config k3_s42 primary + pooled k3)
pairs = []
for cfg, g in te.groupby("config"):
    w = g[g.wrong_label == 1]; t10 = thr[(cfg, "B_STRICT")][0.10]; tA = thr[(cfg, "A_prime")][0.10]
    for (t, wd_), pg in w.groupby(["pathology", "working_diagnosis"]):
        if len(pg) < 5: continue
        top = collections.Counter(x.split("_@_")[0] for s in pg.exposed_common_findings for x in json.loads(s)).most_common(4)
        pairs.append({"config": cfg, "true_diagnosis": t, "working_diagnosis": wd_, "count": len(pg), "mean_confidence": round(pg.model_confidence.mean(), 3), "reachable_count": int((pg.reachability == "EXTERNAL_REACHABLE").sum()), "collision_count": int(pg.concept_collision.sum()), "unreachable_reasons": dict(collections.Counter(pg.unreachable_reason).most_common(3)),
                      "A_prime_detected@fpr10": int((pg.A_prime_score > tA).sum()), "B_strict_detected@fpr10": int((pg.bstrict_score > t10).sum()), "B_knowledge_unavailable": int(pg.bstrict_knowledge_unavailable.sum()), "top_common_findings": "; ".join(f"{em.loc[e, 'concept_1']}({n})" for e, n in top), "wd_known_strict": bool(wd_ in known_dis["S"]), "truth_known_strict": bool(t in known_dis["S"])})
PA = pd.DataFrame(pairs).sort_values(["config", "count"], ascending=[True, False]); PA.to_csv(f"{O}/10_error_pair_analysis.csv", index=False)
audit["finished"] = time.strftime("%Y-%m-%d %H:%M:%S"); audit["test_rows"] = len(te); audit["existing_files_modified"] = []; json.dump(audit, open(f"{O}/14_test_once_audit.json", "w"), indent=1)
pd.set_option("display.width", 260); OV = pd.DataFrame(overall)
print(OV[(OV.config == "k3_s42")][["subset", "method", "n", "n_wrong", "auroc", "auprc", "sens@fpr10_valthr", "sens@fpr5_valthr", "fpr@thr10_test", "n_wrong_unscored(KNOWLEDGE_UNAVAILABLE)"]].to_string())
ST = pd.DataFrame(strata); print(ST[(ST.config == "k3_s42") & (ST.subset == "conf >=0.9")][["method", "n", "n_wrong", "n_wrong_reachable", "auroc", "auroc_ci95", "sens@fpr10_valthr", "fpr@thr10_test"]].to_string())
print(pd.DataFrame(reach).to_string()); print(pd.DataFrame(corr)[lambda d: d.config == "k3_s42"].to_string()); print(pd.DataFrame(incr)[lambda d: d.config == "k3_s42"].to_string()); print(PA[PA.config == "k3_s42"].head(12)[["true_diagnosis", "working_diagnosis", "count", "mean_confidence", "reachable_count", "collision_count", "A_prime_detected@fpr10", "B_strict_detected@fpr10", "B_knowledge_unavailable", "top_common_findings"]].to_string()); log("DONE")
