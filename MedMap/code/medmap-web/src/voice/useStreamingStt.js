import { useCallback, useEffect, useRef, useState } from 'react'
import { startPcmCapture } from './pcmCapture.js'
import { connectWithFallback } from './streamTransport.js'
import { TARGET_RATE, encodeWav } from './pcm.js'
import { transcribeAudio } from '../api/client.js'
import { perfMark } from './perf.js'

// Streaming STT hook(Real-time Clinical Loop). 계약: docs/superpowers/plans/2026-09-30-medmap-realtime-streaming-stt.ledger.md
// - PARTIAL 은 `partial` 상태(UI)에만. onFinal 은 FINAL 로만 호출된다. 이 hook 은 STT 경로 외 API 를 부르지 않는다.
// - 전송 실패·스트림 오류·stop 후 final 미도착 → 모아 둔 PCM 중 "마지막으로 전달된 FINAL 이후" 오디오만 WAV 로 legacy /transcribe.
// - 오디오·전사문은 메모리에만(저장소 쓰기 없음). 계측은 숫자만(perf.js).
const EMPTY = { stable: '', unstable: '' }
const MIN_LEGACY_MS = 300
// 기존 useRecorder 와 같은 60 s 상한: legacy WAV 가 /transcribe 2 MB 상한을 넘지 않게(16 kHz 16-bit ≈ 65 s)
export const MAX_RECORD_MS = 60000

const defaultRaf = (fn) => (typeof requestAnimationFrame === 'function' ? requestAnimationFrame(fn) : setTimeout(fn, 16))

function sliceAfter(chunks, afterMs) {
  const skip = Math.round((afterMs * TARGET_RATE) / 1000)
  const out = []
  let seen = 0
  for (const chunk of chunks) {
    const start = Math.max(0, skip - seen)
    if (start < chunk.length) out.push(start === 0 ? chunk : chunk.subarray(start))
    seen += chunk.length
  }
  return out
}

export function useStreamingStt({
  onFinal,
  capture = startPcmCapture,
  connect = connectWithFallback,
  transcribeLegacy = transcribeAudio,
  raf = defaultRaf,
  now = () => performance.now(),
  stopTimeoutMs = 5000,
} = {}) {
  const [state, setState] = useState('idle')          // idle | connecting | listening | finalizing
  const [partial, setPartial] = useState(EMPTY)
  const [transport, setTransport] = useState(null)    // ws | http | legacy
  const [sttState, setSttState] = useState(null)
  const [error, setError] = useState(null)

  const onFinalRef = useRef(onFinal)
  useEffect(() => { onFinalRef.current = onFinal }, [onFinal])

  const r = useRef(null)                               // 한 번의 녹음(세션) 상태 — start 마다 새로 만든다

  const fresh = () => ({
    capture: null, transport: null, failed: false, pendingPackets: [],
    delivered: new Set(), currentUtt: 1, lastFinalMs: 0, lastPartialMs: -1,
    queuedPartial: null, frameScheduled: false, capturedAt: new Map(), finalSinceStop: false, startedAt: now(),
    ignoreMessages: false, autoStopped: false,
  })

  const deliverFinal = useCallback((msg) => {
    const s = r.current
    if (!s || s.delivered.has(msg.utt)) return
    s.delivered.add(msg.utt)
    s.currentUtt = msg.utt + 1
    s.lastFinalMs = Math.max(s.lastFinalMs, msg.audio_ms ?? 0)
    s.lastPartialMs = -1
    s.queuedPartial = null
    s.finalSinceStop = true
    setPartial(EMPTY)
    const at = s.capturedAt.get(msg.audio_ms)
    perfMark('final_render', { audio_ms: msg.audio_ms, t_final_from_capture: at === undefined ? null : now() - at })
    if (msg.text) onFinalRef.current?.(msg.text)
  }, [now])

  const onMessage = useCallback((msg) => {
    const s = r.current
    if (!s || s.ignoreMessages) return                  // stop 타임아웃 뒤 늦게 온 메시지(legacy 가 대신함) — 중복 방지
    if (msg.type === 'partial') {
      if (s.delivered.has(msg.utt) || msg.utt < s.currentUtt || msg.audio_ms <= s.lastPartialMs) return   // stale
      const srv = msg.srv_ms ?? {}
      perfMark('partial_recv', {                        // 구간 계측(숫자만): 서버 체류·큐·decode·worker·IPC
        audio_ms: msg.audio_ms, srv_since_recv: srv.since_recv ?? null, srv_held: srv.held ?? null, srv_queue: srv.queue ?? null,
        srv_decode: srv.decode ?? null, srv_worker: srv.worker ?? null, srv_ipc: srv.ipc ?? null,
      })
      s.lastPartialMs = msg.audio_ms
      s.queuedPartial = msg
      if (!s.frameScheduled) {
        s.frameScheduled = true
        raf(() => {
          const cur = r.current
          if (!cur || cur !== s) return
          s.frameScheduled = false
          const q = s.queuedPartial
          s.queuedPartial = null
          if (!q || s.delivered.has(q.utt)) return
          setPartial({ stable: q.stable, unstable: q.unstable })
          const at = s.capturedAt.get(q.audio_ms)
          perfMark('partial_render', { audio_ms: q.audio_ms, t_partial: at === undefined ? null : now() - at })
        })
      }
    } else if (msg.type === 'final') {
      const srv = msg.srv_ms ?? {}
      perfMark('final_recv', { audio_ms: msg.audio_ms, srv_decode: srv.decode ?? null, srv_worker: srv.worker ?? null,
        srv_ipc: srv.ipc ?? null, srv_queue: srv.queue ?? null, reused: Boolean(srv.reused),
        srv_speech_start: srv.speech_start_ms ?? null, srv_speech_end: srv.speech_end_ms ?? null,   // VAD 경계(스트림 ms)
        srv_predecoded: Boolean(srv.predecoded), srv_spec_wait: srv.spec_wait ?? null, srv_spec_discarded: srv.spec_discarded ?? null })
      deliverFinal(msg)
    } else if (msg.type === 'error') {
      s.failed = true                                   // 이후 오디오는 legacy 로(stop 시)
      setTransport('legacy')
      perfMark('stream_failed', { code: /^[A-Z_]{1,32}$/.test(msg.code ?? '') ? msg.code.toLowerCase().slice(0, 24) : 'unknown' })
    }
  }, [deliverFinal, now, raf])

  const stopRef = useRef(null)

  const start = useCallback(async () => {
    if (r.current) return
    setError(null)
    setPartial(EMPTY)
    const s = fresh()
    r.current = s
    setState('connecting')
    try {
      s.capture = await capture({
        onPacket: (packet) => {
          s.capturedAt.set(packet.audioEndMs, packet.capturedAt)
          perfMark('packet', { audio_ms: packet.audioEndMs })            // e2e 가 오디오 시점별 T_partial 을 계산한다
          if (packet.audioEndMs >= MAX_RECORD_MS && !s.autoStopped) {
            s.autoStopped = true
            Promise.resolve().then(() => stopRef.current?.())            // 60 s 자동 종료(useRecorder 와 같음)
          }
          if (s.transport && !s.failed) s.transport.send(packet.pcm, packet.audioEndMs)
          else if (!s.transport && !s.failed) s.pendingPackets.push(packet)
        },
      })
    } catch (err) {
      r.current = null
      setState('idle')
      setError(err?.type ?? 'start_failed')
      return
    }
    try {
      const runId = typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : String(Math.random()).slice(2)
      const opened = await connect({ onMessage, runId })
      if (r.current !== s) {                            // 연결되는 사이 unmount/종료됨 → 서버 스트림을 바로 닫는다
        try { opened.close() } catch { /* 무시 */ }
        return
      }
      s.transport = opened
      setTransport(s.transport.kind)
      setSttState(s.transport.sttState ?? null)
      for (const p of s.pendingPackets) s.transport.send(p.pcm, p.audioEndMs)
      perfMark('stream_open', { transport: s.transport.kind, connect_ms: now() - s.startedAt })
    } catch {
      s.failed = true                                   // 녹음은 계속 → stop 시 legacy
      setTransport('legacy')
      perfMark('stream_open', { transport: 'legacy', connect_ms: now() - s.startedAt })
    }
    s.pendingPackets = []
    if (r.current === s) setState('listening')
  }, [capture, connect, onMessage, now])

  const stop = useCallback(async () => {
    const s = r.current
    if (!s || !s.capture || s.stopping) return          // 자동 종료(60 s)와 클릭이 겹쳐도 한 번만
    s.stopping = true
    setState('finalizing')
    const stoppedAt = now()
    perfMark('stop_click', {})
    const chunks = s.capture.stop()                     // 마지막 조각도 onPacket 으로 먼저 전송된다
    if (s.transport && !s.failed) {
      s.finalSinceStop = false
      let timer
      const timeout = new Promise((resolve) => { timer = setTimeout(resolve, stopTimeoutMs) })
      await Promise.race([s.transport.stop().catch(() => { s.failed = true }), timeout])
      clearTimeout(timer)
      if (!s.finalSinceStop) {
        s.failed = true
        s.ignoreMessages = true                         // 이제 legacy 가 남은 오디오를 맡는다 — 늦은 FINAL 은 버린다
      }
    }
    try { s.transport?.close() } catch { /* 무시 */ }
    if (s.failed) {
      const rest = sliceAfter(chunks, s.lastFinalMs)
      const samples = rest.reduce((n, c) => n + c.length, 0)
      if ((samples / TARGET_RATE) * 1000 >= MIN_LEGACY_MS) {
        try {
          const response = await transcribeLegacy(encodeWav(rest, TARGET_RATE))
          if (response?.transcript) onFinalRef.current?.(response.transcript)
          perfMark('final_render', { transport: 'legacy', t_final_from_stop: now() - stoppedAt })
        } catch (err) {
          setError(err?.code === 'AUDIO_EMPTY' ? 'AUDIO_EMPTY' : 'transcribe_failed')
        }
      }
    }
    if (r.current === s) {
      r.current = null
      setPartial(EMPTY)
      setState('idle')
    }
  }, [now, stopTimeoutMs, transcribeLegacy])
  useEffect(() => { stopRef.current = stop }, [stop])

  useEffect(() => () => {
    const s = r.current
    r.current = null
    if (s) {
      try { s.capture?.stop() } catch { /* 무시 */ }
      try { s.transport?.close() } catch { /* 무시 */ }
    }
  }, [])

  return { state, partial, transport, sttState, error, start, stop }
}
