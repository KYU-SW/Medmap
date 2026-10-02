// P2-7 demo 스모크: scripts/demo_serve.sh(기본 https://127.0.0.1:8443, 자체 서명)가 떠 있어야 한다.
// 확인: same-origin 으로 프론트·API 가 한 주소에서 뜨는지, 보안 컨텍스트라 마이크 API 가 열려 있는지,
// 텍스트 흐름이 IG 질문까지 가는지. 자체 서명 인증서라 이 스크립트에서만 인증서 오류를 무시한다. GPU 불필요.
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const { chromium } = require(process.env.PLAYWRIGHT_PATH ?? 'playwright')
const BASE = process.env.MEDMAP_DEMO ?? 'https://127.0.0.1:8443'
const OUT = process.env.OUT_DIR ?? '../logs'

const browser = await chromium.launch()
const context = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 390, height: 900 } })
const page = await context.newPage()
const requests = []
page.on('request', (req) => requests.push(req.url()))
await page.goto(BASE)
const env = await page.evaluate(() => ({
  secure: window.isSecureContext,
  protocol: location.protocol,
  mic: Boolean(navigator.mediaDevices?.getUserMedia),
  recorder: typeof MediaRecorder === 'function',
}))
await page.getByRole('button', { name: '시작하기' }).click()
await page.getByLabel('나이').fill('45')
await page.getByRole('button', { name: '남성' }).click()
await page.getByLabel('지금 불편한 점을 편하게 적어 주세요').fill('그냥 몸이 좀 이상해요')
await page.getByRole('button', { name: '확인하기' }).click()
await page.getByText('말씀하신 내용에서 확실하게 확인할 수 있는 항목을 찾지 못했어요.').waitFor()
await page.getByRole('button', { name: '가장 불편한 증상 고르기' }).click()
await page.getByTestId('initial-frequent').getByRole('button', { name: '기침', exact: true }).click()
for (let i = 0; i < 3; i += 1) await page.getByRole('button', { name: '없음' }).click()
await page.getByText('추가로 확인할 정보').waitFor()
await page.screenshot({ path: `${OUT}/demo_https_ig.png`, fullPage: true })
const origin = new URL(BASE).origin
const result = {
  ...env,
  sameOrigin: requests.filter((u) => u.includes('/v1/') || u.endsWith('/health')).every((u) => u.startsWith(origin)),
  apiCalls: requests.filter((u) => u.includes('/v1/')).length,
}
await browser.close()
console.log(JSON.stringify(result, null, 1))
if (!(result.secure && result.protocol === 'https:' && result.mic && result.recorder && result.sameOrigin && result.apiCalls >= 2)) process.exit(1)
console.log('DEMO_HTTPS_E2E_OK')
