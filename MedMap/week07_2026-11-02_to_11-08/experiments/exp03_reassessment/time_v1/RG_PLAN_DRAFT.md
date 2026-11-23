# EXP-03-TIME 실제 MIMIC 집계 — rg-plan 입력 초안(미등록)

- 상태: 초안. Research Guardian `rg-plan` 등록·`rg-gate` 판정 **없음**. 본실행 BLOCKED(사용자 명시 승인 전).
- 실험 ID 후보: EXP-MAI-003-TIME(등록 시 확정)

## 연구 질문
시간 정책(STRICT_AVAILABLE_TIME vs S1_TRIAGE_AT_INTIME_APPROX vs S2_STRICT_A_ONLY)에 따라 실제 ED 체류의 시간순 증거 포함률과(SIMULATED_WD 주입 시) 재검토 상태·알림이 얼마나 달라지는가 — 시스템 동작 기술, 임상 정확도 아님.

## 데이터(보유분만, 새 다운로드 없음)
- EXP-02 봉인 추출 `extract_v2_20261030_1139`(ED 12,358 체류·10,277 환자: 4질환 코호트 ∪ ED 중 흉부 CTA ∪ PE 의뢰 사유) — 선택 편향 있음(전체 ED 대표 아님).
- 판독 분류 = 동결 v3b(EXP-02, 수정·재평가 없음). TEST 분할과 무관(문서 분류기만 사용).

## 분석 단위·분모
- 기록 단위: 판독 문서 · 검사 행 · ECG 기록 · triage 행 / 체류 단위 / 환자 단위(체류 수 병기, 군집 부트스트랩).

## 측정(사전 고정)
1. 원천별 분모와 등급(A·B·C)별 건수·비율
2. UNKNOWN_AVAILABILITY · TIME_CONFLICT · AMBIGUOUS_STAY · 중복 · POST_ED 건수
3. 정책별 체크포인트(T0=intime, T1=min(intime+3h,outtime), T2=outtime) 사용 증거 건수·체류 비율
4. SIMULATED_WD(전 체류 PE 가설, 시각 = intime) 주입 시 정책 간 요약 상태·알림 변경 체류 수 — '시간 정책 민감도'로만 해석
5. 안전 조건: STRICT 누출 0(assess(전체,T)=assess(T까지,T)), 등급 C 사용 0, 출처 누락 0 — 하나라도 위반 시 결과 무효·중단

## 금지·한계
- 실제 WD 없음 → 알림의 의학적 정오 채점 없음. ED·퇴원 진단 코드를 가설·정답으로 쓰지 않음.
- 공개 = 집계만, 10 미만 '<10'. 원문·식별자·정확 시각·검사값 비출력.
- 시간 정책은 EXP-02 공개 집계를 본 뒤 작성 — 독립 검증 아님.

## 실행 형태(승인 후)
- 로컬 스크립트(nohup + RAM 감시), 출력 = 공개 집계 JSON + 봉인 체류별 결과.
