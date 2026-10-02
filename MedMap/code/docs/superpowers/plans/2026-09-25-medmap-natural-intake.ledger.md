# 실행 원장 — MedMap Natural Intake (feat/natural-intake)

계획: `docs/superpowers/plans/2026-09-25-medmap-natural-intake.md`(rev2) · 방식: Subagent-driven · worktree: `~/medmap-worktrees/natural-intake` · 기반: master `b89b1de`

## Plan revisions

### rev2 (2026-09-25) — 사용자 피드백 9항
1. 구현은 전용 worktree에서만. 무시된 입력은 원본을 가리키는 read-only symlink(`data`, `model_k{3,5,10}.pkl`). master 작업 트리에 구현 변경 0.
2. start feature = 확인된 POSITIVE(initial·additional)만. 확인된 NEGATIVE는 additional에서 빼고 cache에 보존, 엔진이 실제로 제안할 때만 적용.
3. bootstrap UNKNOWN = 기록만(요약 history), exact-k count·`/start` 본문 제외, 다음 frozen 질문으로. 채울 수 없으면 `START_INCOMPLETE`(start 미호출).
4. 위 규칙 테스트 추가(startPlan·NaturalIntakeScreen·hook·integration·backend e2e).
5. 신규 백엔드 테스트 수 = catalog 9 + intake_api 8 + e2e 4 = 21.
6. Task 0에 V1 CSS 의존 preflight 추가.
7. human gate는 의미가 애매한 신규 라벨만. npm ci(lockfile 무변경)·로컬 서버·스크린샷은 무승인.
8. Subagent-driven 절차.
9. design PAUSED, STT scope 밖 유지.

## Preflight (Task 0)

| 항목 | 결과 |
|---|---|
| worktree | `git worktree add -b feat/natural-intake ~/medmap-worktrees/natural-intake master` → HEAD `b89b1de` |
| symlink | `data -> ~/medmap/data`, `exp/step16b_next_information_validation/model_k{3,5,10}.pkl -> ~/medmap/…`. `git status --ignored`: 4개 모두 `!!`(무시), 추적 변경 0 |
| exclude | `~/medmap/.git/info/exclude`에 `/data` 1줄 추가(디렉터리 규칙 `data/`는 symlink를 무시하지 못함). 저장소 공통 exclude — 메인 체크아웃의 `data/`는 이미 무시되고 있어 영향 없음 |
| master 작업 트리 | `?? exp/step17a_intake_start_validation/`뿐. 계획 초안 2개는 master 작업 트리에서 worktree로 이동(mv) |
| V1 CSS 의존 | **PASS** — 재사용 8개 컴포넌트 모두 CSS import 없음, `getComputedStyle` 없음. className은 markup hook(테스트 선택자 `.choice`·`.app-header__brand`·`.candidate__bar`·`.candidate__ghost`). 인라인 style은 막대 폭(확률 비례)·헤더 점 배치뿐. plain.css가 최소 스타일만 정의(ghost는 "이전 N%" 텍스트) |
| 백엔드 기준선 | worktree에서 `unittest discover -s tests` → **Ran 121 tests OK**(`logs/ni_baseline_backend_*.log`) — symlink로 모델 로딩 확인 |
| 프론트 기준선(참고) | feat/web-ui worktree `npx vitest run` → 17 files / **54 passed**. 이 브랜치로는 IntakeScreen·responsive·intake 데이터 테스트를 가져오지 않으므로 수가 다르다 |

## Rulings

### Ruling 1 — bootstrap이 확인된 NEGATIVE 항목도 건너뜀 (rev2 §2·§3)
**충돌:** STEP17A R2/R3는 "initial이거나 이미 공개된 항목은 건너뛴다". rev2에서 확인된 NEGATIVE는 start에 공개하지 않으므로, 문자 그대로면 bootstrap이 같은 질문(예: E_91 "열이 있나요?")을 다시 물을 수 있다.
**판단:** 사용자 지시 "중복 시 frozen backup 사용"에 따라 확인된 모든 항목(POSITIVE·NEGATIVE)을 건너뛰고 예비로 채운다. 같은 질문 재질문 없음. 순서 자체는 불변.

### Ruling 2 — START_INCOMPLETE 조기 판정
**충돌:** 사용자 문구는 "backup을 모두 소진했는데 3개를 채우지 못하면". 남은 질문을 다 답해도 부족분에 못 미치는 시점(`known + 남은 질문 수 < 부족분`)에서 이미 결과가 정해진다.
**판단:** 그 시점에 `START_INCOMPLETE`로 끝낸다. 채울 수 없는 질문을 더 묻지 않는다. `/session/start` 미호출은 동일.

### Ruling 3 — 애매한 라벨 판정 (Task 2 human gate)
신규 69개 중 원문 뜻이 하나로 정해지지 않아 임의 번역이 필요한 것: `E_150`, `E_202`, `E_13`. 나머지 66개는 초안대로 진행. `E_188`은 "흰 변"(의역) → "색이 옅은 변"(직역)으로 정정. 초안 SHA `465c3dcf…`(검수 반영 전).

### Ruling 4 — E_202 설명 문장도 질환명 제거
**충돌:** 사용자는 E_202 라벨을 "질환명 대신 관찰 가능한 증상 표현"으로 확정했으나 초안 `detail_ko`는 "백일해(발작적으로 몰아치는 기침)가 있나요?"로 질환명을 포함했다(검색 결과에 보임).
**판단:** 같은 이유로 `detail_ko`를 "몰아치듯 기침한 뒤 숨을 들이쉴 때 소리가 나는 발작적인 기침이 있나요?"로 맞췄다. 라벨은 사용자 문구 그대로.

### Ruling 5 — rev3: 도달한 확인 NEGATIVE 재사용 (Ruling 1 대체, 2026-09-26 사용자 결정)
**결정:** 확인된 NEGATIVE는 기본 cache. frozen bootstrap/backup 순서에서 이번 start를 채우려고 walk가 실제로 도달하는 항목이면 그 답을 bootstrap 답으로 재사용한다(1개로 계수, 재질문 없음, cache 제외). 도달하지 않거나 목록 밖이면 cache 유지. UNKNOWN은 비계수·다음 backup.
**효과:** 도달한 항목의 시작 상태가 STEP17A R2/R3(해당 항목의 실제 답 공개)와 같아졌다. 남은 차이는 UNKNOWN 처리(시뮬레이션에 없음)와 "발화 순서 앞 3개" heuristic.

## Task log

| Task | 상태 | 커밋 | 리뷰 | 비고 |
|---|---|---|---|---|
| 0 Preflight | DONE | (이 커밋) | coordinator | 위 표 |
| 1 feat/web-ui 기능 로직 import + plain.css | DONE | `d74a72e` | 독립 리뷰 APPROVED(7항목 PASS) | 재사용 34개 중 31개 byte-identical, 3개(package.json scripts·index.html CDN 제거·main.jsx CSS import)만 계획된 수정. lockfile 동일(`git show … \| diff` 직접 비교 — 체크아웃 후 reset으로 untracked 상태라 `git diff feat/web-ui --`는 오탐), npm ci 101 packages, vitest 12 files / 41 passed, NO_IGNORED_SOURCE |
| 2 initial 96 라벨 | GATE PASSED | — | — | 사용자 확정: E_150 "대변·방귀 배출 가능 여부", E_202 "숨 들이쉴 때 소리가 나는 발작적 기침", E_13 "2주 사이 악화·적은 활동에도 증상 발생". 나머지 66개·E_188 승인. 초안 SHA `15c89226…` |
| 3 POST /v1/intake/extract | DONE | `7b2c403` | APPROVED | 추가만(삭제 0), 원문 로그·에코 경로 없음(422 msg·500 경로 확인) |
| 4 백엔드 e2e | DONE | `e480e55` | APPROVED | 4/4. 엔진 제안 C=E_129, E=E_55 → cache 적용 200 분기는 백엔드에서 미실행(프론트 D·D-NEGATIVE·기존 test_api 답변 경로가 커버) |
| 5 intake 규칙 모듈 | DONE | `82f6c84` | APPROVED | 편차: 테스트 fixture 경로를 `new URL(rel, import.meta.url)`→`dirname(fileURLToPath)+join`(Vite가 http URL로 재작성). 단언 무변경 |
| 6 컴포넌트 4개 | DONE | `d67ec03` | APPROVED | 편차 없음 |
| 7 NaturalIntakeScreen | DONE | `e455d4b` | APPROVED | 편차 없음 |
| 8 세션 훅 | DONE | `94f08ff` | APPROVED(opus) | StrictMode 중복 제출 경로 없음 확인 |
| 9 App + 통합 A–G | DONE | `f478879` | APPROVED | 통합 9개(A,B,B-UNKNOWN,B-INCOMPLETE,C,D,E,D-NEGATIVE,G) |
| 10 실서버 e2e + README | DONE | `223aae6` | APPROVED | 편차: e2e 시나리오 B '기침' locator에 `exact: true`(strict mode) |
| whole-branch review | APPROVED_WITH_MINOR(opus) | — | — | CRITICAL/MAJOR 0, MINOR 7 |
| minor 수정 | DONE | `0795f11` | 재리뷰 APPROVED | #1 start 실패 재시도, #3 confirmed 중복 제거, #5 cache 적용 중 세션 저장, #2·#6 README. 미수정(범위 밖): #4 'none'에서 다시 적기, #7 있음/예 라벨 통일 |

## Final verification (coordinator, 2026-09-25)
- 백엔드 `unittest discover -s tests` → Ran 142 OK (skipped=1) = 기준 121 + 신규 21(catalog 9 + intake_api 8 + e2e 4)
- 프론트 `vitest run` → 22 files / 102 passed · `npm run build` OK
- 실서버(worktree, uvicorn :8000 + vite :5173, ram_guard 동반) Playwright e2e A·B × 390/1280 → `E2E_OK`(overflow·원문 노출 0). 서버 종료, 포트 해제 확인
- `git diff master -- medmap/api.py` 삭제 0 · `medmap/intake`·`tests/fixtures` 무변경 · master 작업 트리 `?? exp/step17a_intake_start_validation/`뿐 · feat/web-ui·design/web-ui-v2·research/step17a 미포함
- 남은 사용자 결정: 확인 NEGATIVE가 bootstrap 목록 항목일 때 STEP17A R2/R3처럼 시작 상태에 넣을지(현재 rev2 §2대로 cache)
| rev3 확인 NEGATIVE 재사용 | DONE | `d782291` + 문서 커밋 | opus 리뷰: 로직 PASS, README 33행 rev2 문구 1건 → coordinator 수정 | walkBootstrap 도입. vitest 108, backend 142 OK(skip 1), 테스트 수 유지(e2e 4) |
