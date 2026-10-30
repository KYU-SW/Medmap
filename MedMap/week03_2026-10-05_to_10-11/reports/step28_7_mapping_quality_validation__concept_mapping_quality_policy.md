# STEP28.7 Concept Mapping Quality Policy (연구용)

이 문서는 규칙만 적는다. 수치는 `docs/step28_7_report.md`·`outputs/step28_7_verdict.json` 에서 읽는다.
연구용 품질 기준이며 임상 안전성 승인 기준이 아니다. PRODUCTION_READY = NO.

## 1. 근거 등급(evidence_level)

| 등급 | 조건 | 이번 단계 |
|---|---|---|
| LEVEL_0 | 두 LLM 작성자 모두 연결 근거 없음 | 부여 |
| LEVEL_1 | 한 작성자만 제안, 또는 두 작성자가 서로 다름 | 부여(보류) |
| LEVEL_2 | 두 작성자(opus·sonnet) 범주·concept 일치 | 부여 |
| LEVEL_3 | LEVEL_2 + HPO 정의 대비 자동 감사 EXACT | 부여. 감사자 = opus(작성자 A 와 같은 모델) → 독립 검증 아님 |
| LEVEL_4 | 독립 적격 인간 검토 완료 | **0 — 부여하지 않음** |

LEVEL_3 도 SILVER 다. 모델 간 일치는 독립 검증이 아니다.

## 2. 격리 provenance

- 작성 세션 transcript 검사 PASS → `ISOLATION_PASS`, FAIL → `ISOLATION_FAIL`, 기록 없음 → `ISOLATION_UNVERIFIED`.
- '교차 오염 증거 없음' 은 PASS 로 바꾸는 근거가 아니다.
- ISOLATION_FAIL 행은 양성 연결(기존·동의어·하위·신규 수락)에 쓰지 않는다. '연결 거부(비증상)' 방향 근거로만 쓴다.

## 3. concept 분류(A–F)

A 기존 동의어 · B 기존 속성 조합 · C 기존 하위 · D 독립 신규 · E 비증상 · F 불확실.
- ontology 부모·자식 관계만으로 동의어로 판정하지 않는다(하위 ≠ 동의어).
- C(기존 하위)는 부모 feature 로 자동 통합하지 않는다(예: 마른기침 → cough 는 연구용 부모 후보 표시만, '마른' 속성 보존).
- 피로와 의식 수준 저하(무기력·졸림)를 동의어로 취급하지 않는다.
- 분류자 = STEP28.7 Claude 세션(비인간·비독립). 결정 파일 `data/concept_review_decisions.csv`.

## 4. 정제 대응표 매핑 결정

`scripts/clean_silver_mappings.py` 문서열이 정본. 요약:
- 수락: ACCEPT_EXISTING · ACCEPT_EXISTING_SYNONYM · ACCEPT_SUBTYPE · ACCEPT_NEW_CANDIDATE · ACCEPT_NON_SYMPTOM
- 보류: HOLD_SINGLE_AUTHOR · HOLD_AUTHOR_CONFLICT · HOLD_ISOLATION · HOLD_AUDIT_NOT_EXACT · HOLD_CONCEPT_UNCERTAIN · HOLD_SEMANTIC_TYPE
- 반려: REJECT_AUDIT · 없음: NO_MAPPING(원문 보존)
- 표시 허용: ACCEPT_EXISTING·SYNONYM 만(77 concept 확인 질문). 신규·하위는 표시 안 함.
- usable_by_disease_model: 전부 False.

## 5. 검색 순서(정책 D)

`scripts/safe_offline_retriever.py` 문서열이 정본. 요약:
1. 기존 77 한국어 색인 EXACT · 통증+부위 규칙 · STEP27 B4(= STEP28.5 KO 경로)
2. 정제 SILVER 대응표 완전일치 조회(부분·유사 일치 없음)
3. 기존 결과와 SILVER 가 다르면 점수로 고르지 않고 UNCERTAIN(표시 없음)
4. 한국어 결과가 없을 때만 SILVER 결정(기존·하위·신규·비증상·보류) 사용
5. 아무 근거도 없으면 UNKNOWN_SYMPTOM / UNCERTAIN, 원문 보존

출력 상태: EXISTING_CANONICAL · EXISTING_COMPOSITE · EXISTING_SUBTYPE · NEW_ONTOLOGY_CANDIDATE · NON_SYMPTOM · UNKNOWN_SYMPTOM · UNCERTAIN.

## 6. 의미 구별 규칙(지시문 §4·§10)

코피 ≠ 객혈·토혈 · 구토 ≠ 오심 · 떨림 ≠ 오한 · 고혈압 ≠ 증상 · 기침 억제제 ≠ 기침. 위반 = 자동 concept 또는 표시 후보에 해당 concept.

## 7. 금지

추가 LLM·외부 API·다운로드·재학습·제품/PatientState 변경·기존 산출물 덮어쓰기·MDRKOR·KCD5·SNOMED/UMLS 문자열 외부 전송·라이선스 원문 공개·commit/push.
