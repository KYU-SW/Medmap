# STEP28 인계 — 77 개 밖 증상의 안전한 표준화 준비

STEP28 은 자동 실행하지 않았다. 아래 목록은 기계 분류(의학적 판단·정답 아님)이며 사람 검토 전 후보다.

## 입력 파일
- `data/external_silver_candidates.csv` — BERT-NER-KO 증상(ST) span 442, 모델·B4·STEP27 출력(SILVER_CANDIDATE, human_verified=False)
- `outputs/step28_candidates.csv` — 442 중 KNOWN 아닌 고유 표현 388: {"ONTOLOGY_SEARCH_CANDIDATE": 211, "SYNONYM_GAP_CANDIDATE": 14, "TYPE_UNCLEAR_REVIEW": 163}
- `outputs/unknown_analysis.csv` — BEST 상태 UNKNOWN_SYMPTOM 전체(외부 845행), 내부 후보·후보 유사도 포함
- `outputs/routing_features.csv` · `routing_decisions.csv` — 정책 A–E 전체 출력

## 분류 기준(사전 고정, analyze_routing_errors.py 문서열)
- SYNONYM_GAP_CANDIDATE: 증상 근거 있음 + 내부 1순위 후보 cand_sim ≥ 0.3 + KoE 확률 ≥ 0.5 → 기존 concept 표현 보완 후보. 예: 코피가, 대사성 어지럼증의, 말초성 어지럼증은, 중추성 어지럼증은, 마비가, 구역, 회전성 어지럼증이, 구역을, 발열때문에, 설사때문에, 설사증상, 실신증상과, 어지러운 증상이, 의식소실과
- ONTOLOGY_SEARCH_CANDIDATE: 증상 근거 있음 + 위 조건 미달 → 77 밖 concept 가능성, HPO/SNOMED/UMLS 검색 대상. 예: 두통, 감기, 구토, 두통은, 두통과, 두통의, 코막힘이, 가래에, 발열, 복통, 가래가, 염증, 감각이상, 복통이, 실신전단계
- TYPE_UNCLEAR_REVIEW: 증상 근거 없음(어휘 단서 없음·비증상 점수 ≥ 0.5) → 증상 여부부터 검토. 예: 염증이, 스트레스, 실신, 불안, 알레르기, 객혈은, 객혈을, 객혈의, 객혈이, 객혈이라고, 염증을, 염증이나, 고름이, 소화불량, 기억저하
- '새 concept 자체가 필요한 표현' 확정은 사람 검토 + ontology 검색 결과가 필요하다(이번 단계에서 판정하지 않음).
- **주의(생성 후 육안 확인)**: 이 기계 분류는 눈에 띄게 틀린 예가 있다 — 지원 concept 의 기본 용어(두통·구토·발열·복통)가 ONTOLOGY_SEARCH 로, 미지원 '코피가'가 SYNONYM_GAP 으로, 지원 '객혈'류가 TYPE_UNCLEAR 로 분류됐다. 짧은 명사형 지원 증상 용어가 B4 를 통과하지 못하는 것(학습 표현 유사도·KoE 확률 부족)이 원인 후보이며 확인 필요. STEP28 입력으로 쓰기 전에 분류 규칙 자체를 다시 설계해야 한다(이번 단계에서 고치지 않음).

## STEP28 설계 메모
- 기존 Linear/KoELECTRA 는 고정. 추가는 ontology 후보 검색(HPO/SNOMED/UMLS, 라이선스·로컬 보관 확인 — OFFLINE_ON_PREM_FIRST) + 후보 의미 검증 단계.
- 라우터 인터페이스(`docs/routing_schema.md`)의 UNKNOWN_SYMPTOM.raw_record 를 ontology 검색 입력으로 쓴다. 검색 결과가 있어도 사람 확인 전 canonical 로 자동 확정하지 않는다.
- STEP27 남은 문제: 질환명 NON 인식 손실, 코피류 후보 표시, COMPLEX 정규식 과잉 판정, Gold 부재.
- 금지 승계: 77 밖 증상을 77 에 끼워 맞추지 않음 · weak/SILVER 를 Gold 로 부르지 않음 · 사용자에게 대량 라벨링 요청 금지(방법은 선택지로만).
