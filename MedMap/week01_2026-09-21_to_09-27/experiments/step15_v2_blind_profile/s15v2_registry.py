"""Source registry for STEP15 v2 (external sources only). Metadata joined with raw/fetch_log.jsonl."""
import json, pathlib, datetime
RAW = pathlib.Path("data/disease_profiles_v2/raw")
ACCESS_DATE = "2026-09-21"

# (source_id, disease, organization, title, url, doi, pmid, year, last_updated, source_type, tier, license, independence_note)
SOURCES = [
 ("V41","Acute rhinosinusitis","CDC","Sinus Infection Basics","https://www.cdc.gov/sinus-infection/about/index.html","","","2024","2024-04-17","government_health_page","tier1","US public domain",""),
 ("V46","Acute rhinosinusitis;Chronic rhinosinusitis","AAO-HNS Foundation (PubMed abstract)","Clinical practice guideline (update): adult sinusitis","https://pubmed.ncbi.nlm.nih.gov/25832968/","10.1177/0194599815572097","25832968","2015","","society_guideline_abstract","tier1","abstract via NCBI E-utilities","abstract only; full text not accessed"),
 ("V59","Acute rhinosinusitis;Chronic rhinosinusitis","European Rhinologic Society (EPOS 2020)","European Position Paper on Rhinosinusitis and Nasal Polyps 2020 (Rhinology Suppl 29)","https://epos2020.com/Documents/supplement_29.pdf","10.4193/Rhin20.600","32077450","2020","","international_position_paper","tier1","publisher PDF, free access",""),
 ("V55","Acute rhinosinusitis","NHS (UK)","Sinusitis (sinus infection)","https://www.nhs.uk/conditions/sinusitis-sinus-infection/","","","2024","2024-01-31","government_health_page","tier1","OGL/NHS",""),
 ("V05","Acute rhinosinusitis;Chronic rhinosinusitis","MedlinePlus (NLM)","Sinusitis","https://medlineplus.gov/ency/article/000647.htm","","","","","medlineplus_encyclopedia","tier3","A.D.A.M. licensed content",""),
 ("V65","Chronic rhinosinusitis","CMAJ (PMC open access)","Diagnosis and management of chronic rhinosinusitis","https://pmc.ncbi.nlm.nih.gov/articles/PMC11835454/","10.1503/cmaj.240842","","2025","","peer_reviewed_review","tier2","CC BY-NC-ND (PMC OA)",""),
 ("V08","Acute laryngitis","NHS (UK)","Laryngitis","https://www.nhs.uk/conditions/laryngitis/","","","","","government_health_page","tier1","OGL/NHS",""),
 ("V63","Acute laryngitis","Mandell, Douglas & Bennett PPID 8e, ch.60 (PMC7152044)","Acute Laryngitis","https://pmc.ncbi.nlm.nih.gov/articles/PMC7152044/","10.1016/B978-1-4557-4801-3.00060-3","","2015","","textbook_chapter_pmc","tier3","Elsevier PMC COVID collection","textbook chapter, not peer-reviewed journal"),
 ("V11","Acute laryngitis","MedlinePlus (NLM)","Laryngitis","https://medlineplus.gov/ency/article/001385.htm","","","2024","2024-10-09","medlineplus_encyclopedia","tier3","A.D.A.M. licensed content",""),
 ("V48","Acute laryngitis","AAO-HNS Foundation (PubMed abstract)","Clinical Practice Guideline: Hoarseness (Dysphonia) (Update)","https://pubmed.ncbi.nlm.nih.gov/29494321/","10.1177/0194599817751030","29494321","2018","","society_guideline_abstract","tier1","abstract via NCBI E-utilities","abstract only"),
 ("V12","Viral pharyngitis","CDC","Sore Throat Basics","https://www.cdc.gov/sore-throat/about/index.html","","","2024","2024-04-17","government_health_page","tier1","US public domain",""),
 ("V13","Viral pharyngitis","CDC","Clinical Guidance for Group A Streptococcal Pharyngitis","https://www.cdc.gov/group-a-strep/hcp/clinical-guidance/strep-throat.html","","","2025","2025-11-18","government_clinical_guidance","tier1","US public domain","same organization as V12"),
 ("V15","Viral pharyngitis","MedlinePlus (NLM)","Pharyngitis - viral","https://medlineplus.gov/ency/article/001392.htm","","","2026","2026-01-14","medlineplus_encyclopedia","tier3","A.D.A.M. licensed content",""),
 ("V58","Viral pharyngitis","NHS (UK)","Sore throat","https://www.nhs.uk/conditions/sore-throat/","","","","","government_health_page","tier1","OGL/NHS",""),
 ("V17","Stable angina;Unstable angina","NHLBI (NIH)","Angina (Chest Pain) - Types","https://www.nhlbi.nih.gov/health/angina/types","","","2023","2023-07-10","government_health_page","tier1","US public domain",""),
 ("V18","Stable angina;Unstable angina","NHLBI (NIH)","Angina (Chest Pain) - Symptoms","https://www.nhlbi.nih.gov/health/angina/symptoms","","","2023","2023-07-10","government_health_page","tier1","US public domain","same organization as V17"),
 ("V56","Stable angina;Unstable angina","NHS (UK)","Angina","https://www.nhs.uk/conditions/angina/","","","","","government_health_page","tier1","OGL/NHS",""),
 ("V21","Stable angina","MedlinePlus (NLM)","Stable angina","https://medlineplus.gov/ency/article/000198.htm","","","","","medlineplus_encyclopedia","tier3","A.D.A.M. licensed content",""),
 ("V22","Unstable angina","MedlinePlus (NLM)","Unstable angina","https://medlineplus.gov/ency/article/000201.htm","","","","","medlineplus_encyclopedia","tier3","A.D.A.M. licensed content",""),
 ("V43","Acute HIV infection","CDC","About HIV","https://www.cdc.gov/hiv/about/index.html","","","2025","2025-01-14","government_health_page","tier1","US public domain",""),
 ("V42","Acute HIV infection","HIV.gov (HHS)","Symptoms of HIV","https://www.hiv.gov/hiv-basics/overview/about-hiv-and-aids/symptoms-of-hiv","","","","","government_health_page","tier1","US public domain","page cites CDC as source -> NOT independent of V43"),
 ("V53","Acute HIV infection","NEJM author manuscript (PMC3771113)","Acute HIV-1 Infection (Cohen, Shaw, McMichael, Haynes)","https://pmc.ncbi.nlm.nih.gov/articles/PMC3771113/","10.1056/NEJMra1011874","21591946","2011","","peer_reviewed_review","tier2","NIH public access manuscript",""),
 ("V66","Acute HIV infection","CDC / APHL","Laboratory Testing for the Diagnosis of HIV Infection: Updated Recommendations","https://stacks.cdc.gov/view/cdc/23447","10.15620/cdc.23447","","2014","2014-06-27","government_guideline_pdf","tier1","US public domain",""),
 ("V27","Scombroid poisoning","CDC Yellow Book","Food Poisoning from Marine Toxins","https://www.cdc.gov/yellow-book/hcp/environmental-hazards-risks/food-poisoning-from-marine-toxins.html","","","2025","2025-04-23","government_clinical_guidance","tier1","US public domain",""),
 ("V28","Scombroid poisoning","US FDA","Fish and Fishery Products Hazards and Controls Guidance (4th ed.), Chapter 7 Scombrotoxin (Histamine) Formation","https://www.fda.gov/media/80637/download","","","2022","","government_guidance_pdf","tier1","US public domain",""),
 ("V64","Scombroid poisoning","Am J Trop Med Hyg (PMC9128715)","Scombroid Fish Poisoning (Images in Clinical Tropical Medicine)","https://pmc.ncbi.nlm.nih.gov/articles/PMC9128715/","10.4269/ajtmh.21-1345","35313278","2022","","peer_reviewed_case_image","tier2","CC BY 4.0","short case-based article"),
 ("V30","Scombroid poisoning","MedlinePlus (NLM)","Poisoning - fish and shellfish","https://medlineplus.gov/ency/article/002851.htm","","","","","medlineplus_encyclopedia","tier3","A.D.A.M. licensed content",""),
 ("V44","Acute COPD exacerbation","GOLD","Global Strategy for Prevention, Diagnosis and Management of COPD: 2025 Report","https://goldcopd.org/wp-content/uploads/2024/11/GOLD-2025-Report-v1.0-15Nov2024_WMV.pdf","","","2024","2024-11-15","international_guideline_pdf","tier1","copyright GOLD; personal use, short quotes only",""),
 ("V45","Acute COPD exacerbation","NICE (UK)","COPD in over 16s: diagnosis and management (NG115) - Recommendations","https://www.nice.org.uk/guidance/ng115/chapter/Recommendations","","","2019","","government_guideline","tier1","NICE copyright; short quotes",""),
 ("V31","Acute COPD exacerbation","NHLBI (NIH)","COPD - Symptoms","https://www.nhlbi.nih.gov/health/copd/symptoms","","","2024","2024-10-04","government_health_page","tier1","US public domain",""),
 ("V35","Acute COPD exacerbation","MedlinePlus (NLM)","COPD flare-ups","https://medlineplus.gov/ency/patientinstructions/000698.htm","","","","","medlineplus_encyclopedia","tier3","A.D.A.M. licensed content",""),
 ("V37","PSVT","NHS (UK)","Supraventricular tachycardia (SVT)","https://www.nhs.uk/conditions/supraventricular-tachycardia-svt/","","","2024","2024-06-12","government_health_page","tier1","OGL/NHS",""),
 ("V40","PSVT","NHLBI (NIH)","Arrhythmias - Types","https://www.nhlbi.nih.gov/health/arrhythmias/types","","","2022","2022-03-24","government_health_page","tier1","US public domain",""),
 ("V38","PSVT","MedlinePlus (NLM)","Paroxysmal supraventricular tachycardia (PSVT)","https://medlineplus.gov/ency/article/000183.htm","","","","","medlineplus_encyclopedia","tier3","A.D.A.M. licensed content",""),
]
# Attempted but blocked / unusable (kept for provenance; no facts drawn)
BLOCKED = [
 ("V03","Acute rhinosinusitis","IDSA (OUP)","IDSA clinical practice guideline for acute bacterial rhinosinusitis (Chow 2012)","https://academic.oup.com/cid/article/54/8/e72/364306","tier1","HTTP_403"),
 ("V06","Chronic rhinosinusitis","StatPearls (NCBI Bookshelf)","Chronic Rhinosinusitis","https://www.ncbi.nlm.nih.gov/books/NBK441934/","tier3","BLOCKED_JS"),
 ("V14","Viral pharyngitis","IDSA (OUP)","GAS pharyngitis guideline full text (Shulman 2012)","https://academic.oup.com/cid/article/55/10/e86/321183","tier1","HTTP_403"),
 ("V19","Stable angina;Unstable angina","AHA/ACC (Circulation)","2021 Guideline for the Evaluation and Diagnosis of Chest Pain","https://www.ahajournals.org/doi/10.1161/CIR.0000000000001029","tier1","HTTP_403"),
 ("V20","Stable angina","ESC (EHJ)","2019 ESC Guidelines for chronic coronary syndromes","https://academic.oup.com/eurheartj/article/41/3/407/5556137","tier1","HTTP_403"),
 ("V24","Acute HIV infection","NIH Clinicalinfo","Acute and Recent (Early) HIV Infection - Adult and Adolescent ARV Guidelines","https://clinicalinfo.hiv.gov/en/guidelines/hiv-clinical-guidelines-adult-and-adolescent-arv/acute-and-recent-early-hiv-infection","tier1","HTTP_403"),
 ("V36","PSVT","ACC/AHA/HRS (Circulation)","2015 ACC/AHA/HRS Guideline for the Management of Adult Patients With SVT","https://www.ahajournals.org/doi/10.1161/CIR.0000000000000311","tier1","HTTP_403"),
 ("V39","PSVT","ESC (EHJ)","2019 ESC Guidelines for the management of patients with SVT","https://academic.oup.com/eurheartj/article/41/5/655/5556821","tier1","HTTP_403"),
 ("V49","PSVT","ACC/AHA/HRS (PubMed)","2015 SVT guideline executive summary - PubMed record","https://pubmed.ncbi.nlm.nih.gov/26399662/","tier1","NO_ABSTRACT"),
 ("V50","Unstable angina","AHA/ACC (PubMed)","2014 AHA/ACC NSTE-ACS guideline - PubMed record","https://pubmed.ncbi.nlm.nih.gov/25260718/","tier1","NO_ABSTRACT"),
 ("V51","Stable angina;Unstable angina","AHA/ACC (PubMed abstract)","2021 Chest Pain guideline abstract","https://pubmed.ncbi.nlm.nih.gov/34709879/","tier1","ABSTRACT_NO_CLINICAL_CONTENT"),
 ("V47","Viral pharyngitis","IDSA (PubMed abstract)","GAS pharyngitis guideline abstract (Shulman 2012)","https://pubmed.ncbi.nlm.nih.gov/22965026/","tier1","ABSTRACT_NO_CLINICAL_CONTENT"),
 ("V52","Acute COPD exacerbation","ERS/ATS (PubMed abstract)","Management of COPD exacerbations: ERS/ATS guideline (Wedzicha 2017)","https://pubmed.ncbi.nlm.nih.gov/28298398/","tier1","ABSTRACT_NO_CLINICAL_CONTENT"),
 ("V60","PSVT","JACC","2015 SVT guideline (JACC)","https://www.jacc.org/doi/10.1016/j.jacc.2015.08.856","tier1","HTTP_403"),
 ("V61","PSVT","HRS","2015 SVT guideline (HRS site)","https://www.hrsonline.org/guidance/clinical-resources/2015-accahahrs-guideline-management-adult-patients-supraventricular-tachycardia","tier1","HTTP_403"),
 ("V62","PSVT","ESC","SVT pocket guidelines 2019 PDF","https://www.escardio.org/static-file/Escardio/Guidelines/Documents/Supraventricular-Tachycardia-Pocket-Guidelines-2019.pdf","tier1","HTTP_403"),
 ("V25","Acute HIV infection","PMC (html)","Cohen 2011 PMC html (JS-blocked; obtained via E-utilities as V53)","https://pmc.ncbi.nlm.nih.gov/articles/PMC3771113/","tier2","BLOCKED_JS_SUPERSEDED_BY_V53"),
]

def load_log():
    log = {}
    for line in (RAW/"fetch_log.jsonl").read_text().splitlines():
        r = json.loads(line); log[r["source_id"]] = r   # last record wins
    return log

def registry_rows():
    log = load_log(); rows = []
    for (sid,dis,org,title,url,doi,pmid,year,upd,stype,tier,lic,note) in SOURCES:
        r = log[sid]; assert r["status"]=="OK", (sid, r["status"])
        rows.append(dict(source_id=sid,disease=dis,organization=org,title=title,url=url,doi=doi,pmid=pmid,
            publication_year=year,last_updated=upd,access_date=ACCESS_DATE,access_time=r["access_time"],
            source_type=stype,source_tier=tier,license_status=lic,local_file="data/disease_profiles_v2/raw/"+r["local_file"],
            sha256=r["sha256"],fetch_method=r.get("fetch_method","curl"),status="OK",independence_note=note))
    for (sid,dis,org,title,url,tier,st) in BLOCKED:
        r = log.get(sid,{})
        rows.append(dict(source_id=sid,disease=dis,organization=org,title=title,url=url,doi="",pmid="",publication_year="",
            last_updated="",access_date=ACCESS_DATE,access_time=r.get("access_time",""),source_type="blocked_or_unusable",
            source_tier=tier,license_status="",local_file="data/disease_profiles_v2/raw/"+r.get("local_file","") if r else "",
            sha256=r.get("sha256",""),fetch_method=r.get("fetch_method","curl"),status=st,independence_note="no facts drawn"))
    return rows
