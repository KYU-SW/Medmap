import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'
import turnStart from './test/fixtures/turn.start.json'
import summaryFixture from './test/fixtures/summary.v1.json'

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

test('B-UNKNOWN: 잘 모르겠어요는 start 에 넣지 않고 예비 질문으로 채운다, 요약은 서버 summary API 기준으로 보인다', async () => {
  const user = userEvent.setup()
  const calls = installRoutes({
    '/v1/intake/extract': { candidates: [], mapper_version: 'v1.2' },
    '/v1/session/start': { ...turnStart, next_question: null, stop_reason: 'MAX_QUESTIONS', questions_asked_in_session: 3 },
    '/v1/session/summary': summaryFixture,
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
  // 요약은 UI-local history 가 아니라 /v1/session/summary 응답을 그대로 반영한다(bootstrap UNKNOWN 은 세션에 없어 summary 에도 없다).
  expect(calls.some((call) => call.url === '/v1/session/summary')).toBe(true)
  await waitFor(() => expect(screen.getByText(summaryFixture.chief_complaint.label_ko)).toBeInTheDocument())
  expect(screen.getByText(summaryFixture.confirmed_negative[0].question_ko)).toBeInTheDocument()
})

test('B-INCOMPLETE: 예비까지 써도 3개를 못 채우면 start 를 호출하지 않는다', async () => {
  const user = userEvent.setup()
  const calls = installRoutes({ '/v1/intake/extract': { candidates: [], mapper_version: 'v1.2' }, '/v1/session/start': turnStart })
  render(<App />)
  await pickDizzy(user, calls)
  for (let i = 0; i < 4; i += 1) await user.click(screen.getByRole('button', { name: '잘 모르겠어요' }))   // 6개 중 4개 UNKNOWN → 남은 2개로 불가
  expect(screen.getByText('진료 질문을 시작하려면 몇 가지 정보를 더 확인해야 합니다.')).toBeInTheDocument()
  expect(startCall(calls)).toBeUndefined()
  expect(sessionStorage.length).toBe(0)
})

const unloadPrevented = () => {
  const event = new Event('beforeunload', { cancelable: true })
  window.dispatchEvent(event)
  return event.defaultPrevented
}

test('P2-4: START_INCOMPLETE → 답변 다시 확인하기 → exact-k3 → start. start 전 저장소 쓰기 0, start 후 경고·안내 제거', async () => {
  const user = userEvent.setup()
  const setItem = vi.spyOn(Storage.prototype, 'setItem')
  const calls = installRoutes({
    '/v1/intake/extract': { candidates: [c('E_201', 'POSITIVE', '기침이 있나요?', '기침이 나고'), c('E_77', 'NEGATIVE', '가래가 있나요?', '가래는 없어요', false)], mapper_version: 'v1.2' },
    '/v1/session/start': turnStart,
  })
  render(<App />)
  expect(unloadPrevented()).toBe(false)                       // 시작 화면: 입력 없음
  await describe(user, TYPED)
  await user.click(await screen.findByRole('button', { name: '다음' }))
  for (let i = 0; i < 3; i += 1) await user.click(screen.getByRole('button', { name: '잘 모르겠어요' }))
  expect(screen.getByText('진료 질문을 시작하려면 몇 가지 정보를 더 확인해야 합니다.')).toBeInTheDocument()
  expect(screen.getByTestId('intake-recap')).toHaveTextContent(TYPED)
  expect(screen.getByTestId('prestart-notice')).toBeInTheDocument()
  expect(unloadPrevented()).toBe(true)
  expect(startCall(calls)).toBeUndefined()
  // start 전: 저장소에 아무것도 쓰지 않았다(원문·matched_text·전사문·답 기록 모두)
  expect(setItem).not.toHaveBeenCalled()
  expect(sessionStorage.length).toBe(0)
  expect(localStorage.length).toBe(0)

  await user.click(screen.getByRole('button', { name: '답변 다시 확인하기' }))
  await user.click(screen.getByRole('button', { name: '없음' }))           // E_91
  await user.click(screen.getByRole('button', { name: '없음' }))           // E_53
  await user.click(screen.getByRole('button', { name: '없음' }))           // E_66 → 3개
  await waitFor(() => expect(screen.getByText('추가로 확인할 정보')).toBeInTheDocument())
  expect(calls.filter((call) => call.url === '/v1/session/start')).toHaveLength(1)
  expect(startCall(calls).body.answers.map((a) => [a.question_id, a.kind]))
    .toEqual([['E_91', 'NEGATIVE'], ['E_53', 'NEGATIVE'], ['E_66', 'NEGATIVE']])
  expect(screen.queryByTestId('prestart-notice')).toBeNull()
  expect(unloadPrevented()).toBe(false)                       // start 성공 → listener 제거
  // start 후 저장소: 기존 계약(medmap.session·medmap.intakeCache)뿐, 원문·matched_text 없음
  const written = setItem.mock.calls.map(([key]) => key)
  expect(new Set(written)).toEqual(new Set(['medmap.session', 'medmap.intakeCache']))
  const stored = JSON.stringify({ ...sessionStorage, ...localStorage })
  expect(stored).not.toContain(TYPED)
  expect(stored).not.toContain('기침이 나고')
  expect(stored).not.toContain('가래는 없어요')
  expect(localStorage.length).toBe(0)
  setItem.mockRestore()
})

test('P2-4: 처음부터 다시(명시적 reset)를 눌렀을 때만 입력이 사라지고 beforeunload 도 제거된다', async () => {
  const user = userEvent.setup()
  installRoutes({ '/v1/intake/extract': { candidates: [], mapper_version: 'v1.2' }, '/v1/session/start': turnStart })
  render(<App />)
  await pickDizzy(user)
  for (let i = 0; i < 4; i += 1) await user.click(screen.getByRole('button', { name: '잘 모르겠어요' }))
  expect(screen.getByTestId('intake-recap')).toHaveTextContent('그냥 몸이 좀 이상해요')
  expect(unloadPrevented()).toBe(true)
  await user.click(screen.getByRole('button', { name: '처음부터 다시' }))
  expect(screen.getByRole('button', { name: '시작하기' })).toBeInTheDocument()
  expect(unloadPrevented()).toBe(false)
  await user.click(screen.getByRole('button', { name: '시작하기' }))
  expect(screen.getByLabelText('지금 불편한 점을 편하게 적어 주세요')).toHaveValue('')
  expect(screen.getByLabelText('나이')).toHaveValue('')
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

test('E: 확인된 NEGATIVE 가 frozen bootstrap 목록에 있으면 walk 가 도달할 때 재사용되어 다시 묻지 않는다(rev3)', async () => {
  const user = userEvent.setup()
  const calls = installRoutes({ '/v1/intake/extract': { candidates: [c('E_91', 'NEGATIVE', '열이 있나요?', '열은 없어요')], mapper_version: 'v1.2' }, '/v1/session/start': turnStart })
  render(<App />)
  await describe(user, '열은 없어요')
  await user.click(await screen.findByRole('button', { name: '다음' }))
  expect(within(screen.getByTestId('initial-frequent')).queryByRole('button', { name: '열' })).toBeNull()
  await user.click(within(screen.getByTestId('initial-frequent')).getByRole('button', { name: '기침' }))
  for (let i = 0; i < 2; i += 1) await user.click(screen.getByRole('button', { name: '없음' }))   // E_53·E_66(E_91 은 재사용되어 다시 묻지 않음)
  await waitFor(() => expect(startCall(calls)).toBeDefined())
  expect(startCall(calls).body.initial_evidence).toBe('E_201')
  expect(startCall(calls).body.answers.map((a) => [a.question_id, a.kind]))
    .toEqual([['E_91', 'NEGATIVE'], ['E_53', 'NEGATIVE'], ['E_66', 'NEGATIVE']])
  expect(sessionStorage.getItem('medmap.intakeCache')).toBeNull()
  expect(calls.some((call) => call.url === '/v1/session/answer')).toBe(false)     // 제안 없이 이미 start 본문에 재사용됨
})

test('D-NEGATIVE: frozen 목록 밖의 확인된 NEGATIVE 는 cache 에 남고, 엔진이 그 질문을 실제로 제안할 때만 적용된다', async () => {
  const user = userEvent.setup()
  const calls = installRoutes({
    '/v1/intake/extract': { candidates: [c('E_201', 'POSITIVE', '기침이 있나요?', '기침'), c('E_214', 'NEGATIVE', '숨 내쉴 때 쌕쌕거리나요?', '쌕쌕거리진 않아요')], mapper_version: 'v1.2' },
    '/v1/session/start': asking(yesNo('E_214')),
    '/v1/session/answer': asking(turnStart.next_question, 1),
  })
  render(<App />)
  await describe(user, '기침은 나는데 숨 쉴 때 쌕쌕거리진 않아요')
  await user.click(await screen.findByRole('button', { name: '다음' }))
  for (let i = 0; i < 3; i += 1) await user.click(screen.getByRole('button', { name: '없음' }))   // E_91·E_53·E_66
  await waitFor(() => expect(screen.getByText(/앞서 말씀하신 내용을 반영했어요/)).toBeInTheDocument())
  expect(startCall(calls).body.answers.map((a) => a.question_id)).not.toContain('E_214')
  const answers = calls.filter((call) => call.url === '/v1/session/answer')
  expect(answers).toHaveLength(1)
  expect(answers[0].body.submission).toEqual({ question_id: 'E_214', answer: { kind: 'NEGATIVE', value: null } })
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

// --- STT(음성 입력): App 최상단 flow 에서 자유입력 textbox 로만 들어가고, 자동 submit 은 없다 ---

class FakeMediaRecorder {
  constructor() {
    this.state = 'inactive'
    this.ondataavailable = null
    this.onstop = null
  }

  start() { this.state = 'recording' }

  stop() {
    if (this.state === 'inactive') return
    this.state = 'inactive'
    const data = FakeMediaRecorder.nextBlob ?? new Blob(['audio-bytes'], { type: 'audio/webm' })
    this.ondataavailable?.({ data })
    this.onstop?.()
  }
}
FakeMediaRecorder.isTypeSupported = (type) => type === 'audio/webm;codecs=opus'
FakeMediaRecorder.nextBlob = undefined

function stubMic({ allow = true } = {}) {
  vi.stubGlobal('MediaRecorder', FakeMediaRecorder)
  vi.stubGlobal('navigator', {
    ...globalThis.navigator,
    mediaDevices: {
      getUserMedia: allow
        ? vi.fn(async () => ({ getTracks: () => [{ stop: vi.fn() }] }))
        : vi.fn(async () => { throw Object.assign(new Error('denied'), { name: 'NotAllowedError' }) }),
    },
  })
}

function installRoutesWithStt(routes, sttResponse) {
  const calls = []
  vi.stubGlobal('fetch', vi.fn(async (url, init) => {
    if (url === '/v1/stt/transcribe') {
      calls.push({ url, body: init?.body })
      if (sttResponse?.error) {
        return { ok: false, status: sttResponse.status ?? 500, json: async () => ({ error: sttResponse.error }) }
      }
      return { ok: true, status: 200, json: async () => sttResponse }
    }
    const body = init?.body ? JSON.parse(init.body) : null
    calls.push({ url, body })
    const route = routes[url]
    const payload = url === '/health' ? HEALTH : (typeof route === 'function' ? route(body, calls) : route)
    return { ok: true, status: 200, json: async () => payload }
  }))
  return calls
}

afterEach(() => {
  vi.unstubAllGlobals()
  FakeMediaRecorder.nextBlob = undefined
})

test('STT-1: 음성 전사가 자유입력 textbox 에 들어가고, 사용자가 고쳐 쓴 뒤 확인하기를 눌러야만 extract 가 호출된다', async () => {
  stubMic({ allow: true })
  const calls = installRoutesWithStt(
    { '/v1/intake/extract': { candidates: [], mapper_version: 'v1.2' }, '/v1/session/start': turnStart },
    { transcript: '기침이 나고 열이 나요', duration_s: 1.5, language: 'ko' },
  )
  const user = userEvent.setup()
  render(<App />)
  await waitFor(() => expect(screen.getByRole('button', { name: '시작하기' })).toBeEnabled())
  await user.click(screen.getByRole('button', { name: '시작하기' }))
  await user.type(screen.getByLabelText('나이'), '45')
  await user.click(screen.getByRole('button', { name: '남성' }))

  await user.click(screen.getByRole('button', { name: /말하기/ }))
  await user.click(await screen.findByRole('button', { name: '그만 말하기' }))
  const textarea = await screen.findByDisplayValue('기침이 나고 열이 나요')

  expect(calls.some((call) => call.url === '/v1/intake/extract')).toBe(false)   // 확인하기 전에는 extract 미호출

  await user.type(textarea, ' 사흘째예요')
  expect(textarea).toHaveValue('기침이 나고 열이 나요 사흘째예요')

  expect(calls.some((call) => call.url === '/v1/intake/extract')).toBe(false)   // 여전히 미호출

  await user.click(screen.getByRole('button', { name: '확인하기' }))
  await waitFor(() => expect(calls.some((call) => call.url === '/v1/intake/extract')).toBe(true))
  const extractCall = calls.find((call) => call.url === '/v1/intake/extract')
  expect(extractCall.body).toEqual({ text: '기침이 나고 열이 나요 사흘째예요' })
})

test('STT-2: 음성 인식 실패(서버 AUDIO_EMPTY)는 기존에 직접 입력한 텍스트를 그대로 보존한다', async () => {
  stubMic({ allow: true })
  FakeMediaRecorder.nextBlob = new Blob(['audio-bytes'], { type: 'audio/webm' })
  const calls = installRoutesWithStt(
    { '/v1/intake/extract': { candidates: [], mapper_version: 'v1.2' } },
    { error: { code: 'AUDIO_EMPTY', message: '음성이 없음', field: null }, status: 422 },
  )
  const user = userEvent.setup()
  render(<App />)
  await waitFor(() => expect(screen.getByRole('button', { name: '시작하기' })).toBeEnabled())
  await user.click(screen.getByRole('button', { name: '시작하기' }))
  await user.type(screen.getByLabelText('나이'), '45')
  await user.click(screen.getByRole('button', { name: '남성' }))
  await user.type(screen.getByLabelText('지금 불편한 점을 편하게 적어 주세요'), '직접 입력한 내용')

  await user.click(screen.getByRole('button', { name: /말하기/ }))
  await user.click(await screen.findByRole('button', { name: '그만 말하기' }))
  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent('음성이 감지되지 않았어요. 다시 말하거나 직접 입력해 주세요.')
  expect(alert.textContent).not.toMatch(/AUDIO_EMPTY|422/)

  expect(screen.getByLabelText('지금 불편한 점을 편하게 적어 주세요')).toHaveValue('직접 입력한 내용')
  expect(calls.every((call) => call.url !== '/v1/intake/extract')).toBe(true)
})

// --- flow-hardening: STT lock · retry 복구 · summary reload ---

test('STT-3: 전사 중에는 확인하기가 비활성화되고, 완료 후 다시 활성화된다', async () => {
  stubMic({ allow: true })
  let resolveStt
  vi.stubGlobal('fetch', vi.fn(async (url) => {
    if (url === '/v1/stt/transcribe') return new Promise((resolve) => { resolveStt = resolve })
    if (url === '/health') return { ok: true, status: 200, json: async () => HEALTH }
    return { ok: true, status: 200, json: async () => ({ candidates: [], mapper_version: 'v1.2' }) }
  }))
  const user = userEvent.setup()
  render(<App />)
  await waitFor(() => expect(screen.getByRole('button', { name: '시작하기' })).toBeEnabled())
  await user.click(screen.getByRole('button', { name: '시작하기' }))
  await user.type(screen.getByLabelText('나이'), '45')
  await user.click(screen.getByRole('button', { name: '남성' }))
  await user.type(screen.getByLabelText('지금 불편한 점을 편하게 적어 주세요'), '기침')
  expect(screen.getByRole('button', { name: '확인하기' })).toBeEnabled()

  await user.click(screen.getByRole('button', { name: /말하기/ }))
  await user.click(await screen.findByRole('button', { name: '그만 말하기' }))
  await waitFor(() => expect(screen.getByRole('button', { name: '확인하기' })).toBeDisabled())

  resolveStt({ ok: true, status: 200, json: async () => ({ transcript: '기침이 나요', duration_s: 1, language: 'ko' }) })
  await waitFor(() => expect(screen.getByRole('button', { name: '확인하기' })).toBeEnabled())
})

test('STT-4: 전사가 오류로 끝나도 확인하기는 다시 활성화된다', async () => {
  stubMic({ allow: true })
  installRoutesWithStt(
    { '/v1/intake/extract': { candidates: [], mapper_version: 'v1.2' } },
    { error: { code: 'AUDIO_EMPTY', message: '음성 없음', field: null }, status: 422 },
  )
  const user = userEvent.setup()
  render(<App />)
  await waitFor(() => expect(screen.getByRole('button', { name: '시작하기' })).toBeEnabled())
  await user.click(screen.getByRole('button', { name: '시작하기' }))
  await user.type(screen.getByLabelText('나이'), '45')
  await user.click(screen.getByRole('button', { name: '남성' }))
  await user.type(screen.getByLabelText('지금 불편한 점을 편하게 적어 주세요'), '기침')
  await user.click(screen.getByRole('button', { name: /말하기/ }))
  await user.click(await screen.findByRole('button', { name: '그만 말하기' }))
  await screen.findByRole('alert')
  expect(screen.getByRole('button', { name: '확인하기' })).toBeEnabled()
})

test('RETRY: 상담 중 /answer 500 → 다시 시도 → 복구된다', async () => {
  const user = userEvent.setup()
  const stopped = { ...turnStart, next_question: null, stop_reason: 'MAX_QUESTIONS', questions_asked_in_session: 3 }
  let answerCalls = 0
  vi.stubGlobal('fetch', vi.fn(async (url, init) => {
    if (url === '/health') return { ok: true, status: 200, json: async () => HEALTH }
    if (url === '/v1/intake/extract') return { ok: true, status: 200, json: async () => ({ candidates: [], mapper_version: 'v1.2' }) }
    if (url === '/v1/session/start') return { ok: true, status: 200, json: async () => turnStart }
    if (url === '/v1/session/answer') {
      answerCalls += 1
      if (answerCalls === 1) {
        return { ok: false, status: 500, json: async () => ({ error: { code: 'INTERNAL_ERROR', message: '서버 오류' } }) }
      }
      return { ok: true, status: 200, json: async () => stopped }
    }
    if (url === '/v1/session/summary') return { ok: true, status: 200, json: async () => summaryFixture }
    return { ok: true, status: 200, json: async () => null }
  }))
  render(<App />)
  await describe(user, '그냥 몸이 좀 이상해요')
  expect(await screen.findByText('말씀하신 내용에서 확실하게 확인할 수 있는 항목을 찾지 못했어요.')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: '가장 불편한 증상 고르기' }))
  await user.type(screen.getByLabelText('증상 찾기'), '어지')
  await user.click(within(screen.getByTestId('initial-results')).getByRole('button', { name: '어지럽고 쓰러질 것 같음' }))
  for (let i = 0; i < 3; i += 1) await user.click(screen.getByRole('button', { name: '없음' }))
  await waitFor(() => expect(screen.getByText('추가로 확인할 정보')).toBeInTheDocument())

  await user.click(screen.getByRole('button', { name: '해당 없음' }))
  await user.click(screen.getByRole('button', { name: '다음' }))
  const retryButton = await screen.findByRole('button', { name: '다시 시도' })
  expect(answerCalls).toBe(1)

  await user.click(retryButton)
  await waitFor(() => expect(answerCalls).toBe(2))
  await waitFor(() => expect(screen.getByText('현재까지 확인된 정보')).toBeInTheDocument())
  await waitFor(() => expect(screen.getByText(summaryFixture.chief_complaint.label_ko)).toBeInTheDocument())
  expect(screen.queryByRole('alert')).toBeNull()
})

test('SUMMARY-RESUME: summary 화면에서 reload 해도 같은 세션으로 summary API 를 다시 불러 같은 요약을 복원한다', async () => {
  const user = userEvent.setup()
  const finalTurn = { ...turnStart, next_question: null, stop_reason: 'MAX_QUESTIONS', questions_asked_in_session: 3 }
  const calls = installRoutes({
    '/v1/intake/extract': { candidates: [], mapper_version: 'v1.2' },
    '/v1/session/start': finalTurn,
    '/v1/session/summary': summaryFixture,
  })
  const first = render(<App />)
  await pickDizzy(user, calls)
  for (let i = 0; i < 3; i += 1) await user.click(screen.getByRole('button', { name: '없음' }))
  await waitFor(() => expect(screen.getByText('현재까지 확인된 정보')).toBeInTheDocument())
  await waitFor(() => expect(screen.getByText(summaryFixture.chief_complaint.label_ko)).toBeInTheDocument())
  expect(screen.queryAllByTestId('candidate-row')).toHaveLength(0)                 // 진단 후보는 의사 화면 전용
  const sectionTextBefore = document.querySelector('.summary').textContent
  first.unmount()

  const resumeCalls = installRoutes({ '/v1/session/resume': finalTurn, '/v1/session/summary': summaryFixture })
  render(<App />)
  await waitFor(() => expect(screen.getByText('현재까지 확인된 정보')).toBeInTheDocument())
  await waitFor(() => expect(screen.getByText(summaryFixture.chief_complaint.label_ko)).toBeInTheDocument())
  expect(screen.queryAllByTestId('candidate-row')).toHaveLength(0)                 // 진단 후보는 의사 화면 전용
  // 같은 세션으로 summary API 를 다시 호출하고, 섹션 전체 텍스트가 reload 전후 동일하다.
  const summaryCall = resumeCalls.find((call) => call.url === '/v1/session/summary')
  expect(summaryCall.body).toEqual({ session: finalTurn.session })
  expect(document.querySelector('.summary').textContent).toBe(sectionTextBefore)
})
