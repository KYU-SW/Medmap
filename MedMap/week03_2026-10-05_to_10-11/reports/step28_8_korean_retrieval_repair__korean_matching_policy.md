# STEP28.8 Korean Matching Policy (연구용)

규칙 정본은 `scripts/repair_korean_matching.py`·`scripts/policies.py` 문서열. 수치는 `docs/step28_8_report.md`.

## 검색 순서(구문마다)

| 단계 | 내용 | 허용 | 금지 |
|---|---|---|---|
| A·B 완전 일치 | 질의 키 == 색인 키(원문·조사 제거·술어 정규화) | 검증 용어(STEP23 학습·STEP21 사전·용어집) | 1글자 키(명사구 전체가 1글자일 때 제외) · 1글자 nkey(616행) · 양태가 다른 nkey 일치 |
| C 경계 일치 | 색인 용어 핵심 형태소열이 질의 형태소열 안에 연속 | 증상·질환·부위 용어 | 역방향(질의 ⊂ 긴 색인 문장) · 1글자/신체 부위 단독 형태소 · 검사명·약재명(완전 일치만) |
| D 합성 | 통증 합성어(띄어쓰기 무관) · 통증 술어 + 부위 | pain + E_55 | 'X성' 진단형 수식어가 앞에 있으면 보류 |
| 비증상 | 마지막 명사(핵어)가 질환·약물·치료·검사 접미 | NON_SYMPTOM(원문 보존) | — |
| E SILVER | STEP28.7 정제표 완전일치 | 수락 행 | 보류 행이 KO 를 덮지 않음(단 P4 보류 우선은 예외) |
| F | 근거 없음 | UNKNOWN / UNCERTAIN | 부분 문자열만으로 자동 수락 |

## 보류 우선(P4)

정제표 HOLD_CONCEPT_UNCERTAIN·HOLD_AUDIT_NOT_EXACT 행과 구문 키가 완전일치 → 긍정·미표기 구문은 UNCERTAIN(AMBIGUOUS_CONCEPT_RELATION, canonical null, 표시 0),
부정 구문은 KO 결과 유지 + 확인 필요(모델 사용 불가). 다른 구문에는 적용 안 함.

## 의미 충돌 차단(P5)

구문 키의 정제표 행이 가리키는 concept 와 STEP28.7 ontology 관계 검사에서 모든 id 쌍이 DISTINCT 인 기존 canonical(+ 구토↔오심)은 자동·표시 후보에서 제외.

## 노출 경고

'근'·'주위'·'경추성'·'오바이트'·'흉 통' 등 규칙 일부는 STEP28.7 에서 본 오류 사례를 보고 만들었다 → 해당 사례 결과는 회귀 확인용이며 일반화 성능이 아니다.
