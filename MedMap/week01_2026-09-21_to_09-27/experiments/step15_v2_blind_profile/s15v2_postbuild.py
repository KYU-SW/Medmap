"""03 quality audit, 04 external pair differences, 05 review queue, 06 human review sheet. External facts only."""
import pathlib, pandas as pd, json
OUT = pathlib.Path("exp/step15_v2_blind_profile")
F = pd.read_csv(OUT/"01_disease_profile_facts.csv", dtype=str, keep_default_na=False)
C = pd.read_csv(OUT/"02_disease_profile_concepts.csv", dtype=str, keep_default_na=False)
R = pd.read_csv(OUT/"00_source_registry.csv", dtype=str, keep_default_na=False)
M = F.merge(C[["fact_id","umls_cui","umls_preferred_name","snomed_id","hpo_id","mapping_status","mapping_candidates","review_needed"]].rename(columns={"review_needed":"map_review"}), on="fact_id")
VALUE_COLS = ["location","severity","onset","duration","frequency","progression","trigger","aggravating_factor","relieving_factor","history_context","family_context","exposure_context","medication_context"]
M["value_level"] = (M[VALUE_COLS] != "").any(axis=1)

# ---------- 03 quality audit ----------
rows=[]
for d, g in M.groupby("disease", sort=False):
    srcs = sorted(g.source_id.unique()); reg = R[R.source_id.isin(srcs)]
    def org_key(o):
        o=o.lower()
        if o.startswith("cdc") or o.startswith("hiv.gov"): return "CDC"   # HIV.gov re-cites CDC
        if o.startswith("nhlbi") or o.startswith("nidcd"): return "NIH"
        return o.split(" (")[0]
    orgs = set(org_key(o) for o in reg.organization); indep = len(orgs)
    rows.append(dict(disease=d, n_sources=len(srcs), n_independent_orgs=indep, n_tier1_sources=int((reg.source_tier=="tier1").sum()),
        n_tier2_sources=int((reg.source_tier=="tier2").sum()), n_tier3_sources=int((reg.source_tier=="tier3").sum()),
        total_facts=len(g), symptom_sign_facts=int(g.fact_category.isin(["symptom","sign","associated_symptom","negative_finding"]).sum()),
        temporal_facts=int(((g.fact_category=="temporal")|(g.duration!="")|(g.onset!="")).sum()),
        location_facts=int((g.location!="").sum()), trigger_relief_facts=int(((g.trigger!="")|(g.relieving_factor!="")|(g.aggravating_factor!="")).sum()),
        risk_exposure_facts=int(g.fact_category.isin(["risk_factor","exposure","history","family_history","medication"]).sum()),
        diagnostic_criteria_facts=int((g.fact_category=="diagnostic_criteria").sum()), differentiating_facts=int(((g.fact_category=="differentiating_feature")|(g.diagnostic_role=="differentiating")).sum()),
        red_flag_facts=int((g.fact_category=="red_flag").sum()), lab_facts=int((g.fact_category=="lab_finding").sum()),
        value_level_facts=int(g.value_level.sum()), facts_without_source=int((g.source_id=="").sum()),
        concept_exact=int((g.mapping_status=="EXACT").sum()), concept_partial=int((g.mapping_status=="PARTIAL").sum()),
        concept_ambiguous=int((g.mapping_status=="AMBIGUOUS_MULTI_CUI").sum()), concept_fail=int((g.mapping_status=="FAIL").sum()),
        concept_attribute_not_mapped=int((g.mapping_status=="ATTRIBUTE_NOT_MAPPED").sum()),
        concept_mapping_success=int(g.mapping_status.isin(["EXACT","PARTIAL"]).sum()),
        conflict_groups=int(g[g.conflict_group_id!=""].conflict_group_id.nunique()),
        review_needed_facts=int(((g.review_needed=="True")|(g.map_review=="True")).sum()),
        source_limitation=bool(indep < 2)))
Q = pd.DataFrame(rows); Q.to_csv(OUT/"03_profile_quality_audit.csv", index=False)

# ---------- 04 external pair differences ----------
PAIRS = [("A","Acute rhinosinusitis","Chronic rhinosinusitis"),("B","Stable angina","Unstable angina"),("C","Acute laryngitis","Viral pharyngitis")]
def concept_key(r): return r.umls_cui if r.umls_cui else r.base_concept.lower()
def vals(g, col): return " || ".join(sorted(set(f"{v} [{s}]" for v, s in zip(g[col], g.source_id) if v)))
prow=[]
for pid, a, b in PAIRS:
    ga, gb = M[M.disease==a], M[M.disease==b]
    ka, kb = {concept_key(r): r.base_concept for r in ga.itertuples()}, {concept_key(r): r.base_concept for r in gb.itertuples()}
    common = sorted(set(ka)&set(kb)); ua = sorted(set(ka)-set(kb)); ub = sorted(set(kb)-set(ka))
    def names(keys, d): return "; ".join(sorted(set(d[k] for k in keys)))
    def attr_diff(col):
        return f"{a}: {vals(ga,col) or '-'} ### {b}: {vals(gb,col) or '-'}"
    prow.append(dict(pair_id=pid, disease_a=a, disease_b=b, n_facts_a=len(ga), n_facts_b=len(gb),
        n_common_concepts=len(common), common_concepts=names(common, ka), n_unique_a=len(ua), unique_a_concepts=names(ua, ka),
        n_unique_b=len(ub), unique_b_concepts=names(ub, kb),
        temporal_difference=attr_diff("duration")+" ### ONSET: "+attr_diff("onset"),
        location_difference=attr_diff("location"), trigger_relief_difference="TRIGGER: "+attr_diff("trigger")+" ### RELIEF: "+attr_diff("relieving_factor"),
        progression_difference=attr_diff("progression"), exposure_risk_difference="EXPOSURE: "+attr_diff("exposure_context")+" ### HISTORY: "+attr_diff("history_context"),
        objective_finding_difference=f"{a}: {vals(ga[ga.fact_category.isin(['sign','lab_finding'])],'value_raw') or '-'} ### {b}: {vals(gb[gb.fact_category.isin(['sign','lab_finding'])],'value_raw') or '-'}",
        differentiating_features_external_only=""))
P = pd.DataFrame(prow)
P.loc[P.pair_id=="A","differentiating_features_external_only"] = ("DURATION is the primary discriminator: ARS <12 weeks (EPOS; 4 weeks MedlinePlus/NHS course) vs CRS >=12 weeks / >3 months (EPOS, CMAJ, MedlinePlus). "
 "ONSET: ARS sudden onset, often after a cold (CDC/NHS/MedlinePlus) vs CRS lingering/long-term. COURSE: ARS double-worsening after day 5 / persistence after day 10 is a red flag (CDC, EPOS); "
 "CRS symptoms milder and persistent (MedlinePlus). OBJECTIVE: CRS diagnosis REQUIRES objective endoscopy/CT evidence (AAO-HNS, CMAJ, EPOS) whereas ARS imaging is not indicated when clinical criteria met (AAO-HNS). "
 "FEVER: part of ARS/ABRS criteria (EPOS >38C; NHS high temperature) but signals an alternate/acute diagnosis in CRS (CMAJ). CONTEXT: CRS associated with asthma (25%), polyps, inflammatory rather than infectious etiology, bilateral; unilateral -> red flag.")
P.loc[P.pair_id=="B","differentiating_features_external_only"] = ("PATTERN/TRIGGER: stable = predictable, provoked by exertion/mental stress/cold/large meals, pattern unchanged >=2 months (NHLBI, NHS, MedlinePlus); unstable = new, more frequent, more severe, at rest/sleep or with less activity, no pattern (NHLBI, MedlinePlus, NHS). "
 "RELIEF: stable relieved by rest or nitroglycerin/GTN within minutes; unstable NOT relieved (or poorly) by rest/medicine. DURATION: stable few minutes (<5 min NHLBI; <10 min NHS; 1-15 min MedlinePlus, conflict CG_SA_DUR) vs unstable >20 min (NHLBI) / >15-20 min (MedlinePlus), or recurrent. "
 "PROGRESSION: stable = stable; unstable = crescendo/worsening over short period. ASSOCIATED: unstable may have hypotension or dyspnea; LAB: troponin/ECG relevant to unstable. Shared: retrosternal chest pain quality, radiation, CAD risk factors, family history of early CHD -> not discriminating.")
P.loc[P.pair_id=="C","differentiating_features_external_only"] = ("LOCATION: laryngitis = larynx/vocal cords (voice symptoms: hoarseness, voice loss, aphonia, throat clearing; exam hyperemic vocal folds) vs pharyngitis = throat at/below tonsils (odynophagia, scratchy throat, tender cervical nodes). "
 "Hoarseness is a core symptom of laryngitis but only an associated/viral-suggesting feature of pharyngitis (CDC). ONSET/COURSE: laryngitis sudden, worst first 3 days, resolves 1-2 weeks (NHS; hoarseness median 3 days in colds, Mandell) vs pharyngitis resolves within ~1 week (CDC/NHS) or 7-10 days (MedlinePlus). "
 "CONTEXT: both occur with viral URTI; laryngitis additionally from voice overuse, GERD, irritants (Mandell, MedlinePlus). RED FLAGS differ: laryngitis stridor/airway, hoarseness >2-4 weeks (AAO-HNS laryngoscopy) vs pharyngitis drooling, dysphagia, rash, joint pain. Overlap: sore throat, fever, cough, cervical lymphadenopathy -> not discriminating.")
P.to_csv(OUT/"04_external_pair_differences.csv", index=False)

# ---------- 05 manual review queue ----------
q=[]
for r in M.itertuples():
    reasons=[]
    if r.mapping_status=="AMBIGUOUS_MULTI_CUI": reasons.append("multiple_CUI")
    if r.mapping_status=="PARTIAL": reasons.append("mapped_via_synonym_or_parent_concept")
    if r.mapping_status=="FAIL": reasons.append("concept_mapping_FAIL")
    if r.conflict_group_id: reasons.append("source_conflict:"+r.conflict_group_id)
    if r.review_reason: reasons.append(r.review_reason)
    if r.fact_category=="negative_finding": reasons.append("negative_finding_interpretation")
    if r.fact_category in ("trigger_relief",) : reasons.append("trigger_relief_interpretation")
    if r.fact_category in ("history","family_history"): reasons.append("history_vs_family_placement_check")
    if r.fact_category=="risk_factor" and r.diagnostic_role!="risk": reasons.append("risk_vs_symptom_check")
    if r.fact_category=="diagnostic_criteria": reasons.append("criterion_vs_general_symptom_check")
    if r.source_limitation=="True": reasons.append("source_not_independent")
    q.append(dict(fact_id=r.fact_id, disease=r.disease, base_concept=r.base_concept, fact_category=r.fact_category, value_raw=r.value_raw,
                  source_id=r.source_id, mapping_status=r.mapping_status, umls_cui=r.umls_cui, review_reasons="|".join(reasons)))
Qd = pd.DataFrame(q)
single = set(Q[Q.n_independent_orgs<2].disease)
Qd["single_source_disease"] = Qd.disease.isin(single)
Qd = Qd[(Qd.review_reasons!="")|Qd.single_source_disease]
Qd.to_csv(OUT/"05_manual_review_queue.csv", index=False)

# ---------- 06 human review sheet ----------
reg = R.set_index("source_id")
H = pd.DataFrame(dict(fact_id=M.fact_id, disease=M.disease,
    fact_summary=M.base_concept+" | "+M.relation+" | "+M.value_raw.str.slice(0,160),
    source_short=M.source_id.map(lambda s: reg.loc[s,"organization"]+" "+str(reg.loc[s,"publication_year"])),
    source_url=M.source_id.map(lambda s: reg.loc[s,"url"]), source_quote_short=M.source_quote_short,
    current_mapping=M.umls_cui+" "+M.umls_preferred_name+" ["+M.mapping_status+"]"+(" SNOMED:"+M.snomed_id).where(M.snomed_id!="","")+(" HPO:"+M.hpo_id).where(M.hpo_id!="",""),
    issue=M.fact_id.map(Qd.set_index("fact_id").review_reasons.to_dict()).fillna(""), approve="", corrected_value="", reviewer_note=""))
H.to_csv(OUT/"06_HUMAN_REVIEW_SHEET.csv", index=False)
print(Q.to_string()); print("review queue", len(Qd), "sheet", len(H))
