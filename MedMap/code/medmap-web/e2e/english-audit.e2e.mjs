// C Korean terminology — 실제 제품 화면 영어 노출 감사. API(:8000) + 웹(MEDMAP_WEB)이 떠 있어야 한다. GPU 불필요.
// 고정 seed 로 여러 경로(자연어 후보·initial 선택/검색·bootstrap·IG·후보·요약)를 끝까지 진행하며 화면에 보이는 문자열을
// 단계마다 모아 영문 단어를 찾는다. 다지선다는 '전체 보기'까지 펼쳐 모든 값을 본다. 390px·1280px.
// 허용: 제품명 MedMap, 한국어 문장 안의 병기 약어(HIV·BMI·cm·COPD·NSAID·NOAC·ST·OSA). 그 외 영문 단어 = 노출.
import { createRequire } from 'node:module'
import { writeFileSync } from 'node:fs'

const require = createRequire(import.meta.url)
const { chromium } = require(process.env.PLAYWRIGHT_PATH ?? 'playwright')
const BASE = process.env.MEDMAP_WEB ?? 'http://127.0.0.1:5173'
const OUT = process.env.OUT_DIR ?? '../logs'
const WALKS = Number(process.env.WALKS ?? 12)
const ALLOWED = new Set(['MedMap', 'HIV', 'BMI', 'cm', 'COPD', 'NSAID', 'NOAC', 'ST', 'OSA'])

function rng(seed) {
  let s = seed >>> 0
  return () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 2 ** 32 }
}

const findings = []            // { walk, width, stage, word, line }
const stagesSeen = new Set()
const questionsSeen = new Set()

async function capture(page, ctx, stage) {
  stagesSeen.add(stage)
  // 보이는 텍스트 + 보조기술·입력에 노출되는 속성(aria-label·placeholder·title·alt·입력값)
  const text = await page.evaluate(() => {
    const attrs = [...document.querySelectorAll('[aria-label],[placeholder],[title],[alt],input,textarea')]
      .flatMap((el) => [el.getAttribute('aria-label'), el.getAttribute('placeholder'), el.getAttribute('title'),
        el.getAttribute('alt'), el.value]).filter(Boolean)
    return [document.body.innerText, ...attrs].join('\n')
  })
  for (const line of text.split('\n')) {
    for (const word of line.match(/[A-Za-z]+/g) ?? []) {
      if (!ALLOWED.has(word)) findings.push({ ...ctx, stage, word, line: line.trim().slice(0, 160) })
    }
  }
}

async function start(page, ctx, text) {
  await page.goto(BASE)
  await page.getByRole('button', { name: '시작하기' }).click()
  await page.getByLabel('나이').fill('45')
  await page.getByRole('button', { name: ctx.walk % 2 ? '여성' : '남성' }).click()
  await page.getByLabel('지금 불편한 점을 편하게 적어 주세요').fill(text)
  await capture(page, ctx, 'A-describe')
  await page.getByRole('button', { name: '확인하기' }).click()
}

async function answerIg(page, ctx, rand) {
  for (let i = 0; i < 6; i += 1) {
    if (await page.getByText('현재까지 확인된 정보').isVisible().catch(() => false)) return
    const q = page.locator('.question__text')
    await q.waitFor()
    const more = page.locator('.question__more')
    if (await more.isVisible().catch(() => false)) await more.click()
    questionsSeen.add((await q.innerText()).trim())
    await capture(page, ctx, 'D-IG+E-candidates')
    const before = await q.innerText()
    const next = page.getByRole('button', { name: '다음', exact: true })
    const choices = page.locator('.question__choices button')
    const n = await choices.count()
    await choices.nth(Math.floor(rand() * n)).click()
    if (await next.isVisible().catch(() => false)) {
      if (await next.isDisabled()) await choices.first().click()
      await next.click()
    }
    await page.waitForFunction((prev) => {
      const done = [...document.querySelectorAll('h1')].some((h) => h.textContent.includes('현재까지 확인된 정보'))
      const cur = document.querySelector('.question__text')
      return done || (cur && cur.textContent !== prev)
    }, before, { timeout: 30000 })
  }
}

async function walk(page, ctx) {
  const rand = rng(1000 + ctx.walk)
  const viaMapper = ctx.walk % 3 === 0
  if (viaMapper) {
    await start(page, ctx, ['기침이 나고 열이 나요. 가래도 있고 숨이 차요.', '배가 아프고 설사를 했어요. 열은 없어요.',
      '가슴이 답답하고 어지러워요. 식은땀이 나요.', '목이 아프고 콧물이 나요.'][ctx.walk % 4])
    // extract 응답을 기다린다(isVisible 은 timeout 을 기다리지 않는다): 후보 확인 화면 또는 후보 0 안내
    const next = page.getByRole('button', { name: '다음' })
    const none = page.getByRole('button', { name: '가장 불편한 증상 고르기' })
    await next.or(none).first().waitFor({ timeout: 20000 })
    if (await next.isVisible()) {
      await capture(page, ctx, 'A-candidates')
      await next.click()
    } else {
      await none.click()
    }
    if (await page.getByText('이 중 지금 가장 불편한 증상은 무엇인가요?').isVisible().catch(() => false)) {
      await capture(page, ctx, 'B-initial-choose')
      await page.locator('section.panel .stack button').first().click()
    } else if (await page.getByTestId('initial-frequent').isVisible().catch(() => false)) {
      await capture(page, ctx, 'B-initial-picker')
      await page.getByTestId('initial-frequent').getByRole('button').first().click()
    }
  } else {
    await start(page, ctx, '그냥 몸이 좀 이상해요')
    await page.getByRole('button', { name: '가장 불편한 증상 고르기' }).click()
    await capture(page, ctx, 'B-initial-picker')
    const search = page.getByLabel('증상 찾기')
    await search.fill('퀘퀘퀘')          // 결과 없는 검색어(감사 입력값 자체가 영어로 잡히지 않도록 한글)
    await capture(page, ctx, 'H-search-empty')
    await search.fill(['배', '가슴', '머리', '목', '피부', '숨'][ctx.walk % 6])
    await capture(page, ctx, 'H-search-results')
    const results = page.getByTestId('initial-results').getByRole('button')
    const count = await results.count()
    if (count > 0 && ctx.walk % 2 === 0) {
      await results.nth(ctx.walk % count).click()
    } else {
      await search.fill('')
      const frequent = page.getByTestId('initial-frequent').getByRole('button')
      await frequent.nth(ctx.walk % (await frequent.count())).click()
    }
  }
  for (let i = 0; i < 6; i += 1) {
    const bq = page.getByTestId('bootstrap-question')
    if (!(await bq.isVisible().catch(() => false))) break
    await capture(page, ctx, 'C-bootstrap')
    await page.getByRole('button', { name: rand() < 0.5 ? '있음' : '없음', exact: true }).click()
  }
  await page.getByText(/추가로 확인할 정보|현재까지 확인된 정보/).first().waitFor({ timeout: 30000 })
  await answerIg(page, ctx, rand)
  await page.getByText(/답한 질문 \d+개/).waitFor({ timeout: 30000 })
  await capture(page, ctx, 'F-summary')
  if (ctx.walk < 2) await page.screenshot({ path: `${OUT}/english_audit_summary_${ctx.width}_${ctx.walk}.png`, fullPage: true })
}

const browser = await chromium.launch()
const errors = []
for (const width of [390, 1280]) {
  for (let w = 0; w < WALKS; w += 1) {
    const context = await browser.newContext({ viewport: { width, height: 900 } })
    const page = await context.newPage()
    try {
      await walk(page, { walk: w, width })
    } catch (err) {
      errors.push({ width, walk: w, error: String(err).slice(0, 300) })
      await page.screenshot({ path: `${OUT}/english_audit_error_${width}_${w}.png`, fullPage: true }).catch(() => {})
    }
    await context.close()
  }
}
await browser.close()

const unique = new Map()
for (const f of findings) {
  const key = `${f.word}|${f.line}`
  if (!unique.has(key)) unique.set(key, { ...f, count: 0 })
  unique.get(key).count += 1
}
const report = { walks: WALKS * 2, stages: [...stagesSeen].sort(), distinctQuestions: questionsSeen.size,
  userVisibleEnglish: unique.size, findings: [...unique.values()], errors }
writeFileSync(`${OUT}/english_audit.json`, JSON.stringify(report, null, 1))
console.log(JSON.stringify({ ...report, findings: report.findings.slice(0, 30) }, null, 1))
if (errors.length || unique.size) process.exit(1)
console.log('ENGLISH_AUDIT_OK USER_VISIBLE_ENGLISH=0')
