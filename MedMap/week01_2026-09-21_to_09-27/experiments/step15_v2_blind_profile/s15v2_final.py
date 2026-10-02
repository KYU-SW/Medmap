"""07 scaleup estimate, 08 v1-v2 structural comparison, MANUAL_SOURCE_REQUEST.md, guardian self-checks, PROFILE_FREEZE_V2.json."""
import pathlib, pandas as pd, json, hashlib, subprocess, datetime, re, sys, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, "exp/step15_v2_blind_profile")
from s15v2_schema import TIME_UNIT, TIME_HINT, FAMILY_HINT, ANAT, ONSET_HINT, norm
OUT = pathlib.Path("exp/step15_v2_blind_profile"); V1 = pathlib.Path("exp/step15_disease_profile_pilot")
F = pd.read_csv(OUT/"01_disease_profile_facts.csv", dtype=str, keep_default_na=False)
C = pd.read_csv(OUT/"02_disease_profile_concepts.csv", dtype=str, keep_default_na=False)
R = pd.read_csv(OUT/"00_source_registry.csv", dtype=str, keep_default_na=False)
Q = pd.read_csv(OUT/"03_profile_quality_audit.csv")
RV = pd.read_csv(OUT/"05_manual_review_queue.csv", dtype=str, keep_default_na=False)
log = [json.loads(l) for l in (pathlib.Path("data/disease_profiles_v2/raw/fetch_log.jsonl").read_text().splitlines())]
SESSION_START = "2026-09-21T22:52:00"; SESSION_END = datetime.datetime.now().isoformat(timespec="seconds")
elapsed_min = (datetime.datetime.fromisoformat(SESSION_END) - datetime.datetime.fromisoformat(SESSION_START)).total_seconds()/60

# ---------- MANUAL_SOURCE_REQUEST ----------
MAN = [
 ("Acute rhinosinusitis","IDSA Clinical Practice Guideline for Acute Bacterial Rhinosinusitis (Chow et al. 2012, Clin Infect Dis 54:e72)","https://academic.oup.com/cid/article/54/8/e72/364306","Tier1 society guideline with explicit ABRS clinical criteria (10-day / double-worsening / severe onset); OUP returned HTTP 403","PDF"),
 ("Chronic rhinosinusitis","StatPearls: Chronic Rhinosinusitis (NCBI Bookshelf NBK441934)","https://www.ncbi.nlm.nih.gov/books/NBK441934/","Bookshelf HTML is JS/captcha-gated to curl; optional Tier3 backup only","HTML (save page as .html)"),
 ("Viral pharyngitis","IDSA GAS pharyngitis guideline full text (Shulman et al. 2012, CID 55:e86)","https://academic.oup.com/cid/article/55/10/e86/321183","Full text lists viral-suggestive features (conjunctivitis, coryza, cough, hoarseness, ulcers); abstract has no clinical content; OUP 403","PDF"),
 ("Stable angina","2021 AHA/ACC/ASE/CHEST/SAEM/SCCT/SCMR Chest Pain Guideline (Circulation 144:e368)","https://www.ahajournals.org/doi/10.1161/CIR.0000000000001029","Tier1 guideline defining typical/atypical angina descriptors; ahajournals 403, PubMed abstract has no clinical content","PDF"),
 ("Stable angina","2023 AHA/ACC Chronic Coronary Disease guideline (Circulation 148:e9)","https://www.ahajournals.org/doi/10.1161/CIR.0000000000001168","Tier1 definition of stable angina / CCD; not attempted after repeated 403 on same host","PDF"),
 ("Unstable angina","2025 ACC/AHA/ACEP/NAEMSP/SCAI ACS Guideline (or 2014 AHA/ACC NSTE-ACS, Circulation 130:e344)","https://www.ahajournals.org/doi/10.1161/CIR.0000000000000134","Tier1 definition of unstable angina (rest angina >20 min, new-onset, crescendo); ahajournals 403, PubMed record has no abstract","PDF"),
 ("Acute HIV infection","NIH Clinicalinfo: Acute and Recent (Early) HIV Infection (Adult and Adolescent ARV Guidelines)","https://clinicalinfo.hiv.gov/en/guidelines/hiv-clinical-guidelines-adult-and-adolescent-arv/acute-and-recent-early-hiv-infection","Tier1 clinical description of acute retroviral syndrome signs/symptoms with frequencies and lab staging; HTTP 403","HTML or PDF"),
 ("PSVT","2015 ACC/AHA/HRS Guideline for the Management of Adult Patients With SVT (Circulation 133:e506 / JACC 67:e27)","https://www.ahajournals.org/doi/10.1161/CIR.0000000000000311","Tier1 definitions (PSVT, AVNRT/AVRT), symptom list, ECG criteria; ahajournals/JACC/HRS all 403, PubMed record has no abstract","PDF"),
 ("PSVT","2019 ESC Guidelines for the management of patients with SVT (Eur Heart J 41:655)","https://academic.oup.com/eurheartj/article/41/5/655/5556821","Second Tier1 guideline source for PSVT; OUP 403","PDF"),
 ("Acute COPD exacerbation","ERS/ATS guideline: Management of COPD exacerbations (Wedzicha 2017, Eur Respir J 49:1600791) full text","https://erj.ersjournals.com/content/49/3/1600791","Full text (abstract lacks clinical content); optional since GOLD 2025 + NICE NG115 already Tier1","PDF"),
]
md = ["# MANUAL_SOURCE_REQUEST (STEP15 v2)\n", f"Generated {SESSION_END}. These documents were blocked (HTTP 403 / JS-gated) or contained no clinical content in the accessible abstract. No bypass was attempted. ",
      "If needed, download manually and place files in `data/disease_profiles_v2/manual_sources/<disease_slug>/`; a later builder pass can add facts with new source_ids (facts below were NOT written from these documents).\n",
      "| # | Disease | Document | Official URL | Why needed | Format |","|---|---|---|---|---|---|"]
for i,(d,doc,u,w,fmt) in enumerate(MAN,1): md.append(f"| {i} | {d} | {doc} | {u} | {w} | {fmt} |")
(OUT/"MANUAL_SOURCE_REQUEST.md").write_text("\n".join(md)+"\n")

# ---------- 07 scaleup ----------
n_dis=10; attempts=len({l["source_id"] for l in log}); ok_used=int((R.status=="OK").sum()); blocked=int((R.status!="OK").sum())
per = dict(avg_sources_per_disease=round(ok_used/n_dis,2), avg_independent_orgs_per_disease=round(Q.n_independent_orgs.mean(),2),
  avg_tier1_per_disease=round(Q.n_tier1_sources.mean(),2), avg_facts_per_disease=round(len(F)/n_dis,1), avg_value_level_per_disease=round(Q.value_level_facts.mean(),1),
  avg_review_needed_per_disease=round(Q.review_needed_facts.mean(),1), avg_manual_review_queue_rows_per_disease=round(len(RV)/n_dis,1),
  fetch_attempts_total=attempts, fetch_ok_used=ok_used, fetch_blocked_or_unusable=blocked,
  auto_collection_success_rate=round(ok_used/attempts,3), manual_source_requests=len(MAN), manual_request_rate_per_disease=round(len(MAN)/n_dis,2),
  diseases_with_lt2_independent_orgs=int((Q.n_independent_orgs<2).sum()), session_minutes_total=round(elapsed_min,1), minutes_per_disease=round(elapsed_min/n_dis,1),
  reviewer_minutes_per_disease_assumed=None)
rows=[]
for k,v in per.items(): rows.append(dict(metric=k, pilot_value_10=v, projection_49=(round(v*4.9,1) if isinstance(v,(int,float)) and k.startswith(("avg_","fetch_","manual_source","session_")) and not k.startswith("avg_") else ""), note=""))
proj = dict(projected_sources_49=round(ok_used/n_dis*49), projected_facts_49=round(len(F)/n_dis*49), projected_value_level_facts_49=round(Q.value_level_facts.mean()*49),
  projected_review_needed_49=round(Q.review_needed_facts.mean()*49), projected_manual_review_rows_49=round(len(RV)/n_dis*49), projected_manual_documents_49=round(len(MAN)/n_dis*49),
  projected_builder_minutes_49=round(elapsed_min/n_dis*49), projected_fetch_attempts_49=round(attempts/n_dis*49),
  projected_diseases_lt2_independent_orgs_49=round((Q.n_independent_orgs<2).mean()*49))
for k,v in proj.items(): rows.append(dict(metric=k, pilot_value_10="", projection_49=v, note="linear scaling of pilot rate x4.9; assumes similar web accessibility"))
rows.append(dict(metric="caveat", pilot_value_10="", projection_49="", note="Pilot diseases were chosen because of prior confusion pairs; rarer conditions may have fewer Tier1 pages (higher manual rate). Builder time is Claude session wall-clock, not human time."))
pd.DataFrame(rows).to_csv(OUT/"07_scaleup_estimate.csv", index=False)

# ---------- 08 v1 vs v2 ----------
v1 = pd.read_csv(V1/"01_disease_profile_facts.csv", dtype=str, keep_default_na=False)
c1 = pd.read_csv(V1/"02_disease_profile_concepts.csv", dtype=str, keep_default_na=False)
r1 = pd.read_csv(V1/"00_source_registry.csv", dtype=str, keep_default_na=False)
def struct(df):
    fam = ((df.family_context!="")&~df.family_context.str.contains(FAMILY_HINT)).sum()
    dur = ((df.duration!="")&~(df.duration.str.contains(TIME_UNIT)&df.duration.str.contains(TIME_HINT))).sum()
    trig= ((df.trigger!="")&(df.trigger.str.contains(TIME_UNIT)|df.trigger.str.contains(r"\d"))).sum()
    loc = ((df.location!="")&~df.location.str.lower().apply(lambda s:any(a in s for a in ANAT))).sum()
    ons = ((df.onset!="")&~df.onset.str.contains(ONSET_HINT)).sum()
    return int(fam),int(dur),int(trig),int(loc),int(ons)
f1=struct(v1); f2=struct(F)
def quotes_verified(df, rawdir, multi_ok=True):
    ok=0
    for r in df.itertuples():
        sids = r.source_id.split(";")
        txt="".join(norm(p.read_text(errors="replace")) for s in sids for p in [rawdir/f"{s}.txt", rawdir/f"{s}_webfetch.txt"] if p.exists())
        if txt and norm(r.source_quote_short) in txt: ok+=1
    return ok
q1 = quotes_verified(v1, pathlib.Path("data/disease_profiles/raw")); q2 = quotes_verified(F, pathlib.Path("data/disease_profiles_v2/raw"))
v1_used = r1[r1.status=="USED"]; v1_mlp = v1_used.organization.str.contains("MedlinePlus").sum()
v1_t1 = v1_used.organization.str.contains("CDC|AAO-HNS|NIH").sum()
v2_used = R[R.status=="OK"]
cmp = [
 ("facts_total", len(v1), len(F)),
 ("column_alignment_errors_family_context_nonfamily", f1[0], f2[0]),
 ("invalid_attribute_duration_not_time", f1[1], f2[1]),
 ("invalid_attribute_trigger_contains_time_or_number", f1[2], f2[2]),
 ("invalid_attribute_location_not_anatomical", f1[3], f2[3]),
 ("invalid_attribute_onset", f1[4], f2[4]),
 ("facts_without_source", int((v1.source_id=="").sum()), int((F.source_id=="").sum())),
 ("facts_without_quote", int((v1.source_quote_short=="").sum()), int((F.source_quote_short=="").sum())),
 ("quotes_verbatim_verified_in_raw_text", q1, q2),
 ("duplicate_facts_(disease,concept,relation,source)", int(v1.duplicated(subset=["disease","base_concept","relation","source_id"]).sum()), int(F.duplicated(subset=["disease","base_concept","relation","source_id"]).sum())),
 ("invented_probability_values_in_frequency", int(v1.frequency.str.match(r"^\s*0?\.\d+\s*$").sum()), int(F.frequency.str.match(r"^\s*0?\.\d+\s*$").sum())),
 ("conflict_groups_recorded", 0, int(F[F.conflict_group_id!=""].conflict_group_id.nunique())),
 ("multi_CUI_ambiguity_flagged", int((c1.get("n_cui_candidates",pd.Series(["1"]*len(c1))).astype(str).str.strip().replace("","1").astype(int)>1).sum()), int((C.mapping_status=="AMBIGUOUS_MULTI_CUI").sum()+C.mapping_reason.str.contains("raw CUIs").sum())),
 ("concept_EXACT", int((c1.mapping_status=="EXACT").sum()), int((C.mapping_status=="EXACT").sum())),
 ("concept_PARTIAL", 0, int((C.mapping_status=="PARTIAL").sum())),
 ("concept_FAIL", int((c1.mapping_status=="FAIL").sum()), int((C.mapping_status=="FAIL").sum())),
 ("sources_used", len(v1_used), len(v2_used)),
 ("tier1_sources_used", int(v1_t1), int((v2_used.source_tier=="tier1").sum())),
 ("tier1_share_of_used_sources", round(v1_t1/len(v1_used),2), round((v2_used.source_tier=="tier1").mean(),2)),
 ("medlineplus_share_of_used_sources", round(v1_mlp/len(v1_used),2), round(v2_used.organization.str.contains("MedlinePlus").mean(),2)),
 ("diseases_with_single_source", int((v1.groupby("disease").source_id.nunique()<2).sum()), int((Q.n_independent_orgs<2).sum())),
 ("manual_review_rows", sum(1 for _ in open(V1/"08_manual_review_queue.csv"))-1, len(RV)),
 ("blind_authoring", "NOT_MET (same session had DDXPlus context)", "BLIND_VALID (see PROFILE_FREEZE_V2.json disclosure)"),
 ("fact_construction_method", "hand-typed TSV -> CSV", "Python dataclass + validators + pandas"),
 ("schema_validation_on_save", "none", "per-row validate() incl. quote-in-source check; build fails on error"),
]
pd.DataFrame(cmp, columns=["metric","v1","v2"]).assign(note="v1 not modified; v1 metrics computed read-only from its 00/01/02/08 files (DDXPlus-comparison files 04-07 of v1 were NOT opened)").to_csv(OUT/"08_v1_v2_quality_comparison.csv", index=False)

# ---------- guardian self-check ----------
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
FILES = ["00_source_registry.csv","01_disease_profile_facts.csv","02_disease_profile_concepts.csv","03_profile_quality_audit.csv","04_external_pair_differences.csv","05_manual_review_queue.csv","06_HUMAN_REVIEW_SHEET.csv","07_scaleup_estimate.csv","08_v1_v2_quality_comparison.csv"]
scripts = sorted(p.name for p in OUT.glob("s15v2_*.py"))
code = "\n".join((OUT/s).read_text() for s in scripts if s != "s15v2_final.py")
checks = {
 "1_ddxplus_access_in_scripts": {"pass": not re.search(r"data/ddxplus|release_evidences|release_conditions|exp/step8|exp/step13|exp/step14|evidence_concept_map|04_ddxplus", code, re.I), "detail":"grep of s15v2 scripts (excl. this checker) for DDXPlus/step8/13/14 file-path references; only v1 files 00/01/02/08 are read by this checker"},
 "2_facts_without_source": {"pass": int((F.source_id=="").sum())==0, "detail": f"{int((F.source_id=='').sum())} facts without source"},
 "3_long_copyright_quotes": {"pass": bool((F.source_quote_short.str.split().str.len()<=15).all()), "detail": f"max quote words = {int(F.source_quote_short.str.split().str.len().max())}"},
 "4_invented_probabilities": {"pass": int(F.frequency.str.match(r"^\s*0?\.\d+\s*$").sum())==0 and bool((F.frequency=="").eq(F.frequency_raw=="").all()), "detail":"frequency stored as source literal (frequency_raw)"},
 "5_column_alignment": {"pass": f2==(0,0,0,0,0), "detail": f"family/duration/trigger/location/onset misplacement counts={f2}"},
 "6_duplicate_facts": {"pass": int(F.duplicated(subset=["disease","base_concept","relation","source_id"]).sum())==0, "detail":"key (disease,base_concept,relation,source_id)"},
 "7_all_10_diseases": {"pass": F.disease.nunique()==10, "detail": F.disease.value_counts().to_dict()},
 "8_post_freeze_modification": {"pass": None, "detail":"verified by re-hashing after freeze (see freeze_recheck)"},
 "9_source_tier_classification": {"pass": bool(R[R.status=="OK"].apply(lambda r: r.source_tier == ("tier2" if r.source_type in ("peer_reviewed_review","peer_reviewed_case_image") else "tier3" if r.source_type in ("medlineplus_encyclopedia","textbook_chapter_pmc") else "tier1"), axis=1).all()), "detail":"tier1=gov/society/international guideline; tier2=peer-reviewed journal/PMC OA; tier3=MedlinePlus/textbook chapter"},
 "10_ambiguous_mapped_as_EXACT": {"pass": bool((C[C.mapping_status=="EXACT"].mapping_reason.str.contains("raw CUIs")==False).all() or (C[(C.mapping_status=="EXACT")&C.mapping_reason.str.contains("raw CUIs")].review_needed=="True").all()), "detail":"EXACT facts whose string had >1 raw CUIs are review_needed=True with disambiguation reason recorded"},
 "quotes_verbatim_in_source": {"pass": q2==len(F), "detail": f"{q2}/{len(F)} quotes found verbatim (normalised) in downloaded source text"},
}
n_fail = sum(1 for v in checks.values() if v["pass"] is False)
verdict = "STEP15_V2_PROFILE_GO" if n_fail==0 else ("STEP15_V2_PROFILE_PARTIAL_GO" if n_fail<=2 else "STEP15_V2_PROFILE_NO_GO")
GUIDE_TYPES = {"society_guideline_abstract","international_position_paper","international_guideline_pdf","government_guideline","government_guideline_pdf","government_clinical_guidance","government_guidance_pdf"}
used_by_dis = {}
for r in R[R.status=="OK"].itertuples():
    for d in r.disease.split(";"): used_by_dis.setdefault(d, set()).add(r.source_type)
no_guideline = sorted(d for d,s in used_by_dis.items() if not (s & GUIDE_TYPES))
partial_reasons = []
if (Q.n_independent_orgs<2).sum()>0: partial_reasons.append("disease(s) with <2 independent organisations")
if no_guideline: partial_reasons.append(f"no guideline/clinical-guidance-type source with clinical content for: {no_guideline} (society guidelines blocked -> MANUAL_SOURCE_REQUEST)")
partial_reasons.append("blind disclosure: project memory summaries were read at session start (see PROFILE_FREEZE_V2.json)")
partial_reasons.append("acute HIV symptom itemisation comes from CDC lineage only (HIV.gov re-cites CDC)")
if verdict=="STEP15_V2_PROFILE_GO" and partial_reasons: verdict="STEP15_V2_PROFILE_PARTIAL_GO"
json.dump(dict(checks=checks, n_fail=n_fail, verdict=verdict, partial_reasons=partial_reasons, diseases_without_guideline_source=no_guideline), open(OUT/"GUARDIAN_SELF_CHECK.json","w"), indent=1, default=str)

# ---------- freeze ----------
git = subprocess.run(["git","rev-parse","HEAD"],capture_output=True,text=True).stdout.strip()
freeze = dict(timestamp=SESSION_END, git_commit=git, disease_count=int(F.disease.nunique()), source_count_used=int((R.status=="OK").sum()),
  source_count_attempted=int(len(R)), fact_count=len(F), value_level_fact_count=int(Q.value_level_facts.sum()), review_count=len(RV), concept_status=C.mapping_status.value_counts().to_dict(),
  file_sha256={f: sha(OUT/f) for f in FILES}, script_sha256={s: sha(OUT/s) for s in scripts}, raw_dir="data/disease_profiles_v2/raw", raw_sha256sums="data/disease_profiles_v2/raw/SHA256SUMS.txt",
  blind_status="BLIND_VALID",
  blind_disclosure=("This session did NOT open DDXPlus patient data, release_evidences.json, release_conditions.json, train/validate/test, Step8 evidence map, Step13/14 error analyses, or v1 files 04-08 (DDXPlus comparison). "
    "Disclosure: per CLAUDE.md the project memory index (.claude/memory/medmap-progress-2026-09-21.md) was read at session start; it contains one-line summaries of prior steps (e.g., a statement that DDXPlus has no duration question). No evidence names or question texts were seen. "
    "v1 files 00/01/02/03/08 were read only for structural metrics (column placement, quote verification, counts). Reviewer may downgrade to BLIND_INVALID if the memory summary is judged disqualifying."),
  guardian_verdict=verdict, note="Frozen. No edits to 00-08 after this timestamp; DDXPlus comparison belongs to a separate evaluator session.")
json.dump(freeze, open(OUT/"PROFILE_FREEZE_V2.json","w"), indent=1, ensure_ascii=False)
print(verdict, "fail", n_fail, "| quotes", q2, "/", len(F), "| v1 quotes", q1, "/", len(v1)); print(pd.DataFrame(cmp, columns=["metric","v1","v2"]).to_string())
