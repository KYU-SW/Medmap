# STEP23 표현 생성 프로토콜 (생성·학습 전 작성, 2026-10-08)

## 목적
STEP22 실패가 선형 모델 한계인지, 한국어 학습 표현 부족인지 분리한다. 모델은 그대로 두고, TARGET_20 학습 표현만 늘린다.

## 대상 class
- TARGET_20 = STEP21 pilot 20개, 실제 inventory ID만 사용: pain, dyspnea, fever, cough, nausea, vomiting, diarrhea, dizziness, loc, palpitations, fatigue, limb_weakness, swelling, hemoptysis, hematemesis, confusion, chills, sore_throat, heartburn, decreased_appetite.
- 사용자 후보와의 차이(새 class를 만들지 않음):
  - headache·abdominal pain → `pain` + site 속성
  - syncope → `loc`
  - weakness → `limb_weakness`
  - constipation → inventory에 없음(STEP20: E_150 극성 반전 PARTIAL)
- CONFUSER_57: STEP22 CURATED 표현을 그대로 유지한다. label space는 77개로 STEP22와 동일하다.

## 작성자 격리 (test 누수 방지)
- 메인 세션(Claude)은 STEP22 분석 중에 test 문장 약 20개를 봤다. 따라서 메인 세션은 표현을 쓰지 않는다.
- 작성 방식: `claude -p --restricted --strict-mcp-config --tools Read,Write`, `ENABLE_CLAUDEAI_MCP_SERVERS=false`, model opus.
  - 격리 폴더 `~/medmap_step23_authoring_ws/`에서만 실행한다.
  - 작성 4회(concept 5개씩, concept당 50행)를 순차 실행한다.
- 격리 폴더 입력은 다음 3가지뿐이다.
  1. `concepts.md`: 의학 용어 수준의 정의와 구분 기준. 메인 세션이 쓴 구어 예시는 오염 우려로 삭제했다.
  2. `existing_dictionary_expressions.tsv`: STEP22 CURATED 중 TARGET_20의 기존 MedMap 표현 92개
  3. 작성·감사 지시문
- test, dev, STEP21/22 출력, 오류 분석은 넣지 않았다.
- 의미 감사는 작성과 다른 독립 `claude -p` 세션 2회가 한다.
  - 판정값: VALID / AMBIGUOUS / WRONG_CONCEPT / TOO_GENERIC / NOT_SINGLE_PRESENT
  - 메인 세션은 감사 판정을 바꾸지 않는다.
- 격리 검사(`check_authoring_isolation.py`): transcript의 모든 tool_use가 Read/Write이고 경로가 격리 폴더 안인지 확인한다.
- 남는 한계: STEP21 test도 Claude가 작성했다. 같은 모델 계열이 쓴 표현은 test와 표면이 겹칠 수 있다. 이 효과는 아래 기계 필터로 완전일치·근접 중복만 제거한다. 그보다 약한 유사성은 남으므로, regression test 성능은 과대평가될 수 있다.

## 기계 검사 순서 (`audit_expression_quality.py`, 생성 후 1회)
1. INVALID_ROW
2. 감사자 판정(VALID가 아니면 제외)
3. TOO_SHORT: 공백 제거 후 길이 ≤ 2
4. CONFLICT: 같은 표현이 다른 class에도 있음
5. EXACT_DUPLICATE: 기존 표현 또는 앞선 생성 표현과 완전일치
6. NEAR_DUPLICATE: 같은 class 안에서 difflib 유사도 ≥ 0.90
7. REMOVED_TEST_EXACT / REMOVED_TEST_NEAR_DUPLICATE: regression test(177)와 완전일치 또는 유사도 ≥ 0.80
8. REMOVED_DEV_NEAR_DUPLICATE: dev(97)와 완전일치 또는 유사도 ≥ 0.80
9. REMOVED_PROMPT_EXAMPLE: 지시문이 금지한 예시 5개와 유사도 ≥ 0.80

제거한 표현은 대체하지 않는다. 재생성도, 필터 재조정도 하지 않는다.

## 모델·선택
- 후보는 LINEAR_CHAR, LINEAR_WORD_CHAR 두 개다(사전 등록).
- ngram·min_df는 STEP22 dev 선택값으로 고정한다.
- C ∈ {0.5, 1, 2, 4} × class_weight ∈ {None, balanced}만 dev(core 59)에서 선택한다. STEP22 설정도 이 grid에 포함된다.
- ORIGINAL(276)과 EXPANDED에 같은 코드와 같은 grid를 적용한다.
- BEST_MODEL은 EXPANDED의 dev 결과로 정한다.
- auto-accept margin 임계값은 dev에서 정하고 test에는 1회만 적용한다.

## 평가·판정
- `evaluate_regression.py` 문서열에 규칙을 고정했다.
- 기존 test의 명칭은 FIXED_REGRESSION_TEST다. 개발 방향 결정용이며, 최종 일반화 성능을 주장하지 않는다.
- NEW_BLIND_HOLDOUT_REQUIRED = YES
