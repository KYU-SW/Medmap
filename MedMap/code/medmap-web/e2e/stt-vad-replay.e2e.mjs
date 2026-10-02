// 실제 사람 발화 녹음 replay → VAD endpoint threshold 비교(M2 Task 12). GPU 필요 — wait_for_resources --check OK 일 때만.
// 서버: MEDMAP_STT_ENGINE=ct2 + worker(VAD) + MEDMAP_STT_VAD_SILENCE_MS=<threshold> → MEDMAP_WEB=http://127.0.0.1:8010
// 입력: REPLAY_MANIFEST = scripts/stt_replay_prepare.py 가 만든 manifest.json(wav·sentences·numbers). 녹음마다 Chromium 가짜 마이크.
// 채점(녹음·반복마다, 숫자만 저장 — 전사문·오디오는 파일에 쓰지 않는다):
//   false_endpoints   = VAD 가 문장 중간에서 발화를 끊은 수(FINAL 경계가 정답 문장 끝 ±TOL 글자 밖)
//   missed_endpoints  = 정답 문장 끝인데 FINAL 경계가 없음(두 문장이 한 FINAL 로 합쳐짐)
//   delayed_end       = 마지막 문장이 VAD 로 닫히지 않고 수동 stop 에서야 닫힘(녹음 끝 + TAIL_MS 안에 endpoint 없음)
//   T_partial         = 음성 구간 안 패킷 → partial 표시. 발화 안 쉼(서버 FINAL srv_ms.pauses_ms, ≥96 ms) 패킷은 제외
//   T_final_vad       = 발화 끝(서버 VAD 가 알린 마지막 음성 프레임이 담긴 패킷의 캡처 시각) → FINAL 표시
//   cer · del · ins · sub(정렬 연산 수) · dup(같은 FINAL 조각이 두 번 나옴) · numeric(숫자 표기 accept 목록 중 하나라도 있음)
import { createRequire } from 'node:module'
import { readFileSync, writeFileSync } from 'node:fs'
import { pct, score, tPartialSamples } from './replayScore.mjs'

const require = createRequire(import.meta.url)
const { chromium } = require(process.env.PLAYWRIGHT_PATH ?? 'playwright')
const BASE = process.env.MEDMAP_WEB ?? 'http://127.0.0.1:8010'
const OUT = process.env.OUT_DIR ?? '../logs'
const LABEL = process.env.LABEL ?? 'replay'
const REPEATS = Number(process.env.REPEATS ?? 2)
const TAIL_MS = Number(process.env.TAIL_MS ?? 2000)
const MANIFEST = JSON.parse(readFileSync(process.env.REPLAY_MANIFEST, 'utf-8'))

const STATUS = await (await fetch(`${BASE}/v1/stt/status`)).json()
if (STATUS.vad !== 'server') { console.error(`VAD not active: ${STATUS.vad}`); process.exit(2) }

async function runOnce(rec) {
  const browser = await chromium.launch({
    ...(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {}),
    args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', `--use-file-for-fake-audio-capture=${rec.wav}%noloop`,
      '--autoplay-policy=no-user-gesture-required'],
  })
  try {
    const context = await browser.newContext({ viewport: { width: 390, height: 900 }, permissions: ['microphone'] })
    const page = await context.newPage()
    const frames = []                                   // 메모리에서만 채점에 쓴다(파일에 쓰지 않음)
    page.on('websocket', (ws) => ws.on('framereceived', (f) => {
      try { const msg = JSON.parse(f.payload); if (msg.type === 'final' || msg.type === 'utterance_end') frames.push(msg) } catch { /* binary */ }
    }))
    await page.goto(BASE)
    await page.getByRole('button', { name: '시작하기' }).click()
    await page.getByLabel('나이').fill('45')
    await page.getByRole('button', { name: '남성' }).click()
    await page.evaluate(() => window.__medmapPerf?.reset())
    await page.getByRole('button', { name: '🎙 말하기' }).click()
    await page.getByText('● 듣고 있어요').waitFor({ timeout: 10000 })
    await page.waitForTimeout(Math.round(rec.duration_s * 1000) + TAIL_MS)
    await page.getByRole('button', { name: '그만 말하기' }).click()
    await page.getByRole('button', { name: '🎙 말하기' }).waitFor({ timeout: 30000 })
    const perf = await page.evaluate(() => window.__medmapPerf?.entries() ?? [])
    const transport = perf.find((e) => e.name === 'stream_open')?.transport ?? null
    await context.close()

    const reasons = new Map(frames.filter((m) => m.type === 'utterance_end').map((m) => [m.utt, m.reason]))
    const segments = frames.filter((m) => m.type === 'final').map((m) => ({ text: m.text ?? '', reason: reasons.get(m.utt) ?? null }))
    const packets = perf.filter((e) => e.name === 'packet')
    const stop = perf.find((e) => e.name === 'stop_click')
    const finalRecvs = perf.filter((e) => e.name === 'final_recv')
    const renders = perf.filter((e) => e.name === 'final_render')
    const vadFinals = finalRecvs.filter((f) => f.srv_speech_end != null && (!stop || f.t < stop.t))
    // T_partial: VAD 음성 구간 안의 패킷만(realtime-stt.e2e.mjs 와 같은 규칙) + 발화 안 쉼(서버 pauses_ms) 패킷 제외
    const partials = perf.filter((e) => e.name === 'partial_render' && e.audio_ms != null)
    const spans = finalRecvs.filter((f) => f.srv_speech_start != null).map((f) => [f.srv_speech_start, f.srv_speech_end ?? Infinity])
    const pauses = frames.filter((m) => m.type === 'final').flatMap((m) => m.srv_ms?.pauses_ms ?? [])
    const { values: tPartial, excluded_pause: tPartialPauseExcluded } = tPartialSamples(packets, partials, spans, pauses)
    const tFinalVad = []
    for (const f of vadFinals) {
      const endPacket = packets.find((p) => p.audio_ms >= f.srv_speech_end)
      const render = renders.find((r) => r.audio_ms === f.audio_ms && r.t >= f.t)
      if (endPacket && render) tFinalVad.push(Math.round((render.t - endPacket.t) * 10) / 10)
    }
    return { ok: transport === 'ws', transport, vad_finals: vadFinals.length,
      predecoded: vadFinals.filter((f) => f.srv_predecoded).length,
      spec_discarded: finalRecvs.reduce((a, f) => a + (f.srv_spec_discarded ?? 0), 0),
      manual_final_with_text: segments.some((x) => x.reason === 'manual' && x.text.trim()),
      t_final_vad: tFinalVad, t_partial: tPartial, t_partial_pause_excluded: tPartialPauseExcluded, pauses: pauses.length, category: rec.category ?? null, speed: rec.speed ?? null, ...score(rec, segments) }
  } finally {
    await browser.close()
  }
}

const rows = []
for (let r = 0; r < REPEATS; r++) {
  for (const rec of MANIFEST.recordings) {
    try {
      rows.push({ id: rec.id, repeat: r, ...(await runOnce(rec)) })
    } catch (error) {
      rows.push({ id: rec.id, repeat: r, ok: false, error: String(error.message ?? error).slice(0, 200) })
    }
  }
}
const ok = rows.filter((x) => x.ok)
const sum = (k) => ok.reduce((a, x) => a + (Number(x[k]) || 0), 0)
const tfv = ok.flatMap((x) => x.t_final_vad)
const tp = ok.flatMap((x) => x.t_partial)
const byCategory = {}
for (const x of ok) {
  const c = (byCategory[x.category ?? '-'] ??= { runs: 0, false_endpoints: 0, numeric_split: 0, delayed_end: 0, t_final_vad: [] })
  c.runs++; c.false_endpoints += x.false_endpoints; c.numeric_split += x.numeric_split; c.delayed_end += x.delayed_end ? 1 : 0
  c.t_final_vad.push(...x.t_final_vad)
}
for (const c of Object.values(byCategory)) { c.T_final_vad_p95 = pct(c.t_final_vad, 0.95); delete c.t_final_vad }
const summary = {
  label: LABEL, vad_silence_ms: STATUS.vad_silence_ms, vad_predecode_ms: STATUS.vad_predecode_ms,
  runs: rows.length, ok_runs: ok.length,
  false_endpoints: sum('false_endpoints'), boundaries: sum('boundaries'),
  missed_endpoints: sum('missed_endpoints'), internal_sentence_ends: sum('internal_sentence_ends'),
  delayed_end_runs: ok.filter((x) => x.delayed_end).length,
  T_final_vad_ms: { p50: pct(tfv, 0.5), p95: pct(tfv, 0.95), n: tfv.length, over_500: tfv.filter((x) => x > 500).length },
  T_partial_ms: { p50: pct(tp, 0.5), p95: pct(tp, 0.95), n: tp.length, pause_packets_excluded: sum('t_partial_pause_excluded') },
  in_utterance_pauses: sum('pauses'),
  predecoded_finals: sum('predecoded'), vad_finals: sum('vad_finals'), spec_discarded: sum('spec_discarded'),
  predecode_reuse_rate: sum('vad_finals') ? Math.round((sum('predecoded') / sum('vad_finals')) * 1000) / 1000 : null,
  predecode_discard_rate: (sum('predecoded') + sum('spec_discarded'))
    ? Math.round((sum('spec_discarded') / (sum('predecoded') + sum('spec_discarded'))) * 1000) / 1000 : null,
  endpoints: sum('n_text_finals'), numeric_split: sum('numeric_split'),
  manual_final_with_text_runs: ok.filter((x) => x.manual_final_with_text).length,
  // 사람이 고쳐야 하는 경우의 대리 지표: 문장 중간 잘림 + 숫자 분리 + 늦은 확정(마지막 문장이 수동 stop 으로만 닫힘)
  manual_correction_proxy: sum('false_endpoints') + sum('numeric_split') + ok.filter((x) => x.delayed_end).length,
  by_category: byCategory,
  cer_mean: ok.length ? Math.round((ok.reduce((a, x) => a + x.cer, 0) / ok.length) * 1000) / 1000 : null,
  deletions: sum('del'), insertions: sum('ins'), substitutions: sum('sub'), dup_runs: ok.filter((x) => x.dup).length,
  numeric: { pass: sum('numeric_pass'), total: sum('numeric_total') },
}
writeFileSync(`${OUT}/replay_${LABEL}.json`, JSON.stringify({ summary, rows }, null, 1))
console.log(JSON.stringify(summary))
if (ok.length !== rows.length) process.exit(1)
console.log('VAD_REPLAY_OK')
