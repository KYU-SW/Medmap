# 4주차 (2026-10-12 ~ 10-18) — 한국어 임상 NLU 회복 · 의사 화면 디자인 병합 · 판넬 디자인 적용

## 요약
- **NLU 회복(STEP29.2·29.3)**: 실패 원인을 재현한 뒤 새 합성 평가 세트로 다시 고정·평가했습니다. STEP29.2는 RECOVERY_PASS, STEP29.3은 PARTIAL_IMPROVEMENT였습니다.
- **NLU ↔ 의사 화면 통합(STEP30)**: 공식 판정은 REGRESSION(검사기 오탐)이었고, 탐색 분석으로는 조건부 가능성을 확인했습니다. 자동 입력은 0건이고, 의사 확인을 거쳐야 하는 미리보기만 설계했습니다.
- **제품**: 의사 화면 디자인을 master에 병합했습니다(`MedMap/code` 갱신). 판넬 디자인은 별도 브랜치의 프런트에만 적용했습니다(미병합).

## 날짜별
| 날짜 | 한 일 | 결과 |
|---|---|---|
| 10-13 | **STEP29.2** NLU 회복(문장 분리·평가형 부정 범위·해소 연결·가드) · 의사 화면 디자인 master 병합 | **RECOVERY_PASS · STEP30 CONDITIONAL_GO**(필수 10·R1–R8 통과, 개발 목표 D2·D3 미달) · e2e 6종 통과 |
| 10-14 | **STEP29.3** 개념 검색 수리(시점 가림·표준 질의 재검색·의미 규칙) | **PARTIAL_IMPROVEMENT · CONDITIONAL_GO**(필수 10 통과, P4 미달) |
| 10-14~15 | **STEP30** NLU ↔ 의사 화면 연구 통합 | 공식 **REGRESSION · STEP31 NO_GO**(G10 검사기 오탐) / 탐색 v2 PARTIAL_FEASIBILITY |
| 10-15~16 | 판넬 기준 디자인을 환자·의사 화면에 적용(의사 2단 · 인계번호 숫자판 · 환자 카드) | 프런트만 적용, 서버 변경은 미실시 |

## 폴더
- `reports/` — STEP29.2·29.3·30 보고서·정책·통합 설계(`step30_doctor_nlu_integration__doctor_integration_architecture.md`, `__model_input_safety_contract.md`)
- `experiments/` — 세 단계 스크립트·테스트(데이터·출력 제외)
- `qa_screenshots/` — 판넬 디자인 적용 화면(`panel_apply_*`, 브랜치 상태)

## 아직 검증되지 않은 것
- 모든 NLU 평가는 합성 문장 기준입니다. 실제 음성인식 결과·실제 환자 발화는 없습니다.
- 판넬 디자인 적용은 브랜치에만 있고 master에 병합하지 않았습니다.
