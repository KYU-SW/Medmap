# 기술 검증 결과 — IMPLEMENTATION CHECK

전문가 판단 성능·임상 정확도가 아니다. 제한 자료·외부 호출 없음.

생성 2026-11-05T11:38:11

## 단위 테스트
- 32개, 결과 OK

## 변이 시험
- 20종 중 탐지 19, 생존 ['ai_confirm_without_record']
- 생존 설명: {'ai_confirm_without_record': '동치 변이 — 빈 confirm_ref 는 Provenance 검사가 같은 ValueError 로 거부(이중 방어)'}

## SCT 공개 문항(EXP-04 에서 이미 사용, 독립 평가 아님)
- 전체 174, 최빈 등급 동률 제외 12

| 팔 | 문항 | 적용 범위 | 기권 | 미구현 |
|---|---|---|---|---|
| E0_EXISTING_ENGINE | 162 | 0.000 | 1.000 | 0.000 |
| A_RULES | 162 | 0.000 | 1.000 | 0.000 |
| B_GRAPH | 162 | 0.000 | 1.000 | 0.000 |
| C_LLM_RETRIEVAL | 162 | 0.000 | 0.778 | 0.222 |
| D_HYBRID | 162 | 0.000 | 1.000 | 0.000 |

진단 가설을 엔진 개념으로 연결하는 구성요소가 없어 기권이 정상. 성능 아님

## 합성 타임라인(지어낸 사례)
- 공개 집합이 기존 엔진과 다른 시점: 0

| T | 공개 증거 | 엔진 상태 | 조합 판단 | 검사 상태 | 중복 후보 |
|---|---|---|---|---|---|
| 0.5 |  | INSUFFICIENT |  | NOT_ORDERED | False |
| 1.0 | sym | SUPPORTED | SUPPORT | NOT_ORDERED | False |
| 2.0 | sym | SUPPORTED | SUPPORT | PENDING | True |
| 4.0 | sym,cta1 | CONFLICT | SUPPORT,CONTRADICTION | RESULT_AVAILABLE | True |
| 5.0 | sym,cta1 | CONFLICT | SUPPORT,CONTRADICTION | RESULT_AVAILABLE | True |
| 7.0 | sym,cta2 | SUPPORTED | SUPPORT,SUPPORT | RESULT_AVAILABLE | True |
| 8.0 | sym,cta2 | SUPPORTED | SUPPORT,SUPPORT | REVIEWED | True |

## ER-Reason 형식 시험(자리표시자, 실제 자료 아님)
- 사례 40, 문항 160, 대응 실패 0, 분할 {'HELD_OUT_TEST': 104, 'VALIDATION': 12, 'DEVELOPMENT': 44}, 두 분할에 걸친 사례 0
- 지표 값은 파이프라인 동작 확인용이며 의미 없음

## 원본 보존 확인
- EXP-01 FINAL 체크섬 일치 11, EXP-02 동결 True, time_v2 동결 대비 변경 [], TEST_USED 표지 True, EXP-MAI-003 실행 표지 False
