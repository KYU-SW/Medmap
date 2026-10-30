# STEP30 인계(연구용 연결 설계 입력)

- 진입점: `exp/step29_3_concept_retrieval_repair/scripts/step29_2_adapter.py` 의 `analyze(text, "R2")` — STEP29.2 mention 스키마 + `retrieval`(via·query·tier·basis·원래 상태) ·
  `normalization`(original_phrase·lemma_candidates·core_predicate·anatomical_site·symptom_modifiers·negation) · `semantic_conflict`/`semantic_refinement` · `b4_path`.
- 판정: STEP29_3_RESULT = PARTIAL_IMPROVEMENT · STEP30_READINESS = CONDITIONAL_GO. 제품·PatientState·49질환 모델 연결 금지(model_input.applied = false).
- 남은 위험: 합성 평가뿐(사람 검증 0)·규칙과 평가 데이터 작성자가 같음 · 단서 없는 '목' 통증 해석 · 검색기 사전 대응 오류(누런 가래 → 콧물 E_182 등)는 의미 규칙으로만 막음 · 실제 ASR 전사문 미평가.
