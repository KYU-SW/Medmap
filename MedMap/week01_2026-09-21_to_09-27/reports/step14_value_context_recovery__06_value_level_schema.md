# Value-level patient evidence 표현 스키마 (STEP 14)

단일 CUI로 억지 축약하지 않고 `base concept + attribute + context + value`로 분해한다. 매핑 실패는 unknown이지 negative evidence가 아니다.

| 필드 | 내용 | 표준 자원 역할 |
|---|---|---|
| evidence_id | DDXPlus E_x | — |
| base_concept / base_cui / base_snomed / base_hpo | 핵심 임상 개념(증상·징후·질환). Step 8 MRCONSO exact 매핑 재사용 | 증상·징후: SNOMED CT / UMLS / HPO(+DisMech 등 기존 KB); 질환: SNOMED/UMLS/MONDO |
| concept_2 / operator | 복합 질문(AND/OR)의 두 번째 atomic concept — 하나로 합치지 않음 | 동일 |
| attribute_location | 통증·병변·부종 부위 (E_55/57/133/152: 165개 값) | SNOMED CT body structure (매핑 PENDING) / UMLS |
| attribute_severity | 강도 0~10, 크기>1cm 등 | 자체 구조 필드; NIH CDE severity 형식 참고(형식 표준화용, 의학 근거 아님) |
| attribute_onset / attribute_duration / attribute_frequency | 발생 속도(E_59), 기간(last_2_weeks…), 횟수(≥2/년) | 자체 구조 필드 |
| context_history | PAST_MEDICAL_HISTORY / CURRENT_CONDITION | 질환 concept + HISTORY context |
| context_family | FAMILY_HISTORY(관계: mother, close_family…) | 질환 concept + FAMILY_HISTORY context |
| context_medication | 약물 사용력 | UMLS/SNOMED 약물 개념까지; **RXNORM_PENDING**(RxNorm 파일 미보유) |
| context_exposure / context_lifestyle | 노출·생활습관·직업·거주·여행 | UMLS/SNOMED 개념 있으면 연결, 없으면 normalized category |
| value_raw / value_normalized / unit | 원값, 정규화 유형(boolean / 0-10 ordinal / body_site_code / categorical), 단위 | — |
| mapping_status / mapping_source / mapping_grade | Step 8 상태, 출처, AUTO_HIGH_CONFIDENCE / AUTO_REVIEW_REQUIRED / MANUAL_REQUIRED / UNMAPPABLE | — |

예시
- "오른쪽 아랫배가 8점 정도로 아파요" → base=Abdominal pain(C0000737), attribute_location=Right lower quadrant(SNOMED body structure), attribute_severity=8/10
- "3일 전부터" → attribute_onset/duration=3 days (개념 아님)
- "천식 병력" → base=Asthma(C0004096), context_history=PAST_MEDICAL_HISTORY
- "어머니가 심근경색" → base=Myocardial infarction, context_family=FAMILY_HISTORY(mother)
- "천식이 있거나 기관지확장제 사용" → base=Asthma, concept_2=Bronchodilator agent, operator=OR, context_medication=MEDICATION_USE(RXNORM_PENDING)

Expanded eligibility: EXTERNAL_USABLE_FULL(기존 83) / EXTERNAL_USABLE_PARTIAL(base concept 비교 가능, 위치·강도·시간 속성은 외부 질환지식 부재) / STRUCTURED_ONLY(환자 기록으로 저장, 현재 disease-finding verifier엔 직접 못 씀: 과거력·가족력·약물·노출·생활·인구·시간필드) / UNUSABLE. 검사 결과(TEST_RESULT)는 DDXPlus에 없음 → LOINC 미사용(TEST_STANDARD_PENDING).
