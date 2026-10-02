import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import generated from '../generated/terminology_ko.json'
import { diseaseLabel, evidenceShortLabel, historyQuestionLabel, questionText, valueLabel } from './labels.js'

const here = dirname(fileURLToPath(import.meta.url))
const canonicalPath = join(here, '../../../medmap/data/terminology_ko.json')

test('생성물은 현재 정본에서 export 된 것이다(source_sha256 일치)', () => {
  const sha = createHash('sha256').update(readFileSync(canonicalPath)).digest('hex')
  expect(generated.source_sha256).toBe(sha)
})

test('생성물은 정본의 ok 항목과 같고 review_needed draft 는 없다', () => {
  const canonical = JSON.parse(readFileSync(canonicalPath, 'utf8'))
  for (const [section, field, out] of [['diseases', 'label_ko', 'diseases'], ['evidence_short', 'label_ko', 'evidence_short'],
    ['values', 'label_ko', 'values'], ['evidence_questions', 'text_ko', 'questions']]) {
    const ok = Object.fromEntries(Object.entries(canonical[section])
      .filter(([, v]) => v.status === 'ok').map(([k, v]) => [k, v[field]]))
    expect(generated[out]).toEqual(ok)
  }
})

test('질환: ok 는 한국어, review_needed·미등록은 내부 이름 그대로', () => {
  expect(diseaseLabel('Pneumonia')).toBe('폐렴')
  expect(diseaseLabel('Pulmonary neoplasm')).toBe('폐 종양')
  expect(diseaseLabel('URTI')).not.toBe('URTI')
  expect(diseaseLabel('Nope')).toBe('Nope')
  expect(diseaseLabel('constructor')).toBe('constructor')
})

test('짧은 표시명·값: 없으면 null', () => {
  expect(evidenceShortLabel('E_201')).toBe('기침')
  expect(evidenceShortLabel('E_147')).toBe('최근 병원 주사 치료(구역·흥분·중독 등)')
  expect(evidenceShortLabel('E_99999')).toBeNull()
  expect(valueLabel('V_7')).toBe('동남아시아')
  expect(valueLabel('7')).toBeNull()
})

test('요약 이력 문구: 한국어 질문은 그대로, 영문 fallback 질문은 짧은 표시명', () => {
  expect(historyQuestionLabel({ question_id: 'E_91', question_ko: '열이 있나요?', is_fallback: false })).toBe('열이 있나요?')
  expect(historyQuestionLabel({ question_id: 'E_204', question_ko: 'Have you traveled out of the country in the last 4 weeks?', is_fallback: true }))
    .toBe('4주 내 해외여행')
  expect(historyQuestionLabel({ question_id: 'E_99999', question_ko: 'Unknown question?', is_fallback: true }))
    .toBe('Unknown question?')
})

test('질문 전문: 정본 한국어, 없으면 null', () => {
  expect(questionText('E_91')).toBe('열이 있나요? (느낌으로든 체온계로 잰 것이든)')
  expect(questionText('E_204')).toBe('최근 4주 안에 해외여행을 다녀왔나요? (다녀왔다면 지역을 골라 주세요)')
  expect(questionText('E_134')).toBeNull()          // 제외 질문
  expect(questionText('E_99999')).toBeNull()
})

test('생성물의 모든 표시문에 한국어가 있고 영문 단어는 병기 약어뿐이다', () => {
  const allowed = new Set(['HIV', 'BMI', 'cm', 'COPD', 'NSAID', 'NOAC', 'ST', 'OSA'])
  for (const section of ['diseases', 'evidence_short', 'values', 'questions']) {
    for (const [key, text] of Object.entries(generated[section])) {
      expect(text, `${section}:${key}`).toMatch(/[가-힣]/)
      for (const word of text.match(/[A-Za-z]+/g) ?? []) expect(allowed.has(word), `${section}:${key}:${word}`).toBe(true)
    }
  }
})
