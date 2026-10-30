# STEP29 입력 인터페이스 — STEP28.7 정규화 검색기 출력(연구용)

구현: `scripts/safe_offline_retriever.py` `SafeOfflineRetriever().run(text) -> list[dict]`(구문마다 1개). CPU·오프라인·LLM 없음.
실제 예시 출력은 `outputs/candidate_safety_analysis.csv`(probe) · `data/eval_rows.csv`.

## 필드

| 필드 | 의미 | 상태 |
|---|---|---|
| source_text | 입력 원문(그대로) | 구현 |
| span_text · span_start · span_end | STEP28.5 kiwipiepy 구문·위치 | 구현(검증 안 됨) |
| normalized_expression | 조사 제거·공백 제거 키 | 구현 |
| status | EXISTING_CANONICAL · EXISTING_COMPOSITE · EXISTING_SUBTYPE · NEW_ONTOLOGY_CANDIDATE · NON_SYMPTOM · UNKNOWN_SYMPTOM · UNCERTAIN | 구현 |
| canonical_id | 77 canonical(기존·속성) 또는 하위의 부모 | 구현 |
| ontology_id · ontology_source · concept_name | 신규·하위 후보의 HPO/SNOMED id(SNOMED 이름은 LOCAL_ONLY 로 가림) | 구현 |
| relation_to_existing | EXISTING · EXISTING_SYNONYM · EXISTING_SUBTYPE · NEW_INDEPENDENT_CONCEPT · UNCERTAIN | 구현 |
| evidence_level | LEVEL_0–3(SILVER) · MEDMAP_VERIFIED_TERM · STEP27_B4 · PHRASE_PARTIAL | 구현 |
| audit_status · silver_audit · isolation_status | SILVER 출처일 때 감사·격리 상태 | 구현 |
| model_supported | 77 concept 이고 EXISTING_* | 구현 |
| usable_by_disease_model | model_supported 이고 MedMap 검증 용어·규칙·B4 근거일 때만. SILVER 단독·신규·하위 = False | 구현 |
| safe_for_candidate_display · display | 확인 질문에 보일 77 후보(신규·하위·충돌은 0) | 구현 |
| requires_confirmation | 모델 사용 불가 결과는 True | 구현 |
| polarity · temporal · subject | STEP28.5 규칙 추출값 전달 | **미검증 — STEP29 범위** |
| context_verified | 항상 False | 고정 |
| raw_preserved | 항상 True | 구현 |

## STEP29 가 채울 것

span 경계 검증 · negation · temporality(시작 시점 범위) · experiencer(환자 본인 여부) · uncertainty · symptom_group.
이번 단계에서 부정·시점·주체를 해결했다고 주장하지 않는다.

## 사용 제약

- NEW_ONTOLOGY_CANDIDATE·EXISTING_SUBTYPE 는 49질환 모델 입력 금지(model_supported False).
- SILVER 근거 결과는 확인 질문 없이 확정하지 않는다.
- 대응표 밖 새 표현은 77 한국어 경로로만 처리된다(77 밖 신규 증상은 사전 기반).
