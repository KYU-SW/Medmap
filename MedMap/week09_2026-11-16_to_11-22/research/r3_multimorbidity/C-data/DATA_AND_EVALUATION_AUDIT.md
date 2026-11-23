# MedMap 복합질환 심층 연구 — SUBAGENT C: 연구 데이터와 평가 정답 확보

- 확인일: **2026-11-17** (모든 웹 확인·API 조회 이 날짜 기준). URL은 각 주장 옆과 `sources.csv`.
- 태그: **[원문으로 확인]** 원문 페이지·파일을 직접 열어 확인 / **[초록·요약으로 확인]** 검색 결과 요약·초록으로만 확인 / **[실험으로 확인]** 공개 JSON·API를 내려받아 직접 분석(데이터셋 아님) / **[연구 가설]** 추정 / **[미검증]** 페이지를 못 열었거나 확인 못 함.
- 지킨 것: 계정 가입·자격 신청·승인 데이터 다운로드·유료 API·외부 LLM 없음. ClinicalTrials.gov v2 API 소량 조회(8회), Synthea 모듈 JSON 10개(코드 파일, 환자 데이터 아님)만 받음. NHANES·NIST 등은 공식 문서 페이지만 열람.
- 배경 문서에서 이미 확인된 것(Synthea Apache-2.0, MIMIC-IV Demo ODbL 100명, MGCDS 4사례 Apache-2.0, ADA SoC ML 서면 허가, KDIGO 2024 Executive Summary CC BY-NC-ND, NICE AI 서면 허가, openFDA CC0, TREC CT 판정 체계)은 반복하지 않고 **빈칸만** 채움.

---

## 0. 판정 요약

| 질문 | 판정 |
|---|---|
| E1(수학적 정확성) 평가 자료 | **가능(지금)**. 합성 환자 + 고정 규칙 + 독립 brute-force 오라클. 외부 승인 불필요 |
| E2(임상 지침 일치) 평가 자료 | **조건부 가능**. 공개 환자별 정답은 MGCDS 4사례뿐. 독립 정답은 **전문가 패널(최소 2인) 직접 구성** 필요. 규칙 원천 라이선스가 막힘(KDIGO 전체본도 서면 허가 조항 확인, §1-2) |
| E3(실제 환자에게 더 좋은가) | **불가능(학생팀 자원 기준)**. 가장 가까운 것은 BioLINCC ACCORD(당뇨 10,251명, 무료, 교수 PI+IRB 면제 판정 필요)의 사후 관찰 분석이지만 인과적 우월성 주장 불가 |
| Synthea 다중질환 상호작용 | **부분 존재**. 당뇨→CKD 발생 연결, 단백뇨→ACE/ARB 선택은 있음. **당뇨약 선택은 eGFR·CKD를 전혀 보지 않음**, 심부전 모듈은 당뇨·CKD를 참조하지 않음 [실험으로 확인] → 정답 생성기가 아니라 **위반 사례 생성기** |
| 공개 다중질환·지침충돌 벤치마크 | MGCDS(4사례), Xie & Du 2026(SGLT2i 12개 지침 충돌, 데이터 공개 표시 없음), DriftMedQA(지침 개정 충돌, 다중질환 아님). **공개 polypharmacy LLM 벤치마크 미발견** |
| 추천 조합 | **당뇨 + CKD(1단계) → +심부전(2단계)**. 정량 기준(eGFR 구간)과 CT.gov 시험 다수(DM+CKD 588건, 결과 게시 87건 [실험으로 확인]) |

---

## 1. 이번에 새로 확인한 빈칸

### 1-1. Synthea 다중질환 모듈 실제 로직 [실험으로 확인]

출처: `https://github.com/synthetichealth/synthea/tree/master/src/main/resources/modules` (2026-11-17), 저장소 HEAD `bd8a52b`(2026-10-21), `metabolic_syndrome/medications.json` 마지막 변경 `879e78b`(2023-03-02). raw JSON을 받아 상태·조건을 정적 분석.

- **당뇨 전용 모듈 파일은 없음.** 당뇨는 `metabolic_syndrome_disease.json`(발생) + `metabolic_syndrome_care.json`(진료) + 하위 `metabolic_syndrome/medications.json`, `metabolic_syndrome/kidney_conditions.json`로 구성.
- **당뇨 → CKD 연결 있음**: `chronic_kidney_disease.json`의 `Guard_for_Htn_or_DM`이 `hypertension` 또는 `diabetes` 속성이 있을 때만 신병증 진행으로 넘어감(0.2%는 선천 경로).
- **eGFR 값 존재(배경 문서 정정)**: `chronic_kidney_disease.json` 자체에는 검사값이 없으나, `metabolic_syndrome/kidney_conditions.json`이 CKD 단계별로 MDRD eGFR을 **단계 구간 안에서 범위값**으로 기록(1기 90–150, 2기 60–89, 3기 30–59, 4기 15–29, 5기 5–14). 크레아티닌·칼륨·요단백 패널도 기록. → 배경 문서의 "Synthea CKD 모듈은 eGFR 값 자체가 없음"은 **CKD 모듈 파일 한정으로만 맞음**. 이 하위 모듈은 대사증후군 진료 경로(당뇨·당뇨전단계)에서 호출되므로, 고혈압 단독 CKD 환자에게 eGFR이 기록되는지는 [연구 가설: 미확인].
- **당뇨약 선택은 신기능 무관**: `medications.json`은 `diabetes_severity`(≥2 메트포르민, ≥3 리라글루타이드, ≥4 카나글리플로진)만 조건으로 씀. `ckd`·eGFR 조건 없음 → **CKD 4–5기(eGFR<30)에서도 메트포르민이 시작·유지될 수 있음**(openFDA 라벨 eGFR<30 금기와 충돌). 인슐린 시작만 "당뇨병성 신장질환" 진단을 조건으로 사용.
- **고혈압약은 신장 상태 반영**: `medications/hypertension_medication.json`이 `microalbuminuria`/`proteinuria`일 때 ACE억제제(리시노프릴)/ARB 경로로 보냄. `hypertension.json`은 `ckd > 3`을 제외 조건으로 참조, `chf` 속성 참조.
- **심부전 모듈은 고립**: `congestive_heart_failure.json`과 `heart/chf_meds.json`은 `diabetes`·`ckd` 속성을 전혀 참조하지 않음. 약물은 furosemide·carvedilol·lisinopril·losartan뿐, **SGLT2 억제제 없음**, eGFR·칼륨에 따른 용량/중단 로직 없음. 단 `heart/chf_lab_work.json`이 크레아티닌·eGFR·칼륨·HbA1c·NT-proBNP를 기록.
- **결론**: 동일 합성 환자에서 당뇨+CKD+심부전 동시 발생은 가능하나, **질환 간 치료 상호작용은 고혈압-단백뇨 1개만 모델링**. Synthea 처방은 "지침 정답"이 아니고 E2용 **위반 사례 자동 생성원**(예: eGFR<30 + 메트포르민, 당뇨+HFrEF인데 SGLT2i 없음)으로 쓸 수 있음.

### 1-2. KDIGO 2024 CKD 전체본 라이선스 [원문으로 확인]

출처: `https://kdigo.org/wp-content/uploads/2026/04/KDIGO-2024-CKD-Guideline.pdf`(kdigo.org 지침 페이지 링크, 199쪽), PDF p.14.
- 문구: "This is an open access article under the CC BY-NC-ND license … **No part of this publication may be reproduced, amended, or transmitted in any form … or any information storage and retrieval system, without explicit permission in writing from KDIGO.**"
- 해석: CC BY-NC-ND와 별도의 "서면 허가 없이 복제·수정·정보 저장검색 시스템 금지" 문구가 함께 있음. **규칙 레지스트리로 변환·저장·배포는 KDIGO 서면 허가 전 불가로 보는 것이 안전**. 문구 간 충돌의 법적 우선순위는 [미검증: 법률 검토 필요]. 문의처는 PDF에 KDIGO COO로 명시.

### 1-3. BioLINCC 신청 조건 [원문으로 확인]

출처: `https://biolincc.nhlbi.nih.gov/faq/`
- 학생: **단독 신청 불가**. 지도교수가 PI로 신청하고 학생을 Authorized User로 등록.
- IRB: IRB/EC 문서 필수. 대부분 **면제(exempt) 판정서로 충분**, 일부 연구는 신속·정규 심의(연구 페이지 명시).
- 비용: **무료**("There is no cost to access BioLINCC datasets"), 연구비 불필요.
- 계약: 승인 후 RMDA를 PI와 기관 법적 서명권자(PI 아닌 사람)가 서명.
- 연구계획서 필수.
- 연구별 [원문으로 확인]:
  - SPRINT `https://biolincc.nhlbi.nih.gov/studies/sprint/`: 9,361명, **당뇨 제외**, CKD(eGFR 20–<60) 포함 기준 중 하나, 상업·연구분야 데이터 제한 없음.
  - ACCORD `https://biolincc.nhlbi.nih.gov/studies/accord/`: **제2형 당뇨 10,251명**, 혈당·지질·혈압(4,733명) 3개 시험, 미세혈관 결과·사망·QoL. 페이지에 "**Administration directives에 따라 수정 검토 중**" 배너 → 접근성 변동 위험.
  - TOPCAT `https://biolincc.nhlbi.nih.gov/studies/topcat/`: HFpEF 3,445명(스피로노락톤 vs 위약), "severe renal dysfunction" 제외, 당뇨·eGFR 기저 변수 유무는 데이터 사전 미열람 [미검증].
  - CRIC(CKD 코호트): BioLINCC가 아니라 **NIDDK Central Repository(R4R)** 소관. Version 13(2024-12-13) 요청 가능 [초록·요약으로 확인]. DUA상 요청자(PI)는 기관 **정규직**이어야 함 [초록·요약으로 확인: NIDDK-CR DUA PDF 검색 요약]. IRB·비용 [미검증](FAQ HTTP 403).

### 1-4. NHANES DUA·변수 [원문으로 확인]

- DUA `https://www.cdc.gov/nchs/policy/data-user-agreement.html`: 통계 분석·보고 용도만, 재식별 시도 금지, 다른 개인식별 자료와 연결 금지. 등록 요구 문구 없음. 사용 = 동의.
- 2017–2020.3 사전 팬데믹 변수(`https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/`): `LBXSCR`(혈청 크레아티닌), `LBXSKSI`(칼륨), `URDACT`(UACR), `LBXGH`(HbA1c), `MCQ160b`(심부전 진단 경험), `KIQ022`(신장 약함/부전 진단), `KIQ025`(투석), `RXDDRUG`·`RXDRSC1–3`(처방약 + 사용 이유 ICD-10). → **동일인 당뇨+CKD+심부전 + 검사 + 약물** 구성 가능(단면).
- 사망 연계 공개파일 `https://www.cdc.gov/nchs/linked-data/mortality-files/index.html`: NHANES 1999–2018 성인 공개파일 존재, 일부 기록의 추적기간·사인은 **합성값으로 대체**, 생존 여부는 원값.

### 1-5. 기타 접근 조건

- **ICPSR 39508** = "Informing Patient-Centered Care for People with Multiple Chronic Conditions [Methods Study], 2015–2019", PI Cynthia Boyd, PCORI PCODR 배포, **공개이용 파일, ICPSR 회원기관 불필요**, MCC 환자 434명 선호 설문 [초록·요약으로 확인; 원문 HTTP 403]. 로그인 필요 여부·변수 목록 [미검증].
- **TREC CT 2022**: data.gov 레코드 라이선스 필드 = `https://www.nist.gov/open/license`, qrels 0/1/2(비관련/제외/적격) [초록·요약으로 확인]. NIST 라이선스 본문 [미검증: 페이지 시간초과]. 코퍼스(trec-cds.org)는 별도 출처, 2021 페이지에 라이선스 문구 없음 [원문으로 확인].
- **AACT**: 계정 만들면 클라우드 DB 접속·스냅샷 다운로드, 비용·약관 명시 못 찾음 [원문으로 확인: 홈 / 약관 페이지 404 → 미검증].
- **ClinicalTrials.gov 약관**: 페이지가 JS 렌더링이라 본문 추출 실패 [미검증].
- **Vivli** `https://vivli.org/resources/requestdata/`: 데이터 요청비 명시 없음, **보안분석환경 Standard 365일 무료 후 $12/일**, 팀에 **자격 있는 통계 전문가 필수**, 기관 서명, 학생 규정 없음 [원문으로 확인].
- **YODA**: 무료, PI·핵심인력·연구계획·COI·DUA 교육, 승인 요청과 계획서 **공개 게시**, 결정 30일 목표 [초록·요약으로 확인]. 학생 PI 가능 여부 [미검증].
- **Project Data Sphere**: 페이지 본문 미렌더링 [미검증].
- **UK Biobank**: 학생 등급 **£500+VAT(3년), 연장 £175/년**, 표준 Tier 3 £9,000, 학생·지도교수 모두 신청서 기재, 클라우드 분석 비용 별도(£40 크레딧) [초록·요약으로 확인; 공식 페이지 403]. 영국 외 학부생 적격성 [미검증].
- **CPRD**: 비영리 원가회수, 2019년 자료 기준 비상업 단일 데이터셋 £15,000 / 다중연구 £75,000(구 자료) [초록·요약으로 확인]. 현행가 [미검증]. 학생팀 사실상 불가 [연구 가설].
- **MIMIC-IV 정식**: CITI "Data or Specimens Only Research", **학생은 지도교수를 reference로**, 데이터셋별 DUA, 팀·수업 내 공유 금지(개인별 승인), 2026-06-18 PhysioNet 공지상 심사 지연 가능 [초록·요약으로 확인].
- **NHIS 표본코호트**: IRB 승인서 동봉 필수, 가상화룸 원격 접속(최대 6개월) [초록·요약으로 확인: 2016·2020 보도]. **저위험 표본데이터(2014–2023, 37개 변수, 검진 포함)**는 신청서·확약서로 제공 [초록·요약으로 확인: 2026 보도]. 학부생 자격·수수료 [미검증].
- **HIRA 환자표본(NPS/NIS/APS/PPS)**: 학술·공공 대상, 원격분석 [초록·요약으로 확인]. 비용·학생 자격 [미검증].
- **MedAgentBench**: GitHub `stanfordmlgroup/MedAgentBench` **MIT 라이선스** [원문으로 확인: GitHub API], 의사가 작성한 과제 300개·10범주, FHIR 환자 100명 [초록·요약으로 확인: arXiv 2501.14654]. 환자 원천(실제 비식별 vs 합성) [미검증], 다중질환 지침 판단 과제 아님(조회·기록·주문 위주) [초록·요약으로 확인: HF 미러 예시].
- **Xie & Du, arXiv 2604.17340 (2026-04-19)**: 12개 SGLT2 억제제 지침의 다중질환 충돌, 전문가 수정 gold set, 논문 CC BY 4.0, **데이터·코드 공개 링크 없음** [원문으로 확인: arXiv abs].
- **ConflictMedQA/DriftMedQA (arXiv 2505.07968)**: 지침 개정 전후 권고쌍 195개(만성 129), HF `RDBH/DriftMed` [초록·요약으로 확인]. 라이선스 [미검증].
- **CancerGUIDE (arXiv 2509.07325)**: 폐암 NCCN 준수, 종양내과 주석 121경로 [초록·요약으로 확인]. 다중질환 아님.
- **Polypharmacy LLM 벤치마크**: 공개 데이터셋 **미발견**. 관련 연구(JMIR Aging 2025 Socrates 등)는 데이터 비공개로 보임 [초록·요약으로 확인].

### 1-6. ClinicalTrials.gov 소량 조회 [실험으로 확인]

`https://clinicaltrials.gov/api/v2/studies?query.cond=...&countTotal=true` (검색어 의미론상 근사치)

| 조건 | 전체 | 결과 게시 |
|---|---|---|
| diabetes AND chronic kidney disease | 588 | 87 |
| diabetes AND heart failure | 396 | 57 |
| chronic kidney disease AND heart failure | 384 | 51 |
| diabetes AND CKD AND heart failure | 88 | 15 |
| multimorbidity OR multiple chronic conditions | 2,562 | 651 |

시험별 신기능 경계 예: DAPA-HF(NCT03036124) eGFR ≥30 포함, DELIVER(NCT03619213) eGFR <25 제외, 둘 다 1형 당뇨 제외 [실험으로 확인]. → 심부전 시험끼리도 eGFR 하한이 달라 "근거 적용 범위" 대리 정답의 경계 사례가 자연 발생.

---

## 2. 12항목 표

열: ①다운로드(무승인) ②승인 필요 ③라이선스 ④동일 환자 다중질환 기록 ⑤검사·약물·진단 ⑥의학적 권고·판단 정답 ⑦지침 상호작용 정답 ⑧치료 결과 ⑨환자 선호 ⑩알고리즘 비교 실험 사용 ⑪독립 평가 구성 ⑫검증할 수 없는 것

| 자료 | ① | ② | ③ | ④ | ⑤ | ⑥ | ⑦ | ⑧ | ⑨ | ⑩ | ⑪ | ⑫ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Synthea(+모듈 수정) | 예 | 아니오 | Apache-2.0 | 예(합성, DM→CKD 연결) | 예(eGFR 단계 범위값, 약물) | 아니오(처방이 지침 위반 포함) | 아니오(HTN-단백뇨 1개만) | 합성 사망만 | 아니오 | **예** | 예(생성기·오라클 분리 시) | 실제 결측·분포·임상 타당성 |
| MIMIC-IV Demo 2.2 | 예 | 아니오 | ODbL | 예(실제, 100명) | 예(노트 제외) | 아니오(실제 처방≠정답) | 아니오 | 입원 결과 | 아니오 | 예(소규모) | 부분(규칙위반 탐지율) | 외래 만성질환 대표성, 일반화 |
| MIMIC-IV 정식 | 아니오 | 예(CITI+지도교수 reference+DUA, 개인별) | PhysioNet DUA | 예 | 예 | 아니오 | 아니오 | 예(입원) | 아니오 | 조건부 | 조건부 | 인과 효과, 외래 |
| NHANES 2017–2020.3 | 예 | 아니오(제한파일 제외) | NCHS DUA(통계 용도, 연결 금지) | 예(단면, 자가보고+검사) | 예(크레아티닌·UACR·HbA1c·K·처방+ICD-10 이유) | 아니오 | 아니오 | 사망 연계(공개판 일부 합성) | 아니오 | 예 | 부분(유병·결측 분포) | 처방 시점 판단, 종단 변화 |
| ClinicalTrials.gov / AACT | API 예 / AACT 계정 | 아니오 | 약관 [미검증] | 아니오(시험 단위) | 포함·제외 기준 | 아니오 | 아니오 | 결과 게시 시험 요약 | 아니오 | 예(근거 범위 대리) | 예(외부 작성) | 환자별 적절성 |
| TREC CT 2021–2023 | 예 | 아니오 | NIST open license 지정, 본문 [미검증] | 서술 내 일부 | 서술 텍스트 | 시험 적격 판정(의사) | 아니오 | 아니오 | 아니오 | 예(적격성 과제) | **예(외부 의사 판정)** | 치료 선택 적절성 |
| MGCDS benchmark | 예 | 아니오 | Apache-2.0 | 예(합성 4사례) | 서술 | **예(전문가 기대 출력)** | **예(상호작용·완화)** | 아니오 | 사례2만 | 정성 | 예(n=4) | 통계적 일반화 |
| Xie & Du 2026 SGLT2i 충돌 | 아니오(공개 링크 없음) | 저자 문의 | 논문 CC BY 4.0, 데이터 [미검증] | 아니오(규칙쌍) | 아니오 | 아니오 | **예(규칙쌍 충돌 gold)** | 아니오 | 아니오 | 확보 시 예 | 확보 시 예 | 환자 단위 판단 |
| DriftMedQA | 예(HF) [초록·요약] | 아니오 | [미검증] | 아니오 | 아니오 | 권고 개정 정답 | 아니오(개정 충돌) | 아니오 | 아니오 | 보조 | 부분 | 다중질환 |
| MedAgentBench | 예 | 아니오 | MIT(코드) | FHIR 100명(원천 미검증) | 예 | 과제 정답(조회·주문) | 아니오 | 아니오 | 아니오 | 보조(FHIR 실행 환경) | 부분 | 지침 충돌 해결 |
| openFDA 라벨 | 예 | 아니오 | CC0 | 아니오 | 약물 신장 기준 | 라벨 규칙(연구용) | 부분(병용 경고) | 아니오 | 아니오 | 규칙 원천 | 예(외부 원천) | 임상 정답 |
| KDIGO 2024 전체본 | 열람 예 | **서면 허가**(변환·저장) | CC BY-NC-ND + 서면허가 조항 | 아니오 | 아니오 | 권고(근거등급) | 일부(DM·HF 언급) | 아니오 | practice point | 허가 전 인용만 | 전문가 루브릭 참고 | 환자별 정답 |
| BioLINCC SPRINT | 아니오 | 예(교수 PI, IRB 면제서, RMDA, 무료) | RMDA | CKD+고혈압(당뇨 제외) | 예 | 아니오 | 아니오 | **예(RCT)** | 아니오 | 사후 분석 | 부분 | 당뇨 동반 결론 |
| BioLINCC ACCORD | 아니오 | 위와 같음 | RMDA | **당뇨+eGFR+BP+지질** | 예 | 아니오 | 아니오 | **예(RCT, 미세혈관 포함)** | QoL | 사후 분석 | 부분 | 알고리즘 추천의 인과 효과 |
| BioLINCC TOPCAT | 아니오 | 위와 같음 | RMDA | HFpEF(+동반질환 변수 [미검증]) | 예 | 아니오 | 아니오 | 예(RCT) | QoL | 사후 분석 | 부분 | 중증 CKD |
| NIDDK-CR CRIC | 아니오 | 예(PI 정규직, DUA v5) | DUA | **CKD 코호트(당뇨 다수 [연구 가설])** | 예 | 아니오 | 아니오 | 예(관찰) | 아니오 | 관찰 분석 | 부분 | 인과 |
| Vivli / YODA / PDS | 아니오 | 예(통계가 필수[Vivli], 공개 게시[YODA]) | 개별 DUA | 시험별 | 예 | 아니오 | 아니오 | 예 | 일부 PRO | 사후 분석 | 부분 | 실제 진료 일반화 |
| ICPSR 39508 | 공개이용 [초록·요약] | 아니오(로그인 [미검증]) | [미검증] | MCC 434명 | 아니오(설문) | 아니오 | 아니오 | 아니오 | **예** | 선호 범위 설정 | 부분 | 임상기록과 동일인 결합 |
| UK Biobank | 아니오 | 예(학생 £500+VAT, 지도교수) | 접근계약 | 예(대규모, 1차의료 연계) | 예 | 아니오 | 아니오 | 예 | 일부 | 조건부 | 조건부 | — (비용·자격 미검증) |
| CPRD | 아니오 | 예(라이선스, 고비용) | 라이선스 | 예 | 예 | 아니오 | 아니오 | 예 | 아니오 | 비현실 | — | — |
| NHIS 표본코호트/저위험 표본 | 아니오 | 예(IRB/확약서, 원격) | 공단 규정 | 예(청구+검진) | 진단·처방·검진 | 아니오 | 아니오 | 예(사망·입원) | 아니오 | 조건부 | 조건부 | 검사값 세부(eGFR는 검진 크레아티닌 한정 [연구 가설]) |
| HIRA 환자표본 | 아니오 | 예(원격분석) | 심평원 규정 | 예(1년 청구) | 진단·처방(검사값 없음 [연구 가설]) | 아니오 | 아니오 | 제한 | 아니오 | 조건부 | 조건부 | eGFR 기반 규칙 |

핵심: **⑥⑦ 환자 단위 독립 정답을 가진 공개 자료는 여전히 MGCDS 4사례뿐**. ⑦(지침 간 상호작용 정답)은 MGCDS + Xie & Du(비공개)뿐. ⑧ 결과가 있는 자료(BioLINCC·MIMIC·NHANES 사망연계)는 ⑥⑦이 없다.

---

## 3. E1 / E2 / E3 지원 표

- **E1 수학적 정확성**: 주어진 규칙·사실·의미론에서 알고리즘 출력이 정의대로 계산되는가(완전성·건전성·최소성·단조성).
- **E2 임상 지침 일치**: 출력이 지침 원문과 전문가 해석에 맞는가.
- **E3 환자에게 더 좋은가**: 결과(사망·입원·eGFR 저하·QoL) 개선.

| 자료 | E1 | E2 | E3 | 비고 |
|---|---|---|---|---|
| Synthea(수정 포함) | **강** | 위반 사례 생성만 | 아니오 | 생성기 ≠ 오라클 구현자 분리 |
| 자체 합성 규칙 + brute-force 오라클 | **강** | 아니오 | 아니오 | 순환성 주의(같은 규칙으로 생성·채점) |
| MIMIC-IV Demo / NHANES | 중(실제 결측 패턴 스트레스) | 약(라벨 규칙 위반률) | 아니오(NHANES 사망연계는 연관만) | |
| openFDA 라벨 | 규칙 원천 | 중(라벨 일치) | 아니오 | "의료 결정 의존 금지" 고지 |
| ClinicalTrials.gov | 아니오 | 중(근거 범위 대리) | 아니오 | 포함기준 ≠ 적절성 |
| TREC CT | 아니오 | 중(적격성, 외부 의사 판정) | 아니오 | 치료 선택 아님 |
| MGCDS | 약 | **중(n=4, 정성)** | 아니오 | |
| Xie & Du / DriftMedQA | 아니오 | 중(규칙쌍 충돌·개정) | 아니오 | 데이터 확보 [미검증] |
| 전문가 패널(직접 구성) | 아니오 | **강(설계에 따라)** | 아니오 | 사전 루브릭·2인 독립·불일치 조정 |
| ICPSR 39508 | 선호 민감도 범위 | 약 | 아니오 | 동일인 결합 금지 |
| BioLINCC ACCORD/SPRINT/TOPCAT, CRIC | 아니오 | 약(시험 프로토콜 대비) | **약(사후 관찰 연관만)** | 무작위 배정은 알고리즘 추천에 대해 아님 |
| UKB/CPRD/NHIS/HIRA | 아니오 | 약 | 약(관찰 인과추론, 강한 가정) | 비용·자격 장벽 |

**E3을 진짜로 지원하는 자료는 없음.** "알고리즘을 따른 환자가 더 좋았다"는 무작위 배정된 알고리즘 사용 연구(전향 시험)가 필요하다. ACCORD 같은 RCT도 무작위 대상은 혈당·혈압 목표이지 MedMap 추천이 아니다 [연구 가설이지만 설계상 명백].

---

## 4. 접근 절차·비용

| 자료 | 절차 | 비용 | 학생 가능 | 예상 소요 | 근거 |
|---|---|---|---|---|---|
| Synthea, MIMIC-IV Demo, NHANES, openFDA, CT.gov API, TREC, MGCDS, MedAgentBench | 바로 다운로드 | 0 | 예 | 즉시 | [원문으로 확인] |
| MIMIC-IV 정식 | PhysioNet 계정→CITI→지도교수 reference→DUA(개인별) | 0 | 예(지도교수 필요) | 1–2주, 2026 지연 공지 | [초록·요약] |
| BioLINCC(SPRINT/ACCORD/TOPCAT) | 등록→교수 PI 신청+연구계획+IRB 면제서→승인→RMDA(PI+기관 서명권자) | 0 | **교수 PI 필수** | [미검증] | [원문으로 확인] |
| NIDDK-CR(CRIC) | R4R 등록→신청→완결성 검토→DUA v5 | [미검증] | PI 정규직 필수 | [미검증] | [초록·요약] |
| Vivli | 신청→행정·기여자·IRP 심사→DUA(DocuSign) | 요청 무료 [미검증], 분석환경 365일 후 $12/일 | 통계가 포함 필요 | [미검증] | [원문으로 확인] |
| YODA | 계획서·COI·DUA 교육→심사(30일 목표) | 0 | [미검증] | 결정 ~30일+DUA 후 중앙 35일 | [초록·요약] |
| ICPSR 39508 | 공개이용 다운로드(로그인 [미검증]) | 0 | 예 | 즉시 | [초록·요약] |
| UK Biobank | 신청(학생 등급)+지도교수 | £500+VAT/3년+클라우드 | 학위과정 학생 | [미검증] | [초록·요약] |
| CPRD | 심사위원회+라이선스 | 수만 파운드급(2019 기준) | 사실상 불가 | — | [초록·요약] |
| NHIS 표본코호트 / 저위험 표본 | IRB+심의(월 2회) / 신청서·확약서 | [미검증] | [미검증] | [미검증] | [초록·요약] |
| HIRA 환자표본 | 원격분석 신청 | [미검증] | [미검증] | [미검증] | [초록·요약] |
| KDIGO 규칙화 허가 | KDIGO 서면 허가 요청 | [미검증] | — | — | [원문으로 확인: 조항] |

**과금 주의**: Vivli 분석환경(기간 초과 시), UK Biobank, CPRD, UKB 클라우드는 비용 발생 → 사용자 과금 승인 대상. BioLINCC·YODA·MIMIC·NHANES는 무료.

---

## 5. 추천 질환 조합과 검증 시나리오(대학생 팀 기준)

### 조합: 제2형 당뇨 + CKD(1단계) → + 심부전(2단계)
- 이유: eGFR 구간 정량 규칙(메트포르민 <30 금기, SGLT2i 시작 하한), CT.gov 시험 다수와 시험 간 eGFR 경계 차이(DAPA-HF ≥30, DELIVER <25 제외), NHANES에 동일인 변수 전부 존재, Synthea가 **바로 이 조합에서 위반을 만들어냄**(eGFR<30 메트포르민, 심부전에 SGLT2i 없음) [실험으로 확인].
- 심부전 추가 시 상호작용(SGLT2i가 DM·CKD·HF에 동시 관여, MRA–칼륨–eGFR, ACEi/ARB 공통)이 생겨 "지침 간 충돌" 시나리오가 실제로 생김 [연구 가설: 규칙 수는 A·B 서브에이전트 결과로 확인 필요].

### 시나리오 (자원: 승인 불필요 자료 + 전문가 2인)
1. **E1 (지금 가능)**: 규칙 집합을 openFDA 라벨(CC0) + CT.gov 기준으로만 작성(지침은 인용만). 합성 환자 생성기와 brute-force 오라클을 **다른 사람이 구현**. 속성 기반 테스트(무작위 사실·결측 주입)로 건전성·완전성·최소성 측정. 실제 결측 패턴은 NHANES·MIMIC Demo 결측률로 주입.
2. **E2-a (지금 가능, 약한 정답)**: Synthea 기본 모듈로 1,000명 생성 → 라벨 규칙 위반 사례 탐지 재현율(위반 정의는 모듈 로직으로 사전에 알 수 있음 = 외부 정답).
3. **E2-b (조건부)**: 30–50개 비네트를 사전 고정, **임상의 2인 독립 판정**(동의/비동의/판정 불가) + 불일치 조정, 카파 보고. MGCDS 사례2(CKD+고혈압+심방세동)를 형식 참조. Xie & Du 데이터는 저자에게 공개 여부 문의(이메일 발송은 사용자 판단).
4. **E2-c (지금 가능)**: CT.gov 포함·제외 기준으로 "근거 적용 범위 안/밖/판정 불가" 대리 정답, 반드시 대리 지표로 표기.
5. **E3 (주장하지 않음)**: 필요하면 교수 PI로 BioLINCC ACCORD를 무료 신청해 "기저 상태에서 MedMap이 '근거 범위 밖'으로 분류한 환자군의 치료 효과 이질성" 같은 **가설 생성 분석**만. 우월성 주장 금지.

---

## 6. 검증할 수 없는 주장 목록 (현재 자료로)

1. "MedMap이 임상의보다 정확하다" / 정밀도·재현율을 임상 정답 기준으로 보고 — 환자별 공개 정답 없음(MGCDS n=4).
2. "MedMap을 쓰면 환자 결과가 개선된다"(E3) — 알고리즘 사용을 무작위 배정한 자료 없음.
3. "Synthea 처방 = 표준 치료" — 당뇨약이 eGFR 무관, 심부전 모듈이 DM·CKD 무관 [실험으로 확인].
4. "CT.gov 제외 기준 밖 환자에게 치료가 부적절하다" — 포함기준은 근거 범위일 뿐.
5. "KDIGO/ADA/NICE 규칙을 반영한 공개 규칙 레지스트리" — KDIGO 전체본도 서면 허가 조항, ADA·NICE 서면 허가 [원문/요약 확인].
6. "실제 환자의 선호를 반영했다" — 동일인 임상기록+선호 공개 자료 없음. ICPSR 39508은 다른 사람의 분포.
7. "공개 다중질환 지침충돌 벤치마크에서 SOTA" — 공개·재사용 가능한 표준 벤치마크 없음(Xie & Du 비공개, DriftMedQA는 다중질환 아님).
8. "polypharmacy 벤치마크 성능" — 공개 데이터셋 미발견.
9. "한국 환자에게 일반화된다" — NHIS/HIRA 접근 조건 [미검증], HIRA는 검사값 부재 가능 [연구 가설].
10. NHANES 사망연계 공개판으로 개인 수준 사인·추적기간 정밀 분석 — 일부 값 합성 대체.

---

## 7. 남은 미검증 (다음 확인 대상)

- NIST open license 본문(TREC qrels 재배포), ClinicalTrials.gov·AACT 현행 약관 본문(JS·404).
- ICPSR 39508 로그인 필요 여부·변수 목록(403).
- NIDDK-CR IRB·비용, BioLINCC 처리 기간, TOPCAT 데이터 사전의 당뇨·eGFR 변수.
- NHIS·HIRA 학부생 신청 자격과 수수료(공식 공지 직접 열람 필요).
- MedAgentBench 환자 원천, DriftMedQA 라이선스, Xie & Du 데이터 공개 여부.
- 가장 중요한 다음 한 가지: **지도교수 PI 가능 여부 확인**(BioLINCC·MIMIC 정식·NIDDK-CR 모두 이것에 걸림).
