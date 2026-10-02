// AudioWorkletProcessor 'medmap-pcm': 마이크 입력(보통 44.1/48 kHz) → 16 kHz mono float32, 20 ms(320 샘플) 프레임을 port 로 보낸다.
// 다운샘플 알고리즘은 src/voice/pcm.js createDownsampler 와 같다(worklet 전역 범위에서는 앱 모듈을 import 하지 않는다).
// 오디오는 메인 스레드로만 보내고 어디에도 저장하지 않는다.
const TARGET = 16000
const FRAME = 320

class MedmapPcmProcessor extends AudioWorkletProcessor {
  constructor() {
    super()
    this.ratio = sampleRate / TARGET        // sampleRate: AudioWorkletGlobalScope 전역
    this.leftover = new Float32Array(0)
    this.pos = 0
    this.frame = new Float32Array(FRAME)
    this.filled = 0
  }

  downsample(input) {
    const buf = new Float32Array(this.leftover.length + input.length)
    buf.set(this.leftover)
    buf.set(input, this.leftover.length)
    const out = []
    let start = this.pos
    while (start + this.ratio <= buf.length + 1e-9) {
      const s = Math.floor(start)
      const e = Math.max(s + 1, Math.floor(start + this.ratio))
      let sum = 0
      for (let k = s; k < e; k += 1) sum += buf[k]
      out.push(sum / (e - s))
      start += this.ratio
    }
    const keep = Math.floor(start)
    this.leftover = buf.slice(keep)
    this.pos = start - keep
    return out
  }

  process(inputs) {
    const channel = inputs[0] && inputs[0][0]
    if (!channel) return true
    for (const v of this.downsample(channel)) {
      this.frame[this.filled] = v
      this.filled += 1
      if (this.filled === FRAME) {
        this.port.postMessage(this.frame)
        this.frame = new Float32Array(FRAME)
        this.filled = 0
      }
    }
    return true
  }
}

registerProcessor('medmap-pcm', MedmapPcmProcessor)
