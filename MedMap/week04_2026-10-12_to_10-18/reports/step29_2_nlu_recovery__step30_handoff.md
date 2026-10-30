# STEP30 인계(연구용 연결 설계 입력)

- 진입점: `exp/step29_2_nlu_recovery/scripts/nlu_pipeline_v3.py` 의 `analyze(text, "V3_B0")` — mention 스키마는 docs/nlu_interface_v3.md.
- 판정: STEP29_2_RESULT = RECOVERY_PASS · STEP30_READINESS = CONDITIONAL_GO. 제품·PatientState·49질환 모델 연결 금지(model_input.applied = false 표시만).
- 남은 위험: 검색기(P5) 단계 concept 모호성 · 합성 평가뿐(사람 검증 0) · B4 단독 연결 정책 선택 결과(V3_B0) · 실제 ASR 전사문 미평가.
- 다음 후보(사용자 결정): 실제 전사문 소량 확보·사람 검토 / 검색기 모호성 수정 실험 / STEP30 연구용 인터페이스 설계.
