# MedMap 실제 데이터 파일럿 — 출처·API·라이선스·수집 범위 감사 (Agent A)

- 확인일: **2026-11-20** (모든 웹 확인·API 호출 이 날짜). URL은 각 항목 옆과 `sources.csv`.
- 태그: **[직접 확인]** 공식 원문(페이지·PDF·JSON·OpenAPI)을 직접 열어 확인 / **[실제 실행]** 공개 API를 이번에 호출해 응답 확인 / **[가설]** 해석·추정 / **[미검증]** 원문을 못 열었거나 공식 근거 없음.
- 지킨 것: 무료·무인증 공개 API 소량 호출만(CT.gov 3회, openFDA 1회). 계정 가입·API 키·유료·외부 LLM API 없음. 지침 원문은 라이선스 문구 확인용으로 임시 폴더에서만 열고 이 폴더에 저장하지 않음(라이선스 문구 1~2문장만 인용).
- 이전 기록(2026-11-17, `D_CLINICAL_DATA_FEASIBILITY.md`, `DATA_AND_EVALUATION_AUDIT.md`)과의 차이는 §7.

---

## 0. 판정 요약

| 항목 | 판정 |
|---|---|
| ClinicalTrials.gov API v2 사용 | **가능**. 무료·무인증. 단 배포 시 출처·처리일·수정내역 표시 의무 |
| openFDA drug/label 사용 | **가능**. CC0(예외 표시 없음). "의료 결정에 의존 금지" 고지 필수 |
| 진료지침(ADA 2026, KDIGO 2024/2022, AHA/ACC/HFSA 2022) 구조화 저장 | **불가능(서면 허가 전)** |
| 이번 파일럿 범위 | **openFDA + ClinicalTrials.gov로 제한. "진료지침 충돌 평가"라고 부르지 않음** (예: "라벨–시험 근거 범위 비교"로 부름) |

---

## 1. ClinicalTrials.gov API v2

### 1-1. 접근·버전 [실제 실행]
- `GET https://clinicaltrials.gov/api/v2/version` → `apiVersion: "2.0.5"`, `dataTimestamp: "2026-11-19T10:00:07"`.
- OpenAPI 명세: `https://clinicaltrials.gov/api/oas/v2` (HTTP 200, `application/yaml`, OpenAPI 3.0.3, version 2.0.5). 서버 `https://clinicaltrials.gov/api/v2`.
- 인증·API 키 불필요 [실제 실행: 키 없이 200 응답].
- `https://clinicaltrials.gov/data-api/about-api`, `/about-site/terms-conditions`는 JS 앱 셸(94,251바이트 동일)이라 curl/WebFetch로 본문 안 보임. 약관 본문은 사이트 JS 번들(`chunk-D1BjaCj22.js`)에 내장된 텍스트로 확인 [직접 확인].

### 1-2. 스키마에서 필요한 필드 위치 [직접 확인: OpenAPI] + [실제 실행: NCT03036150]
| 용도 | 경로 |
|---|---|
| 시험 ID | `protocolSection.identificationModule.nctId` |
| 포함·제외 기준(자유 텍스트) | `protocolSection.eligibilityModule.eligibilityCriteria` (string) |
| 구조화 적격 값 | `eligibilityModule.sex`, `minimumAge`, `maximumAge`(패턴 `^\d+ (Year|Years|...)$`), `stdAges`, `healthyVolunteers` |
| 결과 유무 | `hasResults` (boolean) |
| 기초특성 | `resultsSection.baselineCharacteristicsModule` → `populationDescription`, `typeUnitsAnalyzed`, `groups[]`, `denoms[]`, `measures[]` |
| 기초특성 측정값 | `measures[].title / paramType / dispersionType / unitOfMeasure / classes[].categories[].measurements[]{groupId, value, spread, lowerLimit, upperLimit, comment}` |
| 결과 | `resultsSection.outcomeMeasuresModule`, `adverseEventsModule`, `participantFlowModule` |
| 제한사항 | `resultsSection.moreInfoModule.limitationsAndCaveats` |
- 실측: NCT03036150(DAPA-CKD) `hasResults=true`, 기초특성 measures 11개(예: `eGFR`, `Urine albumin creatinine ratio`, `Type 2 Diabetes Mellitus at Baseline`) [실제 실행]. 측정 제목이 시험마다 자유 서술이라 정규화 필요 [가설].
- 대량 조회 시 `fields`로 필요한 모듈만 요청하고 `pageSize`를 크게 잡지 말라는 OpenAPI 설명 존재 [직접 확인].

### 1-3. 이용 조건 (Terms and Conditions, 페이지 lastModDate 2023-01-31) [직접 확인]
URL: https://clinicaltrials.gov/about-site/terms-conditions (본문은 사이트 JS 번들 내 텍스트)
- 데이터 다운로드 = 약관 동의. 형식·취득 방법 무관하게 적용.
- "available to all requesters, both within and outside the United States, at no charge."
- 출판·배포 시 해야 할 것: ① 출처를 ClinicalTrials.gov로 표기 ② 데이터를 항상 최신으로 갱신 ③ ClinicalTrials.gov 처리일 명시 ④ 수정 내용과 그 완전한 설명 명시.
- 데이터베이스에 대한 소유권 주장 금지, 미국 정부 DB가 아닌 것처럼 표현 금지, 추출한 이메일 마케팅 사용 금지.
- "international copyright outside the United States", 일부 데이터는 제3자 저작권 대상일 수 있음.
- 보증·책임 없음. 데이터를 보유하는 한 약관 유효.

### 1-4. Rate limit [미검증]
- 공식 페이지·OpenAPI 명세·사이트 JS 번들 전체(48개 파일)에서 "rate limit / per minute / 429" 문구 **없음**. 응답 헤더에 rate-limit 헤더 없음 [실제 실행].
- "약 50 요청/분/IP"는 제3자 문서(BioMCP)에만 있음 [미검증].
- 운영 권장: **초당 1건 이하, 429/5xx 시 지수 백오프, 응답 원본 캐시 후 재호출 금지** [가설: 보수적 운영 기준].

### 1-5. 재배포 조건 요약
- 내부 저장·분석: 허용 [직접 확인: 무료·전 세계 제공].
- 결과물 배포(보고서·공개 저장소): 출처·처리일(`dataTimestamp` 또는 레코드 `lastUpdatePostDate`)·수정내역 명시 시 허용. "항상 최신 유지" 조항 때문에 **스냅샷 배포 시 "YYYY-MM-DD 기준 스냅샷, 최신 아님"을 명시**해야 함 [가설: 조항 이행 방식].
- 미국 외(한국)에서는 저작권 적용 가능, 자유 텍스트(eligibilityCriteria 등)는 스폰서 작성물이라 제3자 저작권 여지 → **원문 대량 공개 재배포는 피하고 NCT ID + 구조화 값 + 짧은 발췌로 배포** [가설].

---

## 2. openFDA drug/label

### 2-1. 접근·스키마 [실제 실행]
- `GET https://api.fda.gov/drug/label.json?search=openfda.generic_name:"metformin+hydrochloride"&limit=1` → 200.
- `meta.disclaimer`: "Do not rely on openFDA to make decisions regarding medical care. While we make every effort to ensure that data is accurate, you should assume all results are unvalidated. We may limit or otherwise restrict your access to the API in line with our Terms of Service." / `meta.license`: https://open.fda.gov/license/ / `meta.last_updated`: 2026-11-19.
- 최상위 필드 확인: `set_id`, `id`, `version`(예: "6"), `effective_time`(예: "20260812"), `indications_and_usage`, `contraindications`, `warnings_and_cautions`, `dosage_and_administration`, `use_in_specific_populations`, `boxed_warning`, `drug_interactions`, `geriatric_use`, `pediatric_use`, `pregnancy`, `clinical_studies`, `recent_major_changes` 등. 섹션 값은 **문자열 배열**.
- `openfda` 하위: `generic_name`, `brand_name`, `spl_set_id`, `spl_id`, `rxcui`, `application_number`, `manufacturer_name`, `pharm_class_epc`, `product_type`, `route`, `substance_name`, `unii` 등.
- 필드 명세: https://open.fda.gov/fields/druglabel.yaml (200) — 요청 필드 7종 모두 정의됨. **`renal_impairment` 같은 독립 필드는 없음** → 신기능 기준은 `use_in_specific_populations`·`dosage_and_administration`·`contraindications` 텍스트에서 추출해야 함 [직접 확인].
- 라벨 1건 식별 = `set_id` + `version` (+ `effective_time`) 고정 저장 권장 [가설].

### 2-2. Rate limit [직접 확인] https://open.fda.gov/apis/authentication/
- 키 없음: **240 요청/분/IP, 1,000 요청/일/IP**.
- 키 있음: 240/분/키, 120,000/일/키. (키 발급은 이번 파일럿 범위 밖 — 계정·이메일 등록 필요)
- 응답 헤더에 rate-limit 헤더는 안 보임 [실제 실행]. **일 1,000건 상한 때문에 C는 약물당 1~수 건 조회로 설계해야 함.**

### 2-3. 이용 조건 [직접 확인]
- https://open.fda.gov/license/ : "unless otherwise noted, the content, data, documentation, code, and related materials on openFDA is public domain and made available with a Creative Commons CC0 1.0 Universal dedication." 예외(GMDN — 기기 데이터, AI 학습 포함 상업 이용에 라이선스 필요)는 **drug/label과 무관**. FDA는 예외 데이터·필드를 명시하겠다고 함. 보증없음, 보증·승인 암시 금지.
- https://open.fda.gov/terms/ : CC0, 예외는 문서에 경고("This data is not in the public domain…")로 표시. 출처 표기는 의무 아님·요청("Data provided by the U.S. Food and Drug Administration (https://open.fda.gov)"). Right to Limit(부하·남용 시 접근 제한).
- https://open.fda.gov/apis/drug/label/ : "Do not rely on openFDA to make decisions regarding medical care." / 라벨이 현재 유통 제품 라벨·승인 라벨과 다를 수 있음 / unapproved 표시 약물은 FDA 미평가 / 갱신 **주 1회** / 대부분 2009-06 이후. drug/label 문서에 CC0 예외 경고 **없음**.

---

## 3. 공식 진료지침 이용 범위

| 지침 | 확인한 원문 문구 | 구조화 저장 | 태그 |
|---|---|---|---|
| ADA Standards of Care in Diabetes—2026 (Diabetes Care 49 Suppl 1) | "Readers may use this work for educational, noncommercial purposes if properly cited and unaltered… ADA permission is required to post this work on any third-party site or platform. This publication and its contents may not be reproduced, distributed, or used for text or data mining, machine learning, or similar technologies without prior written permission." (PMC12690168 서론, PMC12690186 13장 permissions 동일) | **불가(서면 허가 전)** | [직접 확인: NCBI efetch PMC XML] |
| KDIGO 2024 CKD | CC BY-NC-ND 4.0 + "No part of this publication may be reproduced, amended, or transmitted … or any information storage and retrieval system, without explicit permission in writing from KDIGO." (PDF p.14) | **불가(서면 허가 전)** | [직접 확인: 재다운로드] |
| KDIGO 2022 당뇨-CKD | **이전 미확인 → 이번 확인**: 2024와 동일 구조. CC BY-NC-ND + 정보 저장검색 시스템 서면 허가 조항 (전문 PDF p.13) | **불가(서면 허가 전)** | [직접 확인] |
| AHA/ACC/HFSA 2022 HF | Circulation판(10.1161/CIR.0000000000001063): Crossref 라이선스 없음, 원문 403. JACC판(10.1016/j.jacc.2021.12.012): Elsevier user license — 비상업 "access, download, copy, translate, text and data mine" 허용, "may not redistribute, display or adapt". AHA 지침 자료 재사용은 요청·수수료(비교육 $550/item, 300단어 이상 발췌는 라이선스 계약) | **불가(허가 전)**. 비상업 TDM 자체는 JACC판에서 허용되나, 추출 규칙을 저장·공유하는 것은 adapt/redistribute에 해당할 위험 | [직접 확인: Crossref, Elsevier license, heart.org] / 저널 원문 permissions 문구 [미검증: 403] |

**판정:** 이번 파일럿에서 진료지침의 권고·수치 기준을 구조화해 저장하는 것은 **허용 안 됨**.
→ **데이터 원천을 openFDA drug/label + ClinicalTrials.gov로 제한한다. 결과물을 "진료지침 충돌 평가(guideline conflict evaluation)"라고 부르지 않는다.** 지침은 서지 인용(문제 배경 설명)만 허용.
→ 허가 경로: ADA <email>, KDIGO COO(PDF 명시), AHA copyright request form. 신청 여부는 사용자 결정 [가설: 비용·기간 미확인].

---

## 4. source_type별 저장 허용 범위

| source_type | 원천 | 전문 저장 | 발췌 저장 | 구조화 값 | 배포(보고서·공개) 조건 |
|---|---|---|---|---|---|
| DRUG_LABEL | openFDA drug/label | **허용** (CC0, 내부 원본 JSON 보관) | 허용 | 허용 | 허용. 권장 출처 표기 + `set_id`/`version`/`effective_time`/`meta.last_updated` + "의료 결정에 의존 금지" 고지 + FDA 승인 암시 금지 |
| TRIAL_ELIGIBILITY | CT.gov `eligibilityModule` | **허용(내부)** — 원본 JSON 캐시 | 허용 | 허용 (나이·성별·eGFR 컷오프 등 파싱 값) | 출처·처리일·수정내역 명시. 공개 배포는 NCT ID + 구조화 값 + 짧은 발췌 권장(전문 대량 재배포 지양) [가설: 제3자 저작권 여지] |
| TRIAL_BASELINE_CHARACTERISTICS | CT.gov `resultsSection.baselineCharacteristicsModule` | 허용(내부) | 허용 | 허용 (measure title·param·unit·group별 value/spread) | 위와 같음 |
| TRIAL_RESULTS | CT.gov `outcomeMeasuresModule`·`adverseEventsModule` | 허용(내부) | 허용 | 허용 | 위와 같음. 수치 재계산·정규화 시 "수정 내용" 기술 필수 |
| CLINICAL_GUIDELINE | ADA 2026 / KDIGO 2024·2022 / AHA·ACC·HFSA 2022 | **금지** | **금지**(라이선스 확인용 1~2문장 인용만 예외) | **금지** | 서지 인용만. 서면 허가 후 재검토 |

---

## 5. B·C 작업자용 운영 규칙

- **B (ClinicalTrials.gov):** 원본 JSON(`fields` 제한) + 조회 URL + `dataTimestamp` + 조회일 저장. 초당 1건 이하, 429 시 백오프. 산출 CSV에 `source=ClinicalTrials.gov`, `ctgov_data_timestamp`, `modification_note` 열 권장.
- **C (openFDA):** 원본 JSON + `set_id`, `id`, `version`, `effective_time`, `meta.last_updated` 저장. 일 1,000건/IP 상한(같은 IP의 다른 세션 포함) 관리. 산출물에 disclaimer 문구 유지.
- 공통: 진료지침 PDF·문장·수치 기준을 `normalized/`·`shared-variables/`에 넣지 않는다.

---

## 6. 실패·미확인 기록

| 대상 | 결과 | 영향 |
|---|---|---|
| CT.gov 약관·API 문서 페이지 curl/WebFetch | JS 셸만 반환 | JS 번들 내 텍스트로 약관 확인 성공 |
| Playwright 브라우저 | 브라우저 미설치로 실패 | 설치하지 않음(규칙상 설치 금지) |
| CT.gov 공식 rate limit | 공식 문구 미발견 | [미검증], 보수 운영 |
| Europe PMC fullTextXML(ADA) | 503 | NCBI efetch로 대체 성공 |
| diabetesjournals.org, ahajournals.org, jacc.org | 403 | ADA는 PMC로 확인, AHA는 Crossref·Elsevier·heart.org로 간접 확인 |
| AHA 2022 HF 저널 원문 permissions 문구 | 미확인 | 판정(허가 전 불가)은 유지 — 보수 판정 |
| kdigo.org 기본 curl | 406 | 브라우저 UA 헤더로 성공 |
| KDIGO 링크 `2023/01/KDIGO_DM_GL_Exec_Summary.pdf` | 내용은 **2020** 당뇨 지침 요약(Copyright 2020) | 2022판 확인은 `2022/10/...Diabetes-Management-in-CKD.pdf`로 함 |

---

## 7. 이전 기록 대비 갱신

| 이전(2026-11-17) | 이번(2026-11-20) |
|---|---|
| CT.gov 현행 약관 본문 [미검증: JS·404] | **[직접 확인]** 본문 확보: 출처·최신화·처리일·수정내역 표시 의무, 국외 저작권 |
| CT.gov API 스키마 구체 위치 미기재 | OpenAPI 2.0.5, baseline 모듈 하위 구조까지 확인 |
| openFDA CC0 [직접 확인] | 유지. 무키 rate limit **240/분, 1,000/일 per IP** 확인. GMDN 예외는 기기 전용 |
| ADA SoC 2026: TDM·ML 서면 허가 | **재확인 일치** + 제3자 플랫폼 게시도 허가 필요 |
| KDIGO 2024: CC BY-NC-ND + 저장검색 시스템 서면 허가 | **재확인 일치** |
| KDIGO 2022 당뇨: [확인 필요] | **신규 확인**: 2024와 동일 조항 → 불가 |
| AHA/ACC/HFSA 2022 HF: 언급 없음 | **신규**: 허가 전 불가(JACC판 비상업 TDM 허용, 개작·재배포 금지; AHA 재사용 유료 요청) |
