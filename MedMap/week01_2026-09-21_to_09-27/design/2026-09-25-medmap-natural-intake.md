# MedMap Natural Intake (기능 구현) Implementation Plan

> **Revision 2 (2026-09-25):** 사용자 피드백 9항 반영 — 전용 worktree, POSITIVE-only start feature, UNKNOWN 비계수·START_INCOMPLETE, 신규 테스트 수 21 통일, V1 CSS 의존 preflight, human gate는 애매한 라벨만. 실행 방식: Subagent-driven(task별 fresh implementer + spec/code review, 전체 완료 후 whole-branch review).
> 로컬 대체(이 박스에는 두 스킬이 없음): 실행은 `project-safety-review` 제약 + 사용자 CLAUDE.md 1-2(실행 전 승인)를 따른다. 기존 코드는 삭제하지 않는다.

**Goal:** 자유 텍스트 → `/v1/intake/extract` → 후보 확인 → initial 결정 → 부족분 bootstrap → exact-k3 `/v1/session/start` → 기존 IG 질문 흐름을 실제로 끝까지 동작시킨다(디자인 평가 대상 아님).

**Architecture:** 백엔드는 frozen 매퍼 v1.2를 감싸는 stateless endpoint 1개만 추가한다(기존 session 3 endpoint 무변경). initial/bootstrap/cache 규칙은 프론트엔드의 순수 함수 모듈(`src/intake/`)로 두고, 기존 `feat/web-ui`의 기능 로직(API client·세션 훅·질문/후보/요약 화면)을 파일 단위로 가져와 새 최소 UI(흰 배경·기본 타이포)로 조립한다.

**Tech Stack:** Python 3.12(`~/ai_env`) FastAPI 0.141 · unittest / React 19 · Vite 8 · Vitest 5 · Testing Library(추가 의존성 없음, lockfile 그대로)

**Spec:** 사용자 2026-09-25 프롬프트("UI V2 디자인 작업은 여기서 중단한다 … NEXT PRIORITY Natural Intake") + `docs/medmap_natural_intake_design.md` + `.claude/handoff/HANDOFF_MASTER.md` §23·§25·§26 + `research/step17a:exp/step17a_intake_start_validation/STEP17A_REPORT.md`

## Global Constraints

- 디자인 작업 PAUSED. 새 시각 콘셉트 금지, 관측 기록지(V1) 시각 요소 재사용 금지, V2 시안 production 적용 금지. UI = 흰 배경 · 기본 typography · 명확한 버튼 · 최소 spacing · 모바일 사용 가능.
- `design/web-ui-v2`: 보존 · merge 금지 · 수정 금지. `feat/web-ui`: 보존 · merge 금지 · 삭제 금지(파일 단위 `git checkout feat/web-ui -- <path>`로만 가져온다). `research/step17a`: master merge 금지.
- master에는 intake mapper만 merge된 상태를 유지한다 → 이 작업은 `feat/natural-intake` 브랜치에서만. master merge는 사용자 승인 후 별도.
- **frozen 매퍼 v1.2(`medmap/intake/` 전체) 수정 금지** — 새 파일 추가도 금지. 매퍼 출력은 후보일 뿐, 사용자 확인 없이 세션·cache에 넣지 않는다.
- 한국어 display label은 **mapper alias가 아니다**. `medmap/data/initial_evidence_ko.json`(표시·검색 전용)에 둔다.
- `POST /v1/intake/extract`만 추가. `/health`·`/v1/session/start`·`/answer`·`/resume` 계약 변경 금지.
- request text: 저장 금지 · 로그 금지 · 세션/cache/sessionStorage/`/start` 본문에 넣지 않는다. response는 candidate만.
- exact-k: `/start`는 initial 1 + additional 정확히 3. bootstrap 순서 `E_91 → E_53 → E_66`, 예비 `E_201 → E_175 → E_88`(STEP17A frozen, 변경 금지).
- **(rev2) STEP17A 검증 범위 준수 — start feature는 POSITIVE 확인 + known bootstrap 답만.**
  - initial·additional에는 사용자가 **확인한 POSITIVE**만 쓴다(STEP17A R3 pool = POSITIVE).
  - 확인된 NEGATIVE는 사용자 확인 결과로 보존하되 additional에 넣지 않고 **cache**에 둔다. 엔진이 실제로 그 질문을 제안할 때만 `/session/answer`로 적용한다.
  - bootstrap에서 "잘 모르겠어요"(UNKNOWN)를 고르면 사용자 응답으로 기록(요약 화면 history)하되 **exact-k count에 넣지 않고 `/start` 본문에도 넣지 않는다**. frozen 목록의 다음 질문으로 넘어가 known 답(POSITIVE/NEGATIVE)이 부족분만큼 찰 때까지 진행한다.
  - bootstrap 목록은 initial과 **확인된 모든 항목(POSITIVE·NEGATIVE)**을 건너뛴다(같은 질문 재질문 금지 = "중복 시 backup").
  - frozen 목록을 다 써도(남은 질문으로 채울 수 없게 된 시점 포함) 부족분을 못 채우면 `/session/start`를 호출하지 않고 **`START_INCOMPLETE`** 상태로 끝낸다.
- initial 가능 = TRAIN INITIAL_EVIDENCE 고유값 96개. NEGATIVE·과거력은 initial 불가. 96개 전체를 버튼으로 펼치지 않는다(자주 쓰는 8개 + 검색).
- 목록 밖 주 증상을 "지원 범위 밖" 종료 처리하지 않는다. 추출 0개 문구 = "말씀하신 내용에서 확실하게 확인할 수 있는 항목을 찾지 못했어요." / "증상이 없습니다" 류 금지.
- cache = `{evidence_id, status}`만. 엔진이 실제로 제안한 질문일 때만 `/session/answer`로 적용(질문 예산 1 소비). posterior 직접 수정 금지.
- 제외: STT·Whisper endpoint·최종 디자인·애니메이션·디자인 시스템·embedding·LLM·STEP17B.
- UI에 IG(bits)·`MEDMAP_*` 코드 노출 금지. 런타임 의존성은 react/react-dom뿐(Tailwind·상태관리·UI 프레임워크·차트 금지).
- 원본 VALIDATION/TEST/`release_conditions.json` 접근 금지(`config.check_path` 가드 유지).
- **(rev3, 2026-09-26 사용자 결정)** 확인된 NEGATIVE는 기본 cache. 단 frozen bootstrap/backup 순서에서 이번 start를 채우려고 walk가 실제로 도달하는 항목이면 그 NEGATIVE를 bootstrap 답으로 재사용(additional 1개로 계수, 재질문 없음, cache에서 제외). 도달하지 않거나 목록 밖 NEGATIVE는 cache 유지. bootstrap은 initial·확인 POSITIVE만 건너뛴다(ledger Ruling 1 대체 → Ruling 5). UNKNOWN은 계속 비계수.
- STEP17A R3 top1 0.849를 제품 정확도로 표기하지 않는다. (rev2, rev3로 일부 대체) NEGATIVE·UNKNOWN을 start에서 배제해 시작 상태가 STEP17A R3(POSITIVE pool + R2 bootstrap의 실제 답) 형태와 같아지도록 했다. 남는 미검증: 4개 이상 확인 시 "발화 순서 앞 3개"는 UI heuristic, 사용자가 잘못 확인한 양성의 영향.
- (rev2) 실행 중 human gate는 **의미가 애매한 신규 initial 라벨** 하나뿐이다. `npm ci`(새 dependency 0·lockfile 무변경 확인 시)·로컬 서버 기동·Playwright 스크린샷은 승인 없이 진행한다(외부 publish/upload 금지).
- (rev2) 구현은 전용 worktree `~/medmap-worktrees/natural-intake`에서만. master 작업 트리에는 구현 변경을 만들지 않는다.
- git 커밋: `git -c user.name=medmap -c user.email=<email> commit …`, 메시지 끝 `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- 2분 이상 걸릴 수 있는 명령은 `nohup … > logs/…log 2>&1 &` 백그라운드.

---

## 0. 브랜치 전략

| 항목 | 결정 | 이유 |
|---|---|---|
| 기반 | `master`(`b89b1de`, 매퍼 v1.2 + handoff v4) | 사용자: master = intake mapper만 |
| 새 브랜치 | `feat/natural-intake` | 기능 구현 전용 |
| 작업 위치 | **(rev2) 전용 worktree `~/medmap-worktrees/natural-intake`** (`git worktree add -b feat/natural-intake … master`). master 작업 트리에는 구현 변경 0 | 사용자 rev2 §1 |
| 무시된 입력 | worktree에서 원본을 가리키는 **read-only 참조 symlink**: `data -> ~/medmap/data`, `exp/step16b_next_information_validation/model_k{3,5,10}.pkl -> ~/medmap/…`. `*.pkl`은 기존 `.gitignore`로, `data` symlink는 `.git/info/exclude`의 `/data`로 무시(디렉터리 규칙 `data/`는 symlink에 안 걸림). 원본은 수정하지 않는다 | API 테스트·실서버가 모델·evidence 정의를 읽어야 함(메모리 worktree-missing-gitignored-inputs) |
| feat/web-ui에서 가져오기 | `git checkout feat/web-ui -- <파일>`(아래 §1 목록만). merge·cherry-pick 금지 | V1 시각 CSS·IntakeScreen을 끌고 오지 않기 위해 |
| 새 프론트 데이터 폴더 | `medmap-web/src/intake/` (**`src/data/` 금지**) | 루트 `.gitignore`의 `data/` 규칙이 모든 `data` 폴더를 무시한다. 실제로 `feat/web-ui`의 `medmap-web/src/data/intake.js`·`intake.generated.json`·`intake.test.js`는 **커밋되지 않았다**(worktree에만 존재, `git check-ignore` 확인). 같은 결함 반복 방지 |
| npm | worktree `medmap-web`에서 `npm ci`(lockfile 그대로, 새 패키지 0). 실행 후 `package-lock.json`·dependencies 무변경을 확인하면 중단 없이 진행 | 사용자 rev2 §7 |
| 병합 | 이 계획 범위 밖. 완료 보고 후 사용자 결정 | |

## 1. feat/web-ui 재사용 감사

`git diff master feat/web-ui -- medmap tests`: 백엔드 차이는 intake 매퍼 쪽뿐(= feat/web-ui가 매퍼 이전 분기). 백엔드는 master 것을 그대로 쓴다.

| 파일(`medmap-web/…`) | 처리 | 비고 |
|---|---|---|
| `package.json`, `package-lock.json`, `.gitignore`, `vite.config.js` | 가져옴 | package.json은 scripts만 수정(`build:intake` 제거 → `sync:initial` 추가). 의존성 무변경 |
| `index.html` | 가져와 수정 | Pretendard CDN `<link>` 제거(기본 typography) |
| `src/main.jsx` | 가져와 수정 | V1 CSS 3개 import → `./styles/plain.css` 1개 |
| `src/api/client.js` (+test) | 가져와 수정 | `extractIntake(text)` 추가 |
| `src/api/messages.js` (+test) | 그대로 | 오류 문구·코드 비노출 |
| `src/session/useMedmapSession.js` (+test) | 가져와 수정 | `extract`, cache 적용(`settle`), `autoApplied` 추가. 기존 테스트 전부 유지 |
| `src/components/CandidatePanel.jsx` (+test), `ChoiceButton.jsx`, `Notice.jsx` (+test), `QuestionPanel.jsx` (+test), `AppHeader.jsx` (+test) | 그대로 | 클래스명은 남지만 스타일은 새 plain.css만 적용 |
| `src/lib/candidates.js` (+test) | 그대로 | |
| `src/screens/StartScreen.jsx` (+test), `ConsultScreen.jsx` (+test), `SummaryScreen.jsx` (+test) | 그대로 | |
| `src/a11y.test.jsx` | 그대로 | ConsultScreen·AppHeader만 사용 |
| `src/test/setup.js`, `src/test/fixtures/turn.*.json` | 그대로 | |
| `scripts/record-fixtures.mjs` | 그대로 | |
| `src/App.jsx` | **새로 작성**(Task 9) | IntakeScreen → NaturalIntakeScreen |
| `src/App.test.jsx`, `src/integration.test.jsx` | **새로 작성**(Task 9) | 기존 것은 41개 목록 흐름 전제 |
| `src/screens/IntakeScreen.jsx` (+test), `src/data/*`(미커밋), `scripts/build-intake-data.mjs` | **가져오지 않음** | 41개 목록 + 고정 3문항 폼(교체 대상), 14개 과거력 initial 결함 포함 |
| `src/styles/tokens.css`, `app.css`, `responsive.css`, `responsive.test.js` | **가져오지 않음** | V1 시각(DESIGN_REJECTED) |
| `README.md` | 새로 작성(Task 10) | |

## 2. 파일 구조

**새 파일**
- `medmap/data/initial_evidence_ko.json` — initial 96개 표시 라벨(`evidence_id, train_rank, train_count, label_ko, detail_ko, detail_source`) + `frequent_ids` 8개. 초안: `docs/superpowers/plans/2026-09-25-medmap-natural-intake.initial_evidence_ko.draft.json`(SHA256 `15c892263ffb63187faad952f52a751e85828be79b5eaf84551661fd705e8e4b`(사용자 검수 반영본))
- `tests/test_initial_evidence_catalog.py` — 96개 무결성(+ `MEDMAP_SLOW_TESTS=1`일 때 TRAIN 대조)
- `tests/test_intake_api.py` — `/v1/intake/extract` 계약·원문 비로그
- `tests/test_natural_intake_e2e.py` — 실제 엔진으로 extract → start(A·B·C·E) + 서버측 D 가드
- `medmap-web/scripts/sync-initial-catalog.mjs` — Python 쪽 JSON을 프론트로 복사
- `medmap-web/src/intake/initialCatalog.json` — 위 JSON 사본(동기화 테스트로 동일성 강제)
- `medmap-web/src/intake/catalog.js` (+`catalog.test.js`) — 96개 조회·검색
- `medmap-web/src/intake/startPlan.js` (+`startPlan.test.js`) — initial 후보, additional/cached 분리, bootstrap, `/start` 본문 조립
- `medmap-web/src/intake/answerCache.js` (+`answerCache.test.js`) — cache 저장/정제/적용 판정
- `medmap-web/src/components/FreeTextInput.jsx`, `EvidenceConfirmation.jsx`, `InitialPicker.jsx`, `BootstrapQuestion.jsx` (+각 test)
- `medmap-web/src/screens/NaturalIntakeScreen.jsx` (+test)
- `medmap-web/src/styles/plain.css`
- `medmap-web/e2e/natural-intake.e2e.mjs` — 실서버 Playwright 스모크(설치 없이 캐시된 playwright 사용)

**수정 파일**
- `medmap/api.py` — `MAPPER_VERSION`, `IntakeExtractRequest`, `EngineRegistry.initial_ids`, `POST /v1/intake/extract` 추가만(기존 함수 본문 무변경)
- `medmap-web/src/api/client.js`, `src/session/useMedmapSession.js`, `src/main.jsx`, `index.html`, `package.json`(scripts)

## 3. session resume 충돌 점검(설계 결론 — Task 8·9 테스트로 고정)

| # | 상황 | 처리 |
|---|---|---|
| R1 | intake 도중(시작 전) 새로고침 | 아무것도 저장하지 않았으므로 시작 화면. 원문 복구 없음(의도) |
| R2 | cache 저장 시점 | `/start` 성공 직후에만, 세션 저장과 같은 턴에서 |
| R3 | 세션 + cache가 있는 상태에서 새로고침 | `/resume` → 제안된 질문이 cache에 있으면 `/answer`로 적용 → 반복 |
| R4 | cache만 있고 세션이 없음 | 마운트 시 cache 삭제 |
| R5 | `/resume` 실패 | 세션·cache 모두 삭제, 시작 화면(오류 문구 없음 — 기존 동작) |
| R6 | [처음부터 다시] | 세션·cache 모두 삭제 |
| R7 | cache 자동 적용 중 2번째 `/answer` 실패 | 마지막으로 성공한 턴을 적용하고 오류 표시(서버가 이미 받은 답을 잃지 않음) |
| R8 | StrictMode 이중 effect | 기존 `alive` 가드 — 첫 effect의 resume 결과는 settle하지 않음 |
| R9 | 서버 측 | 제안되지 않은 질문에 답하면 기존 409 `MEDMAP_UNEXPECTED_ANSWER` 그대로 |

---

### Task 0: Preflight — worktree·symlink·CSS 의존 검사·기준선 (coordinator 수행)

**Files:** 없음(환경). 결과는 ledger `docs/superpowers/plans/2026-09-25-medmap-natural-intake.ledger.md`에 기록

- [ ] **Step 1: worktree + read-only symlink**

```bash
git -C ~/medmap worktree add -b feat/natural-intake ~/medmap-worktrees/natural-intake master
W=~/medmap-worktrees/natural-intake
ln -s ~/medmap/data $W/data
for f in model_k3.pkl model_k5.pkl model_k10.pkl; do ln -s ~/medmap/exp/step16b_next_information_validation/$f $W/exp/step16b_next_information_validation/$f; done
grep -qx '/data' ~/medmap/.git/info/exclude || echo '/data' >> ~/medmap/.git/info/exclude
git -C $W status --short --ignored
```
Expected: `!! data`, `!! exp/…/model_k*.pkl`(무시됨), 추적 변경 0. `git -C ~/medmap status --short` = `?? exp/step17a_intake_start_validation/`뿐(master 작업 트리에 구현 변경 0)

- [ ] **Step 2: V1 CSS 의존 검사**

```bash
for f in components/CandidatePanel.jsx components/ChoiceButton.jsx components/Notice.jsx components/QuestionPanel.jsx components/AppHeader.jsx screens/StartScreen.jsx screens/ConsultScreen.jsx screens/SummaryScreen.jsx; do
  git -C ~/medmap show feat/web-ui:medmap-web/src/$f | grep -nE "import .*\.css|getComputedStyle|style=" ; done
```
판정 기준: 컴포넌트가 CSS 파일을 import하거나 계산된 스타일로 동작을 바꾸면 FAIL(기능 markup만 가져오고 재작성). className은 markup hook(테스트 선택자)으로만 쓰이면 PASS. 인라인 `style`은 막대 폭(확률 비례)·헤더 점 배치뿐이면 PASS.
V1 시각 요소(`candidate__ghost` 이전값, `progress-dot`)는 plain.css에서 **평범한 텍스트/작은 점**으로만 스타일링하고 V1 색·격자·괘선은 되살리지 않는다.

- [ ] **Step 3: 백엔드 기준선(worktree, 백그라운드)**

```bash
cd ~/medmap-worktrees/natural-intake && mkdir -p logs && nohup ~/ai_env/bin/python -m unittest discover -s tests > logs/ni_baseline_backend_$(date +%Y%m%d_%H%M).log 2>&1 &
echo "PID: $!"
```
완료 후 `tail -5 logs/ni_baseline_backend_*.log` → `Ran N tests … OK`. N을 ledger에 기록(worktree symlink로 모델 로딩이 되는지도 이것으로 확인).

- [ ] **Step 4: 프론트 기준선(feat/web-ui worktree, 읽기 전용 실행)**

```bash
cd ~/medmap-worktrees/web-ui/medmap-web && npx vitest run 2>&1 | tail -5
```
통과 수를 참고값으로 기록(그 worktree에는 미커밋 `src/data/*`가 있다).

- [ ] **Step 5: 계획·ledger 커밋(feat/natural-intake)**

```bash
cd ~/medmap-worktrees/natural-intake && git add docs/superpowers/plans/2026-09-25-medmap-natural-intake.md docs/superpowers/plans/2026-09-25-medmap-natural-intake.initial_evidence_ko.draft.json docs/superpowers/plans/2026-09-25-medmap-natural-intake.ledger.md
git -c user.name=medmap -c user.email=<email> commit -m "Add Natural Intake implementation plan (rev2) and execution ledger

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 1: feat/web-ui 기능 로직 가져오기 + 최소 스타일

**Files:**
- Create(가져옴): §1 표의 "가져옴/그대로/가져와 수정" 파일
- Create: `medmap-web/src/styles/plain.css`
- Modify: `medmap-web/index.html`, `medmap-web/src/main.jsx`, `medmap-web/package.json`

**Interfaces:**
- Produces: 기존 `client.js` 함수(`getHealth, startSession, submitAnswer, resumeSession, ApiError, MODEL_CONTEXT`), `useMedmapSession`, `QuestionPanel({question,onAnswer,pending})`, `CandidatePanel({rows,note})`, `ConsultScreen({turn,onAnswer,pending})`, `SummaryScreen({turn,history,onRestart})`, `StartScreen({ready,checking,onStart})`, `Notice({message,onRetry,onRestart})`, `AppHeader({step,total})`, `userMessage(error)`

- [ ] **Step 1: 파일 가져오기**

```bash
cd ~/medmap-worktrees/natural-intake && git checkout feat/web-ui -- \
  medmap-web/.gitignore medmap-web/package.json medmap-web/package-lock.json medmap-web/vite.config.js \
  medmap-web/index.html medmap-web/src/main.jsx \
  medmap-web/src/api/client.js medmap-web/src/api/client.test.js \
  medmap-web/src/api/messages.js medmap-web/src/api/messages.test.js \
  medmap-web/src/session/useMedmapSession.js medmap-web/src/session/useMedmapSession.test.jsx \
  medmap-web/src/components/CandidatePanel.jsx medmap-web/src/components/CandidatePanel.test.jsx \
  medmap-web/src/components/ChoiceButton.jsx medmap-web/src/components/Notice.jsx medmap-web/src/components/Notice.test.jsx \
  medmap-web/src/components/QuestionPanel.jsx medmap-web/src/components/QuestionPanel.test.jsx \
  medmap-web/src/components/AppHeader.jsx medmap-web/src/components/AppHeader.test.jsx \
  medmap-web/src/lib/candidates.js medmap-web/src/lib/candidates.test.js \
  medmap-web/src/screens/StartScreen.jsx medmap-web/src/screens/StartScreen.test.jsx \
  medmap-web/src/screens/ConsultScreen.jsx medmap-web/src/screens/ConsultScreen.test.jsx \
  medmap-web/src/screens/SummaryScreen.jsx medmap-web/src/screens/SummaryScreen.test.jsx \
  medmap-web/src/a11y.test.jsx medmap-web/src/test/setup.js \
  medmap-web/src/test/fixtures/turn.start.json medmap-web/src/test/fixtures/turn.answer1.json \
  medmap-web/src/test/fixtures/turn.answer2.json medmap-web/src/test/fixtures/turn.answer3.json \
  medmap-web/scripts/record-fixtures.mjs
git reset -q   # 스테이징만 해제(작업 트리 파일은 유지) — 커밋은 Step 7에서 한 번에
```

- [ ] **Step 2: 의존성 설치(승인 불필요 조건 확인)**

```bash
cd ~/medmap-worktrees/natural-intake/medmap-web && npm ci --prefer-offline --no-audit --no-fund
git -C ~/medmap-worktrees/natural-intake diff --exit-code feat/web-ui -- medmap-web/package-lock.json && echo LOCK_UNCHANGED
```
`LOCK_UNCHANGED`가 아니거나 새 dependency가 생기면 중단하고 보고한다.

- [ ] **Step 3: `index.html` — CDN 폰트 제거**

`medmap-web/index.html`에서 다음 한 줄을 지운다(사용자 지시: 기본 typography):
```html
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable.min.css" />
```

- [ ] **Step 4: `src/main.jsx` — 스타일 import 교체**

```jsx
import './styles/plain.css'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```

- [ ] **Step 5: `src/styles/plain.css` 작성(기능 검증용 최소 스타일)**

```css
/* 기능 검증용 최소 스타일. 최종 디자인 아님(디자인 작업 PAUSED). */
* { box-sizing: border-box; }
body {
  margin: 0; background: #fff; color: #111;
  font-family: system-ui, -apple-system, 'Segoe UI', 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif;
  font-size: 16px; line-height: 1.5; word-break: keep-all;
}
.app { max-width: 720px; margin: 0 auto; padding: 16px; }
.app-header { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 8px;
  padding-bottom: 12px; margin-bottom: 16px; border-bottom: 1px solid #ddd; }
.app-header__brand { font-weight: 700; }
.app-header__progress, .app-header__dots { display: flex; align-items: center; gap: 6px; }
.progress-dot { width: 8px; height: 8px; border-radius: 50%; border: 1px solid #555; }
.progress-dot[data-filled="true"] { background: #555; }
.progress-dash { width: 8px; height: 1px; background: #999; }
.panel, .sheet { margin-bottom: 16px; }
h1 { font-size: 24px; margin: 0 0 12px; }
h2 { font-size: 18px; margin: 0 0 12px; }
.field { display: flex; flex-direction: column; gap: 4px; margin: 0 0 12px; padding: 0; border: 0; }
input, textarea { font: inherit; width: 100%; min-width: 0; padding: 10px; border: 1px solid #888; border-radius: 4px; }
.button { font: inherit; min-height: 44px; padding: 8px 14px; border: 1px solid #555; border-radius: 4px;
  background: #fff; color: #111; cursor: pointer; text-align: left; }
.button[aria-pressed="true"] { background: #111; color: #fff; }
.button--primary { background: #1a56db; border-color: #1a56db; color: #fff; text-align: center; }
.button:disabled { opacity: .5; cursor: not-allowed; }
.row { display: flex; flex-wrap: wrap; gap: 8px; }
.stack, .question__choices { display: flex; flex-direction: column; gap: 8px; }
.list { list-style: none; margin: 0 0 12px; padding: 0; display: flex; flex-direction: column; gap: 12px; }
.hint { margin: 4px 0; color: #555; font-size: 14px; }
.notice { margin-bottom: 16px; padding: 12px; border: 1px solid #b91c1c; }
.applied { margin: 0 0 16px; padding: 8px 12px; border-left: 3px solid #1a56db; }
.candidates__list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.candidate__head { display: flex; justify-content: space-between; gap: 8px; }
.candidate__track { height: 4px; background: #eee; }
.candidate__bar { height: 4px; background: #555; }
.candidate__ghost { color: #555; font-size: 14px; }
.candidate__ghost::before { content: '이전 '; }
.layout { display: grid; gap: 16px; }
@media (min-width: 900px) {
  .app { max-width: 1040px; }
  .layout { grid-template-columns: 1fr 320px; }
  .layout--single { grid-template-columns: 1fr; }
}
```

- [ ] **Step 6: `package.json` scripts 교체**

`"build:intake": "node scripts/build-intake-data.mjs"` 줄을 다음으로 바꾼다(의존성 블록은 손대지 않는다):
```json
    "sync:initial": "node scripts/sync-initial-catalog.mjs"
```
확인: `git -C ~/medmap-worktrees/natural-intake diff feat/web-ui -- medmap-web/package-lock.json` 출력 없음.

- [ ] **Step 7: 가져온 모듈 테스트(App 관련 제외)**

Run:
```bash
cd ~/medmap-worktrees/natural-intake/medmap-web && npx vitest run src/api src/session src/components src/lib src/screens src/a11y.test.jsx
```
Expected: PASS(App.jsx는 Task 9에서 작성 — 이 단계에서는 import하는 테스트가 없다)

- [ ] **Step 8: gitignore 함정 확인 + 커밋**

```bash
cd ~/medmap-worktrees/natural-intake && git add medmap-web && git status --porcelain medmap-web | grep -v '^A ' ; \
  find medmap-web/src medmap-web/scripts -type f | sort > /tmp/ni_fs.txt; git ls-files -co --exclude-standard medmap-web/src medmap-web/scripts | sort > /tmp/ni_git.txt; diff /tmp/ni_fs.txt /tmp/ni_git.txt && echo NO_IGNORED_SOURCE
git -c user.name=medmap -c user.email=<email> commit -m "Import functional web-ui logic from feat/web-ui (no V1 visuals) with plain test CSS

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```
Expected: `NO_IGNORED_SOURCE`(node_modules 제외, src/scripts 안에 무시되는 파일 0)

---

### Task 2: initial 96개 한국어 표시 라벨

**Files:**
- Create: `medmap/data/initial_evidence_ko.json`
- Test: `tests/test_initial_evidence_catalog.py`

**Interfaces:**
- Produces: JSON `{"schema":"medmap.initial_evidence_ko/1","source","note","frequent_ids":[8],"items":[{"evidence_id","train_rank","train_count","label_ko","detail_ko","detail_source"}×96]}` — `detail_source` ∈ `question_labels_ko`(기존 27개, `detail_ko` = `question_labels_ko.json` 문장 그대로) | `new_static_presentation`(신규 69개). items는 `train_rank` 오름차순.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_initial_evidence_catalog.py`:
```python
"""initial 96개 표시 라벨 무결성 — 매퍼 alias 가 아니라 표시·검색용 static presentation.

실행: ~/ai_env/bin/python -m unittest tests.test_initial_evidence_catalog
TRAIN 대조(670MB 읽기): MEDMAP_SLOW_TESTS=1 을 붙인다.
"""
import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from medmap import config
from medmap.intake import IntakeMapper

CATALOG = ROOT / "medmap" / "data" / "initial_evidence_ko.json"
LABELS = ROOT / "medmap" / "data" / "question_labels_ko.json"
KO27 = {"E_9", "E_33", "E_45", "E_50", "E_53", "E_66", "E_77", "E_88", "E_89", "E_91", "E_112", "E_129", "E_148",
        "E_151", "E_155", "E_169", "E_175", "E_181", "E_182", "E_194", "E_201", "E_212", "E_214", "E_216", "E_218",
        "E_220", "E_221"}
PAST_HISTORY_14 = {"E_0", "E_69", "E_70", "E_78", "E_79", "E_104", "E_105", "E_116", "E_120", "E_123", "E_124",
                   "E_189", "E_209", "E_226"}
BOOTSTRAP_ORDER = ["E_91", "E_53", "E_66", "E_201", "E_175", "E_88"]


class InitialCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(CATALOG.read_text(encoding="utf-8"))
        cls.items = cls.data["items"]
        cls.ids = [item["evidence_id"] for item in cls.items]
        cls.evidences = json.loads(config.check_path(config.EVIDENCES_JSON).read_text(encoding="utf-8"))
        cls.labels = json.loads(LABELS.read_text(encoding="utf-8"))["questions"]

    def test_01_exactly_96_unique(self):
        self.assertEqual(len(self.ids), 96)
        self.assertEqual(len(set(self.ids)), 96)

    def test_02_all_binary_and_not_excluded(self):
        for eid in self.ids:
            self.assertIn(eid, self.evidences, eid)
            self.assertEqual(self.evidences[eid]["data_type"], "B", eid)
            self.assertNotIn(eid, config.EXCLUDED_QUESTIONS)

    def test_03_rank_order_matches_counts(self):
        self.assertEqual([item["train_rank"] for item in self.items], list(range(1, 97)))
        counts = [item["train_count"] for item in self.items]
        self.assertEqual(counts, sorted(counts, reverse=True))
        self.assertEqual(sum(counts), 1025602)

    def test_04_ko27_reuse_existing_question_labels(self):
        reused = {item["evidence_id"] for item in self.items if item["detail_source"] == "question_labels_ko"}
        self.assertEqual(reused, KO27)
        for item in self.items:
            if item["detail_source"] == "question_labels_ko":
                self.assertEqual(item["detail_ko"], self.labels[item["evidence_id"]])
            else:
                self.assertEqual(item["detail_source"], "new_static_presentation")

    def test_05_mapper_overlap_is_ko27_and_no_past_history(self):
        self.assertEqual(IntakeMapper().supported & set(self.ids), KO27)
        self.assertFalse(PAST_HISTORY_14 & set(self.ids))

    def test_06_labels_nonempty_and_unique(self):
        labels = [item["label_ko"].strip() for item in self.items]
        self.assertTrue(all(labels))
        self.assertEqual(len(set(labels)), 96)
        self.assertTrue(all(item["detail_ko"].strip() for item in self.items))

    def test_07_frequent_ids_are_top8(self):
        self.assertEqual(self.data["frequent_ids"], self.ids[:8])

    def test_08_bootstrap_questions_have_korean_labels(self):
        for eid in BOOTSTRAP_ORDER:
            self.assertIn(eid, self.labels)
            self.assertEqual(self.evidences[eid]["data_type"], "B")

    @unittest.skipUnless(os.environ.get("MEDMAP_SLOW_TESTS") == "1", "TRAIN 전수 집계 — MEDMAP_SLOW_TESTS=1 일 때만")
    def test_09_matches_train_initial_evidence(self):
        import polars as pl
        path = config.check_path(config.DATA_DIR / "release_train_patients")
        counts = pl.scan_csv(path).select("INITIAL_EVIDENCE").collect()["INITIAL_EVIDENCE"].value_counts()
        self.assertEqual(dict(counts.iter_rows()), {item["evidence_id"]: item["train_count"] for item in self.items})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 실패 확인**

Run: `cd ~/medmap-worktrees/natural-intake && ~/ai_env/bin/python -m unittest tests.test_initial_evidence_catalog -v`
Expected: ERROR `FileNotFoundError … initial_evidence_ko.json`

- [ ] **Step 3: 라벨 확정본 복사 (human gate 통과 2026-09-25 — E_150·E_202·E_13 사용자 확정, 초안 SHA `15c89226…`)**

명확한 라벨은 초안 그대로 쓴다. 원문 뜻이 애매해 임의 번역이 필요한 ID만 표로 모아 중단하고 사용자에게 보인다. 사용자가 답한 문구로 초안을 고친 뒤 복사한다:
```bash
cd ~/medmap-worktrees/natural-intake && cp docs/superpowers/plans/2026-09-25-medmap-natural-intake.initial_evidence_ko.draft.json medmap/data/initial_evidence_ko.json
```
애매 판정(2026-09-25): `E_150`(원문은 "배출할 수 있었나" — 양성이 증상인지 정상인지 뜻이 뒤집힘), `E_202`(원문이 3인칭 "Does the person have a whooping cough?" — 진단명 백일해를 증상 라벨로 쓸지), `E_13`(원문이 두 조건 결합 — "2주간 악화"와 "더 적은 활동으로 유발"). 나머지 66개는 원문 뜻이 하나로 정해져 초안대로 진행한다(E_188만 "흰 변"→"색이 옅은 변" 직역으로 정정, 초안 SHA `465c3dcf…`).

- [ ] **Step 4: 통과 확인**

Run: `cd ~/medmap-worktrees/natural-intake && ~/ai_env/bin/python -m unittest tests.test_initial_evidence_catalog -v`
Expected: 8 PASS, 1 skipped
선택: `MEDMAP_SLOW_TESTS=1 timeout 110 ~/ai_env/bin/python -m unittest tests.test_initial_evidence_catalog.InitialCatalogTests.test_09_matches_train_initial_evidence` → PASS(2026-09-25 계획 작성 시 같은 집계를 1회 실측: 96개, 합 1,025,602)

- [ ] **Step 5: 커밋**

```bash
cd ~/medmap-worktrees/natural-intake && git add medmap/data/initial_evidence_ko.json tests/test_initial_evidence_catalog.py
git -c user.name=medmap -c user.email=<email> commit -m "Add Korean display labels for 96 initial evidences (presentation only, not mapper aliases)

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: `POST /v1/intake/extract`

**Files:**
- Modify: `medmap/api.py` (import 블록 · 상수 블록(34~42행 근처) · `EngineRegistry.__init__` · Request 모델 블록(117행 `ResumeRequest` 뒤) · Endpoints 끝)
- Test: `tests/test_intake_api.py`

**Interfaces:**
- Consumes: `medmap.intake.extract(text) -> list[dict(evidence_id,status,matched_text,source,confidence,alias_id)]`(frozen), `QuestionPresenter.present(eid).to_dict()["question_ko"]`, Task 2 JSON
- Produces: `POST /v1/intake/extract` 요청 `{"text": str(1..1000)}` → 200 `{"candidates":[{"evidence_id","status":"POSITIVE"|"NEGATIVE","label_ko","matched_text","initial_eligible":bool}],"mapper_version":"v1.2"}`; 형식 오류 422 `REQUEST_VALIDATION_ERROR`(원문 미포함)

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_intake_api.py`:
```python
"""/v1/intake/extract 계약 — 후보만 반환, 원문 저장·로그 금지, 기존 session API 무관.

실행: ~/ai_env/bin/python -m unittest tests.test_intake_api
"""
import logging
import sys
import unittest
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from medmap import api as api_module

CLIENT = TestClient(api_module.app)
KEYS = {"evidence_id", "status", "label_ko", "matched_text", "initial_eligible"}


def setUpModule():
    CLIENT.__enter__()


def tearDownModule():
    CLIENT.__exit__(None, None, None)


def extract(text):
    return CLIENT.post("/v1/intake/extract", json={"text": text})


class IntakeExtractTests(unittest.TestCase):
    def test_01_two_positive_candidates(self):
        response = extract("기침이 나고 열이 나요")
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(set(body), {"candidates", "mapper_version"})
        self.assertEqual(body["mapper_version"], "v1.2")
        got = [(c["evidence_id"], c["status"], c["matched_text"], c["initial_eligible"]) for c in body["candidates"]]
        self.assertEqual(got, [("E_201", "POSITIVE", "기침", True), ("E_91", "POSITIVE", "열", True)])
        self.assertEqual(body["candidates"][0]["label_ko"], "기침이 있나요?")
        for c in body["candidates"]:
            self.assertEqual(set(c), KEYS)          # confidence·alias_id·source 비노출

    def test_02_zero_candidates_is_normal(self):
        response = extract("그냥 몸이 좀 이상해요")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["candidates"], [])

    def test_03_negative_is_never_initial_eligible(self):
        body = extract("기침은 나는데 열은 없어요").json()
        got = [(c["evidence_id"], c["status"], c["initial_eligible"]) for c in body["candidates"]]
        self.assertEqual(got, [("E_201", "POSITIVE", True), ("E_91", "NEGATIVE", False)])

    def test_04_past_history_positive_is_not_initial_eligible(self):
        body = extract("기침이 나고 당뇨가 있어요").json()
        got = [(c["evidence_id"], c["status"], c["initial_eligible"]) for c in body["candidates"]]
        self.assertEqual(got, [("E_201", "POSITIVE", True), ("E_69", "POSITIVE", False)])

    def test_05_mention_order_preserved_for_many(self):
        body = extract("기침이 나고 열도 있고 숨이 차요. 가래도 누렇게 나오고 식은땀도 나요. 목소리도 쉬었어요.").json()
        self.assertEqual([c["evidence_id"] for c in body["candidates"]],
                         ["E_201", "E_91", "E_66", "E_77", "E_50", "E_212"])

    def test_06_validation_errors_do_not_echo_text(self):
        secret = "비밀문장가나다" * 150             # 1,050자 > 1,000
        response = extract(secret)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "REQUEST_VALIDATION_ERROR")
        self.assertNotIn("비밀문장", response.text)
        self.assertEqual(extract("").status_code, 422)
        extra = CLIENT.post("/v1/intake/extract", json={"text": "기침", "session": {}})
        self.assertEqual(extra.status_code, 422)

    def test_07_text_is_never_logged_even_with_payload_logging(self):
        marker = "로그금지표식문장 기침이 나요"
        previous = api_module.LOG_PAYLOAD
        api_module.LOG_PAYLOAD = True
        try:
            with self.assertLogs("medmap", level=logging.DEBUG) as captured:
                self.assertEqual(extract(marker).status_code, 200)
        finally:
            api_module.LOG_PAYLOAD = previous
        joined = "\n".join(record.getMessage() for record in captured.records)
        self.assertNotIn("로그금지표식", joined)
        self.assertNotIn("기침이 나요", joined)

    def test_08_response_has_no_session(self):
        body = extract("기침이 나요").json()
        self.assertNotIn("session", body)
        self.assertNotIn("text", body)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 실패 확인**

Run: `cd ~/medmap-worktrees/natural-intake && timeout 110 ~/ai_env/bin/python -m unittest tests.test_intake_api -v`
Expected: FAIL — 404(`/v1/intake/extract` 없음)

- [ ] **Step 3: 구현(추가만)**

`medmap/api.py` import 블록 끝(`from .serialization import …` 뒤)에 추가:
```python
import json
from pathlib import Path

from .intake import extract as intake_extract
```
상수 블록(`STOP_UNSUPPORTED_SESSION_SHAPE = …` 뒤)에 추가:
```python
# Natural Intake: frozen 매퍼 v1.2(freeze 2372e2f)를 감싸기만 한다. medmap/intake/ 는 수정하지 않는다.
MAPPER_VERSION = "v1.2"
INTAKE_TEXT_MAX_CHARS = 1000
INITIAL_CATALOG_JSON = Path(__file__).resolve().parent / "data" / "initial_evidence_ko.json"


def load_initial_ids(path=INITIAL_CATALOG_JSON) -> frozenset:
    """TRAIN INITIAL_EVIDENCE 고유값 96개(표시용 정적 파일). 런타임 추론·원본 데이터 접근 없음."""
    with open(path, encoding="utf-8") as f:
        return frozenset(item["evidence_id"] for item in json.load(f)["items"])
```
`EngineRegistry.__init__`의 `self.ready = True` 바로 위에 추가:
```python
        self.initial_ids = load_initial_ids()
```
`class ResumeRequest` 블록 뒤에 추가:
```python
class IntakeExtractRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=INTAKE_TEXT_MAX_CHARS)
```
파일 끝(`session_resume` 뒤)에 추가:
```python
@app.post(f"/{API_VERSION}/intake/extract")
def intake_extract_endpoint(body: IntakeExtractRequest) -> dict:
    """자유문장 → evidence 후보만. 원문은 저장·로그하지 않는다. PatientState·세션과 무관(stateless).

    후보는 사용자 확인 전까지 어떤 상태에도 들어가지 않는다. confidence·alias_id·source 는 내보내지 않는다.
    """
    registry = _registry()
    candidates = []
    for found in intake_extract(body.text):
        evidence_id, status = found["evidence_id"], found["status"]
        candidates.append({
            "evidence_id": evidence_id,
            "status": status,
            "label_ko": registry.presenter.present(evidence_id).to_dict()["question_ko"],
            "matched_text": found["matched_text"],
            "initial_eligible": status == "POSITIVE" and evidence_id in registry.initial_ids,
        })
    LOG.info("intake extract n_candidates=%d", len(candidates))       # 개수만. 원문·matched_text 미기록
    return {"candidates": candidates, "mapper_version": MAPPER_VERSION}
```

- [ ] **Step 4: 통과 + 기존 API 회귀**

Run: `cd ~/medmap-worktrees/natural-intake && timeout 110 ~/ai_env/bin/python -m unittest tests.test_intake_api tests.test_api -v 2>&1 | tail -5`
Expected: 전부 OK(시간이 110초를 넘으면 Task 0 Step 3처럼 nohup)
추가 확인: `git -C ~/medmap-worktrees/natural-intake diff --stat master -- medmap/intake` 출력 없음(매퍼 무변경)

- [ ] **Step 5: 커밋**

```bash
cd ~/medmap-worktrees/natural-intake && git add medmap/api.py tests/test_intake_api.py
git -c user.name=medmap -c user.email=<email> commit -m "Add POST /v1/intake/extract (candidates only, text never stored or logged)

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: 실제 엔진 end-to-end(백엔드) — A·B·C·E + D 서버 가드

**Files:**
- Test: `tests/test_natural_intake_e2e.py`

**Interfaces:**
- Consumes: Task 3 endpoint, 기존 `/v1/session/start`·`/answer`(무변경). 본문은 Task 5 `buildStartRequest`와 같은 규칙으로 손으로 조립한다(rev2 규칙: additional = initial 제외 확인 **POSITIVE** 발화순 앞 3개, 나머지 POSITIVE·모든 NEGATIVE = cache, bootstrap = `[E_91,E_53,E_66,E_201,E_175,E_88]`에서 initial·확인된 모든 항목 제외, known 답만 start에 넣음)

- [ ] **Step 1: 테스트 작성**

`tests/test_natural_intake_e2e.py`:
```python
"""Natural Intake end-to-end(실제 엔진): extract → 확인(테스트가 사용자 역할) → exact-k3 start → IG 질문.

실행: ~/ai_env/bin/python -m unittest tests.test_natural_intake_e2e
"""
import sys
import unittest
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from medmap import api as api_module

CLIENT = TestClient(api_module.app)
BOOTSTRAP = ["E_91", "E_53", "E_66", "E_201", "E_175", "E_88"]


def setUpModule():
    CLIENT.__enter__()


def tearDownModule():
    CLIENT.__exit__(None, None, None)


def candidates(text):
    response = CLIENT.post("/v1/intake/extract", json={"text": text})
    assert response.status_code == 200, response.text
    return response.json()["candidates"]


def plan(initial, confirmed):
    """rev2: additional = initial 제외 확인 POSITIVE 발화순 앞 3개. 나머지 POSITIVE·모든 NEGATIVE → cache.
    bootstrap 후보 = frozen 순서에서 initial·확인된 모든 항목을 뺀 것(부족분만큼 known 답이 필요)."""
    positives = [c for c in confirmed if c["evidence_id"] != initial and c["status"] == "POSITIVE"]
    additional = positives[:3]
    used = {c["evidence_id"] for c in additional}
    cached = [c for c in confirmed if c["evidence_id"] != initial and c["evidence_id"] not in used]
    taken = {initial, *(c["evidence_id"] for c in confirmed)}
    need = 3 - len(additional)
    boot = [e for e in BOOTSTRAP if e not in taken][:need]
    return additional, boot, cached


def start(initial, answers):
    body = {"age": 45, "sex": "M", "model_context": "k3", "initial_evidence": initial, "answers": answers}
    response = CLIENT.post("/v1/session/start", json=body)
    assert response.status_code == 200, response.text
    return response.json()


class NaturalIntakeEndToEnd(unittest.TestCase):
    def assert_ig_started(self, turn, submitted):
        self.assertIsNone(turn.get("stop_reason"))
        self.assertTrue(turn["model_context_match"])
        self.assertEqual(turn["questions_asked_in_session"], 0)
        self.assertIsNotNone(turn["next_question"])
        self.assertNotIn(turn["next_question"]["question_id"], submitted)

    def test_A_two_candidates_initial_one_bootstrap_two(self):
        found = candidates("기침이 나고 열이 나요")
        confirmed = [{"evidence_id": c["evidence_id"], "status": c["status"]} for c in found]
        self.assertEqual(len(confirmed), 2)
        additional, boot, cached = plan("E_201", confirmed)     # 사용자가 "기침"을 가장 불편한 증상으로 선택
        self.assertEqual([c["evidence_id"] for c in additional], ["E_91"])
        self.assertEqual(boot, ["E_53", "E_66"])
        self.assertEqual(cached, [])
        answers = [{"question_id": c["evidence_id"], "kind": c["status"], "value": None} for c in additional]
        answers += [{"question_id": "E_53", "kind": "NEGATIVE", "value": None},
                    {"question_id": "E_66", "kind": "POSITIVE", "value": None}]
        turn = start("E_201", answers)
        self.assert_ig_started(turn, {"E_201", "E_91", "E_53", "E_66"})

    def test_B_zero_candidates_manual_initial_bootstrap_three(self):
        self.assertEqual(candidates("그냥 몸이 좀 이상해요"), [])
        additional, boot, _ = plan("E_201", [])                 # 검색으로 "기침" 선택
        self.assertEqual(boot, ["E_91", "E_53", "E_66"])
        answers = [{"question_id": "E_91", "kind": "NEGATIVE", "value": None},     # known 답만(UNKNOWN 은 start 에 넣지 않음)
                   {"question_id": "E_53", "kind": "NEGATIVE", "value": None},
                   {"question_id": "E_66", "kind": "POSITIVE", "value": None}]
        turn = start("E_201", answers)
        self.assert_ig_started(turn, {"E_201", "E_91", "E_53", "E_66"})

    def test_C_and_D_many_candidates_cache_rest_and_server_guard(self):
        found = candidates("기침이 나고 열도 있고 숨이 차요. 가래도 누렇게 나오고 식은땀도 나요. 목소리도 쉬었어요.")
        confirmed = [{"evidence_id": c["evidence_id"], "status": c["status"]} for c in found]
        additional, boot, cached = plan("E_66", confirmed)      # "숨이 참" 선택
        self.assertEqual([c["evidence_id"] for c in additional], ["E_201", "E_91", "E_77"])
        self.assertEqual(boot, [])
        self.assertEqual([c["evidence_id"] for c in cached], ["E_50", "E_212"])
        answers = [{"question_id": c["evidence_id"], "kind": c["status"], "value": None} for c in additional]
        turn = start("E_66", answers)
        self.assert_ig_started(turn, {"E_66", "E_201", "E_91", "E_77"})
        # D(서버 측): 엔진이 제안하지 않은 cached evidence 를 미리 제출하면 409 로 막힌다.
        proposed = turn["next_question"]["question_id"]
        for entry in cached:
            submission = {"question_id": entry["evidence_id"], "answer": {"kind": entry["status"], "value": None}}
            response = CLIENT.post("/v1/session/answer", json={"session": turn["session"], "submission": submission})
            if entry["evidence_id"] == proposed:
                self.assertEqual(response.status_code, 200, response.text)
            else:
                self.assertEqual(response.status_code, 409)
                self.assertEqual(response.json()["error"]["code"], "MEDMAP_UNEXPECTED_ANSWER")

    def test_E_negative_candidate_goes_to_cache_not_start(self):
        found = candidates("기침은 나는데 열은 없어요")
        eligible = [c["evidence_id"] for c in found if c["initial_eligible"]]
        self.assertEqual(eligible, ["E_201"])                   # E_91 NEGATIVE 는 initial 후보 아님
        confirmed = [{"evidence_id": c["evidence_id"], "status": c["status"]} for c in found]
        additional, boot, cached = plan("E_201", confirmed)
        self.assertEqual(additional, [])                        # NEGATIVE 는 additional 에 넣지 않음(STEP17A 범위)
        self.assertEqual(cached, [{"evidence_id": "E_91", "status": "NEGATIVE"}])
        self.assertEqual(boot, ["E_53", "E_66", "E_175"])       # E_91(확인됨)·E_201(initial) 건너뛰고 예비 E_175
        answers = [{"question_id": "E_53", "kind": "POSITIVE", "value": None},
                   {"question_id": "E_66", "kind": "NEGATIVE", "value": None},
                   {"question_id": "E_175", "kind": "NEGATIVE", "value": None}]
        turn = start("E_201", answers)
        self.assert_ig_started(turn, {"E_201", "E_53", "E_66", "E_175"})
        # 확인된 NEGATIVE 는 엔진이 E_91 을 실제로 제안할 때만 적용된다(아니면 409).
        submission = {"question_id": "E_91", "answer": {"kind": "NEGATIVE", "value": None}}
        response = CLIENT.post("/v1/session/answer", json={"session": turn["session"], "submission": submission})
        expected = 200 if turn["next_question"]["question_id"] == "E_91" else 409
        self.assertEqual(response.status_code, expected, response.text)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 실행**

Run: `cd ~/medmap-worktrees/natural-intake && timeout 110 ~/ai_env/bin/python -m unittest tests.test_natural_intake_e2e -v`
Expected: 4 PASS(Task 3 완료 후이므로 바로 통과해야 한다. 실패하면 systematic-debugging — 규칙·기대값을 결과에 맞춰 바꾸지 않는다)

- [ ] **Step 3: 커밋**

```bash
cd ~/medmap-worktrees/natural-intake && git add tests/test_natural_intake_e2e.py
git -c user.name=medmap -c user.email=<email> commit -m "Add backend end-to-end tests: extract -> exact-k3 start -> IG question

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: 프론트 intake 규칙 모듈(catalog · startPlan · answerCache · client)

**Files:**
- Create: `medmap-web/scripts/sync-initial-catalog.mjs`, `medmap-web/src/intake/initialCatalog.json`(생성), `src/intake/catalog.js`, `src/intake/startPlan.js`, `src/intake/answerCache.js`
- Modify: `medmap-web/src/api/client.js`
- Test: `src/intake/catalog.test.js`, `src/intake/startPlan.test.js`, `src/intake/answerCache.test.js`, `src/api/client.test.js`(추가)

**Interfaces:**
- Produces:
  - `catalog.js`: `INITIAL_ITEMS: Item[]`, `INITIAL_IDS: Set<string>`, `FREQUENT_IDS: string[]`, `initialItem(id) -> Item|null`, `searchInitial(query, {exclude=[]}) -> Item[]`(최대 10, rank 순)
  - `startPlan.js`: `K=3`, `START_INCOMPLETE='START_INCOMPLETE'`, `BOOTSTRAP_PRIMARY`, `BOOTSTRAP_BACKUP`, `BOOTSTRAP_QUESTIONS_KO`, `initialOptions(confirmed) -> Confirmed[]`, `splitConfirmed(confirmed, initialId) -> {additional: POSITIVE만 ≤3, cached: 나머지 POSITIVE+모든 NEGATIVE}`, `bootstrapSequence(initialId, confirmed) -> string[]`, `bootstrapStep({initialId, confirmed, responses}) -> {status:'READY'} | {status:'ASK', questionId, remaining} | {status:'START_INCOMPLETE'}`, `buildStartRequest({age,sex,initialId,confirmed,bootstrapResponses}) -> {request:{age,sex,initialEvidence,answers}, cached:{evidence_id,status}[], unknownIds:string[]}`
  - `answerCache.js`: `CACHE_KEY='medmap.intakeCache'`, `sanitizeCache(entries)`, `saveCache(entries) -> entries`, `loadCache()`, `clearCache()`, `cachedAnswerFor(cache, question) -> {kind,value:null}|null`, `withoutEvidence(cache, id)`
  - `client.js`: `extractIntake(text) -> Promise<{candidates, mapper_version}>`
  - 타입: `Confirmed = {evidence_id, status:'POSITIVE'|'NEGATIVE'}`, `BootAnswer = {question_id, kind:'POSITIVE'|'NEGATIVE'|'UNKNOWN', value:null}`(UNKNOWN은 기록만, start 제외)

- [ ] **Step 1: 동기화 스크립트 작성·실행**

`medmap-web/scripts/sync-initial-catalog.mjs`:
```js
// initial 96개 표시 라벨을 Python 정본(medmap/data/initial_evidence_ko.json)에서 프론트로 복사한다.
// 폴더는 src/intake/ — 루트 .gitignore 의 data/ 규칙을 피한다(src/data 는 커밋되지 않는다).
import { copyFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
copyFileSync(resolve(here, '../../medmap/data/initial_evidence_ko.json'), resolve(here, '../src/intake/initialCatalog.json'))
console.log('synced src/intake/initialCatalog.json')
```
Run: `mkdir -p ~/medmap-worktrees/natural-intake/medmap-web/src/intake && cd ~/medmap-worktrees/natural-intake/medmap-web && npm run sync:initial`

- [ ] **Step 2: 실패하는 테스트 작성**

`src/intake/catalog.test.js`:
```js
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import catalogCopy from './initialCatalog.json'
import { FREQUENT_IDS, INITIAL_IDS, INITIAL_ITEMS, initialItem, searchInitial } from './catalog.js'

test('프론트 사본은 Python 정본과 같다', () => {
  const source = JSON.parse(readFileSync(fileURLToPath(new URL('../../../medmap/data/initial_evidence_ko.json', import.meta.url)), 'utf8'))
  expect(catalogCopy).toEqual(source)
})

test('initial 가능은 96개, 자주 쓰는 8개는 rank 상위 8개', () => {
  expect(INITIAL_ITEMS).toHaveLength(96)
  expect(INITIAL_IDS.size).toBe(96)
  expect(FREQUENT_IDS).toEqual(INITIAL_ITEMS.slice(0, 8).map((i) => i.evidence_id))
  expect(initialItem('E_201').label_ko).toBe('기침')
  expect(initialItem('E_69')).toBeNull()          // 과거력은 initial 불가
})

test('검색은 라벨·설명에서 공백 무시로 찾고 최대 10개, 제외 목록을 뺀다', () => {
  expect(searchInitial('').length).toBe(0)
  expect(searchInitial('어지').map((i) => i.evidence_id)).toEqual(expect.arrayContaining(['E_82', 'E_76']))
  expect(searchInitial('목 아픔').map((i) => i.evidence_id)).toContain('E_97')
  expect(searchInitial('통증').length).toBeLessThanOrEqual(10)
  expect(searchInitial('열', { exclude: ['E_91'] }).map((i) => i.evidence_id)).not.toContain('E_91')
})
```

`src/intake/startPlan.test.js`:
```js
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import {
  BOOTSTRAP_BACKUP, BOOTSTRAP_PRIMARY, BOOTSTRAP_QUESTIONS_KO, K, START_INCOMPLETE,
  bootstrapSequence, bootstrapStep, buildStartRequest, initialOptions, splitConfirmed,
} from './startPlan.js'

const pos = (id) => ({ evidence_id: id, status: 'POSITIVE' })
const neg = (id) => ({ evidence_id: id, status: 'NEGATIVE' })
const r = (id, kind) => ({ question_id: id, kind, value: null })

test('고정 bootstrap 순서는 STEP17A 그대로다', () => {
  expect(K).toBe(3)
  expect(BOOTSTRAP_PRIMARY).toEqual(['E_91', 'E_53', 'E_66'])
  expect(BOOTSTRAP_BACKUP).toEqual(['E_201', 'E_175', 'E_88'])
})

test('bootstrap 질문 문구는 엔진 한국어 라벨과 같다', () => {
  const labels = JSON.parse(readFileSync(fileURLToPath(new URL('../../../medmap/data/question_labels_ko.json', import.meta.url)), 'utf8')).questions
  for (const id of [...BOOTSTRAP_PRIMARY, ...BOOTSTRAP_BACKUP]) expect(BOOTSTRAP_QUESTIONS_KO[id]).toBe(labels[id])
})

test('initial 후보는 확인된 POSITIVE 중 96개에 속한 것만(NEGATIVE·과거력 제외)', () => {
  expect(initialOptions([pos('E_201'), neg('E_91'), pos('E_69')])).toEqual([pos('E_201')])
  expect(initialOptions([neg('E_91')])).toEqual([])
})

test('확인된 NEGATIVE 는 additional 에 들어가지 않고 cache 에 남는다', () => {
  const { additional, cached } = splitConfirmed([pos('E_201'), neg('E_91'), pos('E_77')], 'E_201')
  expect(additional).toEqual([pos('E_77')])
  expect(cached).toEqual([neg('E_91')])
})

test('POSITIVE 4개 이상이면 발화 순서 앞 3개가 additional, 나머지 POSITIVE·NEGATIVE 는 순서대로 cache', () => {
  const confirmed = [pos('E_201'), pos('E_91'), neg('E_214'), pos('E_66'), pos('E_77'), pos('E_50'), pos('E_212')]
  const { additional, cached } = splitConfirmed(confirmed, 'E_66')
  expect(additional.map((c) => c.evidence_id)).toEqual(['E_201', 'E_91', 'E_77'])
  expect(cached).toEqual([neg('E_214'), pos('E_50'), pos('E_212')])
})

test('bootstrap 후보는 initial 과 확인된 모든 항목(NEGATIVE 포함)을 건너뛴다', () => {
  expect(bootstrapSequence('E_201', [])).toEqual(['E_91', 'E_53', 'E_66', 'E_175', 'E_88'])
  expect(bootstrapSequence('E_201', [neg('E_91')])).toEqual(['E_53', 'E_66', 'E_175', 'E_88'])
  expect(bootstrapSequence('E_66', [pos('E_91'), pos('E_53')])).toEqual(['E_201', 'E_175', 'E_88'])
})

test.each([
  [[], { status: 'ASK', questionId: 'E_91', remaining: 3 }],                                   // POSITIVE additional 0 → 3
  [[pos('E_77')], { status: 'ASK', questionId: 'E_91', remaining: 2 }],                         // 1 → 2
  [[pos('E_77'), pos('E_214')], { status: 'ASK', questionId: 'E_91', remaining: 1 }],           // 2 → 1
  [[pos('E_77'), pos('E_214'), pos('E_50')], { status: 'READY' }],                              // 3 → 0
  [[neg('E_77'), neg('E_214'), neg('E_50')], { status: 'ASK', questionId: 'E_91', remaining: 3 }], // NEGATIVE 는 세지 않음
])('POSITIVE additional %# → bootstrap 부족분', (confirmed, expected) => {
  expect(bootstrapStep({ initialId: 'E_201', confirmed, responses: [] })).toEqual(expected)
})

test('bootstrap UNKNOWN 은 exact-k count 를 늘리지 않고 다음 backup 질문으로 간다', () => {
  const step = (responses) => bootstrapStep({ initialId: 'E_201', confirmed: [], responses })
  expect(step([r('E_91', 'UNKNOWN')])).toEqual({ status: 'ASK', questionId: 'E_53', remaining: 3 })
  expect(step([r('E_91', 'UNKNOWN'), r('E_53', 'NEGATIVE'), r('E_66', 'POSITIVE')]))
    .toEqual({ status: 'ASK', questionId: 'E_175', remaining: 1 })
  expect(step([r('E_91', 'UNKNOWN'), r('E_53', 'NEGATIVE'), r('E_66', 'POSITIVE'), r('E_175', 'NEGATIVE')]))
    .toEqual({ status: 'READY' })
})

test('남은 backup 으로 채울 수 없으면 START_INCOMPLETE', () => {
  expect(START_INCOMPLETE).toBe('START_INCOMPLETE')
  const none = (responses) => bootstrapStep({ initialId: 'E_201', confirmed: [], responses })
  expect(none([r('E_91', 'UNKNOWN'), r('E_53', 'UNKNOWN')])).toEqual({ status: 'ASK', questionId: 'E_66', remaining: 3 })
  expect(none([r('E_91', 'UNKNOWN'), r('E_53', 'UNKNOWN'), r('E_66', 'UNKNOWN')])).toEqual({ status: 'START_INCOMPLETE' })
  const two = [pos('E_77'), pos('E_50')]
  const unknowns = ['E_91', 'E_53', 'E_66', 'E_175'].map((id) => r(id, 'UNKNOWN'))
  expect(bootstrapStep({ initialId: 'E_201', confirmed: two, responses: unknowns })).toEqual({ status: 'ASK', questionId: 'E_88', remaining: 1 })
  expect(bootstrapStep({ initialId: 'E_201', confirmed: two, responses: [...unknowns, r('E_88', 'UNKNOWN')] }))
    .toEqual({ status: 'START_INCOMPLETE' })
})

test('POSITIVE confirmed + known bootstrap 만으로 정확히 k3 를 만든다(NEGATIVE·UNKNOWN 제외)', () => {
  const { request, cached, unknownIds } = buildStartRequest({
    age: 45, sex: 'M', initialId: 'E_201',
    confirmed: [pos('E_201'), neg('E_214'), pos('E_91')],
    bootstrapResponses: [r('E_53', 'UNKNOWN'), r('E_66', 'NEGATIVE'), r('E_175', 'POSITIVE')],
  })
  expect(request).toEqual({
    age: 45, sex: 'M', initialEvidence: 'E_201',
    answers: [
      { question_id: 'E_91', kind: 'POSITIVE', value: null },
      { question_id: 'E_66', kind: 'NEGATIVE', value: null },
      { question_id: 'E_175', kind: 'POSITIVE', value: null },
    ],
  })
  expect(cached).toEqual([neg('E_214')])
  expect(unknownIds).toEqual(['E_53'])
})

test('완성되지 않은 bootstrap 으로는 start 본문을 만들지 않는다', () => {
  expect(() => buildStartRequest({ age: 45, sex: 'M', initialId: 'E_201', confirmed: [], bootstrapResponses: [r('E_91', 'UNKNOWN')] }))
    .toThrow('START_INCOMPLETE')
})

test('NEGATIVE 확인 항목·96개 밖 항목은 initial 이 될 수 없다', () => {
  const known = (ids) => ids.map((id) => r(id, 'NEGATIVE'))
  expect(() => buildStartRequest({ age: 45, sex: 'M', initialId: 'E_91', confirmed: [neg('E_91')], bootstrapResponses: known(['E_53', 'E_66', 'E_201']) }))
    .toThrow('INITIAL_NOT_POSITIVE')
  expect(() => buildStartRequest({ age: 45, sex: 'M', initialId: 'E_69', confirmed: [], bootstrapResponses: known(['E_91', 'E_53', 'E_66']) }))
    .toThrow('INITIAL_NOT_ELIGIBLE')
})

test('bootstrap 응답 순서가 frozen 순서와 다르면 거부한다', () => {
  expect(() => buildStartRequest({ age: 45, sex: 'M', initialId: 'E_201', confirmed: [], bootstrapResponses: [r('E_66', 'NEGATIVE'), r('E_53', 'NEGATIVE'), r('E_91', 'NEGATIVE')] }))
    .toThrow('BOOTSTRAP_MISMATCH')
})
```

`src/intake/answerCache.test.js`:
```js
import { CACHE_KEY, cachedAnswerFor, clearCache, loadCache, sanitizeCache, saveCache, withoutEvidence } from './answerCache.js'

const yesNo = (id) => ({ question_id: id, answer_type: 'YES_NO' })
beforeEach(() => sessionStorage.clear())

test('cache 에는 evidence_id·status 만 남는다(원문·matched_text·label 제거)', () => {
  const clean = sanitizeCache([
    { evidence_id: 'E_50', status: 'POSITIVE', matched_text: '식은땀', label_ko: 'x', text: '원문' },
    { evidence_id: 'E_50', status: 'NEGATIVE' },            // 중복 → 첫 항목만
    { evidence_id: 'E_212', status: 'UNKNOWN' },             // 허용되지 않는 status
    { evidence_id: 'bad', status: 'POSITIVE' },
  ])
  expect(clean).toEqual([{ evidence_id: 'E_50', status: 'POSITIVE' }])
})

test('저장·복원·삭제', () => {
  saveCache([{ evidence_id: 'E_212', status: 'POSITIVE', matched_text: '목소리' }])
  expect(sessionStorage.getItem(CACHE_KEY)).toBe('[{"evidence_id":"E_212","status":"POSITIVE"}]')
  expect(loadCache()).toEqual([{ evidence_id: 'E_212', status: 'POSITIVE' }])
  saveCache([])
  expect(sessionStorage.getItem(CACHE_KEY)).toBeNull()
  saveCache([{ evidence_id: 'E_212', status: 'POSITIVE' }])
  clearCache()
  expect(loadCache()).toEqual([])
})

test('깨진 저장본은 빈 cache', () => {
  sessionStorage.setItem(CACHE_KEY, '{not json')
  expect(loadCache()).toEqual([])
})

test('엔진이 제안한 YES_NO 질문이 cache 에 있을 때만 답을 준다', () => {
  const cache = [{ evidence_id: 'E_50', status: 'POSITIVE' }]
  expect(cachedAnswerFor(cache, yesNo('E_50'))).toEqual({ kind: 'POSITIVE', value: null })
  expect(cachedAnswerFor(cache, yesNo('E_212'))).toBeNull()
  expect(cachedAnswerFor(cache, { question_id: 'E_50', answer_type: 'MULTI_CHOICE' })).toBeNull()
  expect(cachedAnswerFor(cache, null)).toBeNull()
  expect(withoutEvidence(cache, 'E_50')).toEqual([])
})
```

`src/api/client.test.js` 파일 끝에 추가:
```js
test('extractIntake 는 text 만 보낸다', async () => {
  const fetchMock = vi.fn(async () => ({ ok: true, status: 200, json: async () => ({ candidates: [], mapper_version: 'v1.2' }) }))
  vi.stubGlobal('fetch', fetchMock)
  const { extractIntake } = await import('./client.js')
  await expect(extractIntake('기침이 나요')).resolves.toEqual({ candidates: [], mapper_version: 'v1.2' })
  const [url, init] = fetchMock.mock.calls[0]
  expect(url).toBe('/v1/intake/extract')
  expect(JSON.parse(init.body)).toEqual({ text: '기침이 나요' })
})
```

- [ ] **Step 3: 실패 확인**

Run: `cd ~/medmap-worktrees/natural-intake/medmap-web && npx vitest run src/intake src/api`
Expected: FAIL — `catalog.js`/`startPlan.js`/`answerCache.js` 없음, `extractIntake` 없음

- [ ] **Step 4: 구현**

`src/intake/catalog.js`:
```js
// initial 96개 표시·검색용(매퍼 alias 아님). 정본: medmap/data/initial_evidence_ko.json
import catalog from './initialCatalog.json'

export const INITIAL_ITEMS = catalog.items
export const INITIAL_IDS = new Set(INITIAL_ITEMS.map((item) => item.evidence_id))
export const FREQUENT_IDS = catalog.frequent_ids
const BY_ID = new Map(INITIAL_ITEMS.map((item) => [item.evidence_id, item]))
const SEARCH_LIMIT = 10

export function initialItem(evidenceId) {
  return BY_ID.get(evidenceId) ?? null
}

const squash = (value) => value.replace(/\s+/g, '')

export function searchInitial(query, { exclude = [] } = {}) {
  const needle = squash(query ?? '')
  if (!needle) return []
  const blocked = new Set(exclude)
  return INITIAL_ITEMS
    .filter((item) => !blocked.has(item.evidence_id))
    .filter((item) => squash(item.label_ko).includes(needle) || squash(item.detail_ko).includes(needle))
    .slice(0, SEARCH_LIMIT)
}
```

`src/intake/startPlan.js`:
```js
// Natural Intake → exact-k3 시작 규칙(STEP17A GO 범위 그대로. 순서·예비 변경 금지).
// start feature = 확인된 POSITIVE(initial·additional) + bootstrap 의 known 답(POSITIVE/NEGATIVE)뿐.
// 확인된 NEGATIVE·초과 POSITIVE 는 cache, bootstrap UNKNOWN 은 기록만 하고 start 에 넣지 않는다.
import { INITIAL_IDS } from './catalog.js'

export const K = 3
export const START_INCOMPLETE = 'START_INCOMPLETE'
export const BOOTSTRAP_PRIMARY = Object.freeze(['E_91', 'E_53', 'E_66'])
export const BOOTSTRAP_BACKUP = Object.freeze(['E_201', 'E_175', 'E_88'])
export const BOOTSTRAP_QUESTIONS_KO = Object.freeze({
  E_91: '열이 있나요? (느낌으로든 체온계로 잰 것이든)',
  E_53: '이번에 진료를 받으려는 이유와 관련해서 어딘가 통증이 있나요?',
  E_66: '숨이 차거나 숨쉬기가 뚜렷하게 힘든가요?',
  E_201: '기침이 있나요?',
  E_175: '이번 진료와 관련해 새로 생긴 피로감, 막연한 불편감, 온몸이 쑤시는 근육통, 또는 전반적인 컨디션 변화가 있나요?',
  E_88: '너무 피곤해서 평소 하던 일을 못 하거나 하루 종일 누워 지내나요?',
})
const KNOWN = new Set(['POSITIVE', 'NEGATIVE'])

/** 확인된 항목 중 initial 이 될 수 있는 것: POSITIVE ∧ initial 96개. NEGATIVE·과거력은 제외. */
export function initialOptions(confirmed) {
  return confirmed.filter((c) => c.status === 'POSITIVE' && INITIAL_IDS.has(c.evidence_id))
}

/** additional = initial 제외 확인 POSITIVE 를 발화(매퍼 출력) 순서로 앞 K개. 나머지(초과 POSITIVE·모든 NEGATIVE)는 cache. */
export function splitConfirmed(confirmed, initialId) {
  const additional = confirmed.filter((c) => c.evidence_id !== initialId && c.status === 'POSITIVE').slice(0, K)
  const used = new Set(additional.map((c) => c.evidence_id))
  const cached = confirmed.filter((c) => c.evidence_id !== initialId && !used.has(c.evidence_id))
  return { additional, cached }
}

/** frozen 순서에서 initial 과 확인된 모든 항목(POSITIVE·NEGATIVE)을 뺀 bootstrap 후보. 같은 질문을 다시 묻지 않는다. */
export function bootstrapSequence(initialId, confirmed) {
  const taken = new Set([initialId, ...confirmed.map((c) => c.evidence_id)])
  return [...BOOTSTRAP_PRIMARY, ...BOOTSTRAP_BACKUP].filter((id) => !taken.has(id))
}

/**
 * 다음 할 일. responses = 지금까지 제시 순서대로의 bootstrap 응답(UNKNOWN 포함).
 * known 답이 부족분만큼 모이면 READY, 남은 질문을 모두 답해도 못 채우면 START_INCOMPLETE.
 */
export function bootstrapStep({ initialId, confirmed, responses }) {
  const { additional } = splitConfirmed(confirmed, initialId)
  const need = K - additional.length
  const known = responses.filter((response) => KNOWN.has(response.kind)).length
  if (known >= need) return { status: 'READY' }
  const left = bootstrapSequence(initialId, confirmed).slice(responses.length)
  if (known + left.length < need) return { status: START_INCOMPLETE }
  return { status: 'ASK', questionId: left[0], remaining: need - known }
}

export function buildStartRequest({ age, sex, initialId, confirmed, bootstrapResponses }) {
  if (!INITIAL_IDS.has(initialId)) throw new Error('INITIAL_NOT_ELIGIBLE')
  if (confirmed.some((c) => c.evidence_id === initialId && c.status !== 'POSITIVE')) throw new Error('INITIAL_NOT_POSITIVE')
  const sequence = bootstrapSequence(initialId, confirmed)
  if (bootstrapResponses.some((response, i) => response.question_id !== sequence[i])) throw new Error('BOOTSTRAP_MISMATCH')
  if (bootstrapStep({ initialId, confirmed, responses: bootstrapResponses }).status !== 'READY') throw new Error(START_INCOMPLETE)
  const { additional, cached } = splitConfirmed(confirmed, initialId)
  const answers = [
    ...additional.map((c) => ({ question_id: c.evidence_id, kind: 'POSITIVE', value: null })),
    ...bootstrapResponses.filter((response) => KNOWN.has(response.kind))
      .map((response) => ({ question_id: response.question_id, kind: response.kind, value: null })),
  ]
  if (answers.length !== K) throw new Error('EXACT_K_VIOLATION')
  return {
    request: { age, sex, initialEvidence: initialId, answers },
    cached: cached.map((c) => ({ evidence_id: c.evidence_id, status: c.status })),
    unknownIds: bootstrapResponses.filter((response) => response.kind === 'UNKNOWN').map((response) => response.question_id),
  }
}
```

`src/intake/answerCache.js`:
```js
// 확인했지만 start 에 넣지 못한 답. {evidence_id, status} 만 보관(원문·matched_text 금지).
// 엔진이 그 질문을 실제로 제안했을 때만 /session/answer 로 제출한다. posterior 는 건드리지 않는다.
export const CACHE_KEY = 'medmap.intakeCache'
const STATUSES = new Set(['POSITIVE', 'NEGATIVE'])
const EVIDENCE_ID = /^E_\d+$/

export function sanitizeCache(entries) {
  const seen = new Set()
  const clean = []
  for (const entry of Array.isArray(entries) ? entries : []) {
    if (!entry || !EVIDENCE_ID.test(entry.evidence_id) || !STATUSES.has(entry.status) || seen.has(entry.evidence_id)) continue
    seen.add(entry.evidence_id)
    clean.push({ evidence_id: entry.evidence_id, status: entry.status })
  }
  return clean
}

export function saveCache(entries) {
  const clean = sanitizeCache(entries)
  try {
    if (clean.length) sessionStorage.setItem(CACHE_KEY, JSON.stringify(clean))
    else sessionStorage.removeItem(CACHE_KEY)
  } catch { /* 저장 실패는 무시 — cache 는 보조 정보 */ }
  return clean
}

export function loadCache() {
  try {
    return sanitizeCache(JSON.parse(sessionStorage.getItem(CACHE_KEY) ?? '[]'))
  } catch {
    return []
  }
}

export function clearCache() {
  try { sessionStorage.removeItem(CACHE_KEY) } catch { /* 무시 */ }
}

export function cachedAnswerFor(cache, question) {
  if (!question || question.answer_type !== 'YES_NO') return null
  const hit = cache.find((entry) => entry.evidence_id === question.question_id)
  return hit ? { kind: hit.status, value: null } : null
}

export function withoutEvidence(cache, evidenceId) {
  return cache.filter((entry) => entry.evidence_id !== evidenceId)
}
```

`src/api/client.js` 끝에 추가:
```js
export function extractIntake(text) {
  return post('/v1/intake/extract', { text })
}
```

- [ ] **Step 5: 통과 확인**

Run: `cd ~/medmap-worktrees/natural-intake/medmap-web && npx vitest run src/intake src/api`
Expected: PASS

- [ ] **Step 6: 커밋**

```bash
cd ~/medmap-worktrees/natural-intake && git add medmap-web/scripts/sync-initial-catalog.mjs medmap-web/src/intake medmap-web/src/api/client.js medmap-web/src/api/client.test.js
git -c user.name=medmap -c user.email=<email> commit -m "Add intake start-plan rules (96 initial, fixed bootstrap, exact-k3) and answer cache

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: intake 컴포넌트 4개

**Files:**
- Create: `medmap-web/src/components/FreeTextInput.jsx`, `EvidenceConfirmation.jsx`, `InitialPicker.jsx`, `BootstrapQuestion.jsx`
- Test: 각 `*.test.jsx`

**Interfaces:**
- Consumes: Task 5 `FREQUENT_IDS, initialItem, searchInitial, BOOTSTRAP_QUESTIONS_KO`
- Produces:
  - `FreeTextInput({onSubmit({age,sex,text}), pending})` — `TEXT_MAX=1000` export
  - `EvidenceConfirmation({candidates, onConfirm(Confirmed[])})` — 전 후보 표시(접기 없음: 보지 않은 후보는 "확인"이 아니므로), 항목별 [있음][없음][빼기]
  - `InitialPicker({options: Item[], exclude: string[], onPick(id)})` — options ≥2면 그중 선택, 아니면 자주 쓰는 8개 + 검색
  - `BootstrapQuestion({evidenceId, remaining, onAnswer(BootAnswer), pending})` — `remaining` = 더 필요한 known 답 수

- [ ] **Step 1: 실패하는 테스트 작성**

`src/components/FreeTextInput.test.jsx`:
```jsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import FreeTextInput from './FreeTextInput'

test('나이·성별·문장이 모두 있어야 제출되고, 문장은 onSubmit 으로만 넘긴다', async () => {
  const user = userEvent.setup()
  const onSubmit = vi.fn()
  render(<FreeTextInput onSubmit={onSubmit} />)
  const submit = screen.getByRole('button', { name: '확인하기' })
  expect(submit).toBeDisabled()
  await user.type(screen.getByLabelText('나이'), '45')
  await user.click(screen.getByRole('button', { name: '남성' }))
  await user.type(screen.getByLabelText('지금 불편한 점을 편하게 적어 주세요'), '  기침이 나요 ')
  await user.click(submit)
  expect(onSubmit).toHaveBeenCalledWith({ age: 45, sex: 'M', text: '기침이 나요' })
})

test('입력 길이는 1000자로 제한된다', () => {
  render(<FreeTextInput onSubmit={() => {}} />)
  expect(screen.getByLabelText('지금 불편한 점을 편하게 적어 주세요')).toHaveAttribute('maxLength', '1000')
})
```

`src/components/EvidenceConfirmation.test.jsx`:
```jsx
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import EvidenceConfirmation from './EvidenceConfirmation'

const candidates = [
  { evidence_id: 'E_201', status: 'POSITIVE', label_ko: '기침이 있나요?', matched_text: '기침', initial_eligible: true },
  { evidence_id: 'E_91', status: 'NEGATIVE', label_ko: '열이 있나요? (느낌으로든 체온계로 잰 것이든)', matched_text: '열은 없어요', initial_eligible: false },
  { evidence_id: 'E_77', status: 'POSITIVE', label_ko: '가래?', matched_text: '가래도 누렇', initial_eligible: true },
]

test('매퍼 상태가 기본 선택이고, 확인한 것만 넘긴다(빼기 제외, 변경 반영)', async () => {
  const user = userEvent.setup()
  const onConfirm = vi.fn()
  render(<EvidenceConfirmation candidates={candidates} onConfirm={onConfirm} />)
  expect(screen.getByText('말씀하신 내용에서 다음 항목을 확인했어요')).toBeInTheDocument()
  const items = screen.getAllByTestId('confirm-item')
  expect(items).toHaveLength(3)
  expect(within(items[0]).getByRole('button', { name: '있음' })).toHaveAttribute('aria-pressed', 'true')
  expect(within(items[1]).getByRole('button', { name: '없음' })).toHaveAttribute('aria-pressed', 'true')
  await user.click(within(items[0]).getByRole('button', { name: '없음' }))
  await user.click(within(items[2]).getByRole('button', { name: '빼기' }))
  await user.click(screen.getByRole('button', { name: '다음' }))
  expect(onConfirm).toHaveBeenCalledWith([
    { evidence_id: 'E_201', status: 'NEGATIVE' },
    { evidence_id: 'E_91', status: 'NEGATIVE' },
  ])
})

test('신뢰도·내부 코드는 보이지 않는다', () => {
  render(<EvidenceConfirmation candidates={candidates} onConfirm={() => {}} />)
  expect(document.body.textContent).not.toMatch(/HIGH|confidence|E_\d+|MEDMAP_/)
})
```

`src/components/InitialPicker.test.jsx`:
```jsx
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import InitialPicker from './InitialPicker'
import { initialItem } from '../intake/catalog.js'

test('여러 POSITIVE 중 가장 불편한 것 하나를 고른다', async () => {
  const user = userEvent.setup()
  const onPick = vi.fn()
  render(<InitialPicker options={['E_201', 'E_91'].map(initialItem)} onPick={onPick} />)
  expect(screen.getByText('이 중 지금 가장 불편한 증상은 무엇인가요?')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: '열' }))
  expect(onPick).toHaveBeenCalledWith('E_91')
})

test('후보가 없으면 자주 쓰는 8개 + 검색, 96개를 전부 펼치지 않는다', async () => {
  const user = userEvent.setup()
  const onPick = vi.fn()
  render(<InitialPicker options={[]} exclude={[]} onPick={onPick} />)
  expect(within(screen.getByTestId('initial-frequent')).getAllByRole('button')).toHaveLength(8)
  expect(screen.getAllByRole('button').length).toBeLessThan(20)
  await user.type(screen.getByLabelText('증상 찾기'), '목 아픔')
  await user.click(within(screen.getByTestId('initial-results')).getByRole('button', { name: '목 아픔' }))
  expect(onPick).toHaveBeenCalledWith('E_97')
})

test('확인된 항목(NEGATIVE 포함)은 선택지에서 빠진다', async () => {
  const user = userEvent.setup()
  render(<InitialPicker options={[]} exclude={['E_91']} onPick={() => {}} />)
  expect(within(screen.getByTestId('initial-frequent')).queryByRole('button', { name: '열' })).toBeNull()
  await user.type(screen.getByLabelText('증상 찾기'), '열')
  expect(within(screen.getByTestId('initial-results')).queryByRole('button', { name: '열' })).toBeNull()
})

test('검색 결과가 없으면 안내만 하고 종료하지 않는다', async () => {
  const user = userEvent.setup()
  render(<InitialPicker options={[]} exclude={[]} onPick={() => {}} />)
  await user.type(screen.getByLabelText('증상 찾기'), '존재하지않는증상')
  expect(screen.getByText('찾는 증상이 없어요. 다른 말로 찾아보세요.')).toBeInTheDocument()
  expect(document.body.textContent).not.toMatch(/범위 밖|지원하지 않/)
})
```

`src/components/BootstrapQuestion.test.jsx`:
```jsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import BootstrapQuestion from './BootstrapQuestion'

test('한 번에 한 문항, 있음/없음/잘 모르겠어요', async () => {
  const user = userEvent.setup()
  const onAnswer = vi.fn()
  render(<BootstrapQuestion evidenceId="E_53" remaining={2} onAnswer={onAnswer} />)
  expect(screen.getByTestId('bootstrap-question')).toHaveTextContent('이번에 진료를 받으려는 이유와 관련해서 어딘가 통증이 있나요?')
  expect(screen.getByText('시작 전에 2가지만 더 확인할게요')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: '잘 모르겠어요' }))
  expect(onAnswer).toHaveBeenCalledWith({ question_id: 'E_53', kind: 'UNKNOWN', value: null })
})
```

- [ ] **Step 2: 실패 확인**

Run: `cd ~/medmap-worktrees/natural-intake/medmap-web && npx vitest run src/components`
Expected: FAIL — 새 컴포넌트 import 실패(기존 컴포넌트 테스트는 PASS)

- [ ] **Step 3: 구현**

`src/components/FreeTextInput.jsx`:
```jsx
import { useState } from 'react'

export const TEXT_MAX = 1000

// 입력 문장은 이 컴포넌트 안에만 있고, 제출 시 onSubmit 으로만 넘긴다(상위에서 보관·저장하지 않음).
export default function FreeTextInput({ onSubmit, pending = false }) {
  const [age, setAge] = useState('')
  const [sex, setSex] = useState('')
  const [text, setText] = useState('')
  const ageNumber = Number(age)
  const ready = age !== '' && ageNumber >= 0 && ageNumber <= 130 && (sex === 'M' || sex === 'F') && text.trim().length > 0

  function submit(event) {
    event.preventDefault()
    if (!ready || pending) return
    onSubmit({ age: ageNumber, sex, text: text.trim() })
  }

  return (
    <form className="panel" onSubmit={submit}>
      <label className="field">
        <span>나이</span>
        <input inputMode="numeric" value={age} onChange={(e) => setAge(e.target.value.replace(/\D/g, '').slice(0, 3))} />
      </label>
      <fieldset className="field">
        <legend>성별</legend>
        <div className="row">
          {[['M', '남성'], ['F', '여성']].map(([code, label]) => (
            <button key={code} type="button" className="button" aria-pressed={sex === code} onClick={() => setSex(code)}>
              {label}
            </button>
          ))}
        </div>
      </fieldset>
      <label className="field">
        <span>지금 불편한 점을 편하게 적어 주세요</span>
        <textarea
          rows={4}
          maxLength={TEXT_MAX}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="예: 사흘 전부터 기침이 나고 열이 있어요"
        />
      </label>
      <button type="submit" className="button button--primary" disabled={!ready || pending}>확인하기</button>
    </form>
  )
}
```

`src/components/EvidenceConfirmation.jsx`:
```jsx
import { useState } from 'react'

const OPTIONS = [
  ['POSITIVE', '있음'],
  ['NEGATIVE', '없음'],
  ['REMOVE', '빼기'],
]

// 매퍼 후보를 사용자가 확인한다. 보지 않은 후보는 확인된 것이 아니므로 접지 않고 전부 보여준다.
// 후보를 추가하지는 않는다(빠진 정보는 bootstrap 질문이 채운다).
export default function EvidenceConfirmation({ candidates, onConfirm }) {
  const [decisions, setDecisions] = useState(() => Object.fromEntries(candidates.map((c) => [c.evidence_id, c.status])))

  function confirm() {
    onConfirm(candidates
      .filter((c) => decisions[c.evidence_id] !== 'REMOVE')
      .map((c) => ({ evidence_id: c.evidence_id, status: decisions[c.evidence_id] })))
  }

  return (
    <section className="panel">
      <h2>말씀하신 내용에서 다음 항목을 확인했어요</h2>
      <p className="hint">맞는지 확인해 주세요. 틀린 항목은 바꾸거나 빼 주세요.</p>
      <ul className="list">
        {candidates.map((c) => (
          <li key={c.evidence_id} data-testid="confirm-item">
            <p>{c.label_ko}</p>
            <p className="hint">{`“${c.matched_text}”`}</p>
            <div className="row" role="group" aria-label={c.label_ko}>
              {OPTIONS.map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  className="button"
                  aria-pressed={decisions[c.evidence_id] === value}
                  onClick={() => setDecisions((prev) => ({ ...prev, [c.evidence_id]: value }))}
                >
                  {label}
                </button>
              ))}
            </div>
          </li>
        ))}
      </ul>
      <button type="button" className="button button--primary" onClick={confirm}>다음</button>
    </section>
  )
}
```

`src/components/InitialPicker.jsx`:
```jsx
import { useState } from 'react'
import { FREQUENT_IDS, initialItem, searchInitial } from '../intake/catalog.js'

export default function InitialPicker({ options = [], exclude = [], onPick }) {
  const [query, setQuery] = useState('')

  if (options.length >= 2) {
    return (
      <section className="panel">
        <h2>이 중 지금 가장 불편한 증상은 무엇인가요?</h2>
        <div className="stack">
          {options.map((item) => (
            <button key={item.evidence_id} type="button" className="button" onClick={() => onPick(item.evidence_id)}>
              {item.label_ko}
            </button>
          ))}
        </div>
      </section>
    )
  }

  const blocked = new Set(exclude)
  const frequent = FREQUENT_IDS.filter((id) => !blocked.has(id)).map(initialItem)
  const results = searchInitial(query, { exclude })

  return (
    <section className="panel">
      <h2>지금 가장 불편한 증상 하나를 골라 주세요</h2>
      <div className="row" data-testid="initial-frequent">
        {frequent.map((item) => (
          <button key={item.evidence_id} type="button" className="button" onClick={() => onPick(item.evidence_id)}>
            {item.label_ko}
          </button>
        ))}
      </div>
      <label className="field">
        <span>증상 찾기</span>
        <input type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="예: 어지러움, 목 아픔" />
      </label>
      {query.trim() && results.length === 0 && <p className="hint">찾는 증상이 없어요. 다른 말로 찾아보세요.</p>}
      <ul className="list" data-testid="initial-results">
        {results.map((item) => (
          <li key={item.evidence_id}>
            <button type="button" className="button" onClick={() => onPick(item.evidence_id)}>{item.label_ko}</button>
            <p className="hint">{item.detail_ko}</p>
          </li>
        ))}
      </ul>
    </section>
  )
}
```

`src/components/BootstrapQuestion.jsx`:
```jsx
import { BOOTSTRAP_QUESTIONS_KO } from '../intake/startPlan.js'

const CHOICES = [
  ['POSITIVE', '있음'],
  ['NEGATIVE', '없음'],
  ['UNKNOWN', '잘 모르겠어요'],
]

// remaining = 시작에 더 필요한 known 답 수. "잘 모르겠어요"는 이 수를 줄이지 않는다.
export default function BootstrapQuestion({ evidenceId, remaining, onAnswer, pending = false }) {
  return (
    <section className="panel">
      <p className="hint">{`시작 전에 ${remaining}가지만 더 확인할게요`}</p>
      <h2 data-testid="bootstrap-question">{BOOTSTRAP_QUESTIONS_KO[evidenceId]}</h2>
      <div className="stack">
        {CHOICES.map(([kind, label]) => (
          <button
            key={kind}
            type="button"
            className="button choice"
            disabled={pending}
            onClick={() => onAnswer({ question_id: evidenceId, kind, value: null })}
          >
            {label}
          </button>
        ))}
      </div>
    </section>
  )
}
```

- [ ] **Step 4: 통과 확인**

Run: `cd ~/medmap-worktrees/natural-intake/medmap-web && npx vitest run src/components`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
cd ~/medmap-worktrees/natural-intake && git add medmap-web/src/components
git -c user.name=medmap -c user.email=<email> commit -m "Add minimal intake components: free text, confirmation, initial picker, bootstrap question

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: NaturalIntakeScreen(단계 조립)

**Files:**
- Create: `medmap-web/src/screens/NaturalIntakeScreen.jsx`
- Test: `medmap-web/src/screens/NaturalIntakeScreen.test.jsx`

**Interfaces:**
- Consumes: Task 5·6 전부
- Produces: `NaturalIntakeScreen({onExtract(text) -> Promise<Candidate[]|null>, onStart(request, cached, intakeHistory), onRestart, pending})`, `NO_CANDIDATE_MESSAGE`·`START_INCOMPLETE_MESSAGE` export. 단계: `describe → (confirm | none) → [initial] → [bootstrap…] → starting | incomplete`. `intakeHistory = [{question, answer}]`(bootstrap 응답 전부, UNKNOWN 포함 — 사용자 응답 기록)

- [ ] **Step 1: 실패하는 테스트 작성**

`src/screens/NaturalIntakeScreen.test.jsx`:
```jsx
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import NaturalIntakeScreen, { NO_CANDIDATE_MESSAGE, START_INCOMPLETE_MESSAGE } from './NaturalIntakeScreen'

const c = (evidence_id, status, label_ko, matched_text, initial_eligible = status === 'POSITIVE') =>
  ({ evidence_id, status, label_ko, matched_text, initial_eligible })

async function describe(user, text) {
  await user.type(screen.getByLabelText('나이'), '45')
  await user.click(screen.getByRole('button', { name: '남성' }))
  await user.type(screen.getByLabelText('지금 불편한 점을 편하게 적어 주세요'), text)
  await user.click(screen.getByRole('button', { name: '확인하기' }))
}

const answerBoot = async (user, label) => user.click(screen.getByRole('button', { name: label }))

test('POSITIVE 1개면 자동 initial, 확인된 NEGATIVE 는 start 에 넣지 않고 cache 로, bootstrap 은 E_91 을 건너뛴다', async () => {
  const user = userEvent.setup()
  const onStart = vi.fn()
  const onExtract = vi.fn(async () => [c('E_201', 'POSITIVE', '기침이 있나요?', '기침'), c('E_91', 'NEGATIVE', '열이 있나요?', '열은 없어요')])
  render(<NaturalIntakeScreen onExtract={onExtract} onStart={onStart} onRestart={() => {}} />)
  await describe(user, '기침은 나는데 열은 없어요')
  expect(onExtract).toHaveBeenCalledWith('기침은 나는데 열은 없어요')
  expect(screen.queryByLabelText('지금 불편한 점을 편하게 적어 주세요')).toBeNull()   // 입력칸(원문) 사라짐
  await user.click(screen.getByRole('button', { name: '다음' }))
  expect(screen.queryByText('이 중 지금 가장 불편한 증상은 무엇인가요?')).toBeNull()
  expect(screen.getByTestId('bootstrap-question')).toHaveTextContent('통증이 있나요?')     // E_91 은 이미 확인됨 → E_53 부터
  await answerBoot(user, '없음')      // E_53
  await answerBoot(user, '있음')      // E_66
  await answerBoot(user, '없음')      // E_175(예비)
  const [request, cached, intakeHistory] = onStart.mock.calls[0]
  expect(request).toEqual({
    age: 45, sex: 'M', initialEvidence: 'E_201',
    answers: [
      { question_id: 'E_53', kind: 'NEGATIVE', value: null },
      { question_id: 'E_66', kind: 'POSITIVE', value: null },
      { question_id: 'E_175', kind: 'NEGATIVE', value: null },
    ],
  })
  expect(cached).toEqual([{ evidence_id: 'E_91', status: 'NEGATIVE' }])
  expect(intakeHistory.map((h) => h.answer)).toEqual(['없음', '있음', '없음'])
})

test('후보 0개: 안내 문구 → 검색으로 initial → bootstrap 3', async () => {
  const user = userEvent.setup()
  const onStart = vi.fn()
  render(<NaturalIntakeScreen onExtract={vi.fn(async () => [])} onStart={onStart} onRestart={() => {}} />)
  await describe(user, '그냥 몸이 좀 이상해요')
  expect(screen.getByText(NO_CANDIDATE_MESSAGE)).toBeInTheDocument()
  expect(document.body.textContent).not.toMatch(/증상이 없/)
  await user.click(screen.getByRole('button', { name: '가장 불편한 증상 고르기' }))
  await user.type(screen.getByLabelText('증상 찾기'), '기침')
  await user.click(within(screen.getByTestId('initial-results')).getByRole('button', { name: '기침' }))
  for (const expected of ['열이 있나요?', '통증이 있나요?', '숨이 차거나']) {
    expect(screen.getByTestId('bootstrap-question')).toHaveTextContent(expected)
    await answerBoot(user, '없음')
  }
  const [request, cached] = onStart.mock.calls[0]
  expect(request.initialEvidence).toBe('E_201')
  expect(request.answers.map((a) => a.question_id)).toEqual(['E_91', 'E_53', 'E_66'])
  expect(cached).toEqual([])
})

test('잘 모르겠어요는 개수에 넣지 않고 기록만 한 뒤 예비 질문으로 넘어간다', async () => {
  const user = userEvent.setup()
  const onStart = vi.fn()
  render(<NaturalIntakeScreen onExtract={vi.fn(async () => [])} onStart={onStart} onRestart={() => {}} />)
  await describe(user, '몸이 이상해요')
  await user.click(screen.getByRole('button', { name: '가장 불편한 증상 고르기' }))
  await user.click(within(screen.getByTestId('initial-frequent')).getByRole('button', { name: '기침' }))
  await answerBoot(user, '잘 모르겠어요')                       // E_91
  expect(screen.getByText('시작 전에 3가지만 더 확인할게요')).toBeInTheDocument()
  await answerBoot(user, '없음')                                // E_53
  await answerBoot(user, '없음')                                // E_66
  expect(screen.getByTestId('bootstrap-question')).toHaveTextContent('새로 생긴 피로감')   // E_175(예비)
  await answerBoot(user, '있음')
  const [request, , intakeHistory] = onStart.mock.calls[0]
  expect(request.answers).toEqual([
    { question_id: 'E_53', kind: 'NEGATIVE', value: null },
    { question_id: 'E_66', kind: 'NEGATIVE', value: null },
    { question_id: 'E_175', kind: 'POSITIVE', value: null },
  ])
  expect(intakeHistory[0]).toEqual({ question: '열이 있나요? (느낌으로든 체온계로 잰 것이든)', answer: '잘 모르겠어요' })
})

test('예비까지 써도 채울 수 없으면 START_INCOMPLETE — start 를 부르지 않는다', async () => {
  const user = userEvent.setup()
  const onStart = vi.fn()
  const onRestart = vi.fn()
  render(<NaturalIntakeScreen onExtract={vi.fn(async () => [])} onStart={onStart} onRestart={onRestart} />)
  await describe(user, '몸이 이상해요')
  await user.click(screen.getByRole('button', { name: '가장 불편한 증상 고르기' }))
  await user.click(within(screen.getByTestId('initial-frequent')).getByRole('button', { name: '기침' }))
  for (let i = 0; i < 3; i += 1) await answerBoot(user, '잘 모르겠어요')   // E_91·E_53·E_66 → 남은 2개로 3개 불가
  expect(screen.getByText(START_INCOMPLETE_MESSAGE)).toBeInTheDocument()
  expect(screen.queryByTestId('bootstrap-question')).toBeNull()
  expect(onStart).not.toHaveBeenCalled()
  await user.click(screen.getByRole('button', { name: '처음부터 다시' }))
  expect(onRestart).toHaveBeenCalled()
})

test('POSITIVE 여러 개 → 가장 불편한 것 선택, 4개 이상 → 앞 3개 + cache, bootstrap 없음', async () => {
  const user = userEvent.setup()
  const onStart = vi.fn()
  const found = [c('E_201', 'POSITIVE', '기침?', '기침'), c('E_91', 'POSITIVE', '열?', '열'), c('E_66', 'POSITIVE', '숨?', '숨이 차'),
    c('E_77', 'POSITIVE', '가래?', '가래도 누렇'), c('E_50', 'POSITIVE', '땀?', '식은땀'), c('E_212', 'POSITIVE', '목소리?', '목소리도 쉬었')]
  render(<NaturalIntakeScreen onExtract={vi.fn(async () => found)} onStart={onStart} onRestart={() => {}} />)
  await describe(user, '여러 증상')
  await user.click(screen.getByRole('button', { name: '다음' }))
  await user.click(screen.getByRole('button', { name: '숨이 참' }))
  expect(screen.queryByTestId('bootstrap-question')).toBeNull()
  const [request, cached] = onStart.mock.calls[0]
  expect(request.initialEvidence).toBe('E_66')
  expect(request.answers.map((a) => a.question_id)).toEqual(['E_201', 'E_91', 'E_77'])
  expect(cached).toEqual([{ evidence_id: 'E_50', status: 'POSITIVE' }, { evidence_id: 'E_212', status: 'POSITIVE' }])
})

test('추출 실패(null)면 입력 화면에 머문다', async () => {
  const user = userEvent.setup()
  render(<NaturalIntakeScreen onExtract={vi.fn(async () => null)} onStart={vi.fn()} onRestart={() => {}} />)
  await describe(user, '기침')
  expect(screen.getByLabelText('지금 불편한 점을 편하게 적어 주세요')).toHaveValue('기침')
})
```

- [ ] **Step 2: 실패 확인**

Run: `cd ~/medmap-worktrees/natural-intake/medmap-web && npx vitest run src/screens/NaturalIntakeScreen.test.jsx`
Expected: FAIL — 모듈 없음

- [ ] **Step 3: 구현**

`src/screens/NaturalIntakeScreen.jsx`:
```jsx
import { useState } from 'react'
import FreeTextInput from '../components/FreeTextInput.jsx'
import EvidenceConfirmation from '../components/EvidenceConfirmation.jsx'
import InitialPicker from '../components/InitialPicker.jsx'
import BootstrapQuestion from '../components/BootstrapQuestion.jsx'
import { initialItem } from '../intake/catalog.js'
import { BOOTSTRAP_QUESTIONS_KO, START_INCOMPLETE, bootstrapStep, buildStartRequest, initialOptions } from '../intake/startPlan.js'

export const NO_CANDIDATE_MESSAGE = '말씀하신 내용에서 확실하게 확인할 수 있는 항목을 찾지 못했어요.'
export const START_INCOMPLETE_MESSAGE = '시작에 필요한 확인이 부족해 진단을 시작하지 않았어요. 처음부터 다시 시도해 주세요.'
const ANSWER_LABEL = { POSITIVE: '있음', NEGATIVE: '없음', UNKNOWN: '잘 모르겠어요' }

// 자유 입력 → 확인 → initial → bootstrap → start. 원문은 onExtract 로 넘긴 뒤 어디에도 보관하지 않는다.
export default function NaturalIntakeScreen({ onExtract, onStart, onRestart, pending = false }) {
  const [step, setStep] = useState('describe')
  const [profile, setProfile] = useState(null)
  const [candidates, setCandidates] = useState([])
  const [confirmed, setConfirmed] = useState([])
  const [initialId, setInitialId] = useState(null)
  const [responses, setResponses] = useState([])
  const [asking, setAsking] = useState(null)
  const [extracting, setExtracting] = useState(false)

  async function describe({ age, sex, text }) {
    setExtracting(true)
    try {
      const found = await onExtract(text)
      if (found === null) return
      setProfile({ age, sex })
      setCandidates(found)
      setStep(found.length ? 'confirm' : 'none')
    } finally {
      setExtracting(false)
    }
  }

  function finish(id, list, answered) {
    const { request, cached } = buildStartRequest({ ...profile, initialId: id, confirmed: list, bootstrapResponses: answered })
    const intakeHistory = answered.map((r) => ({ question: BOOTSTRAP_QUESTIONS_KO[r.question_id], answer: ANSWER_LABEL[r.kind] }))
    setStep('starting')
    onStart(request, cached, intakeHistory)
  }

  function advance(id, list, answered) {
    const next = bootstrapStep({ initialId: id, confirmed: list, responses: answered })
    if (next.status === 'READY') finish(id, list, answered)
    else if (next.status === START_INCOMPLETE) setStep('incomplete')
    else {
      setAsking(next)
      setStep('bootstrap')
    }
  }

  function chooseInitial(id, list = confirmed) {
    setInitialId(id)
    setResponses([])
    advance(id, list, [])
  }

  function afterConfirm(list) {
    setConfirmed(list)
    const options = initialOptions(list)
    if (options.length === 1) chooseInitial(options[0].evidence_id, list)
    else setStep('initial')
  }

  function answerBootstrap(answer) {
    const answered = [...responses, answer]
    setResponses(answered)
    advance(initialId, confirmed, answered)
  }

  const options = initialOptions(confirmed).map((c) => initialItem(c.evidence_id))

  return (
    <main className="page">
      {step === 'describe' && <FreeTextInput onSubmit={describe} pending={extracting || pending} />}
      {step === 'confirm' && <EvidenceConfirmation candidates={candidates} onConfirm={afterConfirm} />}
      {step === 'none' && (
        <section className="panel">
          <p role="status">{NO_CANDIDATE_MESSAGE}</p>
          <button type="button" className="button button--primary" onClick={() => setStep('initial')}>
            가장 불편한 증상 고르기
          </button>
        </section>
      )}
      {step === 'initial' && (
        <InitialPicker options={options} exclude={confirmed.map((c) => c.evidence_id)} onPick={(id) => chooseInitial(id)} />
      )}
      {step === 'bootstrap' && asking && (
        <BootstrapQuestion
          key={asking.questionId}
          evidenceId={asking.questionId}
          remaining={asking.remaining}
          onAnswer={answerBootstrap}
          pending={pending}
        />
      )}
      {step === 'incomplete' && (
        <section className="panel">
          <p role="status">{START_INCOMPLETE_MESSAGE}</p>
          <button type="button" className="button" onClick={onRestart}>처음부터 다시</button>
        </section>
      )}
      {step === 'starting' && (
        <section className="panel">
          <p role="status">{pending ? '진단을 시작하고 있어요' : '시작하지 못했어요.'}</p>
          {!pending && <button type="button" className="button" onClick={onRestart}>처음부터 다시</button>}
        </section>
      )}
    </main>
  )
}
```
(`finish`는 `describe` 이후에만 호출되므로 `profile`은 항상 채워져 있다. `START_INCOMPLETE`이면 `onStart`를 부르지 않는다.)

- [ ] **Step 4: 통과 확인**

Run: `cd ~/medmap-worktrees/natural-intake/medmap-web && npx vitest run src/screens`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
cd ~/medmap-worktrees/natural-intake && git add medmap-web/src/screens/NaturalIntakeScreen.jsx medmap-web/src/screens/NaturalIntakeScreen.test.jsx
git -c user.name=medmap -c user.email=<email> commit -m "Add NaturalIntakeScreen flow: describe -> confirm -> initial -> bootstrap -> start

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: 세션 훅 — extract · cache 적용 · resume 충돌 처리

**Files:**
- Modify: `medmap-web/src/session/useMedmapSession.js`(전체 교체본 아래 — 기존 공개 API `phase, turn, health, error, pending, history, begin, start, answer, reset, retryHealth`와 `describeAnswer`는 그대로 유지)
- Test: `medmap-web/src/session/useMedmapSession.test.jsx`(기존 테스트 유지 + 추가)

**Interfaces:**
- Consumes: Task 5 `extractIntake`, `answerCache.*`
- Produces: 훅 반환에 `extract(text) -> Promise<Candidate[]|null>`, `autoApplied: {question, answer}[]` 추가, `start(intake, cache = [], intakeHistory = [])` — intakeHistory(bootstrap 응답, UNKNOWN 포함)로 요약 화면 history를 시작한다

- [ ] **Step 1: 실패하는 테스트 추가**

`src/session/useMedmapSession.test.jsx` 끝에 추가:
```jsx
const yesNoQuestion = (id) => ({
  question_id: id, question_text: id, question_ko: `${id} 질문`, question_original: id, answer_type: 'YES_NO', answer_type_raw: 'B',
  possible_values: [], information_gain: 0.5, explanation: null, is_fallback: false,
  choices: [
    { value: true, label: '예', original_label: null, is_fallback: false },
    { value: false, label: '아니요', original_label: null, is_fallback: false },
    { value: null, label: '잘 모르겠어요', original_label: null, is_fallback: false },
  ],
})
const turnAsking = (id, asked = 0) => ({ ...turnStart, next_question: yesNoQuestion(id), questions_asked_in_session: asked })

test('cache 는 start 성공 뒤에만 저장되고, 제안된 질문일 때만 자동 제출된다(D)', async () => {
  sessionStorage.clear()
  const api = fakeApi({
    startSession: vi.fn(async () => turnAsking('E_50')),
    submitAnswer: vi.fn(async () => ({ ...turnStart, questions_asked_in_session: 1 })),   // 다음 질문 E_54(MULTI) — cache 아님
  })
  const { result } = renderHook(() => useMedmapSession({ api }))
  act(() => result.current.begin())
  const cache = [{ evidence_id: 'E_50', status: 'POSITIVE' }, { evidence_id: 'E_212', status: 'POSITIVE' }]
  await act(async () => { await result.current.start({ age: 45, sex: 'M', initialEvidence: 'E_66', answers: [] }, cache) })
  expect(api.submitAnswer).toHaveBeenCalledTimes(1)
  expect(api.submitAnswer).toHaveBeenCalledWith({ session: turnStart.session, questionId: 'E_50', kind: 'POSITIVE', value: null })
  expect(result.current.autoApplied).toEqual([{ question: 'E_50 질문', answer: '예' }])
  expect(JSON.parse(sessionStorage.getItem('medmap.intakeCache'))).toEqual([{ evidence_id: 'E_212', status: 'POSITIVE' }])
  expect(result.current.turn.next_question.question_id).toBe(turnStart.next_question.question_id)
})

test('제안되지 않은 cached evidence 는 제출하지 않는다', async () => {
  sessionStorage.clear()
  const api = fakeApi()                                   // start → E_54(MULTI)
  const { result } = renderHook(() => useMedmapSession({ api }))
  await act(async () => { await result.current.start({ age: 45, sex: 'M', initialEvidence: 'E_66', answers: [] }, [{ evidence_id: 'E_50', status: 'POSITIVE' }]) })
  expect(api.submitAnswer).not.toHaveBeenCalled()
  expect(result.current.autoApplied).toEqual([])
})

test('자동 적용 중 실패하면 마지막 성공 턴을 유지하고 오류를 보인다(R7)', async () => {
  sessionStorage.clear()
  const failure = Object.assign(new Error('x'), { status: 500, code: 'INTERNAL_ERROR' })
  const api = fakeApi({
    startSession: vi.fn(async () => turnAsking('E_50')),
    submitAnswer: vi.fn()
      .mockResolvedValueOnce(turnAsking('E_212', 1))
      .mockRejectedValueOnce(failure),
  })
  const { result } = renderHook(() => useMedmapSession({ api }))
  await act(async () => {
    await result.current.start({ age: 45, sex: 'M', initialEvidence: 'E_66', answers: [] },
      [{ evidence_id: 'E_50', status: 'POSITIVE' }, { evidence_id: 'E_212', status: 'NEGATIVE' }])
  })
  expect(result.current.turn.next_question.question_id).toBe('E_212')
  expect(result.current.error).toBe(failure)
})

test('새로고침: 세션+cache 가 있으면 resume 후 제안된 질문만 적용한다(G, R3)', async () => {
  sessionStorage.clear()
  sessionStorage.setItem('medmap.session', JSON.stringify(turnStart.session))
  sessionStorage.setItem('medmap.intakeCache', JSON.stringify([{ evidence_id: 'E_50', status: 'NEGATIVE' }]))
  const api = fakeApi({
    resumeSession: vi.fn(async () => turnAsking('E_50', 1)),
    submitAnswer: vi.fn(async () => ({ ...turnStart, questions_asked_in_session: 2 })),
  })
  const { result } = renderHook(() => useMedmapSession({ api }))
  await waitFor(() => expect(api.submitAnswer).toHaveBeenCalledWith({ session: turnStart.session, questionId: 'E_50', kind: 'NEGATIVE', value: null }))
  await waitFor(() => expect(result.current.phase).toBe('consult'))
  expect(sessionStorage.getItem('medmap.intakeCache')).toBeNull()
})

test('세션 없이 cache 만 남아 있으면 지운다(R4)', async () => {
  sessionStorage.clear()
  sessionStorage.setItem('medmap.intakeCache', JSON.stringify([{ evidence_id: 'E_50', status: 'POSITIVE' }]))
  const api = fakeApi()
  renderHook(() => useMedmapSession({ api }))
  await waitFor(() => expect(sessionStorage.getItem('medmap.intakeCache')).toBeNull())
})

test('resume 실패와 reset 은 cache 도 지운다(R5, R6)', async () => {
  sessionStorage.clear()
  sessionStorage.setItem('medmap.session', JSON.stringify(turnStart.session))
  sessionStorage.setItem('medmap.intakeCache', JSON.stringify([{ evidence_id: 'E_50', status: 'POSITIVE' }]))
  const api = fakeApi({ resumeSession: vi.fn(async () => { throw Object.assign(new Error('bad'), { status: 409, code: 'MEDMAP_UNSUPPORTED_SESSION_SHAPE' }) }) })
  const { result } = renderHook(() => useMedmapSession({ api }))
  await waitFor(() => expect(sessionStorage.getItem('medmap.intakeCache')).toBeNull())
  await act(async () => { await result.current.start({ age: 45, sex: 'M', initialEvidence: 'E_66', answers: [] }, [{ evidence_id: 'E_9', status: 'POSITIVE' }]) })
  expect(sessionStorage.getItem('medmap.intakeCache')).not.toBeNull()
  act(() => result.current.reset())
  expect(sessionStorage.getItem('medmap.intakeCache')).toBeNull()
})

test('확인된 NEGATIVE cache 도 엔진이 실제로 제안했을 때만 NEGATIVE 로 제출된다', async () => {
  sessionStorage.clear()
  const api = fakeApi({
    startSession: vi.fn(async () => turnAsking('E_91')),
    submitAnswer: vi.fn(async () => ({ ...turnStart, questions_asked_in_session: 1 })),
  })
  const { result } = renderHook(() => useMedmapSession({ api }))
  const history = [{ question: '열이 있나요? (느낌으로든 체온계로 잰 것이든)', answer: '잘 모르겠어요' }]
  await act(async () => {
    await result.current.start({ age: 45, sex: 'M', initialEvidence: 'E_201', answers: [] }, [{ evidence_id: 'E_91', status: 'NEGATIVE' }], history)
  })
  expect(api.submitAnswer).toHaveBeenCalledWith({ session: turnStart.session, questionId: 'E_91', kind: 'NEGATIVE', value: null })
  expect(result.current.history[0]).toEqual(history[0])                // bootstrap 응답 기록 유지
  expect(result.current.history[1]).toEqual({ question: 'E_91 질문', answer: '아니요' })
})

test('extract 는 후보만 돌려주고 원문을 저장하지 않는다(F)', async () => {
  sessionStorage.clear()
  const api = fakeApi({ extractIntake: vi.fn(async () => ({ candidates: [{ evidence_id: 'E_201' }], mapper_version: 'v1.2' })) })
  const { result } = renderHook(() => useMedmapSession({ api }))
  let found
  await act(async () => { found = await result.current.extract('비밀 원문 기침') })
  expect(found).toEqual([{ evidence_id: 'E_201' }])
  expect(JSON.stringify({ ...sessionStorage })).not.toContain('비밀 원문')
})
```

- [ ] **Step 2: 실패 확인**

Run: `cd ~/medmap-worktrees/natural-intake/medmap-web && npx vitest run src/session`
Expected: 기존 테스트 PASS, 새 테스트 FAIL(`autoApplied`/`extract` 없음, cache 미처리)

- [ ] **Step 3: 구현 — `src/session/useMedmapSession.js` 교체본**

```js
import { useCallback, useEffect, useRef, useState } from 'react'
import * as defaultApi from '../api/client.js'
import { cachedAnswerFor, clearCache, loadCache, saveCache, withoutEvidence } from '../intake/answerCache.js'

const SESSION_KEY = 'medmap.session'

export function useMedmapSession({ api = defaultApi } = {}) {
  const [phase, setPhase] = useState('start')
  const [turn, setTurn] = useState(null)
  const [health, setHealth] = useState({ engine_ready: false, max_questions: 3 })
  const [error, setError] = useState(null)
  const [pending, setPending] = useState(false)
  const [history, setHistory] = useState([])
  const [autoApplied, setAutoApplied] = useState([])
  const cacheRef = useRef([])

  useEffect(() => {
    let alive = true
    api.getHealth()
      .then((value) => { if (alive) setHealth(value) })
      .catch((cause) => { if (alive) setError(cause) })
    return () => { alive = false }
  }, [api])


  const applyTurn = useCallback((next) => {
    setTurn(next)
    setPhase(next.next_question ? 'consult' : 'summary')
    try { sessionStorage.setItem(SESSION_KEY, JSON.stringify(next.session)) } catch { /* 저장 실패는 무시 */ }
  }, [])

  // 엔진이 방금 제안한 질문이 확인 cache 에 있을 때만 그 답을 /session/answer 로 제출한다.
  // 제안되지 않은 항목은 미리 제출하지 않고, posterior 는 건드리지 않는다. 적용도 질문 예산 1개를 쓴다.
  const settle = useCallback(async (first) => {
    let next = first
    const applied = []
    try {
      for (;;) {
        const hit = cachedAnswerFor(cacheRef.current, next.next_question)
        if (!hit) break
        const asked = next.next_question
        next = await api.submitAnswer({ session: next.session, questionId: asked.question_id, kind: hit.kind, value: null })
        cacheRef.current = saveCache(withoutEvidence(cacheRef.current, asked.question_id))
        applied.push({ question: asked.question_ko, answer: describeAnswer(asked, hit.kind, null) })
      }
      return { next, applied, failure: null }
    } catch (cause) {
      return { next, applied, failure: cause }     // 마지막으로 성공한 턴은 유지한다
    }
  }, [api])

  const finish = useCallback(({ next, applied, failure }) => {
    applyTurn(next)
    if (applied.length) setHistory((prev) => [...prev, ...applied])
    setAutoApplied(applied)
    if (failure) setError(failure)
  }, [applyTurn])

  // 새로고침 복귀: 저장된 세션이 있으면 서버에 복원을 요청한다(세션 source of truth 는 여전히 서버 응답).
  useEffect(() => {
    let alive = true
    let stored = null
    try { stored = sessionStorage.getItem(SESSION_KEY) } catch { stored = null }
    if (!stored) {
      clearCache()                    // 세션 없이 남은 cache 는 쓸 곳이 없다
      return undefined
    }
    let session
    try { session = JSON.parse(stored) } catch { session = null }
    if (!session) {
      try { sessionStorage.removeItem(SESSION_KEY) } catch { /* 무시 */ }
      clearCache()
      return undefined
    }
    api.resumeSession(session)
      .then(async (next) => {
        if (!alive) return
        cacheRef.current = loadCache()
        const result = await settle(next)
        if (alive) finish(result)
      })
      .catch((cause) => {
        // 더 이상 이어갈 수 없는 저장본은 조용히 버리고 시작 화면에 머문다(오류 문구로 놀래지 않는다).
        console.error('[medmap] resume failed', cause?.code ?? cause?.message)
        try { sessionStorage.removeItem(SESSION_KEY) } catch { /* 무시 */ }
        clearCache()
        cacheRef.current = []
      })
    return () => { alive = false }
  }, [api, settle, finish])

  const begin = useCallback(() => {
    setError(null)
    setPhase('intake')
  }, [])

  // 자유문장 → 후보. 원문은 요청에만 쓰고 어디에도 보관하지 않는다. 실패하면 null.
  const extract = useCallback(async (text) => {
    setPending(true)
    setError(null)
    try {
      const body = await api.extractIntake(text)
      return body.candidates
    } catch (cause) {
      setError(cause)
      return null
    } finally {
      setPending(false)
    }
  }, [api])

  const start = useCallback(async (intake, cache = [], intakeHistory = []) => {
    setPending(true)
    setError(null)
    try {
      const next = await api.startSession(intake)
      cacheRef.current = saveCache(cache)          // start 성공 뒤에만 저장
      setHistory(intakeHistory)                    // bootstrap 응답(잘 모르겠어요 포함)을 사용자 응답으로 기록
      finish(await settle(next))
    } catch (cause) {
      setError(cause)
    } finally {
      setPending(false)
    }
  }, [api, settle, finish])

  const answer = useCallback(async ({ kind, value }) => {
    if (!turn?.next_question) return
    const asked = turn.next_question
    setPending(true)
    setError(null)
    try {
      const next = await api.submitAnswer({ session: turn.session, questionId: asked.question_id, kind, value })
      setHistory((prev) => [...prev, { question: asked.question_ko, answer: describeAnswer(asked, kind, value) }])
      finish(await settle(next))
    } catch (cause) {
      setError(cause)
    } finally {
      setPending(false)
    }
  }, [api, settle, finish, turn])

  const reset = useCallback(() => {
    setTurn(null)
    setHistory([])
    setAutoApplied([])
    setError(null)
    setPhase('start')
    try { sessionStorage.removeItem(SESSION_KEY) } catch { /* 무시 */ }
    clearCache()
    cacheRef.current = []
  }, [])

  const retryHealth = useCallback(async () => {
    setError(null)
    try {
      setHealth(await api.getHealth())
    } catch (cause) {
      setError(cause)
    }
  }, [api])

  return { phase, turn, health, error, pending, history, autoApplied, begin, extract, start, answer, reset, retryHealth }
}

export function describeAnswer(question, kind, value) {
  if (kind === 'POSITIVE') return '예'
  if (kind === 'NEGATIVE') return '아니요'
  if (kind === 'UNKNOWN') return '잘 모르겠어요'
  const labels = (value ?? []).map((code) => question.choices.find((c) => c.value === code)?.label ?? code)
  return labels.join(', ')
}
```

- [ ] **Step 4: 통과 확인(기존 6개 + 신규 8개)**

Run: `cd ~/medmap-worktrees/natural-intake/medmap-web && npx vitest run src/session`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
cd ~/medmap-worktrees/natural-intake && git add medmap-web/src/session
git -c user.name=medmap -c user.email=<email> commit -m "Session hook: intake extract, cached answers applied only when proposed, resume/reset clear cache

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: App 연결 + 프론트 통합 테스트(A–G)

**Files:**
- Create: `medmap-web/src/App.jsx`, `medmap-web/src/App.test.jsx`, `medmap-web/src/integration.test.jsx`

**Interfaces:**
- Consumes: Task 7 `NaturalIntakeScreen`, Task 8 훅, Task 1 화면들

- [ ] **Step 1: 실패하는 테스트 작성**

`src/App.test.jsx`:
```jsx
import { render, screen, waitFor } from '@testing-library/react'
import App from './App'

beforeEach(() => {
  sessionStorage.clear()
  vi.stubGlobal('fetch', vi.fn(async () => ({
    ok: true, status: 200, json: async () => ({ status: 'ok', engine_ready: true, max_questions: 3 }),
  })))
})

test('앱이 헤더와 시작 화면을 렌더링한다', async () => {
  render(<App />)
  expect(document.querySelector('.app-header__brand')).toHaveTextContent('MedMap')
  await waitFor(() => expect(screen.getByRole('button', { name: '시작하기' })).toBeEnabled())
})
```

`src/integration.test.jsx`:
```jsx
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'
import turnStart from './test/fixtures/turn.start.json'

const HEALTH = { status: 'ok', engine_ready: true, max_questions: 3 }
const TYPED = '사흘 전부터 기침이 나고 열이 나요'
const c = (evidence_id, status, label_ko, matched_text, initial_eligible = status === 'POSITIVE') =>
  ({ evidence_id, status, label_ko, matched_text, initial_eligible })
const yesNo = (id) => ({
  question_id: id, question_text: id, question_ko: `${id} 질문`, question_original: id, answer_type: 'YES_NO', answer_type_raw: 'B',
  possible_values: [], information_gain: 0.5, explanation: null, is_fallback: false,
  choices: [{ value: true, label: '예', original_label: null, is_fallback: false },
    { value: false, label: '아니요', original_label: null, is_fallback: false },
    { value: null, label: '잘 모르겠어요', original_label: null, is_fallback: false }],
})
const asking = (question, asked = 0) => ({ ...turnStart, next_question: question, questions_asked_in_session: asked })

beforeEach(() => sessionStorage.clear())

function installRoutes(routes) {
  const calls = []
  vi.stubGlobal('fetch', vi.fn(async (url, init) => {
    const body = init?.body ? JSON.parse(init.body) : null
    calls.push({ url, body })
    const route = routes[url]
    const payload = url === '/health' ? HEALTH : (typeof route === 'function' ? route(body, calls) : route)
    return { ok: true, status: 200, json: async () => payload }
  }))
  return calls
}

async function describe(user, text) {
  await waitFor(() => expect(screen.getByRole('button', { name: '시작하기' })).toBeEnabled())
  await user.click(screen.getByRole('button', { name: '시작하기' }))
  await user.type(screen.getByLabelText('나이'), '45')
  await user.click(screen.getByRole('button', { name: '남성' }))
  await user.type(screen.getByLabelText('지금 불편한 점을 편하게 적어 주세요'), text)
  await user.click(screen.getByRole('button', { name: '확인하기' }))
}

const startCall = (calls) => calls.find((call) => call.url === '/v1/session/start')

test('A: 후보 2 → 확인 → initial 선택 → bootstrap 2 → start → IG 질문, 원문 미저장(F)', async () => {
  const user = userEvent.setup()
  const calls = installRoutes({
    '/v1/intake/extract': { candidates: [c('E_201', 'POSITIVE', '기침이 있나요?', '기침'), c('E_91', 'POSITIVE', '열이 있나요?', '열')], mapper_version: 'v1.2' },
    '/v1/session/start': turnStart,
  })
  render(<App />)
  await describe(user, TYPED)
  await user.click(await screen.findByRole('button', { name: '다음' }))
  await user.click(screen.getByRole('button', { name: '기침' }))
  await user.click(screen.getByRole('button', { name: '없음' }))
  await user.click(screen.getByRole('button', { name: '있음' }))
  await waitFor(() => expect(screen.getByText('추가로 확인할 정보')).toBeInTheDocument())
  expect(startCall(calls).body).toEqual({
    age: 45, sex: 'M', model_context: 'k3', initial_evidence: 'E_201',
    answers: [{ question_id: 'E_91', kind: 'POSITIVE', value: null },
      { question_id: 'E_53', kind: 'NEGATIVE', value: null },
      { question_id: 'E_66', kind: 'POSITIVE', value: null }],
  })
  // F: 원문은 extract 요청 본문에만
  expect(calls.filter((call) => JSON.stringify(call.body ?? {}).includes(TYPED)).map((call) => call.url)).toEqual(['/v1/intake/extract'])
  expect(JSON.stringify({ ...sessionStorage })).not.toContain(TYPED)
  expect(sessionStorage.getItem('medmap.intakeCache')).toBeNull()
  expect(document.body.textContent).not.toContain(TYPED)
})

test('B: 후보 0 → 안내 → 검색 initial → bootstrap 3 → start', async () => {
  const user = userEvent.setup()
  const calls = installRoutes({ '/v1/intake/extract': { candidates: [], mapper_version: 'v1.2' }, '/v1/session/start': turnStart })
  render(<App />)
  await describe(user, '그냥 몸이 좀 이상해요')
  expect(await screen.findByText('말씀하신 내용에서 확실하게 확인할 수 있는 항목을 찾지 못했어요.')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: '가장 불편한 증상 고르기' }))
  await user.type(screen.getByLabelText('증상 찾기'), '어지')
  await user.click(within(screen.getByTestId('initial-results')).getByRole('button', { name: '어지럽고 쓰러질 것 같음' }))
  for (let i = 0; i < 3; i += 1) await user.click(screen.getByRole('button', { name: '없음' }))
  await waitFor(() => expect(startCall(calls)).toBeDefined())
  expect(startCall(calls).body.initial_evidence).toBe('E_82')
  expect(startCall(calls).body.answers.map((a) => [a.question_id, a.kind]))
    .toEqual([['E_91', 'NEGATIVE'], ['E_53', 'NEGATIVE'], ['E_66', 'NEGATIVE']])
})

async function pickDizzy(user, calls) {
  await describe(user, '그냥 몸이 좀 이상해요')
  await user.click(await screen.findByRole('button', { name: '가장 불편한 증상 고르기' }))
  await user.type(screen.getByLabelText('증상 찾기'), '어지')
  await user.click(within(screen.getByTestId('initial-results')).getByRole('button', { name: '어지럽고 쓰러질 것 같음' }))
  return calls
}

test('B-UNKNOWN: 잘 모르겠어요는 start 에 넣지 않고 예비 질문으로 채운다, 응답은 요약 기록에 남는다', async () => {
  const user = userEvent.setup()
  const calls = installRoutes({
    '/v1/intake/extract': { candidates: [], mapper_version: 'v1.2' },
    '/v1/session/start': { ...turnStart, next_question: null, stop_reason: 'MAX_QUESTIONS', questions_asked_in_session: 3 },
  })
  render(<App />)
  await pickDizzy(user, calls)
  await user.click(screen.getByRole('button', { name: '잘 모르겠어요' }))    // E_91
  await user.click(screen.getByRole('button', { name: '없음' }))             // E_53
  await user.click(screen.getByRole('button', { name: '없음' }))             // E_66
  await user.click(screen.getByRole('button', { name: '있음' }))             // E_201(예비)
  await waitFor(() => expect(startCall(calls)).toBeDefined())
  expect(startCall(calls).body.answers.map((a) => [a.question_id, a.kind]))
    .toEqual([['E_53', 'NEGATIVE'], ['E_66', 'NEGATIVE'], ['E_201', 'POSITIVE']])
  expect(JSON.stringify(startCall(calls).body)).not.toContain('UNKNOWN')
  await waitFor(() => expect(screen.getByText('현재까지 확인된 정보')).toBeInTheDocument())
  expect(screen.getByText('열이 있나요? (느낌으로든 체온계로 잰 것이든)')).toBeInTheDocument()
  expect(screen.getAllByText('잘 모르겠어요').length).toBeGreaterThan(0)
})

test('B-INCOMPLETE: 예비까지 써도 3개를 못 채우면 start 를 호출하지 않는다', async () => {
  const user = userEvent.setup()
  const calls = installRoutes({ '/v1/intake/extract': { candidates: [], mapper_version: 'v1.2' }, '/v1/session/start': turnStart })
  render(<App />)
  await pickDizzy(user, calls)
  for (let i = 0; i < 4; i += 1) await user.click(screen.getByRole('button', { name: '잘 모르겠어요' }))   // 6개 중 4개 UNKNOWN → 남은 2개로 불가
  expect(screen.getByText('시작에 필요한 확인이 부족해 진단을 시작하지 않았어요. 처음부터 다시 시도해 주세요.')).toBeInTheDocument()
  expect(startCall(calls)).toBeUndefined()
  expect(sessionStorage.length).toBe(0)
})

const MANY = [c('E_201', 'POSITIVE', '기침?', '기침'), c('E_91', 'POSITIVE', '열?', '열'), c('E_66', 'POSITIVE', '숨?', '숨이 차'),
  c('E_77', 'POSITIVE', '가래?', '가래도 누렇'), c('E_50', 'POSITIVE', '땀?', '식은땀'), c('E_212', 'POSITIVE', '목소리?', '목소리도 쉬었')]

async function runMany(user) {
  await describe(user, '여러 증상이 있어요')
  await user.click(await screen.findByRole('button', { name: '다음' }))
  await user.click(screen.getByRole('button', { name: '숨이 참' }))
}

test('C: 후보 6 → initial → additional 3 → 나머지 cache, 제안 안 된 cache 는 제출 안 함', async () => {
  const user = userEvent.setup()
  const calls = installRoutes({ '/v1/intake/extract': { candidates: MANY, mapper_version: 'v1.2' }, '/v1/session/start': turnStart })
  render(<App />)
  await runMany(user)
  await waitFor(() => expect(screen.getByText('추가로 확인할 정보')).toBeInTheDocument())
  expect(startCall(calls).body.answers.map((a) => a.question_id)).toEqual(['E_201', 'E_91', 'E_77'])
  expect(JSON.parse(sessionStorage.getItem('medmap.intakeCache')))
    .toEqual([{ evidence_id: 'E_50', status: 'POSITIVE' }, { evidence_id: 'E_212', status: 'POSITIVE' }])
  expect(calls.some((call) => call.url === '/v1/session/answer')).toBe(false)
})

test('D: cached evidence 가 실제 IG 질문으로 나오면 그때만 적용하고 알린다', async () => {
  const user = userEvent.setup()
  const calls = installRoutes({
    '/v1/intake/extract': { candidates: MANY, mapper_version: 'v1.2' },
    '/v1/session/start': asking(yesNo('E_50')),
    '/v1/session/answer': asking(turnStart.next_question, 1),
  })
  render(<App />)
  await runMany(user)
  await waitFor(() => expect(screen.getByText(/앞서 말씀하신 내용을 반영했어요/)).toBeInTheDocument())
  const answers = calls.filter((call) => call.url === '/v1/session/answer')
  expect(answers).toHaveLength(1)
  expect(answers[0].body.submission).toEqual({ question_id: 'E_50', answer: { kind: 'POSITIVE', value: null } })
  expect(JSON.parse(sessionStorage.getItem('medmap.intakeCache'))).toEqual([{ evidence_id: 'E_212', status: 'POSITIVE' }])
  expect(screen.getByText('1 / 3')).toBeInTheDocument()     // 질문 예산 1 사용을 숨기지 않는다
})

test('E: NEGATIVE 후보는 initial·additional 로 쓰지 않고 cache 에만 남는다', async () => {
  const user = userEvent.setup()
  const calls = installRoutes({ '/v1/intake/extract': { candidates: [c('E_91', 'NEGATIVE', '열이 있나요?', '열은 없어요')], mapper_version: 'v1.2' }, '/v1/session/start': turnStart })
  render(<App />)
  await describe(user, '열은 없어요')
  await user.click(await screen.findByRole('button', { name: '다음' }))
  expect(within(screen.getByTestId('initial-frequent')).queryByRole('button', { name: '열' })).toBeNull()
  await user.click(within(screen.getByTestId('initial-frequent')).getByRole('button', { name: '기침' }))
  for (let i = 0; i < 3; i += 1) await user.click(screen.getByRole('button', { name: '없음' }))   // E_53·E_66·E_175
  await waitFor(() => expect(startCall(calls)).toBeDefined())
  expect(startCall(calls).body.initial_evidence).toBe('E_201')
  expect(startCall(calls).body.answers.map((a) => [a.question_id, a.kind]))
    .toEqual([['E_53', 'NEGATIVE'], ['E_66', 'NEGATIVE'], ['E_175', 'NEGATIVE']])
  expect(JSON.parse(sessionStorage.getItem('medmap.intakeCache'))).toEqual([{ evidence_id: 'E_91', status: 'NEGATIVE' }])
  expect(calls.some((call) => call.url === '/v1/session/answer')).toBe(false)     // 제안되지 않았으므로 미적용
})

test('D-NEGATIVE: 확인된 NEGATIVE 는 엔진이 그 질문을 실제로 제안할 때만 적용된다', async () => {
  const user = userEvent.setup()
  const calls = installRoutes({
    '/v1/intake/extract': { candidates: [c('E_201', 'POSITIVE', '기침이 있나요?', '기침'), c('E_91', 'NEGATIVE', '열이 있나요?', '열은 없어요')], mapper_version: 'v1.2' },
    '/v1/session/start': asking(yesNo('E_91')),
    '/v1/session/answer': asking(turnStart.next_question, 1),
  })
  render(<App />)
  await describe(user, '기침은 나는데 열은 없어요')
  await user.click(await screen.findByRole('button', { name: '다음' }))
  for (let i = 0; i < 3; i += 1) await user.click(screen.getByRole('button', { name: '없음' }))
  await waitFor(() => expect(screen.getByText(/앞서 말씀하신 내용을 반영했어요/)).toBeInTheDocument())
  expect(startCall(calls).body.answers.map((a) => a.question_id)).not.toContain('E_91')
  const answers = calls.filter((call) => call.url === '/v1/session/answer')
  expect(answers).toHaveLength(1)
  expect(answers[0].body.submission).toEqual({ question_id: 'E_91', answer: { kind: 'NEGATIVE', value: null } })
  expect(sessionStorage.getItem('medmap.intakeCache')).toBeNull()
})

test('G: 새로고침 — 세션+cache 는 resume 후 이어가고, intake 도중 새로고침은 아무것도 남기지 않는다', async () => {
  const user = userEvent.setup()
  sessionStorage.setItem('medmap.session', JSON.stringify(turnStart.session))
  sessionStorage.setItem('medmap.intakeCache', JSON.stringify([{ evidence_id: 'E_50', status: 'NEGATIVE' }]))
  const calls = installRoutes({ '/v1/session/resume': asking(yesNo('E_50'), 1), '/v1/session/answer': asking(turnStart.next_question, 2) })
  const first = render(<App />)
  await waitFor(() => expect(screen.getByText('추가로 확인할 정보')).toBeInTheDocument())
  expect(calls.find((call) => call.url === '/v1/session/answer').body.submission.question_id).toBe('E_50')
  first.unmount()

  sessionStorage.clear()
  installRoutes({ '/v1/intake/extract': { candidates: [], mapper_version: 'v1.2' } })
  render(<App />)
  await describe(user, '기침이 나요')
  expect(sessionStorage.length).toBe(0)                    // intake 단계는 저장하지 않는다(R1)
})
```

- [ ] **Step 2: 실패 확인**

Run: `cd ~/medmap-worktrees/natural-intake/medmap-web && npx vitest run src/App.test.jsx src/integration.test.jsx`
Expected: FAIL — `./App` 없음

- [ ] **Step 3: 구현 — `src/App.jsx`**

```jsx
import AppHeader from './components/AppHeader.jsx'
import StartScreen from './screens/StartScreen.jsx'
import NaturalIntakeScreen from './screens/NaturalIntakeScreen.jsx'
import ConsultScreen from './screens/ConsultScreen.jsx'
import SummaryScreen from './screens/SummaryScreen.jsx'
import Notice from './components/Notice.jsx'
import { userMessage } from './api/messages.js'
import { useMedmapSession } from './session/useMedmapSession.js'

export default function App() {
  const session = useMedmapSession()
  const step = session.turn?.questions_asked_in_session ?? 0
  const total = session.turn?.max_questions ?? session.health.max_questions ?? 3

  return (
    <div className="app">
      <AppHeader step={step} total={total} />
      {session.error && (
        <Notice message={userMessage(session.error)} onRetry={session.retryHealth} onRestart={session.reset} />
      )}
      {session.autoApplied.length > 0 && session.phase !== 'intake' && (
        <p className="applied" role="status">
          {`앞서 말씀하신 내용을 반영했어요: ${session.autoApplied.map((a) => `${a.question} — ${a.answer}`).join(', ')}`}
        </p>
      )}
      {session.phase === 'start' && (
        <StartScreen ready={session.health.engine_ready} checking={false} onStart={session.begin} />
      )}
      {session.phase === 'intake' && (
        <NaturalIntakeScreen
          onExtract={session.extract}
          onStart={session.start}
          onRestart={session.reset}
          pending={session.pending}
        />
      )}
      {session.phase === 'consult' && (
        <ConsultScreen turn={session.turn} onAnswer={session.answer} pending={session.pending} />
      )}
      {session.phase === 'summary' && (
        <SummaryScreen turn={session.turn} history={session.history} onRestart={session.reset} />
      )}
    </div>
  )
}
```

- [ ] **Step 4: 전체 프론트 회귀(H)**

Run: `cd ~/medmap-worktrees/natural-intake/medmap-web && npx vitest run && npm run build`
Expected: 전부 PASS, build 성공. 통과 수를 Task 0 Step 5 참고값과 함께 기록(IntakeScreen·responsive 테스트는 의도적으로 제외됐으므로 수가 다름을 명시)

- [ ] **Step 5: 커밋**

```bash
cd ~/medmap-worktrees/natural-intake && git add medmap-web/src/App.jsx medmap-web/src/App.test.jsx medmap-web/src/integration.test.jsx
git -c user.name=medmap -c user.email=<email> commit -m "Wire NaturalIntakeScreen into App with integration tests A-G

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: 실서버 end-to-end + 전체 회귀 + README

**Files:**
- Create: `medmap-web/e2e/natural-intake.e2e.mjs`, `medmap-web/README.md`
- 결과물(커밋하지 않음): `logs/ni_e2e_*.log`, `logs/ni_e2e_*.png`

- [ ] **Step 1: 실행 조건(rev2 — 승인 불필요)**

uvicorn(:8000)·vite(:5173) 로컬 기동과 Playwright 스크린샷은 가역적인 로컬 작업이라 승인 없이 진행한다. 외부 publish/upload 금지. 캐시된 Playwright(`~/.npm/_npx/9833c18b2d85bc59/node_modules/playwright`, 새 설치 없음), PNG는 `logs/`(gitignore)에만, API는 `ram_guard` 동반.

- [ ] **Step 2: e2e 스크립트 작성**

`medmap-web/e2e/natural-intake.e2e.mjs`:
```js
// 실서버 스모크: API(:8000) + vite(:5173) 가 떠 있어야 한다. 설치 없이 캐시된 playwright 를 쓴다.
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const { chromium } = require(process.env.PLAYWRIGHT_PATH ?? '~/.npm/_npx/9833c18b2d85bc59/node_modules/playwright')
const BASE = process.env.MEDMAP_WEB ?? 'http://127.0.0.1:5173'
const OUT = process.env.OUT_DIR ?? '../logs'

async function describe(page, text) {
  await page.getByRole('button', { name: '시작하기' }).click()
  await page.getByLabel('나이').fill('45')
  await page.getByRole('button', { name: '남성' }).click()
  await page.getByLabel('지금 불편한 점을 편하게 적어 주세요').fill(text)
  await page.getByRole('button', { name: '확인하기' }).click()
}

async function scenarioA(page) {
  await describe(page, '기침이 나고 열이 나요')
  await page.getByRole('button', { name: '다음' }).click()
  await page.getByRole('button', { name: '기침', exact: true }).click()
  await page.getByRole('button', { name: '없음' }).click()
  await page.getByRole('button', { name: '있음' }).click()
  await page.getByText('추가로 확인할 정보').waitFor()
}

async function scenarioB(page) {
  await describe(page, '그냥 몸이 좀 이상해요')
  await page.getByText('말씀하신 내용에서 확실하게 확인할 수 있는 항목을 찾지 못했어요.').waitFor()
  await page.getByRole('button', { name: '가장 불편한 증상 고르기' }).click()
  await page.getByTestId('initial-frequent').getByRole('button', { name: '기침' }).click()
  for (let i = 0; i < 3; i += 1) await page.getByRole('button', { name: '없음' }).click()
  await page.getByText('추가로 확인할 정보').waitFor()
}

const browser = await chromium.launch()
const results = []
for (const [name, run] of [['A', scenarioA], ['B', scenarioB]]) {
  for (const width of [390, 1280]) {
    const page = await browser.newPage({ viewport: { width, height: 900 } })
    const bodies = []
    page.on('request', (req) => { if (req.method() === 'POST') bodies.push({ url: req.url(), body: req.postData() }) })
    await page.goto(BASE)
    await run(page)
    const storage = await page.evaluate(() => JSON.stringify({ ...sessionStorage }))
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)
    await page.screenshot({ path: `${OUT}/ni_e2e_${name}_${width}.png`, fullPage: true })
    const textInStart = bodies.filter((b) => b.url.endsWith('/v1/session/start')).some((b) => b.body.includes('기침이 나고') || b.body.includes('이상해요'))
    results.push({ name, width, overflow, textInStart, storageHasText: storage.includes('기침이 나고') || storage.includes('이상해요') })
    await page.close()
  }
}
await browser.close()
console.log(JSON.stringify(results, null, 1))
if (results.some((r) => r.overflow || r.textInStart || r.storageHasText)) process.exit(1)
console.log('E2E_OK')
```

- [ ] **Step 3: (승인 후) 서버 기동 → e2e → 종료**

```bash
cd ~/medmap-worktrees/natural-intake && TS=$(date +%Y%m%d_%H%M)
nohup ~/ai_env/bin/python -m uvicorn medmap.api:app --host 127.0.0.1 --port 8000 > logs/ni_api_$TS.log 2>&1 &
API_PID=$!; echo "API PID: $API_PID"
nohup bash ~/scripts/ram_guard.sh "$API_PID" 90 60 logs/ram_guard_ni_$TS.log > /dev/null 2>&1 &
cd medmap-web && nohup npx vite --host 127.0.0.1 --port 5173 --strictPort > ../logs/ni_vite_$TS.log 2>&1 &
echo "VITE wrapper PID: $!"
```
준비 확인: `curl -s 127.0.0.1:8000/health`의 `"engine_ready":true`, `curl -s -o /dev/null -w '%{http_code}' 127.0.0.1:5173` = 200. 그 뒤:
```bash
cd ~/medmap-worktrees/natural-intake/medmap-web && node e2e/natural-intake.e2e.mjs 2>&1 | tee ../logs/ni_e2e_$(date +%Y%m%d_%H%M).log | tail -3
```
Expected: `E2E_OK`. PNG 4장을 Read로 직접 열어 390px에서 버튼·입력칸이 잘리지 않았는지 확인.
종료: `ps -eo pid,cmd | grep -E 'uvicorn medmap.api|vite --host' | grep -v grep`로 **실제 PID**를 확인해 `kill <PID>`(pkill -f 금지 — 메모리 pgrep-self-match).

- [ ] **Step 4: 전체 회귀(H)**

```bash
cd ~/medmap-worktrees/natural-intake && nohup ~/ai_env/bin/python -m unittest discover -s tests > logs/ni_final_backend_$(date +%Y%m%d_%H%M).log 2>&1 &
```
Expected: `Ran (N + 21) tests … OK (skipped=1)` — N은 Task 0 기준선, 증분 = catalog 9(1 skip) + intake_api 8 + e2e 4. 프론트: `cd medmap-web && npx vitest run` PASS.
매퍼 무변경 증명: `git -C ~/medmap-worktrees/natural-intake diff --stat master -- medmap/intake tests/fixtures` 출력 없음.
session API 무변경 증명: `git -C ~/medmap-worktrees/natural-intake diff master -- medmap/api.py | grep '^-' | grep -v '^---'` 출력 없음(추가만).

- [ ] **Step 5: README 작성**

`medmap-web/README.md`:
````markdown
# MedMap Web (Natural Intake 기능 검증 UI)

기능 검증용 최소 UI다. 최종 디자인이 아니다(디자인 작업 PAUSED, 2026-09-25).

## 실행

```bash
# API — 메인 체크아웃에서(모델 파일은 git 에 없음)
cd ~/medmap-worktrees/natural-intake && ~/ai_env/bin/python -m uvicorn medmap.api:app --host 127.0.0.1 --port 8000
# UI
cd ~/medmap-worktrees/natural-intake/medmap-web && npm ci && npm run dev   # http://127.0.0.1:5173
```

## 흐름

자유 텍스트 → `POST /v1/intake/extract`(후보만) → 사용자 확인(있음/없음/빼기) → initial 결정
→ 부족분 bootstrap(한 번에 한 문항) → `POST /v1/session/start`(initial 1 + 정확히 3) → 기존 IG 질문

- initial: 확인된 POSITIVE 중 initial 가능(96개) 1개면 그것, 2개 이상이면 "가장 불편한 증상" 선택, 0개면 자주 쓰는 8개 + 검색. NEGATIVE·과거력은 initial 불가.
- start feature는 확인된 POSITIVE와 bootstrap의 known 답(있음/없음)뿐이다(STEP17A 검증 범위).
- additional: initial 제외 확인 POSITIVE를 발화 순서로 앞 3개. 나머지 POSITIVE와 **확인된 NEGATIVE 전부**는 cache(`sessionStorage['medmap.intakeCache']`, `{evidence_id, status}`만). 엔진이 그 질문을 실제로 제안할 때만 `/session/answer`로 적용(질문 예산 1 사용).
- bootstrap: 부족분 = 3 − additional. 순서 E_91 → E_53 → E_66, 예비 E_201 → E_175 → E_88(STEP17A 고정), initial·확인 항목은 건너뜀. "잘 모르겠어요"는 기록만 하고 개수에 넣지 않으며 다음 질문으로 넘어간다. 남은 질문으로 채울 수 없으면 `START_INCOMPLETE` — `/session/start`를 부르지 않는다.
- 원문은 extract 요청 본문에만 쓰이고 서버·브라우저 어디에도 저장·로그되지 않는다.

## 데이터

- `src/intake/initialCatalog.json` = `medmap/data/initial_evidence_ko.json` 사본(`npm run sync:initial`). 표시·검색용, 매퍼 alias 아님.
- 폴더 이름에 `data`를 쓰지 않는다 — 루트 `.gitignore`의 `data/`가 무시한다.

## 알려진 미검증

- start에는 확인된 POSITIVE와 bootstrap의 known 답만 넣는다. 확인된 NEGATIVE는 frozen bootstrap 순서에서 walk가 실제로 도달한 경우에만 그 질문의 답으로 재사용되며(STEP17A R2/R3가 그 항목에서 공개하는 답과 같은 형태), 그 외 NEGATIVE는 cache로 가서 기존 IG 답변 경로(STEP16B 범위)로 들어간다. UNKNOWN은 start에서 배제한다.
- 사용자가 잘못 확인한 양성의 영향은 미검증이다.
- 4개 이상 확인 시 "발화 순서 앞 3개"는 UI heuristic이며 검증된 규칙이 아니다.
- STEP17A 수치(R3 top1 0.849)는 시뮬레이터 결과이며 실제 사용자 정확도가 아니다.

## 테스트

- `npm test` — vitest 전체
- `node e2e/natural-intake.e2e.mjs` — 실서버 스모크(API·vite 실행 중일 때)
````

- [ ] **Step 6: 커밋**

```bash
cd ~/medmap-worktrees/natural-intake && git add medmap-web/e2e/natural-intake.e2e.mjs medmap-web/README.md
git -c user.name=medmap -c user.email=<email> commit -m "Add real-server intake e2e smoke and README (functional UI, design paused)

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 7: 완료 보고 후 중단**(master merge·STT·디자인 재개 자동 착수 금지)

---

## Self-Review

**1. Spec coverage**

| 사용자 요구 | Task |
|---|---|
| POST /v1/intake/extract, 원문 저장·로그 금지, candidate만 | 3 |
| 자유 텍스트 입력 | 6(FreeTextInput), 7 |
| candidate 표시·확인/수정/제거 | 6(EvidenceConfirmation) |
| initial 선택(1개 자동 / 여러 개 "가장 불편한" / 0개 96개 검색, 전체 버튼 금지) | 5(initialOptions), 6(InitialPicker), 7 |
| 한국어 display label mapping(매퍼 alias 아님, v1.2 무수정) | 2, 5(catalog) |
| mapper 0개 fallback 문구 · "증상이 없습니다" 금지 | 7, 9-B |
| bootstrap 0/1/2/3 · 고정 순서 · 중복/예비 · 한 번에 한 질문 | 5(bootstrapSequence·bootstrapStep), 6(BootstrapQuestion), 7 |
| (rev2) 확인된 NEGATIVE는 additional 제외·cache 보존·제안 시만 적용 | 4-E, 5(splitConfirmed), 8(NEG cache), 9-E·D-NEGATIVE |
| (rev2) bootstrap UNKNOWN은 count 제외·기록·다음 backup | 5(bootstrapStep), 7, 8(intakeHistory), 9-B-UNKNOWN |
| (rev2) backup 소진 시 START_INCOMPLETE, start 미호출 | 5, 7, 9-B-INCOMPLETE |
| (rev2) POSITIVE confirmed + known bootstrap만으로 정확히 k3 | 5(buildStartRequest), 9-A·B |
| (rev2) 전용 worktree + read-only symlink, master 무변경 | 0 Step 1 |
| (rev2) V1 CSS 비의존 검사 | 0 Step 2 |
| exact-k3 start | 4, 5(buildStartRequest EXACT_K_VIOLATION), 9 |
| confirmed cache({evidence_id,status}만, 실제 제안 시만, posterior 무수정) | 5(answerCache), 8, 9-C/D, 4(서버 409) |
| 기존 IG 흐름 연결 | 1(ConsultScreen·QuestionPanel 재사용), 9 |
| session resume 충돌 확인 | §3 표, 8(R3~R7), 9-G(R1) |
| feat/web-ui 재사용 파일 명시 | §1, Task 1 |
| 테스트 A~H | A: 4·9 / B: 4·9 / C: 4·9 / D: 4(서버)·8·9 / E: 3·4·5·9 / F: 3·8·9·10 / G: 8·9 / H: 3 Step4·9 Step4·10 Step4 |
| branch 전략·commit 단위 | §0, 각 Task 마지막 Step |
| 제외(STT·Whisper·디자인·embedding·LLM·STEP17B) | Global Constraints — 어떤 Task에도 없음 |

**2. Placeholder scan** — "TBD/TODO/적절히/Similar to" 없음. 69개 라벨은 초안 파일에 전부 들어 있고(SHA 기록), 검수 게이트는 내용 누락이 아니라 사용자 승인 절차다.

**3. Type consistency** — `Confirmed{evidence_id,status}`·`BootAnswer{question_id,kind,value}`·`buildStartRequest → {request:{age,sex,initialEvidence,answers}, cached}`가 Task 5·7·8·9에서 같은 이름으로 쓰인다. `client.startSession({age,sex,initialEvidence,answers})`(기존)와 `request` 키가 일치. 훅 `start(intake, cache)`·`extract(text)`·`autoApplied`가 Task 8·9 일치. `NO_CANDIDATE_MESSAGE` 문자열이 Task 7·9·10 일치.

**4. Review focus(실행 전 검토자가 볼 곳)**
- `settle` 루프(Task 8): 자동 제출이 "제안된 질문"에만 걸리는지, 실패 시 마지막 성공 턴 유지.
- EvidenceConfirmation 접기 제거: 설계 문서(§11 "최대 5개 + 나머지 접기")와 다르다. 이유: 접힌 후보를 확인 없이 cache에 넣으면 "사용자 확인 없이 상태에 넣지 않는다" 위반. 사용자 판단 필요 시 보고.
- 69개 신규 라벨 의미(특히 E_150·E_202).
- (rev2) human gate는 Task 2 Step 3(애매한 라벨 3개: E_150·E_202·E_13) 하나뿐.
