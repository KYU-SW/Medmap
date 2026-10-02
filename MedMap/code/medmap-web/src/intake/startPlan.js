// Natural Intake → exact-k3 시작 규칙(STEP17A GO 범위 그대로. 순서·예비 변경 금지).
// start feature = 확인된 POSITIVE(initial·additional) + bootstrap 의 known 답(POSITIVE/NEGATIVE)뿐.
// 확인된 NEGATIVE·초과 POSITIVE 는 cache, bootstrap UNKNOWN 은 기록만 하고 start 에 넣지 않는다.
// rev3: 확인된 NEGATIVE 가 frozen bootstrap/backup 순서에 있고 walk 가 실제로 그 항목에 도달하면
// 다시 묻지 않고 그 NEGATIVE 를 bootstrap 답으로 재사용한다(known 1개로 세고 start 에 보내고 cache 에서 뺀다).
// walk 가 도달하기 전에 need 가 이미 채워지면(또는 frozen 목록 밖이면) 그 NEGATIVE 는 그대로 cache 에 남는다.
import { INITIAL_IDS } from './catalog.js'
import { questionText } from '../terminology/labels.js'

export const K = 3
export const START_INCOMPLETE = 'START_INCOMPLETE'
export const BOOTSTRAP_PRIMARY = Object.freeze(['E_91', 'E_53', 'E_66'])
export const BOOTSTRAP_BACKUP = Object.freeze(['E_201', 'E_175', 'E_88'])
// 문구는 한국어 용어 정본(medmap/data/terminology_ko.json → generated)에서 가져온다 — 여기서 따로 관리하지 않는다.
export const BOOTSTRAP_QUESTIONS_KO = Object.freeze(Object.fromEntries(
  [...BOOTSTRAP_PRIMARY, ...BOOTSTRAP_BACKUP].map((id) => [id, questionText(id)]),
))
const KNOWN = new Set(['POSITIVE', 'NEGATIVE'])

/** 확인된 항목 중 initial 이 될 수 있는 것: POSITIVE ∧ initial 96개. NEGATIVE·과거력은 제외. */
export function initialOptions(confirmed) {
  return confirmed.filter((c) => c.status === 'POSITIVE' && INITIAL_IDS.has(c.evidence_id))
}

/** additional = initial 제외 확인 POSITIVE 를 발화(매퍼 출력) 순서로 앞 K개. 나머지(초과 POSITIVE·모든 NEGATIVE)는 cache 후보 — frozen walk 가 도달해 재사용된 NEGATIVE 는 buildStartRequest 에서 cache 에서 제외된다(rev3). */
export function splitConfirmed(confirmed, initialId) {
  const seen = new Set()
  const deduped = confirmed.filter((c) => {
    if (seen.has(c.evidence_id)) return false
    seen.add(c.evidence_id)
    return true
  })
  const additional = deduped.filter((c) => c.evidence_id !== initialId && c.status === 'POSITIVE').slice(0, K)
  const used = new Set(additional.map((c) => c.evidence_id))
  const cached = deduped.filter((c) => c.evidence_id !== initialId && !used.has(c.evidence_id))
  return { additional, cached }
}

/** frozen 순서에서 initial 과 확인된 POSITIVE 를 뺀 bootstrap 후보. 확인된 NEGATIVE 는 남아서
 * walk 가 실제로 도달하면 재사용 대상이 된다(rev3). 같은 질문을 다시 묻지는 않는다. */
export function bootstrapSequence(initialId, confirmed) {
  const excluded = new Set([initialId, ...confirmed.filter((c) => c.status === 'POSITIVE').map((c) => c.evidence_id)])
  return [...BOOTSTRAP_PRIMARY, ...BOOTSTRAP_BACKUP].filter((id) => !excluded.has(id))
}

function isConfirmedNegative(id, confirmed) {
  return confirmed.some((c) => c.evidence_id === id && c.status === 'NEGATIVE')
}

/**
 * frozen 순서를 실제로 걸으며 확정 답을 만든다(rev3).
 * - 확인된 NEGATIVE 항목에 도달하면 다시 묻지 않고 재사용(entry.reused=true)한다.
 * - 그 외에는 다음 미소비 response(질문 순서를 지켜야 함, 아니면 BOOTSTRAP_MISMATCH)를 소비하거나,
 *   없으면 그 항목을 다음 질문으로 ASK 한다(단, 남은 항목 수로 채울 수 없으면 START_INCOMPLETE).
 * - responses 에는 실제로 물어본(ASKED) 질문의 응답만 순서대로 들어온다(재사용된 항목은 제외).
 */
function walkBootstrap({ initialId, confirmed, responses, need }) {
  const sequence = bootstrapSequence(initialId, confirmed)
  const entries = []
  let known = 0
  let responseIndex = 0
  for (let i = 0; i < sequence.length; i += 1) {
    if (known >= need) break
    const id = sequence[i]
    if (isConfirmedNegative(id, confirmed)) {
      entries.push({ question_id: id, kind: 'NEGATIVE', value: null, reused: true })
      known += 1
      continue
    }
    const response = responses[responseIndex]
    if (response) {
      if (response.question_id !== id) throw new Error('BOOTSTRAP_MISMATCH')
      responseIndex += 1
      entries.push(response)
      if (KNOWN.has(response.kind)) known += 1
      continue
    }
    const remainingFromHere = sequence.length - i
    if (known + remainingFromHere < need) return { status: START_INCOMPLETE }
    return { status: 'ASK', questionId: id, remaining: need - known }
  }
  if (known >= need) {
    if (responseIndex !== responses.length) throw new Error('BOOTSTRAP_MISMATCH')
    return { status: 'READY', entries }
  }
  return { status: START_INCOMPLETE }
}

/**
 * 다음 할 일. responses = 지금까지 물어본(ASKED) 질문 순서대로의 bootstrap 응답(UNKNOWN 포함, 재사용 항목 제외).
 * known 답(재사용 NEGATIVE 포함)이 부족분만큼 모이면 READY, 남은 질문을 모두 답해도 못 채우면 START_INCOMPLETE.
 */
export function bootstrapStep({ initialId, confirmed, responses }) {
  const { additional } = splitConfirmed(confirmed, initialId)
  const need = K - additional.length
  const result = walkBootstrap({ initialId, confirmed, responses, need })
  if (result.status === 'ASK') return { status: 'ASK', questionId: result.questionId, remaining: result.remaining }
  return { status: result.status }
}

export function buildStartRequest({ age, sex, initialId, confirmed, bootstrapResponses }) {
  if (!INITIAL_IDS.has(initialId)) throw new Error('INITIAL_NOT_ELIGIBLE')
  if (confirmed.some((c) => c.evidence_id === initialId && c.status !== 'POSITIVE')) throw new Error('INITIAL_NOT_POSITIVE')
  const { additional, cached } = splitConfirmed(confirmed, initialId)
  const need = K - additional.length
  const result = walkBootstrap({ initialId, confirmed, responses: bootstrapResponses, need })
  if (result.status !== 'READY') throw new Error(START_INCOMPLETE)
  const reusedIds = new Set(result.entries.filter((entry) => entry.reused).map((entry) => entry.question_id))
  const answers = [
    ...additional.map((c) => ({ question_id: c.evidence_id, kind: 'POSITIVE', value: null })),
    ...result.entries.filter((entry) => KNOWN.has(entry.kind))
      .map((entry) => ({ question_id: entry.question_id, kind: entry.kind, value: null })),
  ]
  if (answers.length !== K) throw new Error('EXACT_K_VIOLATION')
  return {
    request: { age, sex, initialEvidence: initialId, answers },
    cached: cached.filter((c) => !reusedIds.has(c.evidence_id)).map((c) => ({ evidence_id: c.evidence_id, status: c.status })),
    unknownIds: result.entries.filter((entry) => entry.kind === 'UNKNOWN').map((entry) => entry.question_id),
  }
}
