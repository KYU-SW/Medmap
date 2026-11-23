# 이전 결과·보유 자산·제약 (53회차 메인, 2026-11-21)

## 이전 보고서 8개 — 모두 존재 확인
R1 Gate0(JNP·MDQ NO-GO) · R2 K1·K7(NO-GO; K7 은 MedMap 구현 결함 stateAsOf 승인 시각 등) · R3 복합질환 6유형(철회) · R4 GuidelineCoordination 재현(C) · R5 B7+B9+B10 통합(C, 결합 정식화 1,261/1,261) · R6 실제 문서 공유 변수(범주 변화 0) · R7 MIMIC Demo 검사 공백(B; 새 채혈 시점 약 19% 에서 마지막 이용 가능 값과 곧 나올 값이 경계 기준 반대 — 정보 신선도 문제, 가설) · R8 B7+B9 실제 사례(D; 독립 정답 없음, 오류는 지침 해석 단계에서 8건).
반복 금지: JNP·MDQ·K1·K7·C1·복합질환 6유형·B7+B9+B10 결합 최적화, 신장 기능·칼륨 공유 변수.

## 보유 데이터 (사용자 PhysioNet 자격 인증 보유 — 사용 시 규칙 준수)
- 공개: MIMIC-IV Demo v2.2(ODbL, `~/medmap-patient-lab-gap-pilot/data/raw/hosp/` 6파일)
- 자격 인증(로컬, `C:\Users\<user>\Downloads\`): mimic_raw/mimiciv_3.1/hosp(labevents·d_labitems·patients·admissions), mimic-iv-note_2.2 radiology·radiology_detail, mimic-iv-ed-2.2, mimic-iv-ecg 일부·ecg-ext-icd 라벨, mimic-iv-ext-cardiac-disease, MIMIC-IV-Ext-PE(전문가 2인 라벨), ER-REASON v1.1.0(전문의 가능성 변화 점수)
- 규칙: 자격 인증 데이터는 **로컬 스크립트만**, 세션·외부 LLM·웹에는 스키마·코드·집계만. G: 드라이브 금지. 51회차 결정: 정식 MIMIC-IV 3.1 은 데모 파일럿에 쓰지 않음(새 사용은 사용자 승인 필요).
- 전문의 섭외 불가(사용자 결정 40회차) → 독립 정답은 기존 공개 전문가 라벨·실제 기록 사건·수학 정답에서만.

## MedMap 기존 기능(연결 가능)
진단 가설–근거 연결, 출처·발생 시점·인지 시점(as-of) 기록, 정정·중복 처리, 보류 사유, 구조화 인계(MM2), 의사 설명 → 후보 → 확인.
