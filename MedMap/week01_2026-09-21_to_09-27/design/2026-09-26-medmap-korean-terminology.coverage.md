# Korean Terminology — Coverage Report (갱신 2026-09-27, 정본 v1.1.2 — human gate 반영, ledger Ruling 10)

## 현재 (2026-09-27, branch `feat/korean-terminology`, master `2607d80` 병합 후)
생성: `Terminology.coverage(model_k3 classes_, EvidenceCatalog.ids, 라벨형 value code)`.

| 대상 | total | 한국어(ok) | review_needed | 화면 영어 fallback |
|---|---|---|---|---|
| 질환 표시명 | 49 | 49 | 0 | 0 |
| evidence 짧은 표시명 | 223 | 223 | 0 | 0 |
| value 표시명(라벨형) | 199 | 199 | 0 | 0 |
| 질문 전문 | 223 (선택 가능 221) | 221 | 0 | 0 — 남은 2 = 제외 질문 E_134·E_152(질문으로 나가지 않음) |
| 숫자 척도 evidence(0–10) | 6 | 번역 대상 아님(숫자) | — | — |

- 질문 168 추가: source `question_en_translated_2026-09-27`(수기 번역, `scripts/archive/apply_question_ko_2026-09-27.py`, 재실행 금지). 독립 번역 리뷰(opus) MUST_FIX 0 · SHOULD_FIX 10 → 이번 번역분 5건 반영(E_29·E_139·E_146 질문+짧은명, E_34 짧은명, E_204 질문), 기존 승인 문구 해당 5건 + 선택 2건은 human gate(ledger Ruling 8).
- 질환 7·짧은 표시명 2(이전 review_needed)는 원문 직역으로 확정(ledger Ruling 7). 확정값: 만성 폐쇄성 폐질환(COPD) 급성 악화 또는 감염 · 알레르기성 부비동염 · 특발성 식도 파열(보어하브 증후군) · 기관지 연축 또는 천식 급성 악화 · 췌장 종양 · 급성 심근경색 의심(ST분절 상승 또는 비상승) · 폐 종양 · E_139 심장 기형(선천성 등) · E_147 최근 병원 주사 치료(구역·흥분·중독 등).
- 실제 화면 감사(`medmap-web/e2e/english-audit.e2e.mjs`, 고정 seed 24 경로 × 390/1280px, 다지선다 전체 펼침): **USER_VISIBLE_ENGLISH = 0**, 단계 A 후보·B initial 선택/검색·C bootstrap·D IG·E 후보·F 요약·H 검색 빈 결과. 대조군(master 2607d80, 3 경로)은 영어 15건 검출 → 감사가 영어를 잡는 것을 확인.

---

## 이력: v1.0.0 (2026-09-26)


생성: `Terminology.coverage(model_k3 classes_, EvidenceCatalog.ids, 라벨형 value code)` 실행 결과(branch `feat/korean-terminology`, master `43d5a85` 병합 후). 정본 `medmap/data/terminology_ko.json` v1.0.0.

| 대상 | total | 한국어(ok) | review_needed | 미등록 | 화면 fallback |
|---|---|---|---|---|---|
| 질환 표시명 | 49 | 42 | 7 | 0 | 영문 class명 7 |
| evidence 짧은 표시명 | 223 | 221 | 2 | 0 | 표시명 없음 2(E_139, E_147) |
| value 표시명(라벨형) | 199 | 199 | 0 | 0 | 0 (E_204 11개 신규 포함) |
| 질문 전문 | 223 (선택 가능 221) | 53 | 0 | — | 영문 170 (선택 가능 168) → backlog `QUESTION_KO_COMPLETION` |
| 숫자 척도 evidence(0–10) | 6 | 번역 대상 아님(숫자 표시) | — | — | — |

출처 분포 — 짧은 표시명: initial 사용자 검수분 96 · 한국어 질문에서 축약 26 · 영문 질문에서 축약 101. value: 기존 188 · 영문에서 11. 질환: standard_term 49(UMLS KOR 대조 true 30 / false 18 / 후보 없음 1, 문자열 비저장).

## Provenance — `source: "standard_term"` (질환 49)

작성자 수기 번역(표준적으로 쓰이는 한국어 의학용어 기준). 특정 용어집 판본(대한의사협회 의학용어집, KCD 등)을 인용하지 않음. UMLS KCD5/MDRKOR와 boolean 사후 대조(true 30 / false 18 / null 1)만 수행, 불일치 사유 미기록.
- 정본 최초 생성 스크립트(이력 보존, 재실행 금지): `scripts/archive/seed_terminology_2026-09-26.py` — 번역 문자열은 전부 수기 리터럴, MRCONSO/UMLS 문자열 미사용. 후속: backlog `TERMINOLOGY_CITATION_REVIEW`(ledger).

## review_needed (사용자 확정 필요 — 확정 전 화면은 원문 fallback)

| 구분 | ID(영문) | draft | 사유 |
|---|---|---|---|
| 질환 | Acute COPD exacerbation / infection | 만성 폐쇄성 폐질환 급성 악화/감염 | 복합 class |
| 질환 | Allergic sinusitis | 알레르기성 부비동염 | DDXPlus 명칭과 한국 임상 용어(알레르기 비염/부비동염) 범위 차이 |
| 질환 | Boerhaave | 부르하버 증후군(특발성 식도 파열) | 고유명 표기 변이 |
| 질환 | Bronchospasm / acute asthma exacerbation | 기관지 연축/천식 급성 악화 | 복합 class |
| 질환 | Pancreatic neoplasm | 췌장 신생물(종양) | 양성/악성 범위 불명 |
| 질환 | Possible NSTEMI / STEMI | 급성 심근경색 가능성(NSTEMI/STEMI) | 불확실 표현 + 복합 class |
| 질환 | Pulmonary neoplasm | 폐 신생물(종양) | 양성/악성 범위 불명 |
| 짧은 표시명 | E_139 (Do you have a known heart defect?) | 심장 결손 | 선천/후천 범위 불명 |
| 짧은 표시명 | E_147 (Have you been treated in hospital recently for nausea, agitation, intoxication or aggressive behavior and received medication via an intravenous or intramuscular route?) | 최근 병원에서 구역·흥분 등으로 주사 투약 | 복합 조건 축약 |

## 노출 지점 상태 (§2.4)

| # | 상태 | 비고 |
|---|---|---|
| L1 질환 영문명 | 부분 해소 | 42/49 한국어, 7 review_needed 원문 |
| L2 질문 전문 영문 | 완화 | 영문 질문 위에 한국어 짧은 표시명 제목(선택 가능 168 중 review_needed E_139·E_147 제외 166). 전문은 backlog |
| L3 요약 이력 | 부분 해소 | fallback 질문은 짧은 표시명(E_139·E_147만 원문) |
| L4 value 영문 | 해소 | 199/199 |
| L5 raw code | 해소 | describeAnswer → valueLabel → code |
| L6–L8 | 변경 없음 | UI 노출 없음(API 계약 유지) |
