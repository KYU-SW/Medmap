import { formatPercent } from './candidates'

test('확률을 소수 한 자리 퍼센트로 표기한다', () => {
  // 경계값은 IEEE754 표현을 그대로 따른다: 0.2435 → 24.349999…, 0.2445 → 24.449999…
  expect(formatPercent(0.2435)).toBe('24.3')
  expect(formatPercent(0.2445)).toBe('24.4')
  expect(formatPercent(0.2446)).toBe('24.5')
  expect(formatPercent(0.0802)).toBe('8.0')
  expect(formatPercent(0.3879264295101166)).toBe('38.8')
})

import { toCandidateRows } from './candidates'

const turn = {
  diagnoses: [
    { name: '기관지염', probability: 0.405 },
    { name: '급성 후두염', probability: 0.27 },
    { name: 'PSVT', probability: 0.176 },
  ],
  diagnoses_before: [
    { name: '만성 부비동염', probability: 0.2435 },
    { name: '기관지염', probability: 0.2415 },
    { name: '급성 부비동염', probability: 0.2388 },
  ],
}

test('이전 값과 비교해 방향을 매긴다', () => {
  const rows = toCandidateRows(turn)
  expect(rows[0]).toEqual({ name: '기관지염', probability: 0.405, previous: 0.2415, direction: 'up' })
  expect(rows[1]).toEqual({ name: '급성 후두염', probability: 0.27, previous: null, direction: 'same' })
})

test('직전 응답이 없으면 방향은 모두 same 이고 previous 는 null 이다', () => {
  const rows = toCandidateRows({ diagnoses: turn.diagnoses, diagnoses_before: null })
  expect(rows.every((r) => r.direction === 'same' && r.previous === null)).toBe(true)
})

test('같은 확률이면 same 이다', () => {
  const rows = toCandidateRows({
    diagnoses: [{ name: 'URTI', probability: 0.3 }],
    diagnoses_before: [{ name: 'URTI', probability: 0.3 }],
  })
  expect(rows[0].direction).toBe('same')
})
