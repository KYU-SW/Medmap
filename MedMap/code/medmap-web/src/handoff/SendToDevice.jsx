import { useEffect, useState } from 'react'
import * as defaultApi from '../api/handoffClient.js'
import { HANDOFF_CACHE_KEY, HANDOFF_SESSION_KEY } from './useHandoffSession.js'

export const SEND_LABEL = '다른 기기(진료실)로 보내기'
export const SEND_HINT = '진료실에서 이 번호를 알려 주거나 화면을 보여 주세요. 번호는 한 번만, 15분 동안 쓸 수 있습니다.'
export const CODE_EXPIRED = '번호가 만료됐어요. 새 번호를 받아 주세요.'
const FAILED = '번호를 만들지 못했어요. 잠시 후 다시 시도해 주세요.'

const formatCode = (code) => `${code.slice(0, 4)}-${code.slice(4)}`
const formatLeft = (s) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`

function readHandoff() {
  try {
    return {
      session: JSON.parse(sessionStorage.getItem(HANDOFF_SESSION_KEY) ?? 'null'),
      cache: JSON.parse(sessionStorage.getItem(HANDOFF_CACHE_KEY) ?? '[]'),
    }
  } catch {
    return { session: null, cache: [] }
  }
}

// 인계 완료 화면(#/handoff)에서 다른 기기로 보낼 번호를 받는다. 번호는 화면에만 있고 저장하지 않는다.
// 서버 기능이 꺼져 있으면 아무것도 보이지 않는다(같은 브라우저 인계는 그대로).
export default function SendToDevice({ api = defaultApi }) {
  const [enabled, setEnabled] = useState(false)
  const [code, setCode] = useState(null)
  const [left, setLeft] = useState(0)
  const [pending, setPending] = useState(false)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let alive = true
    api.getHandoffStatus().then((s) => { if (alive) setEnabled(Boolean(s?.enabled)) }).catch(() => {})
    return () => { alive = false }
  }, [api])

  useEffect(() => {
    if (!code) return undefined
    const timer = setInterval(() => setLeft((s) => Math.max(0, s - 1)), 1000)
    return () => clearInterval(timer)
  }, [code])

  async function send() {
    const { session, cache } = readHandoff()
    if (!session) { setFailed(true); return }
    setPending(true)
    setFailed(false)
    try {
      const result = await api.createHandoffCode({ session, cache })
      setCode(result.code)
      setLeft(result.expires_in_s)
    } catch {
      setFailed(true)
    } finally {
      setPending(false)
    }
  }

  if (!enabled) return null
  const expired = code && left <= 0
  return (
    <div className="stack" data-testid="handoff-send">
      {!code && (
        <button type="button" className="button" onClick={send} disabled={pending}>{SEND_LABEL}</button>
      )}
      {code && !expired && (
        <div data-testid="handoff-code" aria-live="polite">
          <p className="handoff-code__number">{formatCode(code)}</p>
          <p className="hint">{`${formatLeft(left)} 남음 · ${SEND_HINT}`}</p>
        </div>
      )}
      {expired && <p role="status">{CODE_EXPIRED}</p>}
      {code && (
        <button type="button" className="button" onClick={send} disabled={pending}>새 번호 받기</button>
      )}
      {failed && <p role="alert">{FAILED}</p>}
    </div>
  )
}
