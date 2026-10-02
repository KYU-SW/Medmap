# 실행 원장 — MedMap Clinical Summary (feat/clinical-summary)

계획: `docs/superpowers/plans/2026-09-26-medmap-clinical-summary.md`(rev1, 설계 단계) · 방식: Subagent-driven(승인 후) · worktree: `~/medmap-worktrees/clinical-summary` · 기반: master `336463f`

## Plan revisions

### rev1 (2026-09-26) — 설계 초안
- 판정 BOUNDED: 새 모듈 `medmap/clinical_summary.py` + 테스트만, 기존 모듈·api.py·프론트 무수정.
- 계약 `medmap-clinical-summary-v1`(파생값, 저장 안 함, PatientState에서 재구성).
- 사용자 결정 대기: D1(cache NEGATIVE·bootstrap UNKNOWN 포함 여부), D2(API router 시점·notice 문구), D3(`schema_version` 키·추가 키 허용).

### rev2 (2026-09-26) — 사용자 승인 B1–B3
1. B1: PatientState에서 재구성되지 않는 것(intake cache 미적용 NEGATIVE, 세션 밖 bootstrap UNKNOWN) 제외. 새로고침 전후 동일이 최우선.
2. B2: core builder + 스키마 + 단위 테스트만. api.py 0줄, UI/PDF/인쇄/복사/LLM 제외.
3. B3: `schema_version`, 최종 키 11개(사용자 권장 9 + `unknown`·`answered_questions`). `display.notice_ko` → top-level `disclaimer`(한 문자열, `\n` 두 줄). rev1의 model_context·patient·max_questions·stop_reason·session_shape·source_session_schema·section_titles·Item.source 삭제.

## Preflight (Task 0)

| 항목 | 결과 |
|---|---|
| worktree | `~/medmap-worktrees/clinical-summary`, 브랜치 `feat/clinical-summary`, 기반 `336463f` |
| symlink | `data`, `exp/step16b_next_information_validation/model_k{3,5,10}.pkl` → `~/medmap/…`(read-only, 수정 금지) |
| 기준선 | 다른 세션 확인값: backend 142 OK(skip 1), vitest 108/108, build OK — 이 세션에서는 재실행하지 않음 |
| 기존 모듈 무수정 기준 | `git diff 336463f --stat -- medmap/api.py medmap/patient_state.py medmap/serialization.py medmap-web` 빈 출력(구현 후 재확인) |
| node_modules | worktree에 없음 → `~/medmap/medmap-web/node_modules`(83MB)를 `cp -a`로 복사, `.vite` 캐시 제외. npm install 없음, package-lock.json 336463f와 동일(diff 0). master 쪽은 읽기만. cp -a는 네트워크 설치를 피하려는 것일 뿐이며, 같은 node_modules는 변경 없는 package-lock.json에서 `npm ci`로 재현 가능 |
| 테스트 데이터 출처 | `data/ddxplus/en/release_evidences.json` ← `scripts/download_public.sh` (figshare files/40278013). worktree는 `~/medmap/data` symlink |
| 자원 | 시작 시 RAM available 12.6GB, GPU 789MiB/8188MiB(타 세션). 테스트는 nice 19·OMP 2, GPU 미사용 |

## Rulings

### Ruling 1 — questions_used = null 허용
사용자 "추정 null 금지"와 `n_additional < k` 상태가 충돌. `null`은 API `questions_asked_in_session`이 이미 쓰는 "판정 불가" 표기(`api.py:228-240`)라 추정값이 아니다 → 그대로 둔다. 정상 세션(exact-k start)에서는 항상 정수.

### Ruling 2 — Item.source 제거
initial/start/engine 구분은 exact-k 가정에 기댄 추론이고 비정상 형태에서는 추정이 된다 → B3 "재구성 가능한 값만"에 따라 제거. 물은 순서는 `answered_questions`로 보존.

### Ruling 3 — 후보 입력 검증
top3 입력이 내림차순이 아니거나 확률이 [0,1] 밖이면 `ValueError`(조용한 정렬·보정 없음, serialization 원칙과 동일).
- 리뷰 MINOR(정렬 검증이 top3 절단 전 전체 입력에 적용되는 범위 문제, `clinical_summary.py` 정렬 검사 블록): **검토 후 유지**(리뷰어 지시). 동작 변경 없음.

### Ruling 4 — 리뷰 후속 수정 (2026-09-26)
1. asked에 있으나 answers에 없는 항목: 조용히 건너뛰던 것을 `ValueError("MEDMAP_SUMMARY_ASKED_WITHOUT_ANSWER:<id>")`로 변경. `PatientState.__post_init__`은 answers ⊆ asked만 검사하므로 이런 상태를 직접 만들 수 있다 → 테스트 08b로 고정.
2. tuple 후보 unpack 실패(길이 불일치·비iterable)도 dict 분기와 같은 `MEDMAP_SUMMARY_INVALID_CANDIDATE`로 변경 → 테스트 16b.
3. `requirements-api.txt` 버전 미고정: 프로젝트 공통, 범위 밖(고정하지 않음).

## Review / Audit

| 항목 | 판정 | 후속 |
|---|---|---|
| 독립 코드 리뷰 | APPROVED_WITH_MINOR | MINOR 1·2 수정(Ruling 4), 정렬 범위 MINOR는 유지(Ruling 3) |
| 재현성 감사 | PARTIALLY_REPRODUCIBLE | 데이터 출처(`scripts/download_public.sh`)·`npm ci` 재현 경로 문서화. requirements 미고정은 범위 밖 |

## Task log

| Task | 상태 | 커밋 | 리뷰 | 비고 |
|---|---|---|---|---|
| 설계 문서 | DONE | `e29f413` | — | 승인 게이트에서 정지 → 사용자 승인 |
| 0 Preflight | DONE | — | coordinator | 위 표 |
| 1–3 core + 어댑터 + fixture (TDD) | DONE | `25e4f75` | 별도 리뷰어 대기 | RED: 테스트 먼저 작성 → ImportError 확인. GREEN: 23/23. fixture `tests/fixtures/clinical_summary_turn_answer3.json` = 프론트 `turn.answer3.json` 사본(테스트 23으로 동일성 확인) |
| 4 전체 회귀 | DONE | `93092c2` | — | backend `Ran 165 tests OK (skipped=1)` = 142 + 23 (`logs/cs_backend_full_20260926_1827.log`) · vitest 22 files / 108 passed · build OK (`logs/cs_frontend_20260926_1827.log`). api.py·기존 모듈·프론트 diff 0 |
| 5 리뷰 후속(Ruling 4) | DONE | (다음 커밋 — `git log --grep "review follow-ups"`) | 리뷰 지시 반영 | TDD: 08b·16b 추가 → RED(failures=2) → GREEN 25/25. backend `Ran 167 tests OK (skipped=1)` (`logs/cs_backend_full_r2_20260926_1834.log`) · vitest 22 files / 108 passed · build OK (`logs/cs_frontend_r2_20260926_1834.log`) |
