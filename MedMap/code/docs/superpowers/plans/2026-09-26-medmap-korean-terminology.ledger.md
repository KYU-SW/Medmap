# 실행 원장 — MedMap Korean Terminology (feat/korean-terminology)

계획: `docs/superpowers/plans/2026-09-26-medmap-korean-terminology.md` · worktree: `~/medmap-worktrees/korean-terminology` · 기반: master `336463f`(backend 142 OK skip 1 · vitest 108/108 · build OK, 이 세션에서 재실행 안 함)

## 상태
**COMPLETE (2026-09-27, A 라인 세션 인수)** — 질환 49·짧은명 223·value 199·선택 가능 질문 221 전부 한국어, 화면 영어 0. master 미머지(병합은 사용자 승인).
이전: IMPLEMENTED (rev2, 사용자 승인 C1–C3).
이력: rev1 DESIGN(결정 A·B·C 대기) → 2026-09-26 사용자 승인 C1·C2·C3.

## 감사 실행 기록 (read-only)
| 항목 | 명령/입력 | 결과 |
|---|---|---|
| 모델 class | `nice -n 19` python: `model_k{3,5,10}.pkl` `classes_` | 49, 세 모델 동일 |
| evidence | `release_evidences.json` 집계 | 223(B208/C10/M5), 라벨형 value code 199, 숫자 척도 evidence 6 |
| 기존 한국어 | `question_labels_ko.json` · `initial_evidence_ko.json` | 질문 전문 53 · value 188 · 짧은 표시명 96 |
| UMLS KOR 대조 | `grep -F "\|KOR\|"` MRCONSO → scratchpad(repo 밖, 비추적) | KCD5 11,001 · MDRKOR 119,994행, 49질환 중 48 후보. SRL=3 → 대조 전용 |
| 자원 | 가용 RAM ~11GB, GPU 미사용, 서버·전체 스위트 미실행 | — |

## Rulings

### Ruling 1 — 단일 정본 + 생성 미러 (C3)
기존 파일(`question_labels_ko.json`, `initial_evidence_ko.json`, `initialCatalog.json`)은 경로·형식을 유지한 채 용어 필드를 정본 `terminology_ko.json`에서 export로 재생성한다. 두 기존 파일이 `json.dumps(indent=1, ensure_ascii=False)`로 byte 재현됨을 확인 → export 후 diff는 question_labels_ko.json의 value +11(E_204)과 `source` 헤더 문구뿐, initial 두 파일은 byte 동일. QuestionPresenter·매퍼 테스트·clinical_summary 기본 provider 무수정.

### Ruling 2 — review_needed 기준 재정의 (plan R2.4)
rev1의 "step9 AMBIGUOUS/PARTIAL이면 review"는 UMLS 개념 선택 모호성이라 한국어 의미 모호성과 다르다(백일해·심방세동 등). 영문 class 자체의 의학적 범위가 한 용어로 정해지지 않는 7개만 review_needed.

### Ruling 3 — 짧은 표시명 review_needed 2개
E_139(heart defect 범위), E_147(복합 조건 축약). 화면에서는 짧은 표시명 없이 원문.

### Ruling 4 — clinical_summary 연결
master의 `LabelProvider` 훅에 `TerminologyLabelProvider`(질환명만 정본 사용)를 추가만 했다. 기본 `PresenterLabelProvider`·API 무변경(clinical summary는 API에 노출되지 않음).

### Ruling 5 — provenance 정정 (RG 재현성 감사 PARTIALLY_REPRODUCIBLE 후속)
- `source: "standard_term"`의 정확한 의미: 작성자 수기 번역(표준적으로 쓰이는 한국어 의학용어 기준). 특정 용어집 판본(대한의사협회 의학용어집, KCD 등)을 인용하지 않음. UMLS KCD5/MDRKOR와 boolean 사후 대조(true 30 / false 18 / null 1)만 수행, 불일치 사유 미기록.
- 정본 최초 생성 스크립트를 `scripts/archive/seed_terminology_2026-09-26.py`로 보존(재실행 금지 헤더 11줄 + 원본 byte 동일 본문). 원본 scratchpad 파일 sha256 `9f5c52f4d79fc9969e005f5430b3bfd8dc01e8f3be640c7b6263ff5130a3718d`, archive 파일 sha256 `590fb9a81404833355d97c0994c4351139122f9c2518408f15ba532c6673f69c`. 절대경로 `R = Path('~/medmap-worktrees/korean-terminology')` 포함(헤더에 명시, 로직 무수정).
- 재현 확인: 336463f 입력 사본(question_labels_ko.json·initial_evidence_ko.json) + release_evidences.json + model_k3.pkl 로 임시 경로에서 실행 → 출력 == 현재 정본(umls_kor_crosscheck 를 null 로 되돌린 뒤) **True**. boolean 은 이후 `scripts/crosscheck_umls_kor.py --write` 가 기록.
- 정본 파일 note 는 수정하지 않았다(수정 시 웹 생성물 source_sha256 이 바뀜) → 문서에만 기록.


### Ruling 6 — 질문 전문 완성(QUESTION_KO_COMPLETION 해소, 2026-09-27)
- 사용자 지시(C 인수 프롬프트 §6): 사용자가 받을 수 있는 질문 전문 전체 한국어화. 선택 가능 221 중 기존 53 + 신규 168. 원문 의미·극성·OR/AND·시간·비교 조건·과거력/현재 구분 보존, 조건 삭제 없음.
- 매퍼 테스트 결합(backlog 주의 사항) 해소: `tests/test_intake_mapper.py`의 지원 범위 단언을 표시 파일(question_labels_ko.json) 대신 freeze 당시 41 ID 고정 스냅샷과 비교하도록 변경. 매퍼 지원 범위는 alias 파일에서만 정해지며(`IntakeMapper.supported`), `medmap/intake/` 무변경(freeze 2372e2f 이후 diff 0).
- bootstrap 6문항 문구는 `startPlan.js` 하드코딩 대신 정본(`questionText`)에서 — 문구 byte 동일 확인 후 교체.
- 요약 API 질환 표시명: `EngineRegistry.summary_labels = TerminologyLabelProvider` (응답 키·형태 동일, `name` 은 내부 ID). 프론트 요약 후보는 내부 `name` 으로 `diseaseLabel` 조회.

### Ruling 7 — 이전 review_needed 9개 직역 확정
영문 class/질문을 축약·확장 없이 그대로 옮기면 의미 선택이 필요 없다고 판단(복합 class 는 "A 또는 B", neoplasm 은 양성·악성을 모두 포함하는 "종양", Possible → "의심"). 확정 사유는 각 항목 `note`. 사용자가 다른 표현을 원하면 정본만 수정 → export.

### Ruling 8 — 독립 번역 리뷰 반영 범위 / human gate
- 반영(이번 세션 번역분): E_29(직계→가까운 가족), E_139(심장 결함→심장 기형), E_146(신규→NOAC 계열, 짧은명은 약어 없이), E_34 짧은명(치료 중인→현재 앓고 있는), E_204(지역 선택형 안내).
- 미반영 → human gate(사용자 검수·승인된 기존 문구라 임의 변경 금지): E_150 짧은명(사용자 human gate 확정), E_112·E_77·E_9 짧은명(initial 96 사용자 검수, OR 조건 일부 생략), E_194 질문(v1 승인, "그렁거림"이 stridor 와 다를 수 있음), (선택) E_51·E_65 짧은명.

### Ruling 9 — 전체 브랜치 리뷰(opus, 2026-09-27) APPROVED · CRITICAL 0 · IMPORTANT 0 · MINOR 5
- 반영: (1) bootstrap 6문구 한국어·물음표 단언 (4) 영어 감사에 aria-label·placeholder·title·alt·입력값 포함(검색 빈 결과 입력은 한글 `퀘퀘퀘`) (5) archive 번역 스크립트 '참조 금지' 헤더.
- 기록만: (2) export 의 review_needed 필터는 합성 fixture 테스트 없음 — `_ok()` 가 ok 만 통과, review 항목은 표시 필드가 없어 validate 가 막음(fail-closed) (3) 정본이 깨지면 API lifespan 이 기동 실패 — 기존 question_labels_ko.json 과 같은 fail-closed, sync 테스트가 사전 차단.

### Ruling 10 — 사용자 human gate 결정(2026-09-27, 정본 v1.1.2)
- 유지: E_150 짧은명 "대변·방귀 배출 가능 여부"(polarity 를 뒤집지 않기 위한 중립형 확정 문구). 질환 7개 직역 유지(review_needed 재개 없음, 출처 대조는 TERMINOLOGY_CITATION_REVIEW).
- 수정 승인: E_112 "들숨 때 쌕쌕거림 또는 기침 뒤 거친 숨소리" · E_77 "색이 있거나 양이 많아진 가래" · E_9 "림프절(멍울) 부음·통증" · E_51 "설사 또는 배변 횟수 증가"(원문 OR 보존) · E_65 "삼키기 어려움·삼킬 때 걸리는 느낌" · E_194 질문 "숨을 들이쉴 때 쇳소리처럼 높은 소리가 나나요?"("그렁거림" 제거).
- initial 96 라벨(E_9·E_51·E_65·E_77·E_112)과 E_194 detail 은 export 로 initial 카탈로그에 함께 반영. 회귀 고정: tests/test_terminology.py HumanGateDecisionTests.

## Backlog

### ~~QUESTION_KO_COMPLETION~~ — 2026-09-27 완료(Ruling 6)
- 목표: 사용자에게 보일 수 있는 모든 질문 전문 한국어화. 현재 53/223, 영문 fallback 170(선택 가능 168).
- 편집 위치: `medmap/data/terminology_ko.json` `evidence_questions`만 → `scripts/export_web_terminology.py` 실행.
- 규칙: OR/AND/조건부/과거력(antecedent) 질문은 원문 의미 전체 보존(축약 금지). 애매하면 `review_needed`(draft_ko만).
- 주의: `tests/test_intake_mapper.py:289-291`이 `question_labels_ko.json` questions 중 binary 집합 == 매퍼 지원 41개를 단언한다 → 질문을 추가하면 이 테스트가 실패한다. 착수 전 매퍼 지원 범위 정의를 별도 키로 옮길지 사용자 결정 필요(매퍼 frozen 파일은 무변경).
- 완료 기준: `Terminology.coverage()["question_text"]["english_remaining"] == 0`(선택 가능 기준) + 사용자 검수.

### TERMINOLOGY_CITATION_REVIEW (후속, 미착수)
- 질환 49 표시명마다 특정 참고 판본(예: 대한의사협회 의학용어집 판수, KCD 차수)을 지정해 인용 근거를 기록한다.
- UMLS 대조 false 18개 각각의 불일치 사유(표기 변이·상하위 개념·환자용 표현 선택 등)를 기록한다. UMLS 문자열 자체는 repo 에 쓰지 않는다(SRL=3).
- 결과로 표시명을 바꾸면 정본만 수정 → export → sync 테스트.

## Task log
| Task | 상태 | 커밋 | 리뷰 | 비고 |
|---|---|---|---|---|
| Design doc | DONE | `1e737d1` | 사용자 승인(C1–C3) | rev1 |
| 1 정본·loader·export·crosscheck | DONE | `67cdd7a` | 독립 리뷰 대기 | TDD: RED(import error) → GREEN 23 → +Presenter 2. 정본 seed는 1회성 scratchpad 스크립트(기존 파일 복사 + 수기 번역), 이후 정본이 편집 위치. crosscheck true 30/false 18/null 1 (MRCONSO 5.7s, nice/ionice) |
| 2 웹 lookup | DONE | `035aa0f` | 독립 리뷰 대기 | RED 3 fail → GREEN 33. node_modules = `~/medmap/medmap-web/node_modules` cp -a(85MB, npm install 없음) |
| merge master 43d5a85 | DONE | `0407741` | — | 충돌 0, export --check rc=0 |
| 3 clinical_summary TerminologyLabelProvider | DONE | `f732d69` | 독립 리뷰 대기 | 3 tests, 기존 25 무수정 통과 |
| 4 전체 회귀 | DONE | `b933c80` | — | backend 217 OK skip 3(master 189 +28) `logs/kt_backend_full_20260926_1851.log` · vitest 26 files/163(master 25/154 +1/+9) `logs/kt_vitest_full_20260926_1851.log` · build OK `logs/kt_build_20260926_1851.log` |
| 5 provenance 정정(감사 후속) | DONE | (이 커밋) | 독립 리뷰 APPROVED(선행) · RG PARTIALLY_REPRODUCIBLE 후속 | seed archive(sha 위 Ruling 5) · standard_term 진술 · class drift guard 2 tests(TDD RED errors=2 → GREEN) · backend 219 OK skip 3 `logs/kt_backend_full_20260926_1859.log` · vitest 26/163 `logs/kt_vitest_full_20260926_1859.log` · build OK `logs/kt_build_20260926_1859.log` · export --check rc=0 `logs/kt_export_check_20260926_1859.log` |
