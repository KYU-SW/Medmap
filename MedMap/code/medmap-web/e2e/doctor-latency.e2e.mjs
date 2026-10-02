// M5 Doctor real-time loop 지연(REALTIME_FIRST): 의사가 IG 질문에 답한 순간 → 갱신된 후보 + 다음 질문(또는 한도 도달)이 그려질 때까지.
// 텍스트만(GPU 불필요). 서버: MEDMAP_SERVE_WEB_DIST=medmap-web/dist uvicorn medmap.api:app --port 8010 → MEDMAP_WEB
// 경로는 doctor-mode.e2e.mjs HIT 와 같은 고정 입력(#/handoff → #/doctor → 건너뛰기 → 질문 3개 답).
// 측정(답 하나마다, 숫자만): T_next = doctor_next_render − doctor_answer_click · click→response · response→render
//   · server = Resource Timing(/v1/doctor/answer responseStart − requestStart, 로컬 루프백이라 서버 처리 시간에 가깝다)
// cold = 서버 재시작 직후 첫 실행의 첫 답(러너가 재시작을 보장). warm = 두 번째 실행부터. 결과: OUT_DIR/<PERF_NAME>.json
import { createRequire } from 'node:module'
import { writeFileSync } from 'node:fs'

const require = createRequire(import.meta.url)
const { chromium } = require(process.env.PLAYWRIGHT_PATH ?? 'playwright')
const BASE = process.env.MEDMAP_WEB ?? 'http://127.0.0.1:8010'
const OUT = process.env.OUT_DIR ?? '../logs'
const RUNS = Number(process.env.RUNS ?? 20)
const HIT_TEXT = '다리가 붓고 숨이 차고 기침이 나고 가슴이 아프고 피를 토했어요'

function check(cond, message) { if (!cond) throw new Error(`CHECK_FAILED: ${message}`) }
const pct = (xs, q) => {
  if (!xs.length) return null
  const s = [...xs].sort((a, b) => a - b)
  const i = (s.length - 1) * q
  const lo = Math.floor(i); const hi = Math.ceil(i)
  return Math.round((s[lo] + (s[hi] - s[lo]) * (i - lo)) * 10) / 10
}
const stats = (xs) => ({ p50: pct(xs, 0.5), p95: pct(xs, 0.95), max: xs.length ? Math.round(Math.max(...xs) * 10) / 10 : null, n: xs.length })

async function counter(page) {
  return (await page.getByTestId('doctor-next-counter').innerText()).trim()
}

async function answerCurrent(page) {
  const before = await counter(page)
  const next = page.getByTestId('doctor-next')
  const no = next.getByRole('button', { name: '아니요', exact: true })
  if (await no.count()) {
    await no.click()
  } else {
    await next.locator('.question__choices button').nth(1).click()
    const go = next.getByRole('button', { name: '다음', exact: true })
    if (await go.count() && await go.isEnabled()) await go.click()
  }
  await page.waitForFunction((prev) => {
    const el = document.querySelector('[data-testid="doctor-next-counter"]')
    return el && el.textContent.trim() !== prev
  }, before)
}

const browser = await chromium.launch({ ...(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {}) })

async function runOnce(width) {
  const context = await browser.newContext({ viewport: { width, height: 900 } })
  const page = await context.newPage()
  await page.goto(`${BASE}/#/handoff`)
  await page.getByRole('button', { name: '시작하기' }).click()
  await page.getByLabel('나이').fill('45')
  await page.getByRole('button', { name: '남성' }).click()
  await page.getByLabel('지금 불편한 점을 편하게 적어 주세요').fill(HIT_TEXT)
  await page.getByRole('button', { name: '확인하기' }).click()
  await page.getByRole('button', { name: '다음' }).click()
  await page.getByRole('button', { name: '메스꺼움·구역질', exact: true }).click()
  await page.getByTestId('handoff-done').waitFor()
  await page.getByRole('link', { name: '의사 화면 열기' }).click()
  await page.getByText('환자 요약').waitFor()
  await page.getByRole('button', { name: '건너뛰기' }).click()
  await page.getByTestId('doctor-candidates').waitFor()
  await page.evaluate(() => { window.__medmapPerf?.reset(); performance.clearResourceTimings() })
  for (let i = 0; i < 3; i++) {
    await answerCurrent(page)
    await page.waitForTimeout(300)                      // 사람의 답 사이 간격(측정 구간 밖)
  }
  await page.getByText('추가 질문 한도에 도달했습니다', { exact: false }).waitFor()
  const perf = await page.evaluate(() => window.__medmapPerf?.entries() ?? [])
  const res = await page.evaluate(() => performance.getEntriesByType('resource')
    .filter((e) => new URL(e.name).pathname === '/v1/doctor/answer')
    .map((e) => ({ start: e.startTime, server: e.responseStart - e.requestStart, total: e.responseEnd - e.startTime })))
  await context.close()

  const clicks = perf.filter((e) => e.name === 'doctor_answer_click')
  const answers = []
  for (const click of clicks) {
    const response = perf.find((e) => e.name === 'doctor_answer_response' && e.t >= click.t)
    const render = perf.find((e) => e.name === 'doctor_next_render' && response && e.t >= response.t)
    const r = res.find((x) => x.start >= click.t - 1)
    if (!response || !render) continue
    answers.push({ t_next: render.t - click.t, click_to_response: response.t - click.t, response_to_render: render.t - response.t,
      server: r ? r.server : null, http_total: r ? r.total : null, questions_used: render.questions_used })
  }
  check(answers.length === 3, `answers measured ${answers.length} != 3`)
  return answers
}

const runs = []
let failed = false
for (let i = 0; i < RUNS; i++) {
  try {
    runs.push({ run: i, width: i % 2 ? 1280 : 390, answers: await runOnce(i % 2 ? 1280 : 390) })
  } catch (error) {
    failed = true
    runs.push({ run: i, error: String(error.message ?? error).slice(0, 200) })
  }
}
await browser.close()

const ok = runs.filter((r) => r.answers)
const warm = ok.slice(1).flatMap((r) => r.answers)
const first = ok[0]?.answers ?? []
const pick = (rows, k) => rows.map((a) => a[k]).filter((x) => x != null)
const summary = {
  target: { T_next_warm_p95: '<=500' },
  runs: runs.length, ok_runs: ok.length,
  cold_first_answer: first[0] ?? null,
  first_run: stats(pick(first, 't_next')),
  warm: {
    T_next: stats(pick(warm, 't_next')),
    click_to_response: stats(pick(warm, 'click_to_response')),
    server: stats(pick(warm, 'server')),
    response_to_render: stats(pick(warm, 'response_to_render')),
    by_question: [1, 2, 3].map((q) => ({ questions_used: q, T_next: stats(warm.filter((a) => a.questions_used === q).map((a) => a.t_next)) })),
  },
}
const name = process.env.PERF_NAME ?? 'rt_m5_tnext'
writeFileSync(`${OUT}/${name}.json`, JSON.stringify({ summary, runs }, null, 1))
console.log(JSON.stringify(summary, null, 1))
if (failed) process.exit(1)
console.log('DOCTOR_LATENCY_E2E_OK')
