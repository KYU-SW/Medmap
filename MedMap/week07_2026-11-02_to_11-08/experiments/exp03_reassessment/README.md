# EXP-03 Temporal Evidence & Diagnostic Reassessment Safety-Net — 합성 단계(2026-11-03)

- 목적: 가상 의사 가설(SIMULATED_WD)과 시간순 증거를 비교해 지지·모순·대기·불확실을 구분하고, 재검토 알림을 미래정보 누출 없이 출처와 함께 내는지 검증. 질병 분류·확률 없음. 실제 환자 counted run 없음.
- 프로토콜 `PROTOCOL.md`(구현 전 고정, 변경은 끝 '변경 기록'에만).
- 재사용(수정 없음): EXP-01b 그래프 SUGGESTS 간선 · EXP-02 동결 v2/v3b 분류기(`ext_pe_eval_v3.predict_variant`, 읽기 전용).

| 파일 | 내용 |
|---|---|
| `reassess.py` | Evidence·HypothesisEvent·Timeline(출처 없음·다른 체류 거부) · P-AVAIL(available_at 기준, 없음·역전 제외) · 정정 · 규칙 R1–R9 · 요약 상태 · 알림 AL1/AL2 · session 로그(해제 사유) |
| `ct_bridge.py` | 합성 판독문 → v2/v3b 분류 → IMAGING_REPORT 증거(만성·불확실·보류 보존) |
| `scenarios.py` | CASE A–L + 보조(A2·C2·C5·C6) 18개, 체크포인트 65, 기대 출력 고정 · 거부 사례 C3·C4 |
| `baselines.py` | BASELINE-N(관측 시각·정정 무시 단순 집계, 새 비교 대상) · BASELINE-E(기존 EXP-01b) |
| `tests/test_exp03.py` | 실험 A(누출 성질)·B(상태 전이·출처)·C(잘못된 알림)·v3b 연결 — 10 |
| `fault_injection.py` | 대조 + 결함 7종 |
| `run_exp03.py` | 세 방식 채점·v2/v3b 비교 → 공개 JSON·보고서 |
| `mimic_time_audit.py` | 실제 MIMIC 시간정보 집계(봉인 추출 로컬 처리, 집계만) |

결과: `outputs/exp03_20261103_1013/`(EXP03_REPORT_ko.md) · `outputs/fault_injection_20261103_1012/` · `outputs/mimic_time_audit_20261103_1013/`.
한계: 합성 규칙 정합성일 뿐 의학적 타당성·실제 오진 탐지·임상 안전성 검증 아님. R2(명시 음성 CTPA = 모순)는 시스템 정의 규칙. 기준선 상태 일치율 차이는 상태 어휘(PENDING·UNKNOWN 없음) 차이가 크게 섞여 있어 우월성 근거 아님.
