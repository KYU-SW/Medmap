# Agent A 보고서 — 실제 사례·환자 선호·진료지침 출처

작성일 2026-11-21. 판정: **부분 통과** — 실제 환자 사례 10건 확보(실제 선호 포함 7건). 단, 실제 치료 선호 사례(6건)는 모두 한 출처이고 검사값·실제 결정이 없음.

## 1. 확보 사례 수(종류별)

| 종류 | 수 | 사례 | 조합 |
|---|---|---|---|
| REAL_WITH_PREF | 7 | CASE_01–06(PPC PLoS ONE 2019 S1 Table, CC0), CASE_07(Cureus 2023, CC BY) | (1) 3건: 01·02·07 / (2) 3건: 03·04·05 / (3) 1건: 06 |
| REAL_NO_PREF | 3 | CASE_08(CEM 2023), CASE_09(Cureus 2025, 대리인 선호만), CASE_10(Cureus 2024) | (1) 2건: 08·09 / (3) 1건: 10 |
| GUIDELINE_VIGNETTE | 3 | CASE_11(AGS 2012, 저작권), CASE_12·13(MGCDS, Apache-2.0) | (1)+(2) 1건 / (3) 2건 |
| SYNTHETIC_STRESS | 0 | 만들지 않음(이번 범위는 실제 근거 확보, 합성 사례 생성 안 함) | — |
| 합계 | 13 | | |

조합 (3)으로 바꾼 이유:
- CASE_06: 의료진 이견 + "90세가 시험에 얼마나 포함됐는지 모르겠다"는 B10 발언 + 실제 출혈 공포 선호가 함께 있는 유일한 실제 사례
- CASE_10: eGFR 43→18 시점별 수치와 metformin 감량→금기 과정이 있어 B7 조건부 충돌 시나리오로 적합
- CASE_12·13: 공개 벤치마크 중 기대 출력(수정 치료안·해법 보고서)이 있는 유일한 자료

## 2. MGCDS 벤치마크 확인 결과(요청 항목)
- `github.com/MGCDS/benchmark-framework`: Apache-2.0, 파일 4개(Benchmark_4_cases.docx, LICENSE, 설문 pptx, README). 사례 4개: TIA/십이지장궤양/골다공증, CKD/고혈압/심방세동, VTE/요로감염, 약물방출스텐트/폐종괴. 2021-03-02 이후 갱신 없음.
- 확장 저장소 `github.com/william-vw/MGCDS`(JBI 2023 논문이 가리킴): Apache-2.0, 사례별 설명·슬라이드·근거 PDF, **Solution Reports 6개 팀**, Reporting Template, 일부 OWL/TTL 모델.
- 기대 출력: 사례 안 "Revised treatment"/"Option 1–3"(저자 작성)과 팀별 해법 보고서는 있음. **전문가 합의 정답(gold standard)이라는 문구는 없음**.
- 실제/가상: 실제 환자 문구 없음. JBI 2023 초록 "defining exemplar case studies covering these features" → GUIDELINE_VIGNETTE. Case 2의 "John's preferences"는 저자 작성 가상 선호.
- 당뇨+CKD+심부전, 당뇨+CKD+OA 조합 사례는 **없음**.
- 저장소의 제3자 지침 PDF(NICE 등)는 Apache 대상 아님 → 사용 금지.

## 3. 구조화 가능한 지침 목록

| 구분 | 지침 |
|---|---|
| 허용(추정, 조건부) | VA/DoD 당뇨 v6.0 2023, CKD v5.0 2025, 고관절·무릎 OA v3.0 2026, 고혈압 v5.0 2026 — PDF에 라이선스 문구 없음, 미국 정부 저작물 추정, 제3자 재수록분 제외, 법적 상태 확인 필요 |
| 허용 | 대한고혈압학회 2022 focused update (CC BY 4.0) |
| 비상업 허용 | 대한당뇨병학회 2025, 대한심부전학회 2023 치료·동반질환 (CC BY-NC 4.0); WHO 고혈압 2021 (CC BY-NC-SA 3.0 IGO, 파생물 동일 라이선스) |
| 조건부 | USPSTF(각색 시 면책 문구, 영리 금지; 주제 관련성 낮음) |
| 인용만 | NICE, ADA SoC 2026, KDIGO, AHA/ACC/HFSA 2022, NCCN(인계 사실), AGS 2012 |
| 없음 | VA/DoD 심부전(2007판 폐기), 구조화 허용 심방세동 지침(미확보) |

권고 위치(쪽·권고 번호)는 `guideline-evidence/agentA/GUIDELINE_SOURCES.md`.

## 4. 실패·제외 이유
- PMC 웹페이지(pmc.ncbi.nlm.nih.gov)가 브라우저 확인 화면으로 막힘 → NCBI E-utilities efetch로 OA 본문 XML을 받아 해결. Europe PMC REST API는 시간초과·503으로 사용 못함.
- PMC OA 사례 보고는 대부분 희귀 이상반응 중심(SGLT2i 케톤산증 등)이라 환자 선호 서술이 거의 없음.
- CC BY-NC-ND 사례(Am J Case Rep, Clin Case Rep)는 각색 금지로 제외.
- AGS 2012 사례는 실제 여부 미명시 + 저작권 → 가상 교육 사례로만 분류, 구조화 금지.
- AMIA 2021 논문 본문은 초록만 텍스트로 제공되어 사례 작성 방식 원문을 확인 못함.

## 5. 가장 큰 한계
1. **실제 치료 수준 선호가 있는 사례 6건이 모두 한 출처**(미국 코네티컷 PPC 시범사업, 환자 전원 백인).
2. **이 6건에는 검사값·실제 결정이 없음**. 선호는 실제지만 "정보가 있었다면 판단이 어떻게 됐나"를 원문으로 검증할 수 없음 → B7 판정 정답 비교에는 쓸 수 없고, "무엇을 보류하고 무엇을 먼저 물을지" 시나리오에만 적합.
3. 반대로 검사값·실제 결정이 풍부한 사례(CASE_08·10)에는 환자 선호가 없음. **실제 선호 + 검사값 + 실제 결정을 모두 갖춘 사례는 0건.**
4. 심부전은 구조화 허용 미국 연방 지침이 없고 비상업 조건 한국 학회 지침만 있음.
5. 의료 전문가 정답은 어떤 출처에도 없음(MGCDS 기대안도 합의 정답 아님). 이 보고서에서도 만들지 않음.

## 6. 산출물 경로
- `source-audit/agentA/SOURCES.csv` (사례 출처 19 + 지침 14 + 웹정책 1)
- `source-audit/agentA/LICENSE_AUDIT.md`
- `source-audit/agentA/AGENT_A_REPORT.md` (이 파일)
- `clinical-cases/agentA_candidates/CASE_01.json` ~ `CASE_13.json`, `CASES_INDEX.csv`
- `patient-preferences/agentA/PREFERENCE_AVAILABILITY.md`
- `guideline-evidence/agentA/GUIDELINE_SOURCES.md`

## 7. 확인 필요 목록
- MedMap 결과물의 상업적 이용 여부(NC 자료 사용 범위)
- VA/DoD CPG 공공영역 여부(계약사 참여)
- PPC 본문 Table 2의 환자 번호 # 39·# 143·# 423·# 457이 어느 환자인지
- CASE_07의 혈당강하제 이름(Table 2 전체 미확인)
- CASE_10 원문의 "stage 2 CKD" 표기와 eGFR 43 불일치
- 구조화 허용 심방세동 지침 존재 여부
