import { startPcmCapture } from './pcmCapture.js'

function fakes({ rejectWith, noWorklet = false } = {}) {
  const log = { tracksStopped: 0, closed: 0, modules: [], connected: [] }
  const track = { stop: () => { log.tracksStopped += 1 } }
  const stream = { getTracks: () => [track] }
  const getUserMedia = vi.fn(async () => { if (rejectWith) throw rejectWith; return stream })
  let port
  class AudioContextImpl {
    constructor() {
      this.state = 'running'
      this.destination = { name: 'dest' }
      this.audioWorklet = noWorklet ? undefined : { addModule: async (url) => { log.modules.push(url) } }
    }
    createMediaStreamSource() { return { connect: (n) => log.connected.push('src'), disconnect() {} } }
    createGain() { return { gain: { value: 1 }, connect: () => log.connected.push('gain'), disconnect() {} } }
    close() { log.closed += 1 }
  }
  class AudioWorkletNodeImpl {
    constructor(ctx, name) { log.processor = name; this.port = { onmessage: null }; port = this.port }
    connect() { log.connected.push('node') }
    disconnect() {}
  }
  const frame = (v) => ({ data: new Float32Array(320).fill(v) })
  return { log, getUserMedia, AudioContextImpl, AudioWorkletNodeImpl, emit: (v) => port.onmessage?.(frame(v)) }
}

test('packets every 100 ms (5 frames of 20 ms), audioEndMs is cumulative, stop returns all PCM and releases the mic', async () => {
  const f = fakes()
  const packets = []
  let t = 0
  const cap = await startPcmCapture({ ...f, onPacket: (p) => packets.push(p), now: () => (t += 1) })
  expect(f.log.modules).toEqual(['/pcm-worklet.js'])
  expect(f.log.processor).toBe('medmap-pcm')
  for (let i = 0; i < 16; i += 1) f.emit(0.5)
  expect(packets.map((p) => p.audioEndMs)).toEqual([100, 200, 300])
  expect(new Int16Array(packets[0].pcm).length).toBe(1600)
  const all = cap.stop()                                  // 남은 1 프레임(20 ms)도 마지막 패킷으로
  expect(packets.map((p) => p.audioEndMs)).toEqual([100, 200, 300, 320])
  expect(all.reduce((n, c) => n + c.length, 0)).toBe(16 * 320)
  expect(f.log.tracksStopped).toBe(1)
  expect(f.log.closed).toBe(1)
  f.emit(0.5)                                             // stop 이후 프레임은 무시
  expect(packets).toHaveLength(4)
})

test('permission denied and unsupported are classified like useRecorder', async () => {
  await expect(startPcmCapture({ ...fakes({ rejectWith: { name: 'NotAllowedError' } }) })).rejects.toEqual({ type: 'permission' })
  await expect(startPcmCapture({ ...fakes({ rejectWith: { name: 'NotFoundError' } }) })).rejects.toEqual({ type: 'no_mic' })
  const noWorklet = fakes({ noWorklet: true })
  await expect(startPcmCapture({ ...noWorklet })).rejects.toEqual({ type: 'unsupported' })
  expect(noWorklet.log.tracksStopped).toBe(1)
  await expect(startPcmCapture({ getUserMedia: undefined, AudioContextImpl: undefined, AudioWorkletNodeImpl: undefined }))
    .rejects.toEqual({ type: 'unsupported' })
})

test('M5 AudioContext is created (and resumed) before awaiting getUserMedia, and closed if permission is denied', async () => {
  const order = []
  const f = fakes({ rejectWith: { name: 'NotAllowedError' } })
  const Base = f.AudioContextImpl
  class Ctx extends Base { constructor() { super(); this.state = 'suspended'; order.push('ctx') } resume() { order.push('resume'); return Promise.resolve() } }
  const getUserMedia = async () => { order.push('gum'); throw { name: 'NotAllowedError' } }
  await expect(startPcmCapture({ ...f, AudioContextImpl: Ctx, getUserMedia })).rejects.toEqual({ type: 'permission' })
  expect(order).toEqual(['ctx', 'resume', 'gum'])
  expect(f.log.closed).toBe(1)
})
