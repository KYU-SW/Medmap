import { act, renderHook, waitFor } from '@testing-library/react'
import { useRecorder } from './useRecorder'

class FakeMediaRecorder {
  constructor(stream, options) {
    FakeMediaRecorder.lastInstance = this
    FakeMediaRecorder.lastOptions = options
    this.stream = stream
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
  return { getTracks: () => tracks, __tracks: tracks }
}

beforeEach(() => {
  FakeMediaRecorder.nextBlob = undefined
  FakeMediaRecorder.lastOptions = undefined
})

afterEach(() => {
  vi.useRealTimers()
})

test('허가되면 recording 상태로 전환된다', async () => {
  const stream = fakeStream()
  const getUserMedia = vi.fn(async () => stream)
  const { result } = renderHook(() => useRecorder({ getUserMedia, MediaRecorderImpl: FakeMediaRecorder }))
  expect(result.current.state).toBe('idle')
  await act(async () => { await result.current.start() })
  expect(result.current.state).toBe('recording')
  expect(result.current.error).toBeNull()
  expect(getUserMedia).toHaveBeenCalledWith({ audio: true })
  expect(FakeMediaRecorder.lastOptions).toMatchObject({ mimeType: 'audio/webm;codecs=opus', audioBitsPerSecond: 32000 })
})

test('권한 거부는 permission 오류로 분류된다', async () => {
  const getUserMedia = vi.fn(async () => { throw Object.assign(new Error('denied'), { name: 'NotAllowedError' }) })
  const { result } = renderHook(() => useRecorder({ getUserMedia, MediaRecorderImpl: FakeMediaRecorder }))
  await act(async () => { await result.current.start() })
  expect(result.current.state).toBe('idle')
  expect(result.current.error).toBe('permission')
})

test('마이크 없음은 no_mic 오류로 분류된다', async () => {
  const getUserMedia = vi.fn(async () => { throw Object.assign(new Error('none'), { name: 'NotFoundError' }) })
  const { result } = renderHook(() => useRecorder({ getUserMedia, MediaRecorderImpl: FakeMediaRecorder }))
  await act(async () => { await result.current.start() })
  expect(result.current.error).toBe('no_mic')
})

test('getUserMedia·MediaRecorder 가 없으면 unsupported 오류다', async () => {
  const { result } = renderHook(() => useRecorder({ getUserMedia: undefined, MediaRecorderImpl: undefined }))
  await act(async () => { await result.current.start() })
  expect(result.current.error).toBe('unsupported')
})

test('녹음 시작 실패(생성자 예외)는 start_failed 오류다', async () => {
  class ThrowingRecorder {
    constructor() { throw new Error('boom') }
  }
  ThrowingRecorder.isTypeSupported = () => true
  const stream = fakeStream()
  const getUserMedia = vi.fn(async () => stream)
  const { result } = renderHook(() => useRecorder({ getUserMedia, MediaRecorderImpl: ThrowingRecorder }))
  await act(async () => { await result.current.start() })
  expect(result.current.error).toBe('start_failed')
  expect(stream.__tracks[0].stop).toHaveBeenCalled()
})

test('start/stop: stop 을 호출하면 트랙이 멈추고 idle 로 돌아간다', async () => {
  const stream = fakeStream()
  const getUserMedia = vi.fn(async () => stream)
  const onRecorded = vi.fn(async () => {})
  const { result } = renderHook(() => useRecorder({ getUserMedia, MediaRecorderImpl: FakeMediaRecorder, onRecorded }))
  await act(async () => { await result.current.start() })
  expect(result.current.state).toBe('recording')
  await act(async () => { result.current.stop() })
  await waitFor(() => expect(result.current.state).toBe('idle'))
  expect(stream.__tracks[0].stop).toHaveBeenCalled()
  expect(onRecorded).toHaveBeenCalledTimes(1)
  expect(onRecorded.mock.calls[0][0]).toBeInstanceOf(Blob)
})

test('타이머는 1초 단위로 증가한다', async () => {
  vi.useFakeTimers()
  const stream = fakeStream()
  const getUserMedia = vi.fn(async () => stream)
  const { result } = renderHook(() => useRecorder({ getUserMedia, MediaRecorderImpl: FakeMediaRecorder }))
  await act(async () => { await result.current.start() })
  expect(result.current.elapsed).toBe(0)
  await act(async () => { await vi.advanceTimersByTimeAsync(3000) })
  expect(result.current.elapsed).toBe(3)
})

test('60초에 도달하면 자동으로 stop 된다', async () => {
  vi.useFakeTimers()
  const stream = fakeStream()
  const getUserMedia = vi.fn(async () => stream)
  const onRecorded = vi.fn(async () => {})
  const { result } = renderHook(() => useRecorder({ getUserMedia, MediaRecorderImpl: FakeMediaRecorder, onRecorded, maxSeconds: 60 }))
  await act(async () => { await result.current.start() })
  await act(async () => { await vi.advanceTimersByTimeAsync(60000) })
  expect(result.current.state).toBe('idle')
  expect(stream.__tracks[0].stop).toHaveBeenCalled()
  expect(onRecorded).toHaveBeenCalledTimes(1)
})

test('stop 후 onRecorded 가 처리되는 동안 transcribing 상태를 거친다', async () => {
  const stream = fakeStream()
  const getUserMedia = vi.fn(async () => stream)
  let release
  const onRecorded = vi.fn(() => new Promise((resolve) => { release = resolve }))
  const { result } = renderHook(() => useRecorder({ getUserMedia, MediaRecorderImpl: FakeMediaRecorder, onRecorded }))
  await act(async () => { await result.current.start() })
  act(() => { result.current.stop() })
  await waitFor(() => expect(result.current.state).toBe('transcribing'))
  await act(async () => { release() })
  await waitFor(() => expect(result.current.state).toBe('idle'))
  expect(result.current.error).toBeNull()
})

test('onRecorded 가 실패하면 오류를 표시하고 idle 로 돌아간다(입력 텍스트 보존은 상위 컴포넌트 책임)', async () => {
  const stream = fakeStream()
  const getUserMedia = vi.fn(async () => stream)
  const onRecorded = vi.fn(async () => { throw Object.assign(new Error('server down'), { type: 'transcribe_failed' }) })
  const { result } = renderHook(() => useRecorder({ getUserMedia, MediaRecorderImpl: FakeMediaRecorder, onRecorded }))
  await act(async () => { await result.current.start() })
  await act(async () => { result.current.stop() })
  await waitFor(() => expect(result.current.state).toBe('idle'))
  expect(result.current.error).toBe('transcribe_failed')
  expect(onRecorded).toHaveBeenCalledTimes(1)
})

test('빈 blob(size 0)은 onRecorded 를 호출하지 않고 empty 오류를 낸다', async () => {
  FakeMediaRecorder.nextBlob = new Blob([], { type: 'audio/webm' })
  const stream = fakeStream()
  const getUserMedia = vi.fn(async () => stream)
  const onRecorded = vi.fn(async () => {})
  const { result } = renderHook(() => useRecorder({ getUserMedia, MediaRecorderImpl: FakeMediaRecorder, onRecorded }))
  await act(async () => { await result.current.start() })
  await act(async () => { result.current.stop() })
  await waitFor(() => expect(result.current.error).toBe('empty'))
  expect(result.current.state).toBe('idle')
  expect(onRecorded).not.toHaveBeenCalled()
})
