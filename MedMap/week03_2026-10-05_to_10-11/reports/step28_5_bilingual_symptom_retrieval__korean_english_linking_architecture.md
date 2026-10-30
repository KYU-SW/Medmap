# STEP28.5 한·영 연결 구조 (연구용)

```
한국어 발화
 └ extract_symptom_spans.extract_kiwi()  — kiwipiepy 절 분리 → 구문{명사구·핵어·술어·술어종류·부정·시점·주체·위치}
 └ bilingual_retriever.Retriever.run(text, mode)
    KO_ONLY : korean_index(77 증상·77 밖 DDXPlus 증거·49질환·부위값·UMLS KOR SRL0) 정확/구문/ n-gram(후보만) + 통증·부위 규칙 + STEP27 B4
    EN_ONLY : bilingual_links(같은 레코드의 영어 이름 · STEP20 curated id · UMLS CUI) 키 완전일치 → STEP28 ontology 색인 → STEP28 validate
    PARALLEL: 두 결과를 concept 기준 통합(같으면 근거 2, 다르면 UNCERTAIN·표시 없음, 점수 합산 없음)
 └ 결과: 범주 · concept · 속성 · 표시 후보 · 근거(한국어/영어) · 원문·구문 위치·극성·시점·주체
```

| 연결 근거 | 내용 | 77 밖 증상으로 가는가 |
|---|---|---|
| ID_ANCHORED | 한국어 용어 → STEP20 curated HPO/SNOMED/CUI | 아니오(77 안) |
| EN_TERM_EXACT | 같은 레코드 영어 이름 → 색인 완전일치 | 77 증상·질환명만 |
| UMLS_CUI | UMLS KOR SRL0(검사·약재) | 비증상 |
| 다국어 모델 | siglip2 텍스트 인코더(gate) | gate 미달 시 사용 안 함 |
| (제외) | MDRKOR·KCD5(SRL 3) | 이용 조건 확인 전 미사용 |

원칙: 번역 문자열을 만들지 않는다 · 영어 ontology 에 개념이 있다는 것만으로 한국어 연결을 주장하지 않는다 · 서로 다른 ontology ID 는 CUI(교차 참조)로만 합친다 ·
부모·자식 관계는 같은 의미의 근거가 아니다(STEP28 검증기: 같은 id/CUI = 중복, 속성 칸 있는 기존 concept 하위 = 기존+속성, 그 외 하위 = 신규 후보).
