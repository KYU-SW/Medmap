// VAD replay 채점 단위 테스트. 실행: node --test e2e/replayScore.check.mjs  (vitest 가 아니라 node:test — 파일명이 .test 가 아닌 이유)
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { align, score } from './replayScore.mjs'

const rec = {
  sentences: ['어제부터 배가 아팠어요.', '열이 삼십팔 도 오 부까지 올랐어요.', '구토를 두 번 했어요.'],
  numbers: [{ sentence: 1, accept: ['38.5', '삼십팔도오부'] }, { sentence: 2, accept: ['두번', '2번'] }],
}
const seg = (text, reason = 'vad') => ({ text, reason })

test('perfect: boundaries at every sentence end, nothing missed', () => {
  const r = score(rec, [seg('어제부터 배가 아팠어요.'), seg('열이 38.5도까지 올랐어요.'), seg('구토를 두 번 했어요.'), seg('', 'manual')])
  assert.equal(r.false_endpoints, 0)
  assert.equal(r.missed_endpoints, 0)
  assert.equal(r.delayed_end, false)
  assert.equal(r.numeric_pass, 2)                  // 38.5 표기도 accept
  assert.equal(r.dup, false)
})

test('cut in the middle of a sentence = false endpoint', () => {
  const r = score(rec, [seg('어제부터 배가 아팠어요.'), seg('열이 삼십팔 도'), seg('오 부까지 올랐어요.'), seg('구토를 두 번 했어요.')])
  assert.equal(r.false_endpoints, 1)
  assert.equal(r.missed_endpoints, 0)
})

test('two sentences merged = missed endpoint; last sentence closed only by stop = delayed end', () => {
  const r = score(rec, [seg('어제부터 배가 아팠어요. 열이 삼십팔 도 오 부까지 올랐어요.'), seg('구토를 두 번 했어요.', 'manual')])
  assert.equal(r.missed_endpoints, 1)
  assert.equal(r.false_endpoints, 0)
  assert.equal(r.delayed_end, true)
})

test('lost number and duplicated FINAL are reported', () => {
  const r = score(rec, [seg('어제부터 배가 아팠어요.'), seg('열이 38도까지 올랐어요.'), seg('구토를 두 번 했어요.'), seg('구토를 두 번 했어요.')])
  assert.equal(r.numeric_pass, 1)                  // "38도" ≠ 38.5
  assert.equal(r.dup, true)
  assert.ok(r.ins > 0)
})

test('align counts edit operations', () => {
  const a = align('가나다라', '가다라마')
  assert.deepEqual([a.dist, a.del, a.ins], [2, 1, 1])
})

const numRec = {
  sentences: ['삼십팔 점… 오 도까지 올랐어요.'],
  numbers: [{ sentence: 0, span: '삼십팔 점… 오 도', accept: ['38.5', '삼십팔점오도'] }],
}

test('FINAL boundary inside a number span = numeric split (and a false endpoint)', () => {
  const r = score(numRec, [seg('삼십팔 점'), seg('오 도까지 올랐어요.')])
  assert.equal(r.numeric_split, 1)
  assert.equal(r.false_endpoints, 1)
})

test('number kept in one FINAL = no numeric split', () => {
  const r = score(numRec, [seg('삼십팔 점 오 도까지 올랐어요.')])
  assert.equal(r.numeric_split, 0)
  assert.equal(r.numeric_pass, 1)
})

// ---- T_partial: VAD 음성 구간 안 패킷만, 발화 안 쉼(서버 pauses_ms) 동안 패킷은 뺀다 ----
import { tPartialSamples } from './replayScore.mjs'

test('T_partial excludes packets inside in-utterance pauses (no new partial is expected there)', () => {
  const packets = [400, 500, 600, 700, 800, 900].map((audio_ms, i) => ({ audio_ms, t: 1000 + i * 100 }))
  // 600~800 ms 는 쉼 → 그 동안 partial 없음, 쉼 뒤 900 ms 패킷에서야 partial
  const partials = [{ audio_ms: 400, t: 1050 }, { audio_ms: 500, t: 1150 }, { audio_ms: 900, t: 1560 }]
  const spans = [[0, 1200]]
  const without = tPartialSamples(packets, partials, spans, [])
  const withPause = tPartialSamples(packets, partials, spans, [[560, 820]])
  assert.deepEqual(without.values, [50, 50, 360, 260, 160, 60])            // 쉼 패킷이 부풀린 값(360·260·160)
  assert.deepEqual(withPause.values, [50, 50, 60])
  assert.equal(withPause.excluded_pause, 3)
})

test('T_partial keeps the speech-span and 300 ms warm-up rules', () => {
  const packets = [{ audio_ms: 200, t: 0 }, { audio_ms: 400, t: 10 }, { audio_ms: 1500, t: 20 }]
  const partials = [{ audio_ms: 400, t: 30 }, { audio_ms: 1500, t: 40 }]
  const r = tPartialSamples(packets, partials, [[0, 1000]], [])
  assert.deepEqual(r.values, [20])                                            // 300 ms 미만·음성 구간 밖 제외
})
