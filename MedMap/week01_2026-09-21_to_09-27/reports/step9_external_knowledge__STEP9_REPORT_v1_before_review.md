# STEP 9 (9A~9C) 보고 — 외부 의료지식 매핑·coverage 감사

작성일 2026-09-21. 진단 점수·확률 생성·AUROC 계산은 하지 않았다(중단 조건 준수).

## 1. 무엇을 했는지

- **9A** DDXPlus 49개 질환을 UMLS 2026AA MRCONSO(영어)에서 이름으로 찾고, 그 CUI에 붙은 SNOMED CT·ICD-10·OMIM(숫자 ID만)·Orphanet 코드를 그대로 가져왔다. HPO 질환 ID는 `phenotype.hpoa`에 실제로 존재하는 OMIM/ORPHA만 넣었다. OptimusKG 질환 노드는 CUI → SNOMED → ICD/Orphanet xref → 이름·동의어 순으로 연결했고, 이름으로만 연결된 것은 전부 `review_needed`.
- **9B** 연결된 질환 노드에 대해 OptimusKG `disease_phenotype` edge와 HPO `phenotype.hpoa`에서 실제 질환-소견 관계를 뽑았다. 빈도는 원문(`HP:0040281`, `7/10`, `%`)을 보존하고 min/max로만 변환했다. 빈도가 없으면 `frequency=null`, `relation_present=1`. 임의 확률은 만들지 않았다. NOT 주석은 컬럼으로 보존(이번 데이터엔 0건).
- **9C** Step 8 concept map을 근거로 223개 evidence를 finding 적격/부적격으로 나누고, 질환별로 "DDXPlus 관련 evidence 중 외부 지식에 실제로 존재하는 소견" 비율을 계산했다. 매칭은 HPO ID 정확 일치 + HPO 계층(깊이 3 이하 상위 개념 제외) 일치 두 가지로 따로 셌다.

## 2. 49개 질환 매핑 결과 (`01_disease_concept_map.csv`)

| 상태 | 수 | 예 |
|---|---|---|
| EXACT | 32 | Pericarditis C0031046 / SNOMED 3238004, Myasthenia gravis, SLE, Tuberculosis |
| AMBIGUOUS | 12 | 라벨이 두 개념(`Bronchospasm / acute asthma exacerbation`, `Acute COPD exacerbation / infection`), 영문 라벨≠ICD(`Allergic sinusitis` ↔ J30 allergic rhinitis), 문자열이 복수 CUI(Anaphylaxis·Croup·PSVT·Sarcoidosis), 양성/악성 미구분(`Pulmonary/Pancreatic neoplasm` ↔ C34/C25 악성) |
| PARTIAL | 5 | `HIV (initial infection)`→Acute HIV infection(ICD B20은 전체 HIV), `Possible NSTEMI/STEMI`→Acute MI, `Spontaneous rib fracture`→Rib fracture(spontaneous 손실), `Acute dystonic reactions`, `Localized edema` |
| FAIL | 0 | |

- UMLS CUI 49/49, SNOMED 49/49, OMIM(숫자) 5, Orphanet 7
- **HPO 질환 ID(phenotype.hpoa에 실존) 6/49**: GERD(OMIM:109350), Myasthenia gravis, Chagas, SLE, Ebola, Sarcoidosis
- **OptimusKG 질환 노드 39/49** (CUI 9, SNOMED 16, 이름만 14 → 이름만은 전부 검토 대상)
- review_needed 30/49

**동명이질환·잘못된 subtype 점검(요구 검증 1~4)**
- ❌ `Spontaneous pneumothorax` → OptimusKG `MONDO_0008259 familial spontaneous pneumothorax`(유전형 subtype). 이름 매칭 오류. 후속에서 제외해야 함.
- ⚠ `GERD` → OMIM:109350(유전성 GERD 항목). HPO 주석 5개가 이 OMIM 항목 기준 — 일반 GERD로 쓰기엔 근거 약함.
- ⚠ 상위·인접 개념으로 연결된 것: Acute dystonic reactions→"dystonic disorder", Localized edema→"edema", Panic attack→"panic disorder", Bronchospasm/asthma exacerbation→"asthma", Acute pulmonary edema→"pulmonary edema", Stable angina→"angina pectoris", Acute otitis media→"infectious otitis media". Unstable angina→"intermediate coronary syndrome"는 동의어(정상).
- 흔한 질환이 OMIM 유전질환으로 잘못 연결된 경우: GERD 외 없음(OMIM은 숫자 ID만 남기고 MTHU 보조코드 제거).

## 3. HPO coverage

- HPO 주석이 존재하는 질환 **6/49**. HPO `phenotype.hpoa`는 OMIM/ORPHA/DECIPHER 희귀·유전질환 중심이라 Pneumonia·Influenza·URTI·Bronchitis·Anemia 등 흔한 급성 질환은 항목 자체가 없다(이름 일치 검색 결과 0건).
- edge 264개(빈도 있음 대부분), NOT 주석 0.

## 4. OptimusKG coverage

- 질환 노드는 39/49 연결됐지만 **`disease_phenotype` edge가 있는 것은 7/49**.
- 원인: OptimusKG의 disease-phenotype 관계 157,144개는 **전부 `OPEN_TARGETS/HPO` 출처**다. 즉 OptimusKG 표현형 지식 = HPO 주석의 재배포이며, HPO와 독립적인 지식원이 아니다. Pneumonia(EFO_0003106)·Influenza(EFO_0007328) 같은 노드는 유전자·약물 edge만 있고 표현형 edge가 0개다.
- 결과적으로 HPO ∪ OptimusKG로 소견 지식이 있는 질환은 **10/49**, 완전히 없는 질환 **39/49**.

## 5. 223개 evidence 중 실제 사용 가능한 수 (`03_evidence_eligibility.csv`)

| 구분 | 수 |
|---|---|
| finding 적격(SYMPTOM·SIGN + 자체 HPO 개념을 가진 modifier) | **83** |
| 부적격 → 별도 보존 | 140 (risk/history/context 126, value-level·modifier 14) |
| 적격 중 HPO ID 보유 | 79 (4개는 concept_2에만 HPO) |
| 적격 중 어떤 질환의 외부 소견과라도 실제로 일치 | 21 |
| 너무 상위 개념(HPO 깊이 ≤3) 플래그 | 17 (Pain·Fatigue·Chills·Malaise·Abnormal bleeding·Hoarseness 등) |

Step 8의 temporality/context는 매칭에 사용하지 않았다(HPO ID만 사용). 가족력·약물·노출·생활습관은 전부 부적격 처리했다.

## 6. 질환별 coverage (`04_disease_coverage.csv`)

- 평균 0.076 / 중앙값 0.000 / 최소 0.000 / 최대 1.000 (계층 일치 포함). 정확 ID 일치만: 평균 0.061.
- 0이 아닌 질환 7개뿐:

| 질환 | 적격 finding | HPO 일치 | OKG 일치 | 합집합 | coverage |
|---|---|---|---|---|---|
| Myasthenia gravis | 8 | 8 | 7 | 8 | 1.000 |
| Sarcoidosis | 6 | 4 | 0 | 4 | 0.667 |
| Ebola | 10 | 6 | 0 | 6 | 0.600 |
| Chagas | 8 | 4 | 0 | 4 | 0.500 |
| SLE | 5 | 2 | 0 | 2 | 0.400 |
| Atrial fibrillation | 5 | 0 | 2 | 2 | 0.400 (계층 일치만, 정확 0) |
| GERD | 6 | 1 | 1 | 1 | 0.167 |

## 7. coverage가 낮은 질환

42/49가 coverage 0. 그중 DDXPlus 환자 수가 많은 URTI·Viral pharyngitis·Anemia·Pneumonia·Influenza·Bronchitis·Pulmonary embolism·Anaphylaxis·Panic attack 전부 0. 즉 **지식이 있는 곳은 DDXPlus에서 드문 질환(Ebola 90명, Chagas, SLE, MG)이고, 흔한 질환일수록 지식이 없다.**

## 8. 사람이 확인해야 하는 매핑 (`05_mapping_review_queue.csv`, 69건)

- 질환 30건: AMBIGUOUS 12·PARTIAL 5 전부 + OMIM 붙은 5 + OptimusKG 이름-매칭 14. 우선순위: Spontaneous pneumothorax(오연결), GERD(OMIM 유전형), 양성/악성 neoplasm 2건, 복합 라벨 3건.
- evidence 39건: 적격이면서 (상위 개념 플래그 17 또는 Step 8 상태가 EXACT/COMPOSITE가 아닌 것).

## 9. 다음 실험을 진행해도 되는지

**판정: STEP9_MAPPING_NO_GO** (HPO/OptimusKG를 독립 지식원으로 쓰는 v5 실험 B에 한해)

근거(임의 기준 아님, 실제 수치):
- 질환 ID 매핑 자체는 됐지만(49/49), 질환-소견 **지식이 존재하는 질환이 10/49**, coverage 중앙값 0.
- HPO와 OptimusKG는 같은 출처(HPO 주석)라 "두 지식원"이 아니다 → v5 §10의 "독립 지식원 두 개" 전제가 이 조합으로는 성립하지 않음.
- 지식이 있는 10개는 DDXPlus 내 희귀·저빈도 질환에 치우쳐, 흔한 오답(URTI↔Viral pharyngitis↔Influenza, Bronchitis↔Pneumonia)을 외부 지식으로 판별할 소견이 없다.
- 분석 가능한 subset(MG·Sarcoidosis·Ebola·Chagas·SLE·AF·GERD 7개)은 존재하지만 이것만으로 "working diagnosis 오류 탐지"를 주장하면 rare-disease 편향 결론이 된다 → PARTIAL_GO로 올리지 않음.

바뀌면 재판정: 흔한 급성질환의 질환-증상 관계를 가진 지식원(예: UMLS MRREL의 MEDCIN/NCI 관계, SNOMED `associated finding`, 문헌 기반 HSDN 등)을 추가해 10/49 → 대다수로 올라가면 PARTIAL_GO 이상.

## 생성 파일 (`exp/step9_external_knowledge/`)
`disease_query_table.tsv`(질환 검색어·힌트), `01_disease_concept_map.csv`, `02_external_disease_finding_edges.csv`(341 edge), `03_evidence_eligibility.csv`, `04_disease_coverage.csv`, `04b_coverage_detail.csv`, `05_mapping_review_queue.csv`, `step9_summary.json`, 스크립트 `step9a_disease_map.py`, `step9bc_edges_coverage.py`. 기존 파일 수정 없음.
