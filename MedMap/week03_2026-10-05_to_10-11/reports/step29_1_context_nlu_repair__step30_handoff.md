# STEP29.1 → 다음 단계 인수인계(연구용)

- 진입점: `scripts/nlu_pipeline_v2.py` `analyze(text, "P5")`(STEP29 출력 + 평가형 부정·해소·가드). P4 = 가드 없는 버전.
- 검사기: `scripts/evaluator_v5.py`(mention 단위, SHA 는 `outputs/evaluator_validation.json`). NLU 정답 비교는 `contract_check_v2.py`.
- 자료: 새 계약 42(개발 사용) · 전향적 합성 231(이번 평가로 노출됨) · pilot 274(노출).
- 판정·결함: `docs/step30_readiness.md`. 공식 NO_GO — STEP30 은 자동 실행하지 않는다.
- 금지 유지: LLM·다운로드·설치 사전 승인 · P5·STEP29 원본·제품·PatientState·49질환 모델 변경 금지 · 사후 판정 변경 금지 · commit/push 는 지시 시.
