# STEP29 인계 — Korean Clinical NLU (자동 실행하지 않음)

## STEP28.5 가 넘기는 인터페이스
`extract_symptom_spans.extract_kiwi(text)` → 구문 목록:
`{span_text, start, end, clause_text, noun_phrase, head_noun, predicate, pred_class(PAIN/OCCUR/ABSENT/OTHER/NONE), query_ko, polarity, temporal, temporal_scope_confirmed=false, subject}`
`bilingual_retriever.Retriever().run(text, "PARALLEL")` → 구문별 `{category, concept, attributes(site·E_55 값), display, reason, evidence_ko, evidence_en, …, raw_preserved}`

예: "어제부터 코피가 나고 머리가 아파요. 열은 없어요." → [코피가 나: UNKNOWN(한·영 연결 없음), 시점 '어제부터'(범위 미확정)] [머리가 아파: pain + 머리] [열은 없: fever, NEGATIVE]

## STEP29 가 맡을 것(이번에 구현·주장하지 않음)
- 부정 범위(무엇을 부정하는가) · 시점 표현의 적용 범위(어제부터 → 코피·두통 둘 다?) · 주체(본인/타인) 판정 · 복수 증상 사이 관계
- 기준선: 제품 매퍼(부정 처리 일부, 구토→오심 오매핑 주의) · STEP26 COMPLEX 정규식

## 먼저 정할 것(사용자)
- 77 밖 증상의 한국어 연결 자원: MDRKOR(MedDRA 한국어) 이용 조건 확인 / 사람 검토 소량 대응표 / 격리 LLM 대응표(SILVER, 과금 승인)
- 평가 문장 출처(사람 검토 Gold 소량 / 격리 LLM SILVER / AI-Hub 신청)
