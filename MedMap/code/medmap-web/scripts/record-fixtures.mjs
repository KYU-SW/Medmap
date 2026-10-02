// 사용법: (터미널1) ~/ai_env/bin/python -m uvicorn medmap.api:app --port 8000   (메인 체크아웃에서)
//        (터미널2) node scripts/record-fixtures.mjs
import { writeFileSync } from 'node:fs'
const base = process.env.MEDMAP_API ?? 'http://127.0.0.1:8000'
const body = {
  age: 45, sex: 'M', model_context: 'k3', initial_evidence: 'E_53',
  answers: [
    { question_id: 'E_55', kind: 'VALUE', value: ['V_89'] },
    { question_id: 'E_56', kind: 'VALUE', value: ['2'] },
    { question_id: 'E_204', kind: 'VALUE', value: ['V_10'] },
  ],
}
const turn = await (await fetch(`${base}/v1/session/start`, {
  method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body),
})).json()
writeFileSync(new URL('../src/test/fixtures/turn.start.json', import.meta.url), JSON.stringify(turn, null, 1) + '\n')
console.log('saved turn.start.json', turn.next_question.question_id)

let current = turn
for (let step = 1; step <= 3 && current.next_question; step += 1) {
  const q = current.next_question
  const answer = q.possible_values.length
    ? { kind: 'VALUE', value: [q.possible_values[0]] }
    : { kind: 'NEGATIVE', value: null }
  current = await (await fetch(`${base}/v1/session/answer`, {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ session: current.session, submission: { question_id: q.question_id, answer } }),
  })).json()
  writeFileSync(new URL(`../src/test/fixtures/turn.answer${step}.json`, import.meta.url), JSON.stringify(current, null, 1) + '\n')
  console.log(`saved turn.answer${step}.json`, current.stop_reason)
}
