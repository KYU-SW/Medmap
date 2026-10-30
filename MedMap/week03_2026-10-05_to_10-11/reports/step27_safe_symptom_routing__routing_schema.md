# STEP27 실험용 라우팅 인터페이스 (production 아님)

구현: `scripts/safe_symptom_router.py`(`route()` · `SafeSymptomRouter`). PatientState·제품 매퍼는 바꾸지 않는다.

```json
{
  "source_text": "코피가 나요",
  "status": "KNOWN_SYMPTOM | UNKNOWN_SYMPTOM | NON_SYMPTOM | UNCERTAIN | COMPLEX_INPUT",
  "canonical_id": null,
  "candidate_ids": [],
  "candidate_display_allowed": false,
  "decision": "AUTO_ACCEPT | ASK_CONFIRMATION | PRESERVE_RAW | DO_NOT_MAP | DEFER_TO_NLU",
  "requires_confirmation": true,
  "reason_codes": [],
  "raw_record": {
    "raw_expression": "...", "extracted_span": "...", "supported": false,
    "internal_candidate_ids": [], "uncertain_reason": []
  },
  "model_evidence": {
    "linear_top1": "...", "linear_margin": 0.0, "transformer_top1": "...", "transformer_score": 0.0,
    "agreement": true, "train_similarity": 0.0, "non_symptom_score": 0.0,
    "symptom_cue": false, "non_type_cue": "", "candidate_similarity": {}, "candidate_transformer_prob": {}
  }
}
```

## 상태 ↔ 결정

| status | decision | canonical_id | candidate_ids(표시) | requires_confirmation | 의미 |
|---|---|---|---|---|---|
| KNOWN_SYMPTOM | AUTO_ACCEPT | 1개 | [canonical] | false | B4 자동 수락(두 모델 동의 + KoE ≥ 0.98 + 학습 표현 유사도 ≥ 0.6) |
| UNKNOWN_SYMPTOM | PRESERVE_RAW | null | [] | true | 증상 근거는 있으나 지원 concept 연결 근거 부족. 원문 그대로 기록 |
| UNCERTAIN | ASK_CONFIRMATION | null | 표시 조건 통과 후보만(0–3) | true | 지원 후보가 있으나 자동 기준 미달, 또는 증상 여부 근거 부족(후보 없이 자유 설명 요청) |
| NON_SYMPTOM | DO_NOT_MAP | null | [] | false | 질환·약물·치료·검사 등 비증상 유형의 적극적 근거. 증상 기록과 분리, 원문 보존 |
| COMPLEX_INPUT | DEFER_TO_NLU | null | [] | true | 부정·과거·타인·복수 연결어·40자 초과(정규식). 단일 증상 자동 수락 금지 |

## 규칙

- 지원하지 않는 증상을 다른 증상으로 바꾸지 않는다: UNKNOWN 은 canonical null, 표시 후보 0(내부 후보는 `raw_record.internal_candidate_ids` 에만).
- NON_SYMPTOM 도 `source_text`·`raw_record.raw_expression` 을 지우지 않는다.
- 낮은 confidence 는 NON 근거가 아니다: NON = 증상 어휘 단서 없음 AND [(비증상 유형 어휘 단서 AND 비증상 점수 ≥ t_type) OR 비증상 점수 ≥ t_strong].
- 후보 표시(POLICY_D): 후보 c 의 KoE 확률 ≥ d_conf AND 입력 ↔ c 학습 표현 bigram 유사도 ≥ d_sim. 통과 0 이면 증상 근거 → UNKNOWN, 없으면 후보 없는 UNCERTAIN.
- 임계값(DEV 선택): `outputs/routing_selection.json` `params`.
- 알려진 한계(보고서 §10): 질환명 NON 인식 손실, '코피가 나요' 의 hemoptysis 후보 표시 잔존, COMPLEX 정규식 과잉 판정.
