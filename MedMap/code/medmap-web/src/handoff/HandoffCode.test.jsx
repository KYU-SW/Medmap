import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SendToDevice, { SEND_LABEL, CODE_EXPIRED } from './SendToDevice.jsx'
import HandoffCodeImport, { CLAIM_INVALID, CLAIM_LOCKED } from '../doctor/sections/HandoffCodeImport.jsx'
import { HANDOFF_SESSION_KEY, HANDOFF_CACHE_KEY } from './useHandoffSession.js'
import { ApiError } from '../api/client.js'

const SESSION = { schema_version: 'medmap-session-v1', patient_state: { age: 45 } }
const CACHE = [{ evidence_id: 'E_91', status: 'NEGATIVE' }]

function handoffApi({ enabled = true, codes = ['12345678', '87654321'], expires = 900, claim } = {}) {
  let i = 0
  return {
    getHandoffStatus: vi.fn(async () => ({ enabled, ttl_s: 900 })),
    createHandoffCode: vi.fn(async () => ({ code: codes[i++ % codes.length], expires_in_s: expires })),
    claimHandoffCode: vi.fn(claim ?? (async () => ({ session: SESSION, cache: CACHE }))),
  }
}

beforeEach(() => {
  sessionStorage.clear()
  sessionStorage.setItem(HANDOFF_SESSION_KEY, JSON.stringify(SESSION))
  sessionStorage.setItem(HANDOFF_CACHE_KEY, JSON.stringify(CACHE))
})
afterEach(() => vi.restoreAllMocks())

// ---- 환자 휴대폰: 다른 기기로 보내기 ----
test('disabled on the server → nothing rendered', async () => {
  const api = handoffApi({ enabled: false })
  render(<SendToDevice api={api} />)
  await act(async () => {})
  expect(screen.queryByRole('button', { name: SEND_LABEL })).toBeNull()
})

test('send → code shown as 1234-5678 with remaining time; session and cache sent; code never stored', async () => {
  const user = userEvent.setup()
  const api = handoffApi()
  const setItem = vi.spyOn(Storage.prototype, 'setItem')
  render(<SendToDevice api={api} />)
  await user.click(await screen.findByRole('button', { name: SEND_LABEL }))
  expect(api.createHandoffCode).toHaveBeenCalledWith({ session: SESSION, cache: CACHE })
  const box = await screen.findByTestId('handoff-code')
  expect(box).toHaveTextContent('1234-5678')
  expect(box).toHaveTextContent('15:00')
  expect(setItem).not.toHaveBeenCalled()
  await user.click(screen.getByRole('button', { name: '새 번호 받기' }))
  await waitFor(() => expect(screen.getByTestId('handoff-code')).toHaveTextContent('8765-4321'))
})

test('expired code is replaced by a message and a new-number button', async () => {
  const user = userEvent.setup()
  render(<SendToDevice api={handoffApi({ expires: 1 })} />)
  await user.click(await screen.findByRole('button', { name: SEND_LABEL }))
  expect(await screen.findByText(CODE_EXPIRED, {}, { timeout: 3000 })).toBeInTheDocument()
  expect(screen.queryByText('1234-5678')).toBeNull()
  expect(screen.getByRole('button', { name: '새 번호 받기' })).toBeInTheDocument()
})

test('server capacity error is shown in Korean', async () => {
  const user = userEvent.setup()
  const api = handoffApi()
  api.createHandoffCode.mockRejectedValueOnce(new ApiError(503, 'HANDOFF_CAPACITY', 'HANDOFF_CAPACITY'))
  render(<SendToDevice api={api} />)
  await user.click(await screen.findByRole('button', { name: SEND_LABEL }))
  expect(await screen.findByRole('alert')).toHaveTextContent('잠시 후 다시')
})

// ---- 의사 PC: 번호로 불러오기 ----
test('doctor: 8 digits with auto hyphen → claim → onImport gets {session, cache}', async () => {
  const user = userEvent.setup()
  const api = handoffApi()
  const onImport = vi.fn(() => true)
  render(<HandoffCodeImport api={api} onImport={onImport} />)
  const input = await screen.findByLabelText('환자 번호')
  await user.type(input, '1234a5678')
  expect(input).toHaveValue('1234-5678')
  await user.click(screen.getByRole('button', { name: '번호로 불러오기' }))
  expect(api.claimHandoffCode).toHaveBeenCalledWith('12345678')
  await waitFor(() => expect(onImport).toHaveBeenCalledTimes(1))
  expect(JSON.parse(onImport.mock.calls[0][0])).toEqual({ session: SESSION, cache: CACHE })
})

test('doctor: invalid/expired/used number and lockout show different Korean guidance', async () => {
  const user = userEvent.setup()
  const api = handoffApi({ claim: async () => { throw new ApiError(404, 'HANDOFF_CODE_INVALID', 'x') } })
  const { unmount } = render(<HandoffCodeImport api={api} onImport={vi.fn()} />)
  await user.type(await screen.findByLabelText('환자 번호'), '11112222')
  await user.click(screen.getByRole('button', { name: '번호로 불러오기' }))
  expect(await screen.findByRole('alert')).toHaveTextContent(CLAIM_INVALID)
  unmount()
  const locked = handoffApi({ claim: async () => { throw new ApiError(429, 'HANDOFF_LOCKED', 'x') } })
  render(<HandoffCodeImport api={locked} onImport={vi.fn()} />)
  await user.type(await screen.findByLabelText('환자 번호'), '11112222')
  await user.click(screen.getByRole('button', { name: '번호로 불러오기' }))
  expect(await screen.findByRole('alert')).toHaveTextContent(CLAIM_LOCKED)
})

test('doctor: button disabled until 8 digits; hidden when the server has it off', async () => {
  const user = userEvent.setup()
  render(<HandoffCodeImport api={handoffApi()} onImport={vi.fn()} />)
  await user.type(await screen.findByLabelText('환자 번호'), '1234567')
  expect(screen.getByRole('button', { name: '번호로 불러오기' })).toBeDisabled()
  render(<HandoffCodeImport api={handoffApi({ enabled: false })} onImport={vi.fn()} />)
  await act(async () => {})
  expect(screen.getAllByLabelText('환자 번호')).toHaveLength(1)
})
