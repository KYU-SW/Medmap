# STEP31 인계(연구용 제품 연동 실험 — 사용자 승인 전 시작 금지)

- 판정 근거: outputs/integration_verdict.json(공식) · outputs/exploratory_g10_v2.json(EXPLORATORY) · docs/step30_report.md
- 공식 STEP30_RESULT = REGRESSION(G10 검사기 오탐) → STEP31_READINESS = NO_GO. EXPLORATORY(검사기 v2) = PARTIAL_FEASIBILITY / CONDITIONAL_GO.
  STEP31 을 하려면 먼저 사용자가 이 둘 중 무엇을 기준으로 할지 정해야 한다.

## 진입점
- `scripts/doctor_integration_adapter.py analyze(text)` → packet(step30-doctor-review-v0) · `model_input_eligibility.stage_a/stage_b` ·
  `clinician_confirmation_simulator.apply_decisions` · `blind_workflow_simulator.simulate`(제품 doctor_view in-process)

## 제품 연결 전에 필요한 변경(제품 코드 — 이번 단계에서는 하지 않음)
1. Doctor 화면: 'AI 추출 후보' 영역 + 항목별 확인 UI(있음·없음·보류, A 이외 범주는 재분류 사유 입력). 질환 후보 영역과 분리, 블라인드 단계에서도 표시 가능.
2. 확인 결과 → PatientState 경로: 현재 세션 시작은 exact-k(k3 = 추가 관측 3개) 계약. 의사 확인 증상을 넣으면 model_context_match 가 깨지므로
   (a) 별도 '확인 소견' 묶음으로만 표시 (b) k 문맥 재정의 중 하나를 제품 결정으로 정해야 함.
3. 변환표(data/evidence_mapping_candidates.csv) 의사 검토 — 특히 pain→E_53, cough→E_201, dyspnea→E_66, palpitations→E_155 일반형 선택과 1:N 미변환 4개.
4. NLU 의미 오류가 STAGE_A 로 올라오는 문제(관용구 '열이 받쳐'→발열, '가슴 쪽이 이상'→두근거림, '피가 섞인 기침'→기침으로 객혈 손실,
   '가슴이 답답'→두근거림): STAGE_A 를 '확인 버튼 기본값'으로 쓰지 말 것. NLU 수정은 별도 단계.
5. 음성(ABSENT) evidence 입력 정책 — 현재 금지. 허용하려면 모델 스키마(NEG 열)와 의사 확인 절차 검증 필요.
6. 실행 위치·자원: CPU 전체 경로 p95·RSS 는 outputs/latency.json·memory.json. 서버 안 상주 시 메모리 예산 확인.
7. 검사기: G10 금지 키 검사는 어댑터 필드에만(NLU 원본 'candidates' 는 증상 concept 후보). 다음 단계 검사기는 실제 NLU 전체 키 목록과 먼저 대조.

## 남은 한계
합성 문장만 · 평가 작성자 = 규칙 작성자 · 사람 검증 0 · 실제 ASR 전사문 미평가 · dummy 확인 정책 2개만.
