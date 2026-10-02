"""02: map base_concept -> UMLS CUI / SNOMED / HPO using LOCAL MRCONSO (2026AA) + hp.obo. No DDXPlus access.
Attribute-type facts (temporal/trigger/relief/criteria/differentiating/red_flag) are NOT forced into a CUI."""
import pathlib, re, sys, pandas as pd, pyarrow.parquet as pq
OUT = pathlib.Path("exp/step15_v2_blind_profile")
facts = pd.read_csv(OUT/"01_disease_profile_facts.csv", dtype=str, keep_default_na=False)

ATTR_CATS = {"temporal","trigger_relief","diagnostic_criteria","differentiating_feature","red_flag","location","demographic"}
# concept-level synonyms (terminology linking only; no clinical content added)
SYN = {
 "rhinorrhea":["rhinorrhea"],"nasal congestion":["nasal congestion","nasal obstruction"],"facial pain":["facial pain"],
 "headache":["headache"],"post-nasal drip":["postnasal drip"],"sore throat":["sore throat","pharyngitis"],"cough":["cough"],
 "halitosis":["halitosis"],"preceding common cold":["common cold"],"seasonal allergies":["seasonal allergic rhinitis"],
 "tobacco smoke exposure":["exposure to tobacco smoke","passive smoking"],"nasal polyps / structural sinus problem":["nasal polyp"],
 "immunosuppressive drugs / weak immune system":["immunocompromised","immunosuppressive agents"],"viral etiology":["virus diseases"],
 "hyposmia / anosmia":["hyposmia","anosmia"],"endoscopic sign":["mucopurulent nasal discharge"],"ct change":["mucosal thickening of sinus"],
 "facial pain/tenderness":["facial tenderness","facial pain"],"discoloured nasal discharge":["purulent nasal discharge"],"fever":["fever"],
 "toothache":["toothache"],"ear pressure":["ear fullness","aural fullness"],"cough worse at night":["nocturnal cough"],"fatigue / malaise":["fatigue","malaise"],
 "retro-orbital pain":["retro-orbital pain","retroorbital pain"],"sinus tenderness on percussion":["sinus tenderness"],
 "cystic fibrosis / ciliary dysfunction":["cystic fibrosis","ciliary dyskinesia"],"altitude change (flying, scuba)":["barotrauma"],
 "plain x-ray limited":["sinus radiography"],"objective confirmation required":["nasal endoscopy"],"comorbid conditions to assess":["asthma"],
 "nasal polyps presence/absence":["nasal polyp"],"nasal congestion (long-term)":["nasal congestion","nasal obstruction"],"facial pressure":["facial pressure"],
 "decreased sense of smell":["hyposmia","anosmia"],"endoscopy/rhinoscopy sign":["nasal polyp"],"ct sign":["mucosal thickening of sinus"],
 "sinus radiography limited":["sinus radiography"],"additional symptoms":["ear fullness"],"facial discomfort nonspecific":["facial pain"],
 "asthma comorbidity":["asthma"],"inflammatory rather than infectious":["inflammation"],"hyponasal voice with polyps":["hyponasal speech","hyponasality"],
 "thick mucopurulent secretions (without polyps)":["mucopurulent nasal discharge"],"sleep impairment, fatigue, depression":["sleep disturbance","fatigue","depression"],
 "possible fungal/bacterial cause (medlineplus)":["fungal sinusitis"],
 "site":["larynx"],"hoarse voice":["hoarseness"],"voice loss":["aphonia"],"irritating cough":["cough"],"throat clearing":["throat clearing"],
 "children: fever":["fever"],"difficulty breathing (rare)":["dyspnea"],"linked to colds and flu":["common cold","influenza"],
 "hoarseness / husky voice":["hoarseness"],"dry cough":["dry cough"],"voice breaks / aphonia":["aphonia"],"context of urti":["upper respiratory tract infection"],
 "sex/age in ent clinic":[],"seasonality":["winter"],"respiratory viruses":["parainfluenza virus infection","rhinovirus infection"],
 "noninfectious causes":["gastroesophageal reflux disease","vocal abuse"],"laryngeal exam finding":["erythema of vocal cord","laryngeal erythema"],
 "cervical lymphadenopathy":["cervical lymphadenopathy"],"other causes":["gastroesophageal reflux disease"],
 "antibiotics not beneficial":["antibiotics"],"no routine antibiotics":["antibiotics"],
 "viral cause most common":["virus diseases"],"odynophagia":["odynophagia"],"dry scratchy throat":["throat irritation"],"runny nose":["rhinorrhea"],
 "hoarseness":["hoarseness"],"conjunctivitis":["conjunctivitis"],"smoking / secondhand smoke (other cause)":["passive smoking"],
 "oral ulcers":["oral ulcer","mouth ulcer"],"viruses in all ages":["virus diseases"],
 "palatal petechiae / tonsillar exudate (strep-typical)":["palatal petechiae","tonsillar exudate"],"scarlatiniform rash (strep-typical)":["scarlatiniform rash"],
 "sudden onset with fever (strep-typical)":["fever"],"discomfort when swallowing":["odynophagia","dysphagia"],"joint pain or muscle aches":["arthralgia","myalgia"],
 "tender swollen cervical lymph nodes":["cervical lymphadenopathy"],"negative strep test":["rapid strep test"],"systemic viral illness":["virus diseases"],
 "chest pain quality":["chest pain"],"chest pain quality (shared)":["chest pain"],"origin behind breastbone":["retrosternal pain"],"origin behind breastbone (shared)":["retrosternal pain"],
 "associated symptoms":["dyspnea","nausea","diaphoresis"],"women: atypical location":[],"sudden pain chest/neck/shoulders/jaw/arms":["chest pain"],
 "quality (nhs)":["chest pain"],"quality (medlineplus)":["chest pain"],"nausea, breathlessness, dizziness, sweating":["nausea","dyspnea","dizziness","diaphoresis"],
 "smoking":["smoking"],"hypertension / hypercholesterolaemia":["hypertension","hypercholesterolemia"],"previous heart problems":["myocardial infarction"],
 "family history of heart problems":["family history of heart disease"],"diabetes / arthritis / kidney disease":["diabetes mellitus","kidney disease"],
 "obesity / alcohol":["obesity","alcohol consumption"],"tests":["electrocardiogram"],"retrosternal / slightly left":["retrosternal pain"],
 "radiation":["radiating chest pain","pain radiating to arm"],"gas/indigestion-like":["indigestion","dyspepsia"],"less common symptoms":["fatigue","dyspnea","palpitations"],
 "family history early chd":["family history of coronary artery disease","family history of ischemic heart disease"],"cad risk factors":["diabetes mellitus","hypertension","obesity","smoking"],
 "intense pain":["chest pain"],"hypotension or dyspnea":["hypotension","dyspnea"],"shortness of breath; sweating":["dyspnea","diaphoresis"],"cardiac troponin":["troponin"],
 "ecg / angiography":["electrocardiogram","coronary angiography"],"exam findings":["heart murmur"],"atherosclerotic cad":["coronary arteriosclerosis","coronary artery disease"],
 "flu-like illness":["influenza-like illness"],"asymptomatic possible":["asymptomatic"],"transmission routes":["sexual transmission","needle sharing"],
 "transmitting fluids":["body fluids"],"factors increasing transmission":["sexually transmitted diseases"],"high viral load / contagious":["viral load"],
 "testing required":["hiv test"],"nonspecific symptoms":[],"chills":["chills"],"rash":["rash","exanthema"],"night sweats":["night sweats"],"muscle aches":["myalgia"],
 "fatigue":["fatigue"],"swollen lymph nodes":["lymphadenopathy"],"mouth ulcers":["oral ulcer","mouth ulcer"],"mucosal exposure predominant":["mucosal exposure"],
 "4th generation ag/ab tests":["hiv antigen-antibody test"],"symptoms vague/nonspecific":[],"share of new diagnoses":[],"infectiousness":["infectivity"],
 "rna detectable ~10 days":["hiv-1 rna"],"p24 antigen timing":["hiv p24 antigen"],"igm timing":["igm"],"nonreactive ag/ab with suspicion":["hiv-1 rna"],
 "ingestion of histamine-rich fish":["histamine"],"implicated fish species":["fish"],"improper refrigeration":["food storage"],"toxin heat-stable":["histamine"],
 "allergic-reaction-like presentation":["allergic reaction"],"gi symptoms":["abdominal cramps","diarrhea"],"blurred vision":["blurred vision"],
 "flushing face/upper body":["flushing"],"severe headache":["headache"],"itching":["pruritus"],"palpitations":["palpitations"],"severe manifestations":["hypotension","cardiac arrhythmia"],
 "taste of contaminated fish":["dysgeusia"],"response to antihistamines":["antihistamines"],"urticaria / wheezing (table)":["urticaria","wheezing"],
 "histamine level in implicated fish":["histamine"],"primary species (fda)":["fish"],"oral tingling/burning":["burning mouth","oral paresthesia"],
 "rash/hives upper body":["urticaria"],"hypotension":["hypotension"],"headache, dizziness, itching":["headache","dizziness","pruritus"],
 "nausea, vomiting, diarrhea":["nausea","vomiting","diarrhea"],"bronchoconstriction / respiratory distress":["bronchospasm","respiratory distress"],
 "flushing without wheals":["flushing"],"metallic dysgeusia":["dysgeusia","metallic taste"],"no fish allergy history":["fish allergy"],
 "wheezing / chest tightness (severe)":["wheezing","chest tightness"],"extremely red skin":["erythema","flushing"],"hives and itching":["urticaria","pruritus"],
 "peppery or bitter taste":["dysgeusia"],"fish species (medlineplus)":["fish"],
 "dyspnea (key symptom)":["dyspnea"],"sputum purulence/volume, cough, wheeze":["purulent sputum","cough","wheezing"],"tachypnea / tachycardia":["tachypnea","tachycardia"],
 "differential diagnoses":["pneumonia","heart failure","pulmonary embolism"],"common viruses":["rhinovirus infection","influenza"],
 "frequent exacerbator phenotype":[],"severity variables":["respiratory rate","oxygen saturation"],"particulate matter":["particulate matter"],
 "commonly reported symptoms (nice)":["dyspnea","cough","sputum"],"medication change":[],"harder time breathing":["dyspnea"],"chest tightness or fever":["chest tightness","fever"],
 "more cough / discoloured phlegm":["purulent sputum","cough"],"underlying copd symptoms":["chronic obstructive pulmonary disease"],"emergency signs":["cyanosis"],
 "poor sleep":["sleep deprivation"],"early signs":["wheezing","dyspnea"],"other signs":["ankle edema","hemoptysis"],"flare-up medicines":["bronchodilator agents","corticosteroids"],
 "sudden fast heartbeat":["tachycardia","palpitations"],"heart rate >100 bpm":["tachycardia"],"chest pain/discomfort":["chest pain"],
 "weak, breathless, lightheaded, dizzy":["dyspnea","lightheadedness","dizziness","weakness"],"tiredness":["fatigue"],"may have no other symptoms":["asymptomatic"],
 "ecg":["electrocardiogram"],"origin in upper chambers":["heart atrium"],"digoxin excess":["digoxin toxicity","digoxin"],"wolff-parkinson-white":["wolff-parkinson-white syndrome"],
 "alcohol, caffeine, stimulants, smoking":["alcohol consumption","caffeine","smoking"],"anxiety; chest tightness; rapid pulse; sob":["anxiety","chest tightness","dyspnea"],
 "dizziness / fainting":["dizziness","syncope"],"rapid heart rate; forceful neck pulses":["tachycardia","jugular venous pulsation"],"heart rate range":["tachycardia"],
 "normal rate between episodes":["normal heart rate"],"ecg during symptoms / holter / eps":["electrocardiogram","holter monitoring"],
 "vagal maneuvers terminate":["valsalva maneuver","vagal maneuver"],"children: very high rate":["tachycardia"],
}

SYN.update({'ct change': ['ct of paranasal sinuses'], 'ct sign': ['ct of paranasal sinuses'], 'imaging not indicated': ['ct of paranasal sinuses'], 'after cold or flu': ['common cold', 'influenza'], 'sinus tenderness on percussion': ['tenderness'], 'plain x-ray limited': ['plain radiography'], 'sinus radiography limited': ['plain radiography'], 'endoscopic signs': ['nasal endoscopy'], 'facial pressure': ['facial pain'], 'additional symptoms': ['cough', 'headache', 'fatigue', 'halitosis'], 'fever suggests acute infection, not crs': ['fever'], 'negative strep test': ['throat culture'], 'poor nitroglycerin response': ['nitroglycerin'], 'mucosal exposure predominant': ['mucous membrane'], '4th generation ag/ab tests': ['hiv antigen test'], 'share of new diagnoses': ['hiv infection'], 'rna detectable ~10 days': ['hiv 1 rna assay'], 'nonreactive ag/ab with suspicion': ['hiv 1 rna assay'], 'frequent exacerbator phenotype': ['chronic obstructive pulmonary disease'], 'ear pressure': ['ear discomfort'], 'seasonality': ['season'], 'endoscopic sign': ['purulent nasal discharge'], 'thick mucopurulent secretions (without polyps)': ['purulent nasal discharge']})
print("loading MRCONSO...", file=sys.stderr)
tbl = pq.read_table("data/umls/mrconso_eng.parquet", columns=["CUI","ISPREF","SAB","TTY","CODE","STR","SUPPRESS"]).to_pandas()
tbl = tbl[tbl.SUPPRESS.isin(["N",""])]
tbl["low"] = tbl.STR.str.lower().str.strip()
needed = set()
for c in facts.base_concept: needed.add(c.lower()); needed.update(SYN.get(c.lower(),[]))
sub = tbl[tbl.low.isin(needed)]
print("hits", len(sub), file=sys.stderr)
pref = tbl[(tbl.ISPREF=="Y")&(tbl.TTY.isin(["PT","PN","PF"]))].drop_duplicates("CUI").set_index("CUI").STR.to_dict()
del tbl

def lookup(term):
    h = sub[sub.low==term.lower()]
    if h.empty: return None
    cuis = sorted(h.CUI.unique()); raw_n = len(cuis)
    if raw_n > 1:
        pri = sorted(h[h.SAB.isin(["SNOMEDCT_US","HPO"])].CUI.unique())
        if len(pri) == 1: cuis = pri
        elif len(pri) > 1:
            pt = sorted(h[(h.SAB=="SNOMEDCT_US")&(h.TTY=="PT")].CUI.unique())
            if len(pt) == 1: cuis = pt
    hh = h[h.CUI.isin(cuis)]
    sno = sorted(hh[hh.SAB=="SNOMEDCT_US"].CODE.unique()); hpo = sorted(hh[hh.SAB=="HPO"].CODE.unique())
    return cuis, sno, hpo, raw_n

rows=[]
for _, f in facts.iterrows():
    bc = f.base_concept; key = bc.lower()
    terms = [key] + [t for t in SYN.get(key,[]) if t != key]
    status="FAIL"; cui=""; pn=""; sno=""; hpo=""; cands=[]; reason=""
    if f.fact_category in ATTR_CATS and not SYN.get(key):
        status="ATTRIBUTE_NOT_MAPPED"; reason="temporal/trigger/relief/criteria/differentiating attribute; not forced into one CUI"
    else:
        found=[]
        for i,t in enumerate(terms):
            r = lookup(t)
            if r: found.append((i,t,r))
        if found:
            i,t,(cuis,s,h,raw_n) = found[0]
            cands = [f"{t2}->{c}" for (_,t2,(cs,_,_,_)) in found for c in cs]
            if len(cuis)==1:
                cui=cuis[0]; status = "EXACT" if i==0 else "PARTIAL"
                reason = "base_concept string exact in MRCONSO" if i==0 else f"mapped via synonym '{t}'"
                if raw_n > 1: reason += f"; {raw_n} raw CUIs share the string, disambiguated by SNOMED/HPO atom"
                if len(found)>1 and any(len(x[2][0])>=1 for x in found[1:]): reason += "; additional component concepts listed in candidates"
            else:
                cui=cuis[0]; status="AMBIGUOUS_MULTI_CUI"; reason=f"{len(cuis)} CUIs share string '{t}'"
            pn = pref.get(cui, ""); sno = ";".join(s); hpo = ";".join(h)
            if f.fact_category in ATTR_CATS: status = "PARTIAL"; reason += "; attribute fact mapped only at base-concept level"
        else:
            reason = "no exact string match in MRCONSO for concept or synonyms"
    review = status in {"AMBIGUOUS_MULTI_CUI","PARTIAL","FAIL"} or ("raw CUIs" in reason)
    rows.append(dict(fact_id=f.fact_id, disease=f.disease, base_concept=bc, umls_cui=cui, umls_preferred_name=pn, snomed_id=sno, hpo_id=hpo,
                     mapping_status=status, mapping_candidates="|".join(cands), mapping_reason=reason, review_needed=review))
df = pd.DataFrame(rows); df.to_csv(OUT/"02_disease_profile_concepts.csv", index=False)
print(df.mapping_status.value_counts().to_string())
print("snomed", (df.snomed_id!="").sum(), "hpo", (df.hpo_id!="").sum())
