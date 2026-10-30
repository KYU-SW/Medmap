# STEP28 Ontology 검색 구조 (연구용 프로토타입)

```
한국어 입력
 └─ search_existing_concepts.ExistingSearch.search()
     0 COMPLEX(STEP26 정규식) → UNCERTAIN
     1 통증+부위 규칙(PAIN_COMPOUND·제품 매퍼 BP 매크로) → EXISTING_COMPOSITE(pain + E_55 값 후보) / '목' 모호 → UNCERTAIN
     2 MedMap 한국어 용어 stem 완전일치 → EXISTING_CANONICAL(EXACT_TERM)
     3 STEP27 POLICY_D KNOWN → EXISTING_CANONICAL(MODEL_AUTO)
     4 제품 매퍼 alias(77 crosswalk) / KoE ≥ 0.953 + 어휘 근거 → EXISTING_CANONICAL, 서로 다르면 UNCERTAIN(SOURCE_CONFLICT)
     5 비증상 근거(매퍼 병력 증거·49질환 한국어 라벨·STEP27 NON)
 └─ evaluate_expansion.Expansion.__call__()
     + UMLS KOR SRL0 완전일치(검사명·약재명)·STEP27 NON_TYPE_CUE → NON_SYMPTOM
     + 경로 C(gate 통과 시) xlm-roberta-base → HPO 후보 → validate_concept_candidates.validate()
     → NEW_ONTOLOGY_CONCEPT(검증) / UNKNOWN_SYMPTOM(KOREAN_LINK_MISSING · NEW_CANDIDATE_UNVERIFIED) / UNCERTAIN
 └─ 모든 결과: source_text 보존, 표시 후보 = 기존 concept 결과만
```

## 색인 (`build_ontology_index.py` → `index/ontology_index.sqlite`, LOCAL_ONLY)

| 테이블 | 내용 |
|---|---|
| concept | HPO 전체(obsolete·replaced_by·phenotype 여부) + SNOMED Clinical finding 하위 활성 concept(FSN·semantic tag·정의·is_a) |
| sct_status | SNOMED 전체 활성 여부 |
| term | 정규화 영어 문자열(HPO 이름·동의어, SNOMED description, UMLS ENG SRL0 SAB + SNOMEDCT_US) |
| xref / sty | 위 범위 CUI ↔ HPO·SNOMEDCT_US code, semantic type |
| kor_term | UMLS KOR SRL0(LNC-KO-KR·TKMT)만. MDRKOR·KCD5(SRL3)는 적재 안 함 |

UMLS MRREL 은 쓰지 않음(계층 = HPO·SNOMED 원본 is_a, CUI = 같은 개념 묶음).

## 검증 (`validate_concept_candidates.py`)

활성·obsolete → 증상 유형(질환류 의미유형 + T184 없음 → WRONG) → 기존 77 과의 관계(같은 id/CUI = 중복, 속성 칸 있는 기존 concept 하위 = 기존+속성,
속성 칸 없는 기존 concept 하위 = 상위 연결 기록 신규 후보, 상위 = BROADER) → 근거 경로(C = 자동 후보, 확정 불가) → 정의 유무.
문자열 유사도만으로 EXACT 를 주지 않는다. 계층이 가깝다는 이유로 같은 의미로 보지 않는다(관계는 DISTINCT/IS_A 로만 기록).
