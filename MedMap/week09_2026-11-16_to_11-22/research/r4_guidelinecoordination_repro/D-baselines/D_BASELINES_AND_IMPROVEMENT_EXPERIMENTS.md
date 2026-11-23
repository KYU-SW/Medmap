# D. 기존 강한 방법과 개선 비교 실험 (변이 시험)

작성: SUBAGENT D, 2026-11-18. 대상: GuidelineCoordination commit deb4ae34 (`rules_gold.json` 563건, `pipeline/`).
범위 경고: **실제 논문 오류 사례(LLM 예측 규칙)는 저장소에 없다.** 그래서 이 문서의 수치는 모두 gold 규칙에 통제된 오류를 넣은 **합성 변이 실험**의 결과다. "논문 오류를 해결하는 성능"이 아니고 "기존 방법이 어떤 오류 유형을 잡는가"의 측정이다.

## 0. 판정 요약

| 항목 | 판정 |
|---|---|
| 1. 원본 결정적 판정 원리 문서화 | 통과 (코드 확인 + 실행 확인) |
| 2. 변이 시험 (13개 연산자, 573개 변이, B1~B5) | 통과 |
| 3. 탐지 안 되면서 하류 판정을 바꾸는 유형 분석 | 통과: 7개 유형 확인, 원인 분류 |
| 4. 새 방법 제안 | 조건부 통과: B6(권고 방향 단서 검사) 1개. 사전 기준(탐지 ≥0.50, 위양성 ≤0.20)을 eval에서 충족(0.574 / 0.054). 다만 범위가 좁다 |
| 실제 논문 오류 해결 성능 | 미검증 (LLM 예측 미공개, 과금 승인 없음) |

핵심 수치 [실제 실행해 확인한 결과]
- 정답 없이 쓸 수 있는 기준선 합집합(B1∪B3∪B5) 탐지율: 전체 변이의 **44.9%**. 정답 비교(B2)는 100%.
- 기준선으로 **탐지되지 않았는데 하류 충돌 판정은 바뀐** 변이: **29.8%** (171/573).
- 이런 '조용한 오류' 비율이 큰 유형: 권고 방향 반전 M13 **0.90**, AND→OR M02 **0.84**, 어휘 안에 있는 약 동의어 M09(in-vocab) **0.77**(13건), 부정 제거 M04 0.58, 예외 삭제 M10 0.55, 조건 삭제 M01 0.54.
- 원본 563 규칙 위양성(플래그율): B1 1.2%, B1-LOO 33.6%, B3 0%, B3w 54.7%, B5 8.9%.
- 제안 B6: eval(다른 문서 그룹) M13 탐지 **57.4%**, 원본 위양성 **5.4%**. 다른 유형(M01~M12) 추가 플래그 0%.
- gold 어휘 안의 동의어 id 27묶음을 합치면 원본 analyzer의 쌍 관계 **544쌍**이 바뀐다(충돌계열 +532).
- 원본 `_expand_condition` 접두어 치환 버그: 조건 확장 실패 규칙 7개, 수정하면 쌍 조건관계 328쌍·최종 라벨 6쌍이 바뀐다.

## 1. 원본 결정적 파이프라인의 계산 원리

[원문으로 확인한 사실] `pipeline/analyzer.py`, `pipeline/z3env.py`

### 1.1 입력
- 규칙: `condition` = `pred.*` id를 AND/OR/NOT/괄호로 묶은 문자열, `action` = {subjects(약 id 목록), permission, requirements}.
- 술어 정의: `predicates.json`의 `formal_definition`(예 `$ Value(meas.egfr) < 30 $`). **저장소에 없다**(`gen/`, `standard/` 폴더 없음). terms.json, meds.json, predicate_relations.json도 없다.

### 1.2 조건 관계 (`RuleAnalyzer.analyze_condition_pair`)
1. 빠른 경로: `gen/predicate_relations.json`이 있고 두 조건이 모두 AND로만 이루어졌을 때, 술어 집합 포함과 술어 함의 그래프로 EQUIVALENT / P⇒Q / Q⇒P를 판정. 파일이 없으면 생략.
2. Z3 경로: `_expand_condition`이 `pred.X`를 정의식으로 **문자열 치환**하고(`AND→&`, `OR→|`, `NOT→~`) `eval`로 Z3 식을 만든다. 순서대로 `A≠B` UNSAT → EQUIVALENT, `A∧¬B` UNSAT → P_IMPLIES_Q, `B∧¬A` UNSAT → Q_IMPLIES_P, `A∧B` UNSAT → MUTEX, 아니면 INTERSECT.
3. 정의가 없거나 파싱이 실패하면 UNKNOWN. 단 조건 문자열이 똑같으면 EQUIVALENT.
- Stage/Risk 연산자는 '서로 배타'로 보고 비교하지 않고, Duration/Assess는 지원하지 않는다(`z3env.py`).

### 1.3 행동 관계 (`ActionAnalyzer.analyze_pair`)
- subjects 집합과 permission이 같으면 EQUIVALENT. subjects가 **문자열로 겹치지 않으면** INDEPENDENT. 약 계층(약물군 ⊃ 개별 약)이나 동의어는 고려하지 않는다.
- 사용 계열 안에서 금지{contraindicate, avoid, stop} vs 허용{caution, allow, recommend, require, continue, consider}이면 CONFLICT. 같은 범주 안에서 강도만 다르면 DISAGREEMENT.
- 용량 계열 안에서 reduce_dose vs increase_dose는 CONFLICT, 나머지 용량끼리는 DISAGREEMENT. 금지 vs 용량은 CONFLICT, 허용 vs 용량은 INDEPENDENT.
- requirements는 관계 판정에 쓰이지 않는다.

### 1.4 종합 (`_determine_overall_relation`)
| 조건 \ 행동 | EQUIVALENT | CONFLICT | DISAGREEMENT | INDEPENDENT |
|---|---|---|---|---|
| EQUIVALENT | complete_redundancy | intrinsic_conflict | intrinsic_disagreement | others |
| P⇒Q / Q⇒P | contained_redundancy | implication_conflict | implication_disagreement | others |
| INTERSECT | others | local_conflict | others | others |
| MUTEX | others | others | others | others |
| UNKNOWN | others | **local_conflict** | others | others |

- 조건 관계를 모르면(UNKNOWN) 행동만 충돌해도 local_conflict가 된다.
- 쌍 후보: 기본값은 condition+subjects 문자열의 MinHash LSH(20밴드×5행, 추정 Jaccard ≥0.3) 후보만 판정하고, 같은 관계 유형 안에서 전이폐포로 쌍을 추가한다.

### 1.5 [실제 실행해 확인한 결과] gold 563 규칙에서 원본 analyzer 실행
술어 정의가 없어서 각 `pred.X`를 서로 독립인 Bool 원자(`$ Has(atom.X) $`)로 정의했다('원자 술어 추상화'). 원본 코드는 수정하지 않고 `src_copy/`에서 로드했다(`__init__.py`·LLM 경로는 실행하지 않음).
- 전 쌍 158,203쌍: 충돌계열 7,008쌍(local_conflict 6,779 = 96.7%, implication_conflict 70, intrinsic_conflict 1, implication_disagreement 123, intrinsic_disagreement 35). 중복은 complete 15, contained 73.
- 원본 기본값(LSH+폐포): 후보 5,907쌍. 충돌계열 2,675쌍(local 2,523). 내가 재구현한 LSH 후보 생성이 원본 함수 결과와 정확히 일치했다(5,907 = 5,907).
- 위 수치는 B 서브에이전트의 독립 실행(`B-reproduction`, atom 모드: 충돌계열 7,008, local 6,779, LSH local 2,523)과 같다.
- 논문 벤치마크(226쌍)와는 비교할 수 없다. 226쌍 정답 라벨이 공개되지 않았다.

### 1.6 [실제 실행해 확인한 결과] 원본 버그: 접두어 문자열 치환
`_expand_condition`은 `expr.replace(ref, ...)`로 치환한다. 같은 조건 안에서 앞에 나온 id가 뒤에 나온 id의 접두어이면(예 `pred.has_hf AND pred.has_hfref`) 뒤의 id까지 깨져서 `(Has(atom.has_hf))ref` 같은 식이 되고, eval이 실패해 UNKNOWN이 된다. 순서가 반대이면 정상이다(`logs/smoke_orig.log`).
- gold에서 해당 규칙 7개. 단어 경계로 치환하는 수정판과 비교하면 조건관계가 328쌍에서 바뀌었고(대부분 UNKNOWN→INTERSECT), 최종 라벨은 6쌍에서 바뀌었다(`results_prefix_bug_diff.csv`).
- 실제 predicates.json이 있어도 같은 버그가 생긴다 [연구 가설: 치환 로직이 정의 내용과 무관하므로].

## 2. 변이 시험 설계

[실제 실행해 확인한 결과] 연산자·표본·seed는 생성 전에 `mutation_spec/mutation_operators_v1.json`에 고정했다(2026-11-18T10:35:21+09:00, sha256 d66b25cf…, 읽기 전용 처리). 생성된 변이 `mutants_v1.jsonl`(sha256 0a492f4a…, 10:36:17)도 함께 기록했다(`mutation_spec/FROZEN_AT.txt`).
- seed 20261118. 연산자마다 최대 50개를 뽑았고, 적용 가능한 규칙이 50개보다 적으면 전부 썼다. 변이 573개는 모두 구문상 올바르고 원본과 달랐다.

| id | 연산자 | 오류 계열 | 적용 가능 규칙 | 표본 |
|---|---|---|---|---|
| M01 | 최상위 conjunct 삭제 | 조건 누락 | 368 | 50 |
| M02 | AND→OR | 논리 변환 | 368 | 50 |
| M03 | OR→AND | 논리 변환 | 124 | 50 |
| M04 | NOT 제거 | 논리 변환 | 12 | 12 |
| M05 | NOT 추가 | 논리 변환 | 562 | 50 |
| M06 | 비교 반전(lt↔ge, gt↔le, id 안에서) | 비교 연산 | 156 | 50 |
| M07 | 임계값 변경 | 비교 연산 | 222 | 50 |
| M08 | 술어 동의어 id(has_ 붙이기/떼기) | 용어 연결 | 563 | 50 |
| M09 | 약 동의어 id(sglt2↔sglt2i 등, _tablet) | 용어 연결 | 556 | 50 |
| M10 | 예외(AND NOT …) 삭제 | 조건 누락 | 11 | 11 |
| M11 | 무관한 conjunct 추가 | 조건 추가 | 563 | 50 |
| M12 | 다른 약으로 교체 | 용어 연결 | 556 | 50 |
| M13 | permission 반전 | 행동 방향(대조군) | 563 | 50 |

gold 조건에는 숫자 비교가 직접 들어 있지 않다(전부 `pred.*` 원자). 그래서 비교 연산 오류(M06/M07)는 id 이름 안의 `_lt_30` 같은 토큰을 바꾸는 방식으로만 흉내 낼 수 있었다.

기준선 정의 (`code/eval_static.py`, `code/eval_downstream.py`)
- **B1 정적 검사**: 어휘 밖의 pred/med id, permission enum, subjects 비어 있음·형식 오류, 구문 오류, 조건 자체의 UNSAT/항진. 표준 사전이 공개되지 않아 **gold 563 규칙의 id 집합을 사전 대신** 썼다. B1-LOO는 해당 규칙을 뺀 562 규칙의 어휘를 쓴다.
- **B2 동치 검사**: 원 규칙과 변이 규칙을 Z3로 비교한다. **정답(원 규칙)을 알아야만 쓸 수 있다**. 실제 배포 환경에서는 원 규칙이 없으므로 탐지기가 아니라 상한선이다.
- **B3 용어 정규화**: 어휘 밖 id를 정규화 키(소문자, has_/is_ 제거, 약물군 접미 i/ra 제거, 약어표)나 원본 `lsh_cluster.compute_shingles(k=3)+compute_minhash` Jaccard ≥0.7로 기존 id에 매칭한다. B3-Jaccard는 수작업 규칙 없이 Jaccard만 쓴다. B3w는 어휘 안 id가 동의어 묶음(크기>1)에 속하는지만 보는 약한 경고다.
- **B4 하류 영향**: 원본 analyzer(원자 추상화)로 변이 규칙과 나머지 562 규칙의 쌍 관계를 다시 판정한다(all-pairs). 원본 기본값(LSH+폐포) 모드도 함께 돌렸다. 탐지기가 아니라 '오류가 결과를 바꾸는가'의 척도다.
- **B5 원문 대응(LLM 없음)**: pred id의 숫자가 quote에 있는지, 비교 방향 단서(< ≤ 低于 以下 / > ≥ 以上 超过), subject 약 이름(수작업 사전 `code/med_lexicon.py`, 77개 id), NOT이 있을 때 부정 단서가 있는지.
- 탐지 정의: 변이 규칙에 **원 규칙에는 없던 새 플래그**가 생긴 비율. 원본 플래그율(위양성)은 따로 보고한다.

## 3. 결과: 유형별 탐지율과 하류 영향

`results_by_operator.csv`, 행 단위 결과 `results_mutation_detection.csv` [실제 실행해 확인한 결과]

| 연산자 | n | B1 | B3 | B3-J | B5 | **정답 없는 합집합** | B2(정답 필요) | B4 충돌 변화 | B4 LSH 변화 | **조용한 오류+하류 변화** |
|---|---|---|---|---|---|---|---|---|---|---|
| M01 conjunct 삭제 | 50 | 0 | 0 | 0 | 0 | **0** | 1.0 | 0.54 | 0.66 | **0.54** |
| M02 AND→OR | 50 | 0 | 0 | 0 | 0 | **0** | 1.0 | 0.84 | 0.78 | **0.84** |
| M03 OR→AND | 50 | 0 | 0 | 0 | 0 | **0** | 1.0 | 0.12 | 0.16 | 0.12 |
| M04 NOT 제거 | 12 | 0 | 0 | 0 | 0 | **0** | 1.0 | 0.58 | 0.42 | **0.58** |
| M05 NOT 추가 | 50 | 0 | 0 | 0 | 0.46 | 0.46 | 1.0 | 0.44 | 0.58 | 0.26 |
| M06 비교 반전 | 50 | 0.46 | 0.14 | 0.14 | 0.76 | 0.96 | 1.0 | 0.44 | 0.50 | 0 |
| ㄴ 결과 id 어휘 안 | 27 | 0 | 0 | 0 | 0.93 | 0.93 | 1.0 | 0.63 | 0.63 | 0 |
| M07 임계값 변경 | 50 | 0.56 | 0.34 | 0.34 | 0.94 | 0.98 | 1.0 | 0.14 | 0.30 | 0.02 |
| M08 술어 동의어 | 50 | 0.92 | 0.92 | 0.54 | 0 | 0.92 | 1.0 | 0.30 | 0.32 | 0.02 |
| ㄴ 결과 id 어휘 안 | 4 | 0 | 0 | 0 | 0 | 0 | 1.0 | 0.25 | 0.25 | 0.25 |
| M09 약 동의어 | 50 | 0.74 | 0.14 | 0.14 | 0 | 0.74 | 1.0 | 0.76 | 0.56 | 0.20 |
| ㄴ 결과 id 어휘 안 | 13 | 0 | 0 | 0 | 0 | **0** | 1.0 | 0.77 | 0.54 | **0.77** |
| M10 예외 삭제 | 11 | 0 | 0 | 0 | 0 | **0** | 1.0 | 0.55 | 0.27 | **0.55** |
| M11 conjunct 추가 | 50 | 0 | 0 | 0 | 0.14 | 0.14 | 1.0 | 0.24 | 0.58 | 0.22 |
| M12 다른 약 | 50 | 0 | 0 | 0 | 0.94 | 0.94 | 1.0 | 0.88 | 0.62 | 0.04 |
| M13 permission 반전 | 50 | 0 | 0 | 0 | 0 | **0** | 1.0 | 0.90 | 0.68 | **0.90** |
| **전체** | 573 | 0.234 | 0.134 | 0.101 | 0.283 | **0.449** | 1.0 | 0.511 | 0.515 | **0.298** |
| 원본 563 플래그율(위양성) | 563 | 0.012 | 0 | 0 | 0.089 | – | 0 | – | – | – |

- B1-LOO 탐지율은 B1과 같았지만 원본 위양성이 33.6%였다. 한 번만 쓰이는 id가 많아서 실용성이 없다. B3w는 원본 위양성이 54.7%였다.
- B4 변화 방향(all-pairs 쌍 수 합계, `logs/downstream_*.csv`):
  - M02는 충돌계열 쌍 +254, 유형 변경 178(local→implication 등).
  - M05는 −85. 부정이 추가되면 MUTEX가 되어 **충돌을 놓친다**.
  - M10은 +37. 예외를 지우면 MUTEX였던 쌍이 함의/교차가 되어 **가짜 충돌이 생긴다**(예: vericiguat continue vs stop).
  - M13은 +1,938/−1,061.
- 놓친 사례: M12 중 2건은 '다른 약'으로 바꾼다는 의도와 달리 동의어로 바뀌었다(glp1→glp1ra, sglt2→sglt2i). gold 어휘 자체에 동의어가 섞여 있기 때문이다. spec은 바꾸지 않고 그대로 보고한다.

### 탐지 불가 유형 (정답 없는 기준선 합집합 0%)
M01, M02, M03, M04, M10, M13, 그리고 어휘 안 동의어로 바뀐 M08/M09.

## 4. 탐지되지 않으면서 하류를 바꾸는 유형의 원인 분석

| 유형 | 조용한 오류+하류 변화 | 원인 | 분류 |
|---|---|---|---|
| M13 permission 반전 | 0.90 | 반전된 permission도 enum 안의 값이다. B1/B3/B5는 permission을 보지 않는다 | 규칙만 보면 **원리적으로 불가**. quote를 보면 **계산 방법 부족**(방향 단서가 문장에 명시된 경우가 많음 → B6에서 57% 회수) |
| M02/M03 AND↔OR, M04 NOT 제거, M01/M10 조건·예외 삭제 | 0.12~0.84 | 결과가 구문상 올바르고, 어휘 안의 id만 쓰며, 충족 가능하다. 어떤 논리식도 그럴듯한 지침이 될 수 있다 | 규칙만 보면 **정답(원문 의미) 없이 원리적으로 불가**. quote를 보면 문장 구절↔술어 대응이 필요한데, 그건 변환 과제 자체이고 술어 정의·용어 사전(predicates.json, terms.json)도 공개되지 않았다 → **데이터 부재 + 계산 방법 부족**. 결정적 문자열 규칙으로는 부분적으로만 가능(B5가 부정 추가를 46% 잡은 정도) |
| M08/M09 어휘 안 동의어 | 0.25 / 0.77 | 바뀐 id가 이미 gold 어휘에 있다(sglt2/sglt2i 등). 원본 ActionAnalyzer는 subjects를 문자열로만 비교한다 | **데이터(어휘 정규화) 문제**. gold 자체에 동의어 27묶음이 있다(`logs/b3_vocab_clusters.log`). 묶음을 합치면 544쌍 관계가 바뀐다(아래). B3w 경고는 원본 위양성이 54.7%라서 그대로 쓰기 어렵다 |
| M05 NOT 추가, M11 conjunct 추가 | 0.26 / 0.22 | B5 부정 단서와 숫자 검사가 일부만 잡는다 | 계산 방법 부족(부분) |

원자 추상화의 한계 [아직 검증하지 못한 사항]: 실제 술어 정의가 있으면 `egfr_lt_30 ⇒ egfr_lt_45`, `egfr_lt_30`와 `egfr_ge_45`의 MUTEX 같은 관계가 생긴다. 그러면 local_conflict 대부분이 others나 implication으로 바뀌고 B4 영향률도 달라질 수 있다. M06/M07의 '조용한 오류' 0~2%도 원자 추상화에서는 비교 반전이 단순히 다른 원자로 보이기 때문일 수 있다.

### gold 동의어 id 병합의 하류 영향 [실제 실행해 확인한 결과]
`code/gold_synonym_impact.py`, `results_gold_synonym_merge_*.{csv,json}`
- B3 정규화 키 묶음 27개(약 6개, 술어 21개; 모두 수동으로 확인해 동의어로 판단, 약 `med.class.insulin`/`med.insulin`은 약물군/약제라 경계 사례)를 빈도가 높은 id로 합쳤다. 바뀐 규칙은 48개다.
- 전 쌍 관계가 544쌍에서 바뀌었다: others→local_conflict 511, →implication_disagreement 15, →contained_redundancy 12, →intrinsic_disagreement 6. 충돌계열은 7,008에서 7,540이 됐다.
- 해석: gold 규칙을 그대로 원본 analyzer에 넣어도 동의어 id 때문에 **최소 532개의 충돌계열 쌍이 판정에서 빠진다**(원자 추상화 기준). 이 쌍들이 '진짜 충돌'인지는 정답 라벨이 없어 확인할 수 없다 [아직 검증하지 못한 사항]. 약물군⊃개별 약 계층(예 sglt2 ⊃ dapagliflozin)을 다루지 않아서 생기는 누락은 측정하지 않았다 [아직 검증하지 못한 사항].

### gold 데이터에서 발견한 부수 이상 [실제 실행해 확인한 결과]
- subjects가 비어 있는 규칙 6개, subject 값이 `'nan'`인 규칙 1개(B1 원본 플래그 7건 = 1.2%).
- 같은 문서가 두 이름으로 표기된다(`…专家共识（2023版）` 35건 vs `…专家共识（2023）` 29건). 문서 단위로 분할할 때 누수 위험이 있어 B6 분할에서는 정규화해 묶었다.
- rule id와 permission이 어긋나는 사례: `rule.*_consider_sglt2` 4건이 permission=caution이다(B6 eval 위양성 검토 중 발견).

## 5. 제안 방법 B6: 권고 방향 단서 대응 검사

근거: v1에서 M13은 정답 없는 기준선 탐지 0%, 하류 충돌 변화 90%로 가장 큰 '조용한 오류'였다. 사전 정의는 `mutation_spec/b6_proposal_spec_v2.json`에 있다(v1 결과를 본 뒤 작성, 10:43:09 고정, v1은 수정하지 않음).

| 항목 | 내용 |
|---|---|
| 해결하려는 오류 | permission(권고 방향) 오류 |
| 기존과 다른 점 | 기존 B1/B3/B5는 permission을 원문과 대조하지 않는다 |
| 입력→출력 | (permission, quote) → 플래그 0/1 |
| 계산 | quote에서 금지·주의·허용·감량·증량 단서(중국어 어휘)를 찾는다. 허용 단서는 '不建议/不推荐' 등을 지운 뒤 찾는다. permission 극성의 단서가 **없고** 반대 극성 단서가 **있으면** 플래그 (변형 B) |
| 독립 정답 | 변이 사실(원 permission은 gold) |
| 분할 | 출처 문서 그룹(이름 정규화) 단위 dev 361 / eval 202. 어휘는 dev quote만 보고 1회 작성했다(`logs/b6_dev_quotes_peek.log`). 변형 A/B는 dev에서 사전 규칙(위양성 ≤0.15 중 탐지율 최대)으로 골랐고 B가 선택됐다. eval은 1회만 실행했다 |
| 강한 기준선 | 같은 eval 집합에서 B1/B3/B5(탐지 0, permission을 쓰지 않으므로 구조상 0). 상한선은 B2(정답 필요, 100%) |
| 실패 조건 | 한 quote 안에 서로 다른 방향의 권고가 섞인 경우(예: "A级可使用；B级及C级不建议使用"). 어휘 누락(停药, 禁止, 不使用) |
| 비용 | 문자열 검색뿐. LLM 0, 563 규칙 기준 1초 미만 |

결과 [실제 실행해 확인한 결과] (`results_b6_summary.json`, `results_b6_eval_m13all.csv`)

| 분할 | 원본 위양성 | M13_ALL 탐지 |
|---|---|---|
| dev (n=361) | 0.003 | 0.687 |
| **eval (n=202)** | **0.054** | **0.574** |

- 사전 성공 기준(탐지 ≥0.50, 위양성 ≤0.20)은 eval에서 충족했다.
- 원래 permission별 eval 탐지:

  | 원래 permission | 탐지 |
  |---|---|
  | recommend | 55/77 |
  | consider | 15/15 |
  | reduce_dose | 9/9 |
  | allow | 11/16 |
  | continue | 7/13 |
  | **avoid** | **5/26** |
  | **contraindicate** | **5/17** |
  | **stop** | **0/12** |
  | caution | 2/9 |

  즉 '금지→허용' 방향의 반전은 거의 못 잡는다. 금지 문장에 허용 단서('应', '可', '建议')도 같이 들어 있는 경우가 많기 때문이다.
- 다른 오류 증가 여부: v1 변이 M01~M12에서 B6 추가 플래그는 0%였다. eval 원본 위양성 11건 중 6건은 어휘 누락(停药/禁止/不使用)이고, 1건은 "先纠正…再考虑" 문장(caution 규칙인데 주의 단서가 없음)이며, 4건은 gold의 id/permission 불일치 의심 사례(위 4절)다. 결과를 본 뒤 어휘를 고치지 않았다.
- 한계:
  - B6는 permission 오류만 다룬다. 논리 구조 오류(M01~M04, M10)는 해결하지 못한다.
  - 합성 반전이라 실제 LLM이 permission을 틀리는 분포와 다를 수 있다 [아직 검증하지 못한 사항].
  - 실제 논문 오류 해결 성능이 아니다.

## 6. 다음 단계 (가장 중요한 하나)
predicates.json(394개 술어의 formal_definition)과 226쌍 정답 라벨을 확보해 원자 추상화를 실제 술어 의미로 바꾸고 B4를 다시 측정한다. 그러면 '조용한 오류'의 실제 하류 영향이 확정된다.

## 7. 파일
- 코드:
  - `code/orig_loader.py`: 원본 로드, 원자 추상화
  - `code/common.py`
  - `code/gen_mutants.py`
  - `code/eval_static.py`: B1/B2/B3/B5
  - `code/eval_downstream.py`: B4
  - `code/summarize.py`
  - `code/gold_synonym_impact.py`
  - `code/b6_permission_cue.py`
  - `code/med_lexicon.py`
  - `code/smoke_orig.py`
- 변이 정의(실행 전 고정): `mutation_spec/mutation_operators_v1.json`, `mutation_spec/mutants_v1.jsonl`, `mutation_spec/b6_proposal_spec_v2.json`, `mutation_spec/FROZEN_AT.txt`
- 결과:
  - `results_by_operator.csv`, `results_mutation_detection.csv`, `results_static_flags.csv`
  - `results_gold_relations_allpairs.csv`, `results_gold_summary.json`, `results_prefix_bug_diff.csv`
  - `results_gold_synonym_merge_diff.csv`, `results_gold_synonym_merge_summary.json`
  - `results_b6_eval_m13all.csv`, `results_b6_summary.json`
- `logs/`, `env.txt`(venv: z3-solver 5.4.1.0, pydantic 2.14.3), `RUN_COMMANDS.md`, `src_copy/`(원본 사본, sha256 일치 `logs/src_copy_sha256.txt`)
- 원본 저장소는 수정하지 않았다(analyzer.py, rules_gold.json sha256이 실행 후에도 같음). git·유료 API·LLM 호출 없음. 실행 1회는 최대 48초.
