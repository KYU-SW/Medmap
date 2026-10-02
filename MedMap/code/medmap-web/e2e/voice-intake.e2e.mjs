// 실서버 음성 스모크: API(:8000, 실제 Whisper) + vite(:5173) 가 떠 있어야 한다.
// Chromium 가짜 마이크(--use-file-for-fake-audio-capture)로 WAV 를 흘려보낸다. 설치 없이 캐시된 playwright 사용.
// 흐름: 말하기 → 그만 말하기 → transcript 가 입력칸에 들어감(자동 제출 없음) → [확인하기] → 확인 → initial → bootstrap → /start → IG 질문
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const { chromium } = require(process.env.PLAYWRIGHT_PATH ?? 'playwright')
const BASE = process.env.MEDMAP_WEB ?? 'http://127.0.0.1:5173'
const OUT = process.env.OUT_DIR ?? '../logs'
const WAV = process.env.VOICE_WAV ?? '../stt/samples/medmap_tts_test.wav'
const RECORD_MS = Number(process.env.RECORD_MS ?? 9000)

const browser = await chromium.launch({
  args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', `--use-file-for-fake-audio-capture=${WAV}%noloop`],
})
const context = await browser.newContext({ viewport: { width: 390, height: 900 }, permissions: ['microphone'] })
const page = await context.newPage()
const posts = []
page.on('request', (req) => { if (req.method() === 'POST') posts.push({ url: req.url(), type: req.headers()['content-type'] ?? '', body: req.postData() }) })

await page.goto(BASE)
await page.getByRole('button', { name: '시작하기' }).click()
await page.getByLabel('나이').fill('45')
await page.getByRole('button', { name: '남성' }).click()

await page.getByRole('button', { name: /말하기/ }).first().click()
await page.getByText('듣고 있어요').waitFor()
await page.waitForTimeout(RECORD_MS)
await page.getByRole('button', { name: '그만 말하기' }).click()

const textbox = page.getByLabel('지금 불편한 점을 편하게 적어 주세요')
await page.waitForFunction(() => (document.querySelector('textarea')?.value ?? '').length > 0, null, { timeout: 60000 })
const transcript = await textbox.inputValue()
const extractBeforeConfirm = posts.some((p) => p.url.endsWith('/v1/intake/extract'))
await page.screenshot({ path: `${OUT}/stt_e2e_transcript_390.png`, fullPage: true })

await page.getByRole('button', { name: '확인하기' }).click()
await page.getByRole('button', { name: '다음' }).click()
if (await page.getByText('이 중 지금 가장 불편한 증상은 무엇인가요?').isVisible().catch(() => false)) {
  await page.locator('section.panel .stack button').first().click()
}
for (let i = 0; i < 8; i += 1) {
  const q = page.getByTestId('bootstrap-question')
  if (!(await q.isVisible().catch(() => false))) break
  await page.getByRole('button', { name: '없음' }).click()
}
await page.getByText('추가로 확인할 정보').waitFor({ timeout: 30000 })
await page.screenshot({ path: `${OUT}/stt_e2e_ig_390.png`, fullPage: true })

const stt = posts.find((p) => p.url.endsWith('/v1/stt/transcribe'))
const extract = posts.find((p) => p.url.endsWith('/v1/intake/extract'))
const start = posts.find((p) => p.url.endsWith('/v1/session/start'))
const storage = await page.evaluate(() => JSON.stringify({ ...sessionStorage }))
const snippet = transcript.slice(0, 8)
const result = {
  transcript,
  stt_content_type: stt?.type ?? null,
  extract_before_confirm: extractBeforeConfirm,
  extract_has_transcript: Boolean(extract && extract.body.includes(snippet)),
  start_has_transcript: Boolean(start && start.body.includes(snippet)),
  storage_has_transcript: storage.includes(snippet),
  start_answers: start ? JSON.parse(start.body).answers.length : null,
}
await browser.close()
console.log(JSON.stringify(result, null, 1))
const ok = transcript.length > 0 && stt && !extractBeforeConfirm && result.extract_has_transcript
  && !result.start_has_transcript && !result.storage_has_transcript && result.start_answers === 3
if (!ok) process.exit(1)
console.log('VOICE_E2E_OK')
