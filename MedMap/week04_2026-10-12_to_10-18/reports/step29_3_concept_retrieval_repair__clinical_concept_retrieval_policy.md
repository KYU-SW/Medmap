# STEP29.3 임상 개념 검색 정책(연구용)

구현: `scripts/step29_2_adapter.py`(연결) · `korean_morphological_normalizer.py` · `context_preserving_retriever.py` · `semantic_disambiguator.py` · `b4_evidence_policy.py`.
STEP28.8 P5·STEP27 B4·STEP29/29.2 원본은 호출만 한다. 수치는 `step29_3_report.md`.

## 처리 순서(정책 R2 = 선택 정책)
1. STEP29.2 문장 분리 → 하위 문장마다 **시점 표현을 같은 길이 공백으로 가린 문자열**로 STEP29 분석(오프셋 보존, raw_span 은 원문에서 다시 자름).
   가린 시점어는 mention 의 `onset_text` 로 되돌리고 '…부터'면 ONGOING. 절 구조·해소 연결은 원문 기준.
2. '…할 때' 조건 절의 명시 주체를 다음 절의 주체 생략 mention 에 이어 준다.
3. 검색 계층(mention 단위):
   - 비증상 문맥(환경 진술·인식 표현) → NON_SYMPTOM.
   - 의미 규칙(`semantic_rules`)이 판단하면 그것을 먼저 적용(연결이 비었을 때만 채움, 근거 등급 RULE).
   - 규칙이 없으면 **표준 질의 재검색**: 부정 제거·주제 조사 은/는 → 이/가·어미 표준화('-어요'), 의성어·감각 부사는 보존. 증상 단서나 신체 부위가 없는 단위는 재검색하지 않음.
     채택 근거 등급 = EXACT·BOUNDARY·RULE·MODEL_B4(PHRASE·NGRAM 부분 일치 불채택).
   - 남은 미연결은 STEP28.7 감사 SILVER 표현과 정확 일치(KEEP_NEW_CANDIDATE → NEW_ONTOLOGY_CANDIDATE, MERGE_AS_EXISTING_RELATION → EXISTING_SUBTYPE, 보류·기각 제외).
4. B4 정책 B0(B4 단독 규칙 없음, STEP29.1 가드 + '점점' 보정). 모델 경로와 사전·규칙 경로를 `b4_path` 로 구분 기록.
5. model_input 표시만(applied = false). SILVER·SUBTYPE·불확실·해소된 증상은 모델 입력 불가.

## 보류 원칙
- STEP29/29.2 의 의도적 보류(가드 사유·부위만 평가형 부정·평가형 부정)는 재검색·의미 규칙이 덮어쓰지 않는다.
- 단일 유사도 점수·부분 문자열만으로 확정하지 않는다(G10).
- '목이 아파요'처럼 단서 없는 목 통증은 검색기의 기존 해석을 그대로 두며, 활용형 사이 결과만 일관되게 맞춘다(새로 확정하는 규칙 없음).

## 정책 비교군
R0 = STEP29.2 V3_B0 · R1 = V3_B3 · N1 부사 제거 재검색 · N2 수식어 보존 재검색 · R2(= N3) 의미 규칙·SILVER·비증상 문맥 · N4 = R2 + 의미 충돌 보류 · R3 = N4 + B4 충돌 보류 · R4 = N4 + B4 근거·충돌.
