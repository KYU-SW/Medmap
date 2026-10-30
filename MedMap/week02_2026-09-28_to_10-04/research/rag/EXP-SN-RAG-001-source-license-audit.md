# EXP-SN-RAG-001 출처·라이선스 감사 C0–C1 — rev0 (2026-10-02)

- 단계: **C0 후보 목록 + C1 라이선스 감사(1차).** C2 승인 전 · 원문 확보(C3) 0 · 의학 사실 추출 0
- 법률 판단 아님. 해석이 갈리는 항목은 `LEGAL_QUESTION`

## 0. 방법·공개 사항
- 조사 에이전트 3개(ACS·일반 흉통 / PE·심낭염·기흉 / GERD·공황·고위험)가 WebSearch·WebFetch로 라이선스 페이지 확인 + 메인 세션이 Europe PMC REST API로 보충 검색·재확인
- **검증 수준**
  - `XML_LICENSE`: Europe PMC 전문 JATS XML의 `<permissions>` 블록을 메인 세션이 직접 추출(가장 강함)
  - `FETCHED_PAGE`: 에이전트가 라이선스 페이지·기사 페이지 문구를 직접 확인
  - `EPMC_META`: Europe PMC 검색 메타데이터 `license` 필드만(전문 XML 없음)
  - `SNIPPET_ONLY`: 검색 snippet만 → **입장 불가**
- 열람 범위: 라이선스 블록·제목·저자·연도·목차 제목만. 본문 의학 내용 추출 0. 목차는 브라질 지침·SIRM/SIC 합의문 2건만 추출(1~2단계 제목)
- 예외 기록: 에이전트 1개가 StatPearls "Chest Pain"과 Wikipedia "Chest pain"의 감별진단 절에서 고위험 질환 **이름**을 읽음(아래 §4, unverified)
- ESC·NICE·APA·AHA/ACC·BTS·ACG 지침 원문 열람 0(EXP-SN-001 감사 결과 승계)
- PMC 웹사이트는 WebFetch 시 reCAPTCHA 차단이 잦음. PMC 정책상 웹사이트에서 체계적 다운로드 금지 → C3 확보 경로는 **Europe PMC REST(`/{PMCID}/fullTextXML`) 또는 PMC OA 공식 경로(OAI-PMH·FTP·Cloud)** 후보
- 확인에 쓴 전문 XML 임시 파일은 scratchpad에서 삭제(C3 아님)

## 1. 주요 발견
1. **재사용 가능한 TIER1 흉통 지침 존재**: 브라질 심장학회 2025 응급실 흉통 지침(CC BY 4.0) · 이탈리아 SIRM/SIC 2025 급성 흉통 합의문(CC BY 4.0). EXP-SN-001에서 "SW/AI 허용 출처 0"이었던 상황과 다름
2. **"무료 열람 ≠ 재사용" 실제 사례**: PMC에서 무료로 읽히는 Springer 심낭염 리뷰 = 출판사 독점 라이선스(NOT_ALLOWED)
3. **정부 출처도 일괄 허용 아님**: 국가건강정보포털 협심증·심낭염 = 공공누리 4유형(상업 금지 + 변경 금지). MedlinePlus는 NLM 작성분(PD)과 A.D.A.M. 백과(건강 IT 시스템 투입 금지) 혼재
4. **StatPearls = CC BY-NC-ND 4.0**: ND가 chunk·임베딩과 충돌하는지 `LEGAL_QUESTION`
5. **ESC가 발행했지만 CC BY인 문서 존재**: ESC Working Group CTPA 합의문(EHJ-CI 2025, 기사 단위 CC BY 4.0). ESC 일반 AI 정책과의 관계 `LEGAL_QUESTION`
6. **공백**: 안정형 협심증 전용 · PE 임상 진단 전용 · 심낭염 TIER1·2 · 공황-흉통 체계적 문헌고찰 — 재사용 가능 출처 미발견

## 2. 후보 표 (C1 결과)

### 2.1 흉통 전반 · ACS · 협심증
| ID | 문서 | 연도 | Tier | 라이선스 | 검증 | reuse_status | 목차상 범위 | 비고 |
|---|---|---|---|---|---|---|---|---|
| R-CP-01 | Diretriz Brasileira de Atendimento à Dor Torácica na Unidade de Emergência – 2025 (Arq Bras Cardiol, PMC12981354, 저자 41) | 2025 | TIER1 학회 지침 | CC BY 4.0 | XML_LICENSE | PRODUCTION_ALLOWED | 초기 접근·흉통 경로 활성 기준·ECG 해석·ACS 진단 정의·불안정 환자 접근·위험 점수·트로포닌 알고리즘·비침습 검사·병원 전 ACS | 포르투갈어+영어 병기. 그림 출처 별도 확인 필요 |
| R-CP-02 | SIRM/SIC consensus document on the management of patients with acute chest pain (Radiol Med, PMC12669346, 저자 50) | 2025 | TIER1 학회 합의문 | CC BY 4.0 | XML_LICENSE | PRODUCTION_ALLOWED | 정의·역학·원인 · 병력·통증 특성·진찰 · ECG · 트로포닌 · 1차 영상 · 위험 알고리즘 · 2차 영상 · ACS 위험 분류 · 심근심낭염 추정 경로 · 비심장성 흉통 추정 경로 | 영상의학·심장학회 공동 |
| R-CP-03 | Quality of undifferentiated chest pain evaluation and diagnosis guidelines: SR & critical appraisal (JRSM Open, PMC11772255) | 2024 | TIER2 SR | CC BY 4.0 | XML_LICENSE | PRODUCTION_ALLOWED | 지침 품질 평가(메타 수준) | 사실 근거보다 지침 지형 |
| R-CP-04 | Clinical assessment of patients with chest pain; SR of predictive tools (BMC Cardiovasc Disord, PMC4721048) | 2016 | TIER2 SR | CC BY 4.0 (+데이터 CC0) | XML_LICENSE | PRODUCTION_ALLOWED | 예측 도구 | |
| R-CP-05 | Diagnostic accuracy of signs and symptoms in ACS and AMI: diagnostic meta-analysis (Scand J Prim Health Care, PMC11834805) | 2024 | TIER2 MA | CC BY 4.0 | XML_LICENSE | PRODUCTION_ALLOWED | 증상·징후 진단 정확도 | 병력 소견 근거로 직접 관련 |
| R-CP-06 | CCTA vs standard of care for acute chest pain: living SR & MA (Radiol Cardiothorac Imaging, PMC10483255) | 2023 | TIER2 MA | CC BY 4.0 | XML_LICENSE | PRODUCTION_ALLOWED | 영상 검사 비교 | 검사 쪽 근거(NBI 2.0) |
| R-CP-07 | Treatment efficacy for non-cardiovascular chest pain: SR & MA (PLOS ONE) | 2014 | TIER2 MA | CC BY | FETCHED_PAGE | PRODUCTION_ALLOWED | 비심장성 흉통 치료 | 진단 근거 아님 — 범위 경계 |
| R-CP-08 | 2024 KSMI/NECA guideline for pharmacotherapy of ACS (Korean Circ J, PMC11685345) | 2024 | TIER1 학회·정부 | CC BY-NC 4.0 | XML_LICENSE | RESEARCH_ALLOWED_ONLY | 약물 치료 | 진단 근거 아님 — 범위 밖 가능성 |
| R-CP-09 | NHLBI Health Topics(심근경색·협심증 등) | 상시 | TIER1 정부(환자 교육 성격) | 미국 연방 저작물 PD(대부분) | FETCHED_PAGE(정책) | PRODUCTION_ALLOWED(페이지별 확인) | — | 삽화(Nucleus Medical Media 등) 제3자 저작권 제외. "출판물 변경 자제" 요청 → LEGAL_QUESTION(규범) |
| R-CP-10 | AHRQ CER #171 Noninvasive testing for CAD | ~2017 | TIER1 정부 근거보고서 | PD 추정 | SNIPPET_ONLY | 입장 불가(재확인) | 비침습 검사 | |

### 2.2 폐색전증 · 심낭염 · 심근염 · 기흉
| ID | 문서 | 연도 | Tier | 라이선스 | 검증 | reuse_status | 비고 |
|---|---|---|---|---|---|---|---|
| R-PE-01 | ESC WG on Pulmonary Circulation clinical consensus: CTA for suspected acute PE (Eur Heart J Cardiovasc Imaging, PMC13376148) | 2025 | TIER1 학회 합의문 | CC BY 4.0 | XML_LICENSE | PRODUCTION_ALLOWED + **LEGAL_QUESTION(ESC 정책)** | 영상 수행·판독 — 검사 쪽 |
| R-PE-02 | EANM guideline for V/Q SPECT for diagnosis of PE (Eur J Nucl Med Mol Imaging, PMC6813289) | 2019 | TIER1 학회 지침 | CC BY 4.0 | XML_LICENSE | PRODUCTION_ALLOWED | 핵의학 영상 — 검사 쪽 |
| R-PE-03 | Evidence-based perioperative diagnosis and management of PE: SR (Ann Med Surg, PMC9142630) | 2022 | TIER2 SR | CC BY 4.0 | XML_LICENSE | PRODUCTION_ALLOWED | 수술 전후 맥락 |
| R-PE-04 | SR & MA of diagnostic delay in PE (Eur J Gen Pract, PMC9246192) | 2022 | TIER2 MA | CC BY 4.0 | XML_LICENSE | PRODUCTION_ALLOWED | 진단 지연 요인 |
| R-PE-05 | Diagnostic blood biomarkers for acute PE: SR (Diagnostics) | 2023 | TIER2 SR | CC BY | EPMC_META | PRODUCTION_ALLOWED(전문 XML 없음, 출판사 페이지 재확인) | |
| R-PE-06 | Diagnostic prediction models for suspected PE: SR & external validation (BMJ, PMC4561760) | 2015 | TIER2 SR | CC BY-NC 4.0 | XML_LICENSE | RESEARCH_ALLOWED_ONLY | |
| R-PE-07 | AHRQ VTE guide | — | TIER1 정부 | PD 추정 | SNIPPET_ONLY | 입장 불가(재확인) | 예방 중심 — 범위 경계 |
| R-PER-01 | Importance of ECG in diagnosis of acute pericarditis and MI: review (Cureus, PMC9683083) | 2022 | TIER2-(서술 리뷰, 저권위 저널) | CC BY 3.0 | XML_LICENSE | PRODUCTION_ALLOWED | 심낭염–MI ECG 감별 |
| R-PER-02 | Acute Pericarditis: Update (Curr Cardiol Rep, PMC9122084) | 2022 | TIER2 | Springer 독점 라이선스 | FETCHED_PAGE | **NOT_ALLOWED** | 무료 열람 함정 사례 |
| R-PER-03 | StatPearls Pericarditis (NBK431080) | 2026 | TIER4 | CC BY-NC-ND 4.0 | FETCHED_PAGE | 보류(NC·ND) | |
| R-PER-04 | 국가건강정보포털 심낭염 | 2026 | TIER4 정부 | 공공누리 4유형 | FETCHED_PAGE | 보류(NC·ND) | |
| R-MYO-01 | SCD after acute myocarditis with arrhythmic presentation: SR & MA (Open Heart, PMC11603706) | 2024 | TIER2 MA | CC BY 4.0 | XML_LICENSE | PRODUCTION_ALLOWED | 심근염(EXP-SN-001 CONFIRM_NEEDED 질환) |
| R-PTX-01 | SPLF/SMFU/SRLF/SFAR/SFCTCV guidelines for primary spontaneous pneumothorax (Ann Intensive Care, PMC10509123) | 2023 | TIER1 5개 학회 지침 | CC BY 4.0 | XML_LICENSE | PRODUCTION_ALLOWED | 정의·진단·초기 평가·치료 |
| R-PTX-02 | ERS/EACTS/ESTS spontaneous pneumothorax guideline (ERJ 2024) | 2024 | TIER1 | 미확인(403) | — | LICENSE_UNCLEAR | |
| R-PTX-03 | StatPearls Pneumothorax · 국가건강정보포털 기흉 | — | TIER4 | NC-ND · 유형 미확인 | — | 보류 | |

### 2.3 GERD·비심장성 흉통 · 공황 · 고위험(대동맥·식도)
| ID | 문서 | 연도 | Tier | 라이선스 | 검증 | reuse_status | 비고 |
|---|---|---|---|---|---|---|---|
| R-GI-01 | Esophageal emergencies: WSES guidelines (World J Emerg Surg, PMC6544956) | 2019 | TIER1 학회 지침 | CC BY 4.0 | XML_LICENSE | PRODUCTION_ALLOWED | 이물·부식·식도 천공·외상 |
| R-GI-02 | 2020 Seoul Consensus on diagnosis and management of GERD (J Neurogastroenterol Motil, PMC8521465) | 2021 | TIER1 학회 합의 | CC BY-NC 4.0 | XML_LICENSE | RESEARCH_ALLOWED_ONLY | 한국 학회 |
| R-GI-03 | Lyon Consensus 2.0 (Gut, PMC10846564) | 2024 | TIER2 전문가 합의 | CC BY-NC 4.0 | XML_LICENSE | RESEARCH_ALLOWED_ONLY | |
| R-GI-04 | Rome IV 문서·기준 | — | TIER1 | 유료 라이선스 계약 | FETCHED_PAGE(정책) | **NOT_ALLOWED**(계약 전) | 과금 가능 영역 — 진행 0 |
| R-PAN-01 | Biobehavioral approach to distinguishing panic symptoms from medical illness (Front Psychiatry, PMC11109415) | 2024 | TIER2 리뷰 | CC BY | XML_LICENSE | PRODUCTION_ALLOWED | 목차에 흉통 절(에이전트 확인) |
| R-PAN-02 | WHO mhGAP | — | TIER1 국제기구 | CC BY-NC-SA 3.0 IGO(정책 페이지) | FETCHED_PAGE(정책만) | RESEARCH_ALLOWED_ONLY + LEGAL_QUESTION(SA) | 문서 본문 라이선스 재확인 |
| R-AO-01 | Diagnostic accuracy of alternative biomarkers for acute aortic syndrome: SR (Emerg Med J, PMC11503200) | 2024 | TIER2 SR | CC BY 4.0 | XML_LICENSE | PRODUCTION_ALLOWED | |
| R-AO-02 | Aortic dissection detection risk score ± D-dimer for AAS: MA (PLOS ONE, PMC11192411) | 2024 | TIER2 MA | CC BY | XML_LICENSE | PRODUCTION_ALLOWED | |
| R-AO-03 | Diagnostic biomarkers and aortic dissection: SR & MA (BMC Cardiovasc Disord, PMC10563263) | 2023 | TIER2 MA | CC BY 4.0 | XML_LICENSE | PRODUCTION_ALLOWED | |
| R-AO-04 | Current Understanding of Aortic Dissection (Life, PMC9605578) | 2022 | TIER2- 서술 리뷰 | CC BY | XML_LICENSE | PRODUCTION_ALLOWED | |

### 2.4 집합 출처 정책
| ID | 대상 | 결론 |
|---|---|---|
| R-AGG-01 | PMC OA subset | 기사마다 라이선스 다름. "OA subset" 라벨만으로 허용 아님. 웹사이트 체계적 다운로드 금지, 공식 대량 경로만 |
| R-AGG-02 | MedlinePlus | NLM 작성분 PD / A.D.A.M. 백과 = "EHR·환자 포털·건강 IT 시스템 투입 금지" → 일괄 수집 금지, 페이지별 판정 |
| R-AGG-03 | 공공누리 | 1유형만 상업·변경 허용. 2유형 NC · 3유형 ND · 4유형 NC+ND. 페이지별 유형 확인 |
| R-AGG-04 | 국가정신건강정보포털·국가건강정보포털 | 포털 단일 라이선스 없음, 저작물별 유형 확인. 확인된 2건(협심증·심낭염)은 4유형 |
| R-AGG-05 | Wikipedia(CC BY-SA 4.0, TIER4) | SA 파생물 범위 LEGAL_QUESTION. 단독 근거 부적절 |
| R-AGG-06 | StatPearls(CC BY-NC-ND 4.0) | NC+ND. chunk·임베딩 허용 여부 LEGAL_QUESTION — 사용자 결정 전 제외 |

## 3. 질환별 coverage (C2 승인 후보 = PRODUCTION_ALLOWED + XML_LICENSE)
| 범위 | TIER1 | TIER2 | 판정 |
|---|---|---|---|
| 흉통 전반·ACS | R-CP-01, R-CP-02 | R-CP-03~06 | 충분 |
| 안정형 협심증 | (R-CP-01·02 일부 가능성, 목차상 미확인) | — | **공백** |
| 폐색전증 | R-PE-01(LEGAL_QUESTION), R-PE-02 — 둘 다 영상 검사 중심 | R-PE-03, R-PE-04 | 부분(임상 진단 지침 공백) |
| 심낭염 | (R-CP-02 심근심낭염 경로) | R-PER-01(저권위) | **약함** |
| 심근염 | — | R-MYO-01 | 부분 |
| 기흉 | R-PTX-01 | — | 충분(자연 기흉) |
| GERD·비심장성 흉통 | R-GI-01(식도 응급) · (R-GI-02 NC) | (R-GI-03 NC), R-CP-07 | NC 허용 여부에 의존 |
| 공황·불안 | (R-PAN-02 NC-SA) | R-PAN-01 | 약함 |
| 대동맥 증후군(OOS) | — | R-AO-01~04 | 부분 |
| 식도 파열(OOS) | R-GI-01 | — | 충분 |

## 4. out-of-scope 고위험 원인 — 출처에 실제로 나온 이름만
| 출처 | 위치 | 이름 | 검증 |
|---|---|---|---|
| R-CP-01 | 그림 제목(3장) | 대동맥 박리 · 우심실 압력 과부하 · 심근경색 · 대량 심낭 삼출 | 메인 세션 목차 추출 |
| R-CP-01 | 4.1 | 혈역학적 불안정 흉통 접근 | 동일 |
| R-CP-02 | 목차 | ACS(STEMI·고위험 NSTEMI) · 심근심낭염 · 비심장성 흉통 | 동일 |
| R-GI-01 | 목차 | 식도 천공(경부·흉부·복부) · 식도 외상 · 부식제 · 이물 | 에이전트 FETCHED |
| StatPearls Chest Pain(보류 출처) | 감별진단 절 | 대동맥 박리 · 기흉 · 심낭 압전 · 식도 파열(Boerhaave) | 에이전트, unverified |
| Wikipedia Chest pain(보류 출처) | 감별진단 절 | 심근경색 · 폐색전증 · 흉부 대동맥 박리 · 식도 파열 · 긴장성 기흉 · 심낭 압전 | 에이전트, unverified |

- 최종 OOS 목록은 C2 승인 출처의 **원문 본문**에서 C3 이후 확정(이번 단계는 이름 후보만)

## 5. 사용자 결정 필요
1. **C2 1차 승인 후보**(PRODUCTION_ALLOWED + XML_LICENSE): R-CP-01~06 · R-PE-02~04 · R-PER-01 · R-MYO-01 · R-PTX-01 · R-GI-01 · R-PAN-01 · R-AO-01~04 (19건)
2. NC 출처(R-CP-08 · R-PE-06 · R-GI-02 · R-GI-03)를 연구 corpus에 넣을지(`D-LIC-NC`)
3. ND·SA 출처(StatPearls · 공공누리 3·4유형 · WHO · Wikipedia) 처리(`D-LIC-ND`)
4. R-PE-01(ESC 발행 CC BY) 포함 여부
5. 공백(안정형 협심증·PE 임상 진단·심낭염·공황) 추가 탐색 여부 — 한국어 1유형 출처 포함
