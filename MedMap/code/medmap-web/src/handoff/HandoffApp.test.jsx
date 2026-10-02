import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import HandoffApp, { HANDOFF_DONE_TITLE, HANDOFF_STORAGE_FAILED } from './HandoffApp.jsx'
import turnStart from '../test/fixtures/turn.start.json'

const TYPED = '사흘 전부터 기침이 나고 열이 나요'
const c = (evidence_id, status, label_ko, matched_text, initial_eligible = status === 'POSITIVE') =>
  ({ evidence_id, status, label_ko, matched_text, initial_eligible })

// 통합 테스트 C/D 와 같은 6개 후보: initial 1 + additional 3 → 나머지 E_50·E_212 는 cache
const MANY = [c('E_201', 'POSITIVE', '기침?', '기침'), c('E_91', 'POSITIVE', '열?', '열'), c('E_66', 'POSITIVE', '숨?', '숨이 차'),
  c('E_77', 'POSITIVE', '가래?', '가래도 누렇'), c('E_50', 'POSITIVE', '땀?', '식은땀'), c('E_212', 'POSITIVE', '목소리?', '목소리도 쉬었')]
const yesNo = (id) => ({ ...turnStart.next_question, question_id: id, answer_type: 'YES_NO' })

function fakeApi() {
  return {
    getHealth: vi.fn(async () => ({ status: 'ok', engine_ready: true, max_questions: 3 })),
    extractIntake: vi.fn(async () => ({ candidates: MANY, mapper_version: 'v1.2' })),
    // 기본 흐름이라면 자동 적용됐을 상황(D): IG 첫 질문이 cache 에 있는 E_50
    startSession: vi.fn(async () => ({ ...turnStart, next_question: yesNo('E_50') })),
    submitAnswer: vi.fn(async () => { throw new Error('handoff must not submit answers') }),
    resumeSession: vi.fn(),
    getSummary: vi.fn(),
  }
}

beforeEach(() => sessionStorage.clear())
afterEach(() => vi.restoreAllMocks())

async function runIntake(user) {
  await waitFor(() => expect(screen.getByRole('button', { name: '시작하기' })).toBeEnabled())
  await user.click(screen.getByRole('button', { name: '시작하기' }))
  await user.type(screen.getByLabelText('나이'), '45')
  await user.click(screen.getByRole('button', { name: '남성' }))
  await user.type(screen.getByLabelText('지금 불편한 점을 편하게 적어 주세요'), TYPED)
  await user.click(screen.getByRole('button', { name: '확인하기' }))
  await user.click(await screen.findByRole('button', { name: '다음' }))
  await user.click(screen.getByRole('button', { name: '숨이 참' }))
}

test('handoff intake starts the session without auto-applying the intake cache', async () => {
  const api = fakeApi()
  const user = userEvent.setup()
  const written = []
  const original = Storage.prototype.setItem
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(function spy(key, value) {
    written.push(key)
    return original.call(this, key, value)
  })
  render(<HandoffApp api={api} />)
  await runIntake(user)
  expect(await screen.findByText(HANDOFF_DONE_TITLE)).toBeInTheDocument()
  expect(api.startSession).toHaveBeenCalledTimes(1)
  expect(api.submitAnswer).not.toHaveBeenCalled()
  expect(new Set(written)).toEqual(new Set(['medmap.handoff.session', 'medmap.handoff.cache', 'medmap.handoff.id']))
  expect(sessionStorage.getItem('medmap.handoff.id')).toMatch(/.{8,}/)
  expect(JSON.parse(sessionStorage.getItem('medmap.handoff.session'))).toEqual(turnStart.session)
  expect(JSON.parse(sessionStorage.getItem('medmap.handoff.cache')))
    .toEqual([{ evidence_id: 'E_50', status: 'POSITIVE' }, { evidence_id: 'E_212', status: 'POSITIVE' }])
  expect(api.startSession.mock.calls[0][0].answers.map((a) => a.question_id)).toEqual(['E_201', 'E_91', 'E_77'])
  expect(JSON.stringify({ ...sessionStorage })).not.toContain(TYPED)
  expect(sessionStorage.getItem('medmap.session')).toBeNull()
  expect(sessionStorage.getItem('medmap.intakeCache')).toBeNull()
  expect(screen.getByRole('link', { name: '의사 화면 열기' })).toHaveAttribute('href', '#/doctor')
  expect(screen.queryByText(/추가로 확인할 정보/)).toBeNull()
  vi.restoreAllMocks()
})

test('reload with a stored handoff session shows the done screen; restart clears only handoff keys', async () => {
  sessionStorage.setItem('medmap.handoff.session', JSON.stringify(turnStart.session))
  sessionStorage.setItem('medmap.handoff.cache', '[]')
  sessionStorage.setItem('medmap.session', 'keep')
  const user = userEvent.setup()
  render(<HandoffApp api={fakeApi()} />)
  expect(screen.getByText(HANDOFF_DONE_TITLE)).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: '처음부터 다시' }))
  expect(sessionStorage.getItem('medmap.handoff.session')).toBeNull()
  expect(sessionStorage.getItem('medmap.handoff.cache')).toBeNull()
  expect(sessionStorage.getItem('medmap.session')).toBe('keep')
  expect(screen.getByRole('button', { name: '시작하기' })).toBeInTheDocument()
})

test('storage failure after start does not claim the handoff is ready', async () => {
  const api = fakeApi()
  const user = userEvent.setup()
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('QuotaExceededError') })
  render(<HandoffApp api={api} />)
  await runIntake(user)
  expect(await screen.findByText(HANDOFF_STORAGE_FAILED)).toBeInTheDocument()
  expect(screen.queryByText(HANDOFF_DONE_TITLE)).toBeNull()
  vi.restoreAllMocks()
})

test('Phase A S1: the done screen offers sending to another device only when the server enables it', async () => {
  sessionStorage.setItem('medmap.handoff.session', JSON.stringify(turnStart.session))
  const on = { getHandoffStatus: vi.fn(async () => ({ enabled: true, ttl_s: 900 })), createHandoffCode: vi.fn(), claimHandoffCode: vi.fn() }
  const { unmount } = render(<HandoffApp api={fakeApi()} handoffApi={on} />)
  expect(await screen.findByRole('button', { name: '다른 기기(진료실)로 보내기' })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: '의사 화면 열기' })).toBeInTheDocument()      // 같은 브라우저 인계 유지
  unmount()
  const off = { ...on, getHandoffStatus: vi.fn(async () => ({ enabled: false, ttl_s: 900 })) }
  render(<HandoffApp api={fakeApi()} handoffApi={off} />)
  await screen.findByTestId('handoff-done')
  await waitFor(() => expect(off.getHandoffStatus).toHaveBeenCalled())
  expect(screen.queryByRole('button', { name: '다른 기기(진료실)로 보내기' })).toBeNull()
})
