// initial 96개 표시·검색용(매퍼 alias 아님). 정본: medmap/data/initial_evidence_ko.json
import catalog from './initialCatalog.json'

export const INITIAL_ITEMS = catalog.items
export const INITIAL_IDS = new Set(INITIAL_ITEMS.map((item) => item.evidence_id))
export const FREQUENT_IDS = catalog.frequent_ids
const BY_ID = new Map(INITIAL_ITEMS.map((item) => [item.evidence_id, item]))
const SEARCH_LIMIT = 10

export function initialItem(evidenceId) {
  return BY_ID.get(evidenceId) ?? null
}

const squash = (value) => value.replace(/\s+/g, '')

export function searchInitial(query, { exclude = [] } = {}) {
  const needle = squash(query ?? '')
  if (!needle) return []
  const blocked = new Set(exclude)
  return INITIAL_ITEMS
    .filter((item) => !blocked.has(item.evidence_id))
    .filter((item) => squash(item.label_ko).includes(needle) || squash(item.detail_ko).includes(needle))
    .slice(0, SEARCH_LIMIT)
}
