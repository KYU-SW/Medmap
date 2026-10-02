// Phase A S1 기기 간 인계 e2e(텍스트만, GPU 불필요): 환자 휴대폰(390) → 번호 → 의사 PC(1280, 저장소가 분리된 별도 컨텍스트).
// 서버: MEDMAP_HANDOFF_CODES=1 MEDMAP_SERVE_WEB_DIST=medmap-web/dist uvicorn medmap.api:app --port <p> → MEDMAP_WEB
// 확인: 번호 인계 → blind → 건너뛰기 → 후보 5 → IG 1 답 · 같은 번호 재사용 거부 · 잘못된 번호 안내 · 화면 영어 0 · 저장 키 · 서버 처리 ms
// 결과(숫자만): OUT_DIR/handoff_code_e2e.json · 스크린샷 390/1280
import { createRequire } from 'node:module'
import { writeFileSync } from 'node:fs'

const require = createRequire(import.meta.url)
const { chromium } = require(process.env.PLAYWRIGHT_PATH ?? 'playwright')
const BASE = process.env.MEDMAP_WEB ?? 'http://127.0.0.1:8014'
const OUT = process.env.OUT_DIR ?? '../logs'
const HIT_TEXT = '다리가 붓고 숨이 차고 기침이 나고 가슴이 아프고 피를 토했어요'
const ALLOWED_EN = new Set(['MedMap', 'HIV', 'BMI', 'cm', 'COPD', 'NSAID', 'NOAC', 'ST', 'OSA'])

function check(cond, message) { if (!cond) throw new Error(`CHECK_FAILED: ${message}`) }
async function english(page) {
  const text = await page.evaluate(() => [document.body.innerText,
    ...[...document.querySelectorAll('[aria-label],[placeholder],input,textarea')].map((e) => e.getAttribute('aria-label') ?? e.value ?? '')].join('\n'))
  return [...new Set((text.match(/[A-Za-z]+/g) ?? []).filter((w) => !ALLOWED_EN.has(w)))]
}
const overflow = (page) => page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)
const serverMs = (page, path) => page.evaluate((p) => performance.getEntriesByType('resource')
  .filter((e) => new URL(e.name).pathname === p).map((e) => Math.round((e.responseStart - e.requestStart) * 10) / 10), path)

const browser = await chromium.launch({ ...(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {}) })
const result = {}
try {
  // ---- 환자 휴대폰 ----
  const phone = await browser.newContext({ viewport: { width: 390, height: 900 } })
  const p = await phone.newPage()
  await p.goto(`${BASE}/#/handoff`)
  await p.getByRole('button', { name: '시작하기' }).click()
  await p.getByLabel('나이').fill('45')
  await p.getByRole('button', { name: '남성' }).click()
  await p.getByLabel('지금 불편한 점을 편하게 적어 주세요').fill(HIT_TEXT)
  await p.getByRole('button', { name: '확인하기' }).click()
  await p.getByRole('button', { name: '다음' }).click()
  await p.getByRole('button', { name: '메스꺼움·구역질', exact: true }).click()
  await p.getByTestId('handoff-done').waitFor()
  await p.getByRole('button', { name: '다른 기기(진료실)로 보내기' }).click()
  const shown = (await p.getByTestId('handoff-code').locator('.handoff-code__number').innerText()).trim()
  check(/^\d{4}-\d{4}$/.test(shown), `code format ${shown}`)
  const phoneStorage = await p.evaluate(() => JSON.stringify({ ...sessionStorage, ...localStorage }))
  check(!phoneStorage.includes(shown.replace('-', '')), 'code written to storage')
  result.phone_english = await english(p)
  result.phone_overflow = await overflow(p)
  result.codes_server_ms = await serverMs(p, '/v1/handoff/codes')
  await p.screenshot({ path: `${OUT}/handoff_phone_390.png`, fullPage: true })

  // ---- 의사 PC(별도 컨텍스트 = 저장소 공유 없음) ----
  const pc = await browser.newContext({ viewport: { width: 1280, height: 900 } })
  const d = await pc.newPage()
  await d.goto(`${BASE}/#/doctor`)
  await d.getByLabel('환자 번호').waitFor()
  await d.getByLabel('환자 번호').fill('0000-0000')
  await d.getByRole('button', { name: '번호로 불러오기' }).click()
  await d.getByText('번호를 다시 확인해 주세요', { exact: false }).waitFor()
  await d.getByLabel('환자 번호').fill(shown)
  await d.getByRole('button', { name: '번호로 불러오기' }).click()
  await d.getByText('환자 요약').waitFor()
  check(await d.getByTestId('doctor-candidates').count() === 0, 'candidates before WD (blind broken)')
  await d.getByRole('button', { name: '건너뛰기' }).click()
  const cands = d.getByTestId('doctor-candidates')
  await cands.waitFor()
  check(await cands.getByRole('listitem').count() === 5, 'candidates != 5')
  const next = d.getByTestId('doctor-next')
  await next.getByRole('button', { name: '아니요', exact: true }).click()
  await d.waitForFunction(() => document.querySelector('[data-testid="doctor-next-counter"]')?.textContent.includes('1 / 3'))
  const cache = await d.evaluate(() => sessionStorage.getItem('medmap.doctor.cache'))
  check(cache && JSON.parse(cache).some((e) => e.evidence_id === 'E_53'), 'patient cache not carried over')
  result.claim_server_ms = await serverMs(d, '/v1/handoff/claim')
  result.pc_english = await english(d)
  result.pc_overflow = await overflow(d)
  await d.screenshot({ path: `${OUT}/handoff_pc_1280.png`, fullPage: true })

  // ---- 같은 번호 재사용 거부(다른 PC) ----
  const other = await browser.newContext({ viewport: { width: 1280, height: 900 } })
  const o = await other.newPage()
  await o.goto(`${BASE}/#/doctor`)
  await o.getByLabel('환자 번호').fill(shown)
  await o.getByRole('button', { name: '번호로 불러오기' }).click()
  await o.getByText('번호를 다시 확인해 주세요', { exact: false }).waitFor()
  check(await o.getByText('환자 요약').count() === 0, 'reused code opened a session')

  check(result.phone_english.length === 0 && result.pc_english.length === 0, `English on screen ${result.phone_english} ${result.pc_english}`)
  check(!result.phone_overflow && !result.pc_overflow, 'horizontal overflow')
  result.ok = true
} catch (error) {
  result.ok = false
  result.error = String(error.message ?? error).slice(0, 300)
}
await browser.close()
writeFileSync(`${OUT}/handoff_code_e2e.json`, JSON.stringify(result, null, 1))
console.log(JSON.stringify(result))
if (!result.ok) process.exit(1)
console.log('HANDOFF_CODE_E2E_OK')
