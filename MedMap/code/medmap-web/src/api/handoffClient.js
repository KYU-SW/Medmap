// 기기 간 인계 API(/v1/handoff/*, Phase A S1). 기존 client.js 의 request/post 를 그대로 쓴다.
// 서버는 인계 내용을 메모리에만 15분 두고, 번호로 한 번 가져가면 지운다.
import { post, request } from './client.js'

export function getHandoffStatus() {
  return request('/v1/handoff/status', { method: 'GET' })
}

export function createHandoffCode({ session, cache }) {
  return post('/v1/handoff/codes', { session, cache })
}

export function claimHandoffCode(code) {
  return post('/v1/handoff/claim', { code })
}
