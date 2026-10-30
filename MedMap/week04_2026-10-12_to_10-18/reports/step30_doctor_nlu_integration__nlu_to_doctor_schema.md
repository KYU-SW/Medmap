# NLU → Doctor packet 스키마(step30-doctor-review-v0)

## packet
| 키 | 내용 |
|---|---|
| schema_version | `step30-doctor-review-v0` |
| research_simulation · clinical_validation · human_verified_gold · production_ready | `true` · `NONE` · `0` · `false` (모든 packet) |
| source_text | 입력 원문 그대로 |
| items[] | 아래 item |
| sections | patient_said{source_text, sentences} · confirmed · ai_candidates(A) · negated(C) · historical(D) · other_person(E) · new_standard_candidates(B) · needs_confirmation(F·H) · non_symptom_context(G) — 값은 item_id 목록 |
| model_input | applied=false · auto_input_count=0 · stage_a_technically_eligible[] · stage_b_clinician_confirmed[] · patient_state_delta{} |
| nlu_context | NLU context 원본(문장·dropped_context·masked_time·resolution_context) |

## item
| 필드 | 출처 |
|---|---|
| source_text · raw_span · span_start · span_end · normalized_phrase · canonical_id · ontology_id · assertion · temporality · experiencer · model_supported · evidence_level | NLU 그대로 |
| requires_confirmation | 의사 화면에서는 항상 true. NLU 원래 값은 nlu_requires_confirmation |
| mapping_status | 어댑터 = NLU status |
| provenance | 어댑터 = NLU 진입점·정책 R2·policy_freeze SHA·evidence_sources·ko_tier·ko_evidence·retrieval·b4_path·b4_evidence·assertion_basis·experiencer_basis·relation_to_existing·isolation_status·silver |
| uncertainty_reason | 어댑터 = 범주 사유 + guard_reasons + NLU reason + semantic_conflict |
| category · category_name · category_reasons · section | 어댑터(아래 규칙) |
| label_ko · display_ko | 어댑터(통증은 '부위 표현' 덧붙임 — 부위 값은 변환하지 않음) |
| onset_text · time_scope · current_status · assertion_certainty | NLU 그대로 |
| eligibility | STAGE_A 판정(eligible·target_evidence·blocking_reasons 전부·auto_apply=false·negative_evidence{allowed=false}) |
| confirmation | {status: UNCONFIRMED · CONFIRMED_PRESENT · CONFIRMED_ABSENT · REJECTED, by, sim_step, source, stage_b} |
| nlu_original | NLU mention 원본 전체(deepcopy) — 손실 없음 확인용 |

NLU 가 증상 아님으로 돌린 구문(context.dropped_context)은 범주 G item(mapping_status = DROPPED_CONTEXT)으로 추가한다.

## 범주 규칙(우선순위)
G(NON_SYMPTOM) > E(OTHER_PERSON) > F(주체 MULTIPLE) > C(ABSENT) > D(PAST 또는 RESOLVED) > H(UNKNOWN_SYMPTOM) >
F(POSSIBLE·UNKNOWN·확실성 LOW·UNCERTAIN·가드·의미 충돌·시점 UNKNOWN·호전 중) > B(NEW_ONTOLOGY_CANDIDATE·EXISTING_SUBTYPE) >
A(EXISTING_CANONICAL·COMPOSITE + model_supported, 확인 요청·부분 일치 없음) / 그 밖 F.
