import { createDownsampler, downsampleTo16k, encodeWav, floatToInt16 } from './pcm.js'

test('downsample 48k → 16k keeps length ratio and averages', () => {
  const y = downsampleTo16k(new Float32Array(480).fill(0.5), 48000)
  expect(y.length).toBe(160)
  expect(y[0]).toBeCloseTo(0.5)
  expect(Array.from(downsampleTo16k(new Float32Array([0.1, 0.2]), 16000))).toEqual([expect.closeTo(0.1), expect.closeTo(0.2)])
})

test('stateful downsampler is continuous across 128-sample blocks (44.1k)', () => {
  const rate = 44100
  const n = 128 * 345                             // ≈ 1 s
  const signal = Float32Array.from({ length: n }, (_, i) => Math.sin((2 * Math.PI * 440 * i) / rate))
  const whole = createDownsampler(rate)(signal)
  const ds = createDownsampler(rate)
  const parts = []
  for (let i = 0; i < n; i += 128) parts.push(...ds(signal.subarray(i, i + 128)))
  expect(parts.length).toBe(whole.length)
  expect(Math.abs(parts.length - Math.floor((n * 16000) / rate))).toBeLessThanOrEqual(1)
  for (let i = 0; i < whole.length; i += 97) expect(parts[i]).toBeCloseTo(whole[i], 5)
})

test('floatToInt16 clips', () => {
  expect(Array.from(floatToInt16(new Float32Array([2, -2, 0, 0.5])))).toEqual([32767, -32768, 0, 16384])
})

test('encodeWav header + payload', async () => {
  const blob = encodeWav([new Int16Array([1, 2]), new Int16Array([3])], 16000)
  expect(blob.type).toBe('audio/wav')
  const view = new DataView(await blob.arrayBuffer())
  expect(view.byteLength).toBe(44 + 6)
  expect(String.fromCharCode(view.getUint8(0), view.getUint8(1), view.getUint8(2), view.getUint8(3))).toBe('RIFF')
  expect(view.getUint32(24, true)).toBe(16000)
  expect(view.getUint16(22, true)).toBe(1)
  expect(view.getInt16(44 + 4, true)).toBe(3)
})

test('public/pcm-worklet.js produces the same 16 kHz frames as createDownsampler (duplicated algorithm stays in sync)', async () => {
  const { readFileSync } = await import('node:fs')
  const { dirname, join } = await import('node:path')
  const { fileURLToPath } = await import('node:url')
  const source = readFileSync(join(dirname(fileURLToPath(import.meta.url)), '..', '..', 'public', 'pcm-worklet.js'), 'utf-8')
  let Processor
  class AudioWorkletProcessor { constructor() { this.port = { posted: [], postMessage(m) { this.posted.push(Float32Array.from(m)) } } } }
  new Function('sampleRate', 'AudioWorkletProcessor', 'registerProcessor', source)(
    48000, AudioWorkletProcessor, (name, cls) => { Processor = cls })
  const proc = new Processor()
  const n = 128 * 300
  const signal = Float32Array.from({ length: n }, (_, i) => Math.sin(i / 7))
  for (let i = 0; i < n; i += 128) proc.process([[signal.subarray(i, i + 128)]])
  const frames = proc.port.posted
  const expected = createDownsampler(48000)(signal)
  expect(frames.length).toBe(Math.floor(expected.length / 320))
  const got = new Float32Array(frames.length * 320)
  frames.forEach((f, i) => got.set(f, i * 320))
  for (let i = 0; i < got.length; i += 53) expect(got[i]).toBeCloseTo(expected[i], 6)
})
