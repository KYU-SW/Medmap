# STEP29 인계 — Korean Clinical NLU (자동 실행하지 않음)

목표 예: "어제부터 코피가 나고 머리가 아파요. 열은 없어요."
→ [코피: 증상, UNKNOWN(77 밖, 원문 보존)] [머리 아픔: pain + site=머리] [열: fever, 부정(NEGATIVE)] [시간: '어제부터' 의 적용 범위 = 코피·두통 둘 다인지 확인] [주체: 환자 본인]

## 입력·출력 인터페이스(제안)

```json
{"utterance": "...",
 "mentions": [{"span": [0, 0], "text": "...", "subject": "PATIENT | OTHER | UNCLEAR", "polarity": "POSITIVE | NEGATIVE | UNCERTAIN",
               "temporal": {"expression": "어제부터", "scope_confirmed": false}, "normalization": "<STEP28 Expansion 출력 그대로>"}],
 "unresolved": [], "requires_confirmation": true}
```

## STEP28 에서 넘기는 것
- `scripts/evaluate_expansion.py::Expansion` — span 하나 → 범주·canonical·속성·표시 후보·원문 보존(단일 표현 정규화).
- 제품 매퍼(`medmap/intake/mapper.py`)는 부정·문장 경계를 이미 일부 처리 — STEP29 기준선으로 비교(구토→오심 오매핑 주의).
- STEP26 COMPLEX 정규식은 기준선일 뿐(regression 지원 문장 14.7% 를 COMPLEX 로 오판, STEP27).

## 먼저 정할 것(사용자)
- 평가 문장 출처: 사람 작성·검토 Gold(소량) / 격리 LLM 생성 SILVER(과금 승인) / AI-Hub(신청).
- 한국어 ↔ ontology 연결 자원(MDRKOR 이용 조건 등) — STEP28 의 77 밖 연결 병목.
- 금지 승계: 학습 표현과 평가 문장을 같은 세션이 작성하지 않는다 · weak/SILVER 를 Gold 로 부르지 않는다 · production·PatientState 변경 금지.
