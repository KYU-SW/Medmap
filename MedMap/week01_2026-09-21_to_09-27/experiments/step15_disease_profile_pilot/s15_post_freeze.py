"""STEP15 post-freeze: DDXPlus evidence ↔ frozen profile 비교, coverage, pair 판별, before/after, review queue, scale-up. (freeze 파일 무수정)"""
import pandas as pd, json, re, hashlib, collections, numpy as np, os, time
O = "exp/step15_disease_profile_pilot"; S14 = "exp/step14_value_context_recovery"; S13B = "exp/step13b_external_verifier"
fr = json.load(open(f"{O}/PROFILE_FREEZE.json"))
for f, h in fr["file_sha256"].items(): assert hashlib.sha256(open(f"{O}/{f}", "rb").read()).hexdigest() == h, f"FREEZE violated: {f}"
F = pd.read_csv(f"{O}/01_disease_profile_facts.csv", dtype=str).fillna(""); C = pd.read_csv(f"{O}/02_disease_profile_concepts.csv", dtype=str).fillna("").set_index("fact_id")
cond = json.load(open("data/ddxplus/en/release_conditions.json")); ev = json.load(open("data/ddxplus/en/release_evidences.json"))
VL = pd.read_csv(f"{S14}/07_evidence_value_level_map.csv", dtype=str).fillna("").set_index("evidence_id"); TX = pd.read_csv(f"{S14}/01_evidence_taxonomy.csv", dtype=str).fillna("").set_index("evidence_id")
NAME = {"Acute rhinosinusitis": "Acute rhinosinusitis", "Chronic rhinosinusitis": "Chronic rhinosinusitis", "Acute laryngitis": "Acute laryngitis", "Viral pharyngitis": "Viral pharyngitis", "Stable angina": "Stable angina", "Unstable angina": "Unstable angina", "HIV (initial infection)": "Acute HIV infection", "Scombroid food poisoning": "Scombroid poisoning", "Acute COPD exacerbation / infection": "Acute COPD exacerbation", "PSVT": "PSVT"}
def words(s): return set(re.findall(r"[a-z]{3,}", s.lower())) - {"the", "and", "with", "your", "for", "from", "have", "you", "that", "does", "any", "more", "than", "when", "one", "both"}
BROAD = {"pain", "symptoms", "sinusitis symptoms", "chest pain"}
maps, covs = [], []
for dd, pname in NAME.items():
    rel = list(cond[dd]["symptoms"]) + list(cond[dd]["antecedents"]); facts = F[F.disease == pname]
    for e in rel:
        v = VL.loc[e]; tx = TX.loc[e]; ecui, ehpo = v.base_cui, v.base_hpo; e_attr = [k for k in ["attribute_location", "attribute_severity", "attribute_onset", "attribute_duration", "attribute_frequency", "context_history", "context_family", "context_medication", "context_exposure", "context_lifestyle"] if v[k]]
        best, bstat, why = "", "NO_MATCH", ""
        for fr_ in facts.itertuples():
            cc = C.loc[fr_.fact_id]; fcui = cc.umls_cui; f_attr = [k for k in ["location", "severity", "onset", "duration", "frequency", "progression", "trigger", "relieving_factor", "history_context", "family_context", "exposure_context", "medication_context"] if getattr(fr_, k)]
            same_cui = bool(fcui) and (fcui == ecui or fcui == v.concept_2_cui); same_hpo = bool(ehpo) and ehpo == cc.hpo
            name_ov = len(words(fr_.base_concept) & (words(v.base_concept) | words(v.concept_2))) > 0 or fr_.base_concept.lower() in v.original_text.lower() or v.base_concept.lower() in fr_.value_raw.lower()
            if same_cui or same_hpo:
                st = "ATTRIBUTE_MATCH" if (e_attr and f_attr and fr_.fact_category in ("TRIGGER", "RELIEVING", "ONSET", "DURATION", "PROGRESSION", "LOCATION", "CHARACTER", "TEMPORAL", "SEVERITY")) or (e_attr and f_attr) else "DIRECT_MATCH"
            elif name_ov: st = "PARTIAL_MATCH"
            else: continue
            rank = {"ATTRIBUTE_MATCH": 3, "DIRECT_MATCH": 2, "PARTIAL_MATCH": 1}
            if rank[st] > rank.get(bstat, 0): best, bstat, why = fr_.fact_id, st, f"{fr_.base_concept} [{fr_.fact_category}] attrs={f_attr}"
        if v.base_concept.lower() in BROAD and bstat == "PARTIAL_MATCH": why += " | evidence concept broader than fact"
        maps.append({"ddxplus_original_name": dd, "normalized_disease_name": pname, "evidence_id": e, "evidence_text": v.original_text, "evidence_primary_type": tx.primary_type, "evidence_base_concept": v.base_concept, "evidence_attributes": ";".join(e_attr), "evidence_step14_eligibility": pd.read_csv(f"{S14}/09_expanded_eligibility.csv", dtype=str).set_index("evidence_id").loc[e, "expanded_eligibility"], "match_status": bstat, "matched_fact_id": best, "matched_fact_detail": why})
    M = pd.DataFrame([x for x in maps if x["ddxplus_original_name"] == dd]); basic = M[M.evidence_primary_type.isin(["SYMPTOM", "SIGN"])]
    covs.append({"ddxplus_original_name": dd, "normalized_disease_name": pname, "n_ddxplus_related_evidence": len(rel), "n_profile_facts": len(facts), "n_profile_facts_concept_linked": int((C.loc[facts.fact_id].mapping_status == "EXACT").sum()), "direct_match": int((M.match_status == "DIRECT_MATCH").sum()), "attribute_match": int((M.match_status == "ATTRIBUTE_MATCH").sum()), "partial_match": int((M.match_status == "PARTIAL_MATCH").sum()), "no_match": int((M.match_status == "NO_MATCH").sum()),
                 "basic_n(symptom/sign evidence)": len(basic), "basic_covered(direct+attribute)": int(basic.match_status.isin(["DIRECT_MATCH", "ATTRIBUTE_MATCH"]).sum()), "basic_coverage": round(basic.match_status.isin(["DIRECT_MATCH", "ATTRIBUTE_MATCH"]).mean(), 3) if len(basic) else None, "value_level_n(all evidence)": len(M), "value_level_covered(direct+attribute)": int(M.match_status.isin(["DIRECT_MATCH", "ATTRIBUTE_MATCH"]).sum()), "value_level_coverage": round(M.match_status.isin(["DIRECT_MATCH", "ATTRIBUTE_MATCH"]).mean(), 3), "value_level_coverage_incl_partial": round((M.match_status != "NO_MATCH").mean(), 3)})
MP = pd.DataFrame(maps); MP.to_csv(f"{O}/04_ddxplus_profile_mapping.csv", index=False); CV = pd.DataFrame(covs); CV.to_csv(f"{O}/05_disease_profile_coverage.csv", index=False)
# ---- pairs (외부 fact만 사용)
PAIRS = [("Acute rhinosinusitis", "Chronic rhinosinusitis"), ("Stable angina", "Unstable angina"), ("Acute laryngitis", "Viral pharyngitis")]
pv = pd.read_csv(f"{S14}/05_error_pair_missing_information.csv", dtype=str)
inv = {v: k for k, v in NAME.items()}
for r in pv.itertuples():
    a, b = NAME.get(r.true_diagnosis), NAME.get(r.working_diagnosis)
    if a and b and (a, b) not in PAIRS and (b, a) not in PAIRS: PAIRS.append((a, b))
prow = []
for a, b in PAIRS:
    fa, fb = F[F.disease == a], F[F.disease == b]; ca = {C.loc[x].umls_cui for x in fa.fact_id if C.loc[x].umls_cui}; cb = {C.loc[x].umls_cui for x in fb.fact_id if C.loc[x].umls_cui}
    def named(cuis, g): return sorted({C.loc[x].base_concept for x in g.fact_id if C.loc[x].umls_cui in cuis})
    def attr(g, col): return sorted({getattr(x, col) for x in g.itertuples() if getattr(x, col)})
    prow.append({"disease_A": a, "disease_B": b, "shared_concepts": "; ".join(named(ca & cb, fa)), "A_only_concepts": "; ".join(named(ca - cb, fa)), "B_only_concepts": "; ".join(named(cb - ca, fb)), "A_time(onset/duration/progression)": "; ".join(attr(fa, "onset") + attr(fa, "duration") + attr(fa, "progression")), "B_time": "; ".join(attr(fb, "onset") + attr(fb, "duration") + attr(fb, "progression")), "A_trigger_relief": "; ".join(attr(fa, "trigger") + attr(fa, "relieving_factor")), "B_trigger_relief": "; ".join(attr(fb, "trigger") + attr(fb, "relieving_factor")), "A_location": "; ".join(attr(fa, "location")), "B_location": "; ".join(attr(fb, "location")), "A_exposure": "; ".join(attr(fa, "exposure_context")), "B_exposure": "; ".join(attr(fb, "exposure_context")), "A_risk_history": "; ".join(attr(fa, "history_context") + attr(fa, "family_context")), "B_risk_history": "; ".join(attr(fb, "history_context") + attr(fb, "family_context")), "distinguishing_facts_A": "; ".join(fa[fa.fact_category.isin(["DISTINGUISHING", "NEGATIVE_FINDING", "DURATION", "ONSET", "PROGRESSION", "TRIGGER", "RELIEVING"])].value_normalized.head(6)), "distinguishing_facts_B": "; ".join(fb[fb.fact_category.isin(["DISTINGUISHING", "NEGATIVE_FINDING", "DURATION", "ONSET", "PROGRESSION", "TRIGGER", "RELIEVING"])].value_normalized.head(6)), "discriminable_by_profile": bool((ca ^ cb) or (attr(fa, "duration") != attr(fb, "duration")) or (attr(fa, "trigger") != attr(fb, "trigger")) or (attr(fa, "onset") != attr(fb, "onset")))})
PP = pd.DataFrame(prow); PP.to_csv(f"{O}/06_pair_discriminative_profile.csv", index=False)
# ---- before/after vs Step13b strict KB
R = pd.read_csv(f"{S13B}/00b_relation_matrix_nonzero.csv", dtype=str)
ba = []
for dd, pname in NAME.items():
    kb = R[R.ddxplus_disease == dd]; facts = F[F.disease == pname]; cc = C.loc[facts.fact_id]; M = MP[MP.ddxplus_original_name == dd]
    ba.append({"ddxplus_original_name": dd, "kg_strict_relations(83 findings)": int((kb.strict_score == "1").sum()), "kg_lenient_relations": int((kb.lenient_score == "1").sum()), "kg_disease_known_strict": bool((kb.strict_score == "1").any()), "profile_facts": len(facts), "profile_concept_linked": int((cc.mapping_status == "EXACT").sum()), "profile_value_level_facts(time/location/trigger/context)": int(((facts.onset != "") | (facts.duration != "") | (facts.progression != "") | (facts.trigger != "") | (facts.relieving_factor != "") | (facts.location != "") | (facts.exposure_context != "") | (facts.history_context != "") | (facts.family_context != "") | (facts.medication_context != "")).sum()), "kg_value_level_facts": 0, "ddxplus_evidence_covered_by_kg(strict)": int(kb[kb.strict_score == "1"].evidence_id.nunique()), "ddxplus_evidence_covered_by_profile(direct+attribute)": int(M.match_status.isin(["DIRECT_MATCH", "ATTRIBUTE_MATCH"]).sum()), "ddxplus_evidence_covered_by_profile(incl_partial)": int((M.match_status != "NO_MATCH").sum()), "n_related_evidence": len(M)})
BA = pd.DataFrame(ba); BA.to_csv(f"{O}/07_before_after_knowledge_coverage.csv", index=False)
# ---- review queue
rq = []
for r in F.itertuples():
    reasons = []
    if r.review_needed == "True": reasons.append("flagged at authoring")
    if C.loc[r.fact_id].n_cui_candidates not in ("0", "1", 0, 1): reasons.append("ambiguous UMLS mapping")
    if C.loc[r.fact_id].mapping_status == "FAIL": reasons.append("no UMLS concept")
    if r.fact_category in ("RISK_FACTOR", "MEDICAL_HISTORY") and r.relation == "caused_by": reasons.append("risk factor vs cause vs symptom boundary")
    if r.fact_category in ("DURATION", "ONSET") and re.search(r"\d", r.value_raw): reasons.append("numeric range check across sources")
    if ";" in r.source_id: reasons.append("multi-source wording differs (patient vs guideline)")
    if r.disease.startswith("Chronic") or r.disease.startswith("Acute rhinos"): reasons.append("acute/chronic boundary definition")
    if r.fact_category == "DISTINGUISHING": reasons.append("diagnostic criterion vs common feature")
    if reasons: rq.append({"fact_id": r.fact_id, "disease": r.disease, "base_concept": r.base_concept, "fact_category": r.fact_category, "reasons": "; ".join(reasons), "source_id": r.source_id})
RQ = pd.DataFrame(rq); RQ.to_csv(f"{O}/08_manual_review_queue.csv", index=False)
# ---- scale-up estimate (실측 로그 기반)
t_fetch = os.path.getmtime("data/disease_profiles/raw/S01.html"); t_freeze = time.mktime(time.strptime(fr["timestamp"], "%Y-%m-%dT%H:%M:%S")); hours = (t_freeze - t_fetch) / 3600
A = pd.read_csv(f"{O}/03_profile_quality_audit.csv")
est = {"pilot_diseases": 10, "sources_attempted": 25, "sources_usable": int(pd.read_csv(f"{O}/00_source_registry.csv").status.eq("USED").sum()), "sources_per_disease_mean": round(A.n_sources.mean(), 2), "facts_per_disease_mean": round(A.n_facts.mean(), 1), "concept_linked_per_disease_mean": round(A.n_concept_linked.mean(), 1), "review_facts_total": len(RQ), "review_per_disease_mean": round(len(RQ) / 10, 1), "pilot_wallclock_hours_fetch_to_freeze": round(hours, 2), "hours_per_disease_observed": round(hours / 10, 2), "assumed_human_review_min_per_fact": 2, "review_hours_per_disease_est": round(len(RQ) / 10 * 2 / 60, 2),
       "scaleup_49_facts_est": int(round(A.n_facts.mean() * 49)), "scaleup_49_review_est": int(round(len(RQ) / 10 * 49)), "scaleup_49_authoring_hours_est": round(hours / 10 * 49, 1), "scaleup_49_review_hours_est": round(len(RQ) / 10 * 49 * 2 / 60, 1), "caveat": "authoring time = single-session AI-assisted extraction from 1-3 public-domain pages per disease (StatPearls/CDC guideline pages partly blocked); review-minute assumption (2 min/fact) is an assumption, not measured"}
pd.DataFrame([est]).to_csv(f"{O}/09_scaleup_estimate.csv", index=False)
pd.set_option("display.width", 250); print(CV[["ddxplus_original_name", "n_ddxplus_related_evidence", "n_profile_facts", "direct_match", "attribute_match", "partial_match", "no_match", "basic_coverage", "value_level_coverage", "value_level_coverage_incl_partial"]].to_string()); print(BA[["ddxplus_original_name", "kg_strict_relations(83 findings)", "kg_disease_known_strict", "profile_facts", "profile_value_level_facts(time/location/trigger/context)", "ddxplus_evidence_covered_by_kg(strict)", "ddxplus_evidence_covered_by_profile(direct+attribute)", "ddxplus_evidence_covered_by_profile(incl_partial)"]].to_string()); print(PP[["disease_A", "disease_B", "A_only_concepts", "B_only_concepts", "A_time(onset/duration/progression)", "B_time", "A_trigger_relief", "B_trigger_relief", "discriminable_by_profile"]].to_string()); print("review", len(RQ), est)
json.dump({"coverage": CV.to_dict("records"), "before_after": BA.to_dict("records"), "pairs": PP[["disease_A", "disease_B", "discriminable_by_profile"]].to_dict("records"), "review_queue": len(RQ), "scaleup": est, "match_status_total": MP.match_status.value_counts().to_dict()}, open(f"{O}/10_summary.json", "w"), indent=1, default=str)
