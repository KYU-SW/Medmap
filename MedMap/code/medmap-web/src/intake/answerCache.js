// 확인했지만 start 에 넣지 못한 답. {evidence_id, status} 만 보관(원문·matched_text 금지).
// 엔진이 그 질문을 실제로 제안했을 때만 /session/answer 로 제출한다. posterior 는 건드리지 않는다.
export const CACHE_KEY = 'medmap.intakeCache'
const STATUSES = new Set(['POSITIVE', 'NEGATIVE'])
const EVIDENCE_ID = /^E_\d+$/

export function sanitizeCache(entries) {
  const seen = new Set()
  const clean = []
  for (const entry of Array.isArray(entries) ? entries : []) {
    if (!entry || !EVIDENCE_ID.test(entry.evidence_id) || !STATUSES.has(entry.status) || seen.has(entry.evidence_id)) continue
    seen.add(entry.evidence_id)
    clean.push({ evidence_id: entry.evidence_id, status: entry.status })
  }
  return clean
}

export function saveCache(entries) {
  const clean = sanitizeCache(entries)
  try {
    if (clean.length) sessionStorage.setItem(CACHE_KEY, JSON.stringify(clean))
    else sessionStorage.removeItem(CACHE_KEY)
  } catch { /* 저장 실패는 무시 — cache 는 보조 정보 */ }
  return clean
}

export function loadCache() {
  try {
    return sanitizeCache(JSON.parse(sessionStorage.getItem(CACHE_KEY) ?? '[]'))
  } catch {
    return []
  }
}

export function clearCache() {
  try { sessionStorage.removeItem(CACHE_KEY) } catch { /* 무시 */ }
}

export function cachedAnswerFor(cache, question) {
  if (!question || question.answer_type !== 'YES_NO') return null
  const hit = cache.find((entry) => entry.evidence_id === question.question_id)
  return hit ? { kind: hit.status, value: null } : null
}

export function withoutEvidence(cache, evidenceId) {
  return cache.filter((entry) => entry.evidence_id !== evidenceId)
}
