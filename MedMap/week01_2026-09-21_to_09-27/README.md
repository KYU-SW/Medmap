# 1주차 (2026-09-21 ~ 09-27) — 연구 검증에서 제품 흐름까지

## 요약
- **연구**
  - "외부 의학 지식으로 진단 오류를 잡을 수 있나?"를 검증했으나 **NO_GO**였습니다.
  - 방향을 **"다음에 무엇을 물어야 하나(다음 질문 엔진)"**로 바꿨고, 이쪽은 **GO**였습니다.
- **제품**
  - 엔진 → API → 웹을 만들었습니다.
  - 자연어 증상 입력, 음성 입력, 상담 요약, 한국어화까지 붙여 환자 흐름 전체가 동작합니다.

## 날짜별
| 날짜 | 한 일 | 결과 |
|---|---|---|
| 09-21 | (보고서 작성일 기준) Step 1–15: 기본 진단 모델, 외부 지식원 수집(HPO·HSDN·MedlinePlus·DisMech·Wikidata·UMLS), 외부 지식 verifier(STEP13B), 질환 프로필 파일럿 | STEP13B **NO_GO**(AUROC 0.478). 원인은 지식 coverage와, DDXPlus가 묻지 않는 정보 |
| 09-21~22 | STEP15 v2 blind 질환 프로필(사실 367개, 원문 인용 전수 검증, 09-21 작성) · STEP16A 외부 프로필 기반 질문 선택 | STEP16A NO_GO → 질문 엔진은 내부 IG로 결정 |
| 09-23 | **STEP16B 다음 질문 엔진 검증** · 엔진 모듈 · 세션 JSON 계약 · FastAPI v1 · 웹 UI v1(React+Vite) · 자연어 매퍼 v1 | STEP16B **GO**(1문항 회복률 0.459 vs 무작위 0.053) |
| 09-24 | 매퍼 v1.2 blind v3 · STEP17A(자연어 시작 상태 검증) | 매퍼 **제품 후보**(정밀도 0.963 기준 통과, 재현율 0.61은 기준 미달) · STEP17A **GO** |
| 09-25 | 자연어 intake 구현(추출 → 확인 → 시작 질문 → exact-k3 시작 → IG) · 웹 디자인 v1 반려 | e2e OK |
| 09-26 | 음성 입력(로컬 Whisper) · 상담 요약 핵심 · 흐름 안정화 · 한국어 용어 정본 | VOICE_E2E_OK |
| 09-27 | 요약 화면(새로고침 복원) · 시작 전 입력 유실 방지 · HTTPS 데모 · **한국어화 완료**(질환 49 · 질문 221 · 값 199) | 화면 영어 노출 0 |

## 폴더
- `reports/` — 단계별 연구 보고서(STEP9~17A, 매퍼 결과). 파일명은 `실험폴더__보고서명`입니다.
  - 핵심: `step13b_external_verifier__STEP13B_REPORT.md`, `step16b_next_information_validation__STEP16B_REPORT.md`, `step17a_intake_start_validation__STEP17A_REPORT.md`
- `design/` — 엔진·API 계약, 웹 UI 설계, 자연어 intake 설계, 기능별 구현 계획·실행 기록(ledger)
- `experiments/` — 실험 단계별 Python 스크립트 45개. 보고서와 같은 이름의 폴더로 정리했습니다(Step1 데이터 탐색 → Step2–3 진단 모델 → Step5–7 불일치 → Step8–11 외부 지식 매핑 → Step12–13B verifier → Step14–15 값 수준·질환 프로필 → Step16A/B·17A 다음 질문 엔진).
  - 실행하려면 DDXPlus 원본 데이터(`MedMap/code/scripts/download_public.sh`)가 필요합니다. UMLS·SNOMED 단계는 각 라이선스로 받은 자료가 필요합니다.
  - **의도적으로 뺀 파일**: `s15v2_facts_part1.py`, `s15v2_facts_part2.py`(질환 프로필 사실 367개와 원문 인용 모음). 출처에 저작권이 있는 자료(MedlinePlus 백과, GOLD 보고서, 교과서 등)가 섞여 있어 공개 저장소에는 넣지 않았습니다. 결과 요약은 `reports/step15_v2_blind_profile__STEP15_V2_REPORT.md`에 있습니다.

## 이 주의 교훈
- 결과가 좋아도 비교 설계가 맞는지 먼저 봤습니다. STEP13B·16A·16B·17A는 사전등록 후 평가 데이터를 1회 평가했고, 한 번 쓴 평가 데이터는 다시 쓰지 않았습니다(Step1–12는 탐색 단계). 단, STEP16B는 본 실행 전에 holdout 일부(200명)로 스모크를 1회 실행해 지표를 먼저 봤고, 이 사실을 보고서에 deviation으로 기록했습니다.
- Step5–7 내부 지표 S2(AUROC 0.917)는 "탐지 상한"이 아니라 같은 데이터로 학습한 두 모델이 얼마나 일치하는지였습니다(자체 사전검토에서 지적, `reports/step12_high_confidence_error__STEP12_C1_REPORT.md`, `reports/step13b_external_verifier__STEP13B_REPORT.md`).
