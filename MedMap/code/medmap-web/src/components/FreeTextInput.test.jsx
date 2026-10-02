import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import FreeTextInput, { EMPTY_DRAFT } from './FreeTextInput'

// 상위(NaturalIntakeScreen)처럼 draft 를 소유하는 최소 harness. FreeTextInput 자체는 입력 state 를 갖지 않는다.
function Draft({ initial = EMPTY_DRAFT, onDraft, ...props }) {
  const [draft, setDraft] = useState(initial)
  onDraft?.(draft)
  return <FreeTextInput draft={draft} onDraftChange={setDraft} {...props} />
}

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
    this.ondataavailable?.({ data: new Blob(['audio-bytes'], { type: 'audio/webm' }) })
    this.onstop?.()
  }
}
FakeMediaRecorder.isTypeSupported = (type) => type === 'audio/webm;codecs=opus'

function fakeStream() {
  return { getTracks: () => [{ stop: vi.fn() }] }
}

function stubBrowserRecording({ allow = true } = {}) {
  vi.stubGlobal('MediaRecorder', FakeMediaRecorder)
  vi.stubGlobal('navigator', {
    ...globalThis.navigator,
    mediaDevices: {
      getUserMedia: allow
        ? vi.fn(async () => fakeStream())
        : vi.fn(async () => { throw Object.assign(new Error('denied'), { name: 'NotAllowedError' }) }),
    },
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

test('나이·성별·문장이 모두 있어야 제출되고, 문장은 onSubmit 으로만 넘긴다', async () => {
  const user = userEvent.setup()
  const onSubmit = vi.fn()
  render(<Draft onSubmit={onSubmit} />)
  const submit = screen.getByRole('button', { name: '확인하기' })
  expect(submit).toBeDisabled()
  await user.type(screen.getByLabelText('나이'), '45')
  await user.click(screen.getByRole('button', { name: '남성' }))
  await user.type(screen.getByLabelText('지금 불편한 점을 편하게 적어 주세요'), '  기침이 나요 ')
  await user.click(submit)
  expect(onSubmit).toHaveBeenCalledWith({ age: 45, sex: 'M', text: '기침이 나요' })
})

test('입력 길이는 1000자로 제한된다', () => {
  render(<Draft onSubmit={() => {}} />)
  expect(screen.getByLabelText('지금 불편한 점을 편하게 적어 주세요')).toHaveAttribute('maxLength', '1000')
})

test('VoiceInput 이 마운트되어 말하기 버튼을 보여준다', () => {
  render(<Draft onSubmit={() => {}} />)
  expect(screen.getByRole('button', { name: /말하기/ })).toBeInTheDocument()
})

test('음성 전사 결과가 빈 textarea 에 들어간다', async () => {
  stubBrowserRecording({ allow: true })
  vi.stubGlobal('fetch', vi.fn(async () => ({
    ok: true, status: 200, json: async () => ({ transcript: '기침이 나요', duration_s: 1.2, language: 'ko' }),
  })))
  const user = userEvent.setup()
  render(<Draft onSubmit={() => {}} />)
  await user.click(screen.getByRole('button', { name: /말하기/ }))
  await user.click(await screen.findByRole('button', { name: '그만 말하기' }))
  await screen.findByDisplayValue('기침이 나요')
})

test('기존 텍스트가 있으면 음성 전사가 joinTranscript 규칙으로 안전하게 붙는다', async () => {
  stubBrowserRecording({ allow: true })
  vi.stubGlobal('fetch', vi.fn(async () => ({
    ok: true, status: 200, json: async () => ({ transcript: '열도 있어요', duration_s: 1.2, language: 'ko' }),
  })))
  const user = userEvent.setup()
  render(<Draft onSubmit={() => {}} />)
  await user.type(screen.getByLabelText('지금 불편한 점을 편하게 적어 주세요'), '기침이 나요')
  await user.click(screen.getByRole('button', { name: /말하기/ }))
  await user.click(await screen.findByRole('button', { name: '그만 말하기' }))
  await waitFor(() => expect(screen.getByLabelText('지금 불편한 점을 편하게 적어 주세요')).toHaveValue('기침이 나요\n열도 있어요'))
})

test('전사 후에도 textarea 는 편집 가능하다', async () => {
  stubBrowserRecording({ allow: true })
  vi.stubGlobal('fetch', vi.fn(async () => ({
    ok: true, status: 200, json: async () => ({ transcript: '기침이 나요', duration_s: 1.2, language: 'ko' }),
  })))
  const user = userEvent.setup()
  render(<Draft onSubmit={() => {}} />)
  await user.click(screen.getByRole('button', { name: /말하기/ }))
  await user.click(await screen.findByRole('button', { name: '그만 말하기' }))
  const textarea = await screen.findByDisplayValue('기침이 나요')
  await user.type(textarea, ' 그리고 열도 있어요')
  expect(textarea).toHaveValue('기침이 나요 그리고 열도 있어요')
})

test('음성 인식 실패(권한 거부) 는 기존 입력 텍스트를 보존한다', async () => {
  stubBrowserRecording({ allow: false })
  const user = userEvent.setup()
  render(<Draft onSubmit={() => {}} />)
  await user.type(screen.getByLabelText('지금 불편한 점을 편하게 적어 주세요'), '기존 입력')
  await user.click(screen.getByRole('button', { name: /말하기/ }))
  await screen.findByRole('alert')
  expect(screen.getByLabelText('지금 불편한 점을 편하게 적어 주세요')).toHaveValue('기존 입력')
})

test('pending 이면 VoiceInput 의 말하기 버튼도 비활성화된다', () => {
  render(<Draft onSubmit={() => {}} pending />)
  expect(screen.getByRole('button', { name: /말하기/ })).toBeDisabled()
})

test('전사 중(transcribing)에는 확인하기가 비활성화되고, 끝나면 다시 활성화된다', async () => {
  stubBrowserRecording({ allow: true })
  let resolveFetch
  vi.stubGlobal('fetch', vi.fn(() => new Promise((resolve) => { resolveFetch = resolve })))
  const user = userEvent.setup()
  const onSubmit = vi.fn()
  render(<Draft onSubmit={onSubmit} />)
  await user.type(screen.getByLabelText('나이'), '45')
  await user.click(screen.getByRole('button', { name: '남성' }))
  await user.type(screen.getByLabelText('지금 불편한 점을 편하게 적어 주세요'), '기침이 나요')
  expect(screen.getByRole('button', { name: '확인하기' })).toBeEnabled()

  await user.click(screen.getByRole('button', { name: /말하기/ }))
  await user.click(await screen.findByRole('button', { name: '그만 말하기' }))
  await waitFor(() => expect(screen.getByRole('button', { name: '확인하기' })).toBeDisabled())

  resolveFetch({ ok: true, status: 200, json: async () => ({ transcript: '열도 있어요', duration_s: 1, language: 'ko' }) })
  await waitFor(() => expect(screen.getByRole('button', { name: '확인하기' })).toBeEnabled())
  await user.click(screen.getByRole('button', { name: '확인하기' }))
  expect(onSubmit).toHaveBeenCalledTimes(1)
})

test('전사 실패로 끝나도 확인하기가 다시 활성화된다', async () => {
  stubBrowserRecording({ allow: false })
  const user = userEvent.setup()
  render(<Draft onSubmit={() => {}} />)
  await user.type(screen.getByLabelText('나이'), '45')
  await user.click(screen.getByRole('button', { name: '남성' }))
  await user.type(screen.getByLabelText('지금 불편한 점을 편하게 적어 주세요'), '기침이 나요')
  await user.click(screen.getByRole('button', { name: /말하기/ }))
  await screen.findByRole('alert')
  expect(screen.getByRole('button', { name: '확인하기' })).toBeEnabled()
})

test('draft 는 상위가 소유한다: 입력은 onDraftChange 로만 올라가고, 다시 mount 해도 상위 값 그대로 보인다', async () => {
  const user = userEvent.setup()
  let latest = null
  const { unmount } = render(<Draft onSubmit={() => {}} onDraft={(d) => { latest = d }} />)
  await user.type(screen.getByLabelText('나이'), '45')
  await user.click(screen.getByRole('button', { name: '여성' }))
  await user.type(screen.getByLabelText('지금 불편한 점을 편하게 적어 주세요'), '목이 아파요')
  expect(latest).toEqual({ age: '45', sex: 'F', text: '목이 아파요' })
  unmount()
  render(<FreeTextInput draft={latest} onDraftChange={() => {}} onSubmit={() => {}} />)
  expect(screen.getByLabelText('나이')).toHaveValue('45')
  expect(screen.getByRole('button', { name: '여성' })).toHaveAttribute('aria-pressed', 'true')
  expect(screen.getByLabelText('지금 불편한 점을 편하게 적어 주세요')).toHaveValue('목이 아파요')
})

test('전사 중에 이어서 타이핑해도 전사 결과가 도착하면 둘 다 남는다(stale draft 로 되돌아가지 않음)', async () => {
  stubBrowserRecording({ allow: true })
  let resolveFetch
  vi.stubGlobal('fetch', vi.fn(() => new Promise((resolve) => { resolveFetch = resolve })))
  const setItem = vi.spyOn(Storage.prototype, 'setItem')
  const user = userEvent.setup()
  let latest = null
  render(<Draft onSubmit={() => {}} onDraft={(d) => { latest = d }} />)
  const box = screen.getByLabelText('지금 불편한 점을 편하게 적어 주세요')
  await user.type(box, '기침이 나요')
  await user.click(screen.getByRole('button', { name: /말하기/ }))
  await user.click(await screen.findByRole('button', { name: '그만 말하기' }))
  await user.type(box, ' 목도 아파요')                       // 전사 대기 중 추가 입력
  resolveFetch({ ok: true, status: 200, json: async () => ({ transcript: '열도 있어요', duration_s: 1, language: 'ko' }) })
  await waitFor(() => expect(box.value).toContain('열도 있어요'))
  expect(box.value).toContain('기침이 나요 목도 아파요')
  expect(latest.text).toBe(box.value)
  expect(setItem).not.toHaveBeenCalled()                    // 원문·전사문을 저장소에 쓰지 않는다
  setItem.mockRestore()
})

// ---- Streaming STT (Task 7 계약 C5·C6, ledger 참고) ----
import { act as actStream } from '@testing-library/react'
import { loadSttStreaming, __resetSttAvailabilityForTests } from '../voice/sttAvailability'

function streamingFakes() {
  const ctl = {}
  const capture = async ({ onPacket }) => { ctl.onPacket = onPacket; return { stop: () => [] } }
  const connect = async ({ onMessage }) => {
    ctl.onMessage = onMessage
    return { kind: 'ws', sttState: 'WARM', send: () => {}, stop: async () => {}, close: () => {} }
  }
  return { ctl, sttOptions: { capture, connect, raf: (fn) => fn(), transcribeLegacy: async () => ({ transcript: '' }) } }
}

test('C5 availability: flag off, status failure, or no AudioWorklet → streaming false; prewarm only when streaming', async () => {
  const prewarm = vi.fn(async () => ({}))
  __resetSttAvailabilityForTests()
  expect(await loadSttStreaming({ getStatus: async () => ({ streaming: false }), prewarm, hasWorklet: true })).toMatchObject({ streaming: false })
  __resetSttAvailabilityForTests()
  expect(await loadSttStreaming({ getStatus: async () => { throw new Error('x') }, prewarm, hasWorklet: true })).toMatchObject({ streaming: false })
  __resetSttAvailabilityForTests()
  expect(await loadSttStreaming({ getStatus: async () => ({ streaming: true }), prewarm, hasWorklet: false })).toMatchObject({ streaming: false })
  expect(prewarm).not.toHaveBeenCalled()
  __resetSttAvailabilityForTests()
  expect(await loadSttStreaming({ getStatus: async () => ({ streaming: true, stt_state: 'COLD' }), prewarm, hasWorklet: true }))
    .toEqual({ streaming: true, sttState: 'COLD' })
  await new Promise((r) => setTimeout(r, 0))
  expect(prewarm).toHaveBeenCalledTimes(1)
  __resetSttAvailabilityForTests()
})

test('C5 streaming unavailable keeps the existing VoiceInput exactly (no partial line)', async () => {
  render(<Draft sttAvailability={async () => ({ streaming: false })} />)
  await actStream(async () => {})
  expect(screen.getByRole('button', { name: '🎙 말하기' })).toBeInTheDocument()
  await userEvent.setup().click(screen.getByRole('button', { name: '🎙 말하기' }))
  expect(screen.queryByTestId('stt-partial')).toBeNull()
})

test('C6 streaming: PARTIAL shows outside the textarea and never changes it; FINAL appends via joinTranscript', async () => {
  const { ctl, sttOptions } = streamingFakes()
  const user = userEvent.setup()
  let latest
  render(<Draft initial={{ age: '45', sex: 'M', text: '어제부터' }} onDraft={(d) => { latest = d }}
    sttAvailability={async () => ({ streaming: true })} sttOptions={sttOptions} />)
  await actStream(async () => {})
  const box = screen.getByLabelText('지금 불편한 점을 편하게 적어 주세요')
  box.focus()
  box.setSelectionRange(2, 2)
  await user.click(screen.getByRole('button', { name: '🎙 말하기' }))
  await screen.findByText('● 듣고 있어요')
  actStream(() => ctl.onMessage({ type: 'partial', utt: 1, stable: '배가', unstable: ' 아프', audio_ms: 500, srv_ms: {} }))
  expect(screen.getByTestId('stt-partial')).toHaveTextContent('배가 아프')
  expect(box).toHaveValue('어제부터')
  expect(latest.text).toBe('어제부터')
  actStream(() => ctl.onMessage({ type: 'final', utt: 1, text: '배가 아파요', audio_ms: 900, srv_ms: {} }))
  expect(box).toHaveValue('어제부터.\n배가 아파요')
  expect(screen.getByTestId('stt-partial')).not.toHaveTextContent('아프')
})
