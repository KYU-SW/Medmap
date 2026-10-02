# MedMap Flow Hardening — bounded 계약 (2026-09-26)

branch `feat/flow-hardening` (master `43d5a85`) · worktree `~/medmap-worktrees/flow-hardening` (data·pkl·stt/samples read-only symlink)
근거: 2026-09-26 MEDMAP INTEGRATED PRODUCT AUDIT(P2-2·P2-3·P2-5, 테스트 공백).

## 금지
Korean terminology·C/D worktree·frozen 매퍼·diagnosis model·IG scoring·UI redesign·새 dependency·backend API 계약 변경. 기존 테스트 단언 약화 금지(추가만).

## Task 1 — STT transcribing lock
- `VoiceInput`에 `onBusyChange(busy: boolean)` prop 추가: `state === 'transcribing'`일 때 true, 완료·오류·idle 복귀 시 false(effect로 상태 변화 때만 호출, unmount 시 false).
- `FreeTextInput`: `const [voiceBusy, setVoiceBusy] = useState(false)`, `<VoiceInput … onBusyChange={setVoiceBusy} />`, [확인하기] `disabled={!ready || pending || voiceBusy}`, `submit()`도 `voiceBusy`면 무시. textarea는 계속 편집 가능.
- 문구: transcribing 상태 표시 `음성을 글로 바꾸는 중입니다.`(role=status). 이 탭에서 아직 전사가 한 번도 성공하지 않았으면 그 아래 `처음 한 번은 약 10초 정도 걸릴 수 있습니다.` 추가(모듈 수준 in-memory flag, 첫 성공 후 false; countdown·하드코딩 타이머 금지; 저장소 사용 금지).
- 기존 테스트가 옛 문구 `음성을 글로 바꾸는 중...`을 단언하면 새 문구로 **갱신**(동작 단언은 유지)하고 보고.

## Task 2 — Retry semantics ("다시 시도" = 마지막 실패 action 재실행)
- `useMedmapSession`에 `lastFailedRef`(메모리 전용) 추가: `start`·`answer`·`resume` 실패 시 `{type, args}` 저장, 성공 시 null.
  - start: `{type:'start', args:[intake, cache, intakeHistory]}`
  - answer: `{type:'answer', args:[{session, question, kind, value}]}` — **실패 당시의 turn.session·질문을 그대로** 보관(stateless API라 같은 요청 재전송은 안전: 첫 요청이 서버에서 처리됐어도 클라이언트 세션이 바뀌지 않았으므로 같은 결과).
  - resume: `{type:'resume', args:[session]}`
- 새 `retry()`: `pending`이면 무시(더블클릭 방지). `lastFailedRef`가 있으면 그 action을 같은 인자로 재실행, 없으면 `retryHealth()`. 성공 시 error clear. hook 반환에 `retry`, `canRetry`(= lastFailed 존재 또는 health 오류) 추가.
- resume 실패 정책 변경(데이터 손실 방지): `NETWORK_ERROR`·status ≥ 500·503이면 저장된 세션·cache를 **지우지 않고** error를 표시(Notice 다시 시도 → resume 재실행). 4xx(세션 무효)는 기존대로 조용히 폐기·시작 화면.
- extract 실패는 재실행 대상이 아님(원문을 hook에 보관하지 않음): extract 오류일 때 Notice는 retry 버튼 없이 표시되고, 입력칸의 원문은 FreeTextInput에 그대로 있으므로 사용자가 [확인하기]를 다시 누른다. 이를 위해 error에 `source:'extract'` 표시, App은 `onRetry`를 extract 오류일 때 넘기지 않는다.
- `App.jsx`: `onRetry={session.canRetry ? session.retry : undefined}`, Notice 버튼 `disabled={pending}`(Notice에 `pending` prop 추가).
- 테스트(hook·integration): answer 500 → retry → 같은 session·question_id·kind·value 재전송, 성공 후 error null · start 실패 → retry → 같은 본문 재전송 · retry 중 두 번 눌러도 요청 1회 · resume 네트워크 실패 → 세션 보존 + retry로 복원 · resume 409 → 기존대로 폐기 · extract 실패 → retry 버튼 없음, 입력 보존.

## Task 3 — Summary history 복원: 설계만(구현 보류)
`medmap/clinical_summary.py`는 Python 전용(`summary_from_session(session, diagnoses, catalog, labels)`), 프론트에는 전체 질문 한국어 라벨이 없다 → SummaryScreen이 직접 쓸 수 없다. 새 endpoint 또는 turn 계약 변경이 필요하므로 이번 bounded 범위에서 구현하지 않는다. 설계안은 보고서에만.
설계안(승인 대기):
- `POST /v1/session/summary` 요청 `{session}` → `deserialize_session` → 기존 `_run`과 같은 엔진으로 질문 없이(max_questions=0) 진단 재계산 → `clinical_summary.summary_from_session(session, diagnoses, catalog, labels=PresenterLabelProvider)` → `medmap-clinical-summary-v1` 반환. 서버 저장·로그 없음, 기존 4 endpoint 무변경(추가만).
- 프론트: SummaryScreen이 phase=summary 진입·새로고침 복원 시 이 endpoint로 요약을 받아 "내가 답한 항목"을 PatientState 기준으로 표시(메모리 history 대체) + 안내 문구. 실패 시 현재 화면(후보만) 유지.
- B1 준수: session에 없는 intake NEGATIVE(cache 미적용)·UNKNOWN 미기록분은 표시하지 않음. transcript·matched_text 없음. 라벨은 LabelProvider 경유 → C(한국어 용어) 병합 시 자동 반영.
- 대안(비권장): turn payload에 summary 포함 = 응답 계약 변경.

## Task 4 — 테스트
- Frontend integration(append): 상담 중 /answer 500 → 다시 시도 → 복구 · STT transcribing 중 [확인하기] disabled → 완료 후 enabled(오류 후도 enabled) · summary에서 reload → summary 유지·질환 후보 표시(답한 항목 목록은 현재 복원 안 됨 — Task 3 보류를 명시하는 단언).
- 실서버 e2e(새 파일 `medmap-web/e2e/flow-hardening.e2e.mjs`, 텍스트만·GPU 불필요): E(확인 NEGATIVE E_91 재사용 — "기침은 나는데 열은 없어요" → bootstrap에 열 질문이 나오지 않고 /start answers에 E_91 NEGATIVE) · F(후보 0 → 기침 → 잘 모르겠어요 1회 후 known 3개 → /start answers에 UNKNOWN 없음) · F-INCOMPLETE(잘 모르겠어요로 채울 수 없게 되면 START_INCOMPLETE 문구, /start 미호출) · refresh/resume(상담 중 reload → 같은 질문, 이어서 답변 가능) · API error recovery(/answer 1회 500 가로채기 → Notice 다시 시도 → 같은 요청 재전송 → 1/3).
