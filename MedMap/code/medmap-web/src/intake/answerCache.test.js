import { CACHE_KEY, cachedAnswerFor, clearCache, loadCache, sanitizeCache, saveCache, withoutEvidence } from './answerCache.js'

const yesNo = (id) => ({ question_id: id, answer_type: 'YES_NO' })
beforeEach(() => sessionStorage.clear())

test('cache 에는 evidence_id·status 만 남는다(원문·matched_text·label 제거)', () => {
  const clean = sanitizeCache([
    { evidence_id: 'E_50', status: 'POSITIVE', matched_text: '식은땀', label_ko: 'x', text: '원문' },
    { evidence_id: 'E_50', status: 'NEGATIVE' },            // 중복 → 첫 항목만
    { evidence_id: 'E_212', status: 'UNKNOWN' },             // 허용되지 않는 status
    { evidence_id: 'bad', status: 'POSITIVE' },
  ])
  expect(clean).toEqual([{ evidence_id: 'E_50', status: 'POSITIVE' }])
})

test('저장·복원·삭제', () => {
  saveCache([{ evidence_id: 'E_212', status: 'POSITIVE', matched_text: '목소리' }])
  expect(sessionStorage.getItem(CACHE_KEY)).toBe('[{"evidence_id":"E_212","status":"POSITIVE"}]')
  expect(loadCache()).toEqual([{ evidence_id: 'E_212', status: 'POSITIVE' }])
  saveCache([])
  expect(sessionStorage.getItem(CACHE_KEY)).toBeNull()
  saveCache([{ evidence_id: 'E_212', status: 'POSITIVE' }])
  clearCache()
  expect(loadCache()).toEqual([])
})

test('깨진 저장본은 빈 cache', () => {
  sessionStorage.setItem(CACHE_KEY, '{not json')
  expect(loadCache()).toEqual([])
})

test('엔진이 제안한 YES_NO 질문이 cache 에 있을 때만 답을 준다', () => {
  const cache = [{ evidence_id: 'E_50', status: 'POSITIVE' }]
  expect(cachedAnswerFor(cache, yesNo('E_50'))).toEqual({ kind: 'POSITIVE', value: null })
  expect(cachedAnswerFor(cache, yesNo('E_212'))).toBeNull()
  expect(cachedAnswerFor(cache, { question_id: 'E_50', answer_type: 'MULTI_CHOICE' })).toBeNull()
  expect(cachedAnswerFor(cache, null)).toBeNull()
  expect(withoutEvidence(cache, 'E_50')).toEqual([])
})
