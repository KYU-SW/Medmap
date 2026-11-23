# 기존 연구·구현 상태 점검 (2026-11-05)

출처: 로컬 프로젝트 메모리, `HANDOFF_MASTER.md` §48~§117, 각 실험 공개 결과 파일. 확인 못 한 항목은 UNKNOWN. 판정은 원문 그대로이며 재해석하지 않았다.

## 공통 사실
- 제품 master(977877f)는 EXP-01b·EXP-03 코드를 import 하지 않는다(`medmap/`·`medmap-web/src` 검색 0건). **연구 엔진은 제품에 통합되지 않았다.**
- 실제 의사의 Working Diagnosis 를 입력으로 시험한 실험은 없다. 재검토 정답도 없다.

## 실험별 상태
| 실험 | 연구 질문 | 데이터 | 알고리즘 | 공식 결과 | 한계 | 재사용 코드 | 재사용 금지 평가자료 | MedMap 역할 |
|---|---|---|---|---|---|---|---|---|
| EXP-SN-CORE-001 | WD 가 소견을 설명하는가(ACS·PE·심낭염) | 격리 작성 지식 ck-v0(216 fact), 평가 자료 미접근 | 격리 LLM 지식 작성·검증 | primary ACS–PE **NOT_EVALUABLE** | 해당 쌍 근거 부족 | 작성·검증 절차 문서 | 해당 실험 봉인분 | 지식 작성 절차 참고 |
| NBI-A0 | 구현 정합성 | 사전 계산값 | 결정적 재현 | CONFORMANT·VERIFIED | 재현까지만 | safety-net-nbi 코드 | — | 없음(참고) |
| NBI-B0a/c/d | MIMIC 가용성·시간 정렬 | MIMIC 로컬 | 집계 | COMPLETE·VERIFIED. ECG 시각 불확실, Troponin·D-dimer·흉부 CTA 가용 | 가용성만 | 시간 정렬 코드 | B0 분할 결과 | 시간 정책 근거 |
| NBI-B1/B1S | 측정값 분리도 | MIMIC | 층화 AUROC | Troponin ΔAUROC 0.08(0.06–0.11), B1S 는 MI 라벨 의존(SIGNAL_MOSTLY_REFERENCE_DEPENDENT), 축 중단 권고 | 참조 표준 의존·측정 선택 신호 | 코드 참고 | 동일 코호트 | 제품 기능 후보 아님 |
| EXP-00 | 데이터·실험 준비 | 로컬 자산 | 감사 | CONDITIONAL | 감사만 | `evidence_graph.py` 스키마 참고 | — | 참고 |
| EXP-01 | 음성 답·질문 선택 효과 | DDXPlus(합성 환자) | 확률표 기반 | FINAL: H1 **SAFETY_HOLD**, 채택 C, H3 SAFETY_FAIL | 합성·그래프 추론 아님 | exp/main_ai 동결(수정 금지) | FINAL 분할·DDXPlus 동일 분할 | 재검토 근거 아님 |
| EXP-01b | 그래프 추론 | HSDN·DisMech 등, DDXPlus 시연 | 5상태·규칙 그래프 | 진단 4·노드 94(현재 빌드 기준), explore2 top1 20%, 지식 부족 65%. 성능 주장 없음 | 질환 특이 관계 부재, 약화 간선 없음 | `graph_engine.py`, `knowledge_real_kg.py` 읽기 전용 | explore 사례 | B 그래프 팔의 출발점 |
| EXP-02 v2 | MIMIC 연결·PE 판독 추출 | MIMIC 추출(봉인), Ext-PE | 규칙 | 코호트 12,358 체류 | 공개 집계만 | `mimic_adapter` 읽기 전용 | 봉인 추출 | 추출 계층 참고 |
| EXP-02 v3b | CT 판독 급성 PE 추출 | Ext-PE | 규칙(부정 범위 개선) | TEST 1회: 특이도 0.9672, PPV 0.7788, 민감도 0.9982(보류 제외)·0.9252(보류=비양성), 보류 0.30. 동결 | EXP-04 증례에서 오분류 2건 관찰 | `ct_bridge.classify` 읽기 전용 | **Ext-PE TEST 재평가 금지** | Layer 1 PE 영상 추출기 |
| EXP-03 | 시간순 상태 관리 | 합성 18 시나리오 | 규칙 R1~R9 | 합성 65/65, 누출 0 | SIMULATED_WD, 합성 | `reassess.py` 읽기 전용 | 합성 시나리오(개발에 재사용 가능, 성능 근거 아님) | Layer 4 기준선 |
| EXP-03-TIME | 시간 정책 | 합성 | STRICT/S1/S2 | 합성 통과 | 실제 자료 없음 | `time_v1`·`time_v2` 읽기 전용 | — | Layer 4 정책 |
| EXP-MAI-003 | 실제 MIMIC 시간 불확실성 | 봉인 추출(미실행) | time_v2 | gate **NEEDS_FIX**, 실행 **NOT_TESTED**, 1회 표지 없음 | 공개 보호 MAJOR 2 | 동결 코드 수정 금지 | 표지 미소진 상태 유지 | 보류 |
| EXP-04 | 재검토 평가 자료 탐색 | SCT 공개 174, CC BY 증례 11 | 동결 엔진 | 임상 지표 NOT_EVALUABLE, SCT 진단 문항 엔진 연결 0, 증례 저자 변경 시점 알림 2/11 | 소표본·저자 서술 | 분석 스크립트 | SCT 공개분·증례 11건(이미 열람, 독립 평가 불가) | 한계 근거 |
| STEP29~29.3 | 한국어 임상 NLU | 합성 문장 | 규칙+검색 | 29·29.1 REGRESSION, 29.2 RECOVERY_PASS, 29.3 PARTIAL_IMPROVEMENT | 한국어 전용, 합성 | `nlu_pipeline_v3`(읽기 전용, symptom-ontology) | FROZEN 세트 | 의사 음성 후보 |
| STEP30 | NLU↔Doctor 통합 | 합성 72문장 | 시뮬레이션 | 공식 **REGRESSION**(검사기 오탐), 탐색 PARTIAL_FEASIBILITY. 공식 판정 유지 | STAGE_A 의미 오류 5, 제품 무수정 | `doctor_integration_adapter.analyze` | 같은 72문장 | 확인 UI 설계 참고 |

## 재사용 판단 요약
- **읽기 전용 연결 확인:** `reassess.relation·assess`, `ct_bridge.classify`, EXP-01b 그래프(이번 Adapter 로 실행 확인).
- **조사만 함(연결 미실행):** STEP29 파이프라인, STEP30 어댑터(다른 worktree, 한국어·합성 전용).
- **UNKNOWN:** B1/B1S 코드의 현재 재실행 가능성, 제품 `evidence.py` 와 새 구조의 대응(이번에 분석 안 함).

## 충돌 기록
- EXP-01b 노드 수: 34회차 기록 138, 현재 `build_real_graph` 호출 결과 94. 호출 인자·이후 정리 차이로 보이나 원인 미확인(UNKNOWN). 현재 실행값을 인용.
