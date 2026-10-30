# STEP29.2 B4 단독 연결 가드 재설계

구현: `scripts/b4_evidence_guard.py`. STEP27 B4·STEP28.8 P5·STEP29.1 가드 원본은 호출만(수정 없음). 정책별 수치는 `step29_2_report.md`·`outputs/b4_guard_ablation.csv`.

## 공통(v3, B0–B3)
- STEP29.1 가드 PAIN_PREDICATE_MISMATCH·LEXICAL_OVERLAP_ZERO 그대로.
- EVIDENCE_IDEOPHONE_MISSING 보정: 근거 용어의 반복형 시간·정도 부사(점점·가끔가끔 등)는 의성·의태어로 세지 않는다
  (근거 '다리가 점점 붓고 있어요' 때문에 '다리가 부어요'가 막히던 문제).

## 변형
- B0: B4 단독 규칙 없음(STEP29 상태).
- B1: STEP29.1 MODEL_ONLY_NO_CUE 그대로(증상 단서 없으면 차단 — 엄격).
- B2: 증상 근거 선택 가드. 술어(용언) 존재 · 비증상 명사(약물·검사·치료·질환) 없음 · 논항 명사가 신체/기능/증상/시점/사람/위치/정도어이거나 반복형 의성어 ·
  STEP27 라우터를 단위 문장으로 다시 계산해 선형·KoELECTRA 일치 + 확신도 ≥ 0.95 + 비증상 확률 < 0.5. 하나라도 아니면 UNCERTAIN(원 concept 보존).
- B3: B2 + 의미 충돌 보류(어지럼 단서 ↔ 혼동·의식소실, 오심 ↔ 구토, 구토 ↔ 오심, 사지 떨림 ↔ 오한, 코피 ↔ 객혈·토혈, 목 부위 ↔ 일반 통증).

## 원칙
- 특정 문장·STEP29.1 차단 정답 24건 하드코딩 없음. 규칙은 언어 단서(품사·논항·어휘군)와 모델 특징만 사용.
- 막힌 mention 은 `status=UNCERTAIN`, `guard_blocked_concept`, `guard_reasons`(B4_EVIDENCE_INSUFFICIENT·B4_SEMANTIC_CONFLICT·B4_NON_SYMPTOM_CONTEXT),
  `b4_guard_detail`, `b4_evidence`(라우터 특징 포함)를 남기고 모델 입력 불가.
- 정책 선택은 DEV + 노출 pilot 으로 사전 규칙(gates.select_policy)에 따라 1회, HOLDOUT 은 선택에 쓰지 않음.
- 규칙 설계에 노출 pilot 의 B4 단독 사례(STEP29.1 차단 25건 포함)를 개발 자료로 사용했다 — 독립 검증은 HOLDOUT 결과로만 본다.
