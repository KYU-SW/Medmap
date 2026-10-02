// PCM 순수 함수(streaming STT). 브라우저 오디오를 서버 계약(16 kHz mono s16le)으로 바꾼다.
// public/pcm-worklet.js 는 같은 다운샘플 알고리즘을 복제해 쓴다(worklet 안에서는 이 모듈을 import 하지 않는다).
export const TARGET_RATE = 16000

// 상태를 가진 평균 decimation 다운샘플러: 블록(예: 128 샘플) 경계를 넘어 연속된다. inputRate === 16000 이면 복사.
export function createDownsampler(inputRate, outRate = TARGET_RATE) {
  const ratio = inputRate / outRate
  if (ratio < 1) throw new Error('upsampling not supported')
  let leftover = new Float32Array(0)
  let pos = 0
  return (input) => {
    const buf = new Float32Array(leftover.length + input.length)
    buf.set(leftover)
    buf.set(input, leftover.length)
    const out = []
    let start = pos
    while (start + ratio <= buf.length + 1e-9) {
      const s = Math.floor(start)
      const e = Math.max(s + 1, Math.floor(start + ratio))
      let sum = 0
      for (let k = s; k < e; k += 1) sum += buf[k]
      out.push(sum / (e - s))
      start += ratio
    }
    const keep = Math.floor(start)
    leftover = buf.slice(keep)
    pos = start - keep
    return Float32Array.from(out)
  }
}

export function downsampleTo16k(float32, inputRate) {
  return createDownsampler(inputRate)(float32)
}

export function floatToInt16(float32) {
  const out = new Int16Array(float32.length)
  for (let i = 0; i < float32.length; i += 1) {
    const v = Math.max(-1, Math.min(1, float32[i]))
    out[i] = v < 0 ? Math.round(v * 32768) : Math.round(v * 32767)
  }
  return out
}

// 16-bit mono PCM 청크들 → WAV Blob(audio/wav). 기존 /v1/stt/transcribe 의 allowlist 형식(legacy fallback).
export function encodeWav(chunks, sampleRate = TARGET_RATE) {
  const samples = chunks.reduce((n, c) => n + c.length, 0)
  const buffer = new ArrayBuffer(44 + samples * 2)
  const view = new DataView(buffer)
  const text = (offset, s) => { for (let i = 0; i < s.length; i += 1) view.setUint8(offset + i, s.charCodeAt(i)) }
  text(0, 'RIFF'); view.setUint32(4, 36 + samples * 2, true); text(8, 'WAVE')
  text(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true)
  view.setUint32(24, sampleRate, true); view.setUint32(28, sampleRate * 2, true); view.setUint16(32, 2, true)
  view.setUint16(34, 16, true); text(36, 'data'); view.setUint32(40, samples * 2, true)
  let offset = 44
  for (const chunk of chunks) {
    for (let i = 0; i < chunk.length; i += 1) { view.setInt16(offset, chunk[i], true); offset += 2 }
  }
  return new Blob([buffer], { type: 'audio/wav' })
}
