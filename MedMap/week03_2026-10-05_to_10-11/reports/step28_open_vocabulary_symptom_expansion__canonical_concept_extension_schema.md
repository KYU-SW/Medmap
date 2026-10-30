# 연구용 표준 증상 확장 스키마 (제안 — production·PatientState 미반영)

```json
{
  "concept_id": "NEW:HP:0000421",
  "status": "CANDIDATE | REVIEWED | REJECTED",
  "ontology_refs": [{"source": "HPO", "id": "HP:0000421", "version": "hp/releases/2026-09-01"},
                    {"source": "SNOMED", "id": "249366005", "version": "INT 20260901"},
                    {"source": "UMLS", "cui": "C0014591", "version": "2026AA"}],
  "relation_to_existing": [{"canonical_id": "EV:E_178", "relation": "NARROWER_THAN_EXISTING"}],
  "distinct_from": ["hemoptysis", "hematemesis"],
  "korean_terms": [{"term": "...", "evidence": "사람 검토 | 허용 라이선스 용어집", "verified": false}],
  "ontology_supported": true,
  "model_supported": false,
  "attributes_allowed": ["onset", "duration", "severity"],
  "review": {"reviewer": null, "date": null}
}
```

규칙
- `concept_id` 접두 `NEW:` = 연구용. 기존 77 id(`pain`, `EV:E_…`)와 이름공간이 겹치지 않는다. 같은 ontology id·같은 CUI 는 하나의 NEW id 만 가진다.
- 기존 77 과 같은 id·같은 CUI → 신규 생성 금지(DUPLICATE_OF_EXISTING). 속성 칸이 있는 기존 concept 의 하위(예 Headache ⊂ Pain) → 기존 + 속성.
- `ontology_supported` ≠ `model_supported`. 49질환 모델 입력은 DDXPlus 223 증거로 고정 — 신규 concept 은 `model_supported=false`, 진단 후보 계산에 쓰지 않는다.
- 한국어 표현 연결은 `korean_terms.verified=true`(사람 검토 또는 라이선스 확인된 한국어 용어집) 일 때만 자동 수락 후보가 된다.
- 원문(`source_text`)은 항상 별도 보존. 미지원 증상은 `UNKNOWN_SYMPTOM.raw_record` 로 저장(STEP27 routing_schema).
