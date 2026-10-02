import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  BOOTSTRAP_BACKUP, BOOTSTRAP_PRIMARY, BOOTSTRAP_QUESTIONS_KO, K, START_INCOMPLETE,
  bootstrapSequence, bootstrapStep, buildStartRequest, initialOptions, splitConfirmed,
} from './startPlan.js'

const pos = (id) => ({ evidence_id: id, status: 'POSITIVE' })
const neg = (id) => ({ evidence_id: id, status: 'NEGATIVE' })
const r = (id, kind) => ({ question_id: id, kind, value: null })

// dirname()+join() (not `new URL(rel, import.meta.url)`) — that literal pattern is
// intercepted by Vite's static asset-URL analysis under the jsdom test environment and
// resolves to a dev-server http:// URL instead of the real file:// path.
const here = dirname(fileURLToPath(import.meta.url))

test('고정 bootstrap 순서는 STEP17A 그대로다', () => {
  expect(K).toBe(3)
  expect(BOOTSTRAP_PRIMARY).toEqual(['E_91', 'E_53', 'E_66'])
  expect(BOOTSTRAP_BACKUP).toEqual(['E_201', 'E_175', 'E_88'])
})

test('bootstrap 질문 문구는 엔진 한국어 라벨과 같다', () => {
  const labels = JSON.parse(readFileSync(join(here, '../../../medmap/data/question_labels_ko.json'), 'utf8')).questions
  for (const id of [...BOOTSTRAP_PRIMARY, ...BOOTSTRAP_BACKUP]) expect(BOOTSTRAP_QUESTIONS_KO[id]).toBe(labels[id])
})

test('initial 후보는 확인된 POSITIVE 중 96개에 속한 것만(NEGATIVE·과거력 제외)', () => {
  expect(initialOptions([pos('E_201'), neg('E_91'), pos('E_69')])).toEqual([pos('E_201')])
  expect(initialOptions([neg('E_91')])).toEqual([])
})

test('확인된 NEGATIVE 는 additional 에 들어가지 않고 cache 에 남는다', () => {
  const { additional, cached } = splitConfirmed([pos('E_201'), neg('E_91'), pos('E_77')], 'E_201')
  expect(additional).toEqual([pos('E_77')])
  expect(cached).toEqual([neg('E_91')])
})

test('같은 evidence_id 중복 확인은 첫 등장만 남기고 additional·cache 어디에도 중복이 없다', () => {
  const { additional, cached } = splitConfirmed([pos('E_77'), pos('E_77'), neg('E_91')], 'E_201')
  expect(additional).toEqual([pos('E_77')])
  expect(cached).toEqual([neg('E_91')])
})

test('POSITIVE 4개 이상이면 발화 순서 앞 3개가 additional, 나머지 POSITIVE·NEGATIVE 는 순서대로 cache', () => {
  const confirmed = [pos('E_201'), pos('E_91'), neg('E_214'), pos('E_66'), pos('E_77'), pos('E_50'), pos('E_212')]
  const { additional, cached } = splitConfirmed(confirmed, 'E_66')
  expect(additional.map((c) => c.evidence_id)).toEqual(['E_201', 'E_91', 'E_77'])
  expect(cached).toEqual([neg('E_214'), pos('E_50'), pos('E_212')])
})

test('bootstrap 후보는 initial 과 확인된 POSITIVE 를 건너뛴다(확인된 NEGATIVE는 남아 재사용 대상이 된다, rev3)', () => {
  expect(bootstrapSequence('E_201', [])).toEqual(['E_91', 'E_53', 'E_66', 'E_175', 'E_88'])
  expect(bootstrapSequence('E_201', [neg('E_91')])).toEqual(['E_91', 'E_53', 'E_66', 'E_175', 'E_88'])
  expect(bootstrapSequence('E_66', [pos('E_91'), pos('E_53')])).toEqual(['E_201', 'E_175', 'E_88'])
})

test('rev3-1: frozen 목록에 있는 확인된 NEGATIVE 는 walk 가 도달하면 재사용되고 다시 묻지 않는다', () => {
  const step = bootstrapStep({ initialId: 'E_201', confirmed: [neg('E_91')], responses: [] })
  expect(step).toEqual({ status: 'ASK', questionId: 'E_53', remaining: 2 })
  const { request, cached } = buildStartRequest({
    age: 45, sex: 'M', initialId: 'E_201', confirmed: [neg('E_91')],
    bootstrapResponses: [r('E_53', 'NEGATIVE'), r('E_66', 'POSITIVE')],
  })
  expect(request.answers).toEqual([
    { question_id: 'E_91', kind: 'NEGATIVE', value: null },
    { question_id: 'E_53', kind: 'NEGATIVE', value: null },
    { question_id: 'E_66', kind: 'POSITIVE', value: null },
  ])
  expect(cached).toEqual([])
})

test('rev3-2: walk 가 도달하기 전에 need 가 채워지면 확인된 NEGATIVE 는 cache 에 남는다', () => {
  const confirmed = [pos('E_77'), pos('E_50'), neg('E_88')]
  expect(bootstrapStep({ initialId: 'E_201', confirmed, responses: [] }))
    .toEqual({ status: 'ASK', questionId: 'E_91', remaining: 1 })
  expect(bootstrapStep({ initialId: 'E_201', confirmed, responses: [r('E_91', 'NEGATIVE')] }))
    .toEqual({ status: 'READY' })
  const { request, cached } = buildStartRequest({
    age: 45, sex: 'M', initialId: 'E_201', confirmed,
    bootstrapResponses: [r('E_91', 'NEGATIVE')],
  })
  expect(request.answers).toEqual([
    { question_id: 'E_77', kind: 'POSITIVE', value: null },
    { question_id: 'E_50', kind: 'POSITIVE', value: null },
    { question_id: 'E_91', kind: 'NEGATIVE', value: null },
  ])
  expect(cached).toEqual([neg('E_88')])
})

test('rev3-3: frozen 목록 밖의 확인된 NEGATIVE 는 항상 cache 에 남는다', () => {
  const { cached } = buildStartRequest({
    age: 45, sex: 'M', initialId: 'E_201', confirmed: [neg('E_214')],
    bootstrapResponses: [r('E_91', 'NEGATIVE'), r('E_53', 'NEGATIVE'), r('E_66', 'NEGATIVE')],
  })
  expect(cached).toEqual([neg('E_214')])
})

test('rev3-4: UNKNOWN 뒤에도 확인된 NEGATIVE 재사용은 그대로 동작하고 UNKNOWN 은 unknownIds 로 남는다', () => {
  const confirmed = [neg('E_66')]
  const responses = [r('E_91', 'UNKNOWN'), r('E_53', 'NEGATIVE')]
  expect(bootstrapStep({ initialId: 'E_201', confirmed, responses }))
    .toEqual({ status: 'ASK', questionId: 'E_175', remaining: 1 })
  const { request, unknownIds } = buildStartRequest({
    age: 45, sex: 'M', initialId: 'E_201', confirmed,
    bootstrapResponses: [...responses, r('E_175', 'POSITIVE')],
  })
  expect(request.answers).toEqual([
    { question_id: 'E_53', kind: 'NEGATIVE', value: null },
    { question_id: 'E_66', kind: 'NEGATIVE', value: null },
    { question_id: 'E_175', kind: 'POSITIVE', value: null },
  ])
  expect(unknownIds).toEqual(['E_91'])
})

test('rev3-5: START_INCOMPLETE 판정은 재사용 가능한 NEGATIVE 도 채울 수 있는 것으로 계산한다', () => {
  const confirmed = [neg('E_88')]
  expect(bootstrapStep({ initialId: 'E_201', confirmed, responses: [r('E_91', 'UNKNOWN'), r('E_53', 'UNKNOWN')] }))
    .toEqual({ status: 'ASK', questionId: 'E_66', remaining: 3 })
  expect(bootstrapStep({ initialId: 'E_201', confirmed, responses: [r('E_91', 'UNKNOWN'), r('E_53', 'UNKNOWN'), r('E_66', 'UNKNOWN')] }))
    .toEqual({ status: 'START_INCOMPLETE' })
})

test('rev3-6: 확인된 POSITIVE 는 frozen 목록에서 건너뛰고 다시 묻지 않는다', () => {
  expect(bootstrapStep({ initialId: 'E_201', confirmed: [pos('E_91')], responses: [] }))
    .toEqual({ status: 'ASK', questionId: 'E_53', remaining: 2 })
})

test.each([
  [[], { status: 'ASK', questionId: 'E_91', remaining: 3 }],                                   // POSITIVE additional 0 → 3
  [[pos('E_77')], { status: 'ASK', questionId: 'E_91', remaining: 2 }],                         // 1 → 2
  [[pos('E_77'), pos('E_214')], { status: 'ASK', questionId: 'E_91', remaining: 1 }],           // 2 → 1
  [[pos('E_77'), pos('E_214'), pos('E_50')], { status: 'READY' }],                              // 3 → 0
  [[neg('E_77'), neg('E_214'), neg('E_50')], { status: 'ASK', questionId: 'E_91', remaining: 3 }], // NEGATIVE 는 세지 않음
])('POSITIVE additional %# → bootstrap 부족분', (confirmed, expected) => {
  expect(bootstrapStep({ initialId: 'E_201', confirmed, responses: [] })).toEqual(expected)
})

test('bootstrap UNKNOWN 은 exact-k count 를 늘리지 않고 다음 backup 질문으로 간다', () => {
  const step = (responses) => bootstrapStep({ initialId: 'E_201', confirmed: [], responses })
  expect(step([r('E_91', 'UNKNOWN')])).toEqual({ status: 'ASK', questionId: 'E_53', remaining: 3 })
  expect(step([r('E_91', 'UNKNOWN'), r('E_53', 'NEGATIVE'), r('E_66', 'POSITIVE')]))
    .toEqual({ status: 'ASK', questionId: 'E_175', remaining: 1 })
  expect(step([r('E_91', 'UNKNOWN'), r('E_53', 'NEGATIVE'), r('E_66', 'POSITIVE'), r('E_175', 'NEGATIVE')]))
    .toEqual({ status: 'READY' })
})

test('남은 backup 으로 채울 수 없으면 START_INCOMPLETE', () => {
  expect(START_INCOMPLETE).toBe('START_INCOMPLETE')
  const none = (responses) => bootstrapStep({ initialId: 'E_201', confirmed: [], responses })
  expect(none([r('E_91', 'UNKNOWN'), r('E_53', 'UNKNOWN')])).toEqual({ status: 'ASK', questionId: 'E_66', remaining: 3 })
  expect(none([r('E_91', 'UNKNOWN'), r('E_53', 'UNKNOWN'), r('E_66', 'UNKNOWN')])).toEqual({ status: 'START_INCOMPLETE' })
  const two = [pos('E_77'), pos('E_50')]
  const unknowns = ['E_91', 'E_53', 'E_66', 'E_175'].map((id) => r(id, 'UNKNOWN'))
  expect(bootstrapStep({ initialId: 'E_201', confirmed: two, responses: unknowns })).toEqual({ status: 'ASK', questionId: 'E_88', remaining: 1 })
  expect(bootstrapStep({ initialId: 'E_201', confirmed: two, responses: [...unknowns, r('E_88', 'UNKNOWN')] }))
    .toEqual({ status: 'START_INCOMPLETE' })
})

test('POSITIVE confirmed + known bootstrap 만으로 정확히 k3 를 만든다(NEGATIVE·UNKNOWN 제외)', () => {
  const { request, cached, unknownIds } = buildStartRequest({
    age: 45, sex: 'M', initialId: 'E_201',
    confirmed: [pos('E_201'), neg('E_214'), pos('E_91')],
    bootstrapResponses: [r('E_53', 'UNKNOWN'), r('E_66', 'NEGATIVE'), r('E_175', 'POSITIVE')],
  })
  expect(request).toEqual({
    age: 45, sex: 'M', initialEvidence: 'E_201',
    answers: [
      { question_id: 'E_91', kind: 'POSITIVE', value: null },
      { question_id: 'E_66', kind: 'NEGATIVE', value: null },
      { question_id: 'E_175', kind: 'POSITIVE', value: null },
    ],
  })
  expect(cached).toEqual([neg('E_214')])
  expect(unknownIds).toEqual(['E_53'])
})

test('완성되지 않은 bootstrap 으로는 start 본문을 만들지 않는다', () => {
  expect(() => buildStartRequest({ age: 45, sex: 'M', initialId: 'E_201', confirmed: [], bootstrapResponses: [r('E_91', 'UNKNOWN')] }))
    .toThrow('START_INCOMPLETE')
})

test('NEGATIVE 확인 항목·96개 밖 항목은 initial 이 될 수 없다', () => {
  const known = (ids) => ids.map((id) => r(id, 'NEGATIVE'))
  expect(() => buildStartRequest({ age: 45, sex: 'M', initialId: 'E_91', confirmed: [neg('E_91')], bootstrapResponses: known(['E_53', 'E_66', 'E_201']) }))
    .toThrow('INITIAL_NOT_POSITIVE')
  expect(() => buildStartRequest({ age: 45, sex: 'M', initialId: 'E_69', confirmed: [], bootstrapResponses: known(['E_91', 'E_53', 'E_66']) }))
    .toThrow('INITIAL_NOT_ELIGIBLE')
})

test('bootstrap 응답 순서가 frozen 순서와 다르면 거부한다', () => {
  expect(() => buildStartRequest({ age: 45, sex: 'M', initialId: 'E_201', confirmed: [], bootstrapResponses: [r('E_66', 'NEGATIVE'), r('E_53', 'NEGATIVE'), r('E_91', 'NEGATIVE')] }))
    .toThrow('BOOTSTRAP_MISMATCH')
})

test('bootstrap 질문 문구는 한국어 용어 정본(questionText)에서 오고 기존 승인 문구와 같다', async () => {
  const { questionText } = await import('../terminology/labels.js')
  for (const id of [...BOOTSTRAP_PRIMARY, ...BOOTSTRAP_BACKUP]) {
    expect(BOOTSTRAP_QUESTIONS_KO[id]).toBe(questionText(id))
    expect(BOOTSTRAP_QUESTIONS_KO[id]).toMatch(/[가-힣].*\?/)          // null·빈 문자열이면 실패
  }
  expect(BOOTSTRAP_QUESTIONS_KO.E_91).toBe('열이 있나요? (느낌으로든 체온계로 잰 것이든)')
  expect(BOOTSTRAP_QUESTIONS_KO.E_88).toBe('너무 피곤해서 평소 하던 일을 못 하거나 하루 종일 누워 지내나요?')
  expect(Object.isFrozen(BOOTSTRAP_QUESTIONS_KO)).toBe(true)
})
