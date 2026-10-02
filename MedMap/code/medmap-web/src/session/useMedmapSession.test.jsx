import { act, renderHook, waitFor } from '@testing-library/react'
import { describeAnswer, useMedmapSession } from './useMedmapSession'
import turnStart from '../test/fixtures/turn.start.json'
import summaryFixture from '../test/fixtures/summary.v1.json'

const stopped = { ...turnStart, next_question: null, stop_reason: 'MAX_QUESTIONS', questions_asked_in_session: 3 }

function fakeApi(overrides = {}) {
  return {
    getHealth: vi.fn(async () => ({ engine_ready: true, max_questions: 3 })),
    startSession: vi.fn(async () => turnStart),
    submitAnswer: vi.fn(async () => stopped),
    resumeSession: vi.fn(async () => turnStart),
    getSummary: vi.fn(async () => summaryFixture),
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

test('저장된 세션이 있으면 새로고침 후 이어서 복원한다', async () => {
  sessionStorage.setItem('medmap.session', JSON.stringify(turnStart.session))
  const api = fakeApi()
  const { result } = renderHook(() => useMedmapSession({ api }))
  await waitFor(() => expect(result.current.phase).toBe('consult'))
  expect(api.resumeSession).toHaveBeenCalledWith(turnStart.session)
  expect(result.current.turn.next_question.question_id).toBe(turnStart.next_question.question_id)
  sessionStorage.clear()
})

test('저장된 세션이 더 이상 유효하지 않으면 시작 화면으로 남고 저장본을 지운다', async () => {
  sessionStorage.setItem('medmap.session', JSON.stringify(turnStart.session))
  const api = fakeApi({
    resumeSession: vi.fn(async () => { throw Object.assign(new Error('bad'), { name: 'ApiError', status: 409, code: 'MEDMAP_UNSUPPORTED_SESSION_SHAPE' }) }),
  })
  const { result } = renderHook(() => useMedmapSession({ api }))
  await waitFor(() => expect(api.resumeSession).toHaveBeenCalled())
  await waitFor(() => expect(result.current.phase).toBe('start'))
  expect(sessionStorage.getItem('medmap.session')).toBeNull()
  expect(result.current.error).toBeNull()
})

test('저장된 세션이 없으면 복원을 시도하지 않는다', async () => {
  sessionStorage.clear()
  const api = fakeApi()
  const { result } = renderHook(() => useMedmapSession({ api }))
  await waitFor(() => expect(result.current.health.engine_ready).toBe(true))
  expect(api.resumeSession).not.toHaveBeenCalled()
  expect(result.current.phase).toBe('start')
})

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

test('cache 자동 적용 루프 중 매 성공 턴마다 세션을 저장한다(새로고침 중간 복귀)', async () => {
  sessionStorage.clear()
  const midSession = { ...turnStart.session, marker: 1 }
  const api = fakeApi({
    startSession: vi.fn(async () => turnAsking('E_50')),
    submitAnswer: vi.fn()
      .mockImplementationOnce(async () => ({ ...turnAsking('E_212', 1), session: midSession }))
      .mockImplementationOnce(() => new Promise(() => {})),   // 두 번째는 끝나지 않는다
  })
  const { result } = renderHook(() => useMedmapSession({ api }))
  const cache = [{ evidence_id: 'E_50', status: 'POSITIVE' }, { evidence_id: 'E_212', status: 'POSITIVE' }]
  act(() => {
    result.current.start({ age: 45, sex: 'M', initialEvidence: 'E_66', answers: [] }, cache)
  })
  await waitFor(() => expect(api.submitAnswer).toHaveBeenCalledTimes(2))
  await waitFor(() => expect(JSON.parse(sessionStorage.getItem('medmap.session')).marker).toBe(1))
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

test('answer 실패 후 retry 는 같은 session·question_id·kind·value 로 재전송하고, 성공하면 error 가 지워진다', async () => {
  sessionStorage.clear()
  const failure = Object.assign(new Error('x'), { status: 500, code: 'INTERNAL_ERROR' })
  const api = fakeApi({
    submitAnswer: vi.fn()
      .mockRejectedValueOnce(failure)
      .mockResolvedValueOnce(stopped),
  })
  const { result } = renderHook(() => useMedmapSession({ api }))
  await act(async () => { await result.current.start({ age: 45, sex: 'M', initialEvidence: 'E_201', answers: [] }) })
  await act(async () => { await result.current.answer({ kind: 'NEGATIVE', value: null }) })
  expect(result.current.error).toBe(failure)
  expect(result.current.canRetry).toBe(true)

  await act(async () => { await result.current.retry() })
  expect(api.submitAnswer).toHaveBeenCalledTimes(2)
  expect(api.submitAnswer.mock.calls[1][0]).toEqual({
    session: turnStart.session,
    questionId: turnStart.next_question.question_id,
    kind: 'NEGATIVE',
    value: null,
  })
  expect(result.current.error).toBeNull()
  expect(result.current.phase).toBe('summary')
})

test('start 실패 후 retry 는 같은 본문으로 재전송한다', async () => {
  sessionStorage.clear()
  const failure = Object.assign(new Error('x'), { status: 500, code: 'INTERNAL_ERROR' })
  const api = fakeApi({
    startSession: vi.fn()
      .mockRejectedValueOnce(failure)
      .mockResolvedValueOnce(turnStart),
  })
  const { result } = renderHook(() => useMedmapSession({ api }))
  const intake = { age: 45, sex: 'M', initialEvidence: 'E_201', answers: [] }
  await act(async () => { await result.current.start(intake) })
  expect(result.current.error).toBe(failure)
  expect(result.current.canRetry).toBe(true)

  await act(async () => { await result.current.retry() })
  expect(api.startSession).toHaveBeenCalledTimes(2)
  expect(api.startSession).toHaveBeenNthCalledWith(2, intake)
  expect(result.current.error).toBeNull()
  expect(result.current.phase).toBe('consult')
})

test('retry 는 pending 중이면 무시되어 같은 요청이 두 번 나가지 않는다', async () => {
  sessionStorage.clear()
  const failure = Object.assign(new Error('x'), { status: 500, code: 'INTERNAL_ERROR' })
  let resolveSecond
  const api = fakeApi({
    submitAnswer: vi.fn()
      .mockRejectedValueOnce(failure)
      .mockImplementationOnce(() => new Promise((resolve) => { resolveSecond = resolve })),
  })
  const { result } = renderHook(() => useMedmapSession({ api }))
  await act(async () => { await result.current.start({ age: 45, sex: 'M', initialEvidence: 'E_201', answers: [] }) })
  await act(async () => { await result.current.answer({ kind: 'NEGATIVE', value: null }) })
  expect(api.submitAnswer).toHaveBeenCalledTimes(1)

  act(() => { result.current.retry(); result.current.retry() })
  expect(api.submitAnswer).toHaveBeenCalledTimes(2)     // 두 번째 클릭은 무시됨
  await act(async () => { resolveSecond(stopped) })
})

test('resume 이 네트워크 오류로 실패하면 세션을 지우지 않고 retry 로 복원한다', async () => {
  sessionStorage.clear()
  sessionStorage.setItem('medmap.session', JSON.stringify(turnStart.session))
  const networkError = Object.assign(new Error('down'), { code: 'NETWORK_ERROR', status: 0 })
  const api = fakeApi({
    resumeSession: vi.fn()
      .mockRejectedValueOnce(networkError)
      .mockResolvedValueOnce(turnStart),
  })
  const { result } = renderHook(() => useMedmapSession({ api }))
  await waitFor(() => expect(result.current.error).toBe(networkError))
  expect(sessionStorage.getItem('medmap.session')).not.toBeNull()   // 지우지 않는다
  expect(result.current.phase).toBe('start')
  expect(result.current.canRetry).toBe(true)

  await act(async () => { await result.current.retry() })
  expect(api.resumeSession).toHaveBeenCalledTimes(2)
  expect(result.current.phase).toBe('consult')
  expect(result.current.error).toBeNull()
})

test('resume 이 500 으로 실패해도 세션을 지우지 않는다', async () => {
  sessionStorage.clear()
  sessionStorage.setItem('medmap.session', JSON.stringify(turnStart.session))
  const serverError = Object.assign(new Error('x'), { status: 503, code: 'ENGINE_NOT_READY' })
  const api = fakeApi({ resumeSession: vi.fn(async () => { throw serverError }) })
  const { result } = renderHook(() => useMedmapSession({ api }))
  await waitFor(() => expect(result.current.error).toBe(serverError))
  expect(sessionStorage.getItem('medmap.session')).not.toBeNull()
})

test('resume 이 409(세션 무효)로 실패하면 기존대로 조용히 폐기한다', async () => {
  sessionStorage.clear()
  sessionStorage.setItem('medmap.session', JSON.stringify(turnStart.session))
  const api = fakeApi({
    resumeSession: vi.fn(async () => { throw Object.assign(new Error('bad'), { status: 409, code: 'MEDMAP_UNSUPPORTED_SESSION_SHAPE' }) }),
  })
  const { result } = renderHook(() => useMedmapSession({ api }))
  await waitFor(() => expect(result.current.phase).toBe('start'))
  expect(sessionStorage.getItem('medmap.session')).toBeNull()
  expect(result.current.error).toBeNull()
  expect(result.current.canRetry).toBe(false)
})

test('extract 실패는 source:"extract" 로 표시되고 canRetry 는 false 다(재실행 대상 아님)', async () => {
  sessionStorage.clear()
  const failure = Object.assign(new Error('x'), { status: 500, code: 'INTERNAL_ERROR' })
  const api = fakeApi({ extractIntake: vi.fn(async () => { throw failure }) })
  const { result } = renderHook(() => useMedmapSession({ api }))
  let found
  await act(async () => { found = await result.current.extract('기침') })
  expect(found).toBeNull()
  expect(result.current.error.source).toBe('extract')
  expect(result.current.canRetry).toBe(false)
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

test('describeAnswer: 선택지에 없는 value code 는 raw code 대신 한국어 value 표시명을 쓴다', () => {
  const question = { question_id: 'E_204', choices: [{ value: 'V_10', label: '아니요' }] }
  expect(describeAnswer(question, 'VALUE', ['V_10', 'V_7'])).toBe('아니요, 동남아시아')
  expect(describeAnswer(question, 'VALUE', ['3'])).toBe('3')
})

// --- clinical-summary-ui: /v1/session/summary ---

test('요약 화면 진입 시 turn.session 으로 getSummary 를 호출하고 summaryState 가 ready 가 된다', async () => {
  sessionStorage.clear()
  const api = fakeApi()
  const { result } = renderHook(() => useMedmapSession({ api }))
  await act(async () => { await result.current.start({ age: 45, sex: 'M', initialEvidence: 'E_201', answers: [] }) })
  await act(async () => { await result.current.answer({ kind: 'NEGATIVE', value: null }) })
  await waitFor(() => expect(result.current.summaryState).toBe('ready'))
  expect(api.getSummary).toHaveBeenCalledWith(stopped.session)
  expect(result.current.summary.schema_version).toBe('medmap-clinical-summary-v1')
})

test('진입 직후 재렌더가 일어나도 같은 세션이면 getSummary 를 한 번만 호출한다', async () => {
  sessionStorage.clear()
  const api = fakeApi()
  const { result, rerender } = renderHook(() => useMedmapSession({ api }))
  await act(async () => { await result.current.start({ age: 45, sex: 'M', initialEvidence: 'E_201', answers: [] }) })
  await act(async () => { await result.current.answer({ kind: 'NEGATIVE', value: null }) })
  await waitFor(() => expect(result.current.summaryState).toBe('ready'))
  expect(api.getSummary).toHaveBeenCalledTimes(1)
  rerender()
  expect(api.getSummary).toHaveBeenCalledTimes(1)
})

test('새로고침으로 summary 를 resume 복원해도 같은 session 으로 getSummary 를 호출한다', async () => {
  sessionStorage.clear()
  const finalTurn = { ...turnStart, next_question: null, stop_reason: 'MAX_QUESTIONS', questions_asked_in_session: 3 }
  sessionStorage.setItem('medmap.session', JSON.stringify(finalTurn.session))
  const api = fakeApi({ resumeSession: vi.fn(async () => finalTurn) })
  const { result } = renderHook(() => useMedmapSession({ api }))
  await waitFor(() => expect(result.current.phase).toBe('summary'))
  await waitFor(() => expect(result.current.summaryState).toBe('ready'))
  expect(api.getSummary).toHaveBeenCalledWith(finalTurn.session)
})

test('summary 5xx 는 세션을 보존하고 summaryState=error, retrySummary 는 같은 세션으로 재호출한다', async () => {
  sessionStorage.clear()
  const failure = Object.assign(new Error('x'), { status: 500, code: 'INTERNAL_ERROR' })
  const api = fakeApi({ getSummary: vi.fn().mockRejectedValueOnce(failure).mockResolvedValueOnce(summaryFixture) })
  const { result } = renderHook(() => useMedmapSession({ api }))
  await act(async () => { await result.current.start({ age: 45, sex: 'M', initialEvidence: 'E_201', answers: [] }) })
  await act(async () => { await result.current.answer({ kind: 'NEGATIVE', value: null }) })
  await waitFor(() => expect(result.current.summaryState).toBe('error'))
  expect(sessionStorage.getItem('medmap.session')).not.toBeNull()
  expect(result.current.phase).toBe('summary')

  await act(async () => { await result.current.retrySummary() })
  expect(api.getSummary).toHaveBeenCalledTimes(2)
  expect(api.getSummary).toHaveBeenNthCalledWith(2, stopped.session)
  expect(result.current.summaryState).toBe('ready')
})

test('summary NETWORK_ERROR 도 세션을 보존하고 summaryState=error 가 된다', async () => {
  sessionStorage.clear()
  const failure = Object.assign(new Error('down'), { code: 'NETWORK_ERROR', status: 0 })
  const api = fakeApi({ getSummary: vi.fn(async () => { throw failure }) })
  const { result } = renderHook(() => useMedmapSession({ api }))
  await act(async () => { await result.current.start({ age: 45, sex: 'M', initialEvidence: 'E_201', answers: [] }) })
  await act(async () => { await result.current.answer({ kind: 'NEGATIVE', value: null }) })
  await waitFor(() => expect(result.current.summaryState).toBe('error'))
  expect(sessionStorage.getItem('medmap.session')).not.toBeNull()
})

test('summary 4xx 는 resume 4xx 와 같은 정책으로 세션·cache 를 조용히 버리고 시작 화면으로 되돌린다', async () => {
  sessionStorage.clear()
  const failure = Object.assign(new Error('bad'), { status: 409, code: 'MEDMAP_UNSUPPORTED_SESSION_SHAPE' })
  const api = fakeApi({ getSummary: vi.fn(async () => { throw failure }) })
  const { result } = renderHook(() => useMedmapSession({ api }))
  await act(async () => { await result.current.start({ age: 45, sex: 'M', initialEvidence: 'E_201', answers: [] }) })
  await act(async () => { await result.current.answer({ kind: 'NEGATIVE', value: null }) })
  await waitFor(() => expect(result.current.phase).toBe('start'))
  expect(sessionStorage.getItem('medmap.session')).toBeNull()
  expect(result.current.turn).toBeNull()
  expect(result.current.error).toBeNull()
  expect(result.current.summary).toBeNull()
  expect(result.current.summaryState).toBe('idle')
})

test('summary 는 저장소가 아닌 메모리에만 있고, reset 하면 지워진다', async () => {
  sessionStorage.clear()
  const api = fakeApi()
  const { result } = renderHook(() => useMedmapSession({ api }))
  await act(async () => { await result.current.start({ age: 45, sex: 'M', initialEvidence: 'E_201', answers: [] }) })
  await act(async () => { await result.current.answer({ kind: 'NEGATIVE', value: null }) })
  await waitFor(() => expect(result.current.summaryState).toBe('ready'))
  expect(JSON.stringify({ ...sessionStorage })).not.toContain('medmap-clinical-summary-v1')

  act(() => result.current.reset())
  expect(result.current.summary).toBeNull()
  expect(result.current.summaryState).toBe('idle')
})

function deferred() {
  let resolve, reject
  const promise = new Promise((res, rej) => { resolve = res; reject = rej })
  return { promise, resolve, reject }
}

test('reset 뒤 늦게 도착한 summary 성공 응답은 새 화면을 덮지 않는다', async () => {
  sessionStorage.clear()
  const pending = deferred()
  const api = fakeApi({ getSummary: vi.fn(() => pending.promise) })
  const { result } = renderHook(() => useMedmapSession({ api }))
  await act(async () => { await result.current.start({ age: 45, sex: 'M', initialEvidence: 'E_201', answers: [] }) })
  await act(async () => { await result.current.answer({ kind: 'NEGATIVE', value: null }) })
  await waitFor(() => expect(result.current.summaryState).toBe('loading'))
  act(() => result.current.reset())
  await act(async () => { pending.resolve(summaryFixture); await pending.promise })
  expect(result.current.phase).toBe('start')
  expect(result.current.summary).toBeNull()
  expect(result.current.summaryState).toBe('idle')
})

test('새 세션 시작 뒤 늦게 도착한 이전 summary 4xx 는 새 세션 저장본을 지우지 않는다', async () => {
  sessionStorage.clear()
  const pending = deferred()
  const api = fakeApi({ getSummary: vi.fn(() => pending.promise) })
  const { result } = renderHook(() => useMedmapSession({ api }))
  await act(async () => { await result.current.start({ age: 45, sex: 'M', initialEvidence: 'E_201', answers: [] }) })
  await act(async () => { await result.current.answer({ kind: 'NEGATIVE', value: null }) })
  await waitFor(() => expect(result.current.summaryState).toBe('loading'))
  act(() => result.current.reset())
  await act(async () => { await result.current.start({ age: 45, sex: 'M', initialEvidence: 'E_201', answers: [] }) })
  expect(result.current.phase).toBe('consult')
  const stored = sessionStorage.getItem('medmap.session')
  expect(stored).not.toBeNull()
  const failure = Object.assign(new Error('bad'), { status: 409, code: 'MEDMAP_UNSUPPORTED_SESSION_SHAPE' })
  await act(async () => { pending.reject(failure); await pending.promise.catch(() => {}) })
  expect(result.current.phase).toBe('consult')
  expect(sessionStorage.getItem('medmap.session')).toBe(stored)
  expect(result.current.turn).not.toBeNull()
})
