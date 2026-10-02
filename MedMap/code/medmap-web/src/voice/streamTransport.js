// Streaming STT 전송: WebSocket 우선, 실패하면 HTTP chunk POST. 둘 다 실패하면 reject → 호출자가 legacy(/v1/stt/transcribe)로.
// iPhone Safari 는 자체 서명 인증서에서 wss 가 실패한다는 보고가 있어(spec §6) HTTP 경로가 필수다.
// 메시지(partial/final/utterance_end/error)는 onMessage 로 도착 순서대로 전달한다. 오디오는 보내기만 하고 보관하지 않는다.
const START = { sample_rate: 16000, format: 's16le' }
const SID_HEADER = 'x-stt-stream'

function wsUrl(loc) {
  return `${loc.protocol === 'https:' ? 'wss' : 'ws'}://${loc.host}/v1/stt/stream`
}

export function openWsTransport({ onMessage, runId, WebSocketImpl, location, timeoutMs = 2000, setTimer = setTimeout, clearTimer = clearTimeout }) {
  return new Promise((resolve, reject) => {
    let ws
    try {
      ws = new WebSocketImpl(wsUrl(location))
    } catch {
      reject({ type: 'transport_failed', stage: 'ws' })
      return
    }
    ws.binaryType = 'arraybuffer'
    let ready = false
    let stopWaiter = null
    let manualUtt = null                             // stop 이후 서버가 알린 manual 종료 발화 번호
    const fail = (code) => {
      if (!ready) {
        clearTimer(timer)
        reject({ type: 'transport_failed', stage: 'ws', code })
        try { ws.close() } catch { /* 무시 */ }
      }
    }
    const timer = setTimer(() => fail('READY_TIMEOUT'), timeoutMs)
    ws.onopen = () => ws.send(JSON.stringify({ type: 'start', ...START, run_id: runId }))
    ws.onerror = () => fail('WS_ERROR')
    ws.onclose = () => {
      if (!ready) { fail('WS_CLOSED'); return }
      onMessage({ type: 'error', code: 'TRANSPORT_CLOSED' })
      stopWaiter?.()
    }
    ws.onmessage = (event) => {
      let msg
      try { msg = JSON.parse(event.data) } catch { return }
      if (!ready) {
        if (msg.type === 'ready') {
          ready = true
          clearTimer(timer)
          resolve({
            kind: 'ws',
            sttState: msg.stt_state,
            send(pcm) { if (ws.readyState === 1) ws.send(pcm) },
            stop() {
              return new Promise((done) => {
                stopWaiter = done
                manualUtt = null
                if (ws.readyState === 1) ws.send(JSON.stringify({ type: 'stop' }))
                else done()
              })
            },
            close() {
              ws.onclose = null
              try { if (ws.readyState === 1) ws.send(JSON.stringify({ type: 'close' })); ws.close() } catch { /* 무시 */ }
            },
          })
        } else {
          fail(msg.code ?? 'NOT_READY')
        }
        return
      }
      onMessage(msg)
      // stop 은 "그 stop 으로 닫힌 발화"의 final 에서만 끝난다(직전 자동 종료 발화의 final 로 끝나면 꼬리 오디오를 잃는다)
      if (msg.type === 'utterance_end' && msg.reason === 'manual' && stopWaiter) manualUtt = msg.utt
      const stopDone = msg.type === 'error' || (msg.type === 'final' && manualUtt !== null && msg.utt === manualUtt)
      if (stopDone && stopWaiter) { stopWaiter(); stopWaiter = null; manualUtt = null }
    }
  })
}

export async function openHttpTransport({ onMessage, runId, fetchImpl, batchMs = 100 }) {
  const post = async (path, { body, sid, json } = {}) => {
    const headers = json ? { 'content-type': 'application/json' } : { 'content-type': 'application/octet-stream' }
    if (sid) headers[SID_HEADER] = sid
    const response = await fetchImpl(path, { method: 'POST', headers, body })
    const payload = await response.json().catch(() => null)
    if (!response.ok) throw { type: 'transport_failed', stage: 'http', code: payload?.error?.code ?? 'HTTP_ERROR' }
    return payload
  }
  let opened
  try {
    opened = await post('/v1/stt/stream', { json: true, body: JSON.stringify({ ...START, run_id: runId }) })
  } catch (err) {
    throw err?.type ? err : { type: 'transport_failed', stage: 'http', code: 'NETWORK_ERROR' }
  }
  const sid = opened.sid
  let chain = Promise.resolve()
  let pending = []
  let batchStartMs = null
  let failed = false

  const deliver = (payload) => { for (const msg of payload?.messages ?? []) onMessage(msg) }
  const enqueue = (task) => {
    chain = chain.then(task).catch(() => {
      if (!failed) { failed = true; onMessage({ type: 'error', code: 'TRANSPORT_FAILED' }) }
    })
    return chain
  }
  const flush = () => {
    if (!pending.length) return chain
    const size = pending.reduce((n, b) => n + b.byteLength, 0)
    const body = new Uint8Array(size)
    let offset = 0
    for (const b of pending) { body.set(new Uint8Array(b), offset); offset += b.byteLength }
    pending = []
    batchStartMs = null
    return enqueue(async () => deliver(await post('/v1/stt/stream/audio', { sid, body })))
  }

  return {
    kind: 'http',
    sttState: opened.stt_state,
    send(pcm, audioEndMs) {
      if (failed) return
      pending.push(pcm)
      const startMs = batchStartMs ?? audioEndMs - 100
      batchStartMs = startMs
      if (audioEndMs - startMs >= batchMs) flush()
    },
    async stop() {
      flush()
      await enqueue(async () => deliver(await post('/v1/stt/stream/stop', { sid })))
    },
    close() {
      enqueue(async () => { await post('/v1/stt/stream/close', { sid }) })
    },
  }
}

// WS → HTTP. 둘 다 실패하면 { type: 'transport_failed' } 로 reject(호출자가 legacy 로 강등).
export async function connectWithFallback({
  onMessage,
  runId,
  WebSocketImpl = typeof window !== 'undefined' ? window.WebSocket : undefined,
  fetchImpl = typeof fetch !== 'undefined' ? fetch.bind(globalThis) : undefined,
  location = typeof window !== 'undefined' ? window.location : undefined,
  wsTimeoutMs = 2000,
  setTimer,
  clearTimer,
} = {}) {
  if (WebSocketImpl) {
    try {
      return await openWsTransport({ onMessage, runId, WebSocketImpl, location, timeoutMs: wsTimeoutMs, setTimer, clearTimer })
    } catch { /* HTTP 로 */ }
  }
  if (!fetchImpl) throw { type: 'transport_failed', stage: 'http', code: 'NO_FETCH' }
  return openHttpTransport({ onMessage, runId, fetchImpl })
}
