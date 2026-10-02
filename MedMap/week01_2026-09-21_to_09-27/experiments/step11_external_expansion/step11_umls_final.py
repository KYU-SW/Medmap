"""STEP 11 FINAL: UMLS MRREL 관계 추가 + coverage 최종 재계산 (provenance family 기반 독립 지지). 학습·S2·AUROC 없음."""
import json, re, collections, time
import numpy as np, pandas as pd
O = "exp/step11_external_expansion"; S8 = "exp/step8_mapping"; S9 = "exp/step9_external_knowledge"; S10 = "exp/step10_hsdn"; R = "data/umls/2026AA/relations"
t0 = time.time(); log = lambda *a: print(f"[{time.time()-t0:5.0f}s]", *a, flush=True)
cond = json.load(open("data/ddxplus/en/release_conditions.json")); assert len(cond) == 49
dm = pd.read_csv(f"{S9}/01_disease_concept_map.csv", dtype=str).fillna("").set_index("ddxplus_disease"); cui2dis = {r.umls_cui: d for d, r in dm.iterrows()}
em = pd.read_csv(f"{S8}/evidence_concept_map.csv", dtype=str).fillna("").set_index("evidence_id"); el = pd.read_csv(f"{S9}/03_evidence_eligibility.csv", dtype=str).fillna("")
elig = el[el.finding_eligible == "True"].set_index("evidence_id"); generic9 = set(el[el.too_generic_flag == "True"].evidence_id); log("eligible", len(elig))
m = pd.read_parquet("data/umls/mrconso_eng.parquet"); pref = m[m.ISPREF == "Y"].drop_duplicates("CUI").set_index("CUI")["STR"].to_dict()
msh = m[(m.SAB == "MSH") & (m.TTY == "MH")]; cui2mesh = msh.groupby("CUI")["CODE"].agg(set).to_dict(); hpo_all = m[m.SAB == "HPO"].groupby("CUI")["CODE"].agg(set).to_dict()
# evidence keys
ecui2ev = collections.defaultdict(set); EK = {}
for e in elig.index:
    r = em.loc[e]; ks = {"cui": set(), "hpo": set(), "mesh": set()}
    for k in (1, 2):
        c, h = r[f"concept_{k}_cui"], r[f"concept_{k}_hpo"].split(";")[0]
        if c: ks["cui"].add(c); ks["mesh"] |= cui2mesh.get(c, set()); ecui2ev[c].add(e)
        if h: ks["hpo"].add(h)
    EK[e] = ks
ecui = set(ecui2ev)
dis_rel = {d: [e for e in list(v["symptoms"]) + list(v["antecedents"]) if e in elig.index] for d, v in cond.items()}
# ---------------- MRSAB / MRSTY
sab = pd.read_csv(f"{R}/MRSAB.RRF", sep="|", header=None, dtype=str, quoting=3, na_filter=False); sab_name = dict(zip(sab[3], sab[4])); sab_srl = dict(zip(sab[3], sab[13]))
sty_rows = []
with open(f"{R}/MRSTY.RRF") as f:
    need = set(cui2dis) | ecui
    for line in f:
        p = line.split("|")
        if p[0] in need: sty_rows.append((p[0], p[3]))
sty = collections.defaultdict(set)
for c, s in sty_rows: sty[c].add(s)
log("MRSTY loaded for", len(sty), "CUIs")
# ---------------- 01a → audit
rel = pd.read_csv(f"{O}/01a_umls_relations_around_ddx_diseases.csv", dtype=str).fillna("")
rel["involves_evidence_cui"] = rel.CUI1.isin(ecui) | rel.CUI2.isin(ecui)
aud = rel.groupby(["REL", "RELA", "SAB", "SUPPRESS"]).agg(n=("CUI1", "size"), n_with_evidence_cui=("involves_evidence_cui", "sum")).reset_index().sort_values("n", ascending=False)
aud["SAB_name"] = aud.SAB.map(sab_name); aud.to_csv(f"{O}/01b_umls_relation_type_audit.csv", index=False)
# ---------------- 06. disease↔finding edges (both directions), SUPPRESS 분리
hit = rel[((rel.CUI1.isin(cui2dis)) & (rel.CUI2.isin(ecui))) | ((rel.CUI2.isin(cui2dis)) & (rel.CUI1.isin(ecui)))].copy()
n_supp = int((hit.SUPPRESS != "N").sum()); hit = hit[hit.SUPPRESS == "N"]
DIRECT = {"has_manifestation", "manifestation_of", "has_definitional_manifestation", "definitional_manifestation_of", "has_associated_finding", "associated_finding_of", "has_sign_or_symptom", "sign_or_symptom_of", "has_finding", "finding_of"}
POSSIBLE = {"clinically_associated_with", "co-occurs_with", "ssc"}
NONF = {"isa", "inverse_isa", "mapped_to", "mapped_from", "translation_of", "has_translation", "classifies", "classified_as", "due_to", "cause_of", "may_treat", "may_be_treated_by", "has_causative_agent", "causative_agent_of", "ddx", "was_a", "inverse_was_a", "replaces", "replaced_by", "possibly_equivalent_to", "same_as", "has_alias", "alias_of", "primary_mapped_to", "primary_mapped_from", "used_for", "use", "see", "see_from", "refers_to", "referred_to_by", "clinically_similar", "has_default_inpatient_classification", "has_default_outpatient_classification", "default_inpatient_classification_of", "default_outpatient_classification_of", "has_associated_condition", "associated_condition_of", "interprets", "is_interpreted_by", "has_finding_site", "finding_site_of", "may_prevent", "may_be_prevented_by"}
def quality(rela, rel_):
    if rel_ in ("SY", "PAR", "CHD", "RB", "RN") and rela not in DIRECT: return "NON_FINDING"
    if rela in DIRECT: return "DIRECT_FINDING"
    if rela in POSSIBLE: return "POSSIBLE_FINDING"
    if rela in NONF: return "NON_FINDING"
    return "AMBIGUOUS"  # associated_with, related_to, '' 등
LINEAGE = {"HPO": "CURATED_PHENOTYPE(overlaps HPO)", "OMIM": "CURATED_PHENOTYPE(overlaps HPO/OMIM)", "MSH": "MeSH hierarchy (overlaps HSDN/MEDLINE vocabulary)", "MEDLINEPLUS": "MedlinePlus (overlaps Wikidata references)"}
edges = []
for r in hit.itertuples():
    if r.CUI1 in cui2dis and r.CUI2 in ecui: d, fc, direction = cui2dis[r.CUI1], r.CUI2, "disease->finding"
    else: d, fc, direction = cui2dis[r.CUI2], r.CUI1, "finding->disease"
    q = quality(r.RELA, r.REL)
    for e in ecui2ev[fc]:
        edges.append({"ddxplus_disease": d, "disease_cui": dm.loc[d, "umls_cui"], "finding": em.loc[e, "concept_1"] if em.loc[e, "concept_1_cui"] == fc else em.loc[e, "concept_2"], "finding_cui": fc, "evidence_id": e, "finding_umls_pref": pref.get(fc, ""), "finding_semantic_types": ";".join(sorted(sty.get(fc, []))),
                      "REL": r.REL, "RELA": r.RELA, "SAB": r.SAB, "SAB_name": sab_name.get(r.SAB, ""), "SAB_SRL": sab_srl.get(r.SAB, ""), "RUI": r.RUI, "SUPPRESS": r.SUPPRESS, "relation_direction": direction, "quality_class": q,
                      "lineage_overlap": LINEAGE.get(r.SAB, ""), "mapping_confidence": "CUI-exact(step8 concept CUI == MRREL CUI)", "review_needed": q != "DIRECT_FINDING" or bool(LINEAGE.get(r.SAB, ""))})
UE = pd.DataFrame(edges).drop_duplicates(["ddxplus_disease", "evidence_id", "finding_cui", "RELA", "SAB", "RUI"]); UE.to_csv(f"{O}/01_umls_disease_finding_edges.csv", index=False)
log("UMLS edges", len(UE), "suppressed excluded", n_supp, UE.quality_class.value_counts().to_dict())
# ---------------- 01c provenance
FAM = {"HSDN": "LITERATURE_COOCCURRENCE", "MEDLINE": "LITERATURE_COOCCURRENCE", "HPO": "CURATED_PHENOTYPE", "OPTIMUSKG": "CURATED_PHENOTYPE", "DISMECH": "STRUCTURED_CURATED", "WIKIDATA": "COMMUNITY"}
def umls_family(sab_): return "CURATED_PHENOTYPE" if sab_ in ("HPO", "OMIM") else ("LITERATURE_COOCCURRENCE" if sab_ == "MSH" else f"UMLS_{sab_}")
prov = [{"source": s, "provenance_family": f, "note": ""} for s, f in FAM.items()]
for s_, g in UE.groupby("SAB"): prov.append({"source": f"UMLS:{s_}", "provenance_family": umls_family(s_), "note": f"{sab_name.get(s_, '')}; SRL={sab_srl.get(s_, '')}; edges={len(g)}; quality={g.quality_class.value_counts().to_dict()}; {LINEAGE.get(s_, '')}"})
pd.DataFrame(prov).to_csv(f"{O}/01c_umls_source_provenance.csv", index=False)
# ---------------- 다른 소스 edge 로드 → (disease, evidence) 매칭 with lenient/strict
e9 = pd.read_csv(f"{S9}/02_external_disease_finding_edges.csv", dtype=str).fillna(""); e10 = pd.read_csv(f"{S10}/03_hsdn_disease_finding_edges.csv", dtype=str).fillna("")
DE = pd.read_csv(f"{O}/03_dismech_disease_finding_edges.csv", dtype=str).fillna(""); ME = pd.read_csv(f"{O}/06_medline_disease_finding_edges.csv", dtype=str).fillna(""); WE = pd.read_csv(f"{O}/07_wikidata_disease_finding_edges.csv", dtype=str).fillna("")
hs_dm = pd.read_csv(f"{S10}/01_hsdn_disease_map.csv", dtype=str).fillna("").set_index("ddxplus_disease")
def fl(x):
    try: return float(x)
    except: return np.nan
M = collections.defaultdict(lambda: collections.defaultdict(set))  # M[(d,e)][source] = {"L","S"} lenient/strict
def add(d, keyset, src, strict_ok, key):
    for e in dis_rel.get(d, []):
        if EK[e][key] & keyset:
            M[(d, e)][src].add("L")
            if strict_ok: M[(d, e)][src].add("S")
for r in e9.itertuples():
    src = "OPTIMUSKG" if r.source.startswith("OptimusKG") else "HPO"; ok = (r.hpo_aspect.find("P") >= 0) and r.self_phenotype != "True" and r.negative_annotation != "True" and ("familial" not in r.reference_type)
    if r.finding_hpo: add(r.ddxplus_disease, {r.finding_hpo}, src, ok, "hpo")
for r in e10.itertuples(): add(r.ddxplus_disease, {r.mesh_id}, "HSDN", fl(r.pubmed_cooccurrence) >= 2 and hs_dm.loc[r.ddxplus_disease, "mapping_status"] in ("EXACT", "PARTIAL"), "mesh")
for r in DE.itertuples():
    if r.finding_hpo: add(r.ddxplus_disease, {r.finding_hpo}, "DISMECH", r.has_pubmed_evidence == "True", "hpo")
for r in ME.itertuples(): add(r.ddxplus_disease, {r.finding_mesh}, "MEDLINE", fl(r.cooccurrence) >= 2, "mesh")
for r in WE.itertuples():
    ks = {"cui": {r.finding_cui} - {""}, "hpo": {r.finding_hpo} - {""}, "mesh": {r.finding_mesh} - {""}}
    for k, v in ks.items():
        if v: add(r.ddxplus_disease, v, "WIKIDATA", r.has_reference == "True", k)
for r in UE.itertuples():
    for e in dis_rel.get(r.ddxplus_disease, []):
        if e == r.evidence_id and r.quality_class in ("DIRECT_FINDING", "POSSIBLE_FINDING", "AMBIGUOUS"): M[(r.ddxplus_disease, e)][f"UMLS:{r.SAB}"].add("L")  # NON_FINDING(isa/mapping/translation)은 lenient에서도 제외
        if e == r.evidence_id and r.quality_class == "DIRECT_FINDING" and not r.lineage_overlap: M[(r.ddxplus_disease, e)][f"UMLS:{r.SAB}"].add("S")
# self-reference / generic exclusion for strict
dnames = {d: {dm.loc[d, "umls_name"].lower(), d.lower()} for d in cond}
STAGES = [("A:HPO+OKG", {"HPO", "OPTIMUSKG"}), ("B:+HSDN", {"HSDN"}), ("C:+DisMech", {"DISMECH"}), ("D:+MEDLINE", {"MEDLINE"}), ("E:+Wikidata", {"WIKIDATA"}), ("F:+UMLS_MRREL", None)]
rows, det, mat = [], [], []
for d, evs in dis_rel.items():
    n = len(evs); nst = sum(e not in generic9 for e in evs); accL = {s: 0 for s, _ in STAGES}; accS = {s: 0 for s, _ in STAGES}
    for e in evs:
        srcs = M.get((d, e), {}); gen = e in generic9 or em.loc[e, "concept_1"].lower() in dnames[d]
        cumL = set(); cumS = set()
        for s, members in STAGES:
            mem = members if members else {k for k in srcs if k.startswith("UMLS:")}
            cumL |= {k for k in mem if "L" in srcs.get(k, set())}; cumS |= {k for k in mem if "S" in srcs.get(k, set())}
            accL[s] += bool(cumL); accS[s] += bool(cumS) and not gen
        fam_L = {FAM.get(k, umls_family(k[5:]) if k.startswith("UMLS:") else k) for k in srcs if "L" in srcs[k]}; fam_S = {FAM.get(k, umls_family(k[5:]) if k.startswith("UMLS:") else k) for k in srcs if "S" in srcs[k]}
        det.append({"ddxplus_disease": d, "evidence_id": e, "finding": em.loc[e, "concept_1"], "generic_or_self": gen, "sources_lenient": ";".join(sorted(k for k in srcs if "L" in srcs[k])), "sources_strict": ";".join(sorted(k for k in srcs if "S" in srcs[k])), "umls_any": any(k.startswith("UMLS:") for k in srcs), "umls_direct": any(k.startswith("UMLS:") and "S" in srcs[k] for k in srcs),
                    "raw_source_support_count": sum(1 for k in srcs if "L" in srcs[k]), "independent_provenance_support_count": len(fam_L), "independent_provenance_support_count_strict": len(fam_S), "families_lenient": ";".join(sorted(fam_L)), "families_strict": ";".join(sorted(fam_S))})
    row = {"ddxplus_disease": d, "n_eligible_findings": n, "n_strict_denominator": nst}
    for s, _ in STAGES: row[f"matched|{s}"] = accL[s]; row[f"cov|{s}"] = round(accL[s] / n, 3) if n else None; row[f"matched_strict|{s}"] = accS[s]; row[f"cov_strict|{s}"] = round(accS[s] / nst, 3) if nst else None
    rows.append(row)
CV = pd.DataFrame(rows); CV.to_csv(f"{O}/08_coverage_by_source_final.csv", index=False); DET = pd.DataFrame(det); DET.to_csv(f"{O}/08b_coverage_detail_final.csv", index=False)
inc, prev = [], None
for s, _ in STAGES:
    c = CV[f"cov|{s}"].fillna(0); cs = CV[f"cov_strict|{s}"].fillna(0); mt = CV[f"matched|{s}"]; ms = CV[f"matched_strict|{s}"]
    inc.append({"stage": s, "mean_cov": round(c.mean(), 3), "median_cov": round(c.median(), 3), "mean_cov_strict": round(cs.mean(), 3), "median_cov_strict": round(cs.median(), 3), "zero_cov": int((c == 0).sum()), "zero_cov_strict": int((cs == 0).sum()), "ge25": int((c >= .25).sum()), "ge50": int((c >= .5).sum()), "ge75": int((c >= .75).sum()), "ge50_strict": int((cs >= .5).sum()),
                "matched_pairs": int(mt.sum()), "matched_pairs_strict": int(ms.sum()), "new_pairs_vs_prev": int((mt - CV[f"matched|{prev}"]).sum()) if prev else "", "new_pairs_strict_vs_prev": int((ms - CV[f"matched_strict|{prev}"]).sum()) if prev else "", "newly_alive_diseases": int(((mt > 0) & (CV[f"matched|{prev}"] == 0)).sum()) if prev else "", "newly_alive_strict": int(((ms > 0) & (CV[f"matched_strict|{prev}"] == 0)).sum()) if prev else ""}); prev = s
INC = pd.DataFrame(inc); INC.to_csv(f"{O}/09_coverage_incremental_final.csv", index=False); print(INC.to_string())
# ---------------- 01d previous zero diseases (기존 08 파일에서 실제로 읽음)
old = pd.read_csv(f"{O}/08_coverage_by_source.csv"); zero_before = list(old[old["cov|+WIKIDATA"].fillna(0) == 0].ddxplus_disease)
rec = []
for d in zero_before:
    c = dm.loc[d, "umls_cui"]; around = rel[(rel.CUI1 == c) | (rel.CUI2 == c)]; ue = UE[UE.ddxplus_disease == d]; dd = DET[DET.ddxplus_disease == d]; r = CV[CV.ddxplus_disease == d].iloc[0]
    rec.append({"ddxplus_disease": d, "umls_cui": c, "cui_in_umls": bool(c), "n_mrrel_relations_around": len(around), "n_relations_with_evidence_cui": int(around.involves_evidence_cui.sum()), "n_finding_edges_any_quality": len(ue), "n_direct_finding_edges": int((ue.quality_class == "DIRECT_FINDING").sum()), "n_possible_finding_edges": int((ue.quality_class == "POSSIBLE_FINDING").sum()),
                "matched_eligible_findings_umls": int(dd.umls_any.sum()), "coverage_before": float(old.set_index("ddxplus_disease").loc[d, "cov|+WIKIDATA"]) if not pd.isna(old.set_index("ddxplus_disease").loc[d, "cov|+WIKIDATA"]) else 0, "coverage_after": r["cov|F:+UMLS_MRREL"], "coverage_after_strict": r["cov_strict|F:+UMLS_MRREL"], "newly_alive": bool(r["matched|F:+UMLS_MRREL"] > 0), "newly_alive_strict": bool(r["matched_strict|F:+UMLS_MRREL"] > 0),
                "umls_matched_findings": "; ".join(dd[dd.umls_any].finding), "umls_relas": ";".join(sorted(set(ue.RELA + "@" + ue.SAB)))})
REC = pd.DataFrame(rec); REC.to_csv(f"{O}/01d_previous_zero_disease_umls_recovery.csv", index=False); REC.to_csv(f"{O}/10_previous_failure_recovery_final.csv", index=False)
# ---------------- long final + matrix final + review queue
long = pd.read_csv(f"{O}/12_all_external_edges_long.csv", dtype=str).fillna("")
ul = pd.DataFrame({"ddxplus_disease": UE.ddxplus_disease, "finding": UE.finding, "disease_cui": UE.disease_cui, "finding_cui": UE.finding_cui, "disease_snomed": UE.ddxplus_disease.map(dm.snomed_id), "finding_snomed": "", "disease_hpo": UE.ddxplus_disease.map(dm.hpo_disease_id), "finding_hpo": "", "source": "UMLS:" + UE.SAB, "source_relation": UE.REL + "/" + UE.RELA, "source_weight": "", "frequency_raw": "", "reference": UE.RUI, "mapping_status": UE.quality_class, "review_needed": UE.review_needed.astype(str), "review_flags": np.where(UE.quality_class == "DIRECT_FINDING", "", "umls_" + UE.quality_class.str.lower()) })
long["provenance_family"] = long.source.map(lambda s: FAM.get(s, s)); ul["provenance_family"] = ul.source.map(lambda s: umls_family(s[5:]))
LF = pd.concat([long, ul], ignore_index=True); LF.to_csv(f"{O}/12_all_external_edges_long_final.csv", index=False)
RQ = LF[LF.review_needed.astype(str).isin(["True", "true"])]; RQ.to_csv(f"{O}/11_review_queue_final.csv", index=False)
MAT = DET[DET.raw_source_support_count > 0]; MAT.to_csv(f"{O}/13_disease_finding_source_matrix_final.csv", index=False)
umls_new = DET[DET.umls_any & (DET.sources_lenient.str.replace(r"UMLS:[A-Z0-9_]+;?", "", regex=True).str.strip(";") == "")]
umls_new_strict = DET[DET.umls_direct & (DET.sources_strict.str.replace(r"UMLS:[A-Z0-9_]+;?", "", regex=True).str.strip(";") == "")]
summ = {"umls": {"archive": "/mnt/c/Users/<user>/Desktop/umls-2026AA-metathesaurus-full.zip", "archive_sha256": "041cae91b8ce298435c36f076d562c31b1b97a659c4ecd22d698263bec294685", "archive_size": 5816418280, "mrrel_lines": 66241184, "relations_around_49_diseases": len(rel), "relations_around_with_evidence_cui": int(rel.involves_evidence_cui.sum()), "disease_finding_edges": len(UE), "suppressed_excluded": n_supp, "quality": UE.quality_class.value_counts().to_dict(), "by_sab": UE.SAB.value_counts().to_dict(), "direct_by_sab": UE[UE.quality_class == "DIRECT_FINDING"].SAB.value_counts().to_dict()},
        "umls_matched_pairs_any": int(DET.umls_any.sum()), "umls_matched_pairs_direct": int(DET.umls_direct.sum()), "umls_only_new_pairs_lenient": len(umls_new), "umls_only_new_pairs_strict": len(umls_new_strict), "umls_new_pairs_list": umls_new[["ddxplus_disease", "finding", "sources_lenient"]].values.tolist()[:30],
        "incremental": INC.to_dict("records"), "zero_before_diseases": zero_before, "zero_after": int((CV["cov|F:+UMLS_MRREL"].fillna(0) == 0).sum()), "zero_after_strict": int((CV["cov_strict|F:+UMLS_MRREL"].fillna(0) == 0).sum()), "newly_alive": list(REC[REC.newly_alive].ddxplus_disease), "newly_alive_strict": list(REC[REC.newly_alive_strict].ddxplus_disease),
        "pairs_raw_support_ge2": int((MAT.raw_source_support_count >= 2).sum()), "pairs_independent_family_ge2": int((MAT.independent_provenance_support_count >= 2).sum()), "pairs_independent_family_ge2_strict": int((MAT.independent_provenance_support_count_strict >= 2).sum()), "review_queue_final": len(RQ), "long_final": len(LF)}
json.dump(summ, open(f"{O}/STEP11_FINAL_SUMMARY.json", "w"), indent=1, default=str); print(json.dumps({k: v for k, v in summ.items() if k != "incremental"}, indent=1, default=str)); print(REC[["ddxplus_disease", "n_mrrel_relations_around", "n_finding_edges_any_quality", "n_direct_finding_edges", "matched_eligible_findings_umls", "coverage_after", "newly_alive", "umls_matched_findings"]].to_string()); log("DONE")
