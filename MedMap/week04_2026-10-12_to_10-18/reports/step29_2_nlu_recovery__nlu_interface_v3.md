# STEP29.2 NLU 인터페이스 v3(연구용)

`scripts/nlu_pipeline_v3.py` — `analyze(text, policy) -> {"source_text", "level", "mentions", "context"}`.
정책: `S29`(STEP29 원본) · `S291`(STEP29.1 원본) · `V3_B0`–`V3_B3`. 선택 정책은 `data/policy_freeze.json` 의 `SELECTED_POLICY`.

## mention 필드(STEP29 필드 + 추가)
- 원문: `source_text`(입력 그대로) · `raw_span == source_text[span_start:span_end]` · `source_sentence`(분석한 하위 문장) · `sentence_index` · `sentence_span`
- concept: `status`(EXISTING_CANONICAL/COMPOSITE/SUBTYPE · NEW_ONTOLOGY_CANDIDATE · UNCERTAIN · UNKNOWN_SYMPTOM · NON_SYMPTOM) · `canonical_id` · `ontology_id` ·
  `guard_blocked_concept`(가드가 막은 원 concept) · `eval_site_concept`(부위만 평가형 부정에서 보류한 concept) · `guard_reasons` · `b4_guard_detail` · `b4_evidence`
- 단언: `assertion`(PRESENT · ABSENT · POSSIBLE · UNKNOWN) · `assertion_basis` · `assertion_certainty`(LOW = 확인 필요) · `requires_confirmation`
- 시점: `temporality` = **사건 시점**(CURRENT · ONGOING · PAST · UNKNOWN — 해소 연결이 덮어쓰지 않음) · `onset_text` · `duration_text` · `frequency_text` · `time_scope`
- 현재 상태(새 필드): `current_status` ∈ UNSPECIFIED · RESOLVED · IMPROVING · PERSISTING ·
  `resolution` = {cue_text, cue_start, cue_end, basis, cue_kind(RES_EVAL·RES_HEALED·RES_STOPPED·RES_NONE·RES_PAINNEG·IMPROVE·LATER_ABSENT), strength(STRONG·MODERATE·WEAK), certainty}
- 주체: `experiencer`(PATIENT · OTHER_PERSON · MULTIPLE) · `experiencer_basis`
- 모델 입력(표시만): `model_input` = {eligible, polarity, applied: false}. eligible 조건 = STEP29 규칙 + certainty LOW·UNKNOWN·POSSIBLE 불가 + RESOLVED 인 PRESENT 불가.

## context
- `sentences`(분리 근거·kiwi 비교·채움말) · `dropped_context`(증상 아님으로 돌린 구문과 사유) · `resolution_context`(대상 없는 해소 단서 등) · `triggers`

## 이전 스키마와의 대응
- STEP29/29.1 은 해소를 `temporality=RESOLVED` 로 덮어썼다. v3 에서 같은 정보는 `current_status=RESOLVED` 이고 사건 시점은 보존된다.
  이전 채점기에 넣을 때는 `evaluate_nlu.legacy_view` 처럼 `current_status=RESOLVED → temporality=RESOLVED` 로 바꿔 쓴다.
- 제품·PatientState·49질환 모델 연결 없음(연구용).
