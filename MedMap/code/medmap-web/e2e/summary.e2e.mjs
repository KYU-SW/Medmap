// 실서버 스모크: API(:8000) + vite(:5173) 가 떠 있어야 한다. 설치 없이 캐시된 playwright 를 쓴다.
// Clinical Summary UI 계약(docs/superpowers/plans/2026-09-27-medmap-clinical-summary-ui.md) E2E.
// 텍스트만(GPU 불필요): NORMAL(요약 도달 + 답한 항목 목록) · RELOAD-FROM-SUMMARY(같은 요약 복원)
// · RELOAD-MID-CONSULT(상담 중 새로고침 → resume → 끝까지 → 요약) · SUMMARY-API-ERROR(1회 500 → 세션 유지 → 다시 시도 → 요약)
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

// bootstrap 질문이 보이는 동안 '없음' 을 눌러 채운다(최대 max 회, 무한루프 방지).
async function fillBootstrapWithNo(page, max = 8) {
  for (let i = 0; i < max; i += 1) {
    const q = page.getByTestId('bootstrap-question')
    if (!(await q.isVisible().catch(() => false))) break
    await page.getByRole('button', { name: '없음', exact: true }).click()
  }
}

// consult(IG) 단계의 임의 질문에 답한다: YES_NO 는 '아니요', MULTI_CHOICE 는 첫 선택지 + '다음'.
// 답을 누른 뒤에는 요청이 끝나 질문이 바뀌거나(또는 요약이 뜰 때까지) 기다린다 — 처리 중(disabled) 버튼을 다시 누르지 않는다.
async function answerAnyQuestion(page) {
  const before = await page.locator('.question__text').innerText()
  const no = page.getByRole('button', { name: '아니요', exact: true })
  if (await no.isEnabled().catch(() => false)) {
    await no.click()
  } else {
    await page.locator('.question__choices button').first().click()
    await page.getByRole('button', { name: '다음', exact: true }).click()
  }
  await page.waitForFunction((prev) => {
    const q = document.querySelector('.question__text')
    const done = [...document.querySelectorAll('h1')].some((h) => h.textContent.includes('현재까지 확인된 정보'))
    return done || (q && q.textContent !== prev && !q.closest('section')?.querySelector('button.choice[disabled]'))
  }, before, { timeout: 30000 })
}

async function reachIg(page) {
  await describe(page, '그냥 몸이 좀 이상해요')
  await page.getByText('말씀하신 내용에서 확실하게 확인할 수 있는 항목을 찾지 못했어요.').waitFor()
  await page.getByRole('button', { name: '가장 불편한 증상 고르기' }).click()
  await page.getByTestId('initial-frequent').getByRole('button', { name: '기침', exact: true }).click()
  await fillBootstrapWithNo(page, 3)
  await page.getByText('추가로 확인할 정보').waitFor()
}

// IG 질문에 계속 답해 요약 화면(현재까지 확인된 정보)에 닿을 때까지 진행한다(최대 max 회, 무한루프 방지).
async function answerUntilSummary(page, max = 6) {
  for (let i = 0; i < max; i += 1) {
    if (await page.getByText('현재까지 확인된 정보').isVisible().catch(() => false)) return
    await answerAnyQuestion(page)
  }
  await page.getByText('현재까지 확인된 정보').waitFor()
}

async function reachSummary(page) {
  await reachIg(page)
  await answerUntilSummary(page)
  await page.getByText(/답한 질문 \d+개/).waitFor()
}

// NORMAL: 텍스트 → bootstrap → IG 3문 → 요약. 주 증상·확인 목록·"답한 질문 N개" 가 보인다.
async function scenarioNormal(page) {
  await reachSummary(page)
  const hasChief = await page.getByRole('heading', { name: '주 증상', exact: true }).isVisible().catch(() => false)
  const answeredCountText = (await page.getByText(/답한 질문 \d+개/).innerText()).trim()
  await page.screenshot({ path: `${OUT}/summary_e2e_normal_390.png`, fullPage: true })
  return { name: 'NORMAL', hasChief, answeredCountText, noCandidates: (await page.getByText('현재 확인이 필요한 진단 후보').count()) === 0 && !/\d+(\.\d+)?\s*%/.test(await page.locator('main').innerText()) }
}

// RELOAD-FROM-SUMMARY: 요약 화면에서 reload 해도 같은 세션으로 같은 요약이 복원된다(섹션 전체 텍스트 동일).
async function scenarioReloadFromSummary(page) {
  await reachSummary(page)
  const before = (await page.locator('.summary').innerText()).trim()

  await page.reload()
  await page.getByText('현재까지 확인된 정보').waitFor()
  await page.getByText(/답한 질문 \d+개/).waitFor()
  const after = (await page.locator('.summary').innerText()).trim()
  await page.screenshot({ path: `${OUT}/summary_e2e_reload_390.png`, fullPage: true })

  return { name: 'RELOAD-FROM-SUMMARY', sameSectionText: before === after }
}

// RELOAD-MID-CONSULT: 상담 중 reload → resume 으로 이어감 → 끝까지 답하면 요약이 정상적으로 뜬다.
async function scenarioReloadMidConsult(page) {
  await reachIg(page)
  await answerAnyQuestion(page)
  await page.getByText('1 / 3', { exact: true }).waitFor()

  await page.reload()
  await page.getByText('추가로 확인할 정보').waitFor()
  const headerStillOne = await page.getByText('1 / 3', { exact: true }).isVisible().catch(() => false)

  await answerUntilSummary(page)
  const summaryOk = await page.getByText(/답한 질문 \d+개/).isVisible().catch(() => false)
  await page.screenshot({ path: `${OUT}/summary_e2e_reload_mid_consult_390.png`, fullPage: true })

  return { name: 'RELOAD-MID-CONSULT', headerStillOne, summaryOk }
}

// SUMMARY-API-ERROR: /v1/session/summary 를 1회만 500 으로 가로챈다 → 오류 문구 + 세션은 sessionStorage 에 남는다
// → [다시 시도] → 요약이 정상적으로 뜬다.
async function scenarioSummaryApiError(page) {
  await reachIg(page)
  let attempts = 0
  await page.route('**/v1/session/summary', async (route) => {
    attempts += 1
    if (attempts === 1) {
      await route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ error: { code: 'INTERNAL_ERROR', message: 'boom' } }) })
    } else {
      await route.continue()
    }
  })
  await answerUntilSummary(page)
  await page.getByRole('alert').getByText('요약 정보를 불러오지 못했습니다.').waitFor()
  const sessionDuringError = await page.evaluate(() => sessionStorage.getItem('medmap.session') !== null)
  await page.screenshot({ path: `${OUT}/summary_e2e_api_error_390.png`, fullPage: true })

  await page.getByRole('button', { name: '다시 시도' }).click()
  await page.getByText(/답한 질문 \d+개/).waitFor()
  const noticeGone = (await page.getByRole('alert').count()) === 0
  await page.unroute('**/v1/session/summary')
  await page.screenshot({ path: `${OUT}/summary_e2e_api_error_recovered_390.png`, fullPage: true })

  return { name: 'SUMMARY-API-ERROR', sessionDuringError, noticeGone, retried: attempts >= 2 }
}

const browser = await chromium.launch()
const results = []

for (const [name, run] of [
  ['NORMAL', scenarioNormal],
  ['RELOAD-FROM-SUMMARY', scenarioReloadFromSummary],
  ['RELOAD-MID-CONSULT', scenarioReloadMidConsult],
  ['SUMMARY-API-ERROR', scenarioSummaryApiError],
]) {
  const context = await browser.newContext({ viewport: { width: 390, height: 900 } })
  const page = await context.newPage()
  await page.goto(BASE)
  let result
  try {
    result = await run(page)
  } catch (err) {
    result = { name, error: String(err) }
  }
  results.push(result)
  await context.close()
}

await browser.close()
console.log(JSON.stringify(results, null, 1))

function checksPassed(r) {
  if (r.error) return false
  if (r.name === 'NORMAL') return r.hasChief && /답한 질문 \d+개/.test(r.answeredCountText) && r.noCandidates
  if (r.name === 'RELOAD-FROM-SUMMARY') return r.sameSectionText
  if (r.name === 'RELOAD-MID-CONSULT') return r.headerStillOne && r.summaryOk
  if (r.name === 'SUMMARY-API-ERROR') return r.sessionDuringError && r.noticeGone && r.retried
  return false
}

if (!results.every(checksPassed)) process.exit(1)
console.log('SUMMARY_E2E_OK')
