// 실서버 streaming STT e2e + 지연 측정(REALTIME_FIRST). GPU 필요(실제 Whisper) — wait_for_resources --check 가 OK 일 때만.
// 서버: MEDMAP_STT_STREAMING=1 MEDMAP_SERVE_WEB_DIST=medmap-web/dist uvicorn medmap.api:app --port 8010 → MEDMAP_WEB=http://127.0.0.1:8010
// Chromium 가짜 마이크(WAV %noloop). 시나리오:
//   WS    (RUNS 회): 말하는 동안 partial 이 보임 · stop → 입력칸에 FINAL · 세션/매퍼 호출 0 · T_partial·T_final 측정
//   HTTP  : WebSocket 을 없앤 브라우저 → HTTP chunk 경로로 같은 결과
//   LEGACY: WebSocket 없음 + /v1/stt/stream* 차단 → 기존 /v1/stt/transcribe 1회로 FINAL
// T_partial(오디오 시점별) = 그 시점까지의 오디오가 처음 담긴 partial 이 화면에 그려진 시각 − 그 오디오 패킷이 캡처된 시각.
// T_final = [그만 말하기] 클릭 → FINAL 이 화면에 그려진 시각. 결과는 숫자만 OUT_DIR/rt_m1_e2e_perf.json.
// 서버 VAD(M2, status.vad === 'server'): T_final_vad = 발화 끝(서버 VAD 가 알린 마지막 음성 프레임 끝이 담긴 패킷의 캡처 시각)
//   → 그 발화 FINAL 이 그려진 시각(spec §5 T_final 정의). T_partial 은 VAD 음성 구간 안의 패킷만 센다(무음은 표시할 글자가 없다).
import { createRequire } from 'node:module'
import { writeFileSync } from 'node:fs'

const require = createRequire(import.meta.url)
const { chromium } = require(process.env.PLAYWRIGHT_PATH ?? 'playwright')
const BASE = process.env.MEDMAP_WEB ?? 'http://127.0.0.1:8010'
const OUT = process.env.OUT_DIR ?? '../logs'
const WAV = process.env.VOICE_WAV ?? '../stt/samples/medmap_tts_test.wav'
const RECORD_MS = Number(process.env.RECORD_MS ?? 8500)
const RUNS = Number(process.env.RUNS ?? 13)            // WS: 첫 1회 warm-up 제외
const HTTP_RUNS = Number(process.env.HTTP_RUNS ?? 4)
const LEGACY_RUNS = Number(process.env.LEGACY_RUNS ?? 2)
const ONLY = process.env.ONLY ?? ''                       // 'workerdown': worker 를 끈 서버에서 legacy 강등만 검증
const EXPECTED = process.env.EXPECTED_TEXT ?? '어제부터 배가 아팠는데'
const EXPECT_VAD_FINALS = Number(process.env.EXPECT_VAD_FINALS ?? 2)     // 샘플 = 두 문장, 사이 무음 ≈ 830 ms > 600 ms
// transcript quality: 샘플 원문 대비 CER(공백·문장부호 제거, 문자 단위 편집거리 / 원문 길이). 숫자만 기록한다.
const REFERENCE = process.env.REFERENCE_TEXT ?? '어제부터 배가 아팠는데 오늘은 오른쪽 아래가 더 아파요. 열은 없고 구토를 두 번 했어요.'

function check(cond, message) { if (!cond) throw new Error(`CHECK_FAILED: ${message}`) }
const norm = (t) => t.replace(/[\s.,!?·]/g, '')
function cer(hyp, ref) {
  const a = [...norm(ref)]; const b = [...norm(hyp)]
  let prev = Array.from({ length: b.length + 1 }, (_, j) => j)
  for (let i = 1; i <= a.length; i++) {
    const cur = [i]
    for (let j = 1; j <= b.length; j++) cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1))
    prev = cur
  }
  return Math.round((prev[b.length] / Math.max(1, a.length)) * 1000) / 1000
}
const pct = (xs, q) => {
  if (!xs.length) return null
  const s = [...xs].sort((a, b) => a - b)
  const i = (s.length - 1) * q
  const lo = Math.floor(i); const hi = Math.ceil(i)
  return Math.round((s[lo] + (s[hi] - s[lo]) * (i - lo)) * 10) / 10
}

const STATUS = await (await fetch(`${BASE}/v1/stt/status`)).json()
const VAD = STATUS.vad === 'server'

const browser = await chromium.launch({
  ...(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {}),
  args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', `--use-file-for-fake-audio-capture=${WAV}%noloop`,
    '--autoplay-policy=no-user-gesture-required'],
})

async function runOnce(mode, width = 390) {
  const context = await browser.newContext({ viewport: { width, height: 900 }, permissions: ['microphone'] })
  if (mode === 'http' || mode === 'legacy') await context.addInitScript(() => { window.WebSocket = undefined })
  const page = await context.newPage()
  if (mode === 'legacy') await page.route('**/v1/stt/stream**', (route) => route.abort())
  const posts = []
  page.on('request', (req) => { if (req.method() === 'POST') posts.push(new URL(req.url()).pathname) })

  await page.goto(BASE)
  await page.getByRole('button', { name: '시작하기' }).click()
  await page.getByLabel('나이').fill('45')
  await page.getByRole('button', { name: '남성' }).click()
  await page.evaluate(() => window.__medmapPerf?.reset())
  await page.getByRole('button', { name: '🎙 말하기' }).click()
  await page.getByText('● 듣고 있어요').waitFor({ timeout: 10000 })
  const partialLine = page.getByTestId('stt-partial')
  let sawPartialWhileSpeaking = false
  const deadline = Date.now() + RECORD_MS
  while (Date.now() < deadline) {
    const text = (await partialLine.innerText().catch(() => '')).trim()
    if (text && !text.startsWith('말씀하시면')) sawPartialWhileSpeaking = true
    await page.waitForTimeout(100)
  }
  await page.getByRole('button', { name: '그만 말하기' }).click()
  await page.waitForFunction(() => (document.querySelector('textarea')?.value ?? '').length > 0, null, { timeout: 60000 })
  await page.getByRole('button', { name: '🎙 말하기' }).waitFor({ timeout: 30000 })
  const value = await page.getByLabel('지금 불편한 점을 편하게 적어 주세요').inputValue()
  // M4: streaming 이면 FINAL 뒤 '확인 대기' 후보가 뜨고, [확인하기]는 extract 를 다시 부르지 않는다
  const postsBeforeConfirm = [...posts]
  let prep = null
  if (mode === 'ws' || mode === 'http') {
    const shown = await page.getByTestId('prepared-candidates').waitFor({ timeout: 5000 }).then(() => true, () => false)
    const extractBefore = posts.filter((u) => u === '/v1/intake/extract').length
    let extraExtract = null
    if (shown) {
      await page.getByRole('button', { name: '확인하기' }).click()
      await page.getByTestId('confirm-item').first().waitFor({ timeout: 5000 })
      extraExtract = posts.filter((u) => u === '/v1/intake/extract').length - extractBefore
    }
    prep = { shown, extractBefore, extraExtract }
  }
  const perf = await page.evaluate(() => window.__medmapPerf?.entries() ?? [])
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)
  await page.screenshot({ path: `${OUT}/rt_m1_${mode}_${width}.png`, fullPage: true })
  await context.close()

  const opened = perf.find((e) => e.name === 'stream_open')
  const packets = perf.filter((e) => e.name === 'packet')
  const partials = perf.filter((e) => e.name === 'partial_render' && e.audio_ms != null)
  const stop = perf.find((e) => e.name === 'stop_click')
  const finalRender = perf.filter((e) => e.name === 'final_render').pop()
  const recvs = perf.filter((e) => e.name === 'partial_recv')
  const capAt = new Map(packets.map((p) => [p.audio_ms, p.t]))
  const finalRecvs = perf.filter((e) => e.name === 'final_recv')
  const finalRenders = perf.filter((e) => e.name === 'final_render')
  // VAD 음성 구간 [speech_start, speech_end](스트림 ms). 수동 모드면 구간 없음 → 모든 패킷(M1 과 같은 규칙)
  const spans = finalRecvs.filter((f) => f.srv_speech_start != null)
    .map((f) => [f.srv_speech_start, f.srv_speech_end ?? Infinity])
  const inSpeech = (ms) => !spans.length || spans.some(([a, b]) => ms >= a && ms <= b)
  const vadFinals = finalRecvs.filter((f) => f.srv_speech_end != null && (!stop || f.t < stop.t))
  const tFinalVad = []
  for (const f of vadFinals) {
    const endPacket = packets.find((p) => p.audio_ms >= f.srv_speech_end)
    const render = finalRenders.find((r) => r.audio_ms === f.audio_ms && r.t >= f.t)
    if (endPacket && render) tFinalVad.push(render.t - endPacket.t)
  }
  const tPartial = []
  const parts = []                                      // 오디오 시점별 구간(ms): tick_wait · network · server(held/queue/worker/ipc) · render
  for (const p of packets) {
    if (p.audio_ms < 300 || !inSpeech(p.audio_ms)) continue
    const shown = partials.find((r) => r.audio_ms >= p.audio_ms && r.t >= p.t)
    if (!shown) continue
    const total = shown.t - p.t
    tPartial.push(total)
    const recv = recvs.find((r) => r.audio_ms === shown.audio_ms)
    const capA = capAt.get(shown.audio_ms)
    if (recv && capA != null && recv.srv_since_recv != null) {
      parts.push({ total, tick_wait: capA - p.t, network: recv.t - capA - recv.srv_since_recv, server: recv.srv_since_recv,
        held: recv.srv_held, queue: recv.srv_queue, decode: recv.srv_decode, worker: recv.srv_worker, ipc: recv.srv_ipc,
        render: shown.t - recv.t })
    }
  }
  const finalRecv = perf.filter((e) => e.name === 'final_recv').pop()
  // 말하는 동안(확인 전): 세션·doctor 호출 0. 후보 준비용 /v1/intake/extract 만 허용(M4, 상태 없음)
  const nonStt = postsBeforeConfirm.filter((u) => !u.startsWith('/v1/stt/') && u !== '/v1/intake/extract')
  const prepRender = perf.filter((e) => e.name === 'prep_render').pop()
  const finalBeforePrep = prepRender ? perf.filter((e) => e.name === 'final_render' && e.t <= prepRender.t).pop() : null
  const prepReady = perf.filter((e) => e.name === 'prep_ready').pop()
  const occurrences = value.split(EXPECTED).length - 1
  return {
    mode, width, transport: opened?.transport ?? null, sawPartialWhileSpeaking,
    textOk: value.includes(EXPECTED), cer: cer(value, REFERENCE), overflow, nonSttPosts: nonStt,
    prep, tPrep: prepRender && finalBeforePrep ? prepRender.t - finalBeforePrep.t : null,
    tPrepRequest: prepReady ? prepReady.t_prep_request : null,
    sttPosts: [...new Set(posts.filter((u) => u.startsWith('/v1/stt/')))],
    vadFinals: vadFinals.length, tFinalVad, predecodedFinals: vadFinals.filter((f) => f.srv_predecoded).length,
    tPartial, parts, occurrences, tFinal: stop && finalRender ? finalRender.t - stop.t : null, partialRenders: partials.length,
    finalBreakdown: stop && finalRecv && finalRender ? { stop_to_recv: finalRecv.t - stop.t, render: finalRender.t - finalRecv.t,
      decode: finalRecv.srv_decode, worker: finalRecv.srv_worker, ipc: finalRecv.srv_ipc, queue: finalRecv.srv_queue, reused: finalRecv.reused } : null,
  }
}

const results = []
let failed = false
const plan = ONLY === 'workerdown' ? [['workerdown', 390]] : [
  ...Array.from({ length: RUNS }, (_, i) => ['ws', i % 2 ? 1280 : 390]),
  ...Array.from({ length: HTTP_RUNS }, () => ['http', 390]),
  ...Array.from({ length: LEGACY_RUNS }, () => ['legacy', 390]),
]
for (const [mode, width] of plan) {
  try {
    const r = await runOnce(mode, width)
    check(r.textOk, `${mode}: final text missing expected phrase`)
    check(r.occurrences === 1, `${mode}: FINAL text duplicated (${r.occurrences})`)
    check(r.nonSttPosts.length === 0, `${mode}: non-STT POST during speech ${r.nonSttPosts}`)
    check(!r.overflow, `${mode}: horizontal overflow`)
    if (mode === 'ws') { check(r.transport === 'ws', 'ws transport'); check(r.sawPartialWhileSpeaking, 'no partial while speaking') }
    if (mode === 'ws' || mode === 'http') {
      check(r.prep?.shown, `${mode}: prepared candidates not shown after FINAL`)
      check(r.prep?.extraExtract === 0, `${mode}: 확인하기 re-extracted (${r.prep?.extraExtract})`)
    }
    if (VAD && (mode === 'ws' || mode === 'http')) check(r.vadFinals >= EXPECT_VAD_FINALS, `${mode}: VAD auto finals ${r.vadFinals} < ${EXPECT_VAD_FINALS}`)
    if (mode === 'http') { check(r.transport === 'http', `http transport (${r.transport})`); check(r.sawPartialWhileSpeaking, 'http: no partial while speaking') }
    if (mode === 'legacy') { check(r.transport === 'legacy', 'legacy transport'); check(r.sttPosts.includes('/v1/stt/transcribe'), 'legacy did not call /transcribe') }
    if (mode === 'workerdown') { check(r.sttPosts.includes('/v1/stt/transcribe'), 'worker down: legacy /transcribe not used') }
    results.push({ ...r, ok: true })
  } catch (error) {
    failed = true
    results.push({ mode, width, ok: false, error: String(error.message ?? error).slice(0, 300) })
  }
}
await browser.close()

const warmWs = results.filter((r) => r.mode === 'ws' && r.ok).slice(1)        // 첫 실행 = warm-up 제외
const coldWs = results.find((r) => r.mode === 'ws' && r.ok)
const breakdown = (rows) => {
  if (!rows.length) return null
  const keys = ['total', 'tick_wait', 'network', 'server', 'held', 'queue', 'decode', 'worker', 'ipc', 'render']
  const out = {}
  for (const k of keys) {
    const xs = rows.map((r) => r[k]).filter((x) => x != null)
    out[k] = { p50: pct(xs, 0.5), p95: pct(xs, 0.95) }
  }
  const cut = pct(rows.map((r) => r.total), 0.9)
  const tail = rows.filter((r) => r.total >= cut)
  out.tail_mean_at_p90_plus = Object.fromEntries(keys.map((k) => [k, Math.round(tail.reduce((a, r) => a + (r[k] ?? 0), 0) / Math.max(1, tail.length))]))
  return out
}
const stats = (rows) => {
  const tp = rows.flatMap((r) => r.tPartial ?? [])
  const tf = rows.map((r) => r.tFinal).filter((x) => x != null)
  const cers = rows.map((r) => r.cer).filter((x) => x != null)
  const tfv = rows.flatMap((r) => r.tFinalVad ?? [])
  const tprep = rows.map((r) => r.tPrep).filter((x) => x != null)
  const tprepReq = rows.map((r) => r.tPrepRequest).filter((x) => x != null)
  return { runs: rows.length, cer: { mean: cers.length ? Math.round((cers.reduce((a, x) => a + x, 0) / cers.length) * 1000) / 1000 : null, max: cers.length ? Math.max(...cers) : null },
    T_partial_ms: { p50: pct(tp, 0.5), p95: pct(tp, 0.95), n: tp.length },
    T_final_ms: { p50: pct(tf, 0.5), p95: pct(tf, 0.95), n: tf.length },
    T_final_vad_ms: { p50: pct(tfv, 0.5), p95: pct(tfv, 0.95), n: tfv.length },
    T_prep_ms: { p50: pct(tprep, 0.5), p95: pct(tprep, 0.95), n: tprep.length, target: '<=300' },
    T_prep_request_ms: { p50: pct(tprepReq, 0.5), p95: pct(tprepReq, 0.95), n: tprepReq.length },
    vad_finals_per_run: rows.map((r) => r.vadFinals ?? 0), predecoded_finals_per_run: rows.map((r) => r.predecodedFinals ?? 0), breakdown: breakdown(rows.flatMap((r) => r.parts ?? [])),
    final_breakdown: rows.map((r) => r.finalBreakdown).filter(Boolean) }
}
const summary = {
  targets: { T_partial_p95: '<=600', T_final_p95: '<=500' },
  vad: STATUS.vad, engine: STATUS.engine,
  ws_warm: stats(warmWs),
  ws_cold_first_run: coldWs ? { T_partial_p50: pct(coldWs.tPartial, 0.5), T_partial_p95: pct(coldWs.tPartial, 0.95), T_final: coldWs.tFinal } : null,
  http: stats(results.filter((r) => r.mode === 'http' && r.ok)),
  legacy: stats(results.filter((r) => r.mode === 'legacy' && r.ok)),
  workerdown: stats(results.filter((r) => r.mode === 'workerdown' && r.ok)),
}
const outName = process.env.PERF_NAME ?? 'rt_m1_e2e_perf'
writeFileSync(`${OUT}/${outName}.json`, JSON.stringify({ summary, results: results.map(({ tPartial, parts, tFinalVad, ...rest }) => rest) }, null, 1))
console.log(JSON.stringify(summary, null, 1))
console.log(JSON.stringify(results.map((r) => ({ mode: r.mode, width: r.width, ok: r.ok, transport: r.transport, error: r.error })), null, 0))
if (failed) process.exit(1)
console.log('REALTIME_STT_E2E_OK')
