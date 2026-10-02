# PROVENANCE — STEP15 v2 blind disease profile
- timestamp: 2026-09-21T23:16:32 · git commit at build: a3253feac1135048c0afcc150863a2b5c2a93de0
- Python 3.12.3 (~/ai_env) · pip freeze: `exp/step15_v2_blind_profile/pip_freeze_step15v2.txt`
- UMLS: 2026AA MRCONSO (`data/umls/mrconso_eng.parquet`, English, SUPPRESS in N/blank) · SNOMED CT codes via MRCONSO SAB=SNOMEDCT_US (local RF2 `SnomedCT_InternationalRF2_PRODUCTION_20260901T120000Z`) · HPO via MRCONSO SAB=HPO (data-version: hp/releases/2026-09-01)
- Raw sources: `data/disease_profiles_v2/raw/` (V*.html/.pdf/.xml + extracted .txt), per-fetch log `fetch_log.jsonl`, `SHA256SUMS.txt`
- Blind: DDXPlus files / evidence lists / Step8-13-14 outputs / v1 04-08 NOT opened. Disclosure in PROFILE_FREEZE_V2.json.

## Scripts (all in exp/step15_v2_blind_profile/)
| script | role |
|---|---|
| s15v2_fetch.py | curl GET (descriptive UA, no bypass) → raw + text + sha256 + fetch_log |
| s15v2_efetch.py | NCBI E-utilities efetch (pubmed/pmc XML) |
| s15v2_schema.py | Fact dataclass + validators (column placement, time/anatomy regex, quote-in-source, tier match) |
| s15v2_registry.py | source registry (used + blocked) |
| s15v2_facts_part1.py / part2.py | facts as Python objects (never hand-typed TSV) |
| s15v2_build.py | assemble → validate every row → 00/01 CSV → re-read & re-validate |
| s15v2_concepts.py | 02 concept mapping (MRCONSO exact string, SNOMED/HPO-atom disambiguation, attributes not forced) |
| s15v2_postbuild.py | 03 audit, 04 pair differences, 05 review queue, 06 human sheet |
| s15v2_final.py | 07 scaleup, 08 v1-v2 comparison, MANUAL_SOURCE_REQUEST.md, guardian self-check, PROFILE_FREEZE_V2.json |

## Commands
```
cd ~/medmap && source ~/ai_env/bin/activate
python exp/step15_v2_blind_profile/s15v2_fetch.py <Vxx> <url>      # per source
python exp/step15_v2_blind_profile/s15v2_efetch.py <Vxx> pubmed|pmc <id>
python exp/step15_v2_blind_profile/s15v2_build.py
python exp/step15_v2_blind_profile/s15v2_concepts.py
python exp/step15_v2_blind_profile/s15v2_postbuild.py
python exp/step15_v2_blind_profile/s15v2_final.py
```

## Sources used (34) — access date 2026-09-21
| id | disease | organization | tier | url | sha256 |
|---|---|---|---|---|---|
| V41 | Acute rhinosinusitis | CDC | tier1 | https://www.cdc.gov/sinus-infection/about/index.html | 7c1764ced90d3996… |
| V46 | Acute rhinosinusitis;Chronic rhinosinusitis | AAO-HNS Foundation (PubMed abstract) | tier1 | https://pubmed.ncbi.nlm.nih.gov/25832968/ | adf4a761ebac4812… |
| V59 | Acute rhinosinusitis;Chronic rhinosinusitis | European Rhinologic Society (EPOS 2020) | tier1 | https://epos2020.com/Documents/supplement_29.pdf | a4f36cee8bc6d2a8… |
| V55 | Acute rhinosinusitis | NHS (UK) | tier1 | https://www.nhs.uk/conditions/sinusitis-sinus-infection/ | 29b12621d59dced2… |
| V05 | Acute rhinosinusitis;Chronic rhinosinusitis | MedlinePlus (NLM) | tier3 | https://medlineplus.gov/ency/article/000647.htm | e659b5af28b3aa33… |
| V65 | Chronic rhinosinusitis | CMAJ (PMC open access) | tier2 | https://pmc.ncbi.nlm.nih.gov/articles/PMC11835454/ | d212c744171a71db… |
| V08 | Acute laryngitis | NHS (UK) | tier1 | https://www.nhs.uk/conditions/laryngitis/ | f0e69880909b4888… |
| V63 | Acute laryngitis | Mandell, Douglas & Bennett PPID 8e, ch.60 (PMC7152044) | tier3 | https://pmc.ncbi.nlm.nih.gov/articles/PMC7152044/ | e75d3982719580b5… |
| V11 | Acute laryngitis | MedlinePlus (NLM) | tier3 | https://medlineplus.gov/ency/article/001385.htm | 2f991e20cce1de12… |
| V48 | Acute laryngitis | AAO-HNS Foundation (PubMed abstract) | tier1 | https://pubmed.ncbi.nlm.nih.gov/29494321/ | 9136f10fab4e0b65… |
| V12 | Viral pharyngitis | CDC | tier1 | https://www.cdc.gov/sore-throat/about/index.html | 5af0440a1df6eef5… |
| V13 | Viral pharyngitis | CDC | tier1 | https://www.cdc.gov/group-a-strep/hcp/clinical-guidance/strep-throat.html | f8ec5dcf65f52b98… |
| V15 | Viral pharyngitis | MedlinePlus (NLM) | tier3 | https://medlineplus.gov/ency/article/001392.htm | f22cb2bcd21f8013… |
| V58 | Viral pharyngitis | NHS (UK) | tier1 | https://www.nhs.uk/conditions/sore-throat/ | d5cdb5e1c6ab146a… |
| V17 | Stable angina;Unstable angina | NHLBI (NIH) | tier1 | https://www.nhlbi.nih.gov/health/angina/types | 26d774c053469e2e… |
| V18 | Stable angina;Unstable angina | NHLBI (NIH) | tier1 | https://www.nhlbi.nih.gov/health/angina/symptoms | 4371d845ea999e4b… |
| V56 | Stable angina;Unstable angina | NHS (UK) | tier1 | https://www.nhs.uk/conditions/angina/ | e48cb103f0b22b36… |
| V21 | Stable angina | MedlinePlus (NLM) | tier3 | https://medlineplus.gov/ency/article/000198.htm | 4e144123c5718071… |
| V22 | Unstable angina | MedlinePlus (NLM) | tier3 | https://medlineplus.gov/ency/article/000201.htm | 1f783a8fd65d45ac… |
| V43 | Acute HIV infection | CDC | tier1 | https://www.cdc.gov/hiv/about/index.html | ffdf10f21a70cc66… |
| V42 | Acute HIV infection | HIV.gov (HHS) | tier1 | https://www.hiv.gov/hiv-basics/overview/about-hiv-and-aids/symptoms-of-hiv | 614efeb7bde25d37… |
| V53 | Acute HIV infection | NEJM author manuscript (PMC3771113) | tier2 | https://pmc.ncbi.nlm.nih.gov/articles/PMC3771113/ | 0150b03cb6c45735… |
| V66 | Acute HIV infection | CDC / APHL | tier1 | https://stacks.cdc.gov/view/cdc/23447 | 4d46fe45c3977873… |
| V27 | Scombroid poisoning | CDC Yellow Book | tier1 | https://www.cdc.gov/yellow-book/hcp/environmental-hazards-risks/food-poisoning-from-marine-toxins.html | d6ec2f6408a30146… |
| V28 | Scombroid poisoning | US FDA | tier1 | https://www.fda.gov/media/80637/download | 28d166877548f821… |
| V64 | Scombroid poisoning | Am J Trop Med Hyg (PMC9128715) | tier2 | https://pmc.ncbi.nlm.nih.gov/articles/PMC9128715/ | e81221ebf23938cd… |
| V30 | Scombroid poisoning | MedlinePlus (NLM) | tier3 | https://medlineplus.gov/ency/article/002851.htm | caa4db304cb2d30a… |
| V44 | Acute COPD exacerbation | GOLD | tier1 | https://goldcopd.org/wp-content/uploads/2024/11/GOLD-2025-Report-v1.0-15Nov2024_WMV.pdf | a1a47993d068ebb4… |
| V45 | Acute COPD exacerbation | NICE (UK) | tier1 | https://www.nice.org.uk/guidance/ng115/chapter/Recommendations | 93358ecbd2713c82… |
| V31 | Acute COPD exacerbation | NHLBI (NIH) | tier1 | https://www.nhlbi.nih.gov/health/copd/symptoms | 9ca5161678edc410… |
| V35 | Acute COPD exacerbation | MedlinePlus (NLM) | tier3 | https://medlineplus.gov/ency/patientinstructions/000698.htm | 8f5349aee1b3f0e2… |
| V37 | PSVT | NHS (UK) | tier1 | https://www.nhs.uk/conditions/supraventricular-tachycardia-svt/ | 4439f5876455eba2… |
| V40 | PSVT | NHLBI (NIH) | tier1 | https://www.nhlbi.nih.gov/health/arrhythmias/types | a312a880f23c3c94… |
| V38 | PSVT | MedlinePlus (NLM) | tier3 | https://medlineplus.gov/ency/article/000183.htm | e13985da10743b7c… |

## Blocked / unusable (17)
- V03 IDSA (OUP): IDSA clinical practice guideline for acute bacterial rhinosinusitis (Chow 2012) — HTTP_403 — https://academic.oup.com/cid/article/54/8/e72/364306
- V06 StatPearls (NCBI Bookshelf): Chronic Rhinosinusitis — BLOCKED_JS — https://www.ncbi.nlm.nih.gov/books/NBK441934/
- V14 IDSA (OUP): GAS pharyngitis guideline full text (Shulman 2012) — HTTP_403 — https://academic.oup.com/cid/article/55/10/e86/321183
- V19 AHA/ACC (Circulation): 2021 Guideline for the Evaluation and Diagnosis of Chest Pain — HTTP_403 — https://www.ahajournals.org/doi/10.1161/CIR.0000000000001029
- V20 ESC (EHJ): 2019 ESC Guidelines for chronic coronary syndromes — HTTP_403 — https://academic.oup.com/eurheartj/article/41/3/407/5556137
- V24 NIH Clinicalinfo: Acute and Recent (Early) HIV Infection - Adult and Adolescent ARV Guidelines — HTTP_403 — https://clinicalinfo.hiv.gov/en/guidelines/hiv-clinical-guidelines-adult-and-adolescent-arv/acute-and-recent-early-hiv-infection
- V36 ACC/AHA/HRS (Circulation): 2015 ACC/AHA/HRS Guideline for the Management of Adult Patients With SVT — HTTP_403 — https://www.ahajournals.org/doi/10.1161/CIR.0000000000000311
- V39 ESC (EHJ): 2019 ESC Guidelines for the management of patients with SVT — HTTP_403 — https://academic.oup.com/eurheartj/article/41/5/655/5556821
- V49 ACC/AHA/HRS (PubMed): 2015 SVT guideline executive summary - PubMed record — NO_ABSTRACT — https://pubmed.ncbi.nlm.nih.gov/26399662/
- V50 AHA/ACC (PubMed): 2014 AHA/ACC NSTE-ACS guideline - PubMed record — NO_ABSTRACT — https://pubmed.ncbi.nlm.nih.gov/25260718/
- V51 AHA/ACC (PubMed abstract): 2021 Chest Pain guideline abstract — ABSTRACT_NO_CLINICAL_CONTENT — https://pubmed.ncbi.nlm.nih.gov/34709879/
- V47 IDSA (PubMed abstract): GAS pharyngitis guideline abstract (Shulman 2012) — ABSTRACT_NO_CLINICAL_CONTENT — https://pubmed.ncbi.nlm.nih.gov/22965026/
- V52 ERS/ATS (PubMed abstract): Management of COPD exacerbations: ERS/ATS guideline (Wedzicha 2017) — ABSTRACT_NO_CLINICAL_CONTENT — https://pubmed.ncbi.nlm.nih.gov/28298398/
- V60 JACC: 2015 SVT guideline (JACC) — HTTP_403 — https://www.jacc.org/doi/10.1016/j.jacc.2015.08.856
- V61 HRS: 2015 SVT guideline (HRS site) — HTTP_403 — https://www.hrsonline.org/guidance/clinical-resources/2015-accahahrs-guideline-management-adult-patients-supraventricular-tachycardia
- V62 ESC: SVT pocket guidelines 2019 PDF — HTTP_403 — https://www.escardio.org/static-file/Escardio/Guidelines/Documents/Supraventricular-Tachycardia-Pocket-Guidelines-2019.pdf
- V25 PMC (html): Cohen 2011 PMC html (JS-blocked; obtained via E-utilities as V53) — BLOCKED_JS_SUPERSEDED_BY_V53 — https://pmc.ncbi.nlm.nih.gov/articles/PMC3771113/

## File SHA256 (frozen)
- 00_source_registry.csv: 7c451cc0dae2f92d821e1af4f048bea7788d9ea5c93905d83a43c3383a6a9d4d
- 01_disease_profile_facts.csv: 146c5cbf47efb94d2493bcf06e7b4016e304492259d58302782a76da4928935d
- 02_disease_profile_concepts.csv: 896f2140c927ff140d422e1888c8e97d65ff228c82ade2b3172251518b050fc6
- 03_profile_quality_audit.csv: 5abf454656392219f6bec6dce1082bf85036924dea30a8fb1142c259959b58da
- 04_external_pair_differences.csv: de5c46cebd7a295d9b9e2a01bd99ee7d856a301b737b89df6dcbeb2e22a7174e
- 05_manual_review_queue.csv: 352cb48262165c3b70147272c7a3028e810afdf50205f0b07d53272d1694b27f
- 06_HUMAN_REVIEW_SHEET.csv: f2217c94bcfb004b61fc607767b68db18b549405e89db45170258632293ee95b
- 07_scaleup_estimate.csv: 621e07357e8a02ecb73975e4e809966ae62dd95eebd0b54001fb92577e51c28f
- 08_v1_v2_quality_comparison.csv: cdcbf23ce70c280231a2c9792f02577f39b13123479813e11ddc42affd46ee45
