# SafeNormalizer 출력 인터페이스(실험용, production 미연결)

모든 상태에서 `source_text` 원문을 보존한다. 어떤 상태도 환자 기록을 직접 수정하지 않는다.

| status | decision | condition | ux |
|---|---|---|---|
| KNOWN_SYMPTOM | AUTO_ACCEPT | B4 통과(COMPLEX 아님) | "호흡곤란으로 정리했어요." |
| UNCERTAIN | ASK_CONFIRMATION | 두 모델 동의하나 확신 부족 → 후보 최대 3 | "말씀하신 증상을 정확히 분류하지 못했어요. 다음 중 가까운 표현이 있나요?" |
| UNCERTAIN | NEEDS_CONFIRMATION | COMPLEX_INPUT 또는 판단 불가 | "조금 더 자세히 알려주실 수 있을까요?" (복합 문장은 증상별로 나눠 확인) |
| UNKNOWN_SYMPTOM | NEEDS_CONFIRMATION | 모델 불일치 + 증상 같음 | "현재 지원하는 증상 목록에서 정확히 연결되지 않았어요. 말씀하신 내용은 그대로 기록할게요." |
| NON_SYMPTOM | DO_NOT_MAP | non_symptom_score ≥ 0.65 | "증상보다는 질환이나 병력에 해당할 수 있어요. 증상 기록과 분리해서 확인할게요." |

## 예시 출력(illustrative smoke, 실제 실행 결과)

### 숨이 차요
```json
{
 "status": "KNOWN_SYMPTOM",
 "canonical_id": "dyspnea",
 "candidate_ids": [
  "dyspnea"
 ],
 "decision": "AUTO_ACCEPT",
 "requires_confirmation": false,
 "source_text": "숨이 차요",
 "model_evidence": {
  "linear_top1": "dyspnea",
  "linear_margin": 1.7908,
  "transformer_top1": "dyspnea",
  "transformer_score": 0.9865,
  "agreement": true,
  "train_similarity": 0.6154,
  "non_symptom_score": 0.2028
 },
 "reason": "B4"
}
```
### 코피가 나요
```json
{
 "status": "UNCERTAIN",
 "canonical_id": null,
 "candidate_ids": [
  "hemoptysis",
  "hematemesis",
  "cough"
 ],
 "decision": "ASK_CONFIRMATION",
 "requires_confirmation": true,
 "source_text": "코피가 나요",
 "model_evidence": {
  "linear_top1": "hemoptysis",
  "linear_margin": 0.0848,
  "transformer_top1": "hemoptysis",
  "transformer_score": 0.9225,
  "agreement": true,
  "train_similarity": 0.6,
  "non_symptom_score": 0.1207
 },
 "reason": "AGREE_LOW_CONFIDENCE"
}
```
### 고혈압
```json
{
 "status": "NON_SYMPTOM",
 "canonical_id": null,
 "candidate_ids": [],
 "decision": "DO_NOT_MAP",
 "requires_confirmation": false,
 "source_text": "고혈압",
 "model_evidence": {
  "linear_top1": "decreased_appetite",
  "linear_margin": 0.0149,
  "transformer_top1": "hemoptysis",
  "transformer_score": 0.9791,
  "agreement": false,
  "train_similarity": 0.2857,
  "non_symptom_score": 0.7507
 },
 "reason": "NON_SYMPTOM_SCORE"
}
```
### 몸이 좀 이상해요
```json
{
 "status": "UNKNOWN_SYMPTOM",
 "canonical_id": null,
 "candidate_ids": [],
 "decision": "NEEDS_CONFIRMATION",
 "requires_confirmation": true,
 "source_text": "몸이 좀 이상해요",
 "model_evidence": {
  "linear_top1": "chills",
  "linear_margin": 0.0012,
  "transformer_top1": "fatigue",
  "transformer_score": 0.8344,
  "agreement": false,
  "train_similarity": 0.5,
  "non_symptom_score": 0.1806
 },
 "reason": "DISAGREE_SYMPTOM_LIKE"
}
```

주의: UNKNOWN 은 진단이 아니다. NON_SYMPTOM 은 '증상 기록에 자동 매핑하지 않음'이지 삭제가 아니다. model_evidence 의 점수는 확률이 아니다.
