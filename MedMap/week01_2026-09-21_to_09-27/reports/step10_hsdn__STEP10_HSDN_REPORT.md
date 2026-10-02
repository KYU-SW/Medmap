# STEP 10 — HSDN 추가 시 외부 질환-증상 지식 coverage 변화 (2026-09-21)

질문 하나: **HSDN을 추가하면 DDXPlus 49질환 × 사용 가능 소견의 외부 지식 coverage가 실제로 충분히 증가하는가?** 진단 성능·확률·AUROC는 계산하지 않았다. Step 8/9 파일 무수정(mtime 검증).

## 판정: **STEP10_HSDN_PARTIAL_GO**

## 1. HSDN 원본
- Zhou, Menche, Barabási, Sharma. Human symptoms–disease network. Nat Commun 5:4212 (2014). DOI 10.1038/ncomms5212. 공식 Supplementary Data 1~4 (media.springernature.com) 직접 다운로드, SHA256 `data/hsdn/raw/SHA256SUMS.txt`. GitHub 재배포본 미사용.
- 라이선스: Open Access 저널이나 CC 문구를 기사 HTML에서 확인 못 함 → **RESEARCH_USE_CHECK_REQUIRED**. 재배포 안 함.
- 구조(실측): MeSH 명칭만 있고 ID 없음 → MRCONSO(SAB=MSH)로 MeSH ID·CUI 부여(질환 4,438/4,442, 증상 322/322). 관계 147,978, 중복 0, 결측 0. 가중치 = PubMed 공출현 수 + TF-IDF. **문헌 기반 관계 강도이며 P(증상|질환) 아님** — `data/hsdn/README.md`에 명시.

## 2. 질환 매핑 (`01_hsdn_disease_map.csv`, 49행, 상태 합 49 검증)
| 상태 | 수 | 내용 |
|---|---|---|
| EXACT | 20 | CUI→MeSH MH 직접 일치 + Step 9 EXACT (Pneumonia, Influenza, Anemia, Tuberculosis, PE, GERD, MG, SLE…) |
| PARTIAL | 5 | 상위 개념으로만 존재: Spontaneous pneumothorax→Pneumothorax, Viral pharyngitis→Pharyngitis, Spontaneous rib fracture→Rib Fractures, Stable angina→Angina Pectoris, Panic attack→Panic Disorder |
| AMBIGUOUS | 13 | Step 9 AMBIGUOUS 승계(복합 라벨·양성/악성) + 상위개념(Acute dystonic→Dystonia, NSTEMI/STEMI→Myocardial Infarction, Acute pulmonary edema→Pulmonary Edema, Allergic sinusitis→Rhinitis) |
| FAIL | 11 | Boerhaave, HIV(initial), Acute laryngitis, PSVT, Scombroid, Localized edema, Acute COPD exacerbation, **URTI, Acute otitis media, Acute/Chronic rhinosinusitis** — HSDN에 해당 MeSH MH가 없거나 급성/부위 한정 개념이 없음. 검토용 상위 후보만 기록(Laryngitis, Otitis Media, HIV Infections 등), 자동 확정 안 함 |

HSDN 증상 edge를 실제 보유한 질환: **38/49** (edge 3,074, 질환당 6~180, 중앙값 80).

## 3. 소견 매핑 (`02_hsdn_finding_map.csv`)
- 적격 finding(03_evidence_eligibility 재계산) **83** → HSDN 증상 연결 EXACT 17 / COMPOSITE 4 / PARTIAL 19 / **FAIL 43**.
- FAIL 원인: HSDN 증상 어휘가 322개(2014 MeSH C23)라 Myalgia·Dysphagia·Hyperhidrosis·Melena·Lymphadenopathy·Anxiety·Ptosis·Sore throat·Nasal congestion·Palpitations·Wheezing·Orthopnea·Pleuritic pain 등이 **어휘 자체에 없음** (CUI→MeSH는 성립하나 HSDN 목록 밖). MeSH 상위어(예: Wheezing→Respiratory Sounds, PND→Dyspnea, Paroxysmal)로 올리면 일부 회수 가능하나 MeSH tree 파일 미보유라 이번엔 미적용.
- Step 9에서 HPO 없음으로 부적격이던 SYMPTOM/SIGN 14건도 HSDN 연결 0.
- 복합 evidence는 concept별로 따로 연결(예: E_39 Confusion/Disorientation → 둘 다 "Confusion"), 가족력·약물·노출·생활습관·인구학·시간조건은 연결 대상에서 제외.

## 4. Coverage 전/후 (`04_coverage_before_after.csv`, Step 9 strict_nonself 정의와 동일 분모)
| 지표 | 전 (HPO+OKG) | 후 (+HSDN) | 후, Pain·Body Weight 제외 |
|---|---|---|---|
| 평균 | 0.052 | **0.457** | 0.364 |
| 중앙값 | 0.000 | **0.500** | 0.400 |
| coverage 0 질환 | 44 | **13** | 14 |
| ≥0.25 | 4 | 36 | 33 |
| ≥0.50 | 3 | 30 | 20 |
| ≥0.75 | 1 | 9 | 5 |
| 사용 가능 질환(매칭≥1) | 5 | 36 | 35 |
(0.25/0.50/0.75는 분포 구간이지 합격선이 아님)

## 5. 흔한 질환 (`05_common_disease_audit.csv`)
개선: Influenza 0→0.545(Fever·Cough·Chills·Fatigue·Loss of appetite), Pneumonia 0→0.500(Fever·Cough·Dyspnea·Hemoptysis·Malaise·Loss of appetite), Bronchitis 0→0.500, Viral pharyngitis 0→0.600, Anemia 0→0.600(Pallor·Dizziness·Fatigue·Dyspnea), PE 0→0.800, Anaphylaxis 0→0.625, Panic attack 0→0.500, Tuberculosis 0→1.000, Bronchiolitis 0→0.500, AF 0→0.400(Dyspnea·Dizziness, 비자기참조), GERD 0→0.667(Heartburn·Cough·Hematemesis).
**여전히 0**: URTI, Acute otitis media, Acute/Chronic rhinosinusitis, Acute laryngitis, HIV(initial), PSVT, Boerhaave, Scombroid, Localized edema, Acute COPD exacerbation, Whooping cough(적격 1개), Laryngospasm(적격 1개).
→ 핵심 오답 쌍 중 **Bronchitis↔Pneumonia·Influenza↔Viral pharyngitis는 지식 생김**, **URTI 축은 여전히 공백**(MeSH "Respiratory Tract Infections"는 너무 넓어 자동 확정 안 함).

## 6. 잘못된 관계 검수 (`06_review_queue.csv`, 1,350건)
| 항목 | 건수 | 비고 |
|---|---|---|
| hsdn_edge: 공출현 1건 | 1,157 (3,074의 38%) | 문헌 1편 근거 관계 — 사용 시 최소 공출현 기준 필요 |
| hsdn_edge: 일반 증상(Pain·Body Weight) | 105 | E_53 "Pain"이 거의 모든 질환과 연결 → 위 표 "제외" 열이 실질값 |
| hsdn_edge: 자기참조 | 0 | 질환명=증상명 없음 |
| disease_map | 29 | 비EXACT 전부 |
| finding_map | 68 | 비EXACT·NAME 매칭·generic |
- 유전형 subtype 유래: HSDN은 문헌 공출현이라 OMIM 유전형 문제는 없음. 대신 Pneumonia edge에 "Anoxia"·"Hyperoxia" 같은 문헌 편향 증상이 상위 가중치로 등장 → 임상 비특이 관계 존재.
- 상위/하위 혼동: PARTIAL 5 + AMBIGUOUS 상위개념 4는 검토 없이 확정 금지.

## 7. 판정 근거
- 지식 보유 질환 5→36, 중앙값 0→0.5, 흔한 급성질환 다수에서 실제 증상 관계가 생겼다 → Step 9 NO_GO의 원인(흔한 질환 공백)이 상당 부분 해소. **GO가 아닌 이유**: (a) 질환 11개 FAIL, 그중 URTI·부비동염·중이염·후두염은 DDXPlus 상위 빈도 호흡기 질환, (b) 적격 소견 83 중 43이 HSDN 어휘 밖이라 소견 측 coverage 상한이 낮음, (c) 관계의 38%가 공출현 1건, "Pain" 일반 증상이 coverage를 부풀림(제외 시 0.457→0.364), (d) 질환 매핑 18건(PARTIAL+AMBIGUOUS)이 사람 검토 전.
- 기존 HPO/OKG 대비 실질 추가 정보: HPO/OKG로 0이던 44질환 중 31질환에 새 관계. 5질환 subset이 36질환 subset으로 확장.

## 8. 검증
- DDXPlus 질환 49 / 매핑 상태 합 49 ✔, Step 8·9 파일 변경 없음 ✔(mtime), 중복 edge 0 ✔, 원본 weight 보존 ✔(max diff 2.8e-14, 공출현 수 동일), "probability" 표기 csv 헤더 없음 ✔, MeSH ID·CUI·매핑 방법(CUI→MeSH / NAME→MeSH) 컬럼 보존 ✔, review_needed 컬럼으로 자동/검토 구분 ✔.
- 행수·SHA256(앞 16자): 01 49행 9d123437c7b39737 · 02 97행 b557744d3e982d11 · 03 3,074행 32974fb095b3997c · 04 49행 9fa55f4574aa7e44 · 04b 301행 49b061e92be119e6 · 05 20행 61bda8aa01bb8317 · 06 1,350행 a5ffd1d28e97e441 · 07 5f29e2b9f0a084eb · processed disease 4,442 / symptom 322 / edges 147,978.
