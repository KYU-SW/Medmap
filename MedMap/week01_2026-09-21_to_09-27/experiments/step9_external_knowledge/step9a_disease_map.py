"""STEP 9A: DDXPlus 49 질환 → UMLS CUI/SNOMED/ICD10/OMIM/ORPHA + HPO disease id + OptimusKG node. 억지 채움 없음(없으면 빈칸)."""
import json, re, collections
import pandas as pd, polars as pl
O = "exp/step9_external_knowledge"
cond = json.load(open("data/ddxplus/en/release_conditions.json"))
qt = pd.read_csv(f"{O}/disease_query_table.tsv", sep="\t", dtype=str).fillna("")
m = pd.read_parquet("data/umls/mrconso_eng.parquet")
TAG = re.compile(r"\s*\((finding|disorder|procedure|substance|situation|event|morphologic abnormality|qualifier value|navigational concept|& nos|nos)\)\s*$", re.I)
def normstr(s): s = TAG.sub("", s.lower().strip()).replace("’", "'").replace("'s", "s").replace("'", ""); s = re.sub(r"[^a-z0-9 ]+", " ", s); return re.sub(r"\s+", " ", s).strip()
sub = m[(m["SUPPRESS"] == "N") & m["SAB"].isin(["SNOMEDCT_US", "MSH", "ICD10CM", "ICD10", "OMIM", "ORPHANET", "HPO", "NCI", "MTH", "MDR"])].copy(); sub["n"] = sub["STR"].map(normstr)
by_str = sub.groupby("n")["CUI"].agg(set).to_dict()
def codes(cui, sab, active_only=True):
    r = m.loc[(m["CUI"] == cui) & (m["SAB"] == sab)]
    if active_only and (r["SUPPRESS"] == "N").any(): r = r[r["SUPPRESS"] == "N"]
    out = sorted(set(r["CODE"]))
    if sab == "OMIM": out = [c for c in out if c.isdigit()]  # MTHU* = UMLS 내부 보조코드 제외
    if sab == "ORPHANET": out = [c for c in out if c.isdigit()]
    return out
def cui_name(cui):
    r = m[(m["CUI"] == cui)]; p = r[r["ISPREF"] == "Y"]; return (p if len(p) else r)["STR"].iloc[0]
icd_map = m[m["SAB"].isin(["ICD10CM", "ICD10"])].groupby("CODE")["CUI"].agg(set).to_dict()
# HPO annotation disease ids
hpoa = pd.read_csv("data/hpo/phenotype.hpoa", sep="\t", comment="#", dtype=str); hpoa_ids = set(hpoa["database_id"]); hpoa_names = hpoa.drop_duplicates("database_id").set_index("database_id")["disease_name"].str.lower().to_dict()
# OptimusKG disease nodes
nodes = pl.read_parquet("data/optimuskg/gold/nodes/disease.parquet").to_pandas()
def L(x): return [] if x is None else list(x)
nodes["name"] = nodes["properties"].map(lambda p: (p.get("name") or "").lower())
nodes["cuis"] = nodes["properties"].map(lambda p: set(map(str, L(p.get("umls_cui")))))
nodes["snomed"] = nodes["properties"].map(lambda p: set(str(x).split(".")[0] for x in L(p.get("snomed_concept_ids"))))
nodes["xrefs"] = nodes["properties"].map(lambda p: set(map(str, L(p.get("xrefs")))))
nodes["syn"] = nodes["properties"].map(lambda p: set(str(x).lower() for x in L(p.get("exact_synonyms"))))
print("optimuskg disease nodes", len(nodes), "with cui", (nodes["cuis"].map(len) > 0).sum())
OKG_BLOCK = {"MONDO_0008259": "familial spontaneous pneumothorax = hereditary subtype, not the DDXPlus common disease"}
rows = []
for name, v in cond.items():
    q = qt[qt["ddxplus_disease"] == name].iloc[0]
    queries = [q["primary_query"]] + [a for a in q["alt_queries"].split(";") if a]
    hits = [(qq, sorted(by_str.get(normstr(qq), set()))) for qq in queries]
    icd = v["icd10-id"].upper().split(",")[0].strip(); icd_cuis = sorted(icd_map.get(icd, set()) | icd_map.get(icd.replace(".", ""), set()))
    prim = hits[0][1]; cui = prim[0] if len(prim) == 1 else (sorted(set(prim) & set(icd_cuis))[0] if prim and set(prim) & set(icd_cuis) else (prim[0] if prim else ""))
    reasons = [q["hint_reason"]] if q["hint_reason"] else []; status = q["status_hint"]
    if not prim:
        for qq, hc in hits[1:]:
            if hc: cui = hc[0]; status = "PARTIAL" if status == "EXACT" else status; reasons.append(f"primary '{queries[0]}' not in UMLS; used alt '{qq}'"); break
    if not cui: status = "FAIL"; reasons.append("no UMLS string match for any query")
    if len(prim) > 1: reasons.append(f"primary string maps to {len(prim)} CUIs: {prim}"); status = "AMBIGUOUS" if status == "EXACT" else status
    icd_agree = bool(cui) and cui in icd_cuis
    if cui and icd_cuis and not icd_agree: reasons.append(f"ICD10 {icd} CUI(s) {icd_cuis[:3]} differ from name CUI (ICD often broader/unspecified)")
    sn = codes(cui, "SNOMEDCT_US") if cui else []; icd10 = codes(cui, "ICD10CM") + codes(cui, "ICD10") if cui else []; omim = codes(cui, "OMIM") if cui else []; orpha = codes(cui, "ORPHANET") if cui else []
    hpo_ids = [f"OMIM:{o}" for o in omim if f"OMIM:{o}" in hpoa_ids] + [f"ORPHA:{o}" for o in orpha if f"ORPHA:{o}" in hpoa_ids]
    # OptimusKG: CUI 일치 > SNOMED 일치 > 이름/동의어 정확 일치
    ok = nodes[nodes["cuis"].map(lambda s: cui in s) | nodes["xrefs"].map(lambda s: f"UMLS:{cui}" in s)] if cui else nodes.iloc[0:0]
    how = "cui"
    if not len(ok) and sn: ok = nodes[nodes["snomed"].map(lambda s: bool(s & set(sn))) | nodes["xrefs"].map(lambda s: bool(s & {f"SCTID:{c}" for c in sn}))]; how = "snomed"
    if not len(ok) and (icd10 or orpha): ok = nodes[nodes["xrefs"].map(lambda s: bool(s & ({f"ICD10CM:{c}" for c in icd10} | {f"Orphanet:{c}" for c in orpha})))]; how = "icd10/orphanet_xref"
    if not len(ok):
        qs = {qq.lower() for qq in queries}; ok = nodes[nodes["name"].isin(qs) | nodes["syn"].map(lambda s: bool(s & qs))]; how = "name"
    blocked = [i for i in ok["id"] if i in OKG_BLOCK]; ok = ok[~ok["id"].isin(OKG_BLOCK)]
    if blocked: reasons.append("OptimusKG node(s) REJECTED: " + "; ".join(f"{b} ({OKG_BLOCK[b]})" for b in blocked))
    ok_ids = sorted(ok["id"]); mondo = [i for i in ok_ids if i.startswith("MONDO")] + [x for x in set().union(*ok["xrefs"]) if str(x).startswith("MONDO")] if len(ok) else []
    if len(ok) > 1: reasons.append(f"OptimusKG {len(ok)} nodes match by {how}: {ok_ids[:5]}")
    if len(ok) and how == "name": reasons.append("OptimusKG matched by name/synonym only (no CUI/SNOMED/ICD xref) — verify identity")
    if len(ok) and how == "name" and not (ok["name"] == queries[0].lower()).any(): reasons.append("OptimusKG name matched an ALT query, not primary")
    alt = "; ".join(f"{qq}->{hc}" for qq, hc in hits if hc) + (f" | ICD:{icd}->{icd_cuis[:3]}" if icd_cuis else "")
    if omim and status == "EXACT": reasons.append(f"OMIM ids attached to CUI ({omim[:3]}) — check they are not a hereditary subtype")
    rows.append({"ddxplus_disease": name, "ddxplus_code": v["icd10-id"], "umls_cui": cui, "umls_name": cui_name(cui) if cui else "", "snomed_id": ";".join(sn[:5]), "icd10": ";".join(icd10[:5]),
                 "omim_id": ";".join(omim[:5]), "orpha_id": ";".join(orpha[:5]), "mondo_id": ";".join(sorted(set(mondo))[:5]), "hpo_disease_id": ";".join(hpo_ids[:5]), "optimuskg_disease_id": ";".join(ok_ids[:5]),
                 "optimuskg_match_how": how if len(ok) else "", "okg_link_status": ("REJECTED_" + ";".join(blocked)) if blocked and not len(ok) else ("NAME_ONLY_REVIEW" if (len(ok) and how == "name") else ("OK" if len(ok) else "NONE")), "omim_is_familial_or_susceptibility": ";".join(sorted({o for o in omim if any(k in " ".join(m.loc[(m["SAB"]=="OMIM")&(m["CODE"]==o),"STR"]).lower() for k in ["familial","susceptibility","hereditary"])})), "optimuskg_name": ";".join(ok["name"].head(3)) if len(ok) else "", "icd_agrees_with_name": icd_agree,
                 "mapping_status": status, "mapping_reason": " | ".join(r for r in reasons if r), "review_needed": status != "EXACT" or bool(omim) or len(ok) != 1, "alternative_candidates": alt})
df = pd.DataFrame(rows); df.to_csv(f"{O}/01_disease_concept_map.csv", index=False)
pd.set_option("display.width", 260); pd.set_option("display.max_colwidth", 38)
print(df[["ddxplus_disease", "umls_cui", "umls_name", "snomed_id", "omim_id", "orpha_id", "hpo_disease_id", "optimuskg_disease_id", "optimuskg_match_how", "mapping_status"]].to_string())
print(collections.Counter(df["mapping_status"]), "hpo_ok", (df["hpo_disease_id"] != "").sum(), "okg_ok", (df["optimuskg_disease_id"] != "").sum())
