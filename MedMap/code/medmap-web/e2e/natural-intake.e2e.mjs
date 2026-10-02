// 실서버 스모크: API(:8000) + vite(:5173) 가 떠 있어야 한다. 설치 없이 캐시된 playwright 를 쓴다.
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const { chromium } = require(process.env.PLAYWRIGHT_PATH ?? 'playwright')
const BASE = process.env.MEDMAP_WEB ?? 'http://127.0.0.1:5173'
const OUT = process.env.OUT_DIR ?? '../logs'

async function describe(page, text) {
  await page.getByRole('button', { name: '시작하기' }).click()
  await page.getByLabel('나이').fill('45')
  await page.getByRole('button', { name: '남성' }).click()
  await page.getByLabel('지금 불편한 점을 편하게 적어 주세요').fill(text)
  await page.getByRole('button', { name: '확인하기' }).click()
}

async function scenarioA(page) {
  await describe(page, '기침이 나고 열이 나요')
  await page.getByRole('button', { name: '다음' }).click()
  await page.getByRole('button', { name: '기침', exact: true }).click()
  await page.getByRole('button', { name: '없음' }).click()
  await page.getByRole('button', { name: '있음' }).click()
  await page.getByText('추가로 확인할 정보').waitFor()
}

async function scenarioB(page) {
  await describe(page, '그냥 몸이 좀 이상해요')
  await page.getByText('말씀하신 내용에서 확실하게 확인할 수 있는 항목을 찾지 못했어요.').waitFor()
  await page.getByRole('button', { name: '가장 불편한 증상 고르기' }).click()
  await page.getByTestId('initial-frequent').getByRole('button', { name: '기침', exact: true }).click()
  for (let i = 0; i < 3; i += 1) await page.getByRole('button', { name: '없음' }).click()
  await page.getByText('추가로 확인할 정보').waitFor()
}

const browser = await chromium.launch()
const results = []
for (const [name, run] of [['A', scenarioA], ['B', scenarioB]]) {
  for (const width of [390, 1280]) {
    const page = await browser.newPage({ viewport: { width, height: 900 } })
    const bodies = []
    page.on('request', (req) => { if (req.method() === 'POST') bodies.push({ url: req.url(), body: req.postData() }) })
    await page.goto(BASE)
    await run(page)
    const storage = await page.evaluate(() => JSON.stringify({ ...sessionStorage }))
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)
    await page.screenshot({ path: `${OUT}/ni_e2e_${name}_${width}.png`, fullPage: true })
    const textInStart = bodies.filter((b) => b.url.endsWith('/v1/session/start')).some((b) => b.body.includes('기침이 나고') || b.body.includes('이상해요'))
    results.push({ name, width, overflow, textInStart, storageHasText: storage.includes('기침이 나고') || storage.includes('이상해요') })
    await page.close()
  }
}
await browser.close()
console.log(JSON.stringify(results, null, 1))
if (results.some((r) => r.overflow || r.textInStart || r.storageHasText)) process.exit(1)
console.log('E2E_OK')
