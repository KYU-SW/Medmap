# 사례별 환자 선호 확보 수준 (Agent A)

접근일 2026-11-21. "실제/가상" 판정은 원문 문구로만 함.

## 1. 등급 정의
- **P3 실제 본인 선호(치료 수준)**: 실제 환자가 원하는/원치 않는 치료·검사·생활 부담을 직접 밝힘
- **P2 실제 본인 선호(돌봄 장소·전반 목표)**: 실제 환자 선호가 있으나 약물·치료 선택 수준은 아님
- **P1 대리인 선호만**: 가족·대리 결정자의 신념·선호만 있음
- **P0 없음**
- **PV 가상 선호**: 저자가 교육·벤치마크용으로 작성한 선호(실제 자료로 쓰면 안 됨)

## 2. 사례별 표

| 사례 | 유형 | 등급 | 선호 내용(원문 짧은 인용) | 위치 | 실제 판정 근거 |
|---|---|---|---|---|---|
| CASE_01 (PPC No.5) | REAL_WITH_PREF | P3 | "Not willing to check blood sugar more often, only does it 'when my wife makes me'" / 식이 변경 거부 | PLoS ONE 2019 S1 Table No.5 | 본문 Results: 35명 설명은 EHR에서 확인, 목표·선호는 우선순위 확인 과정에서 확인. IRB 문단: 환자 구두 동의 후 비식별 공개 |
| CASE_02 (PPC No.19) | REAL_WITH_PREF | P3 | "Doesn't wish to see more specialists" / Wants "no surgery of any kind" | S1 Table No.19 | 동일 |
| CASE_03 (PPC No.6) | REAL_WITH_PREF | P3 | "Would like to decrease blood pressure medications if possible" | S1 Table No.6 | 동일 |
| CASE_04 (PPC No.12) | REAL_WITH_PREF | P3 | "Limit use of NSAIDs"(도움 되는/할 수 있는 치료), 수술 후 이동성 저하 우려 | S1 Table No.12 | 동일 |
| CASE_05 (PPC No.14) | REAL_WITH_PREF | P3 | "Reduction in simvastatin to 3 times per week is helping, decreased muscle pain" | S1 Table No.14 | 동일 |
| CASE_06 (PPC No.2) | REAL_WITH_PREF | P3 | "my oxycodone and Celebrex made me dizzy" / warfarin 출혈·멍 때문에 활동이 두려움 | S1 Table No.2 | 동일 |
| CASE_07 (Cureus 2023) | REAL_WITH_PREF | P2 | "the patient's wish was to receive care in her home (she refused any post-acute care recommendations)" | Case presentation 2번째 문단 | 동료심사 사례 보고 |
| CASE_08 (CEM 2023) | REAL_NO_PREF | P0 | — | — | 동료심사 사례 보고 |
| CASE_09 (Cureus 2025) | REAL_NO_PREF | P1 | 딸: 호스피스 = "giving up"이라는 우려 | Case presentation 3번째 문단 | 환자는 의사결정을 딸에게 위임(Discussion) |
| CASE_10 (Cureus 2024) | REAL_NO_PREF | P0 | — | — | 동료심사 사례 보고 |
| CASE_11 (AGS 2012 Case 1) | GUIDELINE_VIGNETTE | PV | "To stay alive / To optimize quality of life / To reduce out-of-pocket expenses / To remain safely in his home" | Case Example 1 | 원문 "To illustrate ... the cases have been distilled" — 실제 여부 미명시 |
| CASE_12 (MGCDS Case 2) | GUIDELINE_VIGNETTE | PV | "John's preferences: To have warfarin replaced by one of the DOACs (apixaban) ..." | Case 2 | JBI 2023 초록 "defining exemplar case studies" |
| CASE_13 (MGCDS Case 1) | GUIDELINE_VIGNETTE | P0 | — | — | 동일 |

## 3. 집계
- P3 실제 치료 수준 선호: **6건**, 모두 한 출처(PPC PLoS ONE 2019 S1 Table)
- P2: 1건 / P1: 1건 / P0(실제): 2건 / PV(가상): 2건, P0(가상): 1건
- 동료심사 사례 보고(PMC OA)에서 **치료 선택 수준의 실제 환자 선호를 가진 당뇨+CKD+심부전 또는 당뇨+CKD+OA 사례는 찾지 못함**(PubMed 검색: case report + OA + 해당 질환 + preference/shared decision/goals 조합 → 해당 1건, 내용은 대리인 선호).

## 4. 한계
1. P3 6건이 모두 같은 연구·같은 지역(미국 코네티컷 1차진료·심장내과)·같은 인종(모두 백인, 원문)이다. 출처 다양성이 없음.
2. P3 사례에는 검사값과 실제 결정이 없다. "선호가 있으면 판단이 어떻게 바뀌었는가"를 원문으로 검증할 수 없음 → 선호는 실제, 결정 비교는 불가.
3. S1 Table 선호는 의료진이 기록한 요약이며 환자 발화 그대로인 것(따옴표)과 요약이 섞여 있음. JSON에는 원문 표기 그대로 둠.
4. 본문 Table 2의 일부 환자 번호(# 39, # 143, # 423, # 457)는 35명 범위를 넘음 → 각주 번호가 붙은 표기로 보이나 어떤 환자인지 **확인 필요**. 이 번호의 발언은 사례에 연결하지 않음.
5. 원문에 선호 강도(얼마나 중요한지)나 선호 간 순위는 'Specific Ask' 외에는 없음.

## 5. 선호 정보가 판단을 바꿀 수 있는 지점(먼저 물을 것 후보)
| 사례 | 먼저 확인할 정보 |
|---|---|
| CASE_01 | 새 약(예: 지침 공통 권고 약제)을 추가로 먹을 의향, 혈당 측정 부담 허용 범위 |
| CASE_02 | 신장내과 의뢰·투석을 원하는지(“전문의 더 안 봄”, “수술 거부”와 지침 의뢰 권고의 충돌) |
| CASE_03 | 아침 어지럼과 혈압약의 관계(기립 혈압) — 감량 선호를 따를지 판단 전 측정 필요 |
| CASE_04 | 통증 부위·NSAID 실제 사용량, 정원 일·운전 중 무엇이 가장 중요한지 |
| CASE_06 | 출혈 공포와 뇌졸중 위험 중 무엇을 더 피하고 싶은지 |
| CASE_09 | 위임 전 환자 본인의 가치관 |
