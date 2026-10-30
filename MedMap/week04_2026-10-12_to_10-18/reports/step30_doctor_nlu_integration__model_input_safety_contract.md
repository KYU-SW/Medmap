# 모델 입력 안전 계약(연구용)

## STAGE_A — TECHNICALLY_ELIGIBLE(표시만, 입력 아님)
모두 만족해야 함(막는 이유는 전부 기록):
status ∈ {EXISTING_CANONICAL, EXISTING_COMPOSITE} · model_supported · is_symptom · 근거가 SILVER 단독 아님 · experiencer = PATIENT ·
assertion = PRESENT · 확실성 LOW 아님 · temporality ∈ {CURRENT, ONGOING} · current_status ∈ {UNSPECIFIED, PERSISTING} ·
NLU requires_confirmation 아님 · 가드 사유 없음 · 의미 충돌 없음 · 부분 일치(PHRASE) 아님 · NLU model_input eligible 이고 polarity = POSITIVE ·
변환표에 허용 규칙 있음 · 대상 evidence 가 카탈로그에 있고 binary·부모 없음·제외 질문 아님 · 범주 A(이중 장치).

## STAGE_B — CLINICIAN_CONFIRMED(모델 입력 후보, applied=false)
decision = CONFIRM_PRESENT · confirmer·source 기록 · 대상 evidence 가 승인 변환표의 대상이고 item concept 의 대상과 같음 ·
evidence 재확인(binary·부모 없음·제외 아님) · 범주 B·G·H 불가 · 범주 C·D·E·F 는 의사의 override_reason 이 있을 때만.
CONFIRM_ABSENT 는 기록만 — 음성 evidence 변환은 허용하지 않음(모델 스키마·정책 미검증).

## 자동 입력 금지(항상)
ABSENT · POSSIBLE · UNKNOWN · PAST · RESOLVED · OTHER_PERSON · NEW_ONTOLOGY_CANDIDATE · SILVER 단독 · HELD/미지원 canonical · 불명확한 속성 조합.
의사 확인 전 packet.model_input: applied=false · stage_b 빈 목록 · patient_state_delta 빈 객체.

## 변환표(data/evidence_mapping_candidates.csv)
- 1:1 concept → 그 evidence. 1:N concept 은 질문 원문이 한정어 없는 일반형일 때만(cough→E_201, dyspnea→E_66, pain→E_53, palpitations→E_155).
- 일반형이 정해지지 않는 concept(vomiting·fatigue·limb_weakness·decreased_appetite)·값 질문(E_55 부위 등)·SILVER 신규/하위는 변환 안 함.
- validation_status = ENGINEERING_DRAFT_UNVERIFIED(의사 검증 0). SNOMED·UMLS 열 없음.
