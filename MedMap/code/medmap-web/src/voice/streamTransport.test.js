import { connectWithFallback, openHttpTransport } from './streamTransport.js'

const LOC = { protocol: 'https:', host: 'demo:8443' }

// 가짜 WebSocket: behavior = 'ready' | 'error' | 'silent' | 'refuse'
function makeWs(behavior, log) {
  return class FakeWs {
    constructor(url) {
      log.url = url
      this.readyState = 0
      this.sent = []
      log.ws = this
      queueMicrotask(() => {
        if (behavior === 'error') { this.onerror?.(); return }
        this.readyState = 1
        this.onopen?.()
      })
    }
    send(data) {
      this.sent.push(data)
      if (typeof data === 'string') {
        const msg = JSON.parse(data)
        if (msg.type === 'start') {
          if (behavior === 'ready') queueMicrotask(() => this.onmessage?.({ data: JSON.stringify({ type: 'ready', stt_state: 'WARM', vad: 'manual' }) }))
          if (behavior === 'refuse') queueMicrotask(() => this.onmessage?.({ data: JSON.stringify({ type: 'error', code: 'STREAM_BUSY' }) }))
        }
        if (msg.type === 'stop') {
          queueMicrotask(() => {
            this.onmessage?.({ data: JSON.stringify({ type: 'utterance_end', utt: 1, reason: 'manual' }) })
            this.onmessage?.({ data: JSON.stringify({ type: 'final', utt: 1, text: '끝', audio_ms: 300, srv_ms: {} }) })
          })
        }
      }
    }
    close() { this.readyState = 3 }
  }
}

function makeFetch(log, { failOpen = false } = {}) {
  log.posts = []
  return vi.fn(async (path, init) => {
    log.posts.push({ path, headers: init.headers, size: init.body?.byteLength ?? (init.body ? init.body.length : 0) })
    if (failOpen) return { ok: false, json: async () => ({ error: { code: 'STREAMING_DISABLED' } }) }
    const body = path === '/v1/stt/stream' ? { sid: 'S1', stt_state: 'WARM' }
      : path.endsWith('/stop') ? { messages: [{ type: 'final', utt: 1, text: 'http', audio_ms: 400, srv_ms: {} }] }
        : path.endsWith('/audio') ? { messages: [{ type: 'partial', utt: 1, stable: '', unstable: 'h', audio_ms: 300, srv_ms: {} }] }
          : { closed: true }
    return { ok: true, json: async () => body }
  })
}

const pcm = () => new Int16Array(1600).buffer

test('WebSocket path: start message, binary audio, stop resolves after final, messages in order', async () => {
  const log = {}
  const messages = []
  const t = await connectWithFallback({ onMessage: (m) => messages.push(m), runId: 'r', WebSocketImpl: makeWs('ready', log), fetchImpl: makeFetch(log), location: LOC })
  expect(t.kind).toBe('ws')
  expect(log.url).toBe('wss://demo:8443/v1/stt/stream')
  expect(JSON.parse(log.ws.sent[0])).toEqual({ type: 'start', sample_rate: 16000, format: 's16le', run_id: 'r' })
  t.send(pcm(), 100)
  expect(log.ws.sent[1]).toBeInstanceOf(ArrayBuffer)
  await t.stop()
  expect(messages.map((m) => m.type)).toEqual(['utterance_end', 'final'])
  expect(log.posts).toEqual([])
})

test('WS error → HTTP chunk path: batches ~100 ms, id in header (not URL), stop delivers final', async () => {
  const log = {}
  const messages = []
  const t = await connectWithFallback({ onMessage: (m) => messages.push(m), runId: 'r', WebSocketImpl: makeWs('error', log), fetchImpl: makeFetch(log), location: LOC })
  expect(t.kind).toBe('http')
  t.send(pcm(), 100)                                   // 100 ms 패킷마다 바로 전송
  t.send(pcm(), 200)
  await t.stop()
  const audio = log.posts.filter((p) => p.path === '/v1/stt/stream/audio')
  expect(audio).toHaveLength(2)
  expect(audio.map((p) => p.size)).toEqual([3200, 3200])
  expect(audio.every((p) => p.headers['x-stt-stream'] === 'S1')).toBe(true)
  expect(log.posts.every((p) => !p.path.includes('S1'))).toBe(true)
  expect(messages.map((m) => m.type)).toEqual(['partial', 'partial', 'final'])
})

test('HTTP chunk path: a custom batchMs still groups packets (300 ms → one POST)', async () => {
  const log = {}
  const t = await openHttpTransport({ onMessage: () => {}, runId: 'r', fetchImpl: makeFetch(log), batchMs: 300 })
  t.send(pcm(), 100)
  t.send(pcm(), 200)
  expect(log.posts.filter((p) => p.path.endsWith('/audio'))).toHaveLength(0)
  t.send(pcm(), 300)
  await t.stop()
  const audio = log.posts.filter((p) => p.path === '/v1/stt/stream/audio')
  expect(audio).toHaveLength(1)
  expect(audio[0].size).toBe(3 * 3200)
})

test('WS silent: timer fires → falls back to HTTP', async () => {
  const log = {}
  let fire
  const pending = connectWithFallback({
    onMessage: () => {}, runId: 'r', WebSocketImpl: makeWs('silent', log), fetchImpl: makeFetch(log), location: LOC,
    setTimer: (fn) => { fire = fn; return 1 }, clearTimer: () => {},
  })
  await new Promise((r) => setTimeout(r, 0))
  fire()
  expect((await pending).kind).toBe('http')
})

test('server refusal on WS (e.g. busy) still tries HTTP; both failing rejects for legacy fallback', async () => {
  const log = {}
  await expect(connectWithFallback({ onMessage: () => {}, runId: 'r', WebSocketImpl: makeWs('refuse', log), fetchImpl: makeFetch(log, { failOpen: true }), location: LOC }))
    .rejects.toMatchObject({ type: 'transport_failed', stage: 'http', code: 'STREAMING_DISABLED' })
  expect(log.posts.map((p) => p.path)).toEqual(['/v1/stt/stream'])
})

test('WS closing mid-stream surfaces a TRANSPORT_CLOSED error and releases a pending stop', async () => {
  const log = {}
  const messages = []
  const t = await connectWithFallback({ onMessage: (m) => messages.push(m), runId: 'r', WebSocketImpl: makeWs('ready', log), fetchImpl: makeFetch(log), location: LOC })
  log.ws.send = () => {}                              // 서버가 응답하지 않는 상태
  const stopped = t.stop()
  log.ws.onclose()
  await stopped
  expect(messages).toEqual([{ type: 'error', code: 'TRANSPORT_CLOSED' }])
})

test('M3 WS stop resolves only on the final of the utterance closed by that stop (not an earlier auto-final)', async () => {
  const log = {}
  const messages = []
  const t = await connectWithFallback({ onMessage: (m) => messages.push(m), runId: 'r', WebSocketImpl: makeWs('ready', log), fetchImpl: makeFetch(log), location: LOC })
  log.ws.send = () => {}                                  // 서버 응답은 아래에서 직접 흘린다
  let done = false
  const stopped = t.stop().then(() => { done = true })
  const emit = (m) => log.ws.onmessage({ data: JSON.stringify(m) })
  emit({ type: 'utterance_end', utt: 1, reason: 'max_duration' })
  emit({ type: 'final', utt: 1, text: '앞', audio_ms: 30000, srv_ms: {} })
  await new Promise((r) => setTimeout(r, 0))
  expect(done).toBe(false)
  emit({ type: 'utterance_end', utt: 2, reason: 'manual' })
  emit({ type: 'final', utt: 2, text: '꼬리', audio_ms: 30800, srv_ms: {} })
  await stopped
  expect(messages.filter((m) => m.type === 'final').map((m) => m.text)).toEqual(['앞', '꼬리'])
})
