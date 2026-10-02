"""STEP 9B: 외부 질환-소견 edge 추출(OptimusKG disease_phenotype + HPO phenotype.hpoa), 빈도는 있는 그대로 보존/없으면 null.
STEP 9C: Step8 evidence 적격성 분리 + 질환별 coverage. 임의 확률·점수 계산 없음."""
import json, re, collections
import numpy as np, pandas as pd, polars as pl
O = "exp/step9_external_knowledge"
dm = pd.read_csv(f"{O}/01_disease_concept_map.csv", dtype=str).fillna("")
cond = json.load(open("data/ddxplus/en/release_conditions.json"))
em = pd.read_csv("exp/step8_mapping/evidence_concept_map.csv", dtype=str).fillna("")
sem = pd.read_csv("exp/step8_mapping/evidence_semantics.tsv", sep="\t", dtype=str).fillna("").set_index("evidence_id")
# ---- HPO ontology
terms, cur, parents, names = {}, None, collections.defaultdict(set), {}
for line in open("data/hpo/hp.obo", encoding="utf-8"):
    line = line.rstrip("\n")
    if line == "[Term]": cur = None
    elif line.startswith("id: HP:"): cur = line[4:]
    elif cur and line.startswith("name: "): names[cur] = line[6:]
    elif cur and line.startswith("is_a: "): parents[cur].add(line[6:].split(" ")[0])
    elif cur and line.startswith("is_obsolete"): cur = None
def ancestors(h, acc=None):
    acc = set() if acc is None else acc
    for p in parents.get(h, ()):
        if p not in acc: acc.add(p); ancestors(p, acc)
    return acc
depth = {h: 0 for h in names}
def dep(h):
    if not parents.get(h): return 0
    return 1 + min(dep(p) for p in parents[h])
import functools; dep = functools.lru_cache(None)(dep)
FREQ = {"HP:0040280": ("Obligate", 100, 100), "HP:0040281": ("Very frequent", 80, 99), "HP:0040282": ("Frequent", 30, 79), "HP:0040283": ("Occasional", 5, 29), "HP:0040284": ("Very rare", 1, 4), "HP:0040285": ("Excluded", 0, 0)}
def parse_freq(f):
    if not f: return ("", None, None)
    if f in FREQ: n, a, b = FREQ[f]; return (f"{f} ({n})", a, b)
    mm = re.fullmatch(r"(\d+)/(\d+)", f)
    if mm and int(mm.group(2)) > 0: p = 100 * int(mm.group(1)) / int(mm.group(2)); return (f, round(p, 1), round(p, 1))
    mm = re.fullmatch(r"(\d+(?:\.\d+)?)%", f)
    if mm: return (f, float(mm.group(1)), float(mm.group(1)))
    return (f, None, None)
# ---- HPO id → CUI/SNOMED (MRCONSO)
m = pd.read_parquet("data/umls/mrconso_eng.parquet", columns=["CUI", "SAB", "CODE", "SUPPRESS"])
hpo2cui = m[m["SAB"] == "HPO"].drop_duplicates("CODE").set_index("CODE")["CUI"].to_dict()
cui2sn = m[(m["SAB"] == "SNOMEDCT_US") & (m["SUPPRESS"] == "N")].groupby("CUI")["CODE"].agg(lambda s: ";".join(sorted(set(s))[:3])).to_dict(); del m
def LA(x): return [] if x is None else [str(i) for i in list(x)]
# ---- 9B edges
edges = []
okg = pl.read_parquet("data/optimuskg/gold/edges/disease_phenotype.parquet").to_pandas()
okg_ids = {i for s in dm["optimuskg_disease_id"] for i in s.split(";") if i}
okg = okg[okg["from"].isin(okg_ids)]
for _, r in okg.iterrows():
    p = r["properties"]; hp = r["to"].replace("_", ":"); fr = LA(p.get("frequency")); raw, a, b = parse_freq(fr[0] if fr else "")
    for dis in dm[dm["optimuskg_disease_id"].str.contains(r["from"], regex=False)]["ddxplus_disease"]:
        edges.append({"ddxplus_disease": dis, "external_disease_id": r["from"], "finding_name": names.get(hp, ""), "finding_cui": hpo2cui.get(hp, ""), "finding_snomed": cui2sn.get(hpo2cui.get(hp, ""), ""), "finding_hpo": hp,
                      "source": "OptimusKG(" + "/".join(LA(p["sources"]["direct"]) + LA(p["sources"]["indirect"])) + ")", "relation_present": 1, "frequency_raw": raw, "frequency_min": a, "frequency_max": b,
                      "negative_annotation": bool(p.get("qualifier_not")), "evidence_or_source_id": ";".join(LA(p.get("references"))[:3]), "hpo_aspect": ";".join(LA(p.get("aspect")))})
hpoa = pd.read_csv("data/hpo/phenotype.hpoa", sep="\t", comment="#", dtype=str).fillna("")
hpo_ids = {i for s in dm["hpo_disease_id"] for i in s.split(";") if i}
for _, r in hpoa[hpoa["database_id"].isin(hpo_ids)].iterrows():
    raw, a, b = parse_freq(r["frequency"]); hp = r["hpo_id"]
    for dis in dm[dm["hpo_disease_id"].str.contains(r["database_id"], regex=False)]["ddxplus_disease"]:
        edges.append({"ddxplus_disease": dis, "external_disease_id": r["database_id"], "finding_name": names.get(hp, ""), "finding_cui": hpo2cui.get(hp, ""), "finding_snomed": cui2sn.get(hpo2cui.get(hp, ""), ""), "finding_hpo": hp,
                      "source": "HPO_phenotype.hpoa", "relation_present": 1, "frequency_raw": raw, "frequency_min": a, "frequency_max": b,
                      "negative_annotation": r["qualifier"].strip().upper() == "NOT", "evidence_or_source_id": r["reference"], "hpo_aspect": r["aspect"]})
E = pd.DataFrame(edges)
# reference_type: OMIM familial/susceptibility 항목 유래인지 (hpoa disease_name 또는 MRCONSO OMIM 제목으로 판정)
hpoa_all = pd.read_csv("data/hpo/phenotype.hpoa", sep="\t", comment="#", dtype=str).fillna("")
omim_title = hpoa_all.drop_duplicates("database_id").set_index("database_id")["disease_name"].str.lower().to_dict()
def ref_type(refs):
    t = []
    for r in str(refs).split(";"):
        if r.startswith("OMIM:"):
            ti = omim_title.get(r, ""); t.append("OMIM_familial_or_susceptibility" if any(k in ti for k in ["familial", "susceptibility", "hereditary"]) else "OMIM")
        elif r.startswith("ORPHA"): t.append("Orphanet")
        elif r.startswith("PMID"): t.append("PMID")
        elif r: t.append(r.split(":")[0])
    return ";".join(sorted(set(t)))
E["reference_type"] = E["evidence_or_source_id"].map(ref_type)
E["reference_title"] = E["evidence_or_source_id"].map(lambda x: ";".join(omim_title.get(r, "") for r in str(x).split(";") if r.startswith("OMIM:"))[:80])
dis_cui = dm.set_index("ddxplus_disease")["umls_cui"].to_dict(); dis_name = dm.set_index("ddxplus_disease")["umls_name"].str.lower().to_dict()
qt = pd.read_csv(f"{O}/disease_query_table.tsv", sep="\t", dtype=str).fillna(""); dis_q = {r.ddxplus_disease: {r.primary_query.lower()} | {a.lower() for a in r.alt_queries.split(";") if a} | {r.ddxplus_disease.lower()} for r in qt.itertuples()}
E["self_phenotype"] = [(r.finding_cui != "" and r.finding_cui == dis_cui.get(r.ddxplus_disease, "x")) or r.finding_name.lower() in dis_q.get(r.ddxplus_disease, set()) or r.finding_name.lower() == dis_name.get(r.ddxplus_disease, "x") for r in E.itertuples()]
E["is_phenotypic_abnormality"] = E["hpo_aspect"].str.contains("P")
E.to_csv(f"{O}/02_external_disease_finding_edges.csv", index=False)
print("edges by reference_type", E["reference_type"].value_counts().to_dict()); print("self_phenotype", int(E["self_phenotype"].sum()), "aspect P", int(E["is_phenotypic_abnormality"].sum()))
print("edges", len(E), "diseases with edges", E["ddxplus_disease"].nunique(), "with freq", E["frequency_min"].notna().sum(), "NOT", int(E["negative_annotation"].sum()))
# ---- 9C eligibility
ELIG_TYPES = {"SYMPTOM", "SIGN"}; COND_TYPES = {"SYMPTOM_MODIFIER", "PAIN_ATTRIBUTE", "LESION_ATTRIBUTE"}
GENERIC_DEPTH = 3
rows = []
for _, r in em.iterrows():
    s = sem.loc[r["evidence_id"]]; t = r["evidence_type"]; hp1 = r["concept_1_hpo"].split(";")[0]; hp2 = r["concept_2_hpo"].split(";")[0]
    if t in ELIG_TYPES: elig, why = True, "symptom/sign"
    elif t in COND_TYPES and s["mapping_required"] != "VALUE_LEVEL" and hp1: elig, why = True, f"{t} with own HPO concept"
    elif t in COND_TYPES: elig, why = False, f"{t}: value-level or modifier without phenotype concept → future/context feature"
    else: elig, why = False, f"{t}: risk factor/history/context → not a disease-finding relation"
    if elig and not hp1 and not hp2: elig, why = False, why + " but no HPO id for concept → cannot compare with HPO-based knowledge (SNOMED-only)"
    generic = bool(hp1) and dep(hp1) <= GENERIC_DEPTH
    rows.append({"evidence_id": r["evidence_id"], "original_question": r["original_question"], "evidence_type": t, "concept_1": r["concept_1"], "concept_1_hpo": hp1, "concept_1_hpo_depth": dep(hp1) if hp1 else "", "concept_2": r["concept_2"], "concept_2_hpo": hp2,
                 "operator": r["operator"], "temporality": r["temporality"], "context": r["context"], "step8_status": r["mapping_status"], "finding_eligible": elig, "eligibility_reason": why,
                 "too_generic_flag": generic, "feature_bucket": "finding" if elig else ("context_modifier" if t in COND_TYPES else "risk_history_context"), "review_needed": (elig and (generic or r["mapping_status"] not in {"EXACT", "COMPOSITE"}))})
EL = pd.DataFrame(rows); EL.to_csv(f"{O}/03_evidence_eligibility.csv", index=False)
print("eligible", EL["finding_eligible"].sum(), "of", len(EL), "generic flagged", EL["too_generic_flag"].sum())
# ---- 9C coverage
ext = collections.defaultdict(lambda: {"hpo": set(), "okg": set(), "hpo_ns": set(), "okg_ns": set()})
for _, r in E.iterrows():
    if r["negative_annotation"] or not r["is_phenotypic_abnormality"]: continue
    k = "okg" if r["source"].startswith("OptimusKG") else "hpo"; ext[r["ddxplus_disease"]][k].add(r["finding_hpo"])
    if not r["self_phenotype"]: ext[r["ddxplus_disease"]][k + "_ns"].add(r["finding_hpo"])
elig_map = EL[EL["finding_eligible"]].set_index("evidence_id")
def match(ev_hps, extset):
    ex, hi, ex_strict = False, False, False
    for h in ev_hps:
        if not h: continue
        if h in extset: ex = True; ex_strict = ex_strict or dep(h) > GENERIC_DEPTH
        anc_h = ancestors(h)
        for x in extset:
            if h in ancestors(x) and dep(h) > GENERIC_DEPTH: hi = True  # 외부 finding이 evidence 개념의 하위(더 구체)
            elif x in anc_h and dep(x) > GENERIC_DEPTH: hi = True      # 외부 finding이 evidence 개념의 상위(덜 구체) — 별도 카운트
    return ex, ex or hi, ex_strict
cov, detail = [], []
for dis, v in cond.items():
    d = dm[dm["ddxplus_disease"] == dis].iloc[0]; rel = list(v["symptoms"].keys()) + list(v["antecedents"].keys())
    el = [e for e in rel if e in elig_map.index]; hs, ks = ext[dis]["hpo"], ext[dis]["okg"]; hs_ns, ks_ns = ext[dis]["hpo_ns"], ext[dis]["okg_ns"]
    n_h = n_k = n_u = n_ex = n_strict = n_ns = 0
    for e in el:
        hps = [elig_map.loc[e, "concept_1_hpo"], elig_map.loc[e, "concept_2_hpo"]]
        h_ex, h_hi, h_st = match(hps, hs); k_ex, k_hi, k_st = match(hps, ks); ns_ex, ns_hi, ns_st = match(hps, hs_ns | ks_ns)
        n_h += h_hi; n_k += k_hi; n_u += (h_hi or k_hi); n_ex += (h_ex or k_ex); n_strict += (h_st or k_st); n_ns += ns_st
        detail.append({"ddxplus_disease": dis, "evidence_id": e, "concept_1": elig_map.loc[e, "concept_1"], "hpo": hps[0], "hpo_depth": dep(hps[0]) if hps[0] else "", "hpo_match": h_hi, "okg_match": k_hi, "exact_match": h_ex or k_ex, "exact_strict_nongeneric": h_st or k_st, "strict_nonself": ns_st})
    cov.append({"ddxplus_disease": dis, "mapping_status": d["mapping_status"], "okg_link_status": d.get("okg_link_status", ""), "n_related_evidence": len(rel), "n_eligible_findings": len(el), "n_external_hpo_findings": len(hs), "n_external_okg_findings": len(ks), "n_external_nonself_findings": len(hs_ns | ks_ns),
                "hpo_matched": n_h, "okg_matched": n_k, "union_matched": n_u, "exact_id_matched": n_ex, "strict_matched": n_strict, "strict_nonself_matched": n_ns,
                "coverage": round(n_u / len(el), 3) if el else None, "coverage_exact_only": round(n_ex / len(el), 3) if el else None, "coverage_strict": round(n_strict / len(el), 3) if el else None, "coverage_strict_nonself": round(n_ns / len(el), 3) if el else None,
                "has_hpo_source": bool(hs), "has_okg_source": bool(ks), "has_nonself_source": bool(hs_ns | ks_ns)})
C = pd.DataFrame(cov); C.to_csv(f"{O}/04_disease_coverage.csv", index=False); pd.DataFrame(detail).to_csv(f"{O}/04b_coverage_detail.csv", index=False)
# ---- review queue
q = []
for _, r in dm[dm["review_needed"] == "True"].iterrows(): q.append({"item_type": "disease", "id": r["ddxplus_disease"], "status": r["mapping_status"], "reason": r["mapping_reason"], "candidates": r["alternative_candidates"], "chosen": f"{r['umls_cui']} {r['umls_name']} | OKG {r['optimuskg_disease_id']} ({r['optimuskg_match_how']})"})
for _, r in EL[EL["review_needed"]].iterrows(): q.append({"item_type": "evidence", "id": r["evidence_id"], "status": r["step8_status"], "reason": ("too generic HPO (depth<=3); " if r["too_generic_flag"] else "") + r["eligibility_reason"], "candidates": "", "chosen": f"{r['concept_1']} {r['concept_1_hpo']}"})
pd.DataFrame(q).to_csv(f"{O}/05_mapping_review_queue.csv", index=False)
pd.set_option("display.width", 220); print(C.to_string()); print(C[["coverage", "coverage_exact_only"]].describe().round(3))
summ = {"diseases": {"n": 49, "external_id_mapped": int((dm["umls_cui"] != "").sum()), "hpo_usable": int(C["has_hpo_source"].sum()), "okg_usable": int(C["has_okg_source"].sum()), "either": int((C["has_hpo_source"] | C["has_okg_source"]).sum()), "none": int((~(C["has_hpo_source"] | C["has_okg_source"])).sum()), "status": dm["mapping_status"].value_counts().to_dict(), "review_needed": int((dm["review_needed"] == "True").sum())},
        "evidence": {"n": len(EL), "finding_eligible": int(EL["finding_eligible"].sum()), "risk_context_history": int((~EL["finding_eligible"]).sum()), "eligible_with_hpo": int((EL["finding_eligible"] & (EL["concept_1_hpo"] != "")).sum()), "eligible_matched_any_disease": int(pd.DataFrame(detail).query("hpo_match or okg_match")["evidence_id"].nunique()) if detail else 0, "too_generic": int(EL["too_generic_flag"].sum()), "bucket": EL["feature_bucket"].value_counts().to_dict()},
        "coverage": {k: (None if pd.isna(v) else round(float(v), 3)) for k, v in C["coverage"].describe().items()}, "coverage_strict_nonself": {k: (None if pd.isna(v) else round(float(v), 3)) for k, v in C["coverage_strict_nonself"].describe().items()}, "diseases_with_nonself_knowledge": int(C["has_nonself_source"].sum()), "diseases_nonzero_strict_nonself": int((C["coverage_strict_nonself"].fillna(0) > 0).sum()), "too_generic_among_eligible": int((EL["finding_eligible"] & EL["too_generic_flag"]).sum()), "coverage_exact": {k: (None if pd.isna(v) else round(float(v), 3)) for k, v in C["coverage_exact_only"].describe().items()},
        "edges": {"n": len(E), "aspect_P": int(E["is_phenotypic_abnormality"].sum()), "with_frequency": int(E["frequency_min"].notna().sum()), "negative": int(E["negative_annotation"].sum()), "self_phenotype": int(E["self_phenotype"].sum()), "sources": E["source"].value_counts().to_dict(), "reference_type": E["reference_type"].value_counts().to_dict(), "okg_edges_by_disease_reftype": {f"{a}|{b}": int(c) for (a, b), c in E[E["source"].str.startswith("OptimusKG")].groupby("ddxplus_disease")["reference_type"].value_counts().items()}}, "review_queue": len(q)}
json.dump(summ, open(f"{O}/step9_summary.json", "w"), indent=1, default=str); print(json.dumps(summ, indent=1, default=str)); print("DONE")
