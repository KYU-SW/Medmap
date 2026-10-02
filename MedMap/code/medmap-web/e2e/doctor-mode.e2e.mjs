// 실서버 Doctor Mode 스모크(텍스트만, GPU 불필요). dist 를 서빙하는 API 가 떠 있어야 한다:
//   MEDMAP_SERVE_WEB_DIST=medmap-web/dist uvicorn medmap.api:app --port 8010  →  MEDMAP_WEB=http://127.0.0.1:8010
// 계약: docs/superpowers/specs/2026-09-29-medmap-doctor-mode-foundation.md (rev4)
// HIT: #/handoff intake(자동 적용 없음, cache 보존) → #/doctor blind → 건너뛰기 → 후보 5/8 → IG 질문 1 답
//      → IG 가 cache 항목(E_53)을 고르면 "환자가 이미 말한 내용" 표시, 의사 확인 후에만 제출 → 한도 3 도달
//      (경로는 2026-09-30 API 탐색으로 찾은 고정 입력: 텍스트·initial E_148·첫 답 아니요)
// WD: 목록 검색 선택 · 목록 밖 직접 입력 · 입력 후 후보 유지
import { createRequire } from 'node:module'
import { writeFileSync } from 'node:fs'

const require = createRequire(import.meta.url)
const { chromium } = require(process.env.PLAYWRIGHT_PATH ?? 'playwright')
const BASE = process.env.MEDMAP_WEB ?? 'http://127.0.0.1:8010'
const OUT = process.env.OUT_DIR ?? '../logs'
const HIT_TEXT = '다리가 붓고 숨이 차고 기침이 나고 가슴이 아프고 피를 토했어요'
const SIMPLE_TEXT = '기침이 나고 열이 나요'
// 영어 노출 규칙은 english-audit.e2e.mjs 와 동일(허용: MedMap·병기 약어). 그 파일은 수정하지 않고 여기서 같은 규칙을 적용한다.
const ALLOWED_EN = new Set(['MedMap', 'HIV', 'BMI', 'cm', 'COPD', 'NSAID', 'NOAC', 'ST', 'OSA'])
const english = []
async function captureEnglish(page, stage) {
  const text = await page.evaluate(() => {
    const attrs = [...document.querySelectorAll('[aria-label],[placeholder],[title],[alt],input,textarea')]
      .flatMap((el) => [el.getAttribute('aria-label'), el.getAttribute('placeholder'), el.getAttribute('title'),
        el.getAttribute('alt'), el.value]).filter(Boolean)
    return [document.body.innerText, ...attrs].join('\n')
  })
  for (const line of text.split('\n')) {
    for (const word of line.match(/[A-Za-z]+/g) ?? []) {
      if (!ALLOWED_EN.has(word)) english.push({ stage, word, line: line.trim().slice(0, 160) })
    }
  }
}
const FORBIDDEN = ['오진', '틀렸', '틀린 진단', '확실합니다', '최종 진단', '확정 진단', '불일치', '진단 오류', '예방합니다', '진단했습니다']

function check(cond, message) {
  if (!cond) throw new Error(`CHECK_FAILED: ${message}`)
}

async function describe(page, text) {
  await page.getByRole('button', { name: '시작하기' }).click()
  await page.getByLabel('나이').fill('45')
  await page.getByRole('button', { name: '남성' }).click()
  await page.getByLabel('지금 불편한 점을 편하게 적어 주세요').fill(text)
  await page.getByRole('button', { name: '확인하기' }).click()
}

async function counter(page) {
  return (await page.getByTestId('doctor-next-counter').innerText()).trim()
}

// YES_NO 는 '아니요', 그 외는 두 번째 선택지(+ 여러 개 고르기면 '다음'). 요청이 끝나 카운터가 바뀔 때까지 기다린다.
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

async function common(page) {
  const text = await page.evaluate(() => document.body.innerText)
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)
  return { percent: /%/.test(text), forbidden: FORBIDDEN.filter((w) => text.includes(w)), overflow }
}

async function scenarioHit(page, log) {
  await page.goto(`${BASE}/#/handoff`)
  await describe(page, HIT_TEXT)
  await page.getByRole('button', { name: '다음' }).click()
  await page.getByRole('button', { name: '메스꺼움·구역질', exact: true }).click()
  await page.getByTestId('handoff-done').waitFor()
  await captureEnglish(page, 'handoff-done')
  const handoff = await page.evaluate(() => ({ ...sessionStorage }))
  check(!('medmap.session' in handoff) && !('medmap.intakeCache' in handoff), 'handoff wrote patient keys')
  check(JSON.parse(handoff['medmap.handoff.cache']).some((e) => e.evidence_id === 'E_53'), 'E_53 not kept in handoff cache')
  check(log.filter((r) => r.url.endsWith('/v1/session/answer')).length === 0, 'handoff auto-applied an answer')

  await page.getByRole('link', { name: '의사 화면 열기' }).click()
  await page.getByText('환자 요약').waitFor()
  const firstView = log.find((r) => r.url.endsWith('/v1/doctor/view'))
  check(firstView && JSON.parse(firstView.response).independent_assessment.status === 'LOCKED', 'first view not LOCKED')
  check(await page.getByTestId('doctor-candidates').count() === 0, 'candidates visible before WD')
  check(await page.getByTestId('doctor-next').count() === 0, 'question visible before WD')
  await captureEnglish(page, 'doctor-pending')
  // Phase 2a: start 에 못 들어간 환자 확인 소견(cache, E_53 포함)이 IG 선택과 무관하게 환자 요약에 보인다(표시만)
  const unapplied = page.getByTestId('doctor-findings-unapplied')
  check(await unapplied.count() === 1, 'unapplied confirmed findings not shown')
  check((await unapplied.innerText()).includes('이번에 진료를 받으려는 이유와 관련해서 어딘가 통증이 있나요?'), 'cached E_53 not listed')
  check(log.filter((r) => r.url.endsWith('/v1/doctor/answer')).length === 0, 'showing cache submitted an answer')

  await page.getByRole('button', { name: '건너뛰기' }).click()
  const cands = page.getByTestId('doctor-candidates')
  await cands.waitFor()
  check(await cands.getByRole('listitem').count() === 5, 'default candidates != 5')
  await cands.getByRole('button', { name: '더 보기' }).click()
  check(await cands.getByRole('listitem').count() === 8, 'expanded candidates != 8')
  await captureEnglish(page, 'doctor-q1')

  check(await counter(page) === '질문 0 / 3', `counter start ${await counter(page)}`)
  check(await page.getByTestId('doctor-patient-said').count() === 0, 'patient-said on first question')
  await answerCurrent(page)
  const said = page.getByTestId('doctor-patient-said')
  await said.waitFor()
  check((await said.innerText()).includes('환자가 이미 말한 내용: 예'), 'patient-said text')
  await captureEnglish(page, 'doctor-q2-patient-said')
  const answersBefore = log.filter((r) => r.url.endsWith('/v1/doctor/answer')).length
  check(answersBefore === 1, `auto-submitted cache answer (${answersBefore})`)
  await said.getByRole('button', { name: '이 답으로 확인' }).click()
  await page.waitForFunction(() => document.querySelector('[data-testid="doctor-next-counter"]')?.textContent.includes('2 / 3'))
  const confirmed = JSON.parse(log.filter((r) => r.url.endsWith('/v1/doctor/answer'))[1].body).submission
  check(confirmed.question_id === 'E_53' && confirmed.answer.kind === 'POSITIVE', 'confirmed submission')
  await answerCurrent(page)
  await page.getByText('추가 질문 한도에 도달했습니다', { exact: false }).waitFor()
  await captureEnglish(page, 'doctor-budget')
  const after = await page.evaluate(() => ({ ...sessionStorage }))
  check(after['medmap.handoff.session'] === handoff['medmap.handoff.session'], 'handoff session changed')
  check(after['medmap.handoff.cache'] === handoff['medmap.handoff.cache'], 'handoff cache changed')
  check(JSON.parse(after['medmap.doctor.cache']).every((e) => e.evidence_id !== 'E_53'), 'doctor cache still has E_53')
  check(!((await page.getByTestId('doctor-findings-unapplied').innerText().catch(() => '')).includes('이번에 진료를 받으려는 이유와 관련해서 어딘가 통증이 있나요?')), 'E_53 still listed as unapplied after doctor confirmed')
  return { answers: log.filter((r) => r.url.endsWith('/v1/doctor/answer')).length }
}

async function scenarioWd(page) {
  await page.goto(`${BASE}/#/handoff`)
  await describe(page, SIMPLE_TEXT)
  await page.getByRole('button', { name: '다음' }).click()
  await page.getByRole('button', { name: '기침', exact: true }).click()
  await page.getByRole('button', { name: '없음' }).click()
  await page.getByRole('button', { name: '있음' }).click()
  await page.getByTestId('handoff-done').waitFor()
  await page.getByRole('link', { name: '의사 화면 열기' }).click()
  await page.getByLabel('진단 검색(모델이 아는 49개 질환)').fill('기관지')
  await captureEnglish(page, 'doctor-wd-search')
  await page.getByRole('button', { name: '기관지염', exact: true }).click()
  await page.getByTestId('doctor-candidates').waitFor()
  check((await page.getByTestId('doctor-wd-value').innerText()).includes('기관지염'), 'catalog WD')
  await page.getByRole('button', { name: '진단 바꾸기' }).click()
  await page.getByLabel('목록에 없는 진단 직접 입력').fill('급성 충수염')
  await page.getByRole('button', { name: '직접 입력' }).click()
  await page.getByText('모델 지원 범위 밖이라 비교하지 않습니다.').waitFor()
  check(await page.getByTestId('doctor-candidates').count() === 1, 'candidates hidden after WD change')
  await captureEnglish(page, 'doctor-wd-out-of-scope')
  return {}
}

// 캐시된 playwright 가 설치된 브라우저보다 새 버전이면 CHROMIUM_PATH 로 기존 브라우저를 지정한다(다운로드 없음).
const browser = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {})
const results = []
let failed = false
for (const [name, run] of [['HIT', scenarioHit], ['WD', scenarioWd]]) {
  for (const width of [390, 1280]) {
    const page = await browser.newPage({ viewport: { width, height: 900 } })
    const log = []
    page.on('response', async (res) => {
      const req = res.request()
      if (req.method() !== 'POST') return
      log.push({ url: req.url(), body: req.postData(), response: await res.text().catch(() => '') })
    })
    const row = { name, width }
    try {
      Object.assign(row, await run(page, log), await common(page), { ok: true })
      if (row.percent || row.forbidden.length || row.overflow) { row.ok = false; failed = true }
    } catch (error) {
      Object.assign(row, { ok: false, error: String(error.message ?? error).slice(0, 300) })
      failed = true
    }
    await page.screenshot({ path: `${OUT}/doctor_e2e_${name}_${width}.png`, fullPage: true })
    results.push(row)
    await page.close()
  }
}
await browser.close()
// 검색 목록 전체(49개 표시명)도 같은 규칙으로 검사한다.
const listed = await (await fetch(`${BASE}/v1/doctor/diagnoses`)).json()
for (const d of listed.diagnoses) {
  for (const word of d.label_ko.match(/[A-Za-z]+/g) ?? []) if (!ALLOWED_EN.has(word)) english.push({ stage: 'diagnoses-list', word, line: d.label_ko })
}
writeFileSync(`${OUT}/doctor_mode_e2e.json`, JSON.stringify({ results, english }, null, 1))
console.log(JSON.stringify(results, null, 1))
console.log(`USER_VISIBLE_ENGLISH=${english.length}`, english.slice(0, 10))
if (failed || english.length) process.exit(1)
console.log('DOCTOR_E2E_OK')
