# Context NLU Policy(STEP29.1, 연구용)

정본: `scripts/nlu_pipeline_v2.py`·`evaluative_negation.py`·`resolution_temporality.py`·`mention_context_validator.py`·`unsupported_input_guard.py` 문서열.

| 단계 | 추가 내용 |
|---|---|
| P1·P2 | STEP29 NLU 그대로(P2 는 검사기만 v5) |
| P3 | 평가형 부정(괜찮·멀쩡·정상이다·문제없 → ABSENT, 추정 동반 → ABSENT+확신 낮음, '괜찮지 않' → PRESENT, 이중 부정 → POSSIBLE) · 개선 술어 부정(안 내려 → 지속 PRESENT) · 개념 어휘 속 부정('입맛이 없음') · 결핍 표현(힘·기운·입맛 + 없) · 간접 의문 + 모르겠 → POSSIBLE |
| P4 | 해소 단서 절(평가·개선 술어, 대상 명사 없음) → 같은 문장 앞 절 또는 앞 문장 마지막 절의 PRESENT 증상을 RESOLVED(근거·위치 기록, certainty POSSIBLE) · 다른 증상이 있는 절은 해소 단서 아님 · 대상 불명확하면 변경 없음 |
| P5 | 통증 술어 ↔ 비통증 concept · 어휘 겹침 0 · 근거 의성어가 입력에 없음 · B4 단독 + 증상 단서 없음 → UNCERTAIN · 조건 '-면'·질문 → assertion UNKNOWN(보고 아님) |

원칙: '괜찮다' 키워드 치환 금지(그 mention 단위의 주 술어일 때만) · 과거 증상 삭제 금지(RESOLVED 로 표시) · ABSENT→PRESENT·타인→환자·과거→현재 양성 변환 금지 · model_input 은 표시만(applied=false).
