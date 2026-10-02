"""STEP 10: HSDN(Zhou 2014) 추가 시 coverage 변화만 확인. 확률 생성·성능 평가 없음.
HSDN 용어는 MeSH 명칭(ID 없음) → MRCONSO SAB=MSH TTY=MH 로 MeSH ID(DUI)·CUI 부여.
질환: step9 01 map의 CUI → MeSH MH(같은 CUI) → HSDN disease 목록 존재 확인. 소견: step9 03 적격 evidence의 concept CUI(step8) → MeSH MH → HSDN symptom 322 존재 확인.
"""
import json, re, collections, hashlib
import numpy as np, pandas as pd
R = "data/hsdn/raw"; P = "data/hsdn/processed"; O = "exp/step10_hsdn"; S9 = "exp/step9_external_knowledge"
hs_d = pd.read_csv(f"{R}/41467_2014_BFncomms5212_MOESM1043_ESM.txt", sep="\t"); hs_s = pd.read_csv(f"{R}/41467_2014_BFncomms5212_MOESM1044_ESM.txt", sep="\t")
hs_e = pd.read_csv(f"{R}/41467_2014_BFncomms5212_MOESM1045_ESM.txt", sep="\t")
hs_e.columns = ["symptom_mesh_term", "disease_mesh_term", "pubmed_cooccurrence", "tfidf_score"]
print("HSDN diseases", len(hs_d), "symptoms", len(hs_s), "edges", len(hs_e), "dup edges", hs_e.duplicated(["symptom_mesh_term", "disease_mesh_term"]).sum(), "NA", hs_e.isna().sum().to_dict())
print("edges: diseases", hs_e.disease_mesh_term.nunique(), "symptoms", hs_e.symptom_mesh_term.nunique(), "tfidf", hs_e.tfidf_score.describe().round(3).to_dict())
# ---- MeSH via MRCONSO
m = pd.read_parquet("data/umls/mrconso_eng.parquet"); msh = m[(m["SAB"] == "MSH")]
mh = msh[msh["TTY"] == "MH"].drop_duplicates(["CUI", "CODE"])
name2 = {}
for r in mh.itertuples(): name2.setdefault(r.STR.lower(), []).append((r.CODE, r.CUI))
cui2mh = collections.defaultdict(list)
for r in mh.itertuples(): cui2mh[r.CUI].append((r.CODE, r.STR))
# HSDN 용어 → MeSH ID (MH 정확 일치; 없으면 entry term(TTY ET/PEP) 일치)
et = msh[msh["TTY"].isin(["ET", "PEP", "NM", "PM"])]; et_name = {}
for r in et.itertuples(): et_name.setdefault(r.STR.lower(), (r.CODE, r.CUI))
def mesh_lookup(term):
    t = term.lower()
    if t in name2: c = name2[t][0]; return c[0], c[1], "MH"
    if t in et_name: c = et_name[t]; return c[0], c[1], "ENTRY_TERM"
    return "", "", "NONE"
for df, col in [(hs_d, "MeSH Disease Term"), (hs_s, "MeSH Symptom Term")]:
    r = df[col].map(mesh_lookup); df["mesh_id"] = [x[0] for x in r]; df["umls_cui"] = [x[1] for x in r]; df["mesh_match"] = [x[2] for x in r]
print("HSDN disease terms with MeSH ID", (hs_d.mesh_id != "").sum(), "/", len(hs_d), "| symptoms", (hs_s.mesh_id != "").sum(), "/", len(hs_s))
hs_d.to_csv(f"{P}/hsdn_disease_terms_mesh.csv", index=False); hs_s.to_csv(f"{P}/hsdn_symptom_terms_mesh.csv", index=False)
E = hs_e.merge(hs_s[["MeSH Symptom Term", "mesh_id", "umls_cui"]].rename(columns={"MeSH Symptom Term": "symptom_mesh_term", "mesh_id": "symptom_mesh_id", "umls_cui": "symptom_cui"}), on="symptom_mesh_term", how="left") \
        .merge(hs_d[["MeSH Disease Term", "mesh_id", "umls_cui"]].rename(columns={"MeSH Disease Term": "disease_mesh_term", "mesh_id": "disease_mesh_id", "umls_cui": "disease_cui"}), on="disease_mesh_term", how="left")
E.to_parquet(f"{P}/hsdn_edges_mesh.parquet", index=False)
hs_dset = set(hs_d["MeSH Disease Term"].str.lower()); hs_sset = set(hs_s["MeSH Symptom Term"].str.lower())
hs_d_by_mesh = hs_d[hs_d.mesh_id != ""].set_index("mesh_id")["MeSH Disease Term"].to_dict(); hs_s_by_mesh = hs_s[hs_s.mesh_id != ""].set_index("mesh_id")["MeSH Symptom Term"].to_dict()
# ---- 3. 질환 매핑
dm = pd.read_csv(f"{S9}/01_disease_concept_map.csv", dtype=str).fillna("")
qt = pd.read_csv(f"{S9}/disease_query_table.tsv", sep="\t", dtype=str).fillna("")
SUBTYPE_KW = ["familial", "hereditary", "congenital", "juvenile", "neonatal", "chronic", "acute", "complicat", "syndrome", "susceptib"]
rows = []
for r in dm.itertuples():
    cands = [(code, nm, "CUI→MeSH") for code, nm in cui2mh.get(r.umls_cui, []) if code in hs_d_by_mesh]
    # 2차: 표준명/검색어 문자열이 HSDN disease 명칭과 정확히 같은가
    q = qt[qt.ddxplus_disease == r.ddxplus_disease].iloc[0]; names = [q.primary_query] + [a for a in q.alt_queries.split(";") if a] + [r.umls_name]
    for nmq in names:
        for code, cui in name2.get(nmq.lower(), []):
            if code in hs_d_by_mesh and code not in [c[0] for c in cands]: cands.append((code, hs_d_by_mesh[code], "NAME→MeSH"))
    # 3차: 검토용 후보 — HSDN disease 중 primary query 단어를 모두 포함
    rev = []
    if not cands:
        ws = set(re.findall(r"[a-z]+", q.primary_query.lower())) - {"of", "the", "acute", "disease", "infection"}
        for t in hs_d["MeSH Disease Term"]:
            tl = t.lower()
            if ws and all(w in tl for w in ws): rev.append(t)
    base_name = q.primary_query.lower()
    if cands:
        code, nm, how = cands[0]; nml = nm.lower()
        hier = nml != base_name and nml != r.umls_name.lower()
        kw = [k for k in SUBTYPE_KW if (k in nml) != (k in base_name)]
        status = "EXACT" if (how == "CUI→MeSH" and not kw) else ("PARTIAL" if not kw else "AMBIGUOUS")
        if len(cands) > 1: status = "AMBIGUOUS"
        reason = f"{how}: {nm} [{code}]" + ("; name differs from DDXPlus primary → check granularity" if hier else "") + (f"; qualifier mismatch {kw}" if kw else "") + (f"; {len(cands)} MeSH candidates" if len(cands) > 1 else "")
        if r.mapping_status != "EXACT": status = "AMBIGUOUS" if r.mapping_status == "AMBIGUOUS" else ("PARTIAL" if status == "EXACT" else status); reason += f"; step9 disease status={r.mapping_status}"
    else:
        code, nm, how, status = "", "", "", "FAIL"; reason = "no MeSH MH on CUI present in HSDN; " + (f"review candidates by word overlap: {rev[:6]}" if rev else "no word-overlap candidate")
    rows.append({"ddxplus_disease": r.ddxplus_disease, "ddxplus_code": r.ddxplus_code, "umls_cui": r.umls_cui, "umls_name": r.umls_name, "mesh_id": code, "hsdn_disease_name": nm, "hsdn_disease_id": code, "mapping_status": status, "mapping_method": how,
                 "mapping_reason": reason, "review_needed": status != "EXACT", "alternative_candidates": "; ".join(f"{c[1]}[{c[0]}]({c[2]})" for c in cands[1:]) + ("; REVIEW:" + "; ".join(rev[:8]) if rev else ""), "step9_status": r.mapping_status})
DM = pd.DataFrame(rows); DM.to_csv(f"{O}/01_hsdn_disease_map.csv", index=False)
assert len(DM) == 49 and DM.mapping_status.value_counts().sum() == 49
print("disease map", DM.mapping_status.value_counts().to_dict())
# ---- 4. 소견 매핑
el = pd.read_csv(f"{S9}/03_evidence_eligibility.csv", dtype=str).fillna(""); em = pd.read_csv("exp/step8_mapping/evidence_concept_map.csv", dtype=str).fillna("").set_index("evidence_id")
elig = el[el.finding_eligible == "True"]; print("eligible findings (recomputed)", len(elig))
# SNOMED-only 증상(HPO 없어 step9 부적격)도 HSDN 후보로 별도 표시
sn_only = el[(el.finding_eligible == "False") & el.evidence_type.isin(["SYMPTOM", "SIGN"])]
GENERIC_MESH = {"pain", "body weight", "signs and symptoms", "disease", "fever"}  # 검토 플래그용(fever는 비특이 플래그만)
frows = []
for r in pd.concat([elig.assign(pool="eligible"), sn_only.assign(pool="snomed_only_symptom")]).itertuples():
    e = em.loc[r.evidence_id]; out = {"evidence_id": r.evidence_id, "original_question": r.original_question, "evidence_type": r.evidence_type, "pool": r.pool, "operator": r.operator}
    for k in (1, 2):
        cname, ccui = e[f"concept_{k}"], e[f"concept_{k}_cui"]; mhs = [(c, n) for c, n in cui2mh.get(ccui, []) if c in hs_s_by_mesh]; how = "CUI→MeSH"
        if not mhs and cname:
            for c, cui in name2.get(cname.lower(), []):
                if c in hs_s_by_mesh: mhs.append((c, hs_s_by_mesh[c])); how = "NAME→MeSH"
        out.update({f"concept_{k}": cname, f"concept_{k}_cui": ccui, f"concept_{k}_mesh_id": mhs[0][0] if mhs else "", f"concept_{k}_hsdn_symptom": mhs[0][1] if mhs else "", f"concept_{k}_method": how if mhs else ("" if not cname else "NONE")})
    n_ok = sum(bool(out[f"concept_{k}_mesh_id"]) for k in (1, 2)); n_c = sum(bool(out[f"concept_{k}"]) for k in (1, 2))
    out["mapping_status"] = "FAIL" if n_ok == 0 else ("EXACT" if n_c == 1 else ("COMPOSITE" if n_ok == n_c else "PARTIAL"))
    out["generic_flag"] = any(out[f"concept_{k}_hsdn_symptom"].lower() in GENERIC_MESH for k in (1, 2))
    out["review_needed"] = out["mapping_status"] != "EXACT" or out["generic_flag"] or any(out[f"concept_{k}_method"] == "NAME→MeSH" for k in (1, 2))
    frows.append(out)
FM = pd.DataFrame(frows); FM.to_csv(f"{O}/02_hsdn_finding_map.csv", index=False)
print("finding map (eligible)", FM[FM.pool == "eligible"].mapping_status.value_counts().to_dict(), "| snomed-only", FM[FM.pool != "eligible"].mapping_status.value_counts().to_dict())
# ---- 5. 관계 추출
ok = DM[DM.mapping_status != "FAIL"]; ed = []
for r in ok.itertuples():
    sub = E[E.disease_mesh_id == r.mesh_id]
    for x in sub.itertuples():
        ed.append({"ddxplus_disease": r.ddxplus_disease, "hsdn_disease_id": r.mesh_id, "hsdn_disease_name": r.hsdn_disease_name, "finding_name": x.symptom_mesh_term, "mesh_id": x.symptom_mesh_id, "umls_cui": x.symptom_cui,
                   "original_hsdn_weight": x.tfidf_score, "pubmed_cooccurrence": x.pubmed_cooccurrence, "source": "HSDN", "relation_type": "literature_cooccurrence_tfidf"})
ED = pd.DataFrame(ed); ED.to_csv(f"{O}/03_hsdn_disease_finding_edges.csv", index=False)
print("HSDN edges for our diseases", len(ED), "diseases with edges", ED.ddxplus_disease.nunique(), "dup", ED.duplicated(["ddxplus_disease", "mesh_id"]).sum())
# ---- 6. coverage 전/후 (STEP9 정의: 적격 finding 중 외부지식에 존재. HPO/OKG=strict_nonself 기준 detail 재사용)
cov9 = pd.read_csv(f"{S9}/04_disease_coverage.csv"); det9 = pd.read_csv(f"{S9}/04b_coverage_detail.csv")
cond = json.load(open("data/ddxplus/en/release_conditions.json"))
fm_e = FM[FM.pool == "eligible"].set_index("evidence_id"); hs_by_dis = ED.groupby("ddxplus_disease")["mesh_id"].agg(set).to_dict()
crow, cdet = [], []
for dis, v in cond.items():
    rel = list(v["symptoms"]) + list(v["antecedents"]); el_ids = [e for e in rel if e in fm_e.index]
    d9 = det9[det9.ddxplus_disease == dis].set_index("evidence_id"); hs = hs_by_dis.get(dis, set())
    n_h = n_k = n_hk = n_hs = n_all = n_fm = 0
    for e in el_ids:
        h = bool(d9.loc[e, "hpo_match"]) if e in d9.index else False; k = bool(d9.loc[e, "okg_match"]) if e in d9.index else False
        prev = bool(d9.loc[e, "strict_nonself"]) if e in d9.index else False
        ms = {fm_e.loc[e, "concept_1_mesh_id"], fm_e.loc[e, "concept_2_mesh_id"]} - {""}; s = bool(ms & hs); n_fm += bool(ms)
        n_h += h; n_k += k; n_hk += prev; n_hs += s; n_all += (prev or s)
        cdet.append({"ddxplus_disease": dis, "evidence_id": e, "concept_1": fm_e.loc[e, "concept_1"], "hsdn_symptom": fm_e.loc[e, "concept_1_hsdn_symptom"], "hpo_okg_strict_nonself": prev, "hsdn_match": s})
    n = len(el_ids)
    crow.append({"ddxplus_disease": dis, "hsdn_disease_status": DM.set_index("ddxplus_disease").loc[dis, "mapping_status"], "n_eligible_findings": n, "n_findings_with_mesh": n_fm, "hpo_matched": n_h, "okg_matched": n_k, "hpo_okg_union_strict_nonself": n_hk, "hsdn_matched": n_hs, "hpo_okg_hsdn_union": n_all,
                 "coverage_before": round(n_hk / n, 3) if n else None, "coverage_after": round(n_all / n, 3) if n else None, "coverage_gain": round((n_all - n_hk) / n, 3) if n else None, "n_hsdn_edges_total": len(hs)})
CV = pd.DataFrame(crow); CV.to_csv(f"{O}/04_coverage_before_after.csv", index=False); pd.DataFrame(cdet).to_csv(f"{O}/04b_coverage_detail.csv", index=False)
# ---- 7. 흔한 질환
COMMON = ["Influenza", "Viral pharyngitis", "URTI", "Bronchitis", "Pneumonia", "Acute rhinosinusitis", "Acute otitis media", "Anemia", "GERD", "Pulmonary embolism", "Anaphylaxis", "Panic attack", "Acute laryngitis", "Croup", "Bronchiolitis", "Tuberculosis", "Atrial fibrillation", "Unstable angina", "Possible NSTEMI / STEMI", "Acute pulmonary edema"]
DET = pd.DataFrame(cdet); ca = []
for dis in COMMON:
    d = DET[DET.ddxplus_disease == dis]; c = CV[CV.ddxplus_disease == dis].iloc[0]
    ca.append({"ddxplus_disease": dis, "hsdn_mapped": c.hsdn_disease_status != "FAIL", "hsdn_disease": DM.set_index("ddxplus_disease").loc[dis, "hsdn_disease_name"], "n_eligible": c.n_eligible_findings, "hsdn_matched": c.hsdn_matched, "coverage_before": c.coverage_before, "coverage_after": c.coverage_after,
               "matched_findings": "; ".join(d[d.hsdn_match].concept_1.head(8)), "missing_findings": "; ".join(d[~d.hsdn_match].concept_1.head(8))})
pd.DataFrame(ca).to_csv(f"{O}/05_common_disease_audit.csv", index=False)
# ---- 8. review queue
rq = []
for r in DM[DM.review_needed].itertuples(): rq.append({"item_type": "disease_map", "id": r.ddxplus_disease, "issue": r.mapping_status, "detail": r.mapping_reason, "candidates": r.alternative_candidates})
for r in FM[FM.review_needed & (FM.pool == "eligible")].itertuples(): rq.append({"item_type": "finding_map", "id": r.evidence_id, "issue": ("generic_symptom; " if r.generic_flag else "") + r.mapping_status, "detail": f"{r.concept_1}→{r.concept_1_hsdn_symptom} ({r.concept_1_method}); {r.concept_2}→{r.concept_2_hsdn_symptom}", "candidates": ""})
dn = DM.set_index("ddxplus_disease")
for r in ED.itertuples():
    iss = []
    if r.finding_name.lower() in GENERIC_MESH: iss.append("generic_symptom")
    if r.finding_name.lower() == r.hsdn_disease_name.lower() or r.umls_cui == dn.loc[r.ddxplus_disease, "umls_cui"]: iss.append("self_reference")
    if r.pubmed_cooccurrence <= 1: iss.append("single_pubmed_cooccurrence")
    if iss: rq.append({"item_type": "hsdn_edge", "id": f"{r.ddxplus_disease}|{r.finding_name}", "issue": ";".join(iss), "detail": f"tfidf={r.original_hsdn_weight:.3f} cooc={r.pubmed_cooccurrence}", "candidates": ""})
RQ = pd.DataFrame(rq); RQ.to_csv(f"{O}/06_review_queue.csv", index=False)
# ---- summary
def q(x): return {k: (None if pd.isna(v) else round(float(v), 3)) for k, v in x.describe().items()}
cb, caft = CV.coverage_before.fillna(0), CV.coverage_after.fillna(0)
summ = {"hsdn": {"diseases": len(hs_d), "symptoms": len(hs_s), "edges": len(hs_e), "disease_terms_with_mesh_id": int((hs_d.mesh_id != "").sum()), "symptom_terms_with_mesh_id": int((hs_s.mesh_id != "").sum())},
        "disease_map": DM.mapping_status.value_counts().to_dict(), "diseases_with_hsdn_edges": int(ED.ddxplus_disease.nunique()), "diseases_usable_before": int((CV.hpo_okg_union_strict_nonself > 0).sum()), "diseases_usable_after": int((CV.hpo_okg_hsdn_union > 0).sum()),
        "diseases_with_any_external_edges_before": int(cov9.has_nonself_source.sum()), "diseases_with_any_external_edges_after": int((cov9.has_nonself_source | CV.ddxplus_disease.isin(ED.ddxplus_disease)).sum()),
        "findings": {"eligible": int(len(elig)), "hsdn_mapped_exact": int((FM[FM.pool == "eligible"].mapping_status == "EXACT").sum()), "hsdn_mapped_any": int((FM[FM.pool == "eligible"].mapping_status != "FAIL").sum()), "fail": int((FM[FM.pool == "eligible"].mapping_status == "FAIL").sum()), "snomed_only_symptoms_mappable": int((FM[FM.pool != "eligible"].mapping_status != "FAIL").sum())},
        "coverage_before": q(cb), "coverage_after": q(caft), "zero_before": int((cb == 0).sum()), "zero_after": int((caft == 0).sum()),
        "ge25_before": int((cb >= .25).sum()), "ge25_after": int((caft >= .25).sum()), "ge50_before": int((cb >= .5).sum()), "ge50_after": int((caft >= .5).sum()), "ge75_before": int((cb >= .75).sum()), "ge75_after": int((caft >= .75).sum()),
        "hsdn_edges_for_our_diseases": len(ED), "dup_edges": int(ED.duplicated(["ddxplus_disease", "mesh_id"]).sum()), "review_queue": RQ.item_type.value_counts().to_dict() if len(RQ) else {}}
json.dump(summ, open(f"{O}/07_summary.json", "w"), indent=1, default=str); print(json.dumps(summ, indent=1, default=str))
pd.set_option("display.width", 250); print(CV[["ddxplus_disease", "hsdn_disease_status", "n_eligible_findings", "hpo_okg_union_strict_nonself", "hsdn_matched", "hpo_okg_hsdn_union", "coverage_before", "coverage_after"]].to_string()); print("DONE")
