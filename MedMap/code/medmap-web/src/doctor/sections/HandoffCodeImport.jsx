import { useEffect, useState } from 'react'
import * as defaultApi from '../../api/handoffClient.js'

export const CLAIM_INVALID = '번호를 다시 확인해 주세요. 번호는 한 번만, 15분 동안 쓸 수 있습니다.'
export const CLAIM_LOCKED = '잘못된 번호가 많이 입력됐어요. 5분 뒤 다시 시도해 주세요.'
const CLAIM_FAILED = '불러오지 못했어요. 잠시 후 다시 시도해 주세요.'

const digitsOf = (value) => value.replace(/\D/g, '').slice(0, 8)
const withHyphen = (digits) => (digits.length > 4 ? `${digits.slice(0, 4)}-${digits.slice(4)}` : digits)

// 의사 PC: 환자 휴대폰에 뜬 8자리 번호로 인계를 가져온다. 가져온 {session, cache} 는 기존 가져오기(onImport)와 같은 경로로 연다.
// 서버 기능이 꺼져 있으면 보이지 않는다.
export default function HandoffCodeImport({ api = defaultApi, onImport, pending = false }) {
  const [enabled, setEnabled] = useState(false)
  const [digits, setDigits] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState(null)

  useEffect(() => {
    let alive = true
    api.getHandoffStatus().then((s) => { if (alive) setEnabled(Boolean(s?.enabled)) }).catch(() => {})
    return () => { alive = false }
  }, [api])

  async function claim(event) {
    event.preventDefault()
    if (digits.length !== 8) return
    setBusy(true)
    setMessage(null)
    try {
      const payload = await api.claimHandoffCode(digits)
      setDigits('')
      if (!onImport(JSON.stringify(payload))) setMessage(CLAIM_FAILED)
    } catch (err) {
      setMessage(err?.status === 404 ? CLAIM_INVALID : err?.status === 429 ? CLAIM_LOCKED : CLAIM_FAILED)
    } finally {
      setBusy(false)
    }
  }

  if (!enabled) return null
  return (
    <form className="sheet doctor-section" onSubmit={claim} data-testid="handoff-code-import">
      <h2>환자 번호로 불러오기</h2>
      <p className="hint">환자 휴대폰에 표시된 8자리 번호를 입력하세요.</p>
      <label className="field">
        <span>환자 번호</span>
        <input inputMode="numeric" autoComplete="off" value={withHyphen(digits)}
          onChange={(e) => setDigits(digitsOf(e.target.value))} disabled={busy || pending} />
      </label>
      <button type="submit" className="button button--primary" disabled={digits.length !== 8 || busy || pending}>
        번호로 불러오기
      </button>
      {message && <p role="alert">{message}</p>}
    </form>
  )
}
