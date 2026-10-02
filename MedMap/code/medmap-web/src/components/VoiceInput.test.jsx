import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import VoiceInput, { __resetVoiceInputTranscribeHintForTests } from './VoiceInput'

class FakeMediaRecorder {
  constructor(stream, options) {
    FakeMediaRecorder.lastOptions = options
    this.state = 'inactive'
    this.ondataavailable = null
    this.onstop = null
  }

  start() {
    this.state = 'recording'
  }

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

function fakeStream() {
  const tracks = [{ stop: vi.fn() }]
  return { getTracks: () => tracks }
}

beforeEach(() => {
  FakeMediaRecorder.nextBlob = undefined
  __resetVoiceInputTranscribeHintForTests()
})

afterEach(() => {
  vi.useRealTimers()
})

test('idle: 말하기 버튼이 보인다', () => {
  render(<VoiceInput onTranscript={() => {}} getUserMedia={vi.fn()} MediaRecorderImpl={FakeMediaRecorder} />)
  expect(screen.getByRole('button', { name: /말하기/ })).toBeInTheDocument()
})

test('허가되면 녹음 상태와 그만 말하기 버튼으로 바뀐다', async () => {
  const user = userEvent.setup()
  const getUserMedia = vi.fn(async () => fakeStream())
  render(<VoiceInput onTranscript={() => {}} getUserMedia={getUserMedia} MediaRecorderImpl={FakeMediaRecorder} />)
  await user.click(screen.getByRole('button', { name: /말하기/ }))
  expect(await screen.findByRole('button', { name: '그만 말하기' })).toBeInTheDocument()
  expect(screen.getByText(/듣고 있어요/)).toBeInTheDocument()
})

test('권한 거부 시 안내 문구를 보여주고 내부 코드를 노출하지 않는다', async () => {
  const user = userEvent.setup()
  const getUserMedia = vi.fn(async () => { throw Object.assign(new Error('denied'), { name: 'NotAllowedError' }) })
  render(<VoiceInput onTranscript={() => {}} getUserMedia={getUserMedia} MediaRecorderImpl={FakeMediaRecorder} />)
  await user.click(screen.getByRole('button', { name: /말하기/ }))
  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent('마이크를 사용할 수 없습니다. 직접 입력해서 계속할 수 있어요.')
  expect(alert.textContent).not.toMatch(/permission|NotAllowedError/i)
})

test('마이크 없음도 같은 안내 문구를 보여준다', async () => {
  const user = userEvent.setup()
  const getUserMedia = vi.fn(async () => { throw Object.assign(new Error('none'), { name: 'NotFoundError' }) })
  render(<VoiceInput onTranscript={() => {}} getUserMedia={getUserMedia} MediaRecorderImpl={FakeMediaRecorder} />)
  await user.click(screen.getByRole('button', { name: /말하기/ }))
  expect(await screen.findByRole('alert')).toHaveTextContent('마이크를 사용할 수 없습니다. 직접 입력해서 계속할 수 있어요.')
})

test('미지원 환경도 같은 안내 문구를 보여준다', async () => {
  const user = userEvent.setup()
  render(<VoiceInput onTranscript={() => {}} getUserMedia={undefined} MediaRecorderImpl={undefined} />)
  await user.click(screen.getByRole('button', { name: /말하기/ }))
  expect(await screen.findByRole('alert')).toHaveTextContent('마이크를 사용할 수 없습니다. 직접 입력해서 계속할 수 있어요.')
})

test('타이머는 MM:SS 로 표시된다', async () => {
  vi.useFakeTimers()
  const getUserMedia = vi.fn(async () => fakeStream())
  render(<VoiceInput onTranscript={() => {}} getUserMedia={getUserMedia} MediaRecorderImpl={FakeMediaRecorder} />)
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: /말하기/ })) })
  expect(screen.getByRole('button', { name: '그만 말하기' })).toBeInTheDocument()
  await act(async () => { await vi.advanceTimersByTimeAsync(5000) })
  expect(screen.getByText(/00:05/)).toBeInTheDocument()
})

test('60초에 도달하면 자동으로 멈추고 전사한다', async () => {
  vi.useFakeTimers()
  const getUserMedia = vi.fn(async () => fakeStream())
  const transcribe = vi.fn(async () => ({ transcript: '자동으로 멈췄어요', duration_s: 60, language: 'ko' }))
  const onTranscript = vi.fn()
  render(<VoiceInput onTranscript={onTranscript} transcribe={transcribe} getUserMedia={getUserMedia} MediaRecorderImpl={FakeMediaRecorder} />)
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: /말하기/ })) })
  expect(screen.getByRole('button', { name: '그만 말하기' })).toBeInTheDocument()
  await act(async () => { await vi.advanceTimersByTimeAsync(60000) })
  expect(onTranscript).toHaveBeenCalledWith('자동으로 멈췄어요')
})

test('그만 말하기를 누르면 transcribing 상태를 보여주고 성공하면 onTranscript 만 호출한다', async () => {
  const user = userEvent.setup()
  const getUserMedia = vi.fn(async () => fakeStream())
  let resolveTranscribe
  const transcribe = vi.fn(() => new Promise((resolve) => { resolveTranscribe = resolve }))
  const onTranscript = vi.fn()
  render(<VoiceInput onTranscript={onTranscript} transcribe={transcribe} getUserMedia={getUserMedia} MediaRecorderImpl={FakeMediaRecorder} />)
  await user.click(screen.getByRole('button', { name: /말하기/ }))
  await user.click(await screen.findByRole('button', { name: '그만 말하기' }))
  expect(await screen.findByRole('status')).toHaveTextContent('음성을 글로 바꾸는 중')
  resolveTranscribe({ transcript: '기침이 나요', duration_s: 1.2, language: 'ko' })
  await waitFor(() => expect(onTranscript).toHaveBeenCalledWith('기침이 나요'))
  expect(onTranscript).toHaveBeenCalledTimes(1)
  expect(screen.queryByRole('status')).toBeNull()
  expect(screen.getByRole('button', { name: /말하기/ })).toBeInTheDocument()
})

test('빈 녹음(무음)은 별도 안내 문구를 보여준다', async () => {
  FakeMediaRecorder.nextBlob = new Blob([], { type: 'audio/webm' })
  const user = userEvent.setup()
  const getUserMedia = vi.fn(async () => fakeStream())
  render(<VoiceInput onTranscript={() => {}} getUserMedia={getUserMedia} MediaRecorderImpl={FakeMediaRecorder} />)
  await user.click(screen.getByRole('button', { name: /말하기/ }))
  await user.click(await screen.findByRole('button', { name: '그만 말하기' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('음성이 감지되지 않았어요. 다시 말하거나 직접 입력해 주세요.')
})

test('서버 오류(AUDIO_EMPTY)는 내부 코드 없이 안내 문구를 보여준다', async () => {
  const user = userEvent.setup()
  const getUserMedia = vi.fn(async () => fakeStream())
  const transcribe = vi.fn(async () => { throw Object.assign(new Error('AUDIO_EMPTY'), { code: 'AUDIO_EMPTY', status: 422 }) })
  render(<VoiceInput onTranscript={() => {}} transcribe={transcribe} getUserMedia={getUserMedia} MediaRecorderImpl={FakeMediaRecorder} />)
  await user.click(screen.getByRole('button', { name: /말하기/ }))
  await user.click(await screen.findByRole('button', { name: '그만 말하기' }))
  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent('음성이 감지되지 않았어요. 다시 말하거나 직접 입력해 주세요.')
  expect(alert.textContent).not.toMatch(/AUDIO_EMPTY|422/)
})

test('네트워크 오류는 일반 실패 안내 문구를 보여준다', async () => {
  const user = userEvent.setup()
  const getUserMedia = vi.fn(async () => fakeStream())
  const transcribe = vi.fn(async () => { throw Object.assign(new Error('network down'), { code: 'NETWORK_ERROR', status: 0 }) })
  render(<VoiceInput onTranscript={() => {}} transcribe={transcribe} getUserMedia={getUserMedia} MediaRecorderImpl={FakeMediaRecorder} />)
  await user.click(screen.getByRole('button', { name: /말하기/ }))
  await user.click(await screen.findByRole('button', { name: '그만 말하기' }))
  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent('음성을 글로 바꾸지 못했어요. 직접 입력해서 계속할 수 있어요.')
  expect(alert.textContent).not.toMatch(/NETWORK_ERROR/)
})

test('자동 submit 은 하지 않는다: onTranscript 외 다른 콜백을 부르지 않는다', async () => {
  const user = userEvent.setup()
  const getUserMedia = vi.fn(async () => fakeStream())
  const transcribe = vi.fn(async () => ({ transcript: '기침', duration_s: 1, language: 'ko' }))
  const onTranscript = vi.fn()
  render(<VoiceInput onTranscript={onTranscript} transcribe={transcribe} getUserMedia={getUserMedia} MediaRecorderImpl={FakeMediaRecorder} />)
  await user.click(screen.getByRole('button', { name: /말하기/ }))
  await user.click(await screen.findByRole('button', { name: '그만 말하기' }))
  await waitFor(() => expect(onTranscript).toHaveBeenCalledTimes(1))
  expect(onTranscript).toHaveBeenCalledWith('기침')
})

test('disabled 면 말하기 버튼이 비활성화된다', () => {
  render(<VoiceInput onTranscript={() => {}} disabled getUserMedia={vi.fn()} MediaRecorderImpl={FakeMediaRecorder} />)
  expect(screen.getByRole('button', { name: /말하기/ })).toBeDisabled()
})

test('onBusyChange: transcribing 이 되면 true, 끝나면 false 로 알린다', async () => {
  const user = userEvent.setup()
  const getUserMedia = vi.fn(async () => fakeStream())
  let resolveTranscribe
  const transcribe = vi.fn(() => new Promise((resolve) => { resolveTranscribe = resolve }))
  const onBusyChange = vi.fn()
  render(<VoiceInput onTranscript={() => {}} transcribe={transcribe} getUserMedia={getUserMedia} MediaRecorderImpl={FakeMediaRecorder} onBusyChange={onBusyChange} />)
  expect(onBusyChange).toHaveBeenCalledWith(false)
  onBusyChange.mockClear()
  await user.click(screen.getByRole('button', { name: /말하기/ }))
  await user.click(await screen.findByRole('button', { name: '그만 말하기' }))
  await waitFor(() => expect(onBusyChange).toHaveBeenCalledWith(true))
  resolveTranscribe({ transcript: '기침', duration_s: 1, language: 'ko' })
  await waitFor(() => expect(onBusyChange).toHaveBeenLastCalledWith(false))
})

test('onBusyChange: 오류로 끝나도 false 로 돌아온다', async () => {
  const user = userEvent.setup()
  const getUserMedia = vi.fn(async () => fakeStream())
  const transcribe = vi.fn(async () => { throw Object.assign(new Error('x'), { code: 'transcribe_failed' }) })
  const onBusyChange = vi.fn()
  render(<VoiceInput onTranscript={() => {}} transcribe={transcribe} getUserMedia={getUserMedia} MediaRecorderImpl={FakeMediaRecorder} onBusyChange={onBusyChange} />)
  await user.click(screen.getByRole('button', { name: /말하기/ }))
  await user.click(await screen.findByRole('button', { name: '그만 말하기' }))
  await waitFor(() => expect(onBusyChange).toHaveBeenLastCalledWith(false))
})

test('onBusyChange: unmount 시 false 로 정리한다', async () => {
  const user = userEvent.setup()
  const getUserMedia = vi.fn(async () => fakeStream())
  const transcribe = vi.fn(() => new Promise(() => {}))
  const onBusyChange = vi.fn()
  const { unmount } = render(<VoiceInput onTranscript={() => {}} transcribe={transcribe} getUserMedia={getUserMedia} MediaRecorderImpl={FakeMediaRecorder} onBusyChange={onBusyChange} />)
  await user.click(screen.getByRole('button', { name: /말하기/ }))
  await user.click(await screen.findByRole('button', { name: '그만 말하기' }))
  await waitFor(() => expect(onBusyChange).toHaveBeenLastCalledWith(true))
  unmount()
  expect(onBusyChange).toHaveBeenLastCalledWith(false)
})

test('transcribing 상태 문구는 "...입니다"로 끝나고, 이 탭 첫 전사 전에는 10초 안내가 함께 보인다', async () => {
  const user = userEvent.setup()
  const getUserMedia = vi.fn(async () => fakeStream())
  let resolveTranscribe
  const transcribe = vi.fn(() => new Promise((resolve) => { resolveTranscribe = resolve }))
  render(<VoiceInput onTranscript={() => {}} transcribe={transcribe} getUserMedia={getUserMedia} MediaRecorderImpl={FakeMediaRecorder} />)
  await user.click(screen.getByRole('button', { name: /말하기/ }))
  await user.click(await screen.findByRole('button', { name: '그만 말하기' }))
  const status = await screen.findByRole('status')
  expect(status).toHaveTextContent('음성을 글로 바꾸는 중입니다.')
  expect(screen.getByText('처음 한 번은 약 10초 정도 걸릴 수 있습니다.')).toBeInTheDocument()
  resolveTranscribe({ transcript: '기침', duration_s: 1, language: 'ko' })
  await waitFor(() => expect(screen.queryByRole('status')).toBeNull())
})

test('첫 전사가 성공한 뒤에는 10초 안내를 더 이상 보여주지 않는다', async () => {
  const user = userEvent.setup()
  const getUserMedia = vi.fn(async () => fakeStream())
  const transcribe = vi.fn(async () => ({ transcript: '기침', duration_s: 1, language: 'ko' }))
  render(<VoiceInput onTranscript={() => {}} transcribe={transcribe} getUserMedia={getUserMedia} MediaRecorderImpl={FakeMediaRecorder} />)
  await user.click(screen.getByRole('button', { name: /말하기/ }))
  await user.click(await screen.findByRole('button', { name: '그만 말하기' }))
  await waitFor(() => expect(screen.queryByRole('status')).toBeNull())

  let resolveSecond
  const transcribe2 = vi.fn(() => new Promise((resolve) => { resolveSecond = resolve }))
  render(<VoiceInput onTranscript={() => {}} transcribe={transcribe2} getUserMedia={getUserMedia} MediaRecorderImpl={FakeMediaRecorder} />)
  const buttons = screen.getAllByRole('button', { name: /말하기/ })
  await user.click(buttons[buttons.length - 1])
  await user.click((await screen.findAllByRole('button', { name: '그만 말하기' })).slice(-1)[0])
  await screen.findAllByRole('status')
  expect(screen.queryByText('처음 한 번은 약 10초 정도 걸릴 수 있습니다.')).toBeNull()
  resolveSecond({ transcript: '기침', duration_s: 1, language: 'ko' })
})
