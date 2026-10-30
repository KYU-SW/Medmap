# Evaluator v5 Spec(STEP29.1)

정본: `scripts/evaluator_v5.py` 문서열. 검증: `scripts/validate_evaluator_v5.py` → `outputs/evaluator_validation.json`.

- 검사 단위 = mention. 규칙은 mention 범위(unit_text) + 그 mention 의 concept 에만 적용, 추위 단서만 문장 문맥 사용.
- 다른 구문의 질환·약물·검사 단어는 그 mention 판정에 쓰지 않는다(STEP29 v4 문장 단위 결함 제거).
- 규칙: SPAN_INVALID · EPISTAXIS_AS_BLEEDING · VOMIT_AS_NAUSEA · MODAL_VOMIT_AS_VOMITING · NAUSEA_AS_VOMITING · TREMOR_AS_CHILLS · BODY_PART_ONLY ·
  DRUG_OR_TREATMENT_TERM · DISEASE_TERM(핵어 명사구 + 나머지 범위 증상 단서 없음) · UNCERTAIN_AUTO_ACCEPT.
- 정답 대조(평가 전): 정상 = STEP28.8 정답 쌍 중 단일 concept + 혼합 문장 정상 mention 12 문장 · 오류 = 15 사례. 대조 중 수정 2회(핵어 명사구·위치 명사 한정·접두 포함) 후 SHA 고정.
- NLU 오류(정답과 다른 concept·assertion·주체·시점)는 계약 채점(contract_check_v2)으로 따로 센다 — 검사기 위반과 섞지 않는다.
- 한계: 규칙이 알려진 사례에서 나왔고, 정답 대조 자료도 합성·감사 표현(사람 검증 Gold 아님).
