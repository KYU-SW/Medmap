# EXP-01b 38회차 판별 근거 — 가상 사례 실행(구조 시험, 실제 환자·성능 아님)

> 관계표 = discriminator_relations.csv · 집계 = summary.json. 진료지침 원문은 로컬에 없어 DisMech·캐시 초록/본문만 사용.

# V1 흉통+앞으로 숙이면 완화, 현재 진단 심근염 → 검사 결과(마찰음·ST 상승) 추가

## 1단계
- 그래프: REAL_KG_v1(HSDN+DisMech+HPO) · 기준 시점 as_of=1.0
- 정렬 = 임상 소견 근거 묶음 수 → 전체 묶음 수(공출현만 있는 묶음은 둘째 기준). 확률·진단 확정 아님. 모든 질환 노드 유지(제거 없음).

| 순위 | 질환 | 독립 지지 묶음 | 임상 소견 묶음 | 공출현만 묶음 | 지지 근거(묶음:최고 등급) | 충돌 | 음성/불충족 | 판단 보류 | 비활성 | 독립성 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 심낭염(Pericarditis)[DX:Pericarditis] | 3 | 3 | 0 | {CONCEPT:chest_pain_relieved_sitting_forward}:DISMECH_NO_REF / {HP:0002094}:DISMECH_NO_REF / {HP:0012531, HP:0100749}:DISMECH_QUOTE_IN_ABSTRACT | 0 | 0 | 16 | 0 | UNVERIFIED |
| 2 | 심근염(Myocarditis)[DX:Myocarditis] | 2 | 2 | 0 | {HP:0002094}:DISMECH_QUOTE_IN_ABSTRACT / {HP:0100749}:DISMECH_QUOTE_IN_ABSTRACT | 0 | 0 | 21 | 0 | UNVERIFIED |
| 3 | 결핵(Tuberculosis)[DX:Tuberculosis] | 2 | 2 | 0 | {HP:0002094}:DISMECH_QUOTE_IN_ABSTRACT / {HP:0100749}:DISMECH_QUOTE_IN_ABSTRACT | 0 | 0 | 19 | 0 | UNVERIFIED |
| 4 | 폐색전증(Pulmonary embolism)[DX:Pulmonary embolism] | 2 | 1 | 1 | {HP:0002094}:DISMECH_QUOTE_IN_ABSTRACT / {HP:0012531, HP:0100749}:HSDN_LITERATURE_COOCCURRENCE | 0 | 0 | 29 | 0 | UNVERIFIED |

### 경로별 근거 추적
- **심낭염(Pericarditis)[DX:Pericarditis]**
  - [뒷받침] [DISMECH_QUOTE_IN_ABSTRACT] Chest pain[HP:0100749] -SUGGESTS-> 심낭염(Pericarditis)[DX:Pericarditis] · 조건: 양성 · 근거ID: V1-E_55-chest · 출처: DisMech eaa5fe99 Pericarditis.yaml phenotypes['Pericarditic chest pain'] freq=None supports={'SUPPORT': 1} refs=PMID:38804758 quote_check={'SUPPORT:FOUND': 1} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [뒷받침] [DISMECH_NO_REF] Dyspnea[HP:0002094] -SUGGESTS-> 심낭염(Pericarditis)[DX:Pericarditis] · 조건: 양성 · 근거ID: V1-E_66-0 · 출처: DisMech eaa5fe99 Pericarditis.yaml phenotypes['Dyspnoea'] freq=None supports={} refs=없음 quote_check={} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Pain[HP:0012531] -SUGGESTS-> 심낭염(Pericarditis)[DX:Pericarditis] · 조건: 양성 · 근거ID: V1-E_53-0 · 출처: HSDN Supp Data 3: 'Pain'–'Pericarditis' PubMed co-occurrence=24, TF-IDF=7.91 (문헌 공출현, 확률 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Chest pain[HP:0100749] -SUGGESTS-> 심낭염(Pericarditis)[DX:Pericarditis] · 조건: 양성 · 근거ID: V1-E_55-chest · 출처: HSDN Supp Data 3: 'Chest Pain'–'Pericarditis' PubMed co-occurrence=74, TF-IDF=81.37 (문헌 공출현, 확률 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Dyspnea[HP:0002094] -SUGGESTS-> 심낭염(Pericarditis)[DX:Pericarditis] · 조건: 양성 · 근거ID: V1-E_66-0 · 출처: HSDN Supp Data 3: 'Dyspnea'–'Pericarditis' PubMed co-occurrence=25, TF-IDF=25.13 (문헌 공출현, 확률 아님)
  - [뒷받침] [DISMECH_NO_REF] 앞으로 숙이면 완화되는 흉통[CONCEPT:chest_pain_relieved_sitting_forward] -SUGGESTS-> 심낭염(Pericarditis)[DX:Pericarditis] · 조건: 양성 · 근거ID: V1-E_33-pos · 출처: DisMech eaa5fe99 Pericarditis.yaml phenotypes['Pericarditic chest pain'].description · quote_check=NO_QUOTE · 조건: 흉통이 있을 때(흉통 복합 + E_33) · 제한: AI 큐레이션 설명 문장, 직접 인용 근거 없음 — 등급 DISMECH_NO_REF
  - [판단 보류 경로 16개 생략 — 근거 미기록·미검사·불확실]
- **심근염(Myocarditis)[DX:Myocarditis]**
  - [뒷받침] [DISMECH_QUOTE_IN_ABSTRACT] Chest pain[HP:0100749] -SUGGESTS-> 심근염(Myocarditis)[DX:Myocarditis] · 조건: 양성 · 근거ID: V1-E_55-chest · 출처: DisMech eaa5fe99 Myocarditis.yaml phenotypes['Chest Pain'] freq=FREQUENT supports={'SUPPORT': 1} refs=PMID:35533750 quote_check={'SUPPORT:FOUND': 1} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [뒷받침] [DISMECH_QUOTE_IN_ABSTRACT] Dyspnea[HP:0002094] -SUGGESTS-> 심근염(Myocarditis)[DX:Myocarditis] · 조건: 양성 · 근거ID: V1-E_66-0 · 출처: DisMech eaa5fe99 Myocarditis.yaml phenotypes['Dyspnea'] freq=FREQUENT supports={'SUPPORT': 1} refs=PMID:29096807 quote_check={'SUPPORT:FOUND': 1} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Chest pain[HP:0100749] -SUGGESTS-> 심근염(Myocarditis)[DX:Myocarditis] · 조건: 양성 · 근거ID: V1-E_55-chest · 출처: HSDN Supp Data 3: 'Chest Pain'–'Myocarditis' PubMed co-occurrence=52, TF-IDF=57.18 (문헌 공출현, 확률 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Dyspnea[HP:0002094] -SUGGESTS-> 심근염(Myocarditis)[DX:Myocarditis] · 조건: 양성 · 근거ID: V1-E_66-0 · 출처: HSDN Supp Data 3: 'Dyspnea'–'Myocarditis' PubMed co-occurrence=23, TF-IDF=23.12 (문헌 공출현, 확률 아님)
  - [판단 보류 경로 21개 생략 — 근거 미기록·미검사·불확실]
- **결핵(Tuberculosis)[DX:Tuberculosis]**
  - [뒷받침] [DISMECH_QUOTE_IN_ABSTRACT] Chest pain[HP:0100749] -SUGGESTS-> 결핵(Tuberculosis)[DX:Tuberculosis] · 조건: 양성 · 근거ID: V1-E_55-chest · 출처: DisMech eaa5fe99 Tuberculosis.yaml phenotypes['Chest Pain'] freq=FREQUENT supports={'NO_EVIDENCE': 1, 'SUPPORT': 2} refs=PMID:17508531,PMID:27499981,PMID:30762202 quote_check={'SUPPORT:FOUND': 2, 'NO_EVIDENCE:FOUND': 1} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [뒷받침] [DISMECH_QUOTE_IN_ABSTRACT] Dyspnea[HP:0002094] -SUGGESTS-> 결핵(Tuberculosis)[DX:Tuberculosis] · 조건: 양성 · 근거ID: V1-E_66-0 · 출처: DisMech eaa5fe99 Tuberculosis.yaml phenotypes['Dyspnea'] freq=OCCASIONAL supports={'NO_EVIDENCE': 1, 'SUPPORT': 1} refs=PMID:15623010,PMID:29900887 quote_check={'NO_EVIDENCE:FOUND': 1, 'SUPPORT:FOUND': 1} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [판단 보류 경로 19개 생략 — 근거 미기록·미검사·불확실]
- **폐색전증(Pulmonary embolism)[DX:Pulmonary embolism]**
  - [뒷받침] [DISMECH_QUOTE_IN_ABSTRACT] Dyspnea[HP:0002094] -SUGGESTS-> 폐색전증(Pulmonary embolism)[DX:Pulmonary embolism] · 조건: 양성 · 근거ID: V1-E_66-0 · 출처: DisMech eaa5fe99 Pulmonary_Embolism.yaml phenotypes['Dyspnoea/Post-pulmonary embolism syndrome'] freq=None supports={'SUPPORT': 4} refs=PMID:17904458,PMID:41765088 quote_check={'SUPPORT:FOUND': 4} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Pain[HP:0012531] -SUGGESTS-> 폐색전증(Pulmonary embolism)[DX:Pulmonary embolism] · 조건: 양성 · 근거ID: V1-E_53-0 · 출처: HSDN Supp Data 3: 'Pain'–'Pulmonary Embolism' PubMed co-occurrence=41, TF-IDF=13.50 (문헌 공출현, 확률 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Chest pain[HP:0100749] -SUGGESTS-> 폐색전증(Pulmonary embolism)[DX:Pulmonary embolism] · 조건: 양성 · 근거ID: V1-E_55-chest · 출처: HSDN Supp Data 3: 'Chest Pain'–'Pulmonary Embolism' PubMed co-occurrence=138, TF-IDF=151.74 (문헌 공출현, 확률 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Dyspnea[HP:0002094] -SUGGESTS-> 폐색전증(Pulmonary embolism)[DX:Pulmonary embolism] · 조건: 양성 · 근거ID: V1-E_66-0 · 출처: HSDN Supp Data 3: 'Dyspnea'–'Pulmonary Embolism' PubMed co-occurrence=343, TF-IDF=344.79 (문헌 공출현, 확률 아님)
  - [판단 보류 경로 29개 생략 — 근거 미기록·미검사·불확실]

### 의사 현재 진단 비교: 심근염(Myocarditis)[DX:Myocarditis] — ASSESSED
- 4분류: A 지지 경로 4 · B 다른 질환만 연결(추가 검토 가능, 불일치 확정 아님) 1 · C 의료 지식 부족(반박 아님) 0 · D 검증된 반박 0(판단 불가(반박 관계 없음)) → 재검토 신호 있음 / 지식 부족 표시 없음
- 뒷받침 근거: Chest pain[HP:0100749] (경로 HP:0100749-SUGGESTS->DX:Myocarditis#DISMECH_QUOTE_IN_ABSTRACT); Dyspnea[HP:0002094] (경로 HP:0002094-SUGGESTS->DX:Myocarditis#DISMECH_QUOTE_IN_ABSTRACT); Chest pain[HP:0100749] (경로 HP:0100749-SUGGESTS->DX:Myocarditis#HSDN_LITERATURE_COOCCURRENCE); Dyspnea[HP:0002094] (경로 HP:0002094-SUGGESTS->DX:Myocarditis#HSDN_LITERATURE_COOCCURRENCE)
- 설명 부족 근거: 앞으로 숙이면 완화되는 흉통[CONCEPT:chest_pain_relieved_sitting_forward] = 현재 진단으로 설명 부족(다른 후보가 설명) → 심낭염(Pericarditis)[DX:Pericarditis]
- 명시적 충돌 근거: 판단 불가(이 그래프에 현재 진단을 반박하는 관계가 없음 → 근거 부족)
- 아직 확인하지 않아 판단할 수 없는 근거(23): 심장 MRI T1 기반 손상 지표 양성[CONCEPT:cmr_t1_marker] (NOT_RECORDED, 경로 RULE:MYO-CMR-ANY->DX:Myocarditis); 심장 MRI T1 기반 손상 지표 양성[CONCEPT:cmr_t1_marker] (NOT_RECORDED, 경로 RULE:MYO-CMR-BOTH->DX:Myocarditis); 심장 MRI T2 기반 부종 지표 양성[CONCEPT:cmr_t2_marker] (NOT_RECORDED, 경로 RULE:MYO-CMR-ANY->DX:Myocarditis); 심장 MRI T2 기반 부종 지표 양성[CONCEPT:cmr_t2_marker] (NOT_RECORDED, 경로 RULE:MYO-CMR-BOTH->DX:Myocarditis); Edema[HP:0000969] (NOT_RECORDED, 경로 HP:0000969-SUGGESTS->DX:Myocarditis#HSDN_LITERATURE_COOCCURRENCE); Congestive heart failure[HP:0001635] (NOT_RECORDED, 경로 HP:0001635-SUGGESTS->DX:Myocarditis#DISMECH_QUOTE_IN_ABSTRACT); Dilated cardiomyopathy[HP:0001644] (NOT_RECORDED, 경로 HP:0001644-SUGGESTS->DX:Myocarditis#DISMECH_QUOTE_IN_ABSTRACT); Sudden cardiac death[HP:0001645] (NOT_RECORDED, 경로 HP:0001645-SUGGESTS->DX:Myocarditis#DISMECH_QUOTE_IN_ABSTRACT) … 외 15개
- 현재 진단 확인에 쓸 수 있는 검사(지식원 기재, 환자 결과 없음): Endomyocardial Biopsy[TEST:Myocarditis:0]; Cardiac Magnetic Resonance[TEST:Myocarditis:1]
- 추가 검토 후보: 심낭염(Pericarditis)[DX:Pericarditis]: 현재 진단으로 설명 부족한 근거 CONCEPT:chest_pain_relieved_sitting_forward 을(를) 설명 / 임상 소견 근거 묶음 3 > 현재 진단 2 / 지식원 감별 목록(상대 질환 항목에 기재): DisMech eaa5fe99 Pericarditis.yaml differential_diagnoses['Myocarditis'] (이름 일치)

## 2단계(검사 결과 추가)
- 그래프: REAL_KG_v1(HSDN+DisMech+HPO) · 기준 시점 as_of=2.0
- 정렬 = 임상 소견 근거 묶음 수 → 전체 묶음 수(공출현만 있는 묶음은 둘째 기준). 확률·진단 확정 아님. 모든 질환 노드 유지(제거 없음).

| 순위 | 질환 | 독립 지지 묶음 | 임상 소견 묶음 | 공출현만 묶음 | 지지 근거(묶음:최고 등급) | 충돌 | 음성/불충족 | 판단 보류 | 비활성 | 독립성 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 심낭염(Pericarditis)[DX:Pericarditis] | 5 | 5 | 0 | {CONCEPT:chest_pain_relieved_sitting_forward}:DISMECH_NO_REF / {CONCEPT:pericarditis_ecg_change, HP:0012251}:DISMECH_QUOTE_IN_ABSTRACT / {HP:0002094}:DISMECH_NO_REF / {HP:0012531, HP:0100749}:DISMECH_QUOTE_IN_ABSTRACT / {HP:0034788}:DISMECH_QUOTE_IN_ABSTRACT | 0 | 0 | 13 | 0 | UNVERIFIED |
| 2 | 심근염(Myocarditis)[DX:Myocarditis] | 2 | 2 | 0 | {HP:0002094}:DISMECH_QUOTE_IN_ABSTRACT / {HP:0100749}:DISMECH_QUOTE_IN_ABSTRACT | 0 | 0 | 21 | 0 | UNVERIFIED |
| 3 | 결핵(Tuberculosis)[DX:Tuberculosis] | 2 | 2 | 0 | {HP:0002094}:DISMECH_QUOTE_IN_ABSTRACT / {HP:0100749}:DISMECH_QUOTE_IN_ABSTRACT | 0 | 0 | 19 | 0 | UNVERIFIED |
| 4 | 폐색전증(Pulmonary embolism)[DX:Pulmonary embolism] | 2 | 1 | 1 | {HP:0002094}:DISMECH_QUOTE_IN_ABSTRACT / {HP:0012531, HP:0100749}:HSDN_LITERATURE_COOCCURRENCE | 0 | 0 | 29 | 0 | UNVERIFIED |

### 경로별 근거 추적
- **심낭염(Pericarditis)[DX:Pericarditis]**
  - [뒷받침] [DISMECH_QUOTE_IN_ABSTRACT] Chest pain[HP:0100749] -SUGGESTS-> 심낭염(Pericarditis)[DX:Pericarditis] · 조건: 양성 · 근거ID: V1-E_55-chest · 출처: DisMech eaa5fe99 Pericarditis.yaml phenotypes['Pericarditic chest pain'] freq=None supports={'SUPPORT': 1} refs=PMID:38804758 quote_check={'SUPPORT:FOUND': 1} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [뒷받침] [DISMECH_QUOTE_IN_ABSTRACT] Pericardial friction rub[HP:0034788] -SUGGESTS-> 심낭염(Pericarditis)[DX:Pericarditis] · 조건: 양성 · 근거ID: V1rub · 출처: DisMech eaa5fe99 Pericarditis.yaml phenotypes['Pericardial friction rub'] freq=None supports={'SUPPORT': 1} refs=PMID:38804758 quote_check={'SUPPORT:FOUND': 1} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [뒷받침] [DISMECH_QUOTE_IN_ABSTRACT] ST segment elevation[HP:0012251] -SUGGESTS-> 심낭염(Pericarditis)[DX:Pericarditis] · 조건: 양성 · 근거ID: V1st · 출처: DisMech eaa5fe99 Pericarditis.yaml phenotypes['Widespread ST-segment elevation'] freq=None supports={'SUPPORT': 1} refs=PMID:38804758 quote_check={'SUPPORT:FOUND': 1} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [뒷받침] [DISMECH_NO_REF] Dyspnea[HP:0002094] -SUGGESTS-> 심낭염(Pericarditis)[DX:Pericarditis] · 조건: 양성 · 근거ID: V1-E_66-0 · 출처: DisMech eaa5fe99 Pericarditis.yaml phenotypes['Dyspnoea'] freq=None supports={} refs=없음 quote_check={} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Pain[HP:0012531] -SUGGESTS-> 심낭염(Pericarditis)[DX:Pericarditis] · 조건: 양성 · 근거ID: V1-E_53-0 · 출처: HSDN Supp Data 3: 'Pain'–'Pericarditis' PubMed co-occurrence=24, TF-IDF=7.91 (문헌 공출현, 확률 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Chest pain[HP:0100749] -SUGGESTS-> 심낭염(Pericarditis)[DX:Pericarditis] · 조건: 양성 · 근거ID: V1-E_55-chest · 출처: HSDN Supp Data 3: 'Chest Pain'–'Pericarditis' PubMed co-occurrence=74, TF-IDF=81.37 (문헌 공출현, 확률 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Dyspnea[HP:0002094] -SUGGESTS-> 심낭염(Pericarditis)[DX:Pericarditis] · 조건: 양성 · 근거ID: V1-E_66-0 · 출처: HSDN Supp Data 3: 'Dyspnea'–'Pericarditis' PubMed co-occurrence=25, TF-IDF=25.13 (문헌 공출현, 확률 아님)
  - [뒷받침] [LITERATURE_QUOTE_IN_TEXT] ST segment elevation[HP:0012251] -IS_A-> 심낭염 심전도 변화(광범위 ST 상승 또는 PR 하강)[CONCEPT:pericarditis_ecg_change] → 특징적 심낭염 흉통(임상의 판정)[CONCEPT:characteristic_pericarditic_chest_pain] -PART_OF-> PERI-CRIT-2of4(DIAGNOSTIC_CRITERION)[RULE:PERI-CRIT-2of4] → Pericardial friction rub[HP:0034788] -PART_OF-> PERI-CRIT-2of4(DIAGNOSTIC_CRITERION)[RULE:PERI-CRIT-2of4] → 심낭염 심전도 변화(광범위 ST 상승 또는 PR 하강)[CONCEPT:pericarditis_ecg_change] -PART_OF-> PERI-CRIT-2of4(DIAGNOSTIC_CRITERION)[RULE:PERI-CRIT-2of4] → Pericardial effusion[HP:0001698] -PART_OF-> PERI-CRIT-2of4(DIAGNOSTIC_CRITERION)[RULE:PERI-CRIT-2of4] → PERI-CRIT-2of4(DIAGNOSTIC_CRITERION)[RULE:PERI-CRIT-2of4] -SUGGESTS-> 심낭염(Pericarditis)[DX:Pericarditis] · 조건: [DIAGNOSTIC_CRITERION] CONCEPT:characteristic_pericarditic_chest_pain=INDETERMINATE(NOT_RECORDED: 판단 보류); HP:0034788=SATISFIED(양성); CONCEPT:pericarditis_ecg_change=SATISFIED(양성); HP:0001698=INDETERMINATE(NOT_RECORDED: 판단 보류) · 근거ID: V1rub, V1st · 출처: DisMech eaa5fe99 Pericarditis.yaml diagnosis 'widespread ST-segment elevation or PR-segment depression'(정의); DisMech eaa5fe99 Pericarditis.yaml diagnosis[0] + PMID:38804758 · quote_check=FOUND · 조건: 급성 심낭염 의심 환자(성인), 4 특징 중 2 이상. 단일 특징 필수 아님 · 제한: 삼출은 '새로 생기거나 악화' 조건이나 HPO 노드는 '심낭 삼출' 일반
  - [뒷받침] [DISMECH_NO_REF] 앞으로 숙이면 완화되는 흉통[CONCEPT:chest_pain_relieved_sitting_forward] -SUGGESTS-> 심낭염(Pericarditis)[DX:Pericarditis] · 조건: 양성 · 근거ID: V1-E_33-pos · 출처: DisMech eaa5fe99 Pericarditis.yaml phenotypes['Pericarditic chest pain'].description · quote_check=NO_QUOTE · 조건: 흉통이 있을 때(흉통 복합 + E_33) · 제한: AI 큐레이션 설명 문장, 직접 인용 근거 없음 — 등급 DISMECH_NO_REF
  - [판단 보류 경로 13개 생략 — 근거 미기록·미검사·불확실]
- **심근염(Myocarditis)[DX:Myocarditis]**
  - [뒷받침] [DISMECH_QUOTE_IN_ABSTRACT] Chest pain[HP:0100749] -SUGGESTS-> 심근염(Myocarditis)[DX:Myocarditis] · 조건: 양성 · 근거ID: V1-E_55-chest · 출처: DisMech eaa5fe99 Myocarditis.yaml phenotypes['Chest Pain'] freq=FREQUENT supports={'SUPPORT': 1} refs=PMID:35533750 quote_check={'SUPPORT:FOUND': 1} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [뒷받침] [DISMECH_QUOTE_IN_ABSTRACT] Dyspnea[HP:0002094] -SUGGESTS-> 심근염(Myocarditis)[DX:Myocarditis] · 조건: 양성 · 근거ID: V1-E_66-0 · 출처: DisMech eaa5fe99 Myocarditis.yaml phenotypes['Dyspnea'] freq=FREQUENT supports={'SUPPORT': 1} refs=PMID:29096807 quote_check={'SUPPORT:FOUND': 1} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Chest pain[HP:0100749] -SUGGESTS-> 심근염(Myocarditis)[DX:Myocarditis] · 조건: 양성 · 근거ID: V1-E_55-chest · 출처: HSDN Supp Data 3: 'Chest Pain'–'Myocarditis' PubMed co-occurrence=52, TF-IDF=57.18 (문헌 공출현, 확률 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Dyspnea[HP:0002094] -SUGGESTS-> 심근염(Myocarditis)[DX:Myocarditis] · 조건: 양성 · 근거ID: V1-E_66-0 · 출처: HSDN Supp Data 3: 'Dyspnea'–'Myocarditis' PubMed co-occurrence=23, TF-IDF=23.12 (문헌 공출현, 확률 아님)
  - [판단 보류 경로 21개 생략 — 근거 미기록·미검사·불확실]
- **결핵(Tuberculosis)[DX:Tuberculosis]**
  - [뒷받침] [DISMECH_QUOTE_IN_ABSTRACT] Chest pain[HP:0100749] -SUGGESTS-> 결핵(Tuberculosis)[DX:Tuberculosis] · 조건: 양성 · 근거ID: V1-E_55-chest · 출처: DisMech eaa5fe99 Tuberculosis.yaml phenotypes['Chest Pain'] freq=FREQUENT supports={'NO_EVIDENCE': 1, 'SUPPORT': 2} refs=PMID:17508531,PMID:27499981,PMID:30762202 quote_check={'SUPPORT:FOUND': 2, 'NO_EVIDENCE:FOUND': 1} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [뒷받침] [DISMECH_QUOTE_IN_ABSTRACT] Dyspnea[HP:0002094] -SUGGESTS-> 결핵(Tuberculosis)[DX:Tuberculosis] · 조건: 양성 · 근거ID: V1-E_66-0 · 출처: DisMech eaa5fe99 Tuberculosis.yaml phenotypes['Dyspnea'] freq=OCCASIONAL supports={'NO_EVIDENCE': 1, 'SUPPORT': 1} refs=PMID:15623010,PMID:29900887 quote_check={'NO_EVIDENCE:FOUND': 1, 'SUPPORT:FOUND': 1} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [판단 보류 경로 19개 생략 — 근거 미기록·미검사·불확실]
- **폐색전증(Pulmonary embolism)[DX:Pulmonary embolism]**
  - [뒷받침] [DISMECH_QUOTE_IN_ABSTRACT] Dyspnea[HP:0002094] -SUGGESTS-> 폐색전증(Pulmonary embolism)[DX:Pulmonary embolism] · 조건: 양성 · 근거ID: V1-E_66-0 · 출처: DisMech eaa5fe99 Pulmonary_Embolism.yaml phenotypes['Dyspnoea/Post-pulmonary embolism syndrome'] freq=None supports={'SUPPORT': 4} refs=PMID:17904458,PMID:41765088 quote_check={'SUPPORT:FOUND': 4} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Pain[HP:0012531] -SUGGESTS-> 폐색전증(Pulmonary embolism)[DX:Pulmonary embolism] · 조건: 양성 · 근거ID: V1-E_53-0 · 출처: HSDN Supp Data 3: 'Pain'–'Pulmonary Embolism' PubMed co-occurrence=41, TF-IDF=13.50 (문헌 공출현, 확률 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Chest pain[HP:0100749] -SUGGESTS-> 폐색전증(Pulmonary embolism)[DX:Pulmonary embolism] · 조건: 양성 · 근거ID: V1-E_55-chest · 출처: HSDN Supp Data 3: 'Chest Pain'–'Pulmonary Embolism' PubMed co-occurrence=138, TF-IDF=151.74 (문헌 공출현, 확률 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Dyspnea[HP:0002094] -SUGGESTS-> 폐색전증(Pulmonary embolism)[DX:Pulmonary embolism] · 조건: 양성 · 근거ID: V1-E_66-0 · 출처: HSDN Supp Data 3: 'Dyspnea'–'Pulmonary Embolism' PubMed co-occurrence=343, TF-IDF=344.79 (문헌 공출현, 확률 아님)
  - [판단 보류 경로 29개 생략 — 근거 미기록·미검사·불확실]

### 재계산으로 바뀐 경로
- HP:0012251-SUGGESTS->DX:Pericarditis#DISMECH_QUOTE_IN_ABSTRACT: 판단 보류 → 뒷받침 (CHANGED)
- HP:0034788-SUGGESTS->DX:Pericarditis#DISMECH_QUOTE_IN_ABSTRACT: 판단 보류 → 뒷받침 (CHANGED)
- RULE:PERI-CRIT-2of4->DX:Pericarditis: 판단 보류 → 뒷받침 (CHANGED)

### 의사 현재 진단 비교: 심근염(Myocarditis)[DX:Myocarditis] — ASSESSED
- 4분류: A 지지 경로 4 · B 다른 질환만 연결(추가 검토 가능, 불일치 확정 아님) 3 · C 의료 지식 부족(반박 아님) 0 · D 검증된 반박 0(판단 불가(반박 관계 없음)) → 재검토 신호 있음 / 지식 부족 표시 없음
- 뒷받침 근거: Chest pain[HP:0100749] (경로 HP:0100749-SUGGESTS->DX:Myocarditis#DISMECH_QUOTE_IN_ABSTRACT); Dyspnea[HP:0002094] (경로 HP:0002094-SUGGESTS->DX:Myocarditis#DISMECH_QUOTE_IN_ABSTRACT); Chest pain[HP:0100749] (경로 HP:0100749-SUGGESTS->DX:Myocarditis#HSDN_LITERATURE_COOCCURRENCE); Dyspnea[HP:0002094] (경로 HP:0002094-SUGGESTS->DX:Myocarditis#HSDN_LITERATURE_COOCCURRENCE)
- 설명 부족 근거: 앞으로 숙이면 완화되는 흉통[CONCEPT:chest_pain_relieved_sitting_forward] = 현재 진단으로 설명 부족(다른 후보가 설명) → 심낭염(Pericarditis)[DX:Pericarditis]; ST segment elevation[HP:0012251] = 현재 진단으로 설명 부족(다른 후보가 설명) → 심낭염(Pericarditis)[DX:Pericarditis]; Pericardial friction rub[HP:0034788] = 현재 진단으로 설명 부족(다른 후보가 설명) → 심낭염(Pericarditis)[DX:Pericarditis]
- 명시적 충돌 근거: 판단 불가(이 그래프에 현재 진단을 반박하는 관계가 없음 → 근거 부족)
- 아직 확인하지 않아 판단할 수 없는 근거(23): 심장 MRI T1 기반 손상 지표 양성[CONCEPT:cmr_t1_marker] (NOT_RECORDED, 경로 RULE:MYO-CMR-ANY->DX:Myocarditis); 심장 MRI T1 기반 손상 지표 양성[CONCEPT:cmr_t1_marker] (NOT_RECORDED, 경로 RULE:MYO-CMR-BOTH->DX:Myocarditis); 심장 MRI T2 기반 부종 지표 양성[CONCEPT:cmr_t2_marker] (NOT_RECORDED, 경로 RULE:MYO-CMR-ANY->DX:Myocarditis); 심장 MRI T2 기반 부종 지표 양성[CONCEPT:cmr_t2_marker] (NOT_RECORDED, 경로 RULE:MYO-CMR-BOTH->DX:Myocarditis); Edema[HP:0000969] (NOT_RECORDED, 경로 HP:0000969-SUGGESTS->DX:Myocarditis#HSDN_LITERATURE_COOCCURRENCE); Congestive heart failure[HP:0001635] (NOT_RECORDED, 경로 HP:0001635-SUGGESTS->DX:Myocarditis#DISMECH_QUOTE_IN_ABSTRACT); Dilated cardiomyopathy[HP:0001644] (NOT_RECORDED, 경로 HP:0001644-SUGGESTS->DX:Myocarditis#DISMECH_QUOTE_IN_ABSTRACT); Sudden cardiac death[HP:0001645] (NOT_RECORDED, 경로 HP:0001645-SUGGESTS->DX:Myocarditis#DISMECH_QUOTE_IN_ABSTRACT) … 외 15개
- 현재 진단 확인에 쓸 수 있는 검사(지식원 기재, 환자 결과 없음): Endomyocardial Biopsy[TEST:Myocarditis:0]; Cardiac Magnetic Resonance[TEST:Myocarditis:1]
- 추가 검토 후보: 심낭염(Pericarditis)[DX:Pericarditis]: 현재 진단으로 설명 부족한 근거 CONCEPT:chest_pain_relieved_sitting_forward 을(를) 설명 / 현재 진단으로 설명 부족한 근거 HP:0012251 을(를) 설명 / 현재 진단으로 설명 부족한 근거 HP:0034788 을(를) 설명 / 임상 소견 근거 묶음 5 > 현재 진단 2 / 지식원 감별 목록(상대 질환 항목에 기재): DisMech eaa5fe99 Pericarditis.yaml differential_diagnoses['Myocarditis'] (이름 일치)

# V2 흉통, 진찰·심전도·초음파 모두 음성 기록(마찰음 음성은 정보 없음), 현재 진단 심낭염

## 1단계
- 그래프: REAL_KG_v1(HSDN+DisMech+HPO) · 기준 시점 as_of=1.0
- 정렬 = 임상 소견 근거 묶음 수 → 전체 묶음 수(공출현만 있는 묶음은 둘째 기준). 확률·진단 확정 아님. 모든 질환 노드 유지(제거 없음).

| 순위 | 질환 | 독립 지지 묶음 | 임상 소견 묶음 | 공출현만 묶음 | 지지 근거(묶음:최고 등급) | 충돌 | 음성/불충족 | 판단 보류 | 비활성 | 독립성 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 심근염(Myocarditis)[DX:Myocarditis] | 1 | 1 | 0 | {HP:0100749}:DISMECH_QUOTE_IN_ABSTRACT | 0 | 0 | 23 | 0 | N/A |
| 2 | 심낭염(Pericarditis)[DX:Pericarditis] | 1 | 1 | 0 | {HP:0012531, HP:0100749}:DISMECH_QUOTE_IN_ABSTRACT | 0 | 0 | 19 | 0 | N/A |
| 3 | 결핵(Tuberculosis)[DX:Tuberculosis] | 1 | 1 | 0 | {HP:0100749}:DISMECH_QUOTE_IN_ABSTRACT | 0 | 0 | 20 | 0 | N/A |
| 4 | 폐색전증(Pulmonary embolism)[DX:Pulmonary embolism] | 1 | 0 | 1 | {HP:0012531, HP:0100749}:HSDN_LITERATURE_COOCCURRENCE | 0 | 0 | 31 | 0 | N/A |

### 경로별 근거 추적
- **심근염(Myocarditis)[DX:Myocarditis]**
  - [뒷받침] [DISMECH_QUOTE_IN_ABSTRACT] Chest pain[HP:0100749] -SUGGESTS-> 심근염(Myocarditis)[DX:Myocarditis] · 조건: 양성 · 근거ID: V2-E_55-chest · 출처: DisMech eaa5fe99 Myocarditis.yaml phenotypes['Chest Pain'] freq=FREQUENT supports={'SUPPORT': 1} refs=PMID:35533750 quote_check={'SUPPORT:FOUND': 1} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Chest pain[HP:0100749] -SUGGESTS-> 심근염(Myocarditis)[DX:Myocarditis] · 조건: 양성 · 근거ID: V2-E_55-chest · 출처: HSDN Supp Data 3: 'Chest Pain'–'Myocarditis' PubMed co-occurrence=52, TF-IDF=57.18 (문헌 공출현, 확률 아님)
  - [판단 보류 경로 23개 생략 — 근거 미기록·미검사·불확실]
- **심낭염(Pericarditis)[DX:Pericarditis]**
  - [뒷받침] [DISMECH_QUOTE_IN_ABSTRACT] Chest pain[HP:0100749] -SUGGESTS-> 심낭염(Pericarditis)[DX:Pericarditis] · 조건: 양성 · 근거ID: V2-E_55-chest · 출처: DisMech eaa5fe99 Pericarditis.yaml phenotypes['Pericarditic chest pain'] freq=None supports={'SUPPORT': 1} refs=PMID:38804758 quote_check={'SUPPORT:FOUND': 1} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Pain[HP:0012531] -SUGGESTS-> 심낭염(Pericarditis)[DX:Pericarditis] · 조건: 양성 · 근거ID: V2-E_53-0 · 출처: HSDN Supp Data 3: 'Pain'–'Pericarditis' PubMed co-occurrence=24, TF-IDF=7.91 (문헌 공출현, 확률 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Chest pain[HP:0100749] -SUGGESTS-> 심낭염(Pericarditis)[DX:Pericarditis] · 조건: 양성 · 근거ID: V2-E_55-chest · 출처: HSDN Supp Data 3: 'Chest Pain'–'Pericarditis' PubMed co-occurrence=74, TF-IDF=81.37 (문헌 공출현, 확률 아님)
  - [판단 보류 경로 19개 생략 — 근거 미기록·미검사·불확실]
- **결핵(Tuberculosis)[DX:Tuberculosis]**
  - [뒷받침] [DISMECH_QUOTE_IN_ABSTRACT] Chest pain[HP:0100749] -SUGGESTS-> 결핵(Tuberculosis)[DX:Tuberculosis] · 조건: 양성 · 근거ID: V2-E_55-chest · 출처: DisMech eaa5fe99 Tuberculosis.yaml phenotypes['Chest Pain'] freq=FREQUENT supports={'NO_EVIDENCE': 1, 'SUPPORT': 2} refs=PMID:17508531,PMID:27499981,PMID:30762202 quote_check={'SUPPORT:FOUND': 2, 'NO_EVIDENCE:FOUND': 1} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [판단 보류 경로 20개 생략 — 근거 미기록·미검사·불확실]
- **폐색전증(Pulmonary embolism)[DX:Pulmonary embolism]**
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Pain[HP:0012531] -SUGGESTS-> 폐색전증(Pulmonary embolism)[DX:Pulmonary embolism] · 조건: 양성 · 근거ID: V2-E_53-0 · 출처: HSDN Supp Data 3: 'Pain'–'Pulmonary Embolism' PubMed co-occurrence=41, TF-IDF=13.50 (문헌 공출현, 확률 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Chest pain[HP:0100749] -SUGGESTS-> 폐색전증(Pulmonary embolism)[DX:Pulmonary embolism] · 조건: 양성 · 근거ID: V2-E_55-chest · 출처: HSDN Supp Data 3: 'Chest Pain'–'Pulmonary Embolism' PubMed co-occurrence=138, TF-IDF=151.74 (문헌 공출현, 확률 아님)
  - [판단 보류 경로 31개 생략 — 근거 미기록·미검사·불확실]

### 의사 현재 진단 비교: 심낭염(Pericarditis)[DX:Pericarditis] — ASSESSED
- 4분류: A 지지 경로 3 · B 다른 질환만 연결(추가 검토 가능, 불일치 확정 아님) 0 · C 의료 지식 부족(반박 아님) 0 · D 검증된 반박 0(판단 불가(반박 관계 없음)) → 재검토 신호 없음 / 지식 부족 표시 없음
- 뒷받침 근거: Chest pain[HP:0100749] (경로 HP:0100749-SUGGESTS->DX:Pericarditis#DISMECH_QUOTE_IN_ABSTRACT); Pain[HP:0012531] (경로 HP:0012531-SUGGESTS->DX:Pericarditis#HSDN_LITERATURE_COOCCURRENCE); Chest pain[HP:0100749] (경로 HP:0100749-SUGGESTS->DX:Pericarditis#HSDN_LITERATURE_COOCCURRENCE)
- 설명 부족 근거: 없음
- 명시적 충돌 근거: 판단 불가(이 그래프에 현재 진단을 반박하는 관계가 없음 → 근거 부족)
- 아직 확인하지 않아 판단할 수 없는 근거(22): 특징적 심낭염 흉통(임상의 판정)[CONCEPT:characteristic_pericarditic_chest_pain] (NOT_RECORDED, 경로 RULE:PERI-CRIT-2of4->DX:Pericarditis); 앞으로 숙이면 완화되는 흉통[CONCEPT:chest_pain_relieved_sitting_forward] (NOT_RECORDED, 경로 CONCEPT:chest_pain_relieved_sitting_forward-SUGGESTS->DX:Pericarditis#DISMECH_NO_REF); 심낭염 심전도 변화(광범위 ST 상승 또는 PR 하강)[CONCEPT:pericarditis_ecg_change] (NOT_RECORDED, 경로 RULE:PERI-CRIT-2of4->DX:Pericarditis); Edema[HP:0000969] (NOT_RECORDED, 경로 HP:0000969-SUGGESTS->DX:Pericarditis#HSDN_LITERATURE_COOCCURRENCE); Angina pectoris[HP:0001681] (NOT_RECORDED, 경로 HP:0001681-SUGGESTS->DX:Pericarditis#HSDN_LITERATURE_COOCCURRENCE); Pericardial effusion[HP:0001698] (NOT_RECORDED, 경로 HP:0001698-SUGGESTS->DX:Pericarditis#DISMECH_NO_REF); Pericardial effusion[HP:0001698] (NOT_RECORDED, 경로 RULE:PERI-CRIT-2of4->DX:Pericarditis); Fever[HP:0001945] (NOT_RECORDED, 경로 HP:0001945-SUGGESTS->DX:Pericarditis#DISMECH_NO_REF) … 외 14개
- 현재 진단 확인에 쓸 수 있는 검사(지식원 기재, 환자 결과 없음): Clinical diagnosis from pain, rub, electrocardiogram, and effusion[TEST:Pericarditis:0]; C-reactive protein guided treatment and activity decisions[TEST:Pericarditis:1]; Cardiac magnetic resonance to distinguish reversible from fixed constriction[TEST:Pericarditis:2]
- 추가 검토 후보: 심근염(Myocarditis)[DX:Myocarditis]: 지식원 감별 목록(현재 진단 항목에 기재): DisMech eaa5fe99 Pericarditis.yaml differential_diagnoses['Myocarditis'] (이름 일치); 폐색전증(Pulmonary embolism)[DX:Pulmonary embolism]: 지식원 감별 목록(현재 진단 항목에 기재): DisMech eaa5fe99 Pericarditis.yaml differential_diagnoses['Pulmonary embolism'] (이름 일치)

## 2단계(검사 결과 추가)
- 그래프: REAL_KG_v1(HSDN+DisMech+HPO) · 기준 시점 as_of=2.0
- 정렬 = 임상 소견 근거 묶음 수 → 전체 묶음 수(공출현만 있는 묶음은 둘째 기준). 확률·진단 확정 아님. 모든 질환 노드 유지(제거 없음).

| 순위 | 질환 | 독립 지지 묶음 | 임상 소견 묶음 | 공출현만 묶음 | 지지 근거(묶음:최고 등급) | 충돌 | 음성/불충족 | 판단 보류 | 비활성 | 독립성 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 심근염(Myocarditis)[DX:Myocarditis] | 1 | 1 | 0 | {HP:0100749}:DISMECH_QUOTE_IN_ABSTRACT | 0 | 0 | 23 | 0 | N/A |
| 2 | 심낭염(Pericarditis)[DX:Pericarditis] | 1 | 1 | 0 | {HP:0012531, HP:0100749}:DISMECH_QUOTE_IN_ABSTRACT | 0 | 4 | 15 | 0 | N/A |
| 3 | 결핵(Tuberculosis)[DX:Tuberculosis] | 1 | 1 | 0 | {HP:0100749}:DISMECH_QUOTE_IN_ABSTRACT | 0 | 0 | 20 | 0 | N/A |
| 4 | 폐색전증(Pulmonary embolism)[DX:Pulmonary embolism] | 1 | 0 | 1 | {HP:0012531, HP:0100749}:HSDN_LITERATURE_COOCCURRENCE | 0 | 0 | 31 | 0 | N/A |

### 경로별 근거 추적
- **심근염(Myocarditis)[DX:Myocarditis]**
  - [뒷받침] [DISMECH_QUOTE_IN_ABSTRACT] Chest pain[HP:0100749] -SUGGESTS-> 심근염(Myocarditis)[DX:Myocarditis] · 조건: 양성 · 근거ID: V2-E_55-chest · 출처: DisMech eaa5fe99 Myocarditis.yaml phenotypes['Chest Pain'] freq=FREQUENT supports={'SUPPORT': 1} refs=PMID:35533750 quote_check={'SUPPORT:FOUND': 1} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Chest pain[HP:0100749] -SUGGESTS-> 심근염(Myocarditis)[DX:Myocarditis] · 조건: 양성 · 근거ID: V2-E_55-chest · 출처: HSDN Supp Data 3: 'Chest Pain'–'Myocarditis' PubMed co-occurrence=52, TF-IDF=57.18 (문헌 공출현, 확률 아님)
  - [판단 보류 경로 23개 생략 — 근거 미기록·미검사·불확실]
- **심낭염(Pericarditis)[DX:Pericarditis]**
  - [뒷받침] [DISMECH_QUOTE_IN_ABSTRACT] Chest pain[HP:0100749] -SUGGESTS-> 심낭염(Pericarditis)[DX:Pericarditis] · 조건: 양성 · 근거ID: V2-E_55-chest · 출처: DisMech eaa5fe99 Pericarditis.yaml phenotypes['Pericarditic chest pain'] freq=None supports={'SUPPORT': 1} refs=PMID:38804758 quote_check={'SUPPORT:FOUND': 1} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [음성(경로 불충족, 질환 유지)] [DISMECH_QUOTE_IN_ABSTRACT] Pericardial friction rub[HP:0034788] -SUGGESTS-> 심낭염(Pericarditis)[DX:Pericarditis] · 조건: 명시적 음성 · 근거ID: V2rub · 출처: DisMech eaa5fe99 Pericarditis.yaml phenotypes['Pericardial friction rub'] freq=None supports={'SUPPORT': 1} refs=PMID:38804758 quote_check={'SUPPORT:FOUND': 1} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [음성(경로 불충족, 질환 유지)] [DISMECH_NO_REF] Pericardial effusion[HP:0001698] -SUGGESTS-> 심낭염(Pericarditis)[DX:Pericarditis] · 조건: 명시적 음성 · 근거ID: V2eff · 출처: DisMech eaa5fe99 Pericarditis.yaml phenotypes['Pericardial effusion'] freq=None supports={} refs=없음 quote_check={} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [음성(경로 불충족, 질환 유지)] [DISMECH_QUOTE_IN_ABSTRACT] ST segment elevation[HP:0012251] -SUGGESTS-> 심낭염(Pericarditis)[DX:Pericarditis] · 조건: 명시적 음성 · 근거ID: V2st · 출처: DisMech eaa5fe99 Pericarditis.yaml phenotypes['Widespread ST-segment elevation'] freq=None supports={'SUPPORT': 1} refs=PMID:38804758 quote_check={'SUPPORT:FOUND': 1} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [음성(경로 불충족, 질환 유지)] [DISMECH_QUOTE_IN_ABSTRACT] PR segment depression[HP:0031594] -SUGGESTS-> 심낭염(Pericarditis)[DX:Pericarditis] · 조건: 명시적 음성 · 근거ID: V2pr · 출처: DisMech eaa5fe99 Pericarditis.yaml phenotypes['PR-segment depression'] freq=None supports={'SUPPORT': 1} refs=PMID:38804758 quote_check={'SUPPORT:FOUND': 1} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Pain[HP:0012531] -SUGGESTS-> 심낭염(Pericarditis)[DX:Pericarditis] · 조건: 양성 · 근거ID: V2-E_53-0 · 출처: HSDN Supp Data 3: 'Pain'–'Pericarditis' PubMed co-occurrence=24, TF-IDF=7.91 (문헌 공출현, 확률 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Chest pain[HP:0100749] -SUGGESTS-> 심낭염(Pericarditis)[DX:Pericarditis] · 조건: 양성 · 근거ID: V2-E_55-chest · 출처: HSDN Supp Data 3: 'Chest Pain'–'Pericarditis' PubMed co-occurrence=74, TF-IDF=81.37 (문헌 공출현, 확률 아님)
  - [판단 보류 경로 15개 생략 — 근거 미기록·미검사·불확실]
- **결핵(Tuberculosis)[DX:Tuberculosis]**
  - [뒷받침] [DISMECH_QUOTE_IN_ABSTRACT] Chest pain[HP:0100749] -SUGGESTS-> 결핵(Tuberculosis)[DX:Tuberculosis] · 조건: 양성 · 근거ID: V2-E_55-chest · 출처: DisMech eaa5fe99 Tuberculosis.yaml phenotypes['Chest Pain'] freq=FREQUENT supports={'NO_EVIDENCE': 1, 'SUPPORT': 2} refs=PMID:17508531,PMID:27499981,PMID:30762202 quote_check={'SUPPORT:FOUND': 2, 'NO_EVIDENCE:FOUND': 1} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [판단 보류 경로 20개 생략 — 근거 미기록·미검사·불확실]
- **폐색전증(Pulmonary embolism)[DX:Pulmonary embolism]**
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Pain[HP:0012531] -SUGGESTS-> 폐색전증(Pulmonary embolism)[DX:Pulmonary embolism] · 조건: 양성 · 근거ID: V2-E_53-0 · 출처: HSDN Supp Data 3: 'Pain'–'Pulmonary Embolism' PubMed co-occurrence=41, TF-IDF=13.50 (문헌 공출현, 확률 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Chest pain[HP:0100749] -SUGGESTS-> 폐색전증(Pulmonary embolism)[DX:Pulmonary embolism] · 조건: 양성 · 근거ID: V2-E_55-chest · 출처: HSDN Supp Data 3: 'Chest Pain'–'Pulmonary Embolism' PubMed co-occurrence=138, TF-IDF=151.74 (문헌 공출현, 확률 아님)
  - [판단 보류 경로 31개 생략 — 근거 미기록·미검사·불확실]

### 재계산으로 바뀐 경로
- HP:0001698-SUGGESTS->DX:Pericarditis#DISMECH_NO_REF: 판단 보류 → 음성(경로 불충족, 질환 유지) (CHANGED)
- HP:0012251-SUGGESTS->DX:Pericarditis#DISMECH_QUOTE_IN_ABSTRACT: 판단 보류 → 음성(경로 불충족, 질환 유지) (CHANGED)
- HP:0031594-SUGGESTS->DX:Pericarditis#DISMECH_QUOTE_IN_ABSTRACT: 판단 보류 → 음성(경로 불충족, 질환 유지) (CHANGED)
- HP:0034788-SUGGESTS->DX:Pericarditis#DISMECH_QUOTE_IN_ABSTRACT: 판단 보류 → 음성(경로 불충족, 질환 유지) (CHANGED)

### 의사 현재 진단 비교: 심낭염(Pericarditis)[DX:Pericarditis] — ASSESSED
- 4분류: A 지지 경로 3 · B 다른 질환만 연결(추가 검토 가능, 불일치 확정 아님) 0 · C 의료 지식 부족(반박 아님) 0 · D 검증된 반박 0(판단 불가(반박 관계 없음)) → 재검토 신호 없음 / 지식 부족 표시 없음
- 뒷받침 근거: Chest pain[HP:0100749] (경로 HP:0100749-SUGGESTS->DX:Pericarditis#DISMECH_QUOTE_IN_ABSTRACT); Pain[HP:0012531] (경로 HP:0012531-SUGGESTS->DX:Pericarditis#HSDN_LITERATURE_COOCCURRENCE); Chest pain[HP:0100749] (경로 HP:0100749-SUGGESTS->DX:Pericarditis#HSDN_LITERATURE_COOCCURRENCE)
- 설명 부족 근거: 없음
- 명시적 충돌 근거: 판단 불가(이 그래프에 현재 진단을 반박하는 관계가 없음 → 근거 부족)
- 아직 확인하지 않아 판단할 수 없는 근거(16): 특징적 심낭염 흉통(임상의 판정)[CONCEPT:characteristic_pericarditic_chest_pain] (NOT_RECORDED, 경로 RULE:PERI-CRIT-2of4->DX:Pericarditis); 앞으로 숙이면 완화되는 흉통[CONCEPT:chest_pain_relieved_sitting_forward] (NOT_RECORDED, 경로 CONCEPT:chest_pain_relieved_sitting_forward-SUGGESTS->DX:Pericarditis#DISMECH_NO_REF); 심낭염 심전도 변화(광범위 ST 상승 또는 PR 하강)[CONCEPT:pericarditis_ecg_change] (NOT_RECORDED, 경로 RULE:PERI-CRIT-2of4->DX:Pericarditis); Edema[HP:0000969] (NOT_RECORDED, 경로 HP:0000969-SUGGESTS->DX:Pericarditis#HSDN_LITERATURE_COOCCURRENCE); Angina pectoris[HP:0001681] (NOT_RECORDED, 경로 HP:0001681-SUGGESTS->DX:Pericarditis#HSDN_LITERATURE_COOCCURRENCE); Fever[HP:0001945] (NOT_RECORDED, 경로 HP:0001945-SUGGESTS->DX:Pericarditis#DISMECH_NO_REF); Fever[HP:0001945] (NOT_RECORDED, 경로 HP:0001945-SUGGESTS->DX:Pericarditis#HSDN_LITERATURE_COOCCURRENCE); Dyspnea[HP:0002094] (NOT_RECORDED, 경로 HP:0002094-SUGGESTS->DX:Pericarditis#DISMECH_NO_REF) … 외 8개
- 현재 진단 확인에 쓸 수 있는 검사(지식원 기재, 환자 결과 없음): Clinical diagnosis from pain, rub, electrocardiogram, and effusion[TEST:Pericarditis:0]; C-reactive protein guided treatment and activity decisions[TEST:Pericarditis:1]; Cardiac magnetic resonance to distinguish reversible from fixed constriction[TEST:Pericarditis:2]
- 추가 검토 후보: 심근염(Myocarditis)[DX:Myocarditis]: 지식원 감별 목록(현재 진단 항목에 기재): DisMech eaa5fe99 Pericarditis.yaml differential_diagnoses['Myocarditis'] (이름 일치); 폐색전증(Pulmonary embolism)[DX:Pulmonary embolism]: 지식원 감별 목록(현재 진단 항목에 기재): DisMech eaa5fe99 Pericarditis.yaml differential_diagnoses['Pulmonary embolism'] (이름 일치)

# V3 흉통·호흡곤란, 현재 진단 심근염 → 심장 MRI T2 만 양성 → T1 도 양성

## 1단계
- 그래프: REAL_KG_v1(HSDN+DisMech+HPO) · 기준 시점 as_of=1.0
- 정렬 = 임상 소견 근거 묶음 수 → 전체 묶음 수(공출현만 있는 묶음은 둘째 기준). 확률·진단 확정 아님. 모든 질환 노드 유지(제거 없음).

| 순위 | 질환 | 독립 지지 묶음 | 임상 소견 묶음 | 공출현만 묶음 | 지지 근거(묶음:최고 등급) | 충돌 | 음성/불충족 | 판단 보류 | 비활성 | 독립성 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 심근염(Myocarditis)[DX:Myocarditis] | 2 | 2 | 0 | {HP:0002094}:DISMECH_QUOTE_IN_ABSTRACT / {HP:0100749}:DISMECH_QUOTE_IN_ABSTRACT | 0 | 0 | 21 | 0 | UNVERIFIED |
| 2 | 심낭염(Pericarditis)[DX:Pericarditis] | 2 | 2 | 0 | {HP:0002094}:DISMECH_NO_REF / {HP:0012531, HP:0100749}:DISMECH_QUOTE_IN_ABSTRACT | 0 | 0 | 17 | 0 | UNVERIFIED |
| 3 | 결핵(Tuberculosis)[DX:Tuberculosis] | 2 | 2 | 0 | {HP:0002094}:DISMECH_QUOTE_IN_ABSTRACT / {HP:0100749}:DISMECH_QUOTE_IN_ABSTRACT | 0 | 0 | 19 | 0 | UNVERIFIED |
| 4 | 폐색전증(Pulmonary embolism)[DX:Pulmonary embolism] | 2 | 1 | 1 | {HP:0002094}:DISMECH_QUOTE_IN_ABSTRACT / {HP:0012531, HP:0100749}:HSDN_LITERATURE_COOCCURRENCE | 0 | 0 | 29 | 0 | UNVERIFIED |

### 경로별 근거 추적
- **심근염(Myocarditis)[DX:Myocarditis]**
  - [뒷받침] [DISMECH_QUOTE_IN_ABSTRACT] Chest pain[HP:0100749] -SUGGESTS-> 심근염(Myocarditis)[DX:Myocarditis] · 조건: 양성 · 근거ID: V3-E_55-chest · 출처: DisMech eaa5fe99 Myocarditis.yaml phenotypes['Chest Pain'] freq=FREQUENT supports={'SUPPORT': 1} refs=PMID:35533750 quote_check={'SUPPORT:FOUND': 1} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [뒷받침] [DISMECH_QUOTE_IN_ABSTRACT] Dyspnea[HP:0002094] -SUGGESTS-> 심근염(Myocarditis)[DX:Myocarditis] · 조건: 양성 · 근거ID: V3-E_66-0 · 출처: DisMech eaa5fe99 Myocarditis.yaml phenotypes['Dyspnea'] freq=FREQUENT supports={'SUPPORT': 1} refs=PMID:29096807 quote_check={'SUPPORT:FOUND': 1} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Chest pain[HP:0100749] -SUGGESTS-> 심근염(Myocarditis)[DX:Myocarditis] · 조건: 양성 · 근거ID: V3-E_55-chest · 출처: HSDN Supp Data 3: 'Chest Pain'–'Myocarditis' PubMed co-occurrence=52, TF-IDF=57.18 (문헌 공출현, 확률 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Dyspnea[HP:0002094] -SUGGESTS-> 심근염(Myocarditis)[DX:Myocarditis] · 조건: 양성 · 근거ID: V3-E_66-0 · 출처: HSDN Supp Data 3: 'Dyspnea'–'Myocarditis' PubMed co-occurrence=23, TF-IDF=23.12 (문헌 공출현, 확률 아님)
  - [판단 보류 경로 21개 생략 — 근거 미기록·미검사·불확실]
- **심낭염(Pericarditis)[DX:Pericarditis]**
  - [뒷받침] [DISMECH_QUOTE_IN_ABSTRACT] Chest pain[HP:0100749] -SUGGESTS-> 심낭염(Pericarditis)[DX:Pericarditis] · 조건: 양성 · 근거ID: V3-E_55-chest · 출처: DisMech eaa5fe99 Pericarditis.yaml phenotypes['Pericarditic chest pain'] freq=None supports={'SUPPORT': 1} refs=PMID:38804758 quote_check={'SUPPORT:FOUND': 1} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [뒷받침] [DISMECH_NO_REF] Dyspnea[HP:0002094] -SUGGESTS-> 심낭염(Pericarditis)[DX:Pericarditis] · 조건: 양성 · 근거ID: V3-E_66-0 · 출처: DisMech eaa5fe99 Pericarditis.yaml phenotypes['Dyspnoea'] freq=None supports={} refs=없음 quote_check={} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Pain[HP:0012531] -SUGGESTS-> 심낭염(Pericarditis)[DX:Pericarditis] · 조건: 양성 · 근거ID: V3-E_53-0 · 출처: HSDN Supp Data 3: 'Pain'–'Pericarditis' PubMed co-occurrence=24, TF-IDF=7.91 (문헌 공출현, 확률 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Chest pain[HP:0100749] -SUGGESTS-> 심낭염(Pericarditis)[DX:Pericarditis] · 조건: 양성 · 근거ID: V3-E_55-chest · 출처: HSDN Supp Data 3: 'Chest Pain'–'Pericarditis' PubMed co-occurrence=74, TF-IDF=81.37 (문헌 공출현, 확률 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Dyspnea[HP:0002094] -SUGGESTS-> 심낭염(Pericarditis)[DX:Pericarditis] · 조건: 양성 · 근거ID: V3-E_66-0 · 출처: HSDN Supp Data 3: 'Dyspnea'–'Pericarditis' PubMed co-occurrence=25, TF-IDF=25.13 (문헌 공출현, 확률 아님)
  - [판단 보류 경로 17개 생략 — 근거 미기록·미검사·불확실]
- **결핵(Tuberculosis)[DX:Tuberculosis]**
  - [뒷받침] [DISMECH_QUOTE_IN_ABSTRACT] Chest pain[HP:0100749] -SUGGESTS-> 결핵(Tuberculosis)[DX:Tuberculosis] · 조건: 양성 · 근거ID: V3-E_55-chest · 출처: DisMech eaa5fe99 Tuberculosis.yaml phenotypes['Chest Pain'] freq=FREQUENT supports={'NO_EVIDENCE': 1, 'SUPPORT': 2} refs=PMID:17508531,PMID:27499981,PMID:30762202 quote_check={'SUPPORT:FOUND': 2, 'NO_EVIDENCE:FOUND': 1} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [뒷받침] [DISMECH_QUOTE_IN_ABSTRACT] Dyspnea[HP:0002094] -SUGGESTS-> 결핵(Tuberculosis)[DX:Tuberculosis] · 조건: 양성 · 근거ID: V3-E_66-0 · 출처: DisMech eaa5fe99 Tuberculosis.yaml phenotypes['Dyspnea'] freq=OCCASIONAL supports={'NO_EVIDENCE': 1, 'SUPPORT': 1} refs=PMID:15623010,PMID:29900887 quote_check={'NO_EVIDENCE:FOUND': 1, 'SUPPORT:FOUND': 1} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [판단 보류 경로 19개 생략 — 근거 미기록·미검사·불확실]
- **폐색전증(Pulmonary embolism)[DX:Pulmonary embolism]**
  - [뒷받침] [DISMECH_QUOTE_IN_ABSTRACT] Dyspnea[HP:0002094] -SUGGESTS-> 폐색전증(Pulmonary embolism)[DX:Pulmonary embolism] · 조건: 양성 · 근거ID: V3-E_66-0 · 출처: DisMech eaa5fe99 Pulmonary_Embolism.yaml phenotypes['Dyspnoea/Post-pulmonary embolism syndrome'] freq=None supports={'SUPPORT': 4} refs=PMID:17904458,PMID:41765088 quote_check={'SUPPORT:FOUND': 4} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Pain[HP:0012531] -SUGGESTS-> 폐색전증(Pulmonary embolism)[DX:Pulmonary embolism] · 조건: 양성 · 근거ID: V3-E_53-0 · 출처: HSDN Supp Data 3: 'Pain'–'Pulmonary Embolism' PubMed co-occurrence=41, TF-IDF=13.50 (문헌 공출현, 확률 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Chest pain[HP:0100749] -SUGGESTS-> 폐색전증(Pulmonary embolism)[DX:Pulmonary embolism] · 조건: 양성 · 근거ID: V3-E_55-chest · 출처: HSDN Supp Data 3: 'Chest Pain'–'Pulmonary Embolism' PubMed co-occurrence=138, TF-IDF=151.74 (문헌 공출현, 확률 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Dyspnea[HP:0002094] -SUGGESTS-> 폐색전증(Pulmonary embolism)[DX:Pulmonary embolism] · 조건: 양성 · 근거ID: V3-E_66-0 · 출처: HSDN Supp Data 3: 'Dyspnea'–'Pulmonary Embolism' PubMed co-occurrence=343, TF-IDF=344.79 (문헌 공출현, 확률 아님)
  - [판단 보류 경로 29개 생략 — 근거 미기록·미검사·불확실]

### 의사 현재 진단 비교: 심근염(Myocarditis)[DX:Myocarditis] — ASSESSED
- 4분류: A 지지 경로 4 · B 다른 질환만 연결(추가 검토 가능, 불일치 확정 아님) 0 · C 의료 지식 부족(반박 아님) 0 · D 검증된 반박 0(판단 불가(반박 관계 없음)) → 재검토 신호 없음 / 지식 부족 표시 없음
- 뒷받침 근거: Chest pain[HP:0100749] (경로 HP:0100749-SUGGESTS->DX:Myocarditis#DISMECH_QUOTE_IN_ABSTRACT); Dyspnea[HP:0002094] (경로 HP:0002094-SUGGESTS->DX:Myocarditis#DISMECH_QUOTE_IN_ABSTRACT); Chest pain[HP:0100749] (경로 HP:0100749-SUGGESTS->DX:Myocarditis#HSDN_LITERATURE_COOCCURRENCE); Dyspnea[HP:0002094] (경로 HP:0002094-SUGGESTS->DX:Myocarditis#HSDN_LITERATURE_COOCCURRENCE)
- 설명 부족 근거: 없음
- 명시적 충돌 근거: 판단 불가(이 그래프에 현재 진단을 반박하는 관계가 없음 → 근거 부족)
- 아직 확인하지 않아 판단할 수 없는 근거(23): 심장 MRI T1 기반 손상 지표 양성[CONCEPT:cmr_t1_marker] (NOT_RECORDED, 경로 RULE:MYO-CMR-ANY->DX:Myocarditis); 심장 MRI T1 기반 손상 지표 양성[CONCEPT:cmr_t1_marker] (NOT_RECORDED, 경로 RULE:MYO-CMR-BOTH->DX:Myocarditis); 심장 MRI T2 기반 부종 지표 양성[CONCEPT:cmr_t2_marker] (NOT_RECORDED, 경로 RULE:MYO-CMR-ANY->DX:Myocarditis); 심장 MRI T2 기반 부종 지표 양성[CONCEPT:cmr_t2_marker] (NOT_RECORDED, 경로 RULE:MYO-CMR-BOTH->DX:Myocarditis); Edema[HP:0000969] (NOT_RECORDED, 경로 HP:0000969-SUGGESTS->DX:Myocarditis#HSDN_LITERATURE_COOCCURRENCE); Congestive heart failure[HP:0001635] (NOT_RECORDED, 경로 HP:0001635-SUGGESTS->DX:Myocarditis#DISMECH_QUOTE_IN_ABSTRACT); Dilated cardiomyopathy[HP:0001644] (NOT_RECORDED, 경로 HP:0001644-SUGGESTS->DX:Myocarditis#DISMECH_QUOTE_IN_ABSTRACT); Sudden cardiac death[HP:0001645] (NOT_RECORDED, 경로 HP:0001645-SUGGESTS->DX:Myocarditis#DISMECH_QUOTE_IN_ABSTRACT) … 외 15개
- 현재 진단 확인에 쓸 수 있는 검사(지식원 기재, 환자 결과 없음): Endomyocardial Biopsy[TEST:Myocarditis:0]; Cardiac Magnetic Resonance[TEST:Myocarditis:1]
- 추가 검토 후보: 심낭염(Pericarditis)[DX:Pericarditis]: 지식원 감별 목록(상대 질환 항목에 기재): DisMech eaa5fe99 Pericarditis.yaml differential_diagnoses['Myocarditis'] (이름 일치)

## 2단계(검사 결과 추가)
- 그래프: REAL_KG_v1(HSDN+DisMech+HPO) · 기준 시점 as_of=2.0
- 정렬 = 임상 소견 근거 묶음 수 → 전체 묶음 수(공출현만 있는 묶음은 둘째 기준). 확률·진단 확정 아님. 모든 질환 노드 유지(제거 없음).

| 순위 | 질환 | 독립 지지 묶음 | 임상 소견 묶음 | 공출현만 묶음 | 지지 근거(묶음:최고 등급) | 충돌 | 음성/불충족 | 판단 보류 | 비활성 | 독립성 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 심근염(Myocarditis)[DX:Myocarditis] | 3 | 3 | 0 | {CONCEPT:cmr_t2_marker}:LITERATURE_QUOTE_IN_TEXT / {HP:0002094}:DISMECH_QUOTE_IN_ABSTRACT / {HP:0100749}:DISMECH_QUOTE_IN_ABSTRACT | 0 | 0 | 20 | 0 | UNVERIFIED |
| 2 | 심낭염(Pericarditis)[DX:Pericarditis] | 2 | 2 | 0 | {HP:0002094}:DISMECH_NO_REF / {HP:0012531, HP:0100749}:DISMECH_QUOTE_IN_ABSTRACT | 0 | 0 | 17 | 0 | UNVERIFIED |
| 3 | 결핵(Tuberculosis)[DX:Tuberculosis] | 2 | 2 | 0 | {HP:0002094}:DISMECH_QUOTE_IN_ABSTRACT / {HP:0100749}:DISMECH_QUOTE_IN_ABSTRACT | 0 | 0 | 19 | 0 | UNVERIFIED |
| 4 | 폐색전증(Pulmonary embolism)[DX:Pulmonary embolism] | 2 | 1 | 1 | {HP:0002094}:DISMECH_QUOTE_IN_ABSTRACT / {HP:0012531, HP:0100749}:HSDN_LITERATURE_COOCCURRENCE | 0 | 0 | 29 | 0 | UNVERIFIED |

### 경로별 근거 추적
- **심근염(Myocarditis)[DX:Myocarditis]**
  - [뒷받침] [DISMECH_QUOTE_IN_ABSTRACT] Chest pain[HP:0100749] -SUGGESTS-> 심근염(Myocarditis)[DX:Myocarditis] · 조건: 양성 · 근거ID: V3-E_55-chest · 출처: DisMech eaa5fe99 Myocarditis.yaml phenotypes['Chest Pain'] freq=FREQUENT supports={'SUPPORT': 1} refs=PMID:35533750 quote_check={'SUPPORT:FOUND': 1} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [뒷받침] [DISMECH_QUOTE_IN_ABSTRACT] Dyspnea[HP:0002094] -SUGGESTS-> 심근염(Myocarditis)[DX:Myocarditis] · 조건: 양성 · 근거ID: V3-E_66-0 · 출처: DisMech eaa5fe99 Myocarditis.yaml phenotypes['Dyspnea'] freq=FREQUENT supports={'SUPPORT': 1} refs=PMID:29096807 quote_check={'SUPPORT:FOUND': 1} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Chest pain[HP:0100749] -SUGGESTS-> 심근염(Myocarditis)[DX:Myocarditis] · 조건: 양성 · 근거ID: V3-E_55-chest · 출처: HSDN Supp Data 3: 'Chest Pain'–'Myocarditis' PubMed co-occurrence=52, TF-IDF=57.18 (문헌 공출현, 확률 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Dyspnea[HP:0002094] -SUGGESTS-> 심근염(Myocarditis)[DX:Myocarditis] · 조건: 양성 · 근거ID: V3-E_66-0 · 출처: HSDN Supp Data 3: 'Dyspnea'–'Myocarditis' PubMed co-occurrence=23, TF-IDF=23.12 (문헌 공출현, 확률 아님)
  - [뒷받침] [LITERATURE_QUOTE_IN_TEXT] 심장 MRI T2 기반 부종 지표 양성[CONCEPT:cmr_t2_marker] -PART_OF-> MYO-CMR-ANY(DIAGNOSTIC_SUPPORT)[RULE:MYO-CMR-ANY] → 심장 MRI T1 기반 손상 지표 양성[CONCEPT:cmr_t1_marker] -PART_OF-> MYO-CMR-ANY(DIAGNOSTIC_SUPPORT)[RULE:MYO-CMR-ANY] → MYO-CMR-ANY(DIAGNOSTIC_SUPPORT)[RULE:MYO-CMR-ANY] -SUGGESTS-> 심근염(Myocarditis)[DX:Myocarditis] · 조건: [DIAGNOSTIC_SUPPORT] CONCEPT:cmr_t2_marker=SATISFIED(양성); CONCEPT:cmr_t1_marker=INDETERMINATE(NOT_RECORDED: 판단 보류) · 근거ID: V3t2 · 출처: PMID:30545455 · quote_check=FOUND · 조건: 위와 같음, 지표 하나만 양성 · 제한: 'may still support' — 약한 지지
  - [판단 보류 경로 20개 생략 — 근거 미기록·미검사·불확실]
- **심낭염(Pericarditis)[DX:Pericarditis]**
  - [뒷받침] [DISMECH_QUOTE_IN_ABSTRACT] Chest pain[HP:0100749] -SUGGESTS-> 심낭염(Pericarditis)[DX:Pericarditis] · 조건: 양성 · 근거ID: V3-E_55-chest · 출처: DisMech eaa5fe99 Pericarditis.yaml phenotypes['Pericarditic chest pain'] freq=None supports={'SUPPORT': 1} refs=PMID:38804758 quote_check={'SUPPORT:FOUND': 1} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [뒷받침] [DISMECH_NO_REF] Dyspnea[HP:0002094] -SUGGESTS-> 심낭염(Pericarditis)[DX:Pericarditis] · 조건: 양성 · 근거ID: V3-E_66-0 · 출처: DisMech eaa5fe99 Pericarditis.yaml phenotypes['Dyspnoea'] freq=None supports={} refs=없음 quote_check={} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Pain[HP:0012531] -SUGGESTS-> 심낭염(Pericarditis)[DX:Pericarditis] · 조건: 양성 · 근거ID: V3-E_53-0 · 출처: HSDN Supp Data 3: 'Pain'–'Pericarditis' PubMed co-occurrence=24, TF-IDF=7.91 (문헌 공출현, 확률 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Chest pain[HP:0100749] -SUGGESTS-> 심낭염(Pericarditis)[DX:Pericarditis] · 조건: 양성 · 근거ID: V3-E_55-chest · 출처: HSDN Supp Data 3: 'Chest Pain'–'Pericarditis' PubMed co-occurrence=74, TF-IDF=81.37 (문헌 공출현, 확률 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Dyspnea[HP:0002094] -SUGGESTS-> 심낭염(Pericarditis)[DX:Pericarditis] · 조건: 양성 · 근거ID: V3-E_66-0 · 출처: HSDN Supp Data 3: 'Dyspnea'–'Pericarditis' PubMed co-occurrence=25, TF-IDF=25.13 (문헌 공출현, 확률 아님)
  - [판단 보류 경로 17개 생략 — 근거 미기록·미검사·불확실]
- **결핵(Tuberculosis)[DX:Tuberculosis]**
  - [뒷받침] [DISMECH_QUOTE_IN_ABSTRACT] Chest pain[HP:0100749] -SUGGESTS-> 결핵(Tuberculosis)[DX:Tuberculosis] · 조건: 양성 · 근거ID: V3-E_55-chest · 출처: DisMech eaa5fe99 Tuberculosis.yaml phenotypes['Chest Pain'] freq=FREQUENT supports={'NO_EVIDENCE': 1, 'SUPPORT': 2} refs=PMID:17508531,PMID:27499981,PMID:30762202 quote_check={'SUPPORT:FOUND': 2, 'NO_EVIDENCE:FOUND': 1} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [뒷받침] [DISMECH_QUOTE_IN_ABSTRACT] Dyspnea[HP:0002094] -SUGGESTS-> 결핵(Tuberculosis)[DX:Tuberculosis] · 조건: 양성 · 근거ID: V3-E_66-0 · 출처: DisMech eaa5fe99 Tuberculosis.yaml phenotypes['Dyspnea'] freq=OCCASIONAL supports={'NO_EVIDENCE': 1, 'SUPPORT': 1} refs=PMID:15623010,PMID:29900887 quote_check={'NO_EVIDENCE:FOUND': 1, 'SUPPORT:FOUND': 1} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [판단 보류 경로 19개 생략 — 근거 미기록·미검사·불확실]
- **폐색전증(Pulmonary embolism)[DX:Pulmonary embolism]**
  - [뒷받침] [DISMECH_QUOTE_IN_ABSTRACT] Dyspnea[HP:0002094] -SUGGESTS-> 폐색전증(Pulmonary embolism)[DX:Pulmonary embolism] · 조건: 양성 · 근거ID: V3-E_66-0 · 출처: DisMech eaa5fe99 Pulmonary_Embolism.yaml phenotypes['Dyspnoea/Post-pulmonary embolism syndrome'] freq=None supports={'SUPPORT': 4} refs=PMID:17904458,PMID:41765088 quote_check={'SUPPORT:FOUND': 4} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Pain[HP:0012531] -SUGGESTS-> 폐색전증(Pulmonary embolism)[DX:Pulmonary embolism] · 조건: 양성 · 근거ID: V3-E_53-0 · 출처: HSDN Supp Data 3: 'Pain'–'Pulmonary Embolism' PubMed co-occurrence=41, TF-IDF=13.50 (문헌 공출현, 확률 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Chest pain[HP:0100749] -SUGGESTS-> 폐색전증(Pulmonary embolism)[DX:Pulmonary embolism] · 조건: 양성 · 근거ID: V3-E_55-chest · 출처: HSDN Supp Data 3: 'Chest Pain'–'Pulmonary Embolism' PubMed co-occurrence=138, TF-IDF=151.74 (문헌 공출현, 확률 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Dyspnea[HP:0002094] -SUGGESTS-> 폐색전증(Pulmonary embolism)[DX:Pulmonary embolism] · 조건: 양성 · 근거ID: V3-E_66-0 · 출처: HSDN Supp Data 3: 'Dyspnea'–'Pulmonary Embolism' PubMed co-occurrence=343, TF-IDF=344.79 (문헌 공출현, 확률 아님)
  - [판단 보류 경로 29개 생략 — 근거 미기록·미검사·불확실]

### 재계산으로 바뀐 경로
- RULE:MYO-CMR-ANY->DX:Myocarditis: 판단 보류 → 뒷받침 (CHANGED)

### 의사 현재 진단 비교: 심근염(Myocarditis)[DX:Myocarditis] — ASSESSED
- 4분류: A 지지 경로 5 · B 다른 질환만 연결(추가 검토 가능, 불일치 확정 아님) 0 · C 의료 지식 부족(반박 아님) 0 · D 검증된 반박 0(판단 불가(반박 관계 없음)) → 재검토 신호 없음 / 지식 부족 표시 없음
- 뒷받침 근거: Chest pain[HP:0100749] (경로 HP:0100749-SUGGESTS->DX:Myocarditis#DISMECH_QUOTE_IN_ABSTRACT); Dyspnea[HP:0002094] (경로 HP:0002094-SUGGESTS->DX:Myocarditis#DISMECH_QUOTE_IN_ABSTRACT); Chest pain[HP:0100749] (경로 HP:0100749-SUGGESTS->DX:Myocarditis#HSDN_LITERATURE_COOCCURRENCE); Dyspnea[HP:0002094] (경로 HP:0002094-SUGGESTS->DX:Myocarditis#HSDN_LITERATURE_COOCCURRENCE); 심장 MRI T2 기반 부종 지표 양성[CONCEPT:cmr_t2_marker] (경로 RULE:MYO-CMR-ANY->DX:Myocarditis)
- 설명 부족 근거: 없음
- 명시적 충돌 근거: 판단 불가(이 그래프에 현재 진단을 반박하는 관계가 없음 → 근거 부족)
- 아직 확인하지 않아 판단할 수 없는 근거(20): 심장 MRI T1 기반 손상 지표 양성[CONCEPT:cmr_t1_marker] (NOT_RECORDED, 경로 RULE:MYO-CMR-BOTH->DX:Myocarditis); Edema[HP:0000969] (NOT_RECORDED, 경로 HP:0000969-SUGGESTS->DX:Myocarditis#HSDN_LITERATURE_COOCCURRENCE); Congestive heart failure[HP:0001635] (NOT_RECORDED, 경로 HP:0001635-SUGGESTS->DX:Myocarditis#DISMECH_QUOTE_IN_ABSTRACT); Dilated cardiomyopathy[HP:0001644] (NOT_RECORDED, 경로 HP:0001644-SUGGESTS->DX:Myocarditis#DISMECH_QUOTE_IN_ABSTRACT); Sudden cardiac death[HP:0001645] (NOT_RECORDED, 경로 HP:0001645-SUGGESTS->DX:Myocarditis#DISMECH_QUOTE_IN_ABSTRACT); Atrioventricular block[HP:0001678] (NOT_RECORDED, 경로 HP:0001678-SUGGESTS->DX:Myocarditis#DISMECH_QUOTE_IN_ABSTRACT); Angina pectoris[HP:0001681] (NOT_RECORDED, 경로 HP:0001681-SUGGESTS->DX:Myocarditis#HSDN_LITERATURE_COOCCURRENCE); Increased total eosinophil count[HP:0001880] (NOT_RECORDED, 경로 HP:0001880-SUGGESTS->DX:Myocarditis#DISMECH_QUOTE_IN_ABSTRACT) … 외 12개
- 현재 진단 확인에 쓸 수 있는 검사(지식원 기재, 환자 결과 없음): Endomyocardial Biopsy[TEST:Myocarditis:0]; Cardiac Magnetic Resonance[TEST:Myocarditis:1]
- 추가 검토 후보: 심낭염(Pericarditis)[DX:Pericarditis]: 지식원 감별 목록(상대 질환 항목에 기재): DisMech eaa5fe99 Pericarditis.yaml differential_diagnoses['Myocarditis'] (이름 일치)

## 3단계(T1 지표 추가)
- 그래프: REAL_KG_v1(HSDN+DisMech+HPO) · 기준 시점 as_of=3.0
- 정렬 = 임상 소견 근거 묶음 수 → 전체 묶음 수(공출현만 있는 묶음은 둘째 기준). 확률·진단 확정 아님. 모든 질환 노드 유지(제거 없음).

| 순위 | 질환 | 독립 지지 묶음 | 임상 소견 묶음 | 공출현만 묶음 | 지지 근거(묶음:최고 등급) | 충돌 | 음성/불충족 | 판단 보류 | 비활성 | 독립성 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 심근염(Myocarditis)[DX:Myocarditis] | 4 | 4 | 0 | {CONCEPT:cmr_t1_marker}:LITERATURE_QUOTE_IN_TEXT / {CONCEPT:cmr_t2_marker}:LITERATURE_QUOTE_IN_TEXT / {HP:0002094}:DISMECH_QUOTE_IN_ABSTRACT / {HP:0100749}:DISMECH_QUOTE_IN_ABSTRACT | 0 | 0 | 19 | 0 | UNVERIFIED |
| 2 | 심낭염(Pericarditis)[DX:Pericarditis] | 2 | 2 | 0 | {HP:0002094}:DISMECH_NO_REF / {HP:0012531, HP:0100749}:DISMECH_QUOTE_IN_ABSTRACT | 0 | 0 | 17 | 0 | UNVERIFIED |
| 3 | 결핵(Tuberculosis)[DX:Tuberculosis] | 2 | 2 | 0 | {HP:0002094}:DISMECH_QUOTE_IN_ABSTRACT / {HP:0100749}:DISMECH_QUOTE_IN_ABSTRACT | 0 | 0 | 19 | 0 | UNVERIFIED |
| 4 | 폐색전증(Pulmonary embolism)[DX:Pulmonary embolism] | 2 | 1 | 1 | {HP:0002094}:DISMECH_QUOTE_IN_ABSTRACT / {HP:0012531, HP:0100749}:HSDN_LITERATURE_COOCCURRENCE | 0 | 0 | 29 | 0 | UNVERIFIED |

### 경로별 근거 추적
- **심근염(Myocarditis)[DX:Myocarditis]**
  - [뒷받침] [DISMECH_QUOTE_IN_ABSTRACT] Chest pain[HP:0100749] -SUGGESTS-> 심근염(Myocarditis)[DX:Myocarditis] · 조건: 양성 · 근거ID: V3-E_55-chest · 출처: DisMech eaa5fe99 Myocarditis.yaml phenotypes['Chest Pain'] freq=FREQUENT supports={'SUPPORT': 1} refs=PMID:35533750 quote_check={'SUPPORT:FOUND': 1} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [뒷받침] [DISMECH_QUOTE_IN_ABSTRACT] Dyspnea[HP:0002094] -SUGGESTS-> 심근염(Myocarditis)[DX:Myocarditis] · 조건: 양성 · 근거ID: V3-E_66-0 · 출처: DisMech eaa5fe99 Myocarditis.yaml phenotypes['Dyspnea'] freq=FREQUENT supports={'SUPPORT': 1} refs=PMID:29096807 quote_check={'SUPPORT:FOUND': 1} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Chest pain[HP:0100749] -SUGGESTS-> 심근염(Myocarditis)[DX:Myocarditis] · 조건: 양성 · 근거ID: V3-E_55-chest · 출처: HSDN Supp Data 3: 'Chest Pain'–'Myocarditis' PubMed co-occurrence=52, TF-IDF=57.18 (문헌 공출현, 확률 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Dyspnea[HP:0002094] -SUGGESTS-> 심근염(Myocarditis)[DX:Myocarditis] · 조건: 양성 · 근거ID: V3-E_66-0 · 출처: HSDN Supp Data 3: 'Dyspnea'–'Myocarditis' PubMed co-occurrence=23, TF-IDF=23.12 (문헌 공출현, 확률 아님)
  - [뒷받침] [LITERATURE_QUOTE_IN_TEXT] 심장 MRI T2 기반 부종 지표 양성[CONCEPT:cmr_t2_marker] -PART_OF-> MYO-CMR-BOTH(DIAGNOSTIC_CRITERION)[RULE:MYO-CMR-BOTH] → 심장 MRI T1 기반 손상 지표 양성[CONCEPT:cmr_t1_marker] -PART_OF-> MYO-CMR-BOTH(DIAGNOSTIC_CRITERION)[RULE:MYO-CMR-BOTH] → MYO-CMR-BOTH(DIAGNOSTIC_CRITERION)[RULE:MYO-CMR-BOTH] -SUGGESTS-> 심근염(Myocarditis)[DX:Myocarditis] · 조건: [DIAGNOSTIC_CRITERION] CONCEPT:cmr_t2_marker=SATISFIED(양성); CONCEPT:cmr_t1_marker=SATISFIED(양성) · 근거ID: V3t2, V3t1 · 출처: DisMech eaa5fe99 Myocarditis.yaml diagnosis['Cardiac Magnetic Resonance'] + PMID:30545455 · quote_check=FOUND · 조건: 급성 심근 염증 의심, 심장 MRI 시행 · 제한: 특이도 증가(확정 아님), 조직 확진은 심내막 생검
  - [뒷받침] [LITERATURE_QUOTE_IN_TEXT] 심장 MRI T2 기반 부종 지표 양성[CONCEPT:cmr_t2_marker] -PART_OF-> MYO-CMR-ANY(DIAGNOSTIC_SUPPORT)[RULE:MYO-CMR-ANY] → 심장 MRI T1 기반 손상 지표 양성[CONCEPT:cmr_t1_marker] -PART_OF-> MYO-CMR-ANY(DIAGNOSTIC_SUPPORT)[RULE:MYO-CMR-ANY] → MYO-CMR-ANY(DIAGNOSTIC_SUPPORT)[RULE:MYO-CMR-ANY] -SUGGESTS-> 심근염(Myocarditis)[DX:Myocarditis] · 조건: [DIAGNOSTIC_SUPPORT] CONCEPT:cmr_t2_marker=SATISFIED(양성); CONCEPT:cmr_t1_marker=SATISFIED(양성) · 근거ID: V3t2, V3t1 · 출처: PMID:30545455 · quote_check=FOUND · 조건: 위와 같음, 지표 하나만 양성 · 제한: 'may still support' — 약한 지지
  - [판단 보류 경로 19개 생략 — 근거 미기록·미검사·불확실]
- **심낭염(Pericarditis)[DX:Pericarditis]**
  - [뒷받침] [DISMECH_QUOTE_IN_ABSTRACT] Chest pain[HP:0100749] -SUGGESTS-> 심낭염(Pericarditis)[DX:Pericarditis] · 조건: 양성 · 근거ID: V3-E_55-chest · 출처: DisMech eaa5fe99 Pericarditis.yaml phenotypes['Pericarditic chest pain'] freq=None supports={'SUPPORT': 1} refs=PMID:38804758 quote_check={'SUPPORT:FOUND': 1} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [뒷받침] [DISMECH_NO_REF] Dyspnea[HP:0002094] -SUGGESTS-> 심낭염(Pericarditis)[DX:Pericarditis] · 조건: 양성 · 근거ID: V3-E_66-0 · 출처: DisMech eaa5fe99 Pericarditis.yaml phenotypes['Dyspnoea'] freq=None supports={} refs=없음 quote_check={} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Pain[HP:0012531] -SUGGESTS-> 심낭염(Pericarditis)[DX:Pericarditis] · 조건: 양성 · 근거ID: V3-E_53-0 · 출처: HSDN Supp Data 3: 'Pain'–'Pericarditis' PubMed co-occurrence=24, TF-IDF=7.91 (문헌 공출현, 확률 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Chest pain[HP:0100749] -SUGGESTS-> 심낭염(Pericarditis)[DX:Pericarditis] · 조건: 양성 · 근거ID: V3-E_55-chest · 출처: HSDN Supp Data 3: 'Chest Pain'–'Pericarditis' PubMed co-occurrence=74, TF-IDF=81.37 (문헌 공출현, 확률 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Dyspnea[HP:0002094] -SUGGESTS-> 심낭염(Pericarditis)[DX:Pericarditis] · 조건: 양성 · 근거ID: V3-E_66-0 · 출처: HSDN Supp Data 3: 'Dyspnea'–'Pericarditis' PubMed co-occurrence=25, TF-IDF=25.13 (문헌 공출현, 확률 아님)
  - [판단 보류 경로 17개 생략 — 근거 미기록·미검사·불확실]
- **결핵(Tuberculosis)[DX:Tuberculosis]**
  - [뒷받침] [DISMECH_QUOTE_IN_ABSTRACT] Chest pain[HP:0100749] -SUGGESTS-> 결핵(Tuberculosis)[DX:Tuberculosis] · 조건: 양성 · 근거ID: V3-E_55-chest · 출처: DisMech eaa5fe99 Tuberculosis.yaml phenotypes['Chest Pain'] freq=FREQUENT supports={'NO_EVIDENCE': 1, 'SUPPORT': 2} refs=PMID:17508531,PMID:27499981,PMID:30762202 quote_check={'SUPPORT:FOUND': 2, 'NO_EVIDENCE:FOUND': 1} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [뒷받침] [DISMECH_QUOTE_IN_ABSTRACT] Dyspnea[HP:0002094] -SUGGESTS-> 결핵(Tuberculosis)[DX:Tuberculosis] · 조건: 양성 · 근거ID: V3-E_66-0 · 출처: DisMech eaa5fe99 Tuberculosis.yaml phenotypes['Dyspnea'] freq=OCCASIONAL supports={'NO_EVIDENCE': 1, 'SUPPORT': 1} refs=PMID:15623010,PMID:29900887 quote_check={'NO_EVIDENCE:FOUND': 1, 'SUPPORT:FOUND': 1} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [판단 보류 경로 19개 생략 — 근거 미기록·미검사·불확실]
- **폐색전증(Pulmonary embolism)[DX:Pulmonary embolism]**
  - [뒷받침] [DISMECH_QUOTE_IN_ABSTRACT] Dyspnea[HP:0002094] -SUGGESTS-> 폐색전증(Pulmonary embolism)[DX:Pulmonary embolism] · 조건: 양성 · 근거ID: V3-E_66-0 · 출처: DisMech eaa5fe99 Pulmonary_Embolism.yaml phenotypes['Dyspnoea/Post-pulmonary embolism syndrome'] freq=None supports={'SUPPORT': 4} refs=PMID:17904458,PMID:41765088 quote_check={'SUPPORT:FOUND': 4} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Pain[HP:0012531] -SUGGESTS-> 폐색전증(Pulmonary embolism)[DX:Pulmonary embolism] · 조건: 양성 · 근거ID: V3-E_53-0 · 출처: HSDN Supp Data 3: 'Pain'–'Pulmonary Embolism' PubMed co-occurrence=41, TF-IDF=13.50 (문헌 공출현, 확률 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Chest pain[HP:0100749] -SUGGESTS-> 폐색전증(Pulmonary embolism)[DX:Pulmonary embolism] · 조건: 양성 · 근거ID: V3-E_55-chest · 출처: HSDN Supp Data 3: 'Chest Pain'–'Pulmonary Embolism' PubMed co-occurrence=138, TF-IDF=151.74 (문헌 공출현, 확률 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Dyspnea[HP:0002094] -SUGGESTS-> 폐색전증(Pulmonary embolism)[DX:Pulmonary embolism] · 조건: 양성 · 근거ID: V3-E_66-0 · 출처: HSDN Supp Data 3: 'Dyspnea'–'Pulmonary Embolism' PubMed co-occurrence=343, TF-IDF=344.79 (문헌 공출현, 확률 아님)
  - [판단 보류 경로 29개 생략 — 근거 미기록·미검사·불확실]

### 재계산으로 바뀐 경로
- RULE:MYO-CMR-BOTH->DX:Myocarditis: 판단 보류 → 뒷받침 (CHANGED)

### 의사 현재 진단 비교: 심근염(Myocarditis)[DX:Myocarditis] — ASSESSED
- 4분류: A 지지 경로 6 · B 다른 질환만 연결(추가 검토 가능, 불일치 확정 아님) 0 · C 의료 지식 부족(반박 아님) 0 · D 검증된 반박 0(판단 불가(반박 관계 없음)) → 재검토 신호 없음 / 지식 부족 표시 없음
- 뒷받침 근거: Chest pain[HP:0100749] (경로 HP:0100749-SUGGESTS->DX:Myocarditis#DISMECH_QUOTE_IN_ABSTRACT); Dyspnea[HP:0002094] (경로 HP:0002094-SUGGESTS->DX:Myocarditis#DISMECH_QUOTE_IN_ABSTRACT); Chest pain[HP:0100749] (경로 HP:0100749-SUGGESTS->DX:Myocarditis#HSDN_LITERATURE_COOCCURRENCE); Dyspnea[HP:0002094] (경로 HP:0002094-SUGGESTS->DX:Myocarditis#HSDN_LITERATURE_COOCCURRENCE); 심장 MRI T2 기반 부종 지표 양성[CONCEPT:cmr_t2_marker], 심장 MRI T1 기반 손상 지표 양성[CONCEPT:cmr_t1_marker] (경로 RULE:MYO-CMR-BOTH->DX:Myocarditis); 심장 MRI T2 기반 부종 지표 양성[CONCEPT:cmr_t2_marker], 심장 MRI T1 기반 손상 지표 양성[CONCEPT:cmr_t1_marker] (경로 RULE:MYO-CMR-ANY->DX:Myocarditis)
- 설명 부족 근거: 없음
- 명시적 충돌 근거: 판단 불가(이 그래프에 현재 진단을 반박하는 관계가 없음 → 근거 부족)
- 아직 확인하지 않아 판단할 수 없는 근거(19): Edema[HP:0000969] (NOT_RECORDED, 경로 HP:0000969-SUGGESTS->DX:Myocarditis#HSDN_LITERATURE_COOCCURRENCE); Congestive heart failure[HP:0001635] (NOT_RECORDED, 경로 HP:0001635-SUGGESTS->DX:Myocarditis#DISMECH_QUOTE_IN_ABSTRACT); Dilated cardiomyopathy[HP:0001644] (NOT_RECORDED, 경로 HP:0001644-SUGGESTS->DX:Myocarditis#DISMECH_QUOTE_IN_ABSTRACT); Sudden cardiac death[HP:0001645] (NOT_RECORDED, 경로 HP:0001645-SUGGESTS->DX:Myocarditis#DISMECH_QUOTE_IN_ABSTRACT); Atrioventricular block[HP:0001678] (NOT_RECORDED, 경로 HP:0001678-SUGGESTS->DX:Myocarditis#DISMECH_QUOTE_IN_ABSTRACT); Angina pectoris[HP:0001681] (NOT_RECORDED, 경로 HP:0001681-SUGGESTS->DX:Myocarditis#HSDN_LITERATURE_COOCCURRENCE); Increased total eosinophil count[HP:0001880] (NOT_RECORDED, 경로 HP:0001880-SUGGESTS->DX:Myocarditis#DISMECH_QUOTE_IN_ABSTRACT); Fever[HP:0001945] (NOT_RECORDED, 경로 HP:0001945-SUGGESTS->DX:Myocarditis#HSDN_LITERATURE_COOCCURRENCE) … 외 11개
- 현재 진단 확인에 쓸 수 있는 검사(지식원 기재, 환자 결과 없음): Endomyocardial Biopsy[TEST:Myocarditis:0]; Cardiac Magnetic Resonance[TEST:Myocarditis:1]
- 추가 검토 후보: 심낭염(Pericarditis)[DX:Pericarditis]: 지식원 감별 목록(상대 질환 항목에 기재): DisMech eaa5fe99 Pericarditis.yaml differential_diagnoses['Myocarditis'] (이름 일치)

# V4 HIV 감염 + 발열·기침, 현재 진단 폐색전증 → HIV 음성으로 정정

## 1단계
- 그래프: REAL_KG_v1(HSDN+DisMech+HPO) · 기준 시점 as_of=1.0
- 정렬 = 임상 소견 근거 묶음 수 → 전체 묶음 수(공출현만 있는 묶음은 둘째 기준). 확률·진단 확정 아님. 모든 질환 노드 유지(제거 없음).

| 순위 | 질환 | 독립 지지 묶음 | 임상 소견 묶음 | 공출현만 묶음 | 지지 근거(묶음:최고 등급) | 충돌 | 음성/불충족 | 판단 보류 | 비활성 | 독립성 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 결핵(Tuberculosis)[DX:Tuberculosis] | 2 | 2 | 0 | {HP:0001945}:DISMECH_QUOTE_IN_ABSTRACT / {HP:0012735}:LITERATURE_QUOTE_IN_TEXT | 0 | 0 | 17 | 0 | UNVERIFIED |
| 2 | 심낭염(Pericarditis)[DX:Pericarditis] | 1 | 1 | 0 | {HP:0001945}:DISMECH_NO_REF | 0 | 0 | 20 | 0 | N/A |
| 3 | 폐색전증(Pulmonary embolism)[DX:Pulmonary embolism] | 2 | 0 | 2 | {HP:0001945}:HSDN_LITERATURE_COOCCURRENCE / {HP:0012735}:HSDN_LITERATURE_COOCCURRENCE | 0 | 0 | 31 | 0 | UNVERIFIED |
| 4 | 심근염(Myocarditis)[DX:Myocarditis] | 1 | 0 | 1 | {HP:0001945}:HSDN_LITERATURE_COOCCURRENCE | 0 | 0 | 24 | 0 | N/A |

### 경로별 근거 추적
- **결핵(Tuberculosis)[DX:Tuberculosis]**
  - [뒷받침] [DISMECH_QUOTE_IN_ABSTRACT] Fever[HP:0001945] -SUGGESTS-> 결핵(Tuberculosis)[DX:Tuberculosis] · 조건: 양성 · 근거ID: V4-E_91-0 · 출처: DisMech eaa5fe99 Tuberculosis.yaml phenotypes['Fever'] freq=FREQUENT supports={'SUPPORT': 3} refs=PMID:11120618,PMID:18173876,PMID:31641790 quote_check={'SUPPORT:FOUND': 3} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Fever[HP:0001945] -SUGGESTS-> 결핵(Tuberculosis)[DX:Tuberculosis] · 조건: 양성 · 근거ID: V4-E_91-0 · 출처: HSDN Supp Data 3: 'Fever'–'Tuberculosis' PubMed co-occurrence=59, TF-IDF=36.52 (문헌 공출현, 확률 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Cough[HP:0012735] -SUGGESTS-> 결핵(Tuberculosis)[DX:Tuberculosis] · 조건: 양성 · 근거ID: V4-E_201-0 · 출처: HSDN Supp Data 3: 'Cough'–'Tuberculosis' PubMed co-occurrence=24, TF-IDF=31.55 (문헌 공출현, 확률 아님)
  - [뒷받침] [LITERATURE_QUOTE_IN_TEXT] Cough[HP:0012735] -PART_OF-> TB-HIV-SYMPTOM-SCREEN(SCREENING_CRITERION)[RULE:TB-HIV-SYMPTOM-SCREEN] → Fever[HP:0001945] -PART_OF-> TB-HIV-SYMPTOM-SCREEN(SCREENING_CRITERION)[RULE:TB-HIV-SYMPTOM-SCREEN] → Night sweats[HP:0030166] -PART_OF-> TB-HIV-SYMPTOM-SCREEN(SCREENING_CRITERION)[RULE:TB-HIV-SYMPTOM-SCREEN] → Hemoptysis[HP:0002105] -PART_OF-> TB-HIV-SYMPTOM-SCREEN(SCREENING_CRITERION)[RULE:TB-HIV-SYMPTOM-SCREEN] → Weight loss[HP:0001824] -PART_OF-> TB-HIV-SYMPTOM-SCREEN(SCREENING_CRITERION)[RULE:TB-HIV-SYMPTOM-SCREEN] → HIV 감염(환자 보고)[CONCEPT:hiv_infection] -GATES-> TB-HIV-SYMPTOM-SCREEN(SCREENING_CRITERION)[RULE:TB-HIV-SYMPTOM-SCREEN] → TB-HIV-SYMPTOM-SCREEN(SCREENING_CRITERION)[RULE:TB-HIV-SYMPTOM-SCREEN] -SUGGESTS-> 결핵(Tuberculosis)[DX:Tuberculosis] · 조건: [SCREENING_CRITERION] HP:0012735=SATISFIED(양성); HP:0001945=SATISFIED(양성); HP:0030166=INDETERMINATE(NOT_RECORDED: 판단 보류); HP:0002105=INDETERMINATE(NOT_RECORDED: 판단 보류); HP:0001824=INDETERMINATE(NOT_RECORDED: 판단 보류); CONCEPT:hiv_infection=SATISFIED(양성) · 근거ID: V4-E_201-0, V4-E_91-0 · 출처: PMID:29196066 CHEST 2018 · quote_check=FOUND · 조건: HIV 감염자에서 WHO 증상(기침·발열·야간 발한·객혈·체중감소) 중 하나 → 결핵 평가 대상 · 제한: 선별 민감도 증가 서술 — 진단 확정 아님
  - [판단 보류 경로 17개 생략 — 근거 미기록·미검사·불확실]
- **심낭염(Pericarditis)[DX:Pericarditis]**
  - [뒷받침] [DISMECH_NO_REF] Fever[HP:0001945] -SUGGESTS-> 심낭염(Pericarditis)[DX:Pericarditis] · 조건: 양성 · 근거ID: V4-E_91-0 · 출처: DisMech eaa5fe99 Pericarditis.yaml phenotypes['Fever'] freq=None supports={} refs=없음 quote_check={} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Fever[HP:0001945] -SUGGESTS-> 심낭염(Pericarditis)[DX:Pericarditis] · 조건: 양성 · 근거ID: V4-E_91-0 · 출처: HSDN Supp Data 3: 'Fever'–'Pericarditis' PubMed co-occurrence=53, TF-IDF=32.80 (문헌 공출현, 확률 아님)
  - [판단 보류 경로 20개 생략 — 근거 미기록·미검사·불확실]
- **폐색전증(Pulmonary embolism)[DX:Pulmonary embolism]**
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Fever[HP:0001945] -SUGGESTS-> 폐색전증(Pulmonary embolism)[DX:Pulmonary embolism] · 조건: 양성 · 근거ID: V4-E_91-0 · 출처: HSDN Supp Data 3: 'Fever'–'Pulmonary Embolism' PubMed co-occurrence=43, TF-IDF=26.61 (문헌 공출현, 확률 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Cough[HP:0012735] -SUGGESTS-> 폐색전증(Pulmonary embolism)[DX:Pulmonary embolism] · 조건: 양성 · 근거ID: V4-E_201-0 · 출처: HSDN Supp Data 3: 'Cough'–'Pulmonary Embolism' PubMed co-occurrence=22, TF-IDF=28.92 (문헌 공출현, 확률 아님)
  - [판단 보류 경로 31개 생략 — 근거 미기록·미검사·불확실]
- **심근염(Myocarditis)[DX:Myocarditis]**
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Fever[HP:0001945] -SUGGESTS-> 심근염(Myocarditis)[DX:Myocarditis] · 조건: 양성 · 근거ID: V4-E_91-0 · 출처: HSDN Supp Data 3: 'Fever'–'Myocarditis' PubMed co-occurrence=25, TF-IDF=15.47 (문헌 공출현, 확률 아님)
  - [판단 보류 경로 24개 생략 — 근거 미기록·미검사·불확실]

### 의사 현재 진단 비교: 폐색전증(Pulmonary embolism)[DX:Pulmonary embolism] — ASSESSED
- 4분류: A 지지 경로 2 · B 다른 질환만 연결(추가 검토 가능, 불일치 확정 아님) 0 · C 의료 지식 부족(반박 아님) 0 · D 검증된 반박 0(판단 불가(반박 관계 없음)) → 재검토 신호 없음 / 지식 부족 표시 없음
- 뒷받침 근거: Fever[HP:0001945] (경로 HP:0001945-SUGGESTS->DX:Pulmonary embolism#HSDN_LITERATURE_COOCCURRENCE); Cough[HP:0012735] (경로 HP:0012735-SUGGESTS->DX:Pulmonary embolism#HSDN_LITERATURE_COOCCURRENCE)
- 설명 부족 근거: 없음
- 명시적 충돌 근거: 판단 불가(이 그래프에 현재 진단을 반박하는 관계가 없음 → 근거 부족)
- 아직 확인하지 않아 판단할 수 없는 근거(31): CT 폐동맥조영 충만 결손[CONCEPT:ctpa_filling_defect] (NOT_RECORDED, 경로 CONCEPT:ctpa_filling_defect-SUGGESTS->DX:Pulmonary embolism#DISMECH_NO_REF); Cyanosis[HP:0000961] (NOT_RECORDED, 경로 HP:0000961-SUGGESTS->DX:Pulmonary embolism#HSDN_LITERATURE_COOCCURRENCE); Edema[HP:0000969] (NOT_RECORDED, 경로 HP:0000969-SUGGESTS->DX:Pulmonary embolism#HSDN_LITERATURE_COOCCURRENCE); Syncope[HP:0001279] (NOT_RECORDED, 경로 HP:0001279-SUGGESTS->DX:Pulmonary embolism#DISMECH_NO_REF); Obesity[HP:0001513] (NOT_RECORDED, 경로 HP:0001513-SUGGESTS->DX:Pulmonary embolism#HSDN_LITERATURE_COOCCURRENCE); Tachycardia[HP:0001649] (NOT_RECORDED, 경로 HP:0001649-SUGGESTS->DX:Pulmonary embolism#DISMECH_NO_REF); Angina pectoris[HP:0001681] (NOT_RECORDED, 경로 HP:0001681-SUGGESTS->DX:Pulmonary embolism#HSDN_LITERATURE_COOCCURRENCE); Right ventricular failure[HP:0001708] (NOT_RECORDED, 경로 HP:0001708-SUGGESTS->DX:Pulmonary embolism#DISMECH_QUOTE_IN_ABSTRACT) … 외 23개
- 현재 진단 확인에 쓸 수 있는 검사(지식원 기재, 환자 결과 없음): Computed tomographic pulmonary angiography[TEST:Pulmonary_Embolism:0]; Risk stratification by right ventricular function and cardiac biomarkers[TEST:Pulmonary_Embolism:1]; D-dimer with pretest probability assessment[TEST:Pulmonary_Embolism:2]
- 추가 검토 후보: 심낭염(Pericarditis)[DX:Pericarditis]: 임상 소견 근거 묶음 1 > 현재 진단 0 / 지식원 감별 목록(상대 질환 항목에 기재): DisMech eaa5fe99 Pericarditis.yaml differential_diagnoses['Pulmonary embolism'] (이름 일치); 결핵(Tuberculosis)[DX:Tuberculosis]: 임상 소견 근거 묶음 2 > 현재 진단 0

## 2단계(HIV 음성으로 정정)
- 그래프: REAL_KG_v1(HSDN+DisMech+HPO) · 기준 시점 as_of=2.0
- 정렬 = 임상 소견 근거 묶음 수 → 전체 묶음 수(공출현만 있는 묶음은 둘째 기준). 확률·진단 확정 아님. 모든 질환 노드 유지(제거 없음).

| 순위 | 질환 | 독립 지지 묶음 | 임상 소견 묶음 | 공출현만 묶음 | 지지 근거(묶음:최고 등급) | 충돌 | 음성/불충족 | 판단 보류 | 비활성 | 독립성 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 결핵(Tuberculosis)[DX:Tuberculosis] | 2 | 1 | 1 | {HP:0001945}:DISMECH_QUOTE_IN_ABSTRACT / {HP:0012735}:HSDN_LITERATURE_COOCCURRENCE | 0 | 0 | 17 | 1 | UNVERIFIED |
| 2 | 심낭염(Pericarditis)[DX:Pericarditis] | 1 | 1 | 0 | {HP:0001945}:DISMECH_NO_REF | 0 | 0 | 20 | 0 | N/A |
| 3 | 폐색전증(Pulmonary embolism)[DX:Pulmonary embolism] | 2 | 0 | 2 | {HP:0001945}:HSDN_LITERATURE_COOCCURRENCE / {HP:0012735}:HSDN_LITERATURE_COOCCURRENCE | 0 | 0 | 31 | 0 | UNVERIFIED |
| 4 | 심근염(Myocarditis)[DX:Myocarditis] | 1 | 0 | 1 | {HP:0001945}:HSDN_LITERATURE_COOCCURRENCE | 0 | 0 | 24 | 0 | N/A |

### 경로별 근거 추적
- **결핵(Tuberculosis)[DX:Tuberculosis]**
  - [뒷받침] [DISMECH_QUOTE_IN_ABSTRACT] Fever[HP:0001945] -SUGGESTS-> 결핵(Tuberculosis)[DX:Tuberculosis] · 조건: 양성 · 근거ID: V4-E_91-0 · 출처: DisMech eaa5fe99 Tuberculosis.yaml phenotypes['Fever'] freq=FREQUENT supports={'SUPPORT': 3} refs=PMID:11120618,PMID:18173876,PMID:31641790 quote_check={'SUPPORT:FOUND': 3} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Fever[HP:0001945] -SUGGESTS-> 결핵(Tuberculosis)[DX:Tuberculosis] · 조건: 양성 · 근거ID: V4-E_91-0 · 출처: HSDN Supp Data 3: 'Fever'–'Tuberculosis' PubMed co-occurrence=59, TF-IDF=36.52 (문헌 공출현, 확률 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Cough[HP:0012735] -SUGGESTS-> 결핵(Tuberculosis)[DX:Tuberculosis] · 조건: 양성 · 근거ID: V4-E_201-0 · 출처: HSDN Supp Data 3: 'Cough'–'Tuberculosis' PubMed co-occurrence=24, TF-IDF=31.55 (문헌 공출현, 확률 아님)
  - [비활성(적용 조건 불충족, 가역)] [LITERATURE_QUOTE_IN_TEXT] Cough[HP:0012735] -PART_OF-> TB-HIV-SYMPTOM-SCREEN(SCREENING_CRITERION)[RULE:TB-HIV-SYMPTOM-SCREEN] → Fever[HP:0001945] -PART_OF-> TB-HIV-SYMPTOM-SCREEN(SCREENING_CRITERION)[RULE:TB-HIV-SYMPTOM-SCREEN] → Night sweats[HP:0030166] -PART_OF-> TB-HIV-SYMPTOM-SCREEN(SCREENING_CRITERION)[RULE:TB-HIV-SYMPTOM-SCREEN] → Hemoptysis[HP:0002105] -PART_OF-> TB-HIV-SYMPTOM-SCREEN(SCREENING_CRITERION)[RULE:TB-HIV-SYMPTOM-SCREEN] → Weight loss[HP:0001824] -PART_OF-> TB-HIV-SYMPTOM-SCREEN(SCREENING_CRITERION)[RULE:TB-HIV-SYMPTOM-SCREEN] → HIV 감염(환자 보고)[CONCEPT:hiv_infection] -GATES-> TB-HIV-SYMPTOM-SCREEN(SCREENING_CRITERION)[RULE:TB-HIV-SYMPTOM-SCREEN] → TB-HIV-SYMPTOM-SCREEN(SCREENING_CRITERION)[RULE:TB-HIV-SYMPTOM-SCREEN] -SUGGESTS-> 결핵(Tuberculosis)[DX:Tuberculosis] · 조건: [SCREENING_CRITERION] HP:0012735=SATISFIED(양성); HP:0001945=SATISFIED(양성); HP:0030166=INDETERMINATE(NOT_RECORDED: 판단 보류); HP:0002105=INDETERMINATE(NOT_RECORDED: 판단 보류); HP:0001824=INDETERMINATE(NOT_RECORDED: 판단 보류); CONCEPT:hiv_infection=UNMET(명시적 음성) · 근거ID: - · 출처: PMID:29196066 CHEST 2018 · quote_check=FOUND · 조건: HIV 감염자에서 WHO 증상(기침·발열·야간 발한·객혈·체중감소) 중 하나 → 결핵 평가 대상 · 제한: 선별 민감도 증가 서술 — 진단 확정 아님
  - [판단 보류 경로 17개 생략 — 근거 미기록·미검사·불확실]
- **심낭염(Pericarditis)[DX:Pericarditis]**
  - [뒷받침] [DISMECH_NO_REF] Fever[HP:0001945] -SUGGESTS-> 심낭염(Pericarditis)[DX:Pericarditis] · 조건: 양성 · 근거ID: V4-E_91-0 · 출처: DisMech eaa5fe99 Pericarditis.yaml phenotypes['Fever'] freq=None supports={} refs=없음 quote_check={} (AI 큐레이션 — 인용 일치는 내용 검증 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Fever[HP:0001945] -SUGGESTS-> 심낭염(Pericarditis)[DX:Pericarditis] · 조건: 양성 · 근거ID: V4-E_91-0 · 출처: HSDN Supp Data 3: 'Fever'–'Pericarditis' PubMed co-occurrence=53, TF-IDF=32.80 (문헌 공출현, 확률 아님)
  - [판단 보류 경로 20개 생략 — 근거 미기록·미검사·불확실]
- **폐색전증(Pulmonary embolism)[DX:Pulmonary embolism]**
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Fever[HP:0001945] -SUGGESTS-> 폐색전증(Pulmonary embolism)[DX:Pulmonary embolism] · 조건: 양성 · 근거ID: V4-E_91-0 · 출처: HSDN Supp Data 3: 'Fever'–'Pulmonary Embolism' PubMed co-occurrence=43, TF-IDF=26.61 (문헌 공출현, 확률 아님)
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Cough[HP:0012735] -SUGGESTS-> 폐색전증(Pulmonary embolism)[DX:Pulmonary embolism] · 조건: 양성 · 근거ID: V4-E_201-0 · 출처: HSDN Supp Data 3: 'Cough'–'Pulmonary Embolism' PubMed co-occurrence=22, TF-IDF=28.92 (문헌 공출현, 확률 아님)
  - [판단 보류 경로 31개 생략 — 근거 미기록·미검사·불확실]
- **심근염(Myocarditis)[DX:Myocarditis]**
  - [뒷받침] [HSDN_LITERATURE_COOCCURRENCE] Fever[HP:0001945] -SUGGESTS-> 심근염(Myocarditis)[DX:Myocarditis] · 조건: 양성 · 근거ID: V4-E_91-0 · 출처: HSDN Supp Data 3: 'Fever'–'Myocarditis' PubMed co-occurrence=25, TF-IDF=15.47 (문헌 공출현, 확률 아님)
  - [판단 보류 경로 24개 생략 — 근거 미기록·미검사·불확실]

### 재계산으로 바뀐 경로
- RULE:TB-HIV-SYMPTOM-SCREEN->DX:Tuberculosis: 뒷받침 → 비활성(적용 조건 불충족, 가역) (DISABLED)

### 의사 현재 진단 비교: 폐색전증(Pulmonary embolism)[DX:Pulmonary embolism] — ASSESSED
- 4분류: A 지지 경로 2 · B 다른 질환만 연결(추가 검토 가능, 불일치 확정 아님) 0 · C 의료 지식 부족(반박 아님) 0 · D 검증된 반박 0(판단 불가(반박 관계 없음)) → 재검토 신호 없음 / 지식 부족 표시 없음
- 뒷받침 근거: Fever[HP:0001945] (경로 HP:0001945-SUGGESTS->DX:Pulmonary embolism#HSDN_LITERATURE_COOCCURRENCE); Cough[HP:0012735] (경로 HP:0012735-SUGGESTS->DX:Pulmonary embolism#HSDN_LITERATURE_COOCCURRENCE)
- 설명 부족 근거: 없음
- 명시적 충돌 근거: 판단 불가(이 그래프에 현재 진단을 반박하는 관계가 없음 → 근거 부족)
- 아직 확인하지 않아 판단할 수 없는 근거(31): CT 폐동맥조영 충만 결손[CONCEPT:ctpa_filling_defect] (NOT_RECORDED, 경로 CONCEPT:ctpa_filling_defect-SUGGESTS->DX:Pulmonary embolism#DISMECH_NO_REF); Cyanosis[HP:0000961] (NOT_RECORDED, 경로 HP:0000961-SUGGESTS->DX:Pulmonary embolism#HSDN_LITERATURE_COOCCURRENCE); Edema[HP:0000969] (NOT_RECORDED, 경로 HP:0000969-SUGGESTS->DX:Pulmonary embolism#HSDN_LITERATURE_COOCCURRENCE); Syncope[HP:0001279] (NOT_RECORDED, 경로 HP:0001279-SUGGESTS->DX:Pulmonary embolism#DISMECH_NO_REF); Obesity[HP:0001513] (NOT_RECORDED, 경로 HP:0001513-SUGGESTS->DX:Pulmonary embolism#HSDN_LITERATURE_COOCCURRENCE); Tachycardia[HP:0001649] (NOT_RECORDED, 경로 HP:0001649-SUGGESTS->DX:Pulmonary embolism#DISMECH_NO_REF); Angina pectoris[HP:0001681] (NOT_RECORDED, 경로 HP:0001681-SUGGESTS->DX:Pulmonary embolism#HSDN_LITERATURE_COOCCURRENCE); Right ventricular failure[HP:0001708] (NOT_RECORDED, 경로 HP:0001708-SUGGESTS->DX:Pulmonary embolism#DISMECH_QUOTE_IN_ABSTRACT) … 외 23개
- 현재 진단 확인에 쓸 수 있는 검사(지식원 기재, 환자 결과 없음): Computed tomographic pulmonary angiography[TEST:Pulmonary_Embolism:0]; Risk stratification by right ventricular function and cardiac biomarkers[TEST:Pulmonary_Embolism:1]; D-dimer with pretest probability assessment[TEST:Pulmonary_Embolism:2]
- 추가 검토 후보: 심낭염(Pericarditis)[DX:Pericarditis]: 임상 소견 근거 묶음 1 > 현재 진단 0 / 지식원 감별 목록(상대 질환 항목에 기재): DisMech eaa5fe99 Pericarditis.yaml differential_diagnoses['Pulmonary embolism'] (이름 일치); 결핵(Tuberculosis)[DX:Tuberculosis]: 임상 소견 근거 묶음 1 > 현재 진단 0
