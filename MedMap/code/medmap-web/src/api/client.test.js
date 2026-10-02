import { ApiError, getHealth, startSession, submitAnswer, resumeSession, getSummary, transcribeAudio } from './client'
import turnStart from '../test/fixtures/turn.start.json'
import summaryFixture from '../test/fixtures/summary.v1.json'

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

test('getSummary 는 session 을 감싸 /v1/session/summary 로 보낸다', async () => {
  const fetchMock = mockFetch(200, summaryFixture)
  vi.stubGlobal('fetch', fetchMock)
  const summary = await getSummary(turnStart.session)
  const [url, init] = fetchMock.mock.calls[0]
  expect(url).toBe('/v1/session/summary')
  expect(JSON.parse(init.body)).toEqual({ session: turnStart.session })
  expect(summary.schema_version).toBe('medmap-clinical-summary-v1')
})

test('getSummary 오류 응답도 ApiError 로 바뀐다', async () => {
  vi.stubGlobal('fetch', mockFetch(500, { error: { code: 'INTERNAL_ERROR', message: 'boom' } }))
  await expect(getSummary(turnStart.session)).rejects.toMatchObject({ name: 'ApiError', status: 500, code: 'INTERNAL_ERROR' })
})

test('health 는 준비 상태를 그대로 돌려준다', async () => {
  vi.stubGlobal('fetch', mockFetch(200, { status: 'ok', engine_ready: true, max_questions: 3 }))
  await expect(getHealth()).resolves.toMatchObject({ engine_ready: true, max_questions: 3 })
})

test('extractIntake 는 text 만 보낸다', async () => {
  const fetchMock = vi.fn(async () => ({ ok: true, status: 200, json: async () => ({ candidates: [], mapper_version: 'v1.2' }) }))
  vi.stubGlobal('fetch', fetchMock)
  const { extractIntake } = await import('./client.js')
  await expect(extractIntake('기침이 나요')).resolves.toEqual({ candidates: [], mapper_version: 'v1.2' })
  const [url, init] = fetchMock.mock.calls[0]
  expect(url).toBe('/v1/intake/extract')
  expect(JSON.parse(init.body)).toEqual({ text: '기침이 나요' })
})

test('transcribeAudio 는 blob 을 raw body 로 보내고 blob.type 을 content-type 으로 쓴다', async () => {
  const fetchMock = mockFetch(200, { transcript: '기침이 나요', duration_s: 1.23, language: 'ko' })
  vi.stubGlobal('fetch', fetchMock)
  const blob = { type: 'audio/webm;codecs=opus' }
  await expect(transcribeAudio(blob)).resolves.toEqual({ transcript: '기침이 나요', duration_s: 1.23, language: 'ko' })
  const [url, init] = fetchMock.mock.calls[0]
  expect(url).toBe('/v1/stt/transcribe')
  expect(init.method).toBe('POST')
  expect(init.headers).toEqual({ 'content-type': 'audio/webm;codecs=opus' })
  expect(init.body).toBe(blob)
})

test('transcribeAudio 는 blob.type 이 없으면 기본 audio/webm 을 쓴다', async () => {
  const fetchMock = mockFetch(200, { transcript: '', duration_s: 0, language: 'ko' })
  vi.stubGlobal('fetch', fetchMock)
  const blob = { type: '' }
  await transcribeAudio(blob)
  expect(fetchMock.mock.calls[0][1].headers).toEqual({ 'content-type': 'audio/webm' })
})

test('transcribeAudio 오류 응답도 ApiError 로 바뀐다', async () => {
  vi.stubGlobal('fetch', mockFetch(422, { error: { code: 'AUDIO_EMPTY', message: '무음', field: null } }))
  await expect(transcribeAudio({ type: 'audio/webm' })).rejects.toMatchObject({ name: 'ApiError', status: 422, code: 'AUDIO_EMPTY' })
})
