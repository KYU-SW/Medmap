import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import DoctorApp from './DoctorApp.jsx'
import { COPY } from './copy.js'
import turnStart from '../test/fixtures/turn.start.json'

const SESSION = turnStart.session
const yesNo = (id) => ({
  question_id: id, question_ko: `${id} 질문`, question_original: id, answer_type: 'YES_NO', is_fallback: false,
  choices: [{ value: true, label: '예', original_label: null, is_fallback: false },
    { value: false, label: '아니요', original_label: null, is_fallback: false },
    { value: null, label: '잘 모르겠어요', original_label: null, is_fallback: false }],
})
const CANDIDATES = Array.from({ length: 8 }, (_, i) => ({ code: `D${i}`, label_ko: `질환${i}` }))
const SUMMARY = {
  age: 45, sex: 'M', chief_complaint: { question_id: 'E_53', label_ko: '통증', question_ko: '통증이 있나요?' },
  confirmed_positive: [], confirmed_negative: [{ question_id: 'E_91', question_ko: '열이 있나요?', answer_ko: '없음' }],
  confirmed_values: [], not_applicable: [], unknown: [], answered_questions: [{}, {}, {}, {}], questions_used: 0,
}
const EXT = Object.fromEntries(['timeline', 'episode', 'diagnosis_coverage', 'unexplained_findings', 'alternatives',
  'turning_points', 'visit', 'recovery'].map((k) => [k, { status: 'NOT_AVAILABLE', reason: 'X' }]))

function makeView(wd, { question = yesNo('E_77'), used = 0, status, session = SESSION } = {}) {
  const locked = wd.state === 'PENDING'
  const value = wd.value ? { ...wd.value, label: wd.value.label ?? `라벨-${wd.value.code}` } : null
  return {
    schema_version: 'medmap-doctor-view-v1',
    patient_summary: SUMMARY,
    working_diagnosis: { state: wd.state, value },
    independent_assessment: locked ? { status: 'LOCKED' }
      : { status: 'AVAILABLE', candidates: CANDIDATES, scope_ko: '모델이 학습한 49개 질환 안에서만 고려합니다', model: { context: 'k3' } },
    next_information: locked ? { status: 'LOCKED' }
      : { status: status ?? (question ? 'QUESTION' : 'BUDGET_REACHED'), question, questions_used: used, max_questions: 3 },
    extensions: EXT,
    session,
  }
}

function fakeApi(overrides = {}) {
  const calls = []
  const api = {
    getDoctorDiagnoses: vi.fn(async () => ({ diagnoses: [{ code: 'Bronchitis', label_ko: '기관지염' }, { code: 'URTI', label_ko: '상기도 감염' }] })),
    getDoctorView: vi.fn(async (args) => { calls.push(['view', args]); return makeView(args.workingDiagnosis) }),
    submitDoctorAnswer: vi.fn(async (args) => {
      calls.push(['answer', args])
      const n = calls.filter(([t]) => t === 'answer').length
      return makeView(args.workingDiagnosis, { question: n < 3 ? yesNo(`E_${100 + n}`) : null, used: n,
        session: { ...SESSION, step: n } })
    }),
    ...overrides,
  }
  return { api, calls }
}

beforeEach(() => sessionStorage.clear())

test('no stored session → load screen with paste/file import', async () => {
  const { api } = fakeApi()
  render(<DoctorApp api={api} />)
  expect(await screen.findByText(COPY.loadTitle)).toBeInTheDocument()
  expect(api.getDoctorView).not.toHaveBeenCalled()
})

test('blind: candidates and question are hidden until the working diagnosis is skipped', async () => {
  sessionStorage.setItem('medmap.handoff.session', JSON.stringify(SESSION))
  const { api } = fakeApi()
  const user = userEvent.setup()
  render(<DoctorApp api={api} />)
  expect(await screen.findByText(COPY.summaryTitle)).toBeInTheDocument()
  expect(screen.queryByTestId('doctor-candidates')).toBeNull()
  expect(screen.queryByTestId('doctor-next')).toBeNull()
  expect(api.getDoctorView.mock.calls[0][0].workingDiagnosis).toEqual({ state: 'PENDING' })
  await user.click(screen.getByRole('button', { name: COPY.wdSkip }))
  const list = await screen.findByTestId('doctor-candidates')
  expect(within(list).getAllByRole('listitem')).toHaveLength(5)
  expect(screen.getByText(COPY.candidatesNotExcluded)).toBeInTheDocument()
  await user.click(within(list).getByRole('button', { name: COPY.more }))
  expect(within(list).getAllByRole('listitem')).toHaveLength(8)
  expect(screen.getByTestId('doctor-next')).toBeInTheDocument()
  expect(document.body.textContent).not.toMatch(/%|\d\.\d/)
})

test('catalog working diagnosis via search and out-of-scope free text', async () => {
  sessionStorage.setItem('medmap.handoff.session', JSON.stringify(SESSION))
  const { api } = fakeApi()
  const user = userEvent.setup()
  render(<DoctorApp api={api} />)
  await screen.findByText(COPY.summaryTitle)
  await user.type(screen.getByLabelText(COPY.wdSearchLabel), '기관지')
  await user.click(screen.getByRole('button', { name: '기관지염' }))
  await screen.findByTestId('doctor-candidates')
  expect(api.getDoctorView).toHaveBeenLastCalledWith({ session: SESSION,
    workingDiagnosis: { state: 'ENTERED', value: { kind: 'CATALOG', code: 'Bronchitis' } } })
  await user.click(screen.getByRole('button', { name: COPY.wdChange }))
  await user.type(screen.getByLabelText(COPY.wdFreeLabel), '급성 충수염')
  await user.click(screen.getByRole('button', { name: COPY.wdFreeSubmit }))
  await waitFor(() => expect(screen.getByTestId('doctor-wd-value')).toHaveTextContent('급성 충수염'))
  expect(screen.getByText(COPY.wdOutOfScope)).toBeInTheDocument()
  expect(screen.getByTestId('doctor-candidates')).toBeInTheDocument()     // 다시 숨기지 않는다
})

test('doctor answers IG questions up to the budget; patient originals are untouched', async () => {
  const handoff = JSON.stringify(SESSION)
  sessionStorage.setItem('medmap.handoff.session', handoff)
  sessionStorage.setItem('medmap.handoff.cache', JSON.stringify([{ evidence_id: 'E_101', status: 'POSITIVE' }]))
  sessionStorage.setItem('medmap.session', '{"patient":"original"}')
  const { api } = fakeApi()
  const user = userEvent.setup()
  render(<DoctorApp api={api} />)
  await screen.findByText(COPY.summaryTitle)
  await user.click(screen.getByRole('button', { name: COPY.wdSkip }))
  await screen.findByText('E_77 질문')
  expect(screen.queryByTestId('doctor-patient-said')).toBeNull()
  await user.click(screen.getByRole('button', { name: '아니요' }))
  // 두 번째 질문 E_101 은 cache 적중: 보여주기만 하고 자동 제출하지 않는다
  expect(await screen.findByTestId('doctor-patient-said')).toHaveTextContent(`${COPY.patientSaid}: 예`)
  // Phase 2a: 같은 cache 항목은 환자 요약의 '반영되지 않은 확인 소견'에도 보인다(표시만 — 자동 제출 없음)
  expect(within(screen.getByTestId('doctor-findings-unapplied')).getByText('지난 1년 동안 천식 발작으로 입원한 적이 있나요?')).toBeInTheDocument()
  expect(api.submitDoctorAnswer).toHaveBeenCalledTimes(1)
  expect(screen.getByTestId('doctor-next-counter')).toHaveTextContent('질문 1 / 3')
  await user.click(screen.getByRole('button', { name: COPY.confirmPatient }))
  await screen.findByText('E_102 질문')
  expect(api.submitDoctorAnswer.mock.calls[1][0]).toMatchObject({ questionId: 'E_101', kind: 'POSITIVE', value: null })
  expect(JSON.parse(sessionStorage.getItem('medmap.doctor.cache'))).toEqual([])
  expect(screen.queryByTestId('doctor-findings-unapplied')).toBeNull()             // 의사가 확인해 반영된 뒤에는 목록에서 빠진다
  await user.click(screen.getByRole('button', { name: '잘 모르겠어요' }))
  expect(await screen.findByText(COPY.budgetReached)).toBeInTheDocument()
  expect(api.submitDoctorAnswer).toHaveBeenCalledTimes(3)
  // 원본 키는 바이트 동일, 사본만 갱신
  expect(sessionStorage.getItem('medmap.handoff.session')).toBe(handoff)
  expect(JSON.parse(sessionStorage.getItem('medmap.handoff.cache'))).toEqual([{ evidence_id: 'E_101', status: 'POSITIVE' }])
  expect(sessionStorage.getItem('medmap.session')).toBe('{"patient":"original"}')
  expect(JSON.parse(sessionStorage.getItem('medmap.doctor.session')).step).toBe(3)
})

test('stored doctor copy restores working diagnosis state after reload', async () => {
  const handoffRaw = JSON.stringify({ ...SESSION, other: true })
  sessionStorage.setItem('medmap.doctor.session', JSON.stringify(SESSION))
  sessionStorage.setItem('medmap.doctor.wd', JSON.stringify({ state: 'SKIPPED' }))
  sessionStorage.setItem('medmap.handoff.session', handoffRaw)
  sessionStorage.setItem('medmap.doctor.seen', JSON.stringify({ handoff: handoffRaw, patient: null }))
  const { api } = fakeApi()
  render(<DoctorApp api={api} />)
  expect(await screen.findByTestId('doctor-candidates')).toBeInTheDocument()
  expect(api.getDoctorView.mock.calls[0][0]).toEqual({ session: SESSION, workingDiagnosis: { state: 'SKIPPED' } })
})

test('paste import: invalid JSON shows message, valid session opens', async () => {
  const { api } = fakeApi()
  const user = userEvent.setup()
  render(<DoctorApp api={api} />)
  await screen.findByText(COPY.loadTitle)
  const box = screen.getByLabelText(COPY.loadPasteLabel)
  await user.type(box, 'not json')
  await user.click(screen.getByRole('button', { name: COPY.loadPasteSubmit }))
  expect(screen.getByText(COPY.loadInvalid)).toBeInTheDocument()
  await user.clear(box)
  await user.click(box)
  await user.paste(JSON.stringify(SESSION))
  await user.click(screen.getByRole('button', { name: COPY.loadPasteSubmit }))
  expect(await screen.findByText(COPY.summaryTitle)).toBeInTheDocument()
})

test('network error keeps the load screen with retry, then recovers', async () => {
  sessionStorage.setItem('medmap.handoff.session', JSON.stringify(SESSION))
  let fail = true
  const { api } = fakeApi({
    getDoctorView: vi.fn(async (args) => {
      if (fail) { fail = false; throw Object.assign(new Error('x'), { code: 'NETWORK_ERROR', status: 0 }) }
      return makeView(args.workingDiagnosis)
    }),
  })
  const user = userEvent.setup()
  render(<DoctorApp api={api} />)
  await user.click(await screen.findByRole('button', { name: COPY.retry }))
  expect(await screen.findByText(COPY.summaryTitle)).toBeInTheDocument()
  expect(sessionStorage.getItem('medmap.handoff.session')).toBe(JSON.stringify(SESSION))
})

test('coming-soon slots render without fake results and the prototype notice is always shown', async () => {
  sessionStorage.setItem('medmap.handoff.session', JSON.stringify(SESSION))
  const { api } = fakeApi()
  render(<DoctorApp api={api} />)
  await screen.findByText(COPY.comingSoonTitle)
  expect(screen.getAllByText(COPY.comingSoonReason)).toHaveLength(Object.keys(COPY.comingSoon).length)
  expect(screen.getByText(COPY.prototypeNotice)).toBeInTheDocument()
})

test('a new handoff replaces the previous patient doctor copy (no wrong patient)', async () => {
  const patientA = { ...SESSION, who: 'A' }
  const patientB = { ...SESSION, who: 'B' }
  sessionStorage.setItem('medmap.doctor.session', JSON.stringify(patientA))
  sessionStorage.setItem('medmap.doctor.wd', JSON.stringify({ state: 'SKIPPED' }))
  sessionStorage.setItem('medmap.doctor.cache', JSON.stringify([{ evidence_id: 'E_9', status: 'POSITIVE' }]))
  sessionStorage.setItem('medmap.doctor.seen', JSON.stringify({ handoff: JSON.stringify(patientA), patient: null }))
  sessionStorage.setItem('medmap.handoff.session', JSON.stringify(patientB))
  sessionStorage.setItem('medmap.handoff.cache', '[]')
  const { api } = fakeApi()
  render(<DoctorApp api={api} />)
  await screen.findByText(COPY.summaryTitle)
  expect(api.getDoctorView.mock.calls[0][0]).toEqual({ session: patientB, workingDiagnosis: { state: 'PENDING' } })
  expect(JSON.parse(sessionStorage.getItem('medmap.doctor.cache'))).toEqual([])
  expect(JSON.parse(sessionStorage.getItem('medmap.doctor.seen')).handoff).toBe(JSON.stringify(patientB))
})

test('patient-said is shown only for YES_NO questions', async () => {
  sessionStorage.setItem('medmap.handoff.session', JSON.stringify(SESSION))
  sessionStorage.setItem('medmap.handoff.cache', JSON.stringify([{ evidence_id: 'E_77', status: 'POSITIVE' }]))
  const valueQuestion = { ...yesNo('E_77'), answer_type: 'SINGLE_CHOICE',
    choices: [{ value: 'V_1', label: '값1', original_label: null, is_fallback: false }] }
  const { api } = fakeApi({ getDoctorView: vi.fn(async (args) => makeView(args.workingDiagnosis, { question: valueQuestion })) })
  const user = userEvent.setup()
  render(<DoctorApp api={api} />)
  await screen.findByText(COPY.summaryTitle)
  await user.click(screen.getByRole('button', { name: COPY.wdSkip }))
  await screen.findByText('E_77 질문')
  expect(screen.queryByTestId('doctor-patient-said')).toBeNull()
})

test('the same intake handed off again (identical session bytes) opens fresh, keyed by the handoff id', async () => {
  const raw = JSON.stringify(SESSION)
  sessionStorage.setItem('medmap.doctor.session', JSON.stringify({ ...SESSION, answered: 3 }))
  sessionStorage.setItem('medmap.doctor.wd', JSON.stringify({ state: 'SKIPPED' }))
  sessionStorage.setItem('medmap.doctor.seen', JSON.stringify({ handoff: 'id-1', patient: null }))
  sessionStorage.setItem('medmap.handoff.session', raw)
  sessionStorage.setItem('medmap.handoff.id', 'id-2')
  const { api } = fakeApi()
  render(<DoctorApp api={api} />)
  await screen.findByText(COPY.summaryTitle)
  expect(api.getDoctorView.mock.calls[0][0]).toEqual({ session: SESSION, workingDiagnosis: { state: 'PENDING' } })
  expect(JSON.parse(sessionStorage.getItem('medmap.doctor.seen')).handoff).toBe('id-2')
})

// ---- M5: T_next 계측(숫자만) — 답 클릭 → 응답 → 새 후보·다음 질문(또는 한도 도달) 렌더 ----
import { perfEntries, perfReset } from '../voice/perf.js'

test('M5 answer timing marks: click → response → next render, numbers only, one set per answer', async () => {
  sessionStorage.setItem('medmap.handoff.session', JSON.stringify(SESSION))
  const { api } = fakeApi()
  const user = userEvent.setup()
  render(<DoctorApp api={api} />)
  await screen.findByText(COPY.summaryTitle)
  await user.click(screen.getByRole('button', { name: COPY.wdSkip }))
  await screen.findByText('E_77 질문')
  perfReset()
  await user.click(screen.getByRole('button', { name: '아니요' }))
  await screen.findByText('E_101 질문')
  await user.click(screen.getByRole('button', { name: '아니요' }))
  await screen.findByText('E_102 질문')
  await user.click(screen.getByRole('button', { name: '아니요' }))
  await screen.findByText(COPY.budgetReached)
  const marks = perfEntries().filter((e) => e.name.startsWith('doctor_'))
  expect(marks.map((e) => e.name)).toEqual([
    'doctor_answer_click', 'doctor_answer_response', 'doctor_next_render',
    'doctor_answer_click', 'doctor_answer_response', 'doctor_next_render',
    'doctor_answer_click', 'doctor_answer_response', 'doctor_next_render',
  ])
  for (let i = 0; i < marks.length; i += 3) expect(marks[i].t <= marks[i + 1].t && marks[i + 1].t <= marks[i + 2].t).toBe(true)
  expect(marks.filter((e) => e.name === 'doctor_next_render').map((e) => e.questions_used)).toEqual([1, 2, 3])
  const allowed = new Set(['name', 't', 'questions_used'])
  for (const e of marks) expect(Object.keys(e).every((k) => allowed.has(k))).toBe(true)    // 질문 id·답·후보 없음
})

// ---- Phase A S1: 환자 번호로 불러오기 ----
test('handoff code: number → claim → the patient session opens (blind), cache kept as doctor copy', async () => {
  const { api } = fakeApi()
  const handoffApi = {
    getHandoffStatus: vi.fn(async () => ({ enabled: true, ttl_s: 900 })),
    createHandoffCode: vi.fn(),
    claimHandoffCode: vi.fn(async () => ({ session: SESSION, cache: [{ evidence_id: 'E_101', status: 'POSITIVE' }] })),
  }
  const user = userEvent.setup()
  render(<DoctorApp api={api} handoffApi={handoffApi} />)
  await user.type(await screen.findByLabelText('환자 번호'), '12345678')
  await user.click(screen.getByRole('button', { name: '번호로 불러오기' }))
  expect(await screen.findByText(COPY.summaryTitle)).toBeInTheDocument()
  expect(handoffApi.claimHandoffCode).toHaveBeenCalledWith('12345678')
  expect(api.getDoctorView.mock.calls[0][0]).toMatchObject({ session: SESSION, workingDiagnosis: { state: 'PENDING' } })
  expect(screen.queryByTestId('doctor-candidates')).toBeNull()                    // blind 유지
  expect(JSON.parse(sessionStorage.getItem('medmap.doctor.cache'))).toEqual([{ evidence_id: 'E_101', status: 'POSITIVE' }])
})
