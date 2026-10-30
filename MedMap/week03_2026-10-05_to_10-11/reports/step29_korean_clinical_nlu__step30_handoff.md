# STEP29 → STEP30 인수인계(연구용)

판정·수치 정본: `outputs/step29_verdict.json`(공식) · `outputs/exploratory_v2.json`(탐색, 공식 아님) · `docs/step29_nlu_report.md`.

- **공식: STEP29_RESULT = REGRESSION · STEP30_READINESS = NO_GO**(사전 고정 hard 게이트 G3·G4 FAIL). STEP30 은 자동 실행하지 않는다.
- G3 FAIL 은 검사기 v4 의 문장 단위 적용 결함(NLU 는 올바름), G4 FAIL 은 실제 NLU 오류('입맛은 괜찮아요' → PRESENT).
- 탐색 v2(검사기 mention 단위 + '괜찮' 평가형 부정)는 모든 게이트 통과 — 그러나 평가 결과를 본 뒤 만든 보완이라 일반화 근거 아님.

## STEP30(제품 연결) 전에 필요한 것

1. 검사기 v5: mention 단위 적용을 **사전 고정**, 정답 대조에 다중 구문 문장(비증상 + 증상 혼합) 포함.
2. 평가형 부정('괜찮다'·'문제없다'·'정상이다' 등) 규칙을 사전 고정하고, pilot_gold 가 아닌 새 자료로 확인(현재 덜 노출 자료 없음 — 사람 검토 소량 또는 실제 전사문 필요).
3. 주체 생략 기본값(PATIENT 가정) 정책 결정 · PAST·POSSIBLE·RESOLVED 의 PatientState 입력 규칙 설계(이번 단계는 model_input 표시만).
4. 남은 P5 결함(nkey 손실 일치, '토하' 모호, B4 오연결)과 NLU 한계(생략된 대상, 중간 부사절, '오늘은 괜찮아요' 절이 해소 단서로 안 쓰이는 경우).
5. 연결 불가 발화(should_link False) 중 auto 8/28 원인 분석.

## 진입점

- `scripts/clinical_nlu_pipeline.py` `analyze(text, "NLU_P5")` · 인터페이스 `docs/nlu_interface.md` · 구조 `docs/clinical_nlu_architecture.md`.
- 금지 유지: LLM·다운로드·설치 사전 승인, P5 원본·제품·PatientState·49질환 모델 변경 금지, 사후 판정 변경 금지, commit/push 는 지시 시.
