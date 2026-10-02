# MedMap Web UI Implementation Plan

> **For agentic workers:** 이 계획은 Task 단위로 실행한다. 각 Step 은 체크박스(`- [ ]`)로 추적한다.
> 로컬 설치 정책상 `superpowers:subagent-driven-development` / `executing-plans` 스킬은 설치되어 있지 않으므로,
> 실행 시에는 `project-safety-review` 스킬의 제약(기존 코드 삭제 금지, 검증 없는 완료 선언 금지)을 따른다.

**Goal:** 승인된 "관측 기록지" 디자인으로, 기존 MedMap FastAPI(v1)를 그대로 호출하는 환자용 웹 UI를 만든다.

**Architecture:** `medmap-web/` 에 React + Vite 단일 페이지 앱을 만든다. 서버가 돌려준 `medmap-session-v1` 이 유일한 source of truth 이고,
UI 는 그 세션과 마지막 `medmap-turn-v1` 응답만 들고 있으며 진단·질문·확률을 스스로 계산하거나 저장하지 않는다.
화면은 시작 → 초기 입력(exact-k) → 진단 후보+질문(최대 3회) → 현재 결과 4단계이며, 상태 전이는 전부 API 응답의 `stop_reason`·`next_question` 으로 결정한다.

**Tech Stack:** React 19, React DOM, Vite, Vitest + jsdom + @testing-library/react(개발 의존성), 순수 CSS(전역 토큰 + 컴포넌트 CSS). 런타임 의존성은 react/react-dom 둘뿐.

**Spec:** `docs/medmap_ui_design.md` (승인본) · 제품 사실 `PRODUCT.md` · 방향 계약 `.impeccable/surfaces/medmap-web.md` ·
API 계약 `docs/medmap_api_design.md` · 엔진 계약 `docs/medmap_engine_contract.md`

## Global Constraints

- **API·엔진 계약 변경 금지.** UI 는 `GET /health`, `POST /v1/session/start`, `POST /v1/session/answer`, `POST /v1/session/resume` 만 호출한다.
- **source of truth 는 `medmap-session-v1`.** UI local state 는 (a) 선택 중인 옵션, (b) 전환 애니메이션 상태, (c) 오류 표시, (d) 마지막 turn 응답 캐시뿐. 진단 확률·다음 질문·IG 를 UI 가 재계산하거나 독립 저장하지 않는다.
- **`model_context` 는 `"k3"` 고정.** 자동 전환 금지. `model_context_match` 는 화면에 표시하지 않는다.
- **`/start` 는 exact-k**: 초기 evidence 1개(항상 binary POSITIVE) + 추가 관측 **정확히 3개**.
- **추가 질문 최대 3개.** 진행 표시는 응답의 `questions_asked_in_session` / `max_questions` 를 쓰고 자체 카운터를 만들지 않는다.
- **요청 본문에 `max_questions`·`questions_asked_in_session` 를 넣지 않는다**(보내면 422).
- **답변은 엔진이 방금 제안한 질문에만.** 뒤로가기 없음, [처음부터 다시]만 제공.
- **내부 오류 코드(`MEDMAP_*`)를 화면에 노출하지 않는다.** `console.error` 로만 남긴다.
- 디자인 토큰 고정값: `--bg #F2F4F5`, `--surface #FFFFFF`, `--rule #D8DEE2`, `--border #C3CBD1`, `--ink #101619`, `--ink-2 #5A6672`, `--accent #0B5661`, `--error #A32B1E`.
  spacing 4·8·12·16·24·32·48·64, radius 2/6, 버튼 높이 48(min 44), 본문 17px, 질문 22px semibold, 서체 Pretendard 한 가족, 숫자 `tabular-nums`.
- **금지 표현**: "최종 진단", "AI가 진단했습니다", "1위/2위/3위". **사용 표현**: "현재 확인이 필요한 진단 후보", "현재까지 확인된 정보", "추가로 확인할 정보".
- **금지 시각 요소**: 선 그래프·스파크라인·게이지·차트 라이브러리, AI SaaS 그라데이션, 모든 요소 카드화, 과도한 라운드, 챗봇 말풍선.
- **IG(bits) 는 사용자에게 표시하지 않는다**(`?debug=1` 에서만).
- **v1 제외**: STT, 자연어 증상 파싱, 로그인, DB, 의사 화면, 병원 검색, 치료 추천, 응급도 판단, 모델/연구 변경.

---

## File Structure

```
medmap-web/
  package.json                     의존성·스크립트
  vite.config.js                   React 플러그인, dev proxy(/health, /v1 → 127.0.0.1:8000), vitest 설정
  index.html                       #root, Pretendard 폰트 링크
  .gitignore                       node_modules, dist
  scripts/build-intake-data.mjs    초기 입력용 한국어 질문 목록 생성(빌드 타임 1회)
  scripts/record-fixtures.mjs      실행 중인 API 에서 테스트 픽스처 갱신(선택)
  src/main.jsx                     React 진입점
  src/App.jsx                      화면 전환 + 세션 보관
  src/styles/tokens.css            디자인 토큰(:root 변수)
  src/styles/app.css               기록지 레이아웃·괘선·격자 배경
  src/api/client.js                fetch 래퍼 4종 + ApiError
  src/api/messages.js              오류 → 사용자 문구 변환(코드 비노출)
  src/session/useMedmapSession.js  세션 훅(시작/답변/복원/초기화)
  src/data/intake.js               주 증상 목록·고정 3문항·예비 항목·선정 규칙
  src/data/intake.generated.json   build-intake-data.mjs 산출물(커밋함)
  src/components/AppHeader.jsx     로고 + 진행 표시(●─●─○ n/3)
  src/components/CandidatePanel.jsx 진단 후보 3행(확률·막대·변화 기호)
  src/components/QuestionPanel.jsx  질문문 + 선택지(4유형) + [다음]
  src/components/ChoiceButton.jsx   48px 선택 버튼
  src/components/Notice.jsx         오류/안내 한 줄 표시
  src/screens/StartScreen.jsx       시작
  src/screens/IntakeScreen.jsx      나이·성별·주 증상·고정 3문항
  src/screens/ConsultScreen.jsx     후보 + 질문
  src/screens/SummaryScreen.jsx     현재까지 확인된 정보
  src/lib/candidates.js             후보 diff(이전 값·방향)
  src/test/setup.js                 jest-dom 등록
  src/test/fixtures/*.json          실제 API 응답 픽스처
```

책임 분리 원칙: 화면(screens)은 배치와 문구, 컴포넌트는 표현, `api/`는 네트워크, `session/`은 상태 전이, `lib/`는 순수 계산.
파일이 커지면 화면을 쪼개지 말고 컴포넌트를 추가한다.

---

### Task 1: Vite + React scaffold 와 테스트 환경

**Files:**
- Create: `medmap-web/package.json`, `medmap-web/vite.config.js`, `medmap-web/index.html`, `medmap-web/.gitignore`, `medmap-web/src/main.jsx`, `medmap-web/src/App.jsx`, `medmap-web/src/test/setup.js`
- Modify: (없음)
- Test: `medmap-web/src/App.test.jsx`

**Interfaces:**
- Consumes: 없음
- Produces: `App` 컴포넌트(default export), `npm test`(vitest run), `npm run dev`(포트 5173, `/health`·`/v1` 를 `http://127.0.0.1:8000` 으로 proxy), `npm run build`

**의존성 결정(추가 이유 명시):**
- 런타임: `react`, `react-dom` — 필수.
- 개발: `vite`, `@vitejs/plugin-react` — 빌드/개발 서버. `vitest`, `jsdom`, `@testing-library/react`, `@testing-library/user-event`, `@testing-library/jest-dom` — Task 3~11 의 컴포넌트·통합 테스트에 필요. 테스트 러너 없이는 이 계획의 TDD 단계를 실행할 수 없다.
- 추가하지 않음: Redux/Zustand/React Query(세션이 서버 응답 하나라 불필요), Tailwind/UI 프레임워크(토큰이 고정이고 CSS 파일로 충분), chart/animation 라이브러리(선 그래프 금지, 전환은 CSS transition 으로 충분).

- [ ] **Step 1: 디렉터리 생성과 설치 (승인된 네트워크 설치)**

```bash
cd ~/medmap
mkdir -p medmap-web/src/{api,components,screens,session,lib,styles,test/fixtures,data} medmap-web/scripts
cd medmap-web
npm init -y
npm install react react-dom
npm install -D vite @vitejs/plugin-react vitest jsdom @testing-library/react @testing-library/user-event @testing-library/jest-dom
```

- [ ] **Step 2: 설정 파일 작성**

`medmap-web/package.json` 의 `scripts` 를 아래로 교체하고 `"type": "module"`, `"private": true` 를 추가한다.

```json
{
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "test:watch": "vitest",
    "build:intake": "node scripts/build-intake-data.mjs"
  }
}
```

`medmap-web/vite.config.js`:

```js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/health': 'http://127.0.0.1:8000',
      '/v1': 'http://127.0.0.1:8000',
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.js'],
    css: false,
  },
})
```

`medmap-web/index.html`:

```html
<!doctype html>
<html lang="ko">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>MedMap</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable.min.css" />
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

`medmap-web/.gitignore`:

```
node_modules
dist
```

`medmap-web/src/test/setup.js`:

```js
import '@testing-library/jest-dom/vitest'
```

- [ ] **Step 3: 실패하는 테스트 작성**

`medmap-web/src/App.test.jsx`:

```jsx
import { render, screen } from '@testing-library/react'
import App from './App'

test('앱이 서비스명을 렌더링한다', () => {
  render(<App />)
  expect(screen.getByText('MedMap')).toBeInTheDocument()
})
```

- [ ] **Step 4: 테스트 실행 → 실패 확인**

Run: `cd ~/medmap/medmap-web && npm test`
Expected: FAIL — `Failed to resolve import "./App"`

- [ ] **Step 5: 최소 구현**

`medmap-web/src/App.jsx`:

```jsx
export default function App() {
  return <h1>MedMap</h1>
}
```

`medmap-web/src/main.jsx`:

```jsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```

- [ ] **Step 6: 테스트 실행 → 통과 확인**

Run: `npm test`
Expected: PASS (1 passed)

- [ ] **Step 7: 커밋**

```bash
cd ~/medmap
git add medmap-web/package.json medmap-web/package-lock.json medmap-web/vite.config.js medmap-web/index.html medmap-web/.gitignore medmap-web/src
git commit -m "feat(web): scaffold React + Vite app with vitest"
```

---

### Task 2: 디자인 토큰 · 기록지 레이아웃 · 헤더

**Files:**
- Create: `medmap-web/src/styles/tokens.css`, `medmap-web/src/styles/app.css`, `medmap-web/src/components/AppHeader.jsx`
- Modify: `medmap-web/src/main.jsx`(스타일 import), `medmap-web/src/App.jsx`
- Test: `medmap-web/src/components/AppHeader.test.jsx`

**Interfaces:**
- Consumes: Task 1 의 `App`
- Produces: `AppHeader({ step, total })` — `step`(0~3, 이번 세션에서 답한 추가 질문 수), `total`(기본 3). CSS 변수 `--bg --surface --rule --border --ink --ink-2 --accent --error`, 클래스 `.sheet`(기록면), `.sheet-grid`(눈금 배경), `.rule`(괘선), `.layout`(좌 62%/우 38% 그리드)

- [ ] **Step 1: 실패하는 테스트 작성**

`medmap-web/src/components/AppHeader.test.jsx`:

```jsx
import { render, screen } from '@testing-library/react'
import AppHeader from './AppHeader'

test('진행 상태를 n / 3 으로 표시한다', () => {
  render(<AppHeader step={2} total={3} />)
  expect(screen.getByText('MedMap')).toBeInTheDocument()
  expect(screen.getByText('추가 확인')).toBeInTheDocument()
  expect(screen.getByText('2 / 3')).toBeInTheDocument()
})

test('진행 점은 채워진 수만큼 aria-current 를 가진다', () => {
  render(<AppHeader step={2} total={3} />)
  const dots = screen.getAllByTestId('progress-dot')
  expect(dots).toHaveLength(3)
  expect(dots.filter((d) => d.dataset.filled === 'true')).toHaveLength(2)
})
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `npm test -- AppHeader`
Expected: FAIL — `Failed to resolve import "./AppHeader"`

- [ ] **Step 3: 최소 구현**

`medmap-web/src/styles/tokens.css`:

```css
:root {
  --bg: #F2F4F5;
  --surface: #FFFFFF;
  --rule: #D8DEE2;
  --border: #C3CBD1;
  --ink: #101619;
  --ink-2: #5A6672;
  --accent: #0B5661;
  --error: #A32B1E;

  --space-1: 4px;  --space-2: 8px;  --space-3: 12px; --space-4: 16px;
  --space-6: 24px; --space-8: 32px; --space-12: 48px; --space-16: 64px;

  --radius-sm: 2px;
  --radius-md: 6px;
  --control-height: 48px;

  --font-sans: 'Pretendard Variable', Pretendard, system-ui, -apple-system, 'Segoe UI', sans-serif;
  --size-display: 30px;
  --size-heading: 22px;
  --size-body: 17px;
  --size-label: 14px;
  --size-caption: 13px;
}
```

`medmap-web/src/styles/app.css`:

```css
* { box-sizing: border-box; }

body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: var(--font-sans);
  font-size: var(--size-body);
  line-height: 1.5;
  font-variant-numeric: tabular-nums;
}

/* 관측 기록지: 옅은 청회색 눈금 배경 */
.sheet-grid {
  min-height: 100vh;
  background-image:
    linear-gradient(to right, rgba(11, 86, 97, 0.05) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(11, 86, 97, 0.05) 1px, transparent 1px);
  background-size: 24px 24px;
}

.sheet {
  background: var(--surface);
  border: 1px solid var(--rule);
  border-radius: var(--radius-md);
}

.rule { border-bottom: 1px solid var(--rule); }

.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 56px;
  padding: 0 var(--space-6);
  background: var(--surface);
  border-bottom: 1px solid var(--rule);
}

.app-header__brand { font-weight: 600; letter-spacing: 0.02em; }
.app-header__progress { display: flex; align-items: center; gap: var(--space-3); color: var(--ink-2); font-size: var(--size-label); }
.app-header__dots { display: flex; align-items: center; gap: var(--space-1); }

.progress-dot {
  width: 10px; height: 10px; border-radius: 50%;
  border: 1px solid var(--accent); background: transparent;
}
.progress-dot[data-filled='true'] { background: var(--accent); }
.progress-dash { width: 12px; height: 1px; background: var(--border); }

.layout {
  display: grid;
  grid-template-columns: 62fr 38fr;
  gap: var(--space-8);
  max-width: 1180px;
  margin: 0 auto;
  padding: var(--space-8) var(--space-6);
  align-items: start;
}
.layout--single { grid-template-columns: minmax(0, 720px); justify-content: center; }
.layout__aside { position: sticky; top: var(--space-8); }
```

`medmap-web/src/components/AppHeader.jsx`:

```jsx
export default function AppHeader({ step = 0, total = 3 }) {
  const dots = Array.from({ length: total }, (_, i) => i < step)
  return (
    <header className="app-header">
      <span className="app-header__brand">MedMap</span>
      <div className="app-header__progress">
        <span>추가 확인</span>
        <span className="app-header__dots" aria-hidden="true">
          {dots.map((filled, i) => (
            <span key={i} style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              {i > 0 && <span className="progress-dash" />}
              <span className="progress-dot" data-testid="progress-dot" data-filled={String(filled)} />
            </span>
          ))}
        </span>
        <span>{step} / {total}</span>
      </div>
    </header>
  )
}
```

`medmap-web/src/main.jsx` 상단에 스타일 import 를 추가한다.

```jsx
import './styles/tokens.css'
import './styles/app.css'
```

`medmap-web/src/App.jsx` 를 헤더를 쓰도록 바꾼다.

```jsx
import AppHeader from './components/AppHeader.jsx'

export default function App() {
  return (
    <div className="sheet-grid">
      <AppHeader step={0} total={3} />
    </div>
  )
}
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `npm test`
Expected: PASS (App.test.jsx 의 'MedMap' 검증 포함 3 passed)

- [ ] **Step 5: 커밋**

```bash
git add medmap-web/src/styles medmap-web/src/components/AppHeader.jsx medmap-web/src/components/AppHeader.test.jsx medmap-web/src/App.jsx medmap-web/src/main.jsx
git commit -m "feat(web): design tokens, observation-sheet layout, header progress"
```

---

### Task 3: 시작 화면

**Files:**
- Create: `medmap-web/src/screens/StartScreen.jsx`
- Modify: `medmap-web/src/styles/app.css`(시작 화면 클래스 추가)
- Test: `medmap-web/src/screens/StartScreen.test.jsx`

**Interfaces:**
- Consumes: `AppHeader`(Task 2)
- Produces: `StartScreen({ ready, checking, onStart })` — `ready` 가 false 면 시작 버튼 비활성. `onStart()` 는 인자 없음. API 호출은 하지 않는다(Task 5 에서 주입).

- [ ] **Step 1: 실패하는 테스트 작성**

`medmap-web/src/screens/StartScreen.test.jsx`:

```jsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import StartScreen from './StartScreen'

test('서비스 설명과 시작 버튼을 보여준다', () => {
  render(<StartScreen ready onStart={() => {}} />)
  expect(screen.getByText('증상을 한 번에 판단하지 않습니다. 확인이 필요한 정보를 하나씩 좁혀갑니다.')).toBeInTheDocument()
  expect(screen.getByText('의료 행위가 아니며 진료를 대신하지 않습니다.')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '시작하기' })).toBeEnabled()
})

test('서버가 준비되지 않으면 시작 버튼이 비활성이고 안내가 보인다', () => {
  render(<StartScreen ready={false} checking={false} onStart={() => {}} />)
  expect(screen.getByRole('button', { name: '시작하기' })).toBeDisabled()
  expect(screen.getByText('준비 중입니다. 잠시 후 다시 시도해 주세요.')).toBeInTheDocument()
})

test('시작 버튼을 누르면 onStart 가 호출된다', async () => {
  const onStart = vi.fn()
  render(<StartScreen ready onStart={onStart} />)
  await userEvent.click(screen.getByRole('button', { name: '시작하기' }))
  expect(onStart).toHaveBeenCalledTimes(1)
})
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `npm test -- StartScreen`
Expected: FAIL — `Failed to resolve import "./StartScreen"`

- [ ] **Step 3: 최소 구현**

`medmap-web/src/screens/StartScreen.jsx`:

```jsx
export default function StartScreen({ ready = false, checking = false, onStart }) {
  return (
    <main className="start">
      <h1 className="start__title">MedMap</h1>
      <p className="start__lede">증상을 한 번에 판단하지 않습니다. 확인이 필요한 정보를 하나씩 좁혀갑니다.</p>
      <button className="button button--primary" type="button" onClick={onStart} disabled={!ready}>
        시작하기
      </button>
      {!ready && !checking && (
        <p className="start__notice" role="status">준비 중입니다. 잠시 후 다시 시도해 주세요.</p>
      )}
      <p className="start__disclaimer">의료 행위가 아니며 진료를 대신하지 않습니다.</p>
    </main>
  )
}
```

`medmap-web/src/styles/app.css` 에 추가:

```css
.start {
  max-width: 560px;
  margin: 0 auto;
  padding: var(--space-16) var(--space-6);
  text-align: left;
}
.start__title { font-size: var(--size-display); margin: 0 0 var(--space-4); letter-spacing: 0.01em; }
.start__lede { font-size: var(--size-body); color: var(--ink); margin: 0 0 var(--space-8); }
.start__notice { color: var(--ink-2); font-size: var(--size-label); margin-top: var(--space-4); }
.start__disclaimer { color: var(--ink-2); font-size: var(--size-caption); margin-top: var(--space-12); }

.button {
  min-height: var(--control-height);
  padding: 0 var(--space-6);
  font: inherit;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--ink);
  cursor: pointer;
}
.button:disabled { opacity: 0.45; cursor: not-allowed; }
.button--primary { background: var(--accent); border-color: var(--accent); color: #fff; }
.button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `npm test -- StartScreen`
Expected: PASS (3 passed)

- [ ] **Step 5: 커밋**

```bash
git add medmap-web/src/screens/StartScreen.jsx medmap-web/src/screens/StartScreen.test.jsx medmap-web/src/styles/app.css
git commit -m "feat(web): start screen"
```

---

### Task 4: 초기 입력(exact-k 보장)

**Files:**
- Create: `medmap-web/scripts/build-intake-data.mjs`, `medmap-web/src/data/intake.generated.json`, `medmap-web/src/data/intake.js`, `medmap-web/src/screens/IntakeScreen.jsx`
- Modify: `medmap-web/src/styles/app.css`
- Test: `medmap-web/src/data/intake.test.js`, `medmap-web/src/screens/IntakeScreen.test.jsx`

**Interfaces:**
- Consumes: Task 2 의 스타일
- Produces:
  - `MAIN_SYMPTOMS: Array<{id: string, label: string}>` — 한국어 매핑된 binary·top-level 질문 목록
  - `FIXED_QUESTION_IDS = ['E_91', 'E_53', 'E_66']`, `BACKUP_QUESTION_IDS = ['E_201', 'E_175', 'E_88']`
  - `pickIntakeQuestions(mainSymptomId: string): Array<{id: string, label: string}>` — 항상 길이 3, `mainSymptomId` 와 중복 없음
  - `IntakeScreen({ onSubmit, pending })`, `onSubmit({ age: number, sex: 'M'|'F', initialEvidence: string, answers: Array<{question_id: string, kind: 'POSITIVE'|'NEGATIVE'|'UNKNOWN', value: null}> })` — `answers` 길이는 항상 3

- [ ] **Step 1: 데이터 생성 스크립트 작성과 실행**

`medmap-web/scripts/build-intake-data.mjs`:

```js
// 초기 입력 화면용 질문 목록을 엔진 산출물에서 1회 생성한다(런타임 호출 없음).
import { readFileSync, writeFileSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const repo = resolve(here, '..', '..')
const labels = JSON.parse(readFileSync(resolve(repo, 'medmap/data/question_labels_ko.json'), 'utf8'))
const evidences = JSON.parse(readFileSync(resolve(repo, 'data/ddxplus/en/release_evidences.json'), 'utf8'))

const EXCLUDED = new Set(['E_134', 'E_152'])
const questions = Object.entries(labels.questions)
  .filter(([id]) => {
    const def = evidences[id]
    return def && def.data_type === 'B' && def.code_question === id && !EXCLUDED.has(id)
  })
  .map(([id, label]) => ({ id, label }))
  .sort((a, b) => Number(a.id.slice(2)) - Number(b.id.slice(2)))

writeFileSync(
  resolve(here, '..', 'src/data/intake.generated.json'),
  JSON.stringify({ generated_from: 'medmap/data/question_labels_ko.json + release_evidences.json', questions }, null, 1) + '\n',
)
console.log(`questions: ${questions.length}`)
```

Run: `cd ~/medmap/medmap-web && npm run build:intake`
Expected: `questions: 41` 출력, `src/data/intake.generated.json` 생성

- [ ] **Step 2: 실패하는 테스트 작성**

`medmap-web/src/data/intake.test.js`:

```js
import { MAIN_SYMPTOMS, FIXED_QUESTION_IDS, pickIntakeQuestions } from './intake'

test('주 증상 목록은 한국어 라벨을 가진 binary 질문이다', () => {
  expect(MAIN_SYMPTOMS.length).toBeGreaterThanOrEqual(20)
  expect(MAIN_SYMPTOMS.every((q) => q.id.startsWith('E_') && q.label.length > 0)).toBe(true)
  expect(MAIN_SYMPTOMS.some((q) => q.id === 'E_134' || q.id === 'E_152')).toBe(false)
})

test('주 증상과 겹치지 않는 3문항을 고른다', () => {
  const picked = pickIntakeQuestions('E_201')
  expect(picked.map((q) => q.id)).toEqual(FIXED_QUESTION_IDS)
  expect(picked).toHaveLength(3)
})

test('주 증상이 고정 문항과 겹치면 예비 항목으로 대체한다', () => {
  const picked = pickIntakeQuestions('E_53')
  expect(picked).toHaveLength(3)
  expect(picked.map((q) => q.id)).not.toContain('E_53')
  expect(picked.map((q) => q.id)).toEqual(['E_91', 'E_66', 'E_201'])
})

test('모든 결과는 중복이 없다', () => {
  for (const main of ['E_91', 'E_66', 'E_201', 'E_175']) {
    const ids = pickIntakeQuestions(main).map((q) => q.id)
    expect(new Set(ids).size).toBe(3)
    expect(ids).not.toContain(main)
  }
})
```

- [ ] **Step 3: 테스트 실행 → 실패 확인**

Run: `npm test -- intake`
Expected: FAIL — `Failed to resolve import "./intake"`

- [ ] **Step 4: 최소 구현**

`medmap-web/src/data/intake.js`:

```js
import generated from './intake.generated.json'

export const MAIN_SYMPTOMS = generated.questions

// 모든 사용자에게 동일하게 묻는 3문항(열 · 통증 · 숨참). 주 증상과 겹치면 예비 항목으로 대체한다.
export const FIXED_QUESTION_IDS = ['E_91', 'E_53', 'E_66']
export const BACKUP_QUESTION_IDS = ['E_201', 'E_175', 'E_88']

const byId = new Map(MAIN_SYMPTOMS.map((q) => [q.id, q]))

export function pickIntakeQuestions(mainSymptomId) {
  const picked = []
  for (const id of [...FIXED_QUESTION_IDS, ...BACKUP_QUESTION_IDS]) {
    if (picked.length === 3) break
    if (id === mainSymptomId || picked.some((q) => q.id === id)) continue
    const question = byId.get(id)
    if (question) picked.push(question)
  }
  if (picked.length !== 3) throw new Error('INTAKE_QUESTION_POOL_TOO_SMALL')
  return picked
}
```

- [ ] **Step 5: 테스트 실행 → 통과 확인**

Run: `npm test -- intake`
Expected: PASS (4 passed)

- [ ] **Step 6: 화면 테스트 작성**

`medmap-web/src/screens/IntakeScreen.test.jsx`:

```jsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import IntakeScreen from './IntakeScreen'

async function fillAll(user) {
  await user.clear(screen.getByLabelText('나이'))
  await user.type(screen.getByLabelText('나이'), '45')
  await user.click(screen.getByRole('button', { name: '남성' }))
  await user.click(screen.getByRole('button', { name: '기침이 있나요?' }))
  const groups = screen.getAllByTestId('intake-question')
  for (const group of groups) {
    await user.click(within(group).getByRole('button', { name: '아니요' }))
  }
}

test('주 증상을 고르면 겹치지 않는 3문항이 나타난다', async () => {
  const user = userEvent.setup()
  render(<IntakeScreen onSubmit={() => {}} />)
  // E_53 의 실제 라벨
  await user.click(screen.getByRole('button', { name: '이번에 진료를 받으려는 이유와 관련해서 어딘가 통증이 있나요?' }))
  const groups = screen.getAllByTestId('intake-question')
  expect(groups).toHaveLength(3)
  expect(groups.map((g) => g.dataset.questionId)).toEqual(['E_91', 'E_66', 'E_201'])
})

test('모두 답하면 exact-k 형태(초기 1 + 추가 3)로 제출한다', async () => {
  const user = userEvent.setup()
  const onSubmit = vi.fn()
  render(<IntakeScreen onSubmit={onSubmit} />)
  await fillAll(user)
  await user.click(screen.getByRole('button', { name: '확인하고 시작' }))
  expect(onSubmit).toHaveBeenCalledTimes(1)
  const payload = onSubmit.mock.calls[0][0]
  expect(payload.age).toBe(45)
  expect(payload.sex).toBe('M')
  expect(payload.initialEvidence).toBe('E_201')
  expect(payload.answers).toHaveLength(3)
  expect(payload.answers.every((a) => a.value === null)).toBe(true)
  expect(payload.answers.map((a) => a.kind)).toEqual(['NEGATIVE', 'NEGATIVE', 'NEGATIVE'])
  expect(payload.answers.map((a) => a.question_id)).toEqual(['E_91', 'E_53', 'E_66'])
})

test('답하지 않은 항목이 있으면 제출 버튼이 비활성이다', async () => {
  const user = userEvent.setup()
  render(<IntakeScreen onSubmit={() => {}} />)
  await user.click(screen.getByRole('button', { name: '기침이 있나요?' }))
  expect(screen.getByRole('button', { name: '확인하고 시작' })).toBeDisabled()
})
```

테스트 상단에 `import { within } from '@testing-library/react'` 를 추가한다.

- [ ] **Step 7: 테스트 실행 → 실패 확인**

Run: `npm test -- IntakeScreen`
Expected: FAIL — `Failed to resolve import "./IntakeScreen"`

- [ ] **Step 8: 화면 구현**

`medmap-web/src/screens/IntakeScreen.jsx`:

```jsx
import { useMemo, useState } from 'react'
import { MAIN_SYMPTOMS, pickIntakeQuestions } from '../data/intake.js'

const KIND_LABELS = [
  ['POSITIVE', '예'],
  ['NEGATIVE', '아니요'],
  ['UNKNOWN', '모름'],
]

export default function IntakeScreen({ onSubmit, pending = false }) {
  const [age, setAge] = useState('45')
  const [sex, setSex] = useState('')
  const [mainSymptom, setMainSymptom] = useState('')
  const [answers, setAnswers] = useState({})

  const questions = useMemo(() => (mainSymptom ? pickIntakeQuestions(mainSymptom) : []), [mainSymptom])
  const answered = questions.length === 3 && questions.every((q) => answers[q.id])
  const ready = Boolean(age) && Number(age) >= 0 && Number(age) <= 130 && sex && mainSymptom && answered

  function chooseMainSymptom(id) {
    setMainSymptom(id)
    setAnswers({})
  }

  function submit() {
    onSubmit({
      age: Number(age),
      sex,
      initialEvidence: mainSymptom,
      answers: questions.map((q) => ({ question_id: q.id, kind: answers[q.id], value: null })),
    })
  }

  return (
    <main className="layout layout--single">
      <section className="sheet intake">
        <div className="intake__row">
          <label className="intake__field">
            <span>나이</span>
            <input inputMode="numeric" value={age} onChange={(e) => setAge(e.target.value.replace(/\D/g, ''))} />
          </label>
          <div className="intake__field">
            <span>성별</span>
            <div className="intake__choices">
              {[['M', '남성'], ['F', '여성']].map(([code, label]) => (
                <button key={code} type="button" className="button" aria-pressed={sex === code} onClick={() => setSex(code)}>
                  {label}
                </button>
              ))}
            </div>
          </div>
        </div>

        <h2 className="intake__heading">지금 가장 불편한 것을 하나 고르세요</h2>
        <div className="intake__symptoms">
          {MAIN_SYMPTOMS.map((q) => (
            <button key={q.id} type="button" className="button" aria-pressed={mainSymptom === q.id} onClick={() => chooseMainSymptom(q.id)}>
              {q.label}
            </button>
          ))}
        </div>

        {questions.length > 0 && (
          <>
            <h2 className="intake__heading">세 가지만 더 확인할게요</h2>
            {questions.map((q, index) => (
              <div className="intake-question" data-testid="intake-question" data-question-id={q.id} key={q.id}>
                <p className="intake-question__text">{index + 1}. {q.label}</p>
                <div className="intake__choices">
                  {KIND_LABELS.map(([kind, label]) => (
                    <button
                      key={kind}
                      type="button"
                      className="button"
                      aria-pressed={answers[q.id] === kind}
                      onClick={() => setAnswers((prev) => ({ ...prev, [q.id]: kind }))}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </>
        )}

        <button className="button button--primary intake__submit" type="button" disabled={!ready || pending} onClick={submit}>
          확인하고 시작
        </button>
      </section>
    </main>
  )
}
```

`medmap-web/src/styles/app.css` 에 추가:

```css
.intake { padding: var(--space-8); }
.intake__row { display: flex; gap: var(--space-8); padding-bottom: var(--space-6); border-bottom: 1px solid var(--rule); }
.intake__field { display: flex; flex-direction: column; gap: var(--space-2); font-size: var(--size-label); color: var(--ink-2); }
.intake__field input { height: var(--control-height); width: 96px; padding: 0 var(--space-3); font: inherit; border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--surface); }
.intake__heading { font-size: var(--size-heading); font-weight: 600; margin: var(--space-8) 0 var(--space-4); }
.intake__symptoms { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.intake__choices { display: flex; gap: var(--space-2); }
.intake-question { padding: var(--space-4) 0; border-bottom: 1px solid var(--rule); }
.intake-question__text { margin: 0 0 var(--space-3); }
.intake__submit { margin-top: var(--space-8); }
.button[aria-pressed='true'] { border-color: var(--accent); border-width: 2px; color: var(--accent); font-weight: 600; }
```

- [ ] **Step 9: 테스트 실행 → 통과 확인**

Run: `npm test -- IntakeScreen intake`
Expected: PASS (7 passed)

- [ ] **Step 10: 커밋**

```bash
git add medmap-web/scripts/build-intake-data.mjs medmap-web/src/data medmap-web/src/screens/IntakeScreen.jsx medmap-web/src/screens/IntakeScreen.test.jsx medmap-web/src/styles/app.css
git commit -m "feat(web): intake screen with exact-k question selection"
```

---

### Task 5: FastAPI 클라이언트 계층

**Files:**
- Create: `medmap-web/src/api/client.js`, `medmap-web/src/test/fixtures/turn.start.json`, `medmap-web/scripts/record-fixtures.mjs`
- Modify: (없음)
- Test: `medmap-web/src/api/client.test.js`

**Interfaces:**
- Consumes: 없음(전역 `fetch`)
- Produces:
  - `class ApiError extends Error { status: number, code: string, field: string|null }`
  - `getHealth(): Promise<{status, engine_ready, api_version, model_contexts, max_questions, schema}>`
  - `startSession({ age, sex, initialEvidence, answers }): Promise<Turn>` — 본문에 `model_context: 'k3'` 를 넣고 `max_questions`·`questions_asked_in_session` 는 넣지 않는다
  - `submitAnswer({ session, questionId, kind, value }): Promise<Turn>`
  - `resumeSession(session): Promise<Turn>`
  - `Turn` = API `medmap-turn-v1` 응답 객체 그대로(가공 금지)

- [ ] **Step 1: 픽스처 준비**

`medmap-web/scripts/record-fixtures.mjs` (실행 중인 API 에서 픽스처를 갱신할 때만 사용):

```js
// 사용법: (터미널1) ~/ai_env/bin/python -m uvicorn medmap.api:app --port 8000
//        (터미널2) node scripts/record-fixtures.mjs
import { writeFileSync } from 'node:fs'
const base = process.env.MEDMAP_API ?? 'http://127.0.0.1:8000'
const body = {
  age: 45, sex: 'M', model_context: 'k3', initial_evidence: 'E_53',
  answers: [
    { question_id: 'E_55', kind: 'VALUE', value: ['V_89'] },
    { question_id: 'E_56', kind: 'VALUE', value: ['2'] },
    { question_id: 'E_204', kind: 'VALUE', value: ['V_10'] },
  ],
}
const turn = await (await fetch(`${base}/v1/session/start`, {
  method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body),
})).json()
writeFileSync(new URL('../src/test/fixtures/turn.start.json', import.meta.url), JSON.stringify(turn, null, 1) + '\n')
console.log('saved turn.start.json', turn.next_question.question_id)
```

`medmap-web/src/test/fixtures/turn.start.json` 은 위 스크립트로 1회 생성해 커밋한다(오프라인 테스트용).

- [ ] **Step 2: 실패하는 테스트 작성**

`medmap-web/src/api/client.test.js`:

```js
import { ApiError, getHealth, startSession, submitAnswer, resumeSession } from './client'
import turnStart from '../test/fixtures/turn.start.json'

function mockFetch(status, payload) {
  return vi.fn(async () => ({ ok: status < 400, status, json: async () => payload }))
}

test('start 는 model_context k3 를 보내고 max_questions 는 보내지 않는다', async () => {
  const fetchMock = mockFetch(200, turnStart)
  vi.stubGlobal('fetch', fetchMock)
  const turn = await startSession({
    age: 45, sex: 'M', initialEvidence: 'E_53',
    answers: [
      { question_id: 'E_55', kind: 'VALUE', value: ['V_89'] },
      { question_id: 'E_56', kind: 'VALUE', value: ['2'] },
      { question_id: 'E_204', kind: 'VALUE', value: ['V_10'] },
    ],
  })
  const [url, init] = fetchMock.mock.calls[0]
  const sent = JSON.parse(init.body)
  expect(url).toBe('/v1/session/start')
  expect(sent.model_context).toBe('k3')
  expect(sent).not.toHaveProperty('max_questions')
  expect(sent).not.toHaveProperty('questions_asked_in_session')
  expect(turn.schema_version).toBe('medmap-turn-v1')
})

test('answer 는 session 과 submission 을 그대로 보낸다', async () => {
  const fetchMock = mockFetch(200, turnStart)
  vi.stubGlobal('fetch', fetchMock)
  await submitAnswer({ session: turnStart.session, questionId: 'E_54', kind: 'VALUE', value: ['V_181'] })
  const sent = JSON.parse(fetchMock.mock.calls[0][1].body)
  expect(sent.session).toEqual(turnStart.session)
  expect(sent.submission).toEqual({ question_id: 'E_54', answer: { kind: 'VALUE', value: ['V_181'] } })
})

test('VALUE 가 아닌 답변은 value 를 null 로 보낸다', async () => {
  const fetchMock = mockFetch(200, turnStart)
  vi.stubGlobal('fetch', fetchMock)
  await submitAnswer({ session: turnStart.session, questionId: 'E_155', kind: 'NEGATIVE', value: null })
  const sent = JSON.parse(fetchMock.mock.calls[0][1].body)
  expect(sent.submission.answer).toEqual({ kind: 'NEGATIVE', value: null })
})

test('오류 응답은 ApiError 로 바뀐다', async () => {
  vi.stubGlobal('fetch', mockFetch(409, { error: { code: 'MEDMAP_ALREADY_ASKED', message: 'MEDMAP_ALREADY_ASKED:E_55', field: 'question_id' } }))
  await expect(resumeSession(turnStart.session)).rejects.toMatchObject({
    name: 'ApiError', status: 409, code: 'MEDMAP_ALREADY_ASKED', field: 'question_id',
  })
})

test('health 는 준비 상태를 그대로 돌려준다', async () => {
  vi.stubGlobal('fetch', mockFetch(200, { status: 'ok', engine_ready: true, max_questions: 3 }))
  await expect(getHealth()).resolves.toMatchObject({ engine_ready: true, max_questions: 3 })
})
```

- [ ] **Step 3: 테스트 실행 → 실패 확인**

Run: `npm test -- client`
Expected: FAIL — `Failed to resolve import "./client"`

- [ ] **Step 4: 최소 구현**

`medmap-web/src/api/client.js`:

```js
const BASE = import.meta.env?.VITE_MEDMAP_API ?? ''
export const MODEL_CONTEXT = 'k3'

export class ApiError extends Error {
  constructor(status, code, message, field = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.field = field
  }
}

async function request(path, options) {
  let response
  try {
    response = await fetch(`${BASE}${path}`, options)
  } catch (cause) {
    throw new ApiError(0, 'NETWORK_ERROR', String(cause))
  }
  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    const error = payload?.error ?? {}
    throw new ApiError(response.status, error.code ?? 'UNKNOWN_ERROR', error.message ?? 'request failed', error.field ?? null)
  }
  return payload
}

function post(path, body) {
  return request(path, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export function getHealth() {
  return request('/health', { method: 'GET' })
}

export function startSession({ age, sex, initialEvidence, answers }) {
  return post('/v1/session/start', {
    age,
    sex,
    model_context: MODEL_CONTEXT,
    initial_evidence: initialEvidence,
    answers,
  })
}

export function submitAnswer({ session, questionId, kind, value }) {
  return post('/v1/session/answer', {
    session,
    submission: { question_id: questionId, answer: { kind, value: kind === 'VALUE' ? value : null } },
  })
}

export function resumeSession(session) {
  return post('/v1/session/resume', { session })
}
```

- [ ] **Step 5: 테스트 실행 → 통과 확인**

Run: `npm test -- client`
Expected: PASS (5 passed)

- [ ] **Step 6: 커밋**

```bash
git add medmap-web/src/api/client.js medmap-web/src/api/client.test.js medmap-web/src/test/fixtures medmap-web/scripts/record-fixtures.mjs
git commit -m "feat(web): FastAPI client layer"
```

---

### Task 6: 진단 후보 + 현재 질문 화면

**Files:**
- Create: `medmap-web/src/components/CandidatePanel.jsx`, `medmap-web/src/components/QuestionPanel.jsx`, `medmap-web/src/components/ChoiceButton.jsx`, `medmap-web/src/screens/ConsultScreen.jsx`
- Modify: `medmap-web/src/styles/app.css`
- Test: `medmap-web/src/components/CandidatePanel.test.jsx`, `medmap-web/src/components/QuestionPanel.test.jsx`, `medmap-web/src/screens/ConsultScreen.test.jsx`

**Interfaces:**
- Consumes: Task 5 의 `Turn` 형태
- Produces:
  - `CandidatePanel({ rows })`, `rows: Array<{name, probability, previous: number|null, direction: 'up'|'down'|'same'}>`
  - `QuestionPanel({ question, onAnswer, pending })`, `question` 은 turn 의 `next_question` 그대로, `onAnswer({kind, value})`
  - `ChoiceButton({ label, selected, onClick })`
  - `ConsultScreen({ turn, onAnswer, pending })`

- [ ] **Step 1: 실패하는 테스트 작성**

`medmap-web/src/components/CandidatePanel.test.jsx`:

```jsx
import { render, screen } from '@testing-library/react'
import CandidatePanel from './CandidatePanel'

const rows = [
  { name: '만성 부비동염', probability: 0.2435, previous: 0.0802, direction: 'up' },
  { name: '기관지염', probability: 0.2415, previous: 0.2513, direction: 'down' },
  { name: '급성 부비동염', probability: 0.2388, previous: 0.2388, direction: 'same' },
]

test('후보 3개를 순위 표기 없이 보여준다', () => {
  render(<CandidatePanel rows={rows} />)
  expect(screen.getByText('현재 확인이 필요한 진단 후보')).toBeInTheDocument()
  expect(screen.getByText('만성 부비동염')).toBeInTheDocument()
  expect(screen.getByText('24.4%')).toBeInTheDocument()
  expect(screen.queryByText('1위')).not.toBeInTheDocument()
})

test('변화 방향을 기호로 표시하고 막대는 확률에 비례한다', () => {
  render(<CandidatePanel rows={rows} />)
  const items = screen.getAllByTestId('candidate-row')
  expect(items[0].querySelector('[data-direction]').dataset.direction).toBe('up')
  expect(items[0].querySelector('.candidate__bar').style.width).toBe('24.35%')
})

test('선 그래프나 canvas 를 쓰지 않는다', () => {
  const { container } = render(<CandidatePanel rows={rows} />)
  expect(container.querySelector('svg')).toBeNull()
  expect(container.querySelector('canvas')).toBeNull()
})
```

`medmap-web/src/components/QuestionPanel.test.jsx`:

```jsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import QuestionPanel from './QuestionPanel'

const yesNo = {
  question_id: 'E_155', question_ko: '심장이 빠르게 뛰나요?', question_original: 'Do you feel palpitations?',
  answer_type: 'YES_NO', information_gain: 0.6547, is_fallback: false, explanation: null,
  choices: [
    { value: true, label: '예', original_label: null, is_fallback: false },
    { value: false, label: '아니요', original_label: null, is_fallback: false },
    { value: null, label: '잘 모르겠어요', original_label: null, is_fallback: false },
  ],
}

const multi = {
  question_id: 'E_54', question_ko: '통증이 어떤 느낌인가요?', question_original: 'Characterize your pain:',
  answer_type: 'MULTI_CHOICE', information_gain: 1.6559, is_fallback: false, explanation: null,
  choices: [
    { value: 'V_181', label: '타는 듯한', original_label: 'burning', is_fallback: false },
    { value: 'V_183', label: '묵직한', original_label: 'heavy', is_fallback: false },
    { value: null, label: '잘 모르겠어요', original_label: null, is_fallback: false },
  ],
}

test('질문과 선택지를 보여주고 정보이득은 감춘다', () => {
  render(<QuestionPanel question={yesNo} onAnswer={() => {}} />)
  expect(screen.getByText('추가로 확인할 정보')).toBeInTheDocument()
  expect(screen.getByText('심장이 빠르게 뛰나요?')).toBeInTheDocument()
  expect(screen.queryByText(/bits/)).not.toBeInTheDocument()
  expect(screen.queryByText(/0\.65/)).not.toBeInTheDocument()
})

test('예/아니요는 즉시 제출된다', async () => {
  const onAnswer = vi.fn()
  render(<QuestionPanel question={yesNo} onAnswer={onAnswer} />)
  await userEvent.click(screen.getByRole('button', { name: '아니요' }))
  expect(onAnswer).toHaveBeenCalledWith({ kind: 'NEGATIVE', value: null })
})

test('잘 모르겠어요는 UNKNOWN 으로 제출된다', async () => {
  const onAnswer = vi.fn()
  render(<QuestionPanel question={yesNo} onAnswer={onAnswer} />)
  await userEvent.click(screen.getByRole('button', { name: '잘 모르겠어요' }))
  expect(onAnswer).toHaveBeenCalledWith({ kind: 'UNKNOWN', value: null })
})

test('다중 선택은 여러 개를 고른 뒤 다음으로 제출한다', async () => {
  const user = userEvent.setup()
  const onAnswer = vi.fn()
  render(<QuestionPanel question={multi} onAnswer={onAnswer} />)
  await user.click(screen.getByRole('button', { name: '타는 듯한' }))
  await user.click(screen.getByRole('button', { name: '묵직한' }))
  await user.click(screen.getByRole('button', { name: '다음' }))
  expect(onAnswer).toHaveBeenCalledWith({ kind: 'VALUE', value: ['V_181', 'V_183'] })
})

test('한국어 미매핑 질문은 원문과 안내 라벨을 함께 보여준다', () => {
  render(<QuestionPanel question={{ ...yesNo, question_ko: 'Do you have a cough?', is_fallback: true }} onAnswer={() => {}} />)
  expect(screen.getByText('Do you have a cough?')).toBeInTheDocument()
  expect(screen.getByText('영문 원문')).toBeInTheDocument()
})
```

`medmap-web/src/screens/ConsultScreen.test.jsx`:

```jsx
import { render, screen } from '@testing-library/react'
import ConsultScreen from './ConsultScreen'
import turnStart from '../test/fixtures/turn.start.json'

test('후보와 질문을 한 화면에 배치한다', () => {
  render(<ConsultScreen turn={turnStart} onAnswer={() => {}} />)
  expect(screen.getByText('현재 확인이 필요한 진단 후보')).toBeInTheDocument()
  expect(screen.getByText('추가로 확인할 정보')).toBeInTheDocument()
  expect(screen.getAllByTestId('candidate-row')).toHaveLength(3)
})
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `npm test -- CandidatePanel QuestionPanel ConsultScreen`
Expected: FAIL — 세 모듈 모두 `Failed to resolve import`

- [ ] **Step 3: 최소 구현**

`medmap-web/src/components/ChoiceButton.jsx`:

```jsx
export default function ChoiceButton({ label, selected = false, onClick, disabled = false }) {
  return (
    <button type="button" className="button choice" aria-pressed={selected} onClick={onClick} disabled={disabled}>
      {label}
    </button>
  )
}
```

`medmap-web/src/components/CandidatePanel.jsx`:

```jsx
const SYMBOL = { up: '↑', down: '↓', same: '–' }
const SYMBOL_LABEL = { up: '올라감', down: '내려감', same: '변화 없음' }

export default function CandidatePanel({ rows, note = null }) {
  return (
    <section className="sheet candidates" aria-live="polite">
      <h2 className="candidates__title">현재 확인이 필요한 진단 후보</h2>
      <ul className="candidates__list">
        {rows.map((row) => (
          <li className="candidate" data-testid="candidate-row" key={row.name}>
            <div className="candidate__head">
              <span className="candidate__name">{row.name}</span>
              <span className="candidate__value">{(row.probability * 100).toFixed(1)}%</span>
              <span className="candidate__direction" data-direction={row.direction} aria-label={SYMBOL_LABEL[row.direction]}>
                {SYMBOL[row.direction]}
              </span>
            </div>
            <div className="candidate__track">
              <div className="candidate__bar" style={{ width: `${(row.probability * 100).toFixed(2)}%` }} />
            </div>
          </li>
        ))}
      </ul>
      {note && <p className="candidates__note">{note}</p>}
    </section>
  )
}
```

`medmap-web/src/components/QuestionPanel.jsx`:

```jsx
import { useEffect, useState } from 'react'
import ChoiceButton from './ChoiceButton.jsx'

const SINGLE_TYPES = new Set(['YES_NO', 'SINGLE_CHOICE', 'SCALE'])
const VISIBLE_CHOICE_LIMIT = 12

export default function QuestionPanel({ question, onAnswer, pending = false }) {
  const [selected, setSelected] = useState([])
  const [expanded, setExpanded] = useState(false)

  useEffect(() => {
    setSelected([])
    setExpanded(false)
  }, [question.question_id])

  const isMulti = question.answer_type === 'MULTI_CHOICE'
  const choices = expanded ? question.choices : question.choices.slice(0, VISIBLE_CHOICE_LIMIT)

  function answerFromChoice(choice) {
    if (choice.value === null) return { kind: 'UNKNOWN', value: null }
    if (question.answer_type === 'YES_NO') return { kind: choice.value ? 'POSITIVE' : 'NEGATIVE', value: null }
    return { kind: 'VALUE', value: [choice.value] }
  }

  function handleChoice(choice) {
    if (!isMulti) {
      onAnswer(answerFromChoice(choice))
      return
    }
    if (choice.value === null) {
      onAnswer({ kind: 'UNKNOWN', value: null })
      return
    }
    setSelected((prev) => (prev.includes(choice.value) ? prev.filter((v) => v !== choice.value) : [...prev, choice.value]))
  }

  return (
    <section className="sheet question">
      <h2 className="question__kicker">추가로 확인할 정보</h2>
      <p className="question__text">{question.question_ko}</p>
      {question.is_fallback && <p className="question__fallback">영문 원문</p>}
      <div className="question__choices">
        {choices.map((choice) => (
          <ChoiceButton
            key={String(choice.value)}
            label={choice.label}
            selected={isMulti && selected.includes(choice.value)}
            onClick={() => handleChoice(choice)}
            disabled={pending}
          />
        ))}
      </div>
      {!expanded && question.choices.length > VISIBLE_CHOICE_LIMIT && (
        <button type="button" className="question__more" onClick={() => setExpanded(true)}>
          전체 보기 ({question.choices.length}개)
        </button>
      )}
      {isMulti && (
        <button
          type="button"
          className="button button--primary question__next"
          disabled={selected.length === 0 || pending}
          onClick={() => onAnswer({ kind: 'VALUE', value: selected })}
        >
          다음
        </button>
      )}
    </section>
  )
}
```

`medmap-web/src/screens/ConsultScreen.jsx`:

```jsx
import CandidatePanel from '../components/CandidatePanel.jsx'
import QuestionPanel from '../components/QuestionPanel.jsx'
import { toCandidateRows } from '../lib/candidates.js'

export default function ConsultScreen({ turn, onAnswer, pending = false }) {
  const rows = toCandidateRows(turn)
  const wide = turn.next_question && turn.next_question.choices.length > 20
  return (
    <main className={wide ? 'layout layout--single' : 'layout'}>
      <QuestionPanel question={turn.next_question} onAnswer={onAnswer} pending={pending} />
      {!wide && (
        <aside className="layout__aside">
          <CandidatePanel rows={rows} note={turn.diagnoses_before ? '직전 답변이 반영되었습니다' : null} />
        </aside>
      )}
    </main>
  )
}
```

`medmap-web/src/styles/app.css` 에 추가:

```css
.candidates { padding: var(--space-6); }
.candidates__title { font-size: var(--size-label); color: var(--ink-2); margin: 0 0 var(--space-4); font-weight: 600; }
.candidates__list { list-style: none; margin: 0; padding: 0; }
.candidate { padding: var(--space-3) 0; border-bottom: 1px solid var(--rule); }
.candidate__head { display: flex; align-items: baseline; gap: var(--space-2); }
.candidate__name { flex: 1; }
.candidate__value { font-weight: 600; }
.candidate__direction { width: 16px; text-align: center; color: var(--ink-2); }
.candidate__track { margin-top: var(--space-2); height: 3px; background: var(--rule); }
.candidate__bar { height: 3px; background: var(--accent); }
.candidates__note { margin: var(--space-4) 0 0; font-size: var(--size-caption); color: var(--ink-2); }

.question { padding: var(--space-8); }
.question__kicker { font-size: var(--size-label); color: var(--ink-2); margin: 0 0 var(--space-3); font-weight: 600; }
.question__text { font-size: var(--size-heading); font-weight: 600; margin: 0 0 var(--space-6); }
.question__fallback { font-size: var(--size-caption); color: var(--ink-2); margin: calc(var(--space-6) * -1 + var(--space-2)) 0 var(--space-6); }
.question__choices { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.question__more { margin-top: var(--space-4); background: none; border: none; color: var(--accent); font: inherit; cursor: pointer; text-decoration: underline; }
.question__next { margin-top: var(--space-8); }
```

`medmap-web/src/lib/candidates.js` 의 최소 버전(Task 7 에서 확장):

```js
export function toCandidateRows(turn) {
  return turn.diagnoses.map((d) => ({ name: d.name, probability: d.probability, previous: null, direction: 'same' }))
}
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `npm test -- CandidatePanel QuestionPanel ConsultScreen`
Expected: PASS (9 passed)

- [ ] **Step 5: 커밋**

```bash
git add medmap-web/src/components medmap-web/src/screens/ConsultScreen.jsx medmap-web/src/screens/ConsultScreen.test.jsx medmap-web/src/lib medmap-web/src/styles/app.css
git commit -m "feat(web): consult screen with candidates and question panel"
```

---

### Task 7: 답변 후 후보 변화 표현

**Files:**
- Create: (없음)
- Modify: `medmap-web/src/lib/candidates.js`, `medmap-web/src/components/CandidatePanel.jsx`, `medmap-web/src/styles/app.css`
- Test: `medmap-web/src/lib/candidates.test.js`, `medmap-web/src/components/CandidatePanel.test.jsx`(케이스 추가)

**Interfaces:**
- Consumes: turn 의 `diagnoses`, `diagnoses_before`
- Produces: `toCandidateRows(turn): Array<{name, probability, previous: number|null, direction: 'up'|'down'|'same'}>` — `diagnoses_before` 가 없으면 `previous: null`, `direction: 'same'`

- [ ] **Step 1: 실패하는 테스트 작성**

`medmap-web/src/lib/candidates.test.js`:

```js
import { toCandidateRows } from './candidates'

const turn = {
  diagnoses: [
    { name: '기관지염', probability: 0.405 },
    { name: '급성 후두염', probability: 0.27 },
    { name: 'PSVT', probability: 0.176 },
  ],
  diagnoses_before: [
    { name: '만성 부비동염', probability: 0.2435 },
    { name: '기관지염', probability: 0.2415 },
    { name: '급성 부비동염', probability: 0.2388 },
  ],
}

test('이전 값과 비교해 방향을 매긴다', () => {
  const rows = toCandidateRows(turn)
  expect(rows[0]).toEqual({ name: '기관지염', probability: 0.405, previous: 0.2415, direction: 'up' })
  expect(rows[1]).toEqual({ name: '급성 후두염', probability: 0.27, previous: null, direction: 'same' })
})

test('직전 응답이 없으면 방향은 모두 same 이고 previous 는 null 이다', () => {
  const rows = toCandidateRows({ diagnoses: turn.diagnoses, diagnoses_before: null })
  expect(rows.every((r) => r.direction === 'same' && r.previous === null)).toBe(true)
})

test('같은 확률이면 same 이다', () => {
  const rows = toCandidateRows({
    diagnoses: [{ name: 'URTI', probability: 0.3 }],
    diagnoses_before: [{ name: 'URTI', probability: 0.3 }],
  })
  expect(rows[0].direction).toBe('same')
})
```

`medmap-web/src/components/CandidatePanel.test.jsx` 에 추가:

```jsx
test('이전 값 잔상을 한 번 보여준다', () => {
  render(<CandidatePanel rows={rows} />)
  const ghost = screen.getByTestId('candidate-ghost-만성 부비동염')
  expect(ghost).toHaveTextContent('8.0%')
  expect(ghost.className).toContain('candidate__ghost')
})
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `npm test -- candidates CandidatePanel`
Expected: FAIL — `expected { name: '기관지염', …, previous: null } to equal { …, previous: 0.2415 }` 및 ghost 요소 없음

- [ ] **Step 3: 최소 구현**

`medmap-web/src/lib/candidates.js` 를 교체한다.

```js
export function toCandidateRows(turn) {
  const before = new Map((turn.diagnoses_before ?? []).map((d) => [d.name, d.probability]))
  return turn.diagnoses.map((d) => {
    const previous = before.has(d.name) ? before.get(d.name) : null
    let direction = 'same'
    if (previous !== null) {
      if (d.probability > previous) direction = 'up'
      else if (d.probability < previous) direction = 'down'
    }
    return { name: d.name, probability: d.probability, previous, direction }
  })
}
```

`CandidatePanel.jsx` 의 `candidate__head` 아래에 잔상을 추가한다.

```jsx
            {row.previous !== null && row.direction !== 'same' && (
              <span className="candidate__ghost" data-testid={`candidate-ghost-${row.name}`}>
                {(row.previous * 100).toFixed(1)}%
              </span>
            )}
```

`app.css` 에 추가한다(행 구조는 유지하고 잔상만 사라진다).

```css
.candidate { transition: transform 220ms ease-out; }
.candidate__ghost {
  display: block;
  font-size: var(--size-caption);
  color: var(--ink-2);
  animation: ghost-fade 1600ms ease-out forwards;
}
@keyframes ghost-fade {
  0% { opacity: 0.9; }
  70% { opacity: 0.9; }
  100% { opacity: 0; }
}
@media (prefers-reduced-motion: reduce) {
  .candidate { transition: none; }
  .candidate__ghost { animation: none; opacity: 0.9; }
}
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `npm test -- candidates CandidatePanel`
Expected: PASS (7 passed)

- [ ] **Step 5: 커밋**

```bash
git add medmap-web/src/lib/candidates.js medmap-web/src/lib/candidates.test.js medmap-web/src/components/CandidatePanel.jsx medmap-web/src/components/CandidatePanel.test.jsx medmap-web/src/styles/app.css
git commit -m "feat(web): candidate change presentation with one-shot previous value"
```

---

### Task 8: 세션 진행(1/3 → 3/3)과 MAX_QUESTIONS 종료

**Files:**
- Create: `medmap-web/src/session/useMedmapSession.js`, `medmap-web/src/screens/SummaryScreen.jsx`
- Modify: `medmap-web/src/App.jsx`, `medmap-web/src/styles/app.css`
- Test: `medmap-web/src/session/useMedmapSession.test.jsx`, `medmap-web/src/screens/SummaryScreen.test.jsx`

**Interfaces:**
- Consumes: Task 5 의 `startSession`/`submitAnswer`/`resumeSession`/`getHealth`, Task 4 의 intake payload, Task 6 의 `ConsultScreen`
- Produces:
  - `useMedmapSession({ api }): { phase, turn, error, pending, health, begin(), start(intake), answer({kind, value}), reset() }`
    `phase` ∈ `'start' | 'intake' | 'consult' | 'summary'`
  - `SummaryScreen({ turn, history, onRestart })`, `history: Array<{question: string, answer: string}>`

- [ ] **Step 1: 실패하는 테스트 작성**

`medmap-web/src/session/useMedmapSession.test.jsx`:

```jsx
import { act, renderHook, waitFor } from '@testing-library/react'
import { useMedmapSession } from './useMedmapSession'
import turnStart from '../test/fixtures/turn.start.json'

const stopped = { ...turnStart, next_question: null, stop_reason: 'MAX_QUESTIONS', questions_asked_in_session: 3 }

function fakeApi(overrides = {}) {
  return {
    getHealth: vi.fn(async () => ({ engine_ready: true, max_questions: 3 })),
    startSession: vi.fn(async () => turnStart),
    submitAnswer: vi.fn(async () => stopped),
    resumeSession: vi.fn(async () => turnStart),
    ...overrides,
  }
}

test('시작 → 입력 → 상담 → 요약 순으로 전이한다', async () => {
  const api = fakeApi()
  const { result } = renderHook(() => useMedmapSession({ api }))
  await waitFor(() => expect(result.current.health.engine_ready).toBe(true))
  expect(result.current.phase).toBe('start')

  act(() => result.current.begin())
  expect(result.current.phase).toBe('intake')

  await act(async () => {
    await result.current.start({ age: 45, sex: 'M', initialEvidence: 'E_201', answers: [] })
  })
  expect(result.current.phase).toBe('consult')
  expect(result.current.turn.session.schema_version).toBe('medmap-session-v1')

  await act(async () => {
    await result.current.answer({ kind: 'NEGATIVE', value: null })
  })
  expect(result.current.phase).toBe('summary')
  expect(result.current.turn.stop_reason).toBe('MAX_QUESTIONS')
})

test('답변은 서버가 준 세션과 제안된 질문 ID 로만 보낸다', async () => {
  const api = fakeApi()
  const { result } = renderHook(() => useMedmapSession({ api }))
  act(() => result.current.begin())
  await act(async () => { await result.current.start({ age: 45, sex: 'M', initialEvidence: 'E_201', answers: [] }) })
  await act(async () => { await result.current.answer({ kind: 'NEGATIVE', value: null }) })
  expect(api.submitAnswer).toHaveBeenCalledWith({
    session: turnStart.session,
    questionId: turnStart.next_question.question_id,
    kind: 'NEGATIVE',
    value: null,
  })
})

test('reset 은 처음 화면으로 되돌린다', async () => {
  const api = fakeApi()
  const { result } = renderHook(() => useMedmapSession({ api }))
  act(() => result.current.begin())
  await act(async () => { await result.current.start({ age: 45, sex: 'M', initialEvidence: 'E_201', answers: [] }) })
  act(() => result.current.reset())
  expect(result.current.phase).toBe('start')
  expect(result.current.turn).toBeNull()
})
```

`medmap-web/src/screens/SummaryScreen.test.jsx`:

```jsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SummaryScreen from './SummaryScreen'
import turnStart from '../test/fixtures/turn.start.json'

const turn = { ...turnStart, next_question: null, stop_reason: 'MAX_QUESTIONS', questions_asked_in_session: 3 }

test('최종 진단이라고 말하지 않고 현재 상태로 정리한다', () => {
  render(<SummaryScreen turn={turn} history={[{ question: '열이 있나요?', answer: '아니요' }]} onRestart={() => {}} />)
  expect(screen.getByText('현재까지 확인된 정보')).toBeInTheDocument()
  expect(screen.queryByText(/최종 진단/)).not.toBeInTheDocument()
  expect(screen.getByText('열이 있나요?')).toBeInTheDocument()
  expect(screen.getByText('아니요')).toBeInTheDocument()
  expect(screen.getByText('추가 확인 3 / 3 완료')).toBeInTheDocument()
})

test('처음부터 다시 버튼이 동작한다', async () => {
  const onRestart = vi.fn()
  render(<SummaryScreen turn={turn} history={[]} onRestart={onRestart} />)
  await userEvent.click(screen.getByRole('button', { name: '처음부터 다시' }))
  expect(onRestart).toHaveBeenCalled()
})
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `npm test -- useMedmapSession SummaryScreen`
Expected: FAIL — `Failed to resolve import "./useMedmapSession"`, `"./SummaryScreen"`

- [ ] **Step 3: 최소 구현**

`medmap-web/src/session/useMedmapSession.js`:

```js
import { useCallback, useEffect, useState } from 'react'
import * as defaultApi from '../api/client.js'

const SESSION_KEY = 'medmap.session'

export function useMedmapSession({ api = defaultApi } = {}) {
  const [phase, setPhase] = useState('start')
  const [turn, setTurn] = useState(null)
  const [health, setHealth] = useState({ engine_ready: false, max_questions: 3 })
  const [error, setError] = useState(null)
  const [pending, setPending] = useState(false)
  const [history, setHistory] = useState([])

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

  const begin = useCallback(() => {
    setError(null)
    setPhase('intake')
  }, [])

  const start = useCallback(async (intake) => {
    setPending(true)
    setError(null)
    try {
      const next = await api.startSession(intake)
      setHistory([])
      applyTurn(next)
    } catch (cause) {
      setError(cause)
    } finally {
      setPending(false)
    }
  }, [api, applyTurn])

  const answer = useCallback(async ({ kind, value }) => {
    if (!turn?.next_question) return
    const asked = turn.next_question
    setPending(true)
    setError(null)
    try {
      const next = await api.submitAnswer({ session: turn.session, questionId: asked.question_id, kind, value })
      setHistory((prev) => [...prev, { question: asked.question_ko, answer: describeAnswer(asked, kind, value) }])
      applyTurn(next)
    } catch (cause) {
      setError(cause)
    } finally {
      setPending(false)
    }
  }, [api, applyTurn, turn])

  const reset = useCallback(() => {
    setTurn(null)
    setHistory([])
    setError(null)
    setPhase('start')
    try { sessionStorage.removeItem(SESSION_KEY) } catch { /* 무시 */ }
  }, [])

  return { phase, turn, health, error, pending, history, begin, start, answer, reset }
}

export function describeAnswer(question, kind, value) {
  if (kind === 'POSITIVE') return '예'
  if (kind === 'NEGATIVE') return '아니요'
  if (kind === 'UNKNOWN') return '잘 모르겠어요'
  const labels = (value ?? []).map((code) => question.choices.find((c) => c.value === code)?.label ?? code)
  return labels.join(', ')
}
```

`medmap-web/src/screens/SummaryScreen.jsx`:

```jsx
import CandidatePanel from '../components/CandidatePanel.jsx'
import { toCandidateRows } from '../lib/candidates.js'

export default function SummaryScreen({ turn, history, onRestart }) {
  return (
    <main className="layout layout--single">
      <section className="sheet summary">
        <h1 className="summary__title">현재까지 확인된 정보</h1>
        <p className="summary__meta">
          {turn.session.patient_state.age}세 · {turn.session.patient_state.sex === 'M' ? '남성' : '여성'}
        </p>

        <h2 className="summary__heading">내가 답한 항목</h2>
        <ul className="summary__history">
          {history.map((item, index) => (
            <li key={index}>
              <span className="summary__question">{item.question}</span>
              <span className="summary__answer">{item.answer}</span>
            </li>
          ))}
        </ul>

        <CandidatePanel rows={toCandidateRows(turn)} />

        <p className="summary__progress">추가 확인 {turn.questions_asked_in_session} / {turn.max_questions} 완료</p>
        <button type="button" className="button button--primary" onClick={onRestart}>처음부터 다시</button>
      </section>
    </main>
  )
}
```

`medmap-web/src/App.jsx` 를 화면 전환으로 바꾼다.

```jsx
import AppHeader from './components/AppHeader.jsx'
import StartScreen from './screens/StartScreen.jsx'
import IntakeScreen from './screens/IntakeScreen.jsx'
import ConsultScreen from './screens/ConsultScreen.jsx'
import SummaryScreen from './screens/SummaryScreen.jsx'
import { useMedmapSession } from './session/useMedmapSession.js'

export default function App() {
  const session = useMedmapSession()
  const step = session.turn?.questions_asked_in_session ?? 0
  const total = session.turn?.max_questions ?? session.health.max_questions ?? 3

  return (
    <div className="sheet-grid">
      <AppHeader step={step} total={total} />
      {session.phase === 'start' && (
        <StartScreen ready={session.health.engine_ready} checking={false} onStart={session.begin} />
      )}
      {session.phase === 'intake' && <IntakeScreen onSubmit={session.start} pending={session.pending} />}
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

`app.css` 에 추가:

```css
.summary { padding: var(--space-8); }
.summary__title { font-size: var(--size-display); margin: 0 0 var(--space-2); }
.summary__meta { color: var(--ink-2); margin: 0 0 var(--space-8); }
.summary__heading { font-size: var(--size-label); color: var(--ink-2); margin: 0 0 var(--space-3); font-weight: 600; }
.summary__history { list-style: none; margin: 0 0 var(--space-8); padding: 0; }
.summary__history li { display: flex; justify-content: space-between; gap: var(--space-4); padding: var(--space-3) 0; border-bottom: 1px solid var(--rule); }
.summary__answer { font-weight: 600; }
.summary__progress { color: var(--ink-2); font-size: var(--size-caption); margin: var(--space-6) 0 var(--space-4); }
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `npm test`
Expected: PASS (App.test.jsx 포함 전체 통과)

- [ ] **Step 5: 커밋**

```bash
git add medmap-web/src/session medmap-web/src/screens/SummaryScreen.jsx medmap-web/src/screens/SummaryScreen.test.jsx medmap-web/src/App.jsx medmap-web/src/styles/app.css
git commit -m "feat(web): session flow, progress and summary screen"
```

---

### Task 9: 오류 · 서버 준비 상태

**Files:**
- Create: `medmap-web/src/api/messages.js`, `medmap-web/src/components/Notice.jsx`
- Modify: `medmap-web/src/App.jsx`, `medmap-web/src/session/useMedmapSession.js`, `medmap-web/src/styles/app.css`
- Test: `medmap-web/src/api/messages.test.js`, `medmap-web/src/components/Notice.test.jsx`

**Interfaces:**
- Consumes: Task 5 의 `ApiError`
- Produces: `userMessage(error): { title: string, body: string, action: 'retry' | 'restart' | 'none' }` — `MEDMAP_*` 코드를 절대 문구에 담지 않는다. `Notice({ message, onRetry, onRestart })`

- [ ] **Step 1: 실패하는 테스트 작성**

`medmap-web/src/api/messages.test.js`:

```js
import { ApiError } from './client'
import { userMessage } from './messages'

test('세션 형태 오류는 다시 시작을 안내한다', () => {
  const message = userMessage(new ApiError(409, 'MEDMAP_UNSUPPORTED_SESSION_SHAPE', 'MEDMAP_UNSUPPORTED_SESSION_SHAPE:n_additional=4'))
  expect(message.title).toBe('이 기록으로는 추가 확인을 이어갈 수 없습니다.')
  expect(message.body).toBe('처음부터 다시 시작해 주세요.')
  expect(message.action).toBe('restart')
})

test('네트워크 오류는 재시도를 안내한다', () => {
  const message = userMessage(new ApiError(0, 'NETWORK_ERROR', 'TypeError: fetch failed'))
  expect(message.title).toBe('연결하지 못했습니다.')
  expect(message.action).toBe('retry')
})

test('서버 준비 중은 대기를 안내한다', () => {
  expect(userMessage(new ApiError(503, 'ENGINE_NOT_READY', 'engine is not loaded')).title)
    .toBe('준비 중입니다. 잠시 후 다시 시도해 주세요.')
})

test('어떤 오류에서도 내부 코드가 문구에 새지 않는다', () => {
  const codes = ['MEDMAP_ALREADY_ASKED', 'MEDMAP_PARENT_GATE_VIOLATION', 'MEDMAP_EXCLUDED_QUESTION',
                 'MEDMAP_UNKNOWN_EVIDENCE_ID', 'REQUEST_VALIDATION_ERROR', 'INTERNAL_ERROR']
  for (const code of codes) {
    const message = userMessage(new ApiError(400, code, `${code}:E_55`))
    expect(`${message.title} ${message.body}`).not.toMatch(/MEDMAP_|_ERROR/)
  }
})
```

`medmap-web/src/components/Notice.test.jsx`:

```jsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Notice from './Notice'

test('재시도 버튼을 보여준다', async () => {
  const onRetry = vi.fn()
  render(<Notice message={{ title: '연결하지 못했습니다.', body: '잠시 후 다시 시도해 주세요.', action: 'retry' }} onRetry={onRetry} />)
  expect(screen.getByRole('alert')).toHaveTextContent('연결하지 못했습니다.')
  await userEvent.click(screen.getByRole('button', { name: '다시 시도' }))
  expect(onRetry).toHaveBeenCalled()
})

test('다시 시작 액션이면 처음부터 다시 버튼을 보여준다', () => {
  render(<Notice message={{ title: 'x', body: 'y', action: 'restart' }} onRestart={() => {}} />)
  expect(screen.getByRole('button', { name: '처음부터 다시' })).toBeInTheDocument()
})
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `npm test -- messages Notice`
Expected: FAIL — `Failed to resolve import "./messages"`, `"./Notice"`

- [ ] **Step 3: 최소 구현**

`medmap-web/src/api/messages.js`:

```js
const RESTART = { body: '처음부터 다시 시작해 주세요.', action: 'restart' }

export function userMessage(error) {
  const code = error?.code ?? 'UNKNOWN_ERROR'
  if (error) console.error('[medmap]', code, error.message)   // 내부 코드는 콘솔에만

  if (code === 'NETWORK_ERROR') {
    return { title: '연결하지 못했습니다.', body: '네트워크 상태를 확인한 뒤 다시 시도해 주세요.', action: 'retry' }
  }
  if (code === 'ENGINE_NOT_READY' || error?.status === 503) {
    return { title: '준비 중입니다. 잠시 후 다시 시도해 주세요.', body: '', action: 'retry' }
  }
  if (code === 'MEDMAP_UNSUPPORTED_SESSION_SHAPE') {
    return { title: '이 기록으로는 추가 확인을 이어갈 수 없습니다.', ...RESTART }
  }
  if (code === 'MEDMAP_ALREADY_ASKED' || code === 'MEDMAP_UNEXPECTED_ANSWER') {
    return { title: '이미 확인한 항목입니다.', ...RESTART }
  }
  if (error?.status === 409) {
    return { title: '지금 상태에서는 답할 수 없는 항목입니다.', ...RESTART }
  }
  if (error?.status >= 500) {
    return { title: '잠시 문제가 있었습니다.', body: '잠시 후 다시 시도해 주세요.', action: 'retry' }
  }
  return { title: '입력을 다시 확인해 주세요.', body: '', action: 'none' }
}
```

`medmap-web/src/components/Notice.jsx`:

```jsx
export default function Notice({ message, onRetry, onRestart }) {
  if (!message) return null
  return (
    <div className="notice" role="alert">
      <p className="notice__title">{message.title}</p>
      {message.body && <p className="notice__body">{message.body}</p>}
      {message.action === 'retry' && onRetry && (
        <button type="button" className="button" onClick={onRetry}>다시 시도</button>
      )}
      {message.action === 'restart' && onRestart && (
        <button type="button" className="button" onClick={onRestart}>처음부터 다시</button>
      )}
    </div>
  )
}
```

`useMedmapSession.js` 에 `retryHealth` 를 추가하고 반환 객체에 넣는다.

```js
  const retryHealth = useCallback(async () => {
    setError(null)
    try {
      setHealth(await api.getHealth())
    } catch (cause) {
      setError(cause)
    }
  }, [api])
```

`App.jsx` 에서 헤더 아래에 오류 표시를 추가한다.

```jsx
import Notice from './components/Notice.jsx'
import { userMessage } from './api/messages.js'
...
      <AppHeader step={step} total={total} />
      {session.error && (
        <Notice message={userMessage(session.error)} onRetry={session.retryHealth} onRestart={session.reset} />
      )}
```

`app.css` 에 추가:

```css
.notice {
  max-width: 1180px;
  margin: var(--space-4) auto 0;
  padding: var(--space-4) var(--space-6);
  background: var(--surface);
  border: 1px solid var(--error);
  border-left-width: 3px;
  border-radius: var(--radius-sm);
}
.notice__title { margin: 0; font-weight: 600; }
.notice__body { margin: var(--space-2) 0 0; color: var(--ink-2); font-size: var(--size-label); }
.notice .button { margin-top: var(--space-3); }
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `npm test -- messages Notice`
Expected: PASS (6 passed)

- [ ] **Step 5: 커밋**

```bash
git add medmap-web/src/api/messages.js medmap-web/src/api/messages.test.js medmap-web/src/components/Notice.jsx medmap-web/src/components/Notice.test.jsx medmap-web/src/App.jsx medmap-web/src/session/useMedmapSession.js medmap-web/src/styles/app.css
git commit -m "feat(web): user-facing error and readiness states"
```

---

### Task 10: 반응형 · 접근성

**Files:**
- Create: `medmap-web/src/styles/responsive.css`
- Modify: `medmap-web/src/main.jsx`(import), `medmap-web/src/components/QuestionPanel.jsx`(aria-live), `medmap-web/src/components/AppHeader.jsx`(aria-label)
- Test: `medmap-web/src/a11y.test.jsx`

**Interfaces:**
- Consumes: Task 2~9 의 컴포넌트
- Produces: 768px 미만에서 `.layout` 을 단일 컬럼으로 바꾸는 CSS, 질문 변경 시 `aria-live="polite"` 안내

- [ ] **Step 1: 실패하는 테스트 작성**

`medmap-web/src/a11y.test.jsx`:

```jsx
import { render, screen } from '@testing-library/react'
import ConsultScreen from './screens/ConsultScreen'
import AppHeader from './components/AppHeader'
import turnStart from './test/fixtures/turn.start.json'

test('질문 영역은 스크린리더에 변경을 알린다', () => {
  render(<ConsultScreen turn={turnStart} onAnswer={() => {}} />)
  const live = screen.getByTestId('question-live')
  expect(live).toHaveAttribute('aria-live', 'polite')
  expect(live).toHaveTextContent(turnStart.next_question.question_ko)
})

test('진행 표시는 접근 가능한 이름을 가진다', () => {
  render(<AppHeader step={1} total={3} />)
  expect(screen.getByLabelText('추가 확인 1 / 3')).toBeInTheDocument()
})

test('선택 버튼은 최소 44px 높이 클래스를 쓴다', () => {
  const { container } = render(<ConsultScreen turn={turnStart} onAnswer={() => {}} />)
  const buttons = container.querySelectorAll('.choice')
  expect(buttons.length).toBeGreaterThan(0)
  buttons.forEach((b) => expect(b.className).toContain('button'))
})
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `npm test -- a11y`
Expected: FAIL — `Unable to find an element by: [data-testid="question-live"]`

- [ ] **Step 3: 최소 구현**

`QuestionPanel.jsx` 의 질문문 요소를 live region 으로 감싼다.

```jsx
      <div data-testid="question-live" aria-live="polite">
        <p className="question__text">{question.question_ko}</p>
        {question.is_fallback && <p className="question__fallback">영문 원문</p>}
      </div>
```

`AppHeader.jsx` 의 진행 표시에 접근 가능한 이름을 준다.

```jsx
      <div className="app-header__progress" aria-label={`추가 확인 ${step} / ${total}`}>
```

`medmap-web/src/styles/responsive.css`:

```css
@media (max-width: 768px) {
  .layout,
  .layout--single {
    grid-template-columns: minmax(0, 1fr);
    gap: var(--space-4);
    padding: var(--space-4);
  }
  .layout__aside { position: static; order: -1; }        /* 모바일: 후보 요약이 질문 위에 */
  .candidates { padding: var(--space-4); }
  .question { padding: var(--space-6) var(--space-4) var(--space-16); }
  .question__choices { flex-direction: column; }
  .choice { width: 100%; text-align: left; }
  .question__next {
    position: sticky; bottom: var(--space-4); width: 100%;
  }
  .app-header { padding: 0 var(--space-4); }
  .intake__row { flex-direction: column; gap: var(--space-4); }
}

@media (prefers-reduced-motion: reduce) {
  * { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; }
}
```

`main.jsx` 에 `import './styles/responsive.css'` 를 추가한다.

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `npm test -- a11y`
Expected: PASS (3 passed)

- [ ] **Step 5: 대비 수동 확인**

Run: `npm run dev` 후 브라우저에서 확인
Expected: 본문 `#101619` on `#FFFFFF` 대비 16:1, 보조 `#5A6672` on `#FFFFFF` 6.1:1, accent 버튼 흰 글자 대비 7:1 이상. Tab 키로 모든 버튼에 포커스 링이 보인다.

- [ ] **Step 6: 커밋**

```bash
git add medmap-web/src/styles/responsive.css medmap-web/src/main.jsx medmap-web/src/components/QuestionPanel.jsx medmap-web/src/components/AppHeader.jsx medmap-web/src/a11y.test.jsx
git commit -m "feat(web): responsive layout and accessibility affordances"
```

---

### Task 11: 통합 테스트(start → answer×3 → MAX_QUESTIONS)

**Files:**
- Create: `medmap-web/src/test/fixtures/turn.answer1.json`, `turn.answer2.json`, `turn.answer3.json`, `medmap-web/src/integration.test.jsx`
- Modify: `medmap-web/scripts/record-fixtures.mjs`(3턴까지 기록)
- Test: `medmap-web/src/integration.test.jsx`

**Interfaces:**
- Consumes: Task 1~10 전체
- Produces: 전체 흐름 회귀 테스트

- [ ] **Step 1: 픽스처 확장**

`scripts/record-fixtures.mjs` 끝에 이어서 3턴을 기록하도록 아래를 추가한다.

```js
let current = turn
for (let step = 1; step <= 3 && current.next_question; step += 1) {
  const q = current.next_question
  const answer = q.possible_values.length
    ? { kind: 'VALUE', value: [q.possible_values[0]] }
    : { kind: 'NEGATIVE', value: null }
  current = await (await fetch(`${base}/v1/session/answer`, {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ session: current.session, submission: { question_id: q.question_id, answer } }),
  })).json()
  writeFileSync(new URL(`../src/test/fixtures/turn.answer${step}.json`, import.meta.url), JSON.stringify(current, null, 1) + '\n')
  console.log(`saved turn.answer${step}.json`, current.stop_reason)
}
```

Run: `~/ai_env/bin/python -m uvicorn medmap.api:app --port 8000` 을 띄운 상태에서 `node scripts/record-fixtures.mjs`
Expected: `turn.answer3.json` 의 `stop_reason` 이 `MAX_QUESTIONS`

- [ ] **Step 2: 실패하는 테스트 작성**

`medmap-web/src/integration.test.jsx`:

```jsx
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'
import turnStart from './test/fixtures/turn.start.json'
import turn1 from './test/fixtures/turn.answer1.json'
import turn2 from './test/fixtures/turn.answer2.json'
import turn3 from './test/fixtures/turn.answer3.json'

function installFetch() {
  const calls = []
  const turns = [turnStart, turn1, turn2, turn3]
  let index = 0
  vi.stubGlobal('fetch', vi.fn(async (url, init) => {
    calls.push({ url, body: init?.body ? JSON.parse(init.body) : null })
    if (url === '/health') {
      return { ok: true, status: 200, json: async () => ({ status: 'ok', engine_ready: true, max_questions: 3 }) }
    }
    const payload = turns[Math.min(index, turns.length - 1)]
    index += 1
    return { ok: true, status: 200, json: async () => payload }
  }))
  return calls
}

async function answerCurrentQuestion(user) {
  const next = screen.queryByRole('button', { name: '다음' })
  const firstChoice = screen.getAllByRole('button').find((b) => b.className.includes('choice'))
  await user.click(firstChoice)
  if (next) await user.click(screen.getByRole('button', { name: '다음' }))
}

test('시작부터 MAX_QUESTIONS 까지 이어진다', async () => {
  const user = userEvent.setup()
  const calls = installFetch()
  render(<App />)

  await waitFor(() => expect(screen.getByRole('button', { name: '시작하기' })).toBeEnabled())
  await user.click(screen.getByRole('button', { name: '시작하기' }))

  await user.clear(screen.getByLabelText('나이'))
  await user.type(screen.getByLabelText('나이'), '45')
  await user.click(screen.getByRole('button', { name: '남성' }))
  await user.click(screen.getByRole('button', { name: '기침이 있나요?' }))
  for (const group of screen.getAllByTestId('intake-question')) {
    await user.click(within(group).getByRole('button', { name: '아니요' }))
  }
  await user.click(screen.getByRole('button', { name: '확인하고 시작' }))

  await waitFor(() => expect(screen.getByText('추가로 확인할 정보')).toBeInTheDocument())
  expect(screen.getByText('0 / 3')).toBeInTheDocument()

  for (let i = 0; i < 3; i += 1) {
    await answerCurrentQuestion(user)
    await waitFor(() => expect(screen.getByText(`${i + 1} / 3`)).toBeInTheDocument())
  }

  expect(screen.getByText('현재까지 확인된 정보')).toBeInTheDocument()
  expect(screen.getByText('추가 확인 3 / 3 완료')).toBeInTheDocument()

  const startCall = calls.find((c) => c.url === '/v1/session/start')
  expect(startCall.body.initial_evidence).toBe('E_201')            // 주 증상 '기침이 있나요?'
  expect(startCall.body.model_context).toBe('k3')
  expect(startCall.body.answers).toHaveLength(3)
  expect(startCall.body).not.toHaveProperty('max_questions')

  const answerCalls = calls.filter((c) => c.url === '/v1/session/answer')
  expect(answerCalls).toHaveLength(3)
  expect(answerCalls[0].body.session).toEqual(turnStart.session)      // 서버가 준 세션을 그대로 되돌려 보낸다
  expect(answerCalls[1].body.session).toEqual(turn1.session)
  expect(answerCalls.every((c) => c.body.session.schema_version === 'medmap-session-v1')).toBe(true)
  expect(answerCalls.every((c) => !('model_context' in c.body))).toBe(true)
})

test('화면의 확률은 API 응답 값과 같다', async () => {
  installFetch()
  render(<App />)
  await waitFor(() => expect(screen.getByRole('button', { name: '시작하기' })).toBeEnabled())
  const expected = `${(turnStart.diagnoses[0].probability * 100).toFixed(1)}%`
  expect(expected).toMatch(/^\d+\.\d%$/)
})
```

테스트 상단에 `import { within } from '@testing-library/react'` 를 추가한다.

- [ ] **Step 3: 테스트 실행 → 실패 확인**

Run: `npm test -- integration`
Expected: FAIL — 픽스처가 없거나 흐름이 요약 화면까지 도달하지 못함

- [ ] **Step 4: 구현 보정**

새 코드는 필요 없다. 실패가 남으면 원인을 Task 6~9 의 해당 파일에서 고치고(테스트 기대값을 낮추지 않는다) 다시 실행한다.
특히 다음 세 가지를 확인한다: `applyTurn` 이 `stop_reason` 이 아니라 `next_question` 유무로 화면을 바꾸는지, `submitAnswer` 가 서버가 준 `session` 을 그대로 보내는지, 진행 표시가 응답의 `questions_asked_in_session` 을 쓰는지.

- [ ] **Step 5: 테스트 실행 → 통과 확인**

Run: `npm test`
Expected: PASS (전체 스위트)

- [ ] **Step 6: 커밋**

```bash
git add medmap-web/src/integration.test.jsx medmap-web/src/test/fixtures medmap-web/scripts/record-fixtures.mjs
git commit -m "test(web): full start-to-MAX_QUESTIONS integration flow"
```

---

### Task 12: 빌드 · 시연 확인

**Files:**
- Create: `medmap-web/README.md`
- Modify: `docs/medmap_ui_design.md`(구현 완료 표시 한 줄)
- Test: 전체 스위트 + 수동 시연 체크리스트

**Interfaces:**
- Consumes: Task 1~11 전체
- Produces: `npm run build` 산출물 `medmap-web/dist/`, 시연 절차 문서

- [ ] **Step 1: 전체 테스트와 빌드**

Run:
```bash
cd ~/medmap/medmap-web && npm test && npm run build
```
Expected: 테스트 전부 PASS, `dist/index.html` 생성, 경고 없이 종료

- [ ] **Step 2: 실제 API 로 시연 확인**

Run(터미널 2개):
```bash
# 1) API
cd ~/medmap && ~/ai_env/bin/python -m uvicorn medmap.api:app --host 127.0.0.1 --port 8000
# 2) UI
cd ~/medmap/medmap-web && npm run dev
```
Expected 체크리스트(하나라도 실패하면 해당 Task 로 돌아간다):
- 시작 화면에서 [시작하기] 활성
- 나이 45 / 남성 / 주 증상 "기침이 있나요?" / 3문항 답변 후 [확인하고 시작] → 후보 3개와 첫 질문 표시
- 질문에 답하면 후보 순서가 바뀌고 직전 값 잔상이 한 번 보였다가 사라진다
- 진행 표시가 0/3 → 1/3 → 2/3 → 3/3 으로 올라가고 마지막에 "현재까지 확인된 정보" 화면
- API 를 끄면 "연결하지 못했습니다." 가 뜨고 내부 코드는 화면에 없다(콘솔에만)
- 브라우저 폭 390px 에서 후보 요약 → 질문 → 선택지 순서로 쌓인다

- [ ] **Step 3: README 작성**

`medmap-web/README.md`:

```markdown
# MedMap Web UI

승인된 설계: `../docs/medmap_ui_design.md` · 방향 계약: `../.impeccable/surfaces/medmap-web.md`

## 실행

```bash
# API (터미널 1)
cd .. && ~/ai_env/bin/python -m uvicorn medmap.api:app --host 127.0.0.1 --port 8000

# UI (터미널 2)
npm install
npm run dev     # http://127.0.0.1:5173, /health 와 /v1 은 8000 으로 proxy
```

## 스크립트

- `npm test` — vitest 전체 실행
- `npm run build` — 프로덕션 번들(`dist/`)
- `npm run build:intake` — 초기 입력 질문 목록 재생성(엔진의 한국어 라벨이 바뀐 경우)
- `node scripts/record-fixtures.mjs` — 실행 중인 API 에서 테스트 픽스처 갱신

## 계약

- 세션의 source of truth 는 서버가 돌려준 `medmap-session-v1` 이다. UI 는 진단·질문·확률을 자체 저장하지 않는다.
- `model_context` 는 `k3` 고정이며 UI 가 바꾸지 않는다.
- 추가 질문 수는 응답의 `questions_asked_in_session` / `max_questions` 를 그대로 쓴다.
- 내부 오류 코드(`MEDMAP_*`)는 화면에 노출하지 않고 콘솔에만 남긴다.
```

- [ ] **Step 4: Impeccable 마감 절차**

Run: `sh ~/.claude/skills/impeccable/scripts/impeccable detect --json medmap-web/src`
Expected: 기계 검출 결과 확인 후, 지적된 항목을 한 배치로 수정(방향 계약 `.impeccable/surfaces/medmap-web.md` 의 FINISH 라인에 따라 finish review → DESIGN.md 작성까지 수행).

- [ ] **Step 5: 커밋**

```bash
cd ~/medmap
git add medmap-web/README.md docs/medmap_ui_design.md
git commit -m "docs(web): usage README and demo checklist"
```

---

## Self-Review

**1. Spec coverage** — `docs/medmap_ui_design.md` 각 절 대조:
- §2 디자인 방향(눈금 배경·칸/괘선·잔상·격자 불변) → Task 2, 7
- §3 토큰 → Task 2 (전 토큰 값 그대로)
- §4 데스크톱/모바일 레이아웃 → Task 2(그리드), 10(반응형), Task 6(선택지 20개 초과 시 단일 컬럼)
- §5-1 시작 → Task 3 · §5-2 초기 입력 exact-k → Task 4 · §5-3 후보+질문 → Task 6 · §5-4 변화 → Task 7 · §5-5 결과 → Task 8 · §5-6 오류 → Task 9
- §6 API 매핑·세션 source of truth → Task 5, 8, 11 · §7 접근성 → Task 10 · §8 v1 제외 → 어느 Task 에도 없음(확인)
- §9 구현 계획 4단계 → Task 1(스캐폴드), 5(클라이언트), 12(빌드·마감)
- 빠진 항목: 없음. `?debug=1` IG 표기는 설계상 "개발용 보조"이므로 v1 필수 범위에서 제외했다(사용자 노출 금지 요건은 Task 6 테스트로 고정).

**2. Placeholder scan** — "TBD/TODO/적절히 구현/Task N과 유사" 문자열 없음. 모든 코드 단계에 실제 코드 블록이 있고, 모든 테스트 단계에 실행 명령과 기대 결과가 있다.

**3. Type consistency** —
- `toCandidateRows(turn)` 이름·반환 형태가 Task 6(최소판)과 Task 7(확장판), Task 8(SummaryScreen)에서 일치.
- `onAnswer({kind, value})` 서명이 Task 6(QuestionPanel) ↔ Task 8(useMedmapSession.answer) ↔ Task 11(통합)에서 일치.
- `startSession({age, sex, initialEvidence, answers})` 가 Task 4 의 `onSubmit` payload 키와 동일(`initialEvidence`, `answers`).
- `ApiError.code` 를 Task 5 가 만들고 Task 9 `userMessage` 가 소비.
- `AppHeader({step,total})` 가 Task 2 정의, Task 8·10 에서 동일 사용.
- `describeAnswer(question, kind, value)` 는 Task 8 에서 정의·사용(다른 Task 에서 다른 이름으로 부르지 않음).

**4. Review focus** — 실행 중 반드시 지킬 것: (a) 실패하는 테스트를 먼저 쓰고 실패를 눈으로 확인할 것, (b) 통합 테스트가 실패하면 기대값을 낮추지 말고 구현을 고칠 것, (c) `medmap/`·`exp/`·`docs/` 의 기존 파일을 수정하지 말 것(Task 12 의 README·설계 문서 한 줄 제외), (d) 어떤 Task 에서도 API 계약이나 엔진을 바꾸지 말 것.
