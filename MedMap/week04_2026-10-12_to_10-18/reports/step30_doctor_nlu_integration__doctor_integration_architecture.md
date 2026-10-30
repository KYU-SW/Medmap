# STEP30 Doctor ↔ NLU 연구용 통합 구조

> 연구 시뮬레이션. 제품(~/medmap master)·PatientState·Doctor UI·8010 서버·49질환 모델은 바꾸지 않는다.

## 흐름
```
환자 발화(합성 문장)
 → STEP29.2 NLU(core3: 문장 분리·STEP29 분석·평가형 부정·해소 연결)
 → STEP29.3 R2 검색 계층(context_preserving_retriever N3 + B4 정책 B0)       ← exp/step29_3…/scripts/step29_2_adapter.analyze(text,"R2")
 → Doctor Integration Adapter(scripts/doctor_integration_adapter.py)
     · mention → item(범주 A–H, 원문 위치, 근거, nlu_original 전체 보존)
     · STAGE_A 판정(scripts/model_input_eligibility.py) — 표시만, auto_apply=false
 → 의사 검토 packet(step30-doctor-review-v0)  ← 질환 이름·점수·순위 없음
 → [dummy 의사 확인](scripts/clinician_confirmation_simulator.py)
     · CONFIRM_PRESENT 만 STAGE_B 후보(변환표·카탈로그 재확인, C/D/E/F 는 재분류 사유 필요)
     · patient_state_delta = 모델 입력 후보(applied=false) — 제품 PatientState 계약은 메모리 안에서만 확인
 → [블라인드 흐름](scripts/blind_workflow_simulator.py)
     · 제품 medmap.doctor_view.build_doctor_view 를 in-process 읽기 호출: WD PENDING → 후보 LOCKED,
       WD ENTERED 뒤에만 후보, 모델 입력 = STAGE_B 확인 evidence 만(격리 PatientState, 저장 없음)
 → 연구용 Preview(preview/index.html, 정적)
```

## 분리 원칙
- **NLU 추출 ≠ 의사 확인**: 모든 item 은 confirmation=UNCONFIRMED 로 시작, 의사 화면에서는 전부 '확인 대상'.
- **환자 증상 정보 ≠ 질환 예측**: packet 생성 경로는 DiagnosisEngine 을 호출하지 않는다(테스트로 확인).
- **기존 intake 매퍼·pre-visit cache 는 그대로**: STEP30 은 별도 경로이며 cache({evidence_id,status}) 형식을 흉내 내지 않는다(확인 출처·confirmer 를 잃지 않기 위해).

## 파일
- scripts: inspect_product_contracts · inspect_nlu_interfaces · validate_schema · doctor_integration_adapter · model_input_eligibility ·
  clinician_confirmation_simulator · blind_workflow_simulator · evaluate_integration · benchmark_runtime · (보조) build_evidence_mapping ·
  check_case_overlap · freeze_prereg · protect_check · license_scan · run_tests · finalize_verdict · build_preview · build_report
- run_all.sh(1회) · run_twice.sh(2회 + 재현 비교, 공식 = 1회차)
