# STEP 11 — 외부 질환-소견 지식원 확장 (UMLS MRREL / DisMech / MEDLINE / Wikidata) 2026-09-21

질문: DDXPlus 49질환 × 비교 가능 evidence(83, 파일에서 재계산)의 외부지식 coverage가 Step 10(HSDN) 대비 얼마나 더 오르는가. 성능·확률·AUROC 계산 없음. Step 8/9/10 파일 무수정.

## 판정: **STEP11_EXTERNAL_PARTIAL_GO** (실질적으로는 "Step 10 PARTIAL_GO 유지, 추가 지식원의 증분은 미미")

## 1. 추가 지식원 확보 결과
| 지식원 | 상태 | 확보 내용 | 라이선스 |
|---|---|---|---|
| UMLS MRREL | **BLOCKED** | Desktop/Downloads에 2026AA full/metathesaurus zip 없음(mrconso.zip만 존재). Desktop에 `미확인 725261.crdownload`(약 25 MB/분으로 증가 중, 15:00 기준 383 MB)가 있어 다운로드 진행 중으로 판단. 선택 추출·CUI 필터 스크립트 `umls_mrrel_extract.py` 준비 완료(전체 해제 안 함) | UTS |
| DisMech | ✅ | github.com/monarch-initiative/dismech shallow clone, commit `eaa5fe99…3282`, kb/disorders yaml 3,052. 질환 연결 17/49(MONDO 2·이름 15), phenotype edge 237(PMID 근거 있음 123, 빈도 있음 171/237) | BSD-3-Clause |
| MEDLINE (hetio) | ✅ | commit `1cd80d12…f04d`, disease-symptom-cooccurrence.tsv 56,658행(DO-slim 135질환 × MeSH 증상), SHA256 기록. 질환 연결 **6/49**(Anemia·SLE EXACT, 나머지 PARTIAL/AMBIGUOUS), edge 2,556 | 저장소 LICENSE 없음 → RESEARCH_USE_CHECK_REQUIRED |
| Wikidata P780 | ✅ (보조) | SPARQL, 49질환 CUI/MeSH/SNOMED로 item 54 → 17질환, edge 91(reference 있음 48 / 없음 43) | CC0 |

각 source의 값(HPO 빈도, HSDN TF-IDF, MEDLINE enrichment, DisMech frequency)은 의미가 달라 합산하지 않고 `12_all_external_edges_long.csv`에 source별 행으로 보존.

## 2. Coverage 증분 (`09_coverage_incremental.csv`, Step 10과 동일 정의: 적격 finding 83 분모)
| 단계 | 평균 | 중앙값 | strict 평균* | strict 중앙값 | coverage 0 질환 | ≥0.5 | 매칭 finding 합 |
|---|---|---|---|---|---|---|---|
| A. HPO+OKG (Step 9) | 0.052 | 0.000 | 0.062 | 0.000 | 44 | 3 | 20 |
| B. +HSDN (Step 10) | 0.457 | 0.500 | 0.410 | 0.455 | 13 | 30 | 143 |
| C. +UMLS MRREL | (BLOCKED, 변화 없음) | | | | 13 | 30 | 143 |
| D. +DisMech | 0.476 | 0.600 | 0.433 | 0.500 | 13 | 31 | 150 |
| E. +MEDLINE | 0.476 | 0.600 | 0.433 | 0.500 | 13 | 31 | 150 |
| F. +Wikidata | **0.484** | **0.600** | **0.442** | 0.500 | **13** | 32 | 153 |
*strict = Step 9의 상위개념 플래그(HPO 깊이≤3: Pain·Fatigue·Chills·Malaise·Abnormal bleeding·Hoarseness 등) 제외. Pain·Body Weight만 제외한 값은 0.411→0.442.

**각 지식원이 Step 10 대비 새로 살린 것**: DisMech finding 7 / 질환 0, MEDLINE finding 0 / 질환 0, Wikidata finding 7 / 질환 0, UMLS 0(BLOCKED). 새로 살아난 질환 **0** — 세 지식원 모두 이미 HSDN이 커버한 질환에만 붙었다.
- DisMech 신규: GBS–Limb weakness, AF–Palpitations, Panic–Palpitations·Anxiety, PE–Pleuritic pain, Influenza–Nasal congestion·Myalgia
- Wikidata 신규: Cluster headache–Nasal congestion, AF–Palpitations, Ebola–Myalgia, Panic–Palpitations, Influenza–Nasal congestion·Myalgia, Pneumonia–Chills
- 이 신규 finding들은 HSDN 어휘 밖(Myalgia·Palpitations·Nasal congestion·Pleuritic pain·Anxiety)이던 것이라 어휘 보완 효과는 실재.

## 3. 이전 실패 질환 (`10_previous_failure_recovery.csv`)
14개 중 **13개 여전히 0**: URTI, Acute otitis media, Acute laryngitis, Acute/Chronic rhinosinusitis, Acute COPD exacerbation, PSVT, Boerhaave, Scombroid, Localized edema, HIV(initial), Whooping cough(적격 1), Laryngospasm(적격 1). Cluster headache만 0.25→0.5(Wikidata Nasal congestion).
원인: DisMech는 희귀·유전질환 중심이라 Pneumonia·Bronchitis·URTI·부비동염·중이염 항목 자체가 없고(아형만: Pneumococcal_Pneumonia 등), MEDLINE은 DO-slim 135질환뿐, Wikidata P780은 흔한 급성 상기도 질환에 증상 statement가 거의 없음.

## 4. 다중 출처 지지 (`13_disease_finding_source_matrix.csv`)
매칭된 (질환, finding) 153쌍 중 **2개 이상 지식원 지지 75**, 3개 이상 18 (예: Influenza–Fever/Chills: HSDN+DisMech+Wikidata, Tuberculosis–Hemoptysis: HSDN+DisMech+Wikidata, MG–Diplopia/Dysarthria: HPO+HSDN+DisMech). 단 HPO와 OptimusKG는 동일 출처라 하나로 셌다.

## 5. 품질 검수 (`11_review_queue.csv`, 4,882행 — long edge 6,296 중)
| 플래그 | 수 |
|---|---|
| 문헌 1건 관계(HSDN 공출현 1·MEDLINE 1) | 2,929 |
| 질환 매핑 AMBIGUOUS / PARTIAL 승계 | 2,698 / 955 |
| 합병증·동반질환 의심(finding명에 neoplasm·syndrome·disease·failure·infarction) | 298 |
| 일반 증상(Pain·Body Weight·Fever 등) | 141 |
| DisMech PMID 근거 없음 | 114 |
| OptimusKG=HPO 재배포(유전형 확인) | 74 |
| Wikidata reference 없음 | 61 |
| 자기참조 | 12 |
DisMech 빈도: FREQUENT 78 / OCCASIONAL 69 / 결측 66 / VERY_FREQUENT 20 / VERY_RARE 3 / OBLIGATE 1 — 결측은 채우지 않음.

## 6. 판정 근거
- strict coverage 실제 증가: 0.410 → 0.442 (+0.032), 매칭 finding 143 → 153 (+10). 증가는 있으나 작다.
- coverage 0 질환: 13 → 13. 흔한 급성질환(URTI 축·중이염·후두염·COPD 악화) **복구 0**.
- 다중 독립 지지 75쌍은 실험 B에서 "신뢰 등급" 축으로 쓸 수 있는 실질 자산.
- 노이즈: long edge의 77%가 검토 플래그(대부분 문헌 1건·매핑 승계). UMLS는 미확보.
→ GO 아님(흔한 질환 공백 미해결·UMLS 미확보), NO_GO 아님(Step 10 기반은 유지되고 어휘 보완·다중지지 정보가 추가됨) → **PARTIAL_GO**.

## 7. 생성 파일 (`exp/step11_external_expansion/`)
01_umls_disease_finding_edges.csv — **미생성(BLOCKED)**, umls_mrrel_extract.py 준비 · 02(49행) · 03(237) · 04(49) · 05(83) · 06(2,556) · 07(91) · 08(49)+08b(301) · 09(6) · 10(14) · 11(4,882) · 12(6,296) · 13(153) · summary.json · step11_expand.py. 데이터: data/dismech(README, clone), data/medline_disease_symptom(README, raw+PROVENANCE+SHA256), data/wikidata(README, raw). SHA256 앞 16자는 summary 보고 시 출력 참조.

## 8. 검증
DDXPlus 49 ✔ · 각 map 상태 합 49 ✔(DisMech FAIL32/PARTIAL13/AMB4, MEDLINE FAIL43/AMB3/EXACT2/PARTIAL1) · Step 8/9/10 무수정 ✔ · 원본 가중치(HSDN tfidf·MEDLINE enrichment·DisMech frequency) 원값 보존, "probability" 표기 없음 ✔ · source/reference/mapping_status 컬럼 유지 ✔.
