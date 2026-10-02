# STEP15 v2 — BLIND DISEASE PROFILE CURATION report
Generated 2026-09-21T23:16:32 · frozen (PROFILE_FREEZE_V2.json) · **판정 STEP15_V2_PROFILE_PARTIAL_GO**

## Blind
- blind_status: **BLIND_VALID** (disclosure: project memory one-line summaries read at session start; no DDXPlus data/evidence/questions opened; v1 DDXPlus-comparison files 04-08 not opened)
- DDXPlus 접근: 없음 (scripts grep 통과, fetch_log에 외부 URL만)

## 질환·출처
- 10/10 질환 완료, 실패 0
- 사용 source 34 (Tier1 22 / Tier2 3 / Tier3 9); 시도 51, 차단/무내용 17
- 독립 기관 <2 인 질환: 0 (HIV = CDC + NEJM 2개; HIV.gov는 CDC 재인용이라 미산입)
- 가이드라인급 출처 없는 질환: ['PSVT', 'Stable angina', 'Unstable angina'] → MANUAL_SOURCE_REQUEST.md 10건
- MedlinePlus 비중 v1 0.6 → v2 0.24; Tier1 비중 0.33 → 0.65

## Facts
- 총 367 (v1 150) · value-level 259 · source 없는 fact 0 · duplicate 0 · schema 오류 0 (빌드 시 즉시 실패 방식) · 인용문 원문 대조 367/367 통과 (v1은 1/150만 verbatim)
- 충돌 그룹 8 (ARS 기간, CRS 병인, 후두염 기간, 인두염 기간, 안정협심증 기간, 불안정협심증 기간, 스콤브로이드 발병/지속) — 평균내지 않고 행 분리
- 질환별: {'Acute rhinosinusitis': 45, 'Stable angina': 45, 'Scombroid poisoning': 44, 'Acute laryngitis': 36, 'Chronic rhinosinusitis': 34, 'Unstable angina': 33, 'Acute HIV infection': 33, 'PSVT': 33, 'Viral pharyngitis': 32, 'Acute COPD exacerbation': 32}

## 표준개념 (02)
- EXACT 54 · PARTIAL 155 (동의어/상위개념 경유) · AMBIGUOUS 13 · FAIL 0 · ATTRIBUTE_NOT_MAPPED 145 (시간/유발/완화/기준/감별 속성은 CUI 강제 안 함)
- SNOMED 부여 169 · HPO 110 · 매핑 review 182

## Pair (04, 외부 fact만)
- A 급성 vs 만성 부비동염: 기간(<12주 vs ≥12주/3개월)·발병(급성·감기 후 vs 지속)·객관소견 필수 여부(CRS)·발열의 의미(ARS 기준 vs CRS 대체진단 신호)·double worsening(ARS)
- B 안정 vs 불안정 협심증: 유발(노작/스트레스/추위 vs 안식·수면·저강도)·완화(휴식/NTG 유효 vs 무효)·기간(수 분 vs >15-20분)·진행(2개월 불변 vs 신규/crescendo)
- C 급성 후두염 vs 바이러스성 인두염: 부위(후두/성대 vs 인두·편도)·핵심증상(쉰목소리/실성 vs 연하통)·발병·경과(3일 악화 후 1-2주 vs ~1주)·red flag 차이. 공통: 인후통·발열·기침·경부 림프절
- 이 단계에서 DDXPlus 질문 존재 여부 미확인

## 사람 검토
- 05 큐 237행 (multi-CUI, synonym/parent 매핑, 충돌, 음성소견 해석, 기준 vs 일반증상, 병력/가족력 배치, 출처 비독립) · 06 시트 367행 (approve/corrected_value/reviewer_note 공란)

## v1 대비 (08)
- 해결: family_context 오배치 17→0, duration 비시간값 4→0, location 비해부값 2→0, 수기 TSV→dataclass+검증, 인용문 verbatim 1/150→367/367, 충돌 기록 0→8, 단일출처 질환 3→0, Tier1 비중 0.33→0.65, 작성자 blind
- 남은 문제: 협심증·PSVT·HIV·ABRS 학회 가이드라인 원문 차단(초록만 또는 403) → 정부 페이지 의존; PARTIAL 매핑 155; HIV 증상 목록 CDC 계열 단일; Mandell 장은 교과서(Tier3)

## 49개 확장 (07)
- source ≈ 167 · fact ≈ 1798 · review(fact) ≈ 1000 · 수동 문서 ≈ 49 · 빌더 세션 ≈ 120분 (선형 외삽; 희귀 질환은 수동 비율 상승 가능)

## 가장 중요한 발견
- 정부/공공 페이지(CDC·NHLBI·NHS·NICE·FDA)와 공개 PDF(EPOS 2020, GOLD 2025)만으로도 10질환 모두 2개 이상 독립 기관 출처와 value-level 속성(기간·유발·완화·진행·노출)을 확보할 수 있었고, 인용문 전수가 원문에서 기계적으로 검증됨.
## 가장 큰 문제
- 학회 가이드라인(AHA/ACC, ESC, IDSA, HRS)과 clinicalinfo.hiv.gov가 일괄 403 → 협심증/PSVT는 진단기준 수준 fact가 정부 환자용 페이지 표현에 머무름.

## 다음 단계
- 별도 evaluator 세션에서 frozen v2 profile(SHA 고정)을 DDXPlus와 비교. 이 세션은 여기서 중단.
