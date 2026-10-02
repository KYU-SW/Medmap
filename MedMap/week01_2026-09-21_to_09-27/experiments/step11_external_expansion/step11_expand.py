"""STEP 11: 외부 질환-소견 지식원 확장(UMLS MRREL / DisMech / MEDLINE / Wikidata) → coverage 증분만 계산. 성능 실험 없음.
모든 source의 점수는 의미가 달라 합산하지 않으며 source별 행을 유지한다."""
import json, re, glob, os, sys, collections, hashlib, zipfile, time
import numpy as np, pandas as pd, yaml
O = "exp/step11_external_expansion"; S8 = "exp/step8_mapping"; S9 = "exp/step9_external_knowledge"; S10 = "exp/step10_hsdn"
t0 = time.time(); log = lambda *a: print(f"[{time.time()-t0:6.0f}s]", *a, flush=True)
cond = json.load(open("data/ddxplus/en/release_conditions.json")); assert len(cond) == 49
dm9 = pd.read_csv(f"{S9}/01_disease_concept_map.csv", dtype=str).fillna("").set_index("ddxplus_disease")
qt = pd.read_csv(f"{S9}/disease_query_table.tsv", sep="\t", dtype=str).fillna("").set_index("ddxplus_disease")
em = pd.read_csv(f"{S8}/evidence_concept_map.csv", dtype=str).fillna("").set_index("evidence_id")
el = pd.read_csv(f"{S9}/03_evidence_eligibility.csv", dtype=str).fillna("")
elig = el[el.finding_eligible == "True"].set_index("evidence_id"); log("eligible findings", len(elig))
hs_dm = pd.read_csv(f"{S10}/01_hsdn_disease_map.csv", dtype=str).fillna("").set_index("ddxplus_disease")
det10 = pd.read_csv(f"{S10}/04b_coverage_detail.csv"); det9 = pd.read_csv(f"{S9}/04b_coverage_detail.csv")
# ---- UMLS 보조 사전
m = pd.read_parquet("data/umls/mrconso_eng.parquet")
msh_mh = m[(m.SAB == "MSH") & (m.TTY == "MH")].drop_duplicates(["CUI", "CODE"]); cui2mesh = msh_mh.groupby("CUI")["CODE"].agg(list).to_dict(); mesh2cui = msh_mh.drop_duplicates("CODE").set_index("CODE")["CUI"].to_dict(); mesh_name = msh_mh.drop_duplicates("CODE").set_index("CODE")["STR"].to_dict()
hpo2cui = m[m.SAB == "HPO"].drop_duplicates("CODE").set_index("CODE")["CUI"].to_dict(); cui2hpo = m[m.SAB == "HPO"].groupby("CUI")["CODE"].agg(lambda s: sorted(set(s))[0]).to_dict()
cui2sn = m[(m.SAB == "SNOMEDCT_US") & (m.SUPPRESS == "N")].groupby("CUI")["CODE"].agg(lambda s: ";".join(sorted(set(s))[:3])).to_dict()
pref = m[m.ISPREF == "Y"].drop_duplicates("CUI").set_index("CUI")["STR"].to_dict()
SUBTYPE_KW = ["familial", "hereditary", "congenital", "susceptibility", "juvenile", "neonatal", "syndrome", "type "]
# evidence concept keys
def ev_keys(e):
    r = em.loc[e]; ks = {"cui": set(), "hpo": set(), "mesh": set()}
    for k in (1, 2):
        c, h = r[f"concept_{k}_cui"], r[f"concept_{k}_hpo"].split(";")[0]
        if c: ks["cui"].add(c); ks["mesh"].update(cui2mesh.get(c, []))
        if h: ks["hpo"].add(h)
        if h and not c and hpo2cui.get(h): ks["cui"].add(hpo2cui[h])
    return ks
EK = {e: ev_keys(e) for e in elig.index}
dis_rel = {d: [e for e in list(v["symptoms"]) + list(v["antecedents"]) if e in elig.index] for d, v in cond.items()}
prov = {}
# =================== 1. UMLS MRREL ===================
umls_zip = [p for pat in ["/mnt/c/Users/*/Desktop/*.zip", "/mnt/c/Users/*/Downloads/*.zip", "/mnt/c/Users/*/Desktop/*/*.zip"] for p in glob.glob(pat) if re.search(r"umls.*2026AA.*(full|meta|metathesaurus)", os.path.basename(p), re.I) and os.path.getsize(p) > 1e9]
umls_edges = pd.DataFrame(); rela_freq = {}
if umls_zip:
    zp = umls_zip[0]; log("UMLS zip", zp, round(os.path.getsize(zp) / 1e9, 2), "GB")
    prov["umls"] = {"file": zp, "size_bytes": os.path.getsize(zp), "sha256": "computed_below"}
    # TODO: 선택 추출 (MRREL/MRSTY/MRSAB) — 실제 zip 구조 확인 후 진행
else:
    prov["umls"] = {"status": "BLOCKED", "reason": "UMLS 2026AA full/metathesaurus zip not found in Desktop/Downloads (only umls-2026AA-mrconso.zip present; a .crdownload in progress was observed)"}; log("UMLS: BLOCKED")
# =================== 3. DisMech ===================
DR = "data/dismech/raw/dismech"; commit = open(f"{DR}/.git/HEAD").read().strip()
if commit.startswith("ref:"): commit = open(f"{DR}/.git/" + commit.split()[1]).read().strip()
prov["dismech"] = {"repo": "https://github.com/monarch-initiative/dismech.git", "commit": commit, "license": open(f"{DR}/LICENSE").read().splitlines()[0][:80], "n_disorder_yaml": len(glob.glob(f"{DR}/kb/disorders/*.yaml"))}
# MONDO → file index (grep 방식)
mondo_file, name_file = {}, {}
for f in glob.glob(f"{DR}/kb/disorders/*.yaml"):
    txt = open(f, encoding="utf-8", errors="ignore").read(20000)
    mm = re.search(r"disease_term:\s*\n\s*preferred_term:\s*(.+)\n\s*term:\s*\n\s*id:\s*(MONDO:\d+)", txt)
    nm = re.match(r"name:\s*(.+)", txt)
    if mm: mondo_file[mm.group(2)] = f
    if nm: name_file[nm.group(1).strip().lower()] = f
    if mm: name_file.setdefault(mm.group(1).strip().lower(), f)
log("dismech index", len(mondo_file), len(name_file))
FREQ_MAP = {"OBLIGATE": (100, 100), "VERY_FREQUENT": (80, 99), "FREQUENT": (30, 79), "OCCASIONAL": (5, 29), "VERY_RARE": (1, 4), "EXCLUDED": (0, 0)}
drows, dedges = [], []
for d in cond:
    r9 = dm9.loc[d]; mondos = [x for x in r9.mondo_id.split(";") if x] ; q = qt.loc[d]; names = [q.primary_query] + [a for a in q.alt_queries.split(";") if a] + [r9.umls_name]
    f, how = None, ""
    for mo in mondos:
        if mo.replace("_", ":") in mondo_file: f, how = mondo_file[mo.replace("_", ":")], f"MONDO({mo})"; break
    if not f:
        for nmq in names:
            if nmq.lower() in name_file: f, how = name_file[nmq.lower()], f"NAME({nmq})"; break
    cands = [os.path.basename(x) for k, x in name_file.items() if f is None and any(w in k for w in re.findall(r"[a-z]{4,}", q.primary_query.lower()) if w not in {"acute", "disease", "infection", "syndrome", "chronic"})][:6]
    if f:
        y = yaml.safe_load(open(f, encoding="utf-8")); dn = y.get("name", ""); term = ((y.get("disease_term") or {}).get("term") or {}); mid = term.get("id", "")
        kw = [k for k in SUBTYPE_KW if (k in dn.lower()) != (k in q.primary_query.lower())]
        status = "EXACT" if (how.startswith("MONDO") and not kw) else ("PARTIAL" if not kw else "AMBIGUOUS")
        if r9.mapping_status != "EXACT": status = "AMBIGUOUS" if r9.mapping_status == "AMBIGUOUS" else ("PARTIAL" if status == "EXACT" else status)
        if dn.lower() != q.primary_query.lower(): status = "PARTIAL" if status == "EXACT" else status
        phs = y.get("phenotypes") or []
        for p in phs:
            t = ((p.get("phenotype_term") or {}).get("term") or {}); hp = t.get("id", "") if str(t.get("id", "")).startswith("HP:") else ""; fr = p.get("frequency") or ""
            evs = p.get("evidence") or []; pm = [e.get("reference", "") for e in evs if str(e.get("reference", "")).startswith("PMID")]
            dedges.append({"ddxplus_disease": d, "dismech_disease": dn, "dismech_mondo": mid, "finding_name": p.get("name", ""), "finding_hpo": hp, "finding_cui": hpo2cui.get(hp, ""), "finding_snomed": cui2sn.get(hpo2cui.get(hp, ""), ""),
                           "frequency_raw": fr, "frequency_min": FREQ_MAP.get(fr, (None, None))[0], "frequency_max": FREQ_MAP.get(fr, (None, None))[1], "temporality": p.get("temporality", "") or p.get("onset", ""), "category": p.get("category", ""),
                           "n_evidence": len(evs), "pmid_refs": ";".join(pm[:5]), "has_pubmed_evidence": bool(pm), "evidence_support": ";".join(sorted({str(e.get("supports", "")) for e in evs})), "source": "DISMECH", "source_relation": "has_phenotype(AI-curated)"})
        drows.append({"ddxplus_disease": d, "ddxplus_code": r9.ddxplus_code, "umls_cui": r9.umls_cui, "step9_mondo": ";".join(mondos), "dismech_file": os.path.basename(f), "dismech_disease": dn, "dismech_mondo": mid, "n_phenotypes": len(phs), "n_phenotypes_with_pmid": sum(1 for p in phs if any(str(e.get("reference", "")).startswith("PMID") for e in (p.get("evidence") or []))),
                      "mapping_status": status, "mapping_method": how, "mapping_reason": (f"qualifier mismatch {kw}; " if kw else "") + (f"name differs: '{dn}' vs '{q.primary_query}'; " if dn.lower() != q.primary_query.lower() else "") + f"step9={r9.mapping_status}", "review_needed": status != "EXACT", "alternative_candidates": ""})
    else:
        drows.append({"ddxplus_disease": d, "ddxplus_code": r9.ddxplus_code, "umls_cui": r9.umls_cui, "step9_mondo": ";".join(mondos), "dismech_file": "", "dismech_disease": "", "dismech_mondo": "", "n_phenotypes": 0, "n_phenotypes_with_pmid": 0, "mapping_status": "FAIL", "mapping_method": "", "mapping_reason": "no MONDO/name match in kb/disorders", "review_needed": True, "alternative_candidates": "; ".join(cands)})
DDM = pd.DataFrame(drows); DDM.to_csv(f"{O}/02_dismech_disease_map.csv", index=False); DE = pd.DataFrame(dedges); DE.to_csv(f"{O}/03_dismech_disease_finding_edges.csv", index=False)
log("dismech", DDM.mapping_status.value_counts().to_dict(), "edges", len(DE), "with pmid", int(DE.has_pubmed_evidence.sum()) if len(DE) else 0)
# =================== 4. MEDLINE ===================
MR = "data/medline_disease_symptom/raw"; med = pd.read_csv(f"{MR}/disease-symptom-cooccurrence.tsv", sep="\t", dtype={"mesh_id": str}); slim = pd.read_csv(f"{MR}/DO-slim-to-mesh.tsv", sep="\t", dtype=str)
prov["medline"] = {"repo": "https://github.com/hetio/medline", "commit": open(f"{MR}/PROVENANCE.txt").read().split("=")[1].split("\n")[0], "sha256_disease_symptom": hashlib.sha256(open(f"{MR}/disease-symptom-cooccurrence.tsv", "rb").read()).hexdigest(), "rows": len(med), "diseases": med.doid_code.nunique(), "symptoms": med.mesh_id.nunique(), "license": "not stated in repo (no LICENSE file) → RESEARCH_USE_CHECK_REQUIRED"}
med_dis_mesh = slim.set_index("mesh_id")["doid_code"].to_dict(); med_sym = set(med.mesh_id)
mrows = []
for d in cond:
    r9 = dm9.loc[d]; meshes = cui2mesh.get(r9.umls_cui, []); hit = [(mm, med_dis_mesh[mm]) for mm in meshes if mm in med_dis_mesh]
    # 이름 경로: HSDN mesh_id(상위개념 포함) 재사용 — PARTIAL 표시
    hm = hs_dm.loc[d, "mesh_id"]; hit2 = [(hm, med_dis_mesh[hm])] if (not hit and hm and hm in med_dis_mesh) else []
    if hit: status, how, (mm, do) = ("EXACT" if r9.mapping_status == "EXACT" else r9.mapping_status), "CUI→MeSH", hit[0]
    elif hit2: status, how, (mm, do) = "PARTIAL", "HSDN-mesh(step10, name-level)", hit2[0]
    else: status, how, mm, do = "FAIL", "", "", ""
    mrows.append({"ddxplus_disease": d, "umls_cui": r9.umls_cui, "mesh_id": mm, "mesh_name": mesh_name.get(mm, ""), "doid_code": do, "doid_name": slim.set_index("doid_code")["doid_name"].get(do, "") if do else "", "mapping_status": status, "mapping_method": how, "mapping_reason": "MEDLINE covers only 135 DO-slim diseases" if status == "FAIL" else f"step9={r9.mapping_status}", "review_needed": status != "EXACT"})
MDM = pd.DataFrame(mrows); MDM.to_csv(f"{O}/04_medline_disease_map.csv", index=False)
frows = []
for e in elig.index:
    ks = EK[e]; hit = [x for x in ks["mesh"] if x in med_sym]
    frows.append({"evidence_id": e, "concept_1": em.loc[e, "concept_1"], "concept_2": em.loc[e, "concept_2"], "concept_cuis": ";".join(sorted(ks["cui"])), "mesh_ids": ";".join(sorted(ks["mesh"])), "medline_symptom_mesh": ";".join(hit), "medline_symptom_name": ";".join(mesh_name.get(x, "") for x in hit), "mapping_status": "EXACT" if hit else "FAIL", "mapping_method": "CUI→MeSH MH" if hit else "", "review_needed": not hit or len(hit) > 1})
MFM = pd.DataFrame(frows); MFM.to_csv(f"{O}/05_medline_finding_map.csv", index=False)
medges = []
for r in MDM[MDM.mapping_status != "FAIL"].itertuples():
    sub = med[med.doid_code == r.doid_code]
    for x in sub.itertuples():
        c = mesh2cui.get(x.mesh_id, "")
        medges.append({"ddxplus_disease": r.ddxplus_disease, "doid_code": x.doid_code, "doid_name": x.doid_name, "finding_name": x.mesh_name, "finding_mesh": x.mesh_id, "finding_cui": c, "finding_hpo": cui2hpo.get(c, ""), "finding_snomed": cui2sn.get(c, ""),
                       "cooccurrence": x.cooccurrence, "expected": x.expected, "enrichment": x.enrichment, "odds_ratio": x.odds_ratio, "p_fisher": x.p_fisher, "source": "MEDLINE", "source_relation": "medline_mesh_cooccurrence(hetio)"})
ME = pd.DataFrame(medges); ME.to_csv(f"{O}/06_medline_disease_finding_edges.csv", index=False)
log("medline", MDM.mapping_status.value_counts().to_dict(), "finding map", MFM.mapping_status.value_counts().to_dict(), "edges", len(ME))
# =================== 5. Wikidata ===================
wi = pd.read_csv("data/wikidata/disease_items_raw.csv", dtype=str).fillna(""); wp = pd.read_csv("data/wikidata/p780_raw.csv", dtype=str).fillna("")
cui2d = {d: r.umls_cui for d, r in dm9.iterrows()}; mesh2d = {}; sn2d = {}
for d, r in dm9.iterrows():
    for mm in cui2mesh.get(r.umls_cui, []): mesh2d.setdefault(mm, d)
    for s in r.snomed_id.split(";"):
        if s: sn2d.setdefault(s, d)
q2d = collections.defaultdict(set)
for r in wi.itertuples():
    for d, c in cui2d.items():
        if r.cui and r.cui == c: q2d[r.d].add((d, "CUI"))
    if r.mesh and r.mesh in mesh2d: q2d[r.d].add((mesh2d[r.mesh], "MeSH"))
    if r.sct and r.sct in sn2d: q2d[r.d].add((sn2d[r.sct], "SNOMED"))
wedges = []
for r in wp.itertuples():
    for d, how in q2d.get(r.d, []):
        wedges.append({"ddxplus_disease": d, "disease_qid": r.d, "disease_label": r.dLabel, "disease_match": how, "symptom_qid": r.s, "finding_name": r.sLabel, "finding_cui": r.sCui, "finding_mesh": r.sMesh, "finding_hpo": r.sHpo, "finding_snomed": cui2sn.get(r.sCui, ""),
                       "has_reference": bool(r.ref), "reference_url": r.refUrl, "stated_in": r.statedInLabel, "reference_id": r.ref, "source": "WIKIDATA", "source_relation": "P780 symptoms_and_signs"})
WE = pd.DataFrame(wedges).drop_duplicates(["ddxplus_disease", "symptom_qid", "reference_id"]) if wedges else pd.DataFrame(); WE.to_csv(f"{O}/07_wikidata_disease_finding_edges.csv", index=False)
prov["wikidata"] = {"endpoint": "https://query.wikidata.org/sparql", "queried": "2026-09-21", "disease_items": int(wi.d.nunique()), "diseases_matched": int(WE.ddxplus_disease.nunique()) if len(WE) else 0, "edges": len(WE), "edges_with_reference": int(WE.has_reference.sum()) if len(WE) else 0}
log("wikidata", prov["wikidata"])
# =================== 7. Coverage ===================
GENERIC_STEP10 = {"Pain", "Body weight"}; generic9 = set(el[el.too_generic_flag == "True"].evidence_id)
def src_sets(E, keycols):
    out = collections.defaultdict(lambda: {"cui": set(), "hpo": set(), "mesh": set()})
    for r in E.itertuples():
        s = out[r.ddxplus_disease]
        for k, col in keycols.items():
            v = getattr(r, col, ""); 
            if v and str(v) != "nan": s[k].add(str(v))
    return out
SS = {"DISMECH": src_sets(DE, {"hpo": "finding_hpo", "cui": "finding_cui"}) if len(DE) else {}, "MEDLINE": src_sets(ME, {"mesh": "finding_mesh", "cui": "finding_cui", "hpo": "finding_hpo"}) if len(ME) else {}, "WIKIDATA": src_sets(WE, {"cui": "finding_cui", "mesh": "finding_mesh", "hpo": "finding_hpo"}) if len(WE) else {}, "UMLS_MRREL": src_sets(umls_edges, {"cui": "finding_cui"}) if len(umls_edges) else {}}
def match(e, d, src):
    s = SS[src].get(d); k = EK[e]
    return bool(s) and (bool(k["cui"] & s["cui"]) or bool(k["hpo"] & s["hpo"]) or bool(k["mesh"] & s["mesh"]))
d10 = det10.set_index(["ddxplus_disease", "evidence_id"]); d9 = det9.set_index(["ddxplus_disease", "evidence_id"])
ORDER = ["HPO_OKG(step9)", "+HSDN(step10)", "+UMLS_MRREL", "+DISMECH", "+MEDLINE", "+WIKIDATA"]
rows, det = [], []
for d, evs in dis_rel.items():
    acc = {k: 0 for k in ORDER}; acc_ng = {k: 0 for k in ORDER}; acc_st = {k: 0 for k in ORDER}; per = {"UMLS_MRREL": 0, "DISMECH": 0, "MEDLINE": 0, "WIKIDATA": 0}
    for e in evs:
        m9 = bool(d9.loc[(d, e), "strict_nonself"]) if (d, e) in d9.index else False; m10 = bool(d10.loc[(d, e), "hsdn_match"]) if (d, e) in d10.index else False
        ms = {s: match(e, d, s) for s in per}; per = {s: per[s] + ms[s] for s in per}
        cum = [m9, m9 or m10]; cum.append(cum[-1] or ms["UMLS_MRREL"]); cum.append(cum[-1] or ms["DISMECH"]); cum.append(cum[-1] or ms["MEDLINE"]); cum.append(cum[-1] or ms["WIKIDATA"])
        ng = em.loc[e, "concept_1"] not in GENERIC_STEP10; st = e not in generic9
        for k, c in zip(ORDER, cum): acc[k] += c; acc_ng[k] += c and ng; acc_st[k] += c and st
        det.append({"ddxplus_disease": d, "evidence_id": e, "concept_1": em.loc[e, "concept_1"], "step9": m9, "hsdn": m10, **{s.lower(): ms[s] for s in per}, "any_after_step11": cum[-1], "generic_pain_bw": not ng, "generic_step9_depth": not st, "n_sources_supporting": int(m9) + int(m10) + sum(ms.values())})
    n = len(evs); row = {"ddxplus_disease": d, "n_eligible_findings": n, "n_nongeneric": sum(em.loc[e, "concept_1"] not in GENERIC_STEP10 for e in evs), "n_strict": sum(e not in generic9 for e in evs)}
    for k in ORDER: row[f"matched|{k}"] = acc[k]; row[f"cov|{k}"] = round(acc[k] / n, 3) if n else None; row[f"cov_nongeneric|{k}"] = round(acc_ng[k] / row["n_nongeneric"], 3) if row["n_nongeneric"] else None; row[f"cov_strict|{k}"] = round(acc_st[k] / row["n_strict"], 3) if row["n_strict"] else None
    for s in per: row[f"matched_alone|{s}"] = per[s]
    rows.append(row)
CV = pd.DataFrame(rows); CV.to_csv(f"{O}/08_coverage_by_source.csv", index=False); DET = pd.DataFrame(det); DET.to_csv(f"{O}/08b_coverage_detail.csv", index=False)
inc = []
prev = None
for k in ORDER:
    c = CV[f"cov|{k}"].fillna(0); cs = CV[f"cov_strict|{k}"].fillna(0); cn = CV[f"cov_nongeneric|{k}"].fillna(0); mt = CV[f"matched|{k}"]
    inc.append({"stage": k, "mean_cov": round(c.mean(), 3), "median_cov": round(c.median(), 3), "mean_cov_nongeneric": round(cn.mean(), 3), "mean_cov_strict": round(cs.mean(), 3), "median_cov_strict": round(cs.median(), 3), "zero_cov_diseases": int((c == 0).sum()), "zero_strict": int((cs == 0).sum()), "ge50": int((c >= .5).sum()), "ge50_strict": int((cs >= .5).sum()),
                "total_matched_findings": int(mt.sum()), "new_matched_vs_prev": int((mt - CV[f"matched|{prev}"]).sum()) if prev else "", "newly_alive_diseases": int(((mt > 0) & (CV[f"matched|{prev}"] == 0)).sum()) if prev else ""}); prev = k
INC = pd.DataFrame(inc); INC.to_csv(f"{O}/09_coverage_incremental.csv", index=False); print(INC.to_string())
# 각 지식원 단독 기여(순서 무관): step10 대비 새로 살린 것
alone = {}
base = CV["matched|+HSDN(step10)"]
for s in ["UMLS_MRREL", "DISMECH", "MEDLINE", "WIKIDATA"]:
    newf = sum(1 for r in DET.itertuples() if getattr(r, s.lower()) and not (r.step9 or r.hsdn)); newd = int(((DET.groupby("ddxplus_disease")[s.lower()].sum() > 0) & (base.set_axis(CV.ddxplus_disease) == 0)).sum())
    alone[s] = {"new_findings_vs_step10": int(newf), "newly_alive_diseases_vs_step10": newd, "diseases_with_edges": int((DET.groupby("ddxplus_disease")[s.lower()].sum() > 0).sum())}
# =================== 8. previous failures ===================
FAILED10 = ["URTI", "Acute otitis media", "Acute laryngitis", "Acute rhinosinusitis", "Chronic rhinosinusitis", "Acute COPD exacerbation / infection", "PSVT", "Boerhaave", "Scombroid food poisoning", "Localized edema", "HIV (initial infection)", "Whooping cough", "Larygospasm", "Cluster headache"]
pf = []
for d in FAILED10:
    r = CV[CV.ddxplus_disease == d].iloc[0]; dd = DET[DET.ddxplus_disease == d]
    pf.append({"ddxplus_disease": d, "n_eligible": r.n_eligible_findings, "HPO_OKG": int(dd.step9.sum()), "HSDN": int(dd.hsdn.sum()), "UMLS_MRREL": int(dd.umls_mrrel.sum()), "DISMECH": int(dd.dismech.sum()), "MEDLINE": int(dd.medline.sum()), "WIKIDATA": int(dd.wikidata.sum()), "cov_step10": r["cov|+HSDN(step10)"], "cov_step11": r["cov|+WIKIDATA"], "cov_step11_strict": r["cov_strict|+WIKIDATA"],
               "matched_findings": "; ".join(dd[dd.any_after_step11].concept_1), "dismech_map": DDM.set_index("ddxplus_disease").loc[d, "mapping_status"], "medline_map": MDM.set_index("ddxplus_disease").loc[d, "mapping_status"], "wikidata_items": int((WE.ddxplus_disease == d).sum()) if len(WE) else 0})
pd.DataFrame(pf).to_csv(f"{O}/10_previous_failure_recovery.csv", index=False)
# =================== 10. long union + matrix ===================
long = []
def add(E, src, fn, w, fr, ref, rel, ms_col=None):
    for r in E.itertuples():
        d = r.ddxplus_disease; long.append({"ddxplus_disease": d, "finding": getattr(r, fn), "disease_cui": dm9.loc[d, "umls_cui"], "finding_cui": getattr(r, "finding_cui", ""), "disease_snomed": dm9.loc[d, "snomed_id"], "finding_snomed": getattr(r, "finding_snomed", ""), "disease_hpo": dm9.loc[d, "hpo_disease_id"], "finding_hpo": getattr(r, "finding_hpo", ""),
                                             "source": src, "source_relation": rel, "source_weight": getattr(r, w) if w else "", "frequency_raw": getattr(r, fr) if fr else "", "reference": getattr(r, ref) if ref else "", "mapping_status": (ms_col.get(d, "") if ms_col is not None else ""), "review_needed": ""})
e9 = pd.read_csv(f"{S9}/02_external_disease_finding_edges.csv", dtype=str).fillna("")
add(e9[~e9.source.str.startswith("OptimusKG")], "HPO", "finding_name", None, "frequency_raw", "evidence_or_source_id", "phenotype.hpoa", dm9.mapping_status.to_dict()); add(e9[e9.source.str.startswith("OptimusKG")], "OPTIMUSKG", "finding_name", None, "frequency_raw", "evidence_or_source_id", "disease_phenotype(OPEN_TARGETS/HPO)", dm9.mapping_status.to_dict())
e10 = pd.read_csv(f"{S10}/03_hsdn_disease_finding_edges.csv", dtype=str).fillna("").rename(columns={"umls_cui": "finding_cui"}); e10["finding_snomed"] = e10.finding_cui.map(cui2sn).fillna(""); e10["finding_hpo"] = e10.finding_cui.map(cui2hpo).fillna("")
add(e10, "HSDN", "finding_name", "original_hsdn_weight", None, "pubmed_cooccurrence", "literature_cooccurrence_tfidf", hs_dm.mapping_status.to_dict())
if len(DE): add(DE, "DISMECH", "finding_name", None, "frequency_raw", "pmid_refs", "has_phenotype(AI-curated)", DDM.set_index("ddxplus_disease").mapping_status.to_dict())
if len(ME): add(ME, "MEDLINE", "finding_name", "enrichment", None, "cooccurrence", "medline_cooccurrence(hetio)", MDM.set_index("ddxplus_disease").mapping_status.to_dict())
if len(WE): add(WE, "WIKIDATA", "finding_name", None, None, "reference_url", "P780", {})
if len(umls_edges): add(umls_edges, "UMLS_MRREL", "finding_name", None, None, "SAB", "MRREL", {})
LONG = pd.DataFrame(long)
# review flags
GEN_NAMES = {"pain", "body weight", "signs and symptoms", "disease", "abnormality", "syndrome", "inflammation", "infection", "fever"}
dnames = {d: {qt.loc[d, "primary_query"].lower(), dm9.loc[d, "umls_name"].lower(), d.lower()} for d in cond}
def rflag(r):
    f = []; fn = str(r.finding).lower()
    if fn in GEN_NAMES or fn in {"pain", "body weight"}: f.append("generic")
    if fn in dnames[r.ddxplus_disease] or (r.finding_cui and r.finding_cui == r.disease_cui): f.append("self_reference")
    if r.source == "HSDN" and str(r.reference).isdigit() and int(r.reference) <= 1: f.append("single_literature")
    if r.source == "MEDLINE" and str(r.reference).replace(".", "").isdigit() and float(r.reference) <= 1: f.append("single_literature")
    if r.source == "WIKIDATA" and not r.reference: f.append("wikidata_no_reference")
    if r.source == "DISMECH" and not r.reference: f.append("dismech_evidence_check")
    if r.source == "OPTIMUSKG": f.append("hpo_redistribution_check_genetic")
    if any(k in fn for k in ["neoplasm", "carcinoma", "cancer", "syndrome", "disease", "failure", "infarction"]) and "self_reference" not in f: f.append("possible_comorbidity_or_complication")
    if r.mapping_status in ("PARTIAL", "AMBIGUOUS"): f.append("disease_map_" + r.mapping_status.lower())
    return ";".join(f)
LONG["review_flags"] = LONG.apply(rflag, axis=1); LONG["review_needed"] = LONG.review_flags != ""
LONG.to_csv(f"{O}/12_all_external_edges_long.csv", index=False)
RQ = LONG[LONG.review_needed][["ddxplus_disease", "finding", "source", "review_flags", "source_weight", "reference", "mapping_status"]]; RQ.to_csv(f"{O}/11_review_queue.csv", index=False)
# matrix: eligible evidence 기준 (DET) + 지식원별 지지
mat = DET[["ddxplus_disease", "evidence_id", "concept_1", "step9", "hsdn", "umls_mrrel", "dismech", "medline", "wikidata", "n_sources_supporting"]].rename(columns={"step9": "HPO_OKG", "hsdn": "HSDN", "umls_mrrel": "UMLS_MRREL", "dismech": "DISMECH", "medline": "MEDLINE", "wikidata": "WIKIDATA"})
mat = mat[mat.n_sources_supporting > 0]; mat.to_csv(f"{O}/13_disease_finding_source_matrix.csv", index=False)
multi = int((mat.n_sources_supporting >= 2).sum()); multi_indep = int(((mat[["HSDN", "DISMECH", "MEDLINE", "WIKIDATA", "HPO_OKG"]].astype(int).sum(axis=1)) >= 2).sum())
summ = {"provenance": prov, "eligible_findings": len(elig), "dismech_map": DDM.mapping_status.value_counts().to_dict(), "dismech_edges": len(DE), "dismech_edges_with_pmid": int(DE.has_pubmed_evidence.sum()) if len(DE) else 0,
        "medline_map": MDM.mapping_status.value_counts().to_dict(), "medline_finding_map": MFM.mapping_status.value_counts().to_dict(), "medline_edges": len(ME), "wikidata": prov["wikidata"],
        "incremental": INC.to_dict("records"), "per_source_contribution_vs_step10": alone, "relations_supported_by_ge2_sources": multi, "review_queue": int(len(RQ)), "review_flags": RQ.review_flags.str.split(";").explode().value_counts().to_dict(), "long_edges": len(LONG), "long_by_source": LONG.source.value_counts().to_dict()}
json.dump(summ, open(f"{O}/summary.json", "w"), indent=1, default=str); print(json.dumps({k: v for k, v in summ.items() if k not in ("incremental",)}, indent=1, default=str)); log("DONE")
