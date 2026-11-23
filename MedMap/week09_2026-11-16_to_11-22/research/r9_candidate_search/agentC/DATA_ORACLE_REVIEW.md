# 데이터·독립 정답 확보 가능성 검토 (Agent C, 2026-11-21)

정답 유형: (1) 실제 기록 사건 (2) 기존 공개 전문가 판정/주석 (3) 수학 계산 (4) 연구자 작성(비독립) (5) 확인 불가.
근거 수준: A=로컬 집계·헤더·API 직접 확인, B=공식 페이지 확인, C=검색 요약, D=추정/확인 필요.
자격 인증 데이터는 파일명·헤더(스키마)만 확인, 행·원문 미열람. 전체 표 = `DATA_ORACLE_FEASIBILITY.csv`(26행).

## 영역별 판정

| 영역 | 판정 | 독립 정답 경로 | 핵심 한계 |
|---|---|---|---|
| PA 후속 조치 미완료 | 조건부 가능 | (1) radiology 권고 보고서 → 이후 같은 부위 영상 보고서 charttime / labevents 시행 사건 / ED·재입원 사건 | 기관 외 시행 관측 불가(미시행≠미완료). 결과 열람·검토·환자 설명 기록 없음 → '확인 누락' 정답 불가. 권고 문장 추출은 구현자(4). 공개 권고 주석 코퍼스 없음 |
| PB 지침→규칙 변환 손실 | 조건부 가능 | (2) CMS eCQM CQL + 측정 개발자 작성 기대 MeasureReport(CC0, 71개 측정) / CDC 오피오이드 CDS(지침 서술→요구사항→CQL) | 기대값이 공식 CQL 과 같은 해석 → '재구현 vs 공식 사양' 불일치만 판정. '원 지침 대비 손실' 자체는 독립 정답 없음 |
| PC 시간 상태·기록 모순·복사 | 조건부 가능 | (1) 퇴원요약 수치 주장 ↔ labevents 실제 값·시각 / (3) 입원 간 문자열 중복률 / (2) n2c2 2012 시간 관계(미보유, DUA) | 주장 추출 단계는 구현자(4). 같은 입원 내 경과기록 없음(MIMIC-IV-Note 는 퇴원요약·영상만). 임상적 '모순' 판단은 전문가 필요 |
| PD 경고 피로 | 불가능 | (5) | 공개 override 로그 없음. MIMIC 에 경고 로그 없음 |
| PE 진단 불일치·오류 | 가능(라벨 범위 내) | (2) MIMIC-IV-Ext-PE(의사 2인+모델), ER-REASON(전문의 2인+조정, 194건) — 둘 다 보유 / (1) ED 진단↔퇴원 진단 불일치·ED 퇴실 후 재내원 | 코드 불일치·재내원은 '오류'가 아닌 대리 사건. PE 라벨은 수동/모델 혼재 구분 필드가 보유 CSV 헤더에 없음 |
| PF 인계·요약 누락 | 부분 통과 | (2) ann-pt-summ(근거 없는 사실 주석, 미보유) / (1) MIMIC-IV-Ext-BHC 참조 요약(미보유) | '누락(omission)' 전문가 주석 공개 데이터 미발견. 참조 요약 대비 자동 지표만 가능 |

## MIMIC-IV Demo 2.2 시각 필드 실측(집계만, 공개 ODbL)

- labevents 107,727행·100명. hadm_id 결측 26.4%(외래 검사).
- storetime 결측 0.92%. storetime−charttime: 중앙 65분, p25 39분, p75 102분, p95 296분, p99 617분, 최대 39,962분. 음수 0건.
- 범주별 중앙(p95): Blood Gas 2분(8), Hematology 55분(277), Chemistry 81분(355). 입원 79,307행 중앙 67분, 외래 28,420행 중앙 57분·p95 460분.
- 검체(specimen) 11,122개 중 storetime 복수 27% → 결과가 단계적으로 저장됨. charttime 은 검체 내 단일.
- charttime 초 단위 전부 0(분 해상도).
- comments: 비결측 17.1%. "PROVIDER NOTIFIED PER CURRENT LAB POLICY" 계열 155행(통보 사실만, 시각·대상 없음). "CORRECTED RESULT PREVIOUSLY REPORTED AS n" 계열 27행(이전 값은 주석 문자열로만, 버전 이력 없음).
- order_provider_id 결측 84.4%.
- admissions 275건, edregtime 존재 182건. 다음 입원 있는 175건 중 30일 내 재입원 54건. 퇴원 후 30일 내 검사 존재 102건(그중 외래 검사 88건).
- 데모에 노트 없음(radiology/discharge 는 자격 인증 MIMIC-IV-Note 에만).

## 결과 '열람/검토/환자 설명' 기록

- 없음. MIMIC-IV hosp(보유 6표)·MIMIC-IV-Note·MIMIC-IV-ED 어디에도 결과 열람·서명(acknowledge)·환자 설명 이벤트 표 없음.
- 대리 정보: labevents.comments 의 'PROVIDER NOTIFIED'(소수·시각 없음), 이후 노트 언급(추출 필요, 4).
- 공개 EHR audit log 데이터셋 미발견.

## PB 독립 테스트 케이스 확인 내용

- `cqframework/ecqm-content-qicore-2024`(CC0, 마지막 커밋 2026-05-13): `input/tests/measure/` 71개 측정. CMS71 한 측정 테스트 폴더 약 765개.
- 각 테스트 폴더: 합성 FHIR 리소스 + `MeasureReport`(madie.cms.gov 측정 참조, 기대 count: initial-population/denominator/denominator-exclusion/numerator/denominator-exception, testCaseDescription 서술). 실제 1건 열어 확인.
- 의미: 사람 판단 없이 기계적으로 '재구현 규칙 출력 = 공식 기대 count' 판정 가능. 정답 작성자는 MedMap 구현자와 독립(측정 개발자).
- 한계: 기대값은 공식 사양 해석과 동일 출처 → 공식 CQL 의 지침 대비 손실은 검출 불가. 지침 원문↔코드 쌍은 eCQM 사람용 서술 수준. 
- Cypress: 논리 경로 ≥95% 포괄 설계, 완전 검사 아님(ONC 명시). 공식 패키지 내 테스트 번들 포함 여부 확인 필요.
- CDS Connect: 2026-11-21 artifact URL 이 digital.ahrq.gov 로 리다이렉트 후 403 → 운영 상태 확인 필요. CQL Testing Framework(Apache-2.0, YAML 기대값)는 존재하나 공개 아티팩트 동봉 여부 미확인.
- CDC 오피오이드 CDS(`cqframework/opioid-cds-r4`, CC): 12개 권고, `Requirements-fromNarrative.json`, `tests/` 존재. 기대 출력 포함 여부 확인 필요.

## 이용 조건·AI 사용

- PhysioNet 자격 인증 데이터(MIMIC-IV, Note, ED, Ext-PE, BHC, ann-pt-summ, CDM, DiReCT): DUA 상 제3자 공유 금지. PhysioNet 공지(2025-09-24): API 전송 포함 제3자 공유 금지, 제3자 LLM 저장·보존 금지, 무보존·무학습·무사람검토 검증 가능한 경우만 클라우드 허용, 불확실하면 금지, 로컬 LLM 권장. → 로컬 스크립트·로컬 LLM 만, 세션에는 스키마·집계만(기존 규칙과 일치).
- ER-REASON: Contributor Review 라이선스 + 저자 개별 연구 승인. 승인된 연구 목적 범위 확인 필요.
- n2c2·MedAlign·EHRSHOT: 별도 DUA(미보유). LLM 조항 확인 필요.
- MIMIC-IV Demo·ED Demo: ODbL, 공개 사용 가능. eCQM GitHub 콘텐츠: CC0.

## 확인 필요 목록

1. MIMIC-IV-Note radiology 의 외래 영상 포함 범위(검열 규모) — 로컬 집계로만 확인 가능.
2. 로컬 discharge.csv.gz 사용 승인 여부(PRIOR 목록 미기재).
3. MIMIC-IV-Ext-PE 수동/모델 라벨 구분 방법.
4. 공식 eCQM 패키지·Cypress 테스트 데크 공개 다운로드 경로.
5. CDS Connect 저장소 현재 운영 상태.
6. opioid-cds-r4 테스트 기대 출력 포함 여부.
7. n2c2 포털 현재 신청 가능 여부.
8. Discharge Me 사람 평가 결과 공개 여부.

## 출처

- https://physionet.org/news/post/llm-responsible-use/
- https://physionet.org/content/mimic-iv-note/2.2/
- https://physionet.org/content/mimic-iv-ext-pe/1.0.0/
- https://physionet.org/content/er-reason/
- https://physionet.org/content/labelled-notes-hospital-course/1.2.0/
- https://www.physionet.org/content/ann-pt-summ/1.0.1/
- https://physionet.org/content/mimic-iv-ext-direct/1.0.0/
- https://www.physionet.org/content/mimic-iv-ext-cdm/
- https://physionet.org/content/discharge-me/
- https://www.physionet.org/content/mimic-iv-ed-demo/2.2/
- https://github.com/cqframework/ecqm-content-qicore-2024
- https://github.com/cqframework/opioid-cds-r4
- https://github.com/AHRQ-CDS/CQL-Testing-Framework
- https://www.healthit.gov/cypress/resources.html
- https://ecqi.healthit.gov/tool/bonnie
- https://n2c2.dbmi.hms.harvard.edu/challenge/2012-temporal-relations
- https://hai.stanford.edu/news/advancing-responsible-healthcare-ai-longitudinal-ehr-datasets
- https://shahlab.stanford.edu/ehrshot_license
- https://arxiv.org/html/2511.11867v1
- https://pmc.ncbi.nlm.nih.gov/articles/PMC6748816
