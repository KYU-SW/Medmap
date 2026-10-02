# STEP 9 (9A~9C) 보고 — 외부 의료지식 매핑·coverage 감사 (v2, Reviewer #2 반영)

작성일 2026-09-21. 진단 점수·확률 생성·AUROC 계산은 하지 않았다(중단 조건 준수). v1은 `STEP9_REPORT_v1_before_review.md`로 보존. v1→v2 변경: OptimusKG 오연결(familial pneumothorax) 차단, edge에 `reference_type`·`self_phenotype`·aspect 컬럼 추가, 정확 일치에도 상위개념 게이트를 적용한 `coverage_strict`·자기참조 제외 `coverage_strict_nonself` 추가, SNOMED RF2 관계 실측, v5 §10 인용 정정.

## 1. 무엇을 했는지

- **9A** DDXPlus 49개 질환을 UMLS 2026AA MRCONSO(영어)에서 이름으로 찾고, 그 CUI에 붙은 SNOMED CT·ICD-10·OMIM(숫자 ID만, MTHU 보조코드 제외)·Orphanet 코드를 그대로 가져왔다. HPO 질환 ID는 `phenotype.hpoa`에 실존하는 OMIM/ORPHA만 넣었다. OptimusKG 질환 노드는 CUI → SNOMED → ICD/Orphanet xref → 이름·동의어 순으로 연결했고, 이름으로만 연결된 것은 `okg_link_status=NAME_ONLY_REVIEW`. 유전형 subtype 노드(`MONDO_0008259 familial spontaneous pneumothorax`)는 차단하고 사유를 기록했다.
- **9B** 연결된 질환에 대해 OptimusKG `disease_phenotype` edge와 HPO `phenotype.hpoa`에서 질환-소견 관계를 뽑았다. 빈도는 원문(`HP:0040281`, `7/10`, `%`)을 보존하고 min/max로만 변환, 없으면 `frequency=null`·`relation_present=1`. 임의 확률은 만들지 않았다. NOT 주석 컬럼 보존(0건). 각 edge에 `reference_type`(OMIM / OMIM_familial_or_susceptibility / Orphanet / PMID), `self_phenotype`(외부 finding이 질환 자체와 같은 개념), `is_phenotypic_abnormality`(HPO aspect P) 를 붙였다.
- **9C** Step 8 concept map으로 223개 evidence를 finding 적격/부적격으로 나누고 질환별 coverage를 4가지로 계산했다: 계층 일치 포함(`coverage`), 정확 ID 일치(`coverage_exact_only`), 정확 일치 + 상위개념(HPO 깊이≤3) 제외(`coverage_strict`), 여기에 자기참조·aspect P 아님 제외(`coverage_strict_nonself`). 매칭엔 HPO ID만 쓰고 Step 8의 temporality/context는 쓰지 않았다.

## 2. 49개 질환 매핑 결과 (`01_disease_concept_map.csv`)

| 상태 | 수 | 예 |
|---|---|---|
| EXACT | 32 | Pericarditis C0031046 / SNOMED 3238004, Myasthenia gravis, SLE, Tuberculosis |
| AMBIGUOUS | 12 | 라벨이 두 개념(`Bronchospasm / acute asthma exacerbation`, `Acute COPD exacerbation / infection`), 영문 라벨≠ICD(`Allergic sinusitis` ↔ J30 allergic rhinitis), 문자열이 복수 CUI(Anaphylaxis·Croup·PSVT·Sarcoidosis), 양성/악성 미구분(`Pulmonary/Pancreatic neoplasm` ↔ C34/C25 악성) |
| PARTIAL | 5 | `HIV (initial infection)`→Acute HIV infection(ICD B20은 전체 HIV), `Possible NSTEMI/STEMI`→Acute MI, `Spontaneous rib fracture`→Rib fracture, `Acute dystonic reactions`, `Localized edema` |
| FAIL | 0 | |

- UMLS CUI 49/49, SNOMED 49/49, OMIM 숫자 ID 4(GERD 109350, MG 254200, Allergic sinusitis 607154=susceptibility locus, SLE 152700), Orphanet 7
- **HPO 질환 ID(hpoa 실존) 6/49**: GERD, MG, Chagas, SLE, Ebola, Sarcoidosis
- **OptimusKG 노드 39/49** (CUI 9, SNOMED 16, 이름만 14 → `NAME_ONLY_REVIEW`)
- review_needed 30/49 = 상태≠EXACT 17 + EXACT이면서 OMIM 붙음 3 + EXACT이면서 OptimusKG 노드가 0개 또는 2개 이상 10

**동명이질환·subtype·상위개념 점검(요구 검증 1~4)**
- 차단: `Spontaneous pneumothorax` → `MONDO_0008259 familial spontaneous pneumothorax`(유전형). 차단 후 `MONDO_0002076 pneumothorax`(상위, 이름만)로 재연결.
- 상위·인접 개념 연결(전부 review): Acute dystonic reactions→"dystonic disorder", Localized edema→"edema", Panic attack→"panic disorder", Bronchospasm/asthma exacerbation→"asthma", Acute pulmonary edema→"pulmonary edema", Stable angina→"angina pectoris", Acute otitis media→"infectious otitis media", Viral pharyngitis→"acute pharyngitis; pharyngitis"(바이러스 특정 손실, 2노드), HIV(initial)→"hiv infection", Spontaneous pneumothorax→"pneumothorax". Unstable angina→"intermediate coronary syndrome"은 동의어.
- **흔한 질환이 OMIM 유전 항목으로 연결된 경우**: HPO 직접 경로에서는 GERD(OMIM:109350 "Gastroesophageal reflux", 멘델 항목)뿐이지만, **OptimusKG 경로의 흔한 질환 edge는 전부 OMIM 유전형/감수성 항목에서 온다** (§4 표). 이름이 비슷한 다른 질환으로의 연결은 위 pneumothorax 외 발견되지 않았다.

## 3. HPO coverage

- hpoa 주석이 있는 질환 **6/49**. `phenotype.hpoa`는 OMIM/ORPHA/DECIPHER 희귀·유전질환 중심이라 Pneumonia·Influenza·URTI·Bronchitis·Anemia·Asthma·AF·PE 등은 이름 일치 항목 자체가 없다.
- HPO edge 264 (Orphanet 222, OMIM 42), 빈도 있음 대다수, NOT 0.

## 4. OptimusKG coverage

- 노드 39/49 연결, **`disease_phenotype` edge가 있는 질환 6/49** (차단 전 7). edge 74.
- **OptimusKG의 disease_phenotype 157,144건은 전부 `direct=OPEN_TARGETS, indirect=HPO`** — HPO 주석의 재배포이며 HPO와 독립적인 지식원이 아니다. 따라서 두 결과를 서로 검증하는 데 쓸 수 없다.
- OptimusKG 경로 edge의 출처(질환별):

| 질환 | edge | 출처 항목 | 판정 |
|---|---|---|---|
| Atrial fibrillation | 21 | OMIM:611819 Long QT syndrome 10 / OMIM:613120 Brugada syndrome 7 (PMID 참조) | 유전 채널병증 주석, 일반 AF 아님 |
| Bronchospasm/asthma | 5 | OMIM:600807 "Asthma, susceptibility to" | 감수성 항목 |
| GERD | 5 | OMIM:109350 | 멘델 항목 |
| Pancreatic neoplasm | 5 | OMIM:260350 "Pancreatic cancer"(유전성) | 유전 항목 |
| Myasthenia gravis | 15 | OMIM:254200 | 정상(질환 자체가 OMIM 등재) |
| SLE | 23 | OMIM:152700 + PMID | 정상 |

- 결과: HPO ∪ OptimusKG로 소견 지식이 있는 질환 **9/49**, 없음 **40/49**.

## 5. 223개 evidence 중 실제 사용 가능한 수 (`03_evidence_eligibility.csv`)

| 구분 | 수 |
|---|---|
| finding 적격 | **83** (SYMPTOM·SIGN 69 + 자체 HPO 개념을 가진 modifier 14) |
| 부적격 → 별도 보존 | 140 = risk/history/context 126 + value-level·modifier 14 |
| 적격 중 HPO ID 보유 | 79 |
| 적격 중 어떤 질환의 외부 소견과라도 일치 | 21 |
| 상위 개념(HPO 깊이≤3) 플래그 | 17 / 223, 그중 적격 11 (Pain·Fatigue·Chills·Malaise·Abnormal bleeding·Hoarseness 등) |

주의: "적격 83"은 HPO 기반 지식원을 전제한 수치다. SYMPTOM/SIGN인데 HPO ID가 없어 부적격 처리된 14건(Chest pain at rest, Paroxysmal cough, Expiratory wheeze, Whooping cough, Vaginal discharge, Unintentional weight loss 등)은 SNOMED 코드는 있으므로 SNOMED 기반 지식원이 생기면 적격으로 바뀐다.

## 6. 질환별 coverage (`04_disease_coverage.csv`)

| 기준 | 평균 | 중앙값 | 최대 | 0이 아닌 질환 |
|---|---|---|---|---|
| 계층 일치 포함 (`coverage`) | 0.076 | 0 | 1.0 | 7 |
| 정확 ID 일치 | 0.061 | 0 | 1.0 | 6 |
| 정확 + 상위개념 제외 + 자기참조 제외 (`coverage_strict_nonself`) | **0.052** | 0 | 1.0 | **5** |

| 질환 | 적격 finding | 계층 일치 | 정확 | strict_nonself | 비고 |
|---|---|---|---|---|---|
| Myasthenia gravis | 8 | 8 | 8 | 8 (1.000) | |
| Chagas | 8 | 4 | 4 | 4 (0.500) | |
| Ebola | 10 | 6 | 6 | 5 (0.500) | Fever/Nausea/Diarrhea/Cough/Dyspnea 등 |
| Sarcoidosis | 6 | 4 | 2 | 2 (0.333) | |
| SLE | 5 | 2 | 2 | 1 (0.200) | Fatigue(깊이 3) 제외됨 |
| Atrial fibrillation | 5 | 2 | 0 | **0** | 외부 finding = "Atrial fibrillation/SVT/Atrial flutter" 자기참조 |
| GERD | 6 | 1 | 1 | **0** | Heartburn ↔ HP:0002020 "Gastroesophageal reflux" 자기참조 |

## 7. coverage가 낮은 질환

44/49가 strict_nonself 0. DDXPlus 환자 수 상위인 URTI·Viral pharyngitis·Anemia·HIV·Anaphylaxis·PE·Localized edema·Influenza·Bronchitis·Pneumonia 전부 0. **지식이 있는 5개는 DDXPlus 저빈도 질환(Ebola 90명·Chagas·SLE·MG·Sarcoidosis)** 이고, 흔한 오답 쌍(URTI↔Viral pharyngitis↔Influenza, Bronchitis↔Pneumonia)을 판별할 외부 소견이 없다.

## 8. 사람이 확인해야 하는 매핑 (`05_mapping_review_queue.csv`, 69건)

- 질환 30건(§2 분해). 우선순위: GERD·AF·asthma·Pancreatic neoplasm(OKG edge가 유전형 유래), 양성/악성 neoplasm 2건, 복합 라벨 3건, 상위개념 연결 10건.
- evidence 39건: 적격이면서 상위개념 플래그(11) 또는 Step 8 상태가 EXACT/COMPOSITE가 아닌 것.

## 9. 다음 실험을 진행해도 되는지

**판정: STEP9_MAPPING_NO_GO** — v5 §10 실험 B를 HPO/OptimusKG로 수행하는 것에 한해.

근거(실측):
- v5 §10은 "DDXPlus와 별개의 의료지식" 하나를 요구한다(후보 HPO·UMLS·SNOMED·OptimusKG). 그 후보 중 질환-소견 관계를 실제로 가진 것은 HPO 주석 하나뿐이고, OptimusKG는 같은 주석의 재배포(157,144/157,144)다.
- 그 HPO 주석이 49개 질환 중 **9개**에만 있고, 유전형 유래·자기참조를 걷어내면 **5개**, 전부 DDXPlus 저빈도 질환. coverage 중앙값 0.
- 로컬 SNOMED CT RF2 실측(`06_snomed_relations_touching_diseases.csv`): 49질환 SNOMED ID로 들어오는 활성 관계 166건/22질환은 Due to 92·Associated finding 32·After 23·Associated with 14 — 내용은 "…due to tuberculosis", "Post-myocarditic cardiomyopathy", "Ebola virus disease not suspected" 같은 합병증·병력·situation이며 증상 관계가 아니다. 나가는 관계 106건은 Finding site 53·Associated morphology 40·Causative agent 10·Due to 3로 역시 증상이 아니다. **SNOMED는 구제 경로가 아니다.**
- UMLS는 MRCONSO만 보유, **MRREL 미보유** — MEDCIN/NCI 관계는 현재 검증 불가.
- 5질환 subset으로 실험 B를 돌리면 "희귀·감염질환에서만 검증된 방법"이 되어 v5 §17이 허용하는 주장 범위를 못 채운다 → PARTIAL_GO로 올리지 않는다. 단, 이 5질환은 **알고리즘 동작 확인용 pilot**으로는 쓸 수 있다(성능 주장 금지).

재판정 조건: 흔한 급성질환의 질환-증상 관계를 가진 자원을 새로 확보해 9C를 재계산했을 때 지식 보유 질환이 다수가 되면 PARTIAL_GO 이상. 후보(모두 미보유·미검증): 문헌 기반 HSDN(Zhou 2014), UMLS MRREL(UTS 추가 다운로드), MedlinePlus/Mayo류 증상 텍스트, LLM 생성 지식(단, DDXPlus와의 독립성 입증 필요).

## 생성 파일 (`exp/step9_external_knowledge/`)
`disease_query_table.tsv`, `01_disease_concept_map.csv`, `02_external_disease_finding_edges.csv`(338), `03_evidence_eligibility.csv`, `04_disease_coverage.csv`, `04b_coverage_detail.csv`, `05_mapping_review_queue.csv`, `06_snomed_relations_touching_diseases.csv`, `06b_snomed_outgoing_relations.csv`, `step9_summary.json`, `STEP9_REPORT_v1_before_review.md`, 스크립트 `step9a_disease_map.py`·`step9bc_edges_coverage.py`. Step 8 이전 파일 수정 없음.
