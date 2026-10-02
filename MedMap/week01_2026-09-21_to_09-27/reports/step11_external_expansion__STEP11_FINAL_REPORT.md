# STEP 11 FINAL — UMLS MRREL 추가 후 외부지식 coverage 최종 (2026-09-21)

이전 Step 11 결과는 `exp/step11_external_expansion_before_umls/`에 백업(9파일). Step 8/9/10 무수정. 학습·S2·AUROC 없음.

## 판정: **STEP11_EXTERNAL_PARTIAL_GO** (유지)

## 1. UMLS 확보
- archive `umls-2026AA-metathesaurus-full.zip` 5.82 GB, SHA256 `041cae91…685`, 131 members. **MRREL(6.4 GB, 66,241,184행, 17필드 검증)·MRSTY·MRSAB만 추출**, 전체 해제 안 함 → `data/umls/2026AA/relations/` (README·SHA256SUMS).
- 스트리밍 필터: 49질환 CUI가 CUI1/CUI2인 관계 **112,852행** (`01a`), 그중 evidence CUI(245개)와 닿는 것 4,630행.

## 2. 관계 종류 감사 (`01b_umls_relation_type_audit.csv`)
49질환 주변 RELA 상위: classifies/classified_as 17,050(분류), has_member 6,559, translation 5,994(MedDRA 다국어), isa 4,328, mapped_to 3,402, **clinically_associated_with 2,218(CCPSS)**, associated_with 1,218, **manifestation_of/has_manifestation 718(전부 OMIM)**, co-occurs_with 566(CCPSS), may_treat 507, has_finding_site 480, due_to 276, has_associated_finding 197(SNOMED), ddx 92(CCPSS). `has_sign_or_symptom`/`sign_or_symptom_of`/`has_finding` 계열은 **49질환 주변에 존재하지 않음**.

## 3. 질환↔evidence 직접 관계 (`01_umls_disease_finding_edges.csv`)
양방향 정규화, SUPPRESS≠N 46행 제외 후 **1,480 edge**:
| quality_class | 수 | 내용 |
|---|---|---|
| DIRECT_FINDING | **14** | 전부 OMIM has_manifestation/manifestation_of — MG(Ptosis·Dysphagia·Diplopia·Dysarthria·Facial weakness), SLE(Seizure). **HPO 계보와 동일**(lineage_overlap) |
| POSSIBLE_FINDING | 182 | CCPSS clinically_associated_with·co-occurs_with·ssc (SRL=3) |
| AMBIGUOUS | 84 | BI/SNMI associated_with, MEDLINEPLUS related_to, MTH/AOD RELA 없음 |
| NON_FINDING | 1,200 | isa/PAR/CHD, mapped_to, MedDRA translation(27개 언어 SAB 36행씩), ddx, due_to 등 |
SAB별 계보는 `01c_umls_source_provenance.csv` (OMIM/HPO→CURATED_PHENOTYPE, MSH→LITERATURE 어휘 중복, 나머지 UMLS_<SAB>).

## 4. coverage 최종 (`09_coverage_incremental_final.csv`, 적격 finding 83)
**주의: 이번 strict 정의는 이전 단계보다 엄격**(일반증상·자기참조 제외 + HPO aspect P·비유전형 + HSDN·MEDLINE 공출현 ≥2 + HSDN 질환매핑 EXACT/PARTIAL만 + DisMech PMID 있음 + Wikidata reference 있음 + UMLS DIRECT_FINDING만, 계층 일치 불허). 그래서 Step 10 strict가 이전 보고 0.410이 아니라 0.273으로 표시된다.
| 단계 | 평균 | 중앙값 | strict 평균 | strict 중앙값 | cov 0 | strict 0 | ≥.25/.5/.75 | pair | strict pair | 새 pair | 새로 살아난 질환 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A HPO+OKG | 0.061 | 0 | 0.062 | 0 | 43 | 44 | 5/3/1 | 23 | 20 | | |
| B +HSDN | 0.459 | 0.5 | 0.273 | 0 | 13 | 25 | 36/30/9 | 144 | 68 | +121 | 30 |
| C +DisMech | 0.478 | 0.6 | 0.299 | 0.25 | 13 | 23 | 36/31/9 | 151 | 73 | +7 | 0 |
| D +MEDLINE | 0.478 | 0.6 | 0.342 | 0.4 | 13 | 20 | 36/31/9 | 151 | 82 | 0 (strict +9) | 0 |
| E +Wikidata | 0.486 | 0.6 | 0.348 | 0.4 | 13 | 19 | 36/32/10 | 154 | 83 | +3 | 0 |
| **F +UMLS** | **0.516** | 0.6 | **0.348** | 0.4 | **11** | **19** | 37/33/12 | **165** | **83** | **+11** | **2 (PSVT, URTI)** / strict 0 |

## 5. coverage 0 질환 13개 (`01d_previous_zero_disease_umls_recovery.csv`, 기존 08 파일에서 실제 읽음)
| 질환 | MRREL 주변 관계 | finding edge(품질 불문) | DIRECT | 매칭 | 후 coverage |
|---|---|---|---|---|---|
| URTI | 3,978 | 10 | 0 | Cough·Fever (CCPSS POSSIBLE) | 0.25 (strict 0) |
| PSVT | 872 | 22 | 0 | Palpitations (BI AMBIGUOUS) | 0.167 (strict 0) |
| Laryngospasm | 1,730 | 546(전부 NON_FINDING: 다국어 translation) | 0 | 0 | 0 |
| Whooping cough | 568 | 4 | 0 | 0 | 0 |
| Boerhaave·HIV(initial)·Acute laryngitis·Scombroid·Localized edema·Acute otitis media·COPD exacerbation·Acute/Chronic rhinosinusitis | 144~2,818 | **0** | 0 | 0 | 0 |
→ 13 → **11** (lenient), strict 기준 **변화 없음**. URTI는 CCPSS(1999년 문제목록 어휘, SRL 3) "clinically_associated_with"로만 살아남.

## 6. UMLS가 새로 추가한 pair (기존 5개 지식원 어디에도 없던 것): **11개** (lenient), strict **0**
Anemia–Presyncope·Hematochezia·Melena(CCPSS), Croup–Inspiratory stridor(MTH, RELA 없음), PSVT–Palpitations(BI), AF–Irregular heart beat(BI·MedlinePlus), SLE–Skin lesion(AOD/MTH), URTI–Cough·Fever(CCPSS), Pneumonia–Productive cough·Myalgia(CCPSS). UMLS가 매칭한 pair 41 중 30은 기존 지식원과 중복 확인.

## 7. 다중 출처 지지 재계산 (`13_disease_finding_source_matrix_final.csv`, family: LITERATURE_COOCCURRENCE{HSDN,MEDLINE,UMLS:MSH} / CURATED_PHENOTYPE{HPO,OKG,UMLS:OMIM/HPO} / STRUCTURED_CURATED{DisMech} / COMMUNITY{Wikidata} / UMLS_<SAB>)
- raw_source_support ≥2: 85쌍 → **independent_provenance ≥2: 64쌍**, strict 기준 **24쌍**. (이전 보고 "75"는 HSDN+MEDLINE을 별개로 센 값)

## 8. 검토 필요 (`11_review_queue_final.csv`): 6,362행 / long edge 7,776 (UMLS 1,480 중 DIRECT 14 외 전부 review)

## 9. 판정 근거
1. coverage 0 질환 13→11, 그러나 살아난 URTI·PSVT는 POSSIBLE/AMBIGUOUS 관계뿐이라 strict에선 0 그대로.
2. strict coverage 증가 **0** (0.348→0.348, strict pair 83→83).
3. UMLS DIRECT_FINDING 14건은 전부 OMIM = HPO 계보 → 독립 정보 아님. 실질 신규는 CCPSS(SRL 3 제한 어휘, 1999년) 기반 POSSIBLE 관계.
4. UMLS 매칭 41 pair 중 30(73%)이 기존 지식원 중복 확인.
5. URTI 계열: URTI만 lenient로 생존, 부비동염·중이염·후두염·COPD 악화는 여전히 0.
→ UMLS는 **공백을 실질적으로 메우지 못했고 대부분 중복 확인**. GO 불가. 그러나 Step 10 기반(36질환, strict 20질환 ≥0.5)과 독립 provenance 24~64쌍은 유지되므로 NO_GO 아님 → **PARTIAL_GO**.

## 10. 생성 파일
01_umls_disease_finding_edges.csv(1,480) · 01a(112,852) · 01b(관계 감사) · 01c(provenance) · 01d(13질환 회복표) · 08_coverage_by_source_final.csv(49) · 08b_coverage_detail_final.csv(301) · 09_coverage_incremental_final.csv(6) · 10_previous_failure_recovery_final.csv(13) · 11_review_queue_final.csv(6,362) · 12_all_external_edges_long_final.csv(7,776) · 13_disease_finding_source_matrix_final.csv · STEP11_FINAL_SUMMARY.json · 스크립트 umls_extract_and_filter.py, step11_umls_final.py. `data/umls/2026AA/relations/{MRREL,MRSTY,MRSAB}.RRF + SHA256SUMS.txt + README.md`. 이전 파일 삭제 없음.
