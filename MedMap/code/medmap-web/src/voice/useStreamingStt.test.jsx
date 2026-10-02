import { act, renderHook } from '@testing-library/react'
import { useStreamingStt } from './useStreamingStt.js'

// 계약: docs/superpowers/plans/2026-09-30-medmap-realtime-streaming-stt.ledger.md (Task 7 C1–C7)

function fakeCapture() {
  const ctl = { packets: [], stopped: false }
  const capture = vi.fn(async ({ onPacket }) => {
    ctl.onPacket = onPacket
    return {
      sampleRate: 16000,
      stop: () => { ctl.stopped = true; return ctl.packets.map((p) => new Int16Array(p.pcm)) },
    }
  })
  ctl.push = (ms) => {
    const p = { pcm: new Int16Array(1600).fill(ms).buffer, audioEndMs: ms, capturedAt: ms }
    ctl.packets.push(p)
    ctl.onPacket(p)
  }
  return { capture, ctl }
}

function fakeConnect({ fail = false, finalOnStop = true } = {}) {
  const ctl = { sent: [], closed: false }
  const connect = vi.fn(async ({ onMessage }) => {
    ctl.onMessage = onMessage
    if (fail) throw { type: 'transport_failed' }
    return {
      kind: 'ws',
      sttState: 'WARM',
      send: (pcm, ms) => ctl.sent.push(ms),
      stop: async () => {
        if (finalOnStop) ctl.onMessage({ type: 'final', utt: ctl.nextUtt ?? 1, text: 'stop-final', audio_ms: 999, srv_ms: {} })
      },
      close: () => { ctl.closed = true },
    }
  })
  return { connect, ctl }
}

function setup(opts = {}) {
  const cap = fakeCapture()
  const con = fakeConnect(opts)
  const frames = []
  const raf = (fn) => { frames.push(fn); return frames.length }
  const flushFrames = () => act(() => { while (frames.length) frames.shift()() })
  const onFinal = vi.fn()
  const transcribeLegacy = vi.fn(async () => ({ transcript: 'legacy-text' }))
  const fetchSpy = vi.fn()
  vi.stubGlobal('fetch', fetchSpy)
  const hook = renderHook(() => useStreamingStt({
    onFinal, capture: cap.capture, connect: con.connect, transcribeLegacy, raf, now: () => 0, stopTimeoutMs: opts.stopTimeoutMs,
  }))
  return { ...cap, con: con.ctl, connect: con.connect, onFinal, transcribeLegacy, fetchSpy, hook, flushFrames }
}

const partial = (utt, stable, unstable, audio_ms) => ({ type: 'partial', utt, stable, unstable, audio_ms, srv_ms: {} })
const final = (utt, text, audio_ms = 1000) => ({ type: 'final', utt, text, audio_ms, srv_ms: {} })

test('C1 partial is UI-only: it updates partial state, never calls onFinal, and no non-STT API is called', async () => {
  const t = setup()
  await act(() => t.hook.result.current.start())
  expect(t.hook.result.current.state).toBe('listening')
  expect(t.hook.result.current.transport).toBe('ws')
  t.ctl.push(100)
  expect(t.con.sent).toEqual([100])
  act(() => t.con.onMessage(partial(1, '어제부터', ' 배가', 100)))
  t.flushFrames()
  expect(t.hook.result.current.partial).toEqual({ stable: '어제부터', unstable: ' 배가' })
  expect(t.onFinal).not.toHaveBeenCalled()
  act(() => t.con.onMessage(final(1, '어제부터 배가 아팠어요')))
  expect(t.onFinal).toHaveBeenCalledWith('어제부터 배가 아팠어요')
  expect(t.fetchSpy).not.toHaveBeenCalled()
})

test('C2 stale partials are dropped: older audio_ms, and partials of an already-finalized utterance', async () => {
  const t = setup()
  await act(() => t.hook.result.current.start())
  act(() => t.con.onMessage(partial(1, 'a b', '', 500)))
  act(() => t.con.onMessage(partial(1, 'a', ' x', 300)))        // 늦게 도착한 옛 partial
  t.flushFrames()
  expect(t.hook.result.current.partial).toEqual({ stable: 'a b', unstable: '' })
  act(() => t.con.onMessage(final(1, 'a b c')))
  act(() => t.con.onMessage(partial(1, 'a b c', ' zz', 900)))   // 이미 끝난 발화의 partial
  t.flushFrames()
  expect(t.hook.result.current.partial).toEqual({ stable: '', unstable: '' })
})

test('C2 partials are merged per animation frame (one render per frame)', async () => {
  const t = setup()
  await act(() => t.hook.result.current.start())
  const before = t.hook.result.current
  act(() => {
    t.con.onMessage(partial(1, '', 'a', 100))
    t.con.onMessage(partial(1, '', 'a b', 200))
    t.con.onMessage(partial(1, '', 'a b c', 300))
  })
  expect(t.hook.result.current.partial).toEqual(before.partial)  // 프레임 전에는 반영 안 됨
  t.flushFrames()
  expect(t.hook.result.current.partial).toEqual({ stable: '', unstable: 'a b c' })
})

test('C3 final is delivered once per utterance and resets partial; next utterance starts clean', async () => {
  const t = setup()
  await act(() => t.hook.result.current.start())
  act(() => t.con.onMessage(partial(1, '', '첫', 100)))
  t.flushFrames()
  act(() => { t.con.onMessage(final(1, '첫 문장')); t.con.onMessage(final(1, '첫 문장')) })
  expect(t.onFinal).toHaveBeenCalledTimes(1)
  expect(t.hook.result.current.partial).toEqual({ stable: '', unstable: '' })
  act(() => t.con.onMessage(partial(2, '', '둘', 1200)))
  t.flushFrames()
  expect(t.hook.result.current.partial).toEqual({ stable: '', unstable: '둘' })
  act(() => t.con.onMessage(final(2, '둘째 문장', 2000)))
  expect(t.onFinal.mock.calls.map((c) => c[0])).toEqual(['첫 문장', '둘째 문장'])
})

test('C4 connect failure → legacy: keeps recording, stop sends one WAV to /transcribe and delivers its text', async () => {
  const t = setup({ fail: true })
  await act(() => t.hook.result.current.start())
  expect(t.hook.result.current.transport).toBe('legacy')
  expect(t.hook.result.current.state).toBe('listening')
  t.ctl.push(100); t.ctl.push(200); t.ctl.push(300); t.ctl.push(400)
  await act(() => t.hook.result.current.stop())
  expect(t.transcribeLegacy).toHaveBeenCalledTimes(1)
  const blob = t.transcribeLegacy.mock.calls[0][0]
  expect(blob.type).toBe('audio/wav')
  expect(blob.size).toBe(44 + 4 * 3200)
  expect(t.onFinal).toHaveBeenCalledWith('legacy-text')
  expect(t.hook.result.current.state).toBe('idle')
  expect(t.ctl.stopped).toBe(true)
})

test('C3/C4 mid-stream failure sends only audio after the last delivered final (no duplicated text)', async () => {
  const t = setup()
  await act(() => t.hook.result.current.start())
  t.ctl.push(100); t.ctl.push(200)
  act(() => t.con.onMessage(final(1, '앞 문장', 200)))
  t.ctl.push(300); t.ctl.push(400); t.ctl.push(500)
  act(() => t.con.onMessage({ type: 'error', code: 'STREAM_OVERLOADED' }))
  expect(t.hook.result.current.transport).toBe('legacy')
  t.ctl.push(600)
  await act(() => t.hook.result.current.stop())
  expect(t.transcribeLegacy).toHaveBeenCalledTimes(1)
  expect(t.transcribeLegacy.mock.calls[0][0].size).toBe(44 + 4 * 3200)   // 300~600 ms 네 패킷만
  expect(t.onFinal.mock.calls.map((c) => c[0])).toEqual(['앞 문장', 'legacy-text'])
  expect(t.con.closed).toBe(true)
})

test('C4 stop timeout (final never arrives) → legacy for the remaining audio', async () => {
  const t = setup({ finalOnStop: false, stopTimeoutMs: 10 })
  await act(() => t.hook.result.current.start())
  t.ctl.push(100); t.ctl.push(200); t.ctl.push(300); t.ctl.push(400)
  await act(() => t.hook.result.current.stop())
  expect(t.transcribeLegacy).toHaveBeenCalledTimes(1)
  expect(t.onFinal).toHaveBeenCalledWith('legacy-text')
})

test('C4 normal stop over the stream uses the streamed final, not legacy', async () => {
  const t = setup()
  await act(() => t.hook.result.current.start())
  t.ctl.push(100)
  await act(() => t.hook.result.current.stop())
  expect(t.onFinal).toHaveBeenCalledWith('stop-final')
  expect(t.transcribeLegacy).not.toHaveBeenCalled()
  expect(t.con.closed).toBe(true)
})

test('C4 legacy skips when the remaining audio is shorter than 0.3 s', async () => {
  const t = setup({ fail: true })
  await act(() => t.hook.result.current.start())
  t.ctl.push(100)
  await act(() => t.hook.result.current.stop())
  expect(t.transcribeLegacy).not.toHaveBeenCalled()
})

test('C7 capture failure surfaces the error and does not connect', async () => {
  const t = setup()
  t.capture.mockImplementationOnce(async () => { throw { type: 'permission' } })
  await act(() => t.hook.result.current.start())
  expect(t.hook.result.current.error).toBe('permission')
  expect(t.hook.result.current.state).toBe('idle')
  expect(t.connect).not.toHaveBeenCalled()
})

// ---- M1 리뷰 수정 회귀(I1·I2·M4) ----
test('I1 a final that arrives after the stop timeout is ignored (legacy delivers once, no duplicate text)', async () => {
  const cap = fakeCapture()
  let onMessage
  let releaseStop
  const connect = vi.fn(async (o) => {
    onMessage = o.onMessage
    return { kind: 'http', sttState: 'LOADING', send: () => {}, stop: () => new Promise((r) => { releaseStop = r }), close: () => {} }
  })
  const onFinal = vi.fn()
  let releaseLegacy
  // legacy 요청이 아직 진행 중일 때(서버 inference lock 뒤에 줄 서 있음) 늦은 stream FINAL 이 도착하는 경로
  const transcribeLegacy = vi.fn(() => new Promise((r) => { releaseLegacy = () => r({ transcript: '같은 문장' }) }))
  const hook = renderHook(() => useStreamingStt({ onFinal, capture: cap.capture, connect, transcribeLegacy, raf: (fn) => fn(), stopTimeoutMs: 10 }))
  await act(() => hook.result.current.start())
  cap.ctl.push(100); cap.ctl.push(200); cap.ctl.push(300); cap.ctl.push(400)
  let stopping
  act(() => { stopping = hook.result.current.stop() })
  await vi.waitFor(() => expect(transcribeLegacy).toHaveBeenCalled())
  act(() => { onMessage({ type: 'final', utt: 1, text: '같은 문장', audio_ms: 400, srv_ms: {} }); releaseStop() })
  await act(async () => { releaseLegacy(); await stopping })
  expect(onFinal.mock.calls.map((c) => c[0])).toEqual(['같은 문장'])
})

test('I2 recording stops automatically at 60 s like useRecorder', async () => {
  const t = setup()
  await act(() => t.hook.result.current.start())
  await act(async () => { t.ctl.push(60000) })
  await vi.waitFor(() => expect(t.hook.result.current.state).toBe('idle'))
  expect(t.ctl.stopped).toBe(true)
  expect(t.onFinal).toHaveBeenCalledWith('stop-final')
})

test('M4 unmount while connecting closes the late transport (no leaked server stream)', async () => {
  const cap = fakeCapture()
  let resolveConnect
  const closed = vi.fn()
  const connect = vi.fn(() => new Promise((r) => { resolveConnect = r }))
  const hook = renderHook(() => useStreamingStt({ onFinal: () => {}, capture: cap.capture, connect, raf: (fn) => fn() }))
  let starting
  act(() => { starting = hook.result.current.start() })
  await vi.waitFor(() => expect(connect).toHaveBeenCalled())
  hook.unmount()
  await act(async () => { resolveConnect({ kind: 'ws', send: () => {}, stop: async () => {}, close: closed }); await starting })
  expect(closed).toHaveBeenCalledTimes(1)
})

test('stop() runs once even if auto-stop and a click coincide', async () => {
  const cap = fakeCapture()
  const transportStop = vi.fn(async () => {})
  const connect = vi.fn(async ({ onMessage }) => ({
    kind: 'ws', send: () => {}, close: () => {},
    stop: () => transportStop().then(() => onMessage({ type: 'final', utt: 1, text: 'x', audio_ms: 100, srv_ms: {} })),
  }))
  const hook = renderHook(() => useStreamingStt({ onFinal: () => {}, capture: cap.capture, connect, raf: (fn) => fn() }))
  await act(() => hook.result.current.start())
  cap.ctl.push(100)
  await act(async () => { await Promise.all([hook.result.current.stop(), hook.result.current.stop()]) })
  expect(transportStop).toHaveBeenCalledTimes(1)
})
