# PROVENANCE — STEP 15 (2026-09-21)

- git commit (before this step's commit): 4150c5876a5b269101158a0eab0f00e967bdbed5
- Python: Python 3.12.3, pip freeze: docs/environment_ai_env_pip_freeze_2026-09-21.txt
- 실행: raw 수집(curl/PubMed efetch/PMC efetch/WebFetch 발췌 — data/disease_profiles/raw, SHA256SUMS.txt, ACCESS_DATE.txt) → 수기 fact 표(01_disease_profile_facts.tsv→csv) → `s15_concepts_freeze.py` (UMLS 2026AA MRCONSO exact, DDXPlus 미참조) → PROFILE_FREEZE.json → `s15_post_freeze.py`
- UMLS 2026AA MRCONSO(mrconso_eng.parquet) / SNOMED CT 20260901(코드는 MRCONSO 경유) / Step14 value-level map(07) / Step13b 관계행렬(00b)
- 순서 준수: 외부 자료 → fact → freeze(SHA) → DDXPlus 비교. freeze 검증은 s15_post_freeze.py 첫 줄 assert

## 출처 (00_source_registry.csv)
- S01 | MedlinePlus (NLM) | Sinusitis | https://medlineplus.gov/ency/article/000647.htm | access 2026-09-21T11:36Z | USED | PUBLIC_DOMAIN | raw S01.txt 4c33298f668ffb2d
- S02 | CDC | Sinus Infection (Sinusitis) | https://www.cdc.gov/sinus-infection/about/index.html | access 2026-09-21T11:36Z | USED | PUBLIC_DOMAIN | raw S02.txt cb313d0261842633
- S03 | AAO-HNS (PubMed) | Clinical practice guideline (update): adult sinusitis (Rosenfeld 2015) | https://pubmed.ncbi.nlm.nih.gov/25832968/ | access 2026-09-21T11:36Z | USED | COPYRIGHTED_REFERENCE_ONLY | raw S03.txt 6c09c113107a3064
- S04 | StatPearls (NCBI Bookshelf) | Chronic Rhinosinusitis | https://www.ncbi.nlm.nih.gov/books/NBK441934/ | access 2026-09-21T11:36Z | FETCH_FAILED(reCAPTCHA/403/404) | UNKNOWN | raw S04.txt cbe67c025c766161
- S05 | StatPearls (NCBI Bookshelf) | Acute Laryngitis | https://www.ncbi.nlm.nih.gov/books/NBK534871/ | access 2026-09-21T11:36Z | FETCH_FAILED(reCAPTCHA/403/404) | UNKNOWN | raw S05.txt cbe67c025c766161
- S06 | MedlinePlus (NLM) | Laryngitis | https://medlineplus.gov/ency/article/001385.htm | access 2026-09-21T11:36Z | USED | PUBLIC_DOMAIN | raw S06.txt bf624e45d8920d06
- S07 | CDC | Sore Throat | https://www.cdc.gov/sore-throat/about/index.html | access 2026-09-21T11:36Z | USED | PUBLIC_DOMAIN | raw S07.txt 5419a52f0259b55b
- S08 | MedlinePlus (NLM) | Pharyngitis - viral | https://medlineplus.gov/ency/article/001392.htm | access 2026-09-21T11:36Z | USED | PUBLIC_DOMAIN | raw S08.txt cf1b3685afb8aa73
- S09 | IDSA (PubMed) | Clinical practice guideline for GAS pharyngitis (Shulman 2012) | https://pubmed.ncbi.nlm.nih.gov/22965026/ | access 2026-09-21T11:36Z | FETCHED_NOT_USED | COPYRIGHTED_REFERENCE_ONLY | raw S09.txt 2bd02a04f6732e87
- S10 | StatPearls (NCBI Bookshelf) | Stable Angina | https://www.ncbi.nlm.nih.gov/books/NBK559016/ | access 2026-09-21T11:36Z | FETCH_FAILED(reCAPTCHA/403/404) | UNKNOWN | raw S10.txt cbe67c025c766161
- S11 | MedlinePlus (NLM) | Stable angina | https://medlineplus.gov/ency/article/000198.htm | access 2026-09-21T11:36Z | USED | PUBLIC_DOMAIN | raw S11.txt 7817eea3aa9dec2c
- S12 | StatPearls (NCBI Bookshelf) | Unstable Angina | https://www.ncbi.nlm.nih.gov/books/NBK442000/ | access 2026-09-21T11:36Z | FETCH_FAILED(reCAPTCHA/403/404) | UNKNOWN | raw S12.txt cbe67c025c766161
- S13 | MedlinePlus (NLM) | Unstable angina | https://medlineplus.gov/ency/article/000201.htm | access 2026-09-21T11:36Z | USED | PUBLIC_DOMAIN | raw S13.txt 4cee7be0a0f7913e
- S14 | NIH Clinicalinfo | Acute and Recent (Early) HIV Infection (Adult and Adolescent ARV Guidelines) | https://clinicalinfo.hiv.gov/en/guidelines/hiv-clinical-guidelines-adult-and-adolescent-arv/acute-and-recent-early-hiv-infection | access 2026-09-21T11:36Z | FETCH_FAILED(reCAPTCHA/403/404) | UNKNOWN | raw S14.txt 0b5346172e9efa23
- S15 | CDC | Symptoms of HIV | https://www.cdc.gov/hiv/signs-symptoms/index.html | access 2026-09-21T11:36Z | USED | PUBLIC_DOMAIN | raw S15.txt 9616d3f64b279b9e
- S16 | StatPearls (NCBI Bookshelf) | Scombroid Toxicity | https://www.ncbi.nlm.nih.gov/books/NBK537349/ | access 2026-09-21T11:36Z | FETCH_FAILED(reCAPTCHA/403/404) | UNKNOWN | raw S16.txt cbe67c025c766161
- S17 | CDC (Yellow Book) | Food Poisoning from Marine Toxins | https://www.cdc.gov/yellow-book/hcp/environmental-hazards-risks/food-poisoning-from-marine-toxins.html | access 2026-09-21T11:36Z | USED | PUBLIC_DOMAIN | raw S17.txt 5c98a1c58befa145
- S18 | StatPearls (NCBI Bookshelf) | COPD Exacerbation | https://www.ncbi.nlm.nih.gov/books/NBK559281/ | access 2026-09-21T11:36Z | FETCH_FAILED(reCAPTCHA/403/404) | UNKNOWN | raw S18.txt cbe67c025c766161
- S19 | MedlinePlus (NLM) | COPD - flare-up | https://medlineplus.gov/ency/patientinstructions/000698.htm | access 2026-09-21T11:36Z | USED | PUBLIC_DOMAIN | raw S19.txt 6d4579b429001c36
- S20 | StatPearls (NCBI Bookshelf) | Paroxysmal Supraventricular Tachycardia | https://www.ncbi.nlm.nih.gov/books/NBK441972/ | access 2026-09-21T11:36Z | FETCH_FAILED(reCAPTCHA/403/404) | UNKNOWN | raw S20.txt cbe67c025c766161
- S21 | MedlinePlus (NLM) | Paroxysmal supraventricular tachycardia (PSVT) | https://medlineplus.gov/ency/article/000183.htm | access 2026-09-21T11:36Z | USED | PUBLIC_DOMAIN | raw S21.txt 1c97392e070a1427
- S22 | StatPearls (NCBI Bookshelf) | Acute Sinusitis | https://www.ncbi.nlm.nih.gov/books/NBK547701/ | access 2026-09-21T11:36Z | FETCH_FAILED(reCAPTCHA/403/404) | UNKNOWN | raw S22.txt cbe67c025c766161
- S24 | MedlinePlus (NLM) | Poisoning - fish and shellfish | https://medlineplus.gov/ency/article/002851.htm | access 2026-09-21T11:36Z | USED | PUBLIC_DOMAIN | raw S24.txt ac4eb8ad874930b4
- S25 | MedlinePlus (NLM) | Chronic obstructive pulmonary disease (COPD) | https://medlineplus.gov/ency/article/000091.htm | access 2026-09-21T11:36Z | USED | PUBLIC_DOMAIN | raw S25.txt dd996f4827b25a2b
- S29 | NEJM / PMC author manuscript | Acute HIV-1 Infection (Cohen et al. 2011) | https://pmc.ncbi.nlm.nih.gov/articles/PMC3771113/ | access 2026-09-21T11:36Z | USED | OPEN_ACCESS(NIHPA author manuscript) | raw S29_pmc3771113.txt f65353f3855053ad

## 생성 파일 SHA256
- 00_source_registry.csv rows=25 b4e1c8ec23ae7abb0418126983ba903c7ad07bb19e94405fefaf2becf68a8e6f
- 01_disease_profile_facts.csv rows=150 70b7ddfdf71fd200fe8a0d4e567b74fad3feca18bc09fd5e7d04b8138782e994
- 01_disease_profile_facts.tsv rows= 5fbc745fcc4256b5013a5392c193dfbfbb05b27da89ab2dc77d44e2d72617701
- 02_disease_profile_concepts.csv rows=150 ef7f92b6587f05f77e9354864038a9594fed5b9b15b1ef7b8b54ed5b133c4fd3
- 03_profile_quality_audit.csv rows=10 5e841024115a39ab681cb80bb5573b64942f9267da13e7e708be82b389774439
- 04_ddxplus_profile_mapping.csv rows=194 7a5d0a714daad1d82c27172fd7666e8429b5a776eeabd19276d83eb098697311
- 05_disease_profile_coverage.csv rows=10 40bf02a7f8579eec5e4d71f60b458a4ddc3b7f3d2e932fdf8c4bdbffdaa03d55
- 06_pair_discriminative_profile.csv rows=3 4bd0c17752cf618f11a85249795270600152cb5210bf1f179fbdc8696cf9dea4
- 07_before_after_knowledge_coverage.csv rows=10 a7d0fac24c55b4cca7230f827f3b5e0578803eda5d0e3d48a41ae4b145693120
- 08_manual_review_queue.csv rows=85 9fe59db0b780d1e814ecdccd1401470810b25a16b253569009ae1db3453c8ad6
- 09_scaleup_estimate.csv rows=1 e0dc87fb13b320e54d9a291317f130a3d6b7792f9e706565a0f8d1277cdbbd3d
- 10_summary.json rows= 99cafe7a6448cb76b6e63bd970d704bc80ce5a95eb34453c50c9db3f9aea5dc9
- PROFILE_FREEZE.json rows= 517445a401097044fb16e9231245899ceb6749ded5f861639ccaf51f5f5a909c
- s15_concepts_freeze.py rows= 1fa7944f51b42ce3049741e53f2c0cfdc943777a2e145ab6185cb30f8d7eac54
- s15_post_freeze.py rows= 9056d4c2032ec66eaf847c0bd147702f36fcff077421ac6a16c0bd11239700dd