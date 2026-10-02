// 실서버 스모크: API(:8000) + vite(:5173) 가 떠 있어야 한다. 설치 없이 캐시된 playwright 를 쓴다.
// flow-hardening 계약(docs/superpowers/plans/2026-09-26-medmap-flow-hardening.md) Task4 e2e 시나리오.
// 텍스트만(GPU 불필요): E(NEGATIVE E_91 재사용) · F(UNKNOWN 은 start 에 안 들어감) · F-INCOMPLETE(시작 안 됨)
// · F-RECOVER(P2-4: START_INCOMPLETE 후 입력 유지·새로고침 경고 → 답변 다시 확인하기 → exact-k3 → IG 질문)
// · RESUME(새로고침 후 같은 질문에서 이어감) · API-ERROR(1회 500 → 다시 시도 → 같은 요청 재전송)
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const { chromium } = require(process.env.PLAYWRIGHT_PATH ?? 'playwright')
const BASE = process.env.MEDMAP_WEB ?? 'http://127.0.0.1:5173'
const OUT = process.env.OUT_DIR ?? '../logs'

const START_INCOMPLETE_MESSAGE = '진료 질문을 시작하려면 몇 가지 정보를 더 확인해야 합니다.'

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
    await page.getByRole('button', { name: '없음' }).click()
  }
}

// consult(IG) 단계의 임의 질문에 답한다: YES_NO 는 '아니요', MULTI_CHOICE 는 첫 선택지 + '다음'.
async function answerAnyQuestion(page) {
  const no = page.getByRole('button', { name: '아니요', exact: true })
  if (await no.isVisible().catch(() => false)) {
    await no.click()
    return
  }
  await page.locator('.question__choices button').first().click()
  await page.getByRole('button', { name: '다음', exact: true }).click()
}

async function reachIg(page) {
  await describe(page, '그냥 몸이 좀 이상해요')
  await page.getByText('말씀하신 내용에서 확실하게 확인할 수 있는 항목을 찾지 못했어요.').waitFor()
  await page.getByRole('button', { name: '가장 불편한 증상 고르기' }).click()
  await page.getByTestId('initial-frequent').getByRole('button', { name: '기침', exact: true }).click()
  await fillBootstrapWithNo(page, 3)
  await page.getByText('추가로 확인할 정보').waitFor()
}

function startCallOf(posts) {
  const call = posts.find((p) => p.url.endsWith('/v1/session/start'))
  return call ? JSON.parse(call.body) : null
}

// E: "기침은 나는데 열은 없어요" → 확인 → (기침 1개뿐이라 자동 initial) → E_91(열) 은 확인된 NEGATIVE 로 재사용되어
// bootstrap 질문으로 다시 나오지 않는다. start 본문에 {question_id:'E_91', kind:'NEGATIVE'} 가 포함되고 answers 는 3개.
async function scenarioE(page, posts) {
  await describe(page, '기침은 나는데 열은 없어요')
  await page.getByRole('button', { name: '다음' }).click()
  const seenTexts = []
  for (let i = 0; i < 8; i += 1) {
    const q = page.getByTestId('bootstrap-question')
    if (!(await q.isVisible().catch(() => false))) break
    seenTexts.push((await q.innerText()).trim())
    await page.getByRole('button', { name: '없음' }).click()
  }
  await page.getByText('추가로 확인할 정보').waitFor()
  const body = startCallOf(posts)
  return {
    name: 'E',
    feverQuestionNeverShown: !seenTexts.some((t) => t.includes('열이 있나요')),
    hasE91Negative: Boolean(body?.answers?.some((a) => a.question_id === 'E_91' && a.kind === 'NEGATIVE')),
    answersLength3: body?.answers?.length === 3,
  }
}

// F: 후보 0 → 가장 불편한 증상 고르기 → 빈발 목록의 '기침'(정확히) → '잘 모르겠어요' 1회 → '없음' 으로 채움.
// UNKNOWN 은 start 본문에 들어가지 않고, E_91(잘 모르겠어요로 답한 항목) 도 들어가지 않는다.
async function scenarioF(page, posts) {
  await describe(page, '그냥 몸이 좀 이상해요')
  await page.getByText('말씀하신 내용에서 확실하게 확인할 수 있는 항목을 찾지 못했어요.').waitFor()
  await page.getByRole('button', { name: '가장 불편한 증상 고르기' }).click()
  await page.getByTestId('initial-frequent').getByRole('button', { name: '기침', exact: true }).click()
  await page.getByRole('button', { name: '잘 모르겠어요' }).click()
  await fillBootstrapWithNo(page, 8)
  await page.getByText('추가로 확인할 정보').waitFor()
  const body = startCallOf(posts)
  return {
    name: 'F',
    answersLength3: body?.answers?.length === 3,
    noUnknown: !body?.answers?.some((a) => a.kind === 'UNKNOWN'),
    noE91: !body?.answers?.some((a) => a.question_id === 'E_91'),
  }
}

// F-INCOMPLETE: '잘 모르겠어요' 를 계속 누르면(최대 6회) 남은 항목으로 3개를 채울 수 없어 START_INCOMPLETE 문구가 뜨고,
// /v1/session/start 는 호출되지 않는다.
async function scenarioFIncomplete(page, posts) {
  await describe(page, '그냥 몸이 좀 이상해요')
  await page.getByText('말씀하신 내용에서 확실하게 확인할 수 있는 항목을 찾지 못했어요.').waitFor()
  await page.getByRole('button', { name: '가장 불편한 증상 고르기' }).click()
  await page.getByTestId('initial-frequent').getByRole('button', { name: '기침', exact: true }).click()
  let reached = false
  for (let i = 0; i < 6; i += 1) {
    await page.getByRole('button', { name: '잘 모르겠어요' }).click()
    if (await page.getByText(START_INCOMPLETE_MESSAGE).isVisible().catch(() => false)) {
      reached = true
      break
    }
  }
  return { name: 'F-INCOMPLETE', reachedIncomplete: reached, noStartCall: !posts.some((p) => p.url.endsWith('/v1/session/start')) }
}

// F-RECOVER(P2-4): 기침(initial) → 잘 모르겠어요 3회 → START_INCOMPLETE(시작 안 됨, 입력·답 유지, 안내 표시)
// → 새로고침 시도 시 브라우저 기본 beforeunload 확인창(취소하면 그대로 남음) → [답변 다시 확인하기]
// → 열(E_91)만 없음으로 바꾸고 나머지는 그대로 → 남은 frozen 예비(E_175·E_88)를 없음으로 → /start 1회(exact-k3, UNKNOWN 없음)
// → IG 질문. start 후에는 안내가 사라지고 새로고침해도 확인창이 뜨지 않는다.
async function scenarioFRecover(page, posts) {
  const TEXT = '그냥 몸이 좀 이상해요'
  await describe(page, TEXT)
  await page.getByText('말씀하신 내용에서 확실하게 확인할 수 있는 항목을 찾지 못했어요.').waitFor()
  await page.getByRole('button', { name: '가장 불편한 증상 고르기' }).click()
  await page.getByTestId('initial-frequent').getByRole('button', { name: '기침', exact: true }).click()
  const asked = []
  for (let i = 0; i < 3; i += 1) {
    asked.push((await page.getByTestId('bootstrap-question').innerText()).trim())
    await page.getByRole('button', { name: '잘 모르겠어요' }).click()
  }
  await page.getByText(START_INCOMPLETE_MESSAGE).waitFor()
  const recap = await page.getByTestId('intake-recap').innerText()
  const keptAfterIncomplete = recap.includes(TEXT) && recap.includes('45세') && recap.includes('남성') && recap.includes('기침')
    && (recap.match(/잘 모르겠어요/g) ?? []).length === 3
  const noticeBefore = await page.getByTestId('prestart-notice').isVisible()
  const noStartYet = !posts.some((p) => p.url.endsWith('/v1/session/start'))

  // 실제 브라우저 새로고침 → beforeunload 기본 확인창 → 취소(dismiss)하면 입력이 그대로 남는다
  let dialogType = null
  page.once('dialog', async (dialog) => { dialogType = dialog.type(); await dialog.dismiss() })
  await page.reload({ timeout: 3000 }).catch(() => {})
  const reloadWarned = dialogType === 'beforeunload'
  const keptAfterCancel = (await page.getByTestId('intake-recap').innerText()).includes(TEXT)

  await page.getByRole('button', { name: '답변 다시 확인하기' }).click()
  const reviewed = []
  const reviewAnswers = ['없음', '잘 모르겠어요', '잘 모르겠어요']      // E_91 만 바꾸고 E_53·E_66 은 그대로
  for (const label of reviewAnswers) {
    reviewed.push((await page.getByTestId('bootstrap-question').innerText()).trim())
    await page.getByRole('button', { name: label }).click()
  }
  const continued = []
  for (let i = 0; i < 4; i += 1) {
    const q = page.getByTestId('bootstrap-question')
    if (!(await q.isVisible().catch(() => false))) break
    continued.push((await q.innerText()).trim())
    await page.getByRole('button', { name: '없음' }).click()
  }
  await page.getByText('추가로 확인할 정보').waitFor()
  const starts = posts.filter((p) => p.url.endsWith('/v1/session/start'))
  const body = starts[0] ? JSON.parse(starts[0].body) : null
  const noticeGone = !(await page.getByTestId('prestart-notice').isVisible().catch(() => false))

  let dialogAfterStart = null
  page.once('dialog', async (dialog) => { dialogAfterStart = dialog.type(); await dialog.dismiss() })
  await page.reload()
  await page.getByText('추가로 확인할 정보').waitFor()
  page.removeAllListeners('dialog')
  const storage = await page.evaluate(() => JSON.stringify({ ...sessionStorage, ...localStorage }))

  return {
    name: 'F-RECOVER',
    keptAfterIncomplete,
    noticeBefore,
    noStartYet,
    reloadWarned,
    keptAfterCancel,
    reviewSameOrder: reviewed.length === 3 && reviewed.every((t, i) => t.includes(asked[i].split('\n').pop())),
    continuedFrozenBackupOnly: continued.length === 2 && continued[0].includes('새로 생긴 피로감') && continued[1].includes('너무 피곤해서'),
    startOnce: starts.length === 1,
    exactK3: body?.answers?.length === 3,
    answers: body?.answers?.map((a) => `${a.question_id}:${a.kind}`),
    noUnknown: !body?.answers?.some((a) => a.kind === 'UNKNOWN'),
    noticeGone,
    noDialogAfterStart: dialogAfterStart === null,
    noRawTextInStorage: !storage.includes(TEXT),
  }
}

// RESUME: IG 도달 → 한 번 답하면 다음 질문이 나온다(이 질문 텍스트를 기록) → reload → 같은 질문에서 이어가고
// 진행률(1 / 3)도 그대로다 → 한 번 더 답하면 2 / 3 으로 넘어간다.
async function scenarioResume(page) {
  await reachIg(page)
  await answerAnyQuestion(page)
  await page.getByText('1 / 3', { exact: true }).waitFor()
  const pendingQuestion = (await page.getByTestId('question-live').innerText()).trim()
  await page.screenshot({ path: `${OUT}/flow_e2e_resume_before_390.png`, fullPage: true })

  await page.reload()
  await page.getByText('추가로 확인할 정보').waitFor()
  const pendingQuestionAfterReload = (await page.getByTestId('question-live').innerText()).trim()
  const headerStillOne = await page.getByText('1 / 3', { exact: true }).isVisible().catch(() => false)

  await answerAnyQuestion(page)
  await page.getByText('2 / 3', { exact: true }).waitFor()
  await page.screenshot({ path: `${OUT}/flow_e2e_resume_after_390.png`, fullPage: true })

  return { name: 'RESUME', sameQuestionAfterReload: pendingQuestionAfterReload === pendingQuestion, headerStillOne }
}

// API-ERROR: IG 도달 → /v1/session/answer 를 1회만 500 으로 가로채고 이후는 실제 서버로 통과시킨다 →
// 답하면 Notice(다시 시도) 가 뜬다 → 다시 시도 → 재전송 본문이 실패했던 요청과 같다 → 1 / 3, Notice 사라짐.
async function scenarioApiError(page) {
  await reachIg(page)
  const bodies = []
  let attempts = 0
  await page.route('**/v1/session/answer', async (route) => {
    bodies.push(route.request().postData())
    attempts += 1
    if (attempts === 1) {
      await route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ error: { code: 'INTERNAL_ERROR', message: 'boom' } }) })
    } else {
      await route.continue()
    }
  })
  await answerAnyQuestion(page)
  const retryButton = page.getByRole('button', { name: '다시 시도' })
  await retryButton.waitFor()
  await page.screenshot({ path: `${OUT}/flow_e2e_api_error_notice_390.png`, fullPage: true })
  await retryButton.click()
  await page.getByText('1 / 3', { exact: true }).waitFor()
  await page.screenshot({ path: `${OUT}/flow_e2e_api_error_recovered_390.png`, fullPage: true })
  const noticeGone = (await page.getByRole('alert').count()) === 0
  await page.unroute('**/v1/session/answer')

  return { name: 'API-ERROR', sameRetryBody: bodies.length === 2 && bodies[0] === bodies[1], noticeGone }
}

const browser = await chromium.launch()
const results = []

for (const [name, run] of [
  ['E', scenarioE],
  ['F', scenarioF],
  ['F-INCOMPLETE', scenarioFIncomplete],
  ['F-RECOVER', scenarioFRecover],
  ['RESUME', (page) => scenarioResume(page)],
  ['API-ERROR', (page) => scenarioApiError(page)],
]) {
  const context = await browser.newContext({ viewport: { width: 390, height: 900 } })
  const page = await context.newPage()
  const posts = []
  page.on('request', (req) => { if (req.method() === 'POST') posts.push({ url: req.url(), body: req.postData() }) })
  await page.goto(BASE)
  let result
  try {
    result = name === 'E' || name === 'F' || name === 'F-INCOMPLETE' || name === 'F-RECOVER' ? await run(page, posts) : await run(page)
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
  if (r.name === 'E') return r.feverQuestionNeverShown && r.hasE91Negative && r.answersLength3
  if (r.name === 'F') return r.answersLength3 && r.noUnknown && r.noE91
  if (r.name === 'F-INCOMPLETE') return r.reachedIncomplete && r.noStartCall
  if (r.name === 'F-RECOVER') {
    return r.keptAfterIncomplete && r.noticeBefore && r.noStartYet && r.reloadWarned && r.keptAfterCancel && r.reviewSameOrder
      && r.continuedFrozenBackupOnly && r.startOnce && r.exactK3 && r.noUnknown && r.noticeGone && r.noDialogAfterStart && r.noRawTextInStorage
  }
  if (r.name === 'RESUME') return r.sameQuestionAfterReload && r.headerStillOne
  if (r.name === 'API-ERROR') return r.sameRetryBody && r.noticeGone
  return false
}

if (!results.every(checksPassed)) process.exit(1)
console.log('FLOW_E2E_OK')
