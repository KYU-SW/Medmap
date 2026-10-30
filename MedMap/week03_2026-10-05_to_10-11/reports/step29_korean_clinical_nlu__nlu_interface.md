# STEP29 NLU 출력 인터페이스

`clinical_nlu_pipeline.analyze(text, "NLU_P5")` → `{"source_text", "level", "mentions": [...], "context": {"triggers", "context_clauses"}}`

| mention 필드 | 의미 |
|---|---|
| raw_span · span_start · span_end · source_sentence | 원문 code point 구간(raw_span == source_text[start:end]) |
| unit_text · role | P5 에 보낸 단위 원문 · SINGLE/PRIMARY/ASSOCIATED/COORDINATED(ASSOCIATED 는 detail_of_span) |
| normalized_phrase · status · canonical_id · ontology_id · relation_to_existing | STEP28.8 P5 결과(상태 7종) |
| evidence_level · silver · isolation_status · evidence_sources · ko_evidence | 근거·SILVER 출처 |
| assertion · assertion_basis | PRESENT/ABSENT/POSSIBLE(UNKNOWN 예약) + 근거(부정 표지·이중 부정·추정·문장 추정) |
| temporality · onset_text · duration_text · frequency_text · time_scope · inherited_onset_candidate · resolution_text | CURRENT/PAST/ONGOING/RESOLVED/UNKNOWN · CLAUSE/UNCERTAIN/NONE(시점어 복사 안 함) |
| experiencer · experiencer_basis | PATIENT/OTHER_PERSON/MULTIPLE/UNKNOWN · EXPLICIT/INHERITED/ASSUMED_INTAKE_DEFAULT |
| attributes · trigger_text | 의성·의태어·수식어·'…듯이' 원문 · '숨 쉴 때마다' 같은 상황 문맥 |
| guard_reasons · guard_blocked_concept · candidates | 의미 충돌로 보류한 이유·원래 concept·SILVER 후보(표시·모델 없음) |
| model_supported · usable_by_disease_model · model_input{eligible, polarity, applied=false} · requires_confirmation | 49질환 모델 입력 후보 표시(실제 입력 안 함) |
| raw_preserved · context_verified(false) | 원문 보존 · 사람 검증 없음 |

시각 계산 없음(기준 시각 미제공 → 상대 시점 원문 보존). 정보가 없으면 null/UNKNOWN.
