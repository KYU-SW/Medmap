# 의료 개념 연결 (`hybrid2/lexicon.py`, `hybrid2/parser.py`)

## 방법
- LLM 없음. 정확 문자열 일치, 긴 구문 우선, 유사 매칭 없음.
- 사전: 직접 정의한 파일럿 개념 10종(PE·심낭염·심근염·결핵·CTPA·D-dimer·관류 스캔·충만 결손·DVT·초음파) + 로컬 `hp.obo` 이름과 EXACT 동의어(HP:0000118 하위만, 실행 시 읽기, 재배포 없음).
- 표준 코드: PE 등 진단은 그래프에 이미 있는 UMLS·MeSH·MONDO, 소견은 HP id. 확인 안 된 코드(LOINC·SNOMED)는 넣지 않음.

## 구분하는 상태
PRESENT, NEGATED, UNCERTAIN, HISTORICAL, OTHER_PERSON, PURPOSE_OR_DIFFERENTIAL, ORDERED_NOT_RESULTED, RESULT_PENDING, CONDITIONAL. 연결 상태: LINKED, AMBIGUOUS(PE 약어·embolism 단독·thrombus·clot·CT 단독). 사전에 없으면 레코드를 만들지 않음. HPO 에는 있지만 그래프에 없으면 `graph_node` 빈 값.

## 다섯 표현
| 문장 | 상태 | 출력(중간 임상 확률 가정) |
|---|---|---|
| No evidence of pulmonary embolism (CTPA 판독) | NEGATED | WEAKEN, PE-CTPA-NEGATIVE |
| Possible pulmonary embolism | UNCERTAIN | ABSTAIN |
| History of pulmonary embolism | HISTORICAL | INSUFFICIENT_EVIDENCE, ASSOCIATED_WITH |
| Rule out pulmonary embolism | PURPOSE | ABSTAIN, TEST_PURPOSE_NOT_RESULT |
| Pulmonary embolism confirmed (검사 출처 없음) | PRESENT | ABSTAIN, DIAGNOSIS_MENTION_WITHOUT_TEST_SOURCE |

## v3b 재사용
CTPA 맥락의 PE 언급은 동결 v3b 도 호출한다. 반대·불확실 의견이면 `EXTRACTOR_CONFLICT` 로 기권(EXP-04 에서 본 "ruling out"→양성 오류 대응). v3b 는 수정하지 않음.

## 표준 용어 상태
| 표준 | 사용 | 라이선스 확인 |
|---|---|---|
| HPO | 로컬 파일 실행 시 읽기 | 공식 페이지 조회 실패(404). **재확인 필요** |
| UMLS·MeSH·MONDO | 그래프에 이미 있는 코드만 표시 | UMLS 문자열 공개 금지 규칙 유지 |
| LOINC | 미사용 | 무료·라이선스 동의 필요(검색 확인) |
| SNOMED CT | 미사용 | 한국 조건 **확인 필요** |
| ICD | 미사용 | **확인 필요** |
온톨로지 관계는 용어 정렬에만 쓰고 판단 규칙으로 변환하지 않는다.

## 결과
수치는 `VALIDATION_REPORT.md`. 1차 오류 유형: CT 검사명 변형 누락, 복수형·하이픈 누락, 수식어가 HPO 로 연결, 다른 검사의 normal 을 끌어옴, 위험 점수 문맥 미인식, 문서 안 약어 정의 미사용.
