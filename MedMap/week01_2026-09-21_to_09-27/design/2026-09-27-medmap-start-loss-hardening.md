# MedMap P2-4 시작 전 입력 유실 hardening — 계약 (2026-09-27)

브랜치 `feat/start-loss-hardening` (worktree `~/medmap-worktrees/start-loss-hardening`). 사용자 승인: P2-4 bounded design + 결정 1(UNKNOWN 재답변 허용, 중립 문구) + 결정 2(beforeunload 조건부).

## 고정 (변경 금지)
- `src/intake/startPlan.js` 규칙(rev3): K=3, E_91→E_53→E_66, 예비 E_201→E_175→E_88, UNKNOWN 비계수·미전송, walk·buildStartRequest 무수정.
- 새 evidence 질문 추가 금지. 재답변은 이미 물어본 frozen 질문의 답을 사용자가 명시적으로 바꿀 때만 교체.
- localStorage·sessionStorage·IndexedDB·파일·서버에 새로 저장 금지. `medmap.session`·`medmap.intakeCache`(start 성공 후) 계약 유지.
- API·백엔드·frozen 매퍼 무변경. 디자인 PAUSED(새 색·폰트 없음, 기존 `panel`·`hint`·`button` 클래스만).

## 변경
1. **draft 소유권**: `NaturalIntakeScreen`이 `{age, sex, text}` draft 의 유일한 source of truth. `FreeTextInput`은 완전 controlled(`draft`, `onDraftChange(updater)`), 자체 입력 state 없음. 전사 결과는 updater 함수로 합쳐 stale 덮어쓰기 없음.
2. **in-memory 유지**: age·sex·원문·후보·확인 결과·initial·bootstrap 답(UNKNOWN 포함)은 intake 화면이 살아 있는 동안 React state 에만. start 성공(→consult/summary) 또는 명시적 reset(→start)으로 화면이 unmount 되면 사라진다.
3. **START_INCOMPLETE = 오류 아님**: "진료 질문을 시작하려면 몇 가지 정보를 더 확인해야 합니다." + "'잘 모르겠어요'도 괜찮은 답입니다…" + 지금까지 입력·확인한 내용 표시 + [답변 다시 확인하기] + [처음부터 다시].
4. **답변 다시 확인하기**: UNKNOWN 으로 답한 질문만 원래 순서대로 한 번씩 다시 보여준다. 선택지 있음/없음/잘 모르겠어요, 기본 선택 없음. 있음/없음을 누른 경우만 교체. 교체 직후 walk 가 READY 가 되는 가장 짧은 앞부분이 있으면 그 답들로 바로 `/start`. 한 바퀴 뒤 walk 가 ASK 면 남은 frozen 질문을 이어서, 여전히 INCOMPLETE 면 "현재 확인된 정보만으로는 다음 상담 질문을 시작하기 어렵습니다." (입력 유지, [답변 다시 확인하기]·[처음부터 다시]).
5. **안내**: intake 화면 위 작은 hint "아직 저장된 상담이 아닙니다. / 이 단계에서 새로고침하면 입력한 내용이 사라질 수 있습니다." (modal 없음)
6. **beforeunload**: intake 화면에서 dirty(나이·성별·문장 중 하나라도 입력 또는 describe 이후 단계)일 때만 등록. `preventDefault()` + `returnValue=''`(브라우저 기본 확인창, custom 문구 없음). dirty 해제·unmount(start 성공·reset) 시 제거.

## 테스트
- 단위(NaturalIntakeScreen): START_INCOMPLETE 후 age·sex·text·확인 항목·initial·known·UNKNOWN 표시 유지 / 재답변: 그대로 두기·UNKNOWN→known·exact-k3 시 onStart 1회·UNKNOWN 미포함·전부 유지 시 incomplete 유지·새 evidence 미생성 / [처음부터 다시]만 onRestart / notice / beforeunload clean·dirty·unmount.
- FreeTextInput: controlled draft, 전사 중 타이핑 + 전사 도착 시 둘 다 유지(stale 없음), remount 시 값 유지.
- integration(App): start 성공 → beforeunload 제거·notice 사라짐 / reset → 제거 / start 전 `Storage.setItem` 0회, 원문·matched_text·transcript 미저장.
- 회귀: 기존 vitest 전체, build, 실서버 text e2e(`e2e/flow-hardening.e2e.mjs`의 F-INCOMPLETE 갱신 + F-RECOVER 추가). GPU 불필요.
