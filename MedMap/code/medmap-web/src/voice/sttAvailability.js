import { getSttStatus, prewarmStt } from '../api/client.js'

// 서버 streaming 플래그 + 브라우저 AudioWorklet 지원을 페이지당 한 번만 확인한다.
// streaming 가능할 때만 Whisper prewarm(멱등)을 건다 — 플래그 OFF 면 기존 경로와 같은 호출만 남는다(status GET 1회 제외).
let cached = null

export function loadSttStreaming({
  getStatus = getSttStatus,
  prewarm = prewarmStt,
  hasWorklet = typeof window !== 'undefined' && typeof window.AudioWorkletNode === 'function',
} = {}) {
  if (!cached) {
    cached = Promise.resolve()
      .then(() => getStatus())
      .then((status) => {
        const streaming = Boolean(status?.streaming) && hasWorklet
        if (streaming) Promise.resolve().then(() => prewarm()).catch(() => {})
        return { streaming, sttState: status?.stt_state ?? null }
      })
      .catch(() => ({ streaming: false, sttState: null }))
  }
  return cached
}

export function __resetSttAvailabilityForTests() {
  cached = null
}
