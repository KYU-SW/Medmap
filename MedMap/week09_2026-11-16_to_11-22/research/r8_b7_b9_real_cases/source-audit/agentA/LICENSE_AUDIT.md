# 라이선스 감사 (Agent A)

접근일 2026-11-21. 라이선스 문구는 각 원문(PMC XML의 license-p·copyright-statement, GitHub API, PDF 판권면)에서 직접 확인함. 상세 문구는 `SOURCES.csv` 참조.

## 1. 판정 기준
- **구조화 허용**: 규칙 변환·JSON 저장 같은 각색이 라이선스상 허용되는지. CC BY·CC BY-NC·CC0·Apache-2.0 = 각색 허용. CC BY-NC-ND = 각색 금지. "text mining·fair use"만 있는 것 = 불가.
- **비상업(NC)**: MedMap 산출물의 상업적 이용 여부를 이 에이전트는 모름 → NC 자료는 "비상업 연구 한정"으로 표시.
- **ShareAlike(SA)**: 파생물도 같은 라이선스로 공개해야 함(WHO).

## 2. 사례 출처

| 출처 | 라이선스 | 구조화 | 재배포 | 사용 사례 |
|---|---|---|---|---|
| PLoS ONE 2019 PPC 연구(S05, S1 Table 포함) | CC0 1.0 | 허용 | 허용 | CASE_01–06 |
| Cureus 2023 (S06) | CC BY(버전 미표기) | 허용(출처 표기) | 허용 | CASE_07 |
| Cardiovasc Endocrinol Metab 2023 (S07) | CC BY 4.0 | 허용 | 허용 | CASE_08 |
| Cureus 2025 (S08) | CC BY 4.0 | 허용 | 허용 | CASE_09 |
| Cureus 2024 (S09) | CC BY 4.0 | 허용 | 허용 | CASE_10 |
| AGS 2012 (S10) | 저작권 보유, PMC "text mining / fair use" | **불가** | 불가 | CASE_11(짧은 인용·위치만) |
| MGCDS 저장소 2개(S01, S02) | Apache-2.0 | 허용(사례·해법 텍스트) | 허용(고지 유지) | CASE_12–13 |
| MGCDS 저장소 안 제3자 지침 PDF | 각 원저작권자 | **불가** | 불가 | 사용 안 함 |
| AMIA 2021 논문(S03) | "verbatim copying and redistribution ... permitted" | 불명확(수정 허용 문구 없음) | 축자만 | 사례 판정 참고 |
| JBI 2023 논문(S04) | OA 아님 | 불가 | 불가 | 초록만 참고 |
| Am J Case Rep 2025(S13), Clin Case Rep 2020(S14) | CC BY-NC-ND 4.0 | **불가(ND)** | 무변경 비상업만 | 제외 |

## 3. 진료지침
`guideline-evidence/agentA/GUIDELINE_SOURCES.md` §1 판정표 참조. 핵심:
- VA/DoD 4종(당뇨 2023·CKD 2025·OA 2026·고혈압 2026): PDF 안에 라이선스·공공영역 문구 **없음**. 미국 연방 정부 저작물(17 U.S.C. §105)로 추정하여 "조건부 허용"으로 표시. 민간 계약사가 개발을 지원했으므로 **법적 상태는 확인 필요**. 제3자 재수록분(CKD p.29 KDIGO 그림, p.138 KDIGO 각색, HTN pp.107·109 AHA 각색)은 제외.
- 대한고혈압학회 2022: CC BY 4.0 → 허용.
- 대한당뇨병학회 2025·대한심부전학회 2023: CC BY-NC 4.0 → 비상업 허용.
- WHO 고혈압 2021: CC BY-NC-SA 3.0 IGO → 비상업 허용, 파생 규칙도 같은 라이선스, WHO 보증 암시·로고 금지.
- USPSTF: 무변경 재사용 허용, 각색 시 비보증 면책 문구, 영리 금지.
- NICE·ADA·KDIGO·AHA/ACC/HFSA·NCCN: 인용만(상위 지시 인계, 재확인 안 함).

## 4. 이 감사에서 지킨 것
- 전문 복제 없음. 사례 JSON에는 원문 인용 1~2문장과 위치만 넣음.
- 로그인·유료 API·저자 연락 없음. PMC 웹페이지는 브라우저 확인 화면으로 막혀 NCBI E-utilities(efetch, 무료 공개 API)로 OA 본문 XML을 받음.
- 다운로드 총량 약 16 MB(VA PDF 4개 13.4 MB, WHO PDF 0.8 MB, PMC XML·docx 소량). 모두 작업용 임시 폴더(scratchpad)에 두고 산출물 폴더에는 복사하지 않음.

## 5. 남은 확인 사항
1. MedMap 산출물이 상업적으로 쓰일 가능성 → NC 자료 사용 가능 범위가 달라짐
2. VA/DoD CPG의 공공영역 여부(계약사 참여분 포함)
3. MGCDS 사례 텍스트 저작자가 Apache 라이선스 부여 권한을 가졌는지(저장소 소유자 = 연구 그룹, 사례 작성자 = 여러 기관 공동) — 일반적으로 허용으로 보나 확인 필요
