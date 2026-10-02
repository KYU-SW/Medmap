import { readdirSync, readFileSync, statSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { COPY, FORBIDDEN_CLAIMS } from './copy.js'

const HERE = dirname(fileURLToPath(import.meta.url))

function strings(value) {
  if (typeof value === 'string') return [value]
  if (typeof value === 'function') return [String(value(1, 3))]
  if (value && typeof value === 'object') return Object.values(value).flatMap(strings)
  return []
}

function sourceFiles(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    if (statSync(path).isDirectory()) return sourceFiles(path)
    return /\.(jsx?|mjs)$/.test(name) && !/\.test\./.test(name) ? [path] : []
  })
}

export function findClaims(texts) {
  return texts.flatMap((text) => FORBIDDEN_CLAIMS.filter((word) => text.includes(word)).map((word) => ({ word, text })))
}

test('control: the checker flags a forbidden claim (verify the verifier)', () => {
  expect(findClaims(['현재 진단이 틀렸습니다', '오진을 잡았습니다'])).toHaveLength(2)
  expect(findClaims(['독립 모델 평가에서 고려된 후보'])).toHaveLength(0)
})

test('doctor copy has no forbidden clinical claims and no percent/probability wording', () => {
  const texts = strings(COPY)
  expect(texts.length).toBeGreaterThan(30)
  expect(findClaims(texts)).toEqual([])
  expect(texts.filter((t) => /%|확률|신뢰도|1위/.test(t))).toEqual([])
})

test('doctor/handoff source files contain no forbidden claims outside the forbidden list itself', () => {
  const files = [...sourceFiles(HERE), ...sourceFiles(join(HERE, '..', 'handoff'))]
    .filter((path) => !path.endsWith('copy.js'))
  expect(files.length).toBeGreaterThan(5)
  const hits = files.flatMap((path) => findClaims([readFileSync(path, 'utf-8')]).map((hit) => ({ path, word: hit.word })))
  expect(hits).toEqual([])
})
