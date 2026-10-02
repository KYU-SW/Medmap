# MedMap Korean Terminology (presentation layer) Implementation Plan

> **Revision 2 (2026-09-26, 사용자 승인):** C1(질환 표준 용어 직접 작성·UMLS 문자열 repo 금지·boolean 대조만) · C2(질환 49·짧은 표시명 223·value 199 완료 필수, 질문 전문은 backlog `QUESTION_KO_COMPLETION`) · C3(단일 정본 `medmap/data/terminology_ko.json` + 결정적 export + sync 테스트). **rev2가 §3·§6·§7·§9·§11의 rev1 내용을 대체한다 — 맨 아래 'Revision 2' 절이 정본.**
> rev1 상태 문구: DESIGN — 사용자 승인 대기(구현 전).
> 로컬 대체: 이 박스에는 `subagent-driven-development`·`executing-plans`·`brainstorming` 스킬이 없다. 실행은 `project-safety-review` 제약 + 사용자 CLAUDE.md 1-2(실행 전 승인)를 따른다. 기존 코드는 삭제하지 않는다.

**Goal:** 사용자 화면에 영어/raw 문자열이 보이는 지점을 없애기 위해, 모델·내부 ID와 분리된 **정적 한국어 표시 용어층**(질환명 49 · evidence 짧은 표시명 223 · 선택값 표시명)을 만들고 fallback을 감사 가능하게 만든다.

**Architecture:** 번역은 전부 `medmap/data/` 아래 정적 JSON(표시 전용)으로 두고, 읽기 전용 loader 모듈 `medmap/terminology.py` 하나가 조회·fallback·coverage를 책임진다. 진단 모델·PatientState·IG·매퍼(`medmap/intake/`)·세션 계약은 건드리지 않는다. 웹은 기존 선례(`initialCatalog.json` = 정본 사본 + 동등성 테스트)대로 사본을 번들해 ID로 조회한다 → **API 응답 key 변경 0**(§7 결정 C 권장안).

**Tech Stack:** Python 3.12(`~/ai_env`) · unittest / React 19 · Vitest(추가 의존성 없음)

**Spec:** 사용자 2026-09-26 PARALLEL C 프롬프트(아래 Global Constraints에 요약) + `PRODUCT.md` + `docs/medmap_api_design.md` + 선례 `docs/superpowers/plans/2026-09-25-medmap-natural-intake.md`(Task 2 initial 라벨 human gate)

## Global Constraints

- 작업 위치: worktree `~/medmap-worktrees/korean-terminology`, 브랜치 `feat/korean-terminology`(기반 master `336463f`). `~/medmap` master 체크아웃·다른 worktree·STT 파일 수정 금지. `data`·`model_k*.pkl`은 read-only symlink.
- 매핑은 **presentation only**: model/internal ID(질환 class 문자열, `E_*`, `V_*`)를 key로만 쓰고 값으로 바꾸지 않는다. PatientState·`/start`·`/answer` 본문·세션 JSON에 한국어가 들어가지 않는다.
- **mapper alias와 분리**: `medmap/intake/`(freeze `2372e2f`: `aliases_ko.json`, `negative_policy.json`, `mapper.py`, `__init__.py`) 수정·파일 추가 금지. 새 용어 파일은 alias로 쓰이지 않는다.
- 진단 모델(`exp/step16b_*/model_k*.pkl`)·`medmap/diagnosis.py`·`medmap/patient_state.py`·IG 수정 금지. `medmap/api.py` 큰 변경 금지(권장안은 0줄).
- 의료 의미가 애매한 질환명은 임의 번역하지 않고 `review_needed`로 분리 → 사용자 확정 전에는 화면에 draft를 쓰지 않는다(§5).
- 런타임 번역·LLM 호출·외부/유료 API·embedding 매퍼·새 모델·UI 리디자인 금지.
- `release_conditions.json`(en/fr)은 런타임·빌드 어디에서도 새로 읽지 않는다(`config.FORBIDDEN_PATHS`·STEP16B 사전등록). 질환 목록의 정본은 모델 `classes_`.
- git 커밋: `git -c user.name=medmap -c user.email=<email> commit …`, 메시지 끝 `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- 자원: GPU·서버·전체 테스트 스위트는 사용자 지시 전 실행 금지(다른 세션 사용 중). 검증은 신규/관련 테스트 파일 단위.

---

## 1. 판정: **bounded**

| 근거 | 증거 |
|---|---|
| 변경이 표시 계층 한 곳에 갇힘 | 질문 표시는 이미 `QuestionPresenter`(medmap/question_presentation.py:57-116)가 정적 JSON + `is_fallback`으로 처리하는 구조. 같은 패턴의 파일 3개 + loader 1개 추가 |
| 모델·상태·IG 무관 | 질환 key = `model.classes_`(k3/k5/k10 동일 49개, 검증함). evidence/value key = release_evidences.json ID. 인코딩(`evidence.py:48`)·IG 경로에 문자열 값이 들어가지 않음 |
| API 계약 무변경 가능 | 계약 테스트가 key 집합을 고정: `tests/test_serialization.py:156`(`diagnoses[0]` = `{"name","probability"}`), `tests/test_intake_api.py:20,46`(candidate KEYS). 웹 측 ID 조회로 이 key들을 그대로 둘 수 있음(선례 `medmap-web/src/intake/catalog.test.js:12-15`) |
| 되돌리기 쉬움 | 새 파일 추가 + 조회 1곳씩. 삭제만으로 원상복귀 |
| architectural 이 될 조건(채택 안 함) | 서버 응답에 `display_name_ko` 등 key를 추가하면 위 계약 테스트·`docs/medmap_api_design.md` 변경 필요 → §7 결정 C 대안 B로만 남김 |

→ bounded-design 절차: 이 문서(설계 + 과제) → 사용자 결정 3건 → 번역 초안 human gate → 구현.

## 2. 감사 결과 (read-only, 2026-09-26)

### 2.1 도메인 크기

| 항목 | 수 | 출처 |
|---|---|---|
| 진단 후보(모델이 반환 가능한 class) | **49** (k3/k5/k10 `classes_` 동일) | `exp/step16b_next_information_validation/model_k{3,5,10}.pkl`, `medmap/diagnosis.py:39` |
| evidence | **223** (B 208 · C 10 · M 5), 선택 가능 221(제외 `E_134`,`E_152` — `medmap/config.py:14`) | `data/ddxplus/en/release_evidences.json` |
| 부모 질문 / 자식 evidence | 8 / 19 | 같은 파일 `code_question` |
| 비이진 evidence | 15 = 라벨형 9 + 숫자 척도(0–10, value_meaning 없음) 6(`E_56,E_58,E_59,E_132,E_136`, 제외 `E_134`) | 〃 |
| (evidence, value) 쌍 | 764 | 〃 |
| 라벨 있는 고유 value code | **199** (code 간 영문 의미 충돌 0 → 전역 code key 가능) | 〃 |

### 2.2 기존 한국어 자산

| 파일 | 내용 | 상태 |
|---|---|---|
| `medmap/data/question_labels_ko.json` | 질문 전문 53(부모 8 전부 포함), value 188/199, 예/아니요/잘 모르겠어요 | 제품 추적 파일, frozen 아님. 테스트가 개수는 고정 안 함(`tests/test_question_presentation.py:80-84`) |
| `medmap/data/initial_evidence_ko.json` | initial 96개 `label_ko`(짧은 표시명) + `detail_ko`, 사용자 검수 완료(2026-09-25) | 제품 추적 파일. 웹 사본 `medmap-web/src/intake/initialCatalog.json`(byte 동일) |
| `medmap-web/src/intake/startPlan.js:13-20` | bootstrap 6개 질문 문구 | 웹 상수 |
| `medmap/intake/aliases_ko.json`, `negative_policy.json`, `mapper.py` | 매퍼 alias(evidence 41개, 전부 question_labels_ko에 있음) | **FROZEN**(`2372e2f`) — 읽기만, 표시명 출처로 쓰지 않음 |
| 질환 한국어명 | **제품 자산 0** (exp 보고서 본문에만 산발) | — |
| UMLS 2026AA KOR (로컬 `data/umls`) | KCD5 11,001행 · MDRKOR 119,994행. 49질환 중 CUI 경유 47, ICD→KCD5 경유 46, 합 48 후보 존재(`Acute dystonic reactions` 0) | **SRL=3(재배포 제한)** — `data/umls/2026AA/relations/README.md`. repo 복사 불가 → 로컬 대조 전용(§7 결정 A) |
| step9 질환 개념맵 | `exp/step9_external_knowledge/01_disease_concept_map.csv`: EXACT 32 · AMBIGUOUS 12 · PARTIAL 5, review_needed 30 | 기존 연구 산출물(읽기만) |
| step8 evidence 개념맵 | `exp/step8_mapping/evidence_concept_map.csv`: concept_1에 KOR 용어 있는 것 180/223 | 참고만(질문과 1:1 아님, COMPOSITE 55) |

### 2.3 한국어 커버리지 초안(숫자만)

| 대상 | 전체 | 기존 한국어 있음 | 없음 |
|---|---|---|---|
| 질환 표시명 | 49 | 0 | 49 |
| evidence 짧은 표시명 | 223 | 96 (initial `label_ko`) | 127 |
| evidence 질문 전문 | 223 (선택 가능 221) | 53 | 170 (선택 가능 168) |
| evidence 한국어 문구가 하나라도 있음(짧은명 ∪ 전문) | 223 | 122 | 101 |
| 라벨형 value code | 199 | 188 | 11 (`E_204` 여행 지역 `V_0–V_9, V_13`) |
| 숫자 척도 value(0–10) | 6 evidence × 11 | 숫자 그대로 표시(영어 아님) | 척도 양끝 의미 라벨 없음 — 원본에도 없음, 이번 범위 밖 |

### 2.4 영어/raw 노출 지점 (UI·API)

| # | 노출 | 생성 위치 | 화면 위치 | 규모 |
|---|---|---|---|---|
| L1 | 진단 후보 영문 class명 | `medmap/serialization.py:180` (`_top` → `name`) | `medmap-web/src/components/CandidatePanel.jsx:14` (Consult·Summary 둘 다, `SummaryScreen.jsx:23`) | 49 전부 |
| L2 | 질문 전문 영문 fallback | `medmap/question_presentation.py:78-80` (`korean or question.text`) | `QuestionPanel.jsx:74` + "영문 원문" 배지 `:75` | 선택 가능 168 |
| L3 | L2가 요약 이력으로 전파 | `medmap-web/src/session/useMedmapSession.js:45,135` (`asked.question_ko`) | `SummaryScreen.jsx:17` | L2와 동일 |
| L4 | 선택값 영문 fallback | `question_presentation.py:105` (`korean or english or code`) | `QuestionPanel.jsx:81`, 요약 `useMedmapSession.js:171` | `E_204` 11 |
| L5 | raw value code fallback | `useMedmapSession.js:171` (`?.label ?? code`) | `SummaryScreen.jsx:18` | 현재 도달 0(choices에 항상 label 존재) — 방어용 |
| L6 | API payload의 원문 필드 | `question_presentation.py:36,53`(`original_label`,`question_original`), `next_information.py:70` | 웹 렌더 0건(grep) | API 전용, 의도된 필드 — 유지 |
| L7 | 영문 오류 message·`MEDMAP_*` 코드 | `medmap/api.py:151` | `api/messages.js:5` 콘솔만, 화면은 한국어 고정 문구 | UI 노출 0 |
| L8 | intake 후보 라벨 = 질문 전문 | `medmap/api.py:346` | `EvidenceConfirmation.jsx:27` | 현재 41개 모두 한국어 → 노출 0. 짧은 표시명이 아니라 전문 사용(개선 여지, 계약 key 고정이라 이번엔 무변경) |

`medmap/demo_cli.py`(개발용 CLI)는 사용자 UI가 아니라 범위 밖.

## 3. 파일 스키마 (신규 3개, 전부 `medmap/data/`)

(아래 JSON의 label_ko 값은 형식 예시일 뿐 확정 번역이 아니다. 확정은 Task 1 human gate.)

공통 규칙: key는 내부 ID 그대로. 모든 파일에 `schema`·`version`·`generated`·`source_policy`. 항목별 `status ∈ {ok, review_needed}`와 `source` 필수. `review_needed` 항목의 `label_ko`는 **draft**이며 loader가 표시하지 않는다.

### 3.1 `diagnosis_labels_ko.json`

```json
{
  "schema": "medmap.diagnosis_labels_ko/1",
  "version": "1.0.0",
  "generated": "2026-09-26",
  "key_source": "model_k3.pkl classes_ (k3/k5/k10 동일 49개). release_conditions.json 미사용",
  "source_policy": "§4 provenance 규칙",
  "labels": {
    "Pneumonia": {"label_ko": "폐렴", "status": "ok", "source": "standard_term",
                   "crosscheck": "umls_kor_agree", "note": null},
    "URTI": {"label_ko": "상기도 감염", "status": "ok", "source": "standard_term",
             "crosscheck": "umls_kor_agree", "note": "약어 풀어 씀"},
    "Possible NSTEMI / STEMI": {"label_ko": "<draft>", "status": "review_needed",
             "source": "standard_term", "crosscheck": "umls_kor_differ",
             "review_reason": ["compound_class", "hedged_class"], "note": null}
  }
}
```

- `source ∈ {standard_term, existing_asset, user_confirmed}` · `crosscheck ∈ {umls_kor_agree, umls_kor_differ, umls_kor_none, not_checked}`(UMLS 문자열 자체는 저장하지 않음).
- 49개 key 전부 존재해야 함(누락 = 테스트 실패).

### 3.2 `evidence_short_labels_ko.json`

```json
{
  "schema": "medmap.evidence_short_labels_ko/1",
  "version": "1.0.0",
  "generated": "2026-09-26",
  "key_source": "data/ddxplus/en/release_evidences.json (223, 원본 미수정)",
  "labels": {
    "E_201": {"label_ko": "기침", "status": "ok", "source": "initial_evidence_ko", "kind": "symptom"},
    "E_57":  {"label_ko": "통증이 퍼지는 곳", "status": "ok", "source": "question_labels_ko_derived",
              "kind": "attribute", "parent": "E_53"},
    "E_134": {"label_ko": "<예시>", "status": "ok", "source": "question_en_derived",
              "kind": "attribute", "excluded": true}
  }
}
```

- `source ∈ {initial_evidence_ko, question_labels_ko_derived, question_en_derived, user_confirmed}` · `kind ∈ {symptom, history, exposure, family_history, attribute, demographic}`(step8 `evidence_type` 참고, 표시 그룹용).
- 223 key 전부. 96개는 `initial_evidence_ko.label_ko`와 **동일 문자열**(테스트로 고정, 이중 정본 방지).
- 짧은 표시명은 명사구(≤ 12자 권장, 문장·물음표 금지). 자식 evidence는 부모 맥락을 담는다(예: "통증 부위").

### 3.3 `value_labels_ko.json`

```json
{
  "schema": "medmap.value_labels_ko/1",
  "version": "1.0.0",
  "generated": "2026-09-26",
  "key_source": "release_evidences.json value_meaning (라벨형 199 code, code 간 의미 충돌 0)",
  "labels": {
    "V_89": {"label_ko": "이마", "status": "ok", "source": "question_labels_ko"},
    "V_0":  {"label_ko": "북아프리카", "status": "ok", "source": "question_en_derived", "evidence": ["E_204"]}
  },
  "numeric_scale_evidence": ["E_56", "E_58", "E_59", "E_132", "E_134", "E_136"]
}
```

- 199 key 전부. 188개는 `question_labels_ko.values`와 **동일 문자열**(테스트 고정). 신규는 11개(`E_204` 지역).
- 숫자 척도 code("0"–"10")는 번역 대상 아님 → `numeric_scale_evidence`로만 명시(coverage에서 분리 집계).

## 4. 번역 provenance 규칙 (추측 금지)

우선순위(위가 이김):
1. `user_confirmed` — 사용자 human gate에서 확정한 문구.
2. `existing_asset` / `initial_evidence_ko` / `question_labels_ko` — 이미 검수된 제품 파일의 문자열을 그대로 복사(수정 금지).
3. `standard_term` — 대한의학회 의학용어집 등 **널리 쓰이는 표준 한국어 의학용어**가 영문 class와 1:1로 대응할 때만. 로컬 UMLS KOR(KCD5/MDRKOR)과 대조해 `crosscheck`만 기록.
4. `question_labels_ko_derived` / `question_en_derived` — evidence·value 짧은 표시명을 해당 질문 한국어 전문(있으면) 또는 영문 원문에서 **축약**만 한 것(의미 추가 금지).

금지: 런타임/LLM 번역, UMLS SRL=3 문자열의 repo 저장·출처 표기, DDXPlus 프랑스어 질환명 사용(`release_conditions.json` 봉인 — 프랑스어는 `release_evidences.json`의 `question_fr`만 evidence 의미 확인용으로 참고 가능).

## 5. review_needed 기준

질환명은 아래 중 하나라도 해당하면 `review_needed`(draft만 기록, 화면 미사용):
- **R1 복합 class**: `/` 또는 괄호로 둘 이상을 묶음 — 예 `Acute COPD exacerbation / infection`, `Bronchospasm / acute asthma exacerbation`, `HIV (initial infection)`.
- **R2 불확실 표현 포함**: `Possible NSTEMI / STEMI`.
- **R3 약어·고유명만 있음**: `PSVT`, `GERD`, `URTI`, `SLE`, `Boerhaave`, `Chagas`, `Ebola`, `Croup` 등 → 풀어 쓴 표준어가 1개로 정해지면 ok, 여럿이면 review.
- **R4 범위 애매**: step9 `mapping_status ∈ {AMBIGUOUS, PARTIAL}`(17개) 또는 영문과 KOR 대조가 상·하위 개념으로 갈림(`Pulmonary neoplasm`=신생물 vs 악성신생물, `Allergic sinusitis`=부비동염 vs 비염, `Localized edema`, `Spontaneous rib fracture`, `Acute dystonic reactions` KOR 0).
- **R5 원문 오탈자**: `Larygospasm`(key는 원문 그대로 유지, 표시명만).
- **R6 표준어 복수 공존**: 고유어/한자어 병존(예 `심장막염`/`심낭염`, `굴염`/`부비동염`, `기흉`/`공기가슴증`) — 사용자 톤 결정 필요 시.

evidence 짧은 표시명: 질문이 OR/AND/조건부(`negative_policy.json`의 UNSAFE 분류 기준과 같은 판단)여서 축약 시 의미가 줄어들면 `review_needed`. value: 영문 의미가 문맥 없이 모호하면 `review_needed`.

## 6. Loader / presentation 모듈 API — `medmap/terminology.py` (신규)

```python
TERMINOLOGY_DIR = Path(__file__).resolve().parent / "data"

@dataclass(frozen=True)
class DisplayLabel:
    key: str             # 내부 ID(질환 class / E_* / V_*) — 바꾸지 않음
    label: str           # 화면 문자열(한국어 또는 fallback)
    is_fallback: bool    # True = 한국어 ok 항목이 없어 원문을 씀
    status: str          # "ok" | "review_needed" | "missing"

class Terminology:
    def __init__(self, directory=None): ...          # 3개 JSON 로드, schema 검사, 실패 시 ValueError("MEDMAP_TERMINOLOGY_INVALID:...")
    def diagnosis(self, class_name: str) -> DisplayLabel
    def evidence_short(self, evidence_id: str, fallback_text: str | None = None) -> DisplayLabel
    def value(self, code: str, fallback_text: str | None = None) -> DisplayLabel
    def coverage(self, classes, catalog) -> dict       # §8 형식
```

Fallback 정책:
- `status == "ok"` → `label_ko`, `is_fallback=False`.
- `review_needed` 또는 파일에 없음 → 호출자가 준 `fallback_text`(질환은 영문 class명, evidence는 한국어 질문 전문이 있으면 그것, 없으면 영문 원문, value는 영문 라벨), `is_fallback=True`. **draft 문자열은 절대 반환하지 않는다.** raw ID(`E_*`,`V_*`)는 fallback_text가 없을 때만 최후 수단.
- 모듈은 IG·모델·PatientState를 import하지 않는다(`EvidenceCatalog`는 coverage 계산에만 인자로 받음).

## 7. 사용자 승인 필요 결정 (3건)

| # | 결정 | 권장 | 대안 |
|---|---|---|---|
| **A** | 질환명 출처 | 수기 `standard_term` + 로컬 UMLS KOR(KCD5/MDRKOR, SRL=3)은 **대조 결과 플래그만** 기록, 문자열 복사 없음. review_needed는 사용자 human gate에서 확정 | UMLS 한국어 문자열을 그대로 채택(라이선스상 repo 추적 파일에 넣을 수 없음 → 비권장) |
| **B** | 영문 질문 전문 168개(L2/L3) | 이번 범위는 **짧은 표시명만**(사용자 지시 "질문은 기존 그대로 유지 가능"). 대신 fallback 질문일 때 웹이 짧은 표시명을 한국어 제목으로 함께 보여 영어 단독 노출은 없앤다(표시 1줄 추가, 리디자인 아님) | 168개 질문 전문 한국어화까지 이번에 포함(번역량 3배, 별도 human gate 필요) |
| **C** | 표시명을 어디서 붙이나 | **웹 번들 사본 + ID 조회**(선례 `initialCatalog.json`). API·`serialization.py`·계약 테스트 무변경. 백엔드 변경은 `QuestionPresenter`의 value fallback 1곳(`E_204` 11개, 응답 key 불변)뿐 | 서버가 `diagnoses[].display_name_ko`·`next_question.short_label_ko` 추가 → `tests/test_serialization.py:156`·`docs/medmap_api_design.md` 계약 변경(= architectural) |

## 8. Coverage report 형식

`Terminology.coverage()` 출력 + `docs/…/2026-09-26-medmap-korean-terminology.coverage.md`(Task 5에서 생성, 사람이 읽는 표):

```json
{
  "diagnosis":  {"total": 49, "ok": 0, "review_needed": 0, "missing": 0},
  "evidence_short": {"total": 223, "selectable": 221, "ok": 0, "review_needed": 0, "missing": 0,
                     "by_source": {"initial_evidence_ko": 96}},
  "value": {"labeled_total": 199, "ok": 0, "review_needed": 0, "missing": 0,
            "numeric_scale_evidence": 6},
  "question_full_ko": {"selectable": 221, "korean": 53, "fallback_en": 168},
  "leaks": [{"id": "L1", "status": "closed|open", "remaining": 0}]
}
```

사람용 표에는 추가로 review_needed 목록(key · draft · 사유 코드 R1–R6 · crosscheck)을 전부 나열한다.

## 9. 파일 구조

| 파일 | 변경 | 책임 |
|---|---|---|
| `medmap/data/diagnosis_labels_ko.json` | 신규 | 질환 49 표시명 |
| `medmap/data/evidence_short_labels_ko.json` | 신규 | evidence 223 짧은 표시명 |
| `medmap/data/value_labels_ko.json` | 신규 | value 199 표시명 |
| `medmap/terminology.py` | 신규 | loader·fallback·coverage |
| `medmap/question_presentation.py:104-105` | 수정(추가만) | `values_ko`에 없으면 `Terminology.value` ok 항목 사용(L4). 기존 경로·반환 key 불변 |
| `tests/test_terminology.py` | 신규 | §10 |
| `medmap-web/src/terminology/{diagnosisLabels,evidenceShortLabels,valueLabels}.json` | 신규(사본) | 웹 번들 |
| `medmap-web/src/terminology/labels.js` + `.test.js` | 신규 | `diagnosisLabel(name)`, `evidenceShortLabel(id)` — ok만 반환, 아니면 원문 |
| `medmap-web/src/components/CandidatePanel.jsx:14` | 수정 1줄 | `{diagnosisLabel(row.name)}` (key·testid는 `row.name` 유지) |
| `medmap-web/src/components/QuestionPanel.jsx:74-75` | 수정(결정 B 채택 시) | fallback 질문이면 짧은 표시명 제목 추가 |
| `medmap/api.py` | **무변경** | — |

## 10. 테스트 계획

Python `tests/test_terminology.py`:
1. 3개 파일 schema·version·필수 필드·`status` 값 검증.
2. 질환 key 집합 == `DiagnosisEngine(…,"k3").classes`(49, 여분·누락 0) — 모델 로드 1회(pkl 238KB).
3. evidence key 집합 == `EvidenceCatalog().ids`(223).
4. value key 집합 == 라벨형 199 code; 숫자 척도 evidence 목록 == value_meaning 없는 6개.
5. 이중 정본 방지: 96개 짧은 표시명 == `initial_evidence_ko.label_ko`, 188개 value == `question_labels_ko.values`.
6. `review_needed` 항목은 `diagnosis()`가 draft가 아닌 영문 원문 + `is_fallback=True` 반환.
7. 짧은 표시명 형식: 비어 있지 않음, `?`·문장부호 종결 없음, 라틴 알파벳 없음(약어 예외 허용 목록 명시).
8. 분리 보장: `medmap/terminology.py` 소스가 `medmap.intake`·`next_information`·`diagnosis`를 import하지 않음(정적 검사), `medmap/intake/` 파일 SHA가 freeze `2372e2f`와 동일.
9. `QuestionPresenter.present("E_204")` 선택지 11개가 한국어·`is_fallback=False`, 기존 `test_question_presentation.py` 전부 무수정 통과.

Vitest:
10. 웹 사본 3개 == Python 정본(`catalog.test.js:12-15` 패턴).
11. `CandidatePanel`이 한국어 표시명 렌더, `data-testid`는 영문 key 유지, review_needed/미등록은 원문.
12. (결정 B) fallback 질문에 짧은 표시명 제목 표시, 비-fallback 질문은 화면 무변화.

실행 범위: 위 신규 파일 + `tests/test_question_presentation.py` + 관련 vitest 파일만(전체 스위트는 사용자 지시 후).

## 11. Tasks (승인 후)

### Task 0: Preflight (coordinator)
- [ ] symlink·`git status` clean·`free -m` ≥ 3GB 확인, `medmap/intake/` SHA 기록.

### Task 1: 번역 초안 (문서 산출, 코드 없음) — **human gate**
- [ ] 3개 JSON 초안을 §3 스키마로 작성(기존 자산 복사분 먼저, 신규는 §4 규칙). 로컬 UMLS KOR 대조 결과는 `crosscheck` 플래그만.
- [ ] review_needed 목록 + 신규 evidence 127·value 11 문구를 사용자에게 제출 → 확정분 `user_confirmed`.

### Task 2: `medmap/terminology.py` + `tests/test_terminology.py` (§6, §10 1–8)
- [ ] 테스트 먼저 작성 → 실패 확인 → loader 구현 → 통과 → 커밋.

### Task 3: `QuestionPresenter` value fallback (L4) (§10 9)
- [ ] `test_question_presentation.py` 옆에 E_204 테스트 추가 → 구현(추가만) → 기존 테스트 무수정 통과 → 커밋.

### Task 4: 웹 사본 + `labels.js` + CandidatePanel(+결정 B 시 QuestionPanel) (§10 10–12)
- [ ] 사본 복사 → 동등성 테스트 → 표시 변경 → vitest(관련 파일) → build → 커밋.

### Task 5: coverage report + 원장 갱신
- [ ] `Terminology.coverage()` 결과로 `.coverage.md` 작성(수치는 실행 결과에서만), L1–L8 closed/open 표기 → 커밋.

## Self-Review
- Spec 4항(질환·evidence·value·fallback audit) → §2.4, §3, Task 1–5에 대응. 파일 3종 형태 검토 → §3. coverage report → §8/Task 5.
- 매퍼 frozen·모델·PatientState·api.py 비변경 → Global Constraints, §9, §10-8.
- 미정 사항은 §7 결정 A–C로만 남김. 번역 문구 자체는 Task 1 human gate 전까지 작성하지 않음.


---

## Revision 2 (2026-09-26 사용자 승인) — 구현 정본

### R2.1 판정 재분류: **bounded (다중 표면, 계약 무변경)**
C3로 백엔드 정적 파일 loader·export 스크립트·프론트 조회가 함께 바뀌지만, 바뀌는 것은 모두 표시 계층이다.
- API 응답 key 변경 0(`tests/test_serialization.py:156`, `tests/test_intake_api.py:20,46` 무수정 통과로 검증).
- 모델·PatientState·IG·매퍼 무변경(`git diff master -- medmap/intake/` 비어 있음으로 검증).
- 되돌리기: 새 파일 삭제 + 프론트 조회 3곳 원복 + 미러 파일 이전 버전 복원.
→ 절차: TDD(loader·export·sync 먼저 실패 테스트) + 프론트 lookup 테스트.

### R2.2 단일 정본과 미러 (한 문자열 = 편집 가능한 위치 하나)

| 문자열 | 정본(편집 위치) | 파생(생성물, 손으로 편집 금지) |
|---|---|---|
| 질환 표시명 49 | `terminology_ko.json` `diseases` | `medmap-web/src/generated/terminology_ko.json` |
| evidence 짧은 표시명 223 | `terminology_ko.json` `evidence_short` | web generated · `initial_evidence_ko.json` 의 96개 `label_ko` · `medmap-web/src/intake/initialCatalog.json` |
| 질문 전문 53 | `terminology_ko.json` `evidence_questions` | `question_labels_ko.json` `questions` · `initial_evidence_ko.json` 의 `detail_source=="question_labels_ko"` 27개 `detail_ko` |
| value 199 | `terminology_ko.json` `values` | `question_labels_ko.json` `values` · web generated |
| 예/아니요/잘 모르겠어요 | `terminology_ko.json` `answer_labels` | `question_labels_ko.json` |
| initial 전용 필드(rank·count·신규 69 `detail_ko`·frequent_ids·header) | `initial_evidence_ko.json`(그대로) | initialCatalog.json |

**선택 이유:** 기존 소비자(`QuestionPresenter`, `api.load_initial_ids`, 매퍼 테스트 `tests/test_intake_mapper.py:17`, 웹 `catalog.js`·`startPlan.test.js`, master의 `clinical_summary.PresenterLabelProvider`)가 읽는 파일 경로·형식을 그대로 두어 동작을 깨지 않으면서, 그 파일의 용어 필드를 정본에서 **결정적으로 재생성**한다. 두 기존 파일은 `json.dumps(indent=1, ensure_ascii=False)`(끝 개행 없음)로 byte 재현됨을 확인했다 → 재생성 전후 diff는 의도한 변경(value +11)뿐.
생성기: `scripts/export_web_terminology.py`(인자 없음 = 쓰기, `--check` = 불일치 시 exit 1). sync 테스트가 생성 결과와 커밋된 파일 전부를 byte 비교한다.

### R2.3 정본 스키마 `medmap/data/terminology_ko.json`
```json
{
 "schema": "medmap.terminology_ko/1",
 "version": "1.0.0",
 "note": "...",
 "answer_labels": {"unknown_choice_label": "잘 모르겠어요", "yes_label": "예", "no_label": "아니요"},
 "diseases": {"Pneumonia": {"label_ko": "폐렴", "status": "ok", "source": "standard_term", "umls_kor_crosscheck": true},
              "Pulmonary neoplasm": {"draft_ko": "…", "status": "review_needed", "source": "standard_term",
                                     "umls_kor_crosscheck": false, "review_reason": "…"}},
 "evidence_short": {"E_53": {"label_ko": "통증", "status": "ok", "source": "initial_evidence_ko_user_reviewed"}},
 "evidence_questions": {"E_0": {"text_ko": "…", "status": "ok", "source": "question_labels_ko_v1"}},
 "values": {"V_0": {"label_ko": "북아프리카", "status": "ok", "source": "question_en_derived"}}
}
```
- `ok`만 `label_ko`/`text_ko`를 가진다. `review_needed`는 `draft_ko`만 → loader·export가 draft를 절대 내보내지 않는다(구조적 보장).
- `umls_kor_crosscheck`: `true`(표시명이 로컬 UMLS KCD5/MDRKOR 문자열과 공백·하이픈 무시 일치) / `false`(후보는 있으나 불일치) / `null`(후보 없음). 문자열은 저장하지 않는다. 계산 스크립트 `scripts/crosscheck_umls_kor.py`(로컬 UMLS 필요, repo에 UMLS 데이터 없음).
- source 값: `standard_term` · `initial_evidence_ko_user_reviewed` · `question_labels_ko_v1` · `question_labels_ko_derived` · `question_en_derived`.

### R2.4 review_needed 기준(질환, rev1 §5 정정)
rev1 R4(step9 AMBIGUOUS/PARTIAL)는 UMLS 개념 선택의 모호함이지 한국어 의미의 모호함이 아니다(예: 백일해·심방세동은 AMBIGUOUS였지만 번역은 1:1). rev2는 **영문 class 자체의 의학적 범위가 한 한국어 용어로 정해지지 않는 경우**만 review_needed로 둔다: 복합 class(`/`), 불확실 표현(Possible), 양성/악성 범위 불명(neoplasm), DDXPlus 명칭과 실제 임상상이 어긋날 수 있는 것(Allergic sinusitis), 표기 변이가 커 표준 표기를 정할 수 없는 고유명(Boerhaave).

### R2.5 Loader API `medmap/terminology.py`
`Terminology(path=None)` · `.disease(name)` · `.evidence_short(evidence_id)` · `.question(evidence_id, fallback)` · `.value(code, fallback=None)` → `DisplayLabel(key, label, is_fallback, status)`; `.review_needed()` → 목록; `.coverage(disease_classes, evidence_ids, value_codes)` → dict. 파일 형식 오류는 `ValueError("MEDMAP_TERMINOLOGY_INVALID:…")`. IG·모델·매퍼 import 없음.
fallback: 질환 → 영문 class명, 짧은 표시명 → `None`(label 없음, `is_fallback=True`), 질문 → 호출자 fallback(영문 원문), value → 호출자 fallback.

### R2.6 프론트
- `medmap-web/src/generated/terminology_ko.json`(생성물, ok 항목만 + `source_sha256`).
- `src/terminology/labels.js`: `diseaseLabel(name)`(없으면 name), `evidenceShortLabel(id)`(없으면 null), `valueLabel(code)`(없으면 null).
- 적용: `CandidatePanel` 표시명(Consult·Summary 공통, key·testid는 내부 이름 유지) · `QuestionPanel` 영문 fallback 질문일 때 한국어 짧은 표시명 제목 1줄 · `useMedmapSession` 요약 이력(fallback 질문은 짧은 표시명) · `describeAnswer` code fallback → valueLabel.

### R2.7 Backlog `QUESTION_KO_COMPLETION` (이 브랜치 merge blocker 아님, 최종 제품 전 필수)
- 목표: 사용자에게 보일 수 있는 **모든 질문 전문** 한국어화(현재 53/223, 영문 fallback 170 = 선택 가능 168 + 제외 2).
- 규칙: 정본 `terminology_ko.json` `evidence_questions`에만 추가(미러는 export로 생성). OR/AND/조건부/과거력(antecedent) 질문은 **원문 의미 전체 보존, 축약 금지**. 의미가 애매하면 `review_needed`(draft_ko만). 추가 후 `QuestionPanel`의 "영문 원문" 배지·짧은 표시명 제목은 자동으로 사라진다(is_fallback=false).
- 완료 기준: `Terminology.coverage()["question_text"]["english_remaining"] == 0`(선택 가능 기준) + 사용자 검수.
- 매퍼 영향 주의: `tests/test_intake_mapper.py:17`이 `question_labels_ko.json` questions 키 집합으로 매퍼 지원 범위를 검사할 수 있다 → 추가 전 해당 테스트 의미 확인 필요.
