# STEP25 — 어노테이션 스키마 감사

## 로컬 데이터 구조

```json
{
 "KBMC": {
  "n_rows": 6150,
  "n_unique_text": 6125,
  "n_misaligned": 0,
  "tagset": {
   "Disease-B": 10595,
   "Disease-I": 10089,
   "O": 124882,
   "Body-B": 5215,
   "Body-I": 1158,
   "Treatment-B": 1193,
   "Treatment-I": 839
  },
  "span_counts": {
   "Disease": 10632,
   "Body": 5226,
   "Treatment": 1194
  },
  "has_symptom_label": false,
  "has_negation_label": false,
  "has_temporality_label": false,
  "pii_pattern_rows": {
   "phone": 0,
   "email": 0,
   "rrn": 0,
   "url": 0
  },
  "unique_disease_spans": 4239,
  "note": "Symptom 라벨 없음. '호흡 곤란'·'근육 통증' 같은 증상 표현도 Disease 로 태깅(헤더 직후 예시 행에서 확인)"
 },
 "BERT_NER_KO": {
  "n_rows_train_plus_eval": 2189,
  "n_unique_text": 1830,
  "tagset": {
   "B-ST": 1267,
   "O": 26855,
   "I-ST": 133,
   "B-DS": 916,
   "B-BD": 1013,
   "I-DS": 353,
   "I-BD": 43
  },
  "span_counts": {
   "ST": 1267,
   "DS": 916,
   "BD": 1013
  },
  "n_ST_spans": 1267,
  "n_unique_ST_spans": 455,
  "has_symptom_label": "CATEGORY_ONLY(ST)",
  "has_concept_id": false,
  "has_negation_label": false,
  "has_temporality_label": false,
  "pii_pattern_rows": {
   "phone": 0,
   "email": 0,
   "rrn": 0,
   "url": 0
  }
 },
 "KO_MEDICAL_CHAT": {
  "n_dialogues": 1678,
  "n_client_turns": 9007,
  "n_first_client_turns": 1678,
  "n_unique_first_client_turns": 1677,
  "mean_first_turn_chars": 171.9,
  "has_any_label": false,
  "pii_pattern_rows": {
   "phone": 0,
   "email": 0,
   "rrn": 0,
   "url": 0
  },
  "provenance": "GPT-3.5 변환 생성문"
 }
}
```

## 외부 라벨 → MedMap 77 매핑

| dataset | external_label | canonical_id | grade | reason | used_for_accuracy |
|---|---|---|---|---|---|
| KBMC | Disease |  | NO_MATCH | 질병 범주(증상 표현도 섞여 태깅됨) — 질병 라벨을 증상 concept 으로 바꾸지 않음 | False |
| KBMC | Body |  | NO_MATCH | 신체 부위 = MedMap 에서는 concept 이 아니라 site 속성 | False |
| KBMC | Treatment |  | NO_MATCH | 치료 | False |
| BERT_NER_KO | ST | (77 중 미지정) | PARTIAL | '증상' 범주 라벨 — 어느 concept 인지 원본에 없음 | False |
| BERT_NER_KO | DS |  | NO_MATCH | 질병 | False |
| BERT_NER_KO | BD |  | NO_MATCH | 신체 부위(site 속성) | False |
| KO_MEDICAL_CHAT | (라벨 없음) |  | NO_MATCH | 라벨 없음 | False |
| AIHUB_98 | 증상/징후(카테고리) | (77 중 미지정) | PARTIAL | 카테고리 단위, 개별 증상 concept 아님 · 승인 전 원문 미확인 | False |
| AIHUB_208 | '증상별' 수집 단위 |  | UNCERTAIN | 안심존 데이터 — JSON 스키마·라벨 미확인 | False |

- EXACT/ACCEPTABLE 0건 → GOLD_CANDIDATE 0. 범주 라벨(ST·증상/징후)은 concept 을 지정하지 않음.
- 부정·시점 라벨: 세 데이터 모두 없음. 개인정보 패턴(전화·이메일·주민번호·URL): 0건.
- KBMC 는 증상 표현도 Disease 로 태깅 → 질병 라벨을 증상으로 바꾸지 않음(NO_MATCH).
