import { TARGET_RATE, floatToInt16 } from './pcm.js'

// 마이크 → AudioWorklet(16 kHz) → packetMs 단위 Int16 패킷. 전체 PCM 은 메모리에만 모아 두었다가 stop() 이 돌려준다
// (streaming 실패 시 WAV 로 감싸 기존 /v1/stt/transcribe 로 보내는 fallback 용). 저장소·서버 외 어디에도 두지 않는다.
// audioEndMs = 캡처 시작 이후 누적 오디오 길이(ms). 서버 audio_ms 와 같은 기준이라 T_partial 계산에 쓴다.

function classify(err) {
  const name = err?.name
  if (name === 'NotAllowedError' || name === 'SecurityError') return 'permission'
  if (name === 'NotFoundError' || name === 'OverconstrainedError') return 'no_mic'
  return 'start_failed'
}

export async function startPcmCapture({
  onPacket,
  getUserMedia = typeof navigator !== 'undefined' ? navigator.mediaDevices?.getUserMedia?.bind(navigator.mediaDevices) : undefined,
  AudioContextImpl = typeof window !== 'undefined' ? (window.AudioContext ?? window.webkitAudioContext) : undefined,
  AudioWorkletNodeImpl = typeof window !== 'undefined' ? window.AudioWorkletNode : undefined,
  packetMs = 100,
  now = () => performance.now(),
  workletUrl = '/pcm-worklet.js',
} = {}) {
  if (!getUserMedia || !AudioContextImpl || !AudioWorkletNodeImpl) throw { type: 'unsupported' }
  // AudioContext 는 첫 await 전에(= 클릭 제스처 안에서) 만들고 resume 한다. iOS Safari 는 제스처 밖에서 만든 context 를 suspended 로 둘 수 있다.
  let ctx
  try {
    ctx = new AudioContextImpl()
    if (ctx.state === 'suspended' && ctx.resume) ctx.resume().catch(() => {})
  } catch {
    throw { type: 'unsupported' }
  }
  const closeCtx = () => { try { ctx?.close?.() } catch { /* 무시 */ } }
  let stream
  try {
    stream = await getUserMedia({ audio: true })
  } catch (err) {
    closeCtx()
    throw { type: classify(err) }
  }
  const stopTracks = () => stream?.getTracks?.().forEach((t) => t.stop())
  let node
  let source
  let sink
  try {
    if (!ctx.audioWorklet) throw { type: 'unsupported' }
    await ctx.audioWorklet.addModule(workletUrl)
    if (ctx.state === 'suspended' && ctx.resume) await ctx.resume()
    source = ctx.createMediaStreamSource(stream)
    node = new AudioWorkletNodeImpl(ctx, 'medmap-pcm')
    sink = ctx.createGain()
    sink.gain.value = 0                                                     // 일부 브라우저는 destination 연결이 있어야 처리한다(소리는 0)
    source.connect(node)
    node.connect(sink)
    sink.connect(ctx.destination)
  } catch (err) {
    stopTracks()
    closeCtx()
    throw err?.type ? err : { type: 'unsupported' }
  }

  const perPacket = Math.round((TARGET_RATE * packetMs) / 1000)
  const all = []
  let pending = []
  let pendingLen = 0
  let total = 0
  let stopped = false

  const flush = () => {
    if (!pendingLen) return
    const packet = new Int16Array(pendingLen)
    let offset = 0
    for (const c of pending) { packet.set(c, offset); offset += c.length }
    pending = []
    pendingLen = 0
    all.push(packet)
    total += packet.length
    onPacket?.({ pcm: packet.buffer, audioEndMs: Math.round((total / TARGET_RATE) * 1000), capturedAt: now() })
  }

  node.port.onmessage = (event) => {
    if (stopped) return
    const frame = floatToInt16(event.data)
    pending.push(frame)
    pendingLen += frame.length
    if (pendingLen >= perPacket) flush()
  }

  return {
    sampleRate: TARGET_RATE,
    stop() {
      if (stopped) return all
      flush()
      stopped = true
      node.port.onmessage = null
      try { source.disconnect(); node.disconnect(); sink.disconnect() } catch { /* 무시 */ }
      stopTracks()
      try { ctx.close?.() } catch { /* 무시 */ }
      return all
    },
  }
}
