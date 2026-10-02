# MedMap Clinical Summary UI — bounded 계약 (2026-09-27 승인)

branch `feat/clinical-summary-ui` (master `447527d`) · worktree `~/medmap-worktrees/clinical-summary-ui` (data·pkl·stt/samples read-only symlink)
근거: audit P2-1(새로고침 후 요약 기록 유실)·P2-6(요약에 주 증상·확인 항목·안내 없음). 기존 `medmap/clinical_summary.py`가 single source of truth.

## 금지
C(korean-terminology)·D worktree 접근·C 코드 복사·별도 번역 테이블 · frozen 매퍼·diagnosis model·IG · 기존 6 endpoint request/response 의미 변경 · 서버 저장·DB·transcript/raw text/matched_text 저장·payload 로그 · 새 clinical inference · 새 dependency · UI redesign(기존 plain.css class만) · P2-4(시작 전 새로고침/START_INCOMPLETE) 혼합.

## Backend — `POST /v1/session/summary` (medmap/api.py, 추가만)
- 요청 모델 `SummaryRequest{session: dict}`(extra=forbid). 형식 오류 → 기존 422 `REQUEST_VALIDATION_ERROR`.
- 처리: `state, model_context = _restore(body.session)`(기존 검증기; 무효 세션은 기존 핸들러 400/409 그대로) → `payload = _run(state, model_context)`(= `/session/resume`과 같은 공식 경로, 상태 불변·결정적) → `clinical_summary.summary_from_session(body.session, payload["diagnoses"], catalog=registry.catalog, labels=PresenterLabelProvider(registry.catalog, registry.presenter))` → 그 dict를 그대로 반환(`medmap-clinical-summary-v1`, 키 = `clinical_summary.SUMMARY_KEYS`).
- `PresenterLabelProvider`는 레지스트리 초기화 때 1회 생성해 재사용해도 됨(추가만).
- summary 로직을 endpoint에 복제하지 않는다. 로그: 결과 코드·ms만(access log 기존). `LOG_PAYLOAD`로 summary·session을 찍지 않는다.
- 테스트 `tests/test_summary_api.py`(실제 엔진, GPU 불필요): valid session(start→answer×3로 만든 종료 세션) → 200, 키 = SUMMARY_KEYS, schema_version · 같은 세션 2회 → 완전히 같은 JSON · malformed(`session` 누락/문자열) → 422 · invalid session(schema_version 틀림 / 부모 없는 자식 답 등 기존 SessionValidationError) → 기존 /resume과 같은 status·code · 응답 전체 문자열에 `transcript`·`matched_text`·원문 없음 · intake cache로만 확인된(세션에 반영 안 된) NEGATIVE evidence가 summary 어디에도 없음 · bootstrap UNKNOWN(세션 미전송)이 `unknown`에 없음 · `diagnosis_candidates`의 name·probability가 같은 세션 `/session/resume` 응답 `diagnoses` top3와 일치 · 호출 전후 세션 불변 + 기존 /start /answer /resume 회귀(기존 테스트 전부 통과).

## Frontend
- `src/api/client.js`: `getSummary(session)` → POST `/v1/session/summary` `{session}`.
- `src/session/useMedmapSession.js`: `summary`, `summaryState: 'idle'|'loading'|'ready'|'error'`, `retrySummary()` 추가.
  - phase가 `summary`가 되는 모든 경로(answer/start/settle 종료, 새로고침 resume로 summary 복원)에서 현재 `turn.session`으로 `getSummary` 호출(같은 세션으로 중복 호출 방지).
  - 실패: `NETWORK_ERROR`·status ≥ 500 → 세션·cache 보존, `summaryState='error'`, `retrySummary()`는 같은 session으로 재호출(처리 중 중복 방지). 4xx → 기존 resume 4xx 정책과 동일(저장 세션·cache 폐기, 시작 화면, 조용히).
  - summary는 메모리에만(스토리지 저장 금지). reset 시 초기화.
- `src/screens/SummaryScreen.jsx`(props: `turn, summary, summaryState, onRetrySummary, onRestart`): 제목 `현재까지 확인된 정보` + 나이·성별(기존).
  - loading: `요약을 불러오는 중입니다.`(role=status). error: `요약 정보를 불러오지 못했습니다.`(role=alert) + [다시 시도](→ onRetrySummary, 처리 중 비활성). 이때도 진단 후보(turn 기준)와 [처음부터 다시]는 유지.
  - ready 표시 순서(schema에 있는 필드만): 1 주 증상(`chief_complaint.label_ko ?? question_ko`) → 2 있다고 확인한 증상(`confirmed_positive`) → 3 없다고 확인한 증상(`confirmed_negative`) → 4 선택한 값(`confirmed_values`: question_ko + answer_ko) → 5 해당 없음(`not_applicable`) → (schema의 `unknown`이 비어 있지 않으면 `잘 모르겠다고 답한 질문`) → 6 `답한 질문 N개 · 추가 확인 {questions_used} / {turn.max_questions}` → 7 `현재 확인이 필요한 진단 후보`(`diagnosis_candidates`의 `display_name`·`probability`, 기존 CandidatePanel 재사용 가능) → 8 안내 문구(`disclaimer`, `\n` 줄바꿈 유지).
  - 빈 섹션은 숨긴다. `최종 진단`·`확정 진단` 문구 금지. `is_fallback` 항목(영어)은 그대로 표시(crash 없음) — C 병합 후 LabelProvider 교체로 자동 한국어.
  - UI-local `history`는 더 이상 요약 목록의 근거가 아니다(요약은 summary API 기준).
- 기존 SummaryScreen 테스트가 history 목록을 단언하면, 새 계약(summary 기반)으로 **목적을 유지한 채 갱신**하고 보고(최종 진단 금지·처음부터 다시 단언은 유지).
- 테스트: 진입 시 summary API 호출 · 새로고침(resume→summary) 후 같은 세션으로 재호출·목록 복원 · history 비어도 목록 표시 · 5xx → 세션 보존 + 다시 시도 → 성공 · 4xx → 폐기 · 안내 문구 · `최종 진단`/`확정 진단` 없음 · 후보 표시 · is_fallback(영어) 항목에도 정상 렌더.

## E2E — `medmap-web/e2e/summary.e2e.mjs`(실서버, 텍스트, GPU 불필요)
1 정상: 텍스트 → 3질문 → 요약 → 답한 항목 목록 존재(주 증상 + 확인 목록, `답한 질문 N개`) · 2 요약에서 reload → 같은 요약(섹션 텍스트 동일, N 동일) · 3 상담 중 reload → resume → 끝까지 → 요약 정상 · 4 `/v1/session/summary` 1회 500 가로채기 → 세션 유지(sessionStorage `medmap.session` 존재) → [다시 시도] → 요약 표시. 실패 시 exit 1, 성공 `SUMMARY_E2E_OK`.
