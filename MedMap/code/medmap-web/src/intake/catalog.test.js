import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import catalogCopy from './initialCatalog.json'
import { FREQUENT_IDS, INITIAL_IDS, INITIAL_ITEMS, initialItem, searchInitial } from './catalog.js'

// dirname()+join() (not `new URL(rel, import.meta.url)`) — that literal pattern is
// intercepted by Vite's static asset-URL analysis under the jsdom test environment and
// resolves to a dev-server http:// URL instead of the real file:// path.
const here = dirname(fileURLToPath(import.meta.url))

test('프론트 사본은 Python 정본과 같다', () => {
  const source = JSON.parse(readFileSync(join(here, '../../../medmap/data/initial_evidence_ko.json'), 'utf8'))
  expect(catalogCopy).toEqual(source)
})

test('initial 가능은 96개, 자주 쓰는 8개는 rank 상위 8개', () => {
  expect(INITIAL_ITEMS).toHaveLength(96)
  expect(INITIAL_IDS.size).toBe(96)
  expect(FREQUENT_IDS).toEqual(INITIAL_ITEMS.slice(0, 8).map((i) => i.evidence_id))
  expect(initialItem('E_201').label_ko).toBe('기침')
  expect(initialItem('E_69')).toBeNull()          // 과거력은 initial 불가
})

test('검색은 라벨·설명에서 공백 무시로 찾고 최대 10개, 제외 목록을 뺀다', () => {
  expect(searchInitial('').length).toBe(0)
  expect(searchInitial('어지').map((i) => i.evidence_id)).toEqual(expect.arrayContaining(['E_82', 'E_76']))
  expect(searchInitial('목 아픔').map((i) => i.evidence_id)).toContain('E_97')
  expect(searchInitial('통증').length).toBeLessThanOrEqual(10)
  expect(searchInitial('열', { exclude: ['E_91'] }).map((i) => i.evidence_id)).not.toContain('E_91')
})
