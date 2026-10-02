import { ApiError } from './client'
import { userMessage } from './messages'

test('세션 형태 오류는 다시 시작을 안내한다', () => {
  const message = userMessage(new ApiError(409, 'MEDMAP_UNSUPPORTED_SESSION_SHAPE', 'MEDMAP_UNSUPPORTED_SESSION_SHAPE:n_additional=4'))
  expect(message.title).toBe('이 기록으로는 추가 확인을 이어갈 수 없습니다.')
  expect(message.body).toBe('처음부터 다시 시작해 주세요.')
  expect(message.action).toBe('restart')
})

test('네트워크 오류는 재시도를 안내한다', () => {
  const message = userMessage(new ApiError(0, 'NETWORK_ERROR', 'TypeError: fetch failed'))
  expect(message.title).toBe('연결하지 못했습니다.')
  expect(message.action).toBe('retry')
})

test('서버 준비 중은 대기를 안내한다', () => {
  expect(userMessage(new ApiError(503, 'ENGINE_NOT_READY', 'engine is not loaded')).title)
    .toBe('준비 중입니다. 잠시 후 다시 시도해 주세요.')
})

test('어떤 오류에서도 내부 코드가 문구에 새지 않는다', () => {
  const codes = ['MEDMAP_ALREADY_ASKED', 'MEDMAP_PARENT_GATE_VIOLATION', 'MEDMAP_EXCLUDED_QUESTION',
                 'MEDMAP_UNKNOWN_EVIDENCE_ID', 'REQUEST_VALIDATION_ERROR', 'INTERNAL_ERROR']
  for (const code of codes) {
    const message = userMessage(new ApiError(400, code, `${code}:E_55`))
    expect(`${message.title} ${message.body}`).not.toMatch(/MEDMAP_|_ERROR/)
  }
})
