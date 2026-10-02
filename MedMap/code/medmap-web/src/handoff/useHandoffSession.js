import { useCallback, useEffect, useRef, useState } from 'react'
import * as defaultApi from '../api/client.js'
import { sanitizeCache } from '../intake/answerCache.js'

export const HANDOFF_SESSION_KEY = 'medmap.handoff.session'
export const HANDOFF_CACHE_KEY = 'medmap.handoff.cache'
// 인계마다 새 식별자. 같은 입력이면 세션 JSON 이 바이트 단위로 같으므로, 의사 화면은 이 값으로 새 인계를 구분한다.
export const HANDOFF_ID_KEY = 'medmap.handoff.id'
const HANDOFF_KEYS = [HANDOFF_SESSION_KEY, HANDOFF_CACHE_KEY, HANDOFF_ID_KEY]

function newHandoffId() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID()
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`
}

function readSession() {
  try {
    const value = JSON.parse(sessionStorage.getItem(HANDOFF_SESSION_KEY) ?? 'null')
    return value && value.patient_state ? value : null
  } catch {
    return null
  }
}

// 의사 인계용 intake(#/handoff). 기존 useMedmapSession 을 쓰지 않는다: start 뒤 intake cache 를 자동 적용(settle)하지 않고
// 세션(exact-k3, IG 질문 0개)과 cache 를 그대로 보존한다(spec rev4 §11-6 B). 시작 전 입력은 어디에도 저장하지 않는다.
export function useHandoffSession({ api = defaultApi } = {}) {
  const [phase, setPhase] = useState(() => (readSession() ? 'done' : 'start'))
  const [health, setHealth] = useState({ engine_ready: false })
  const [error, setError] = useState(null)
  const [pending, setPending] = useState(false)
  const [storageFailed, setStorageFailed] = useState(false)
  const lastStartRef = useRef(null)

  useEffect(() => {
    let alive = true
    api.getHealth()
      .then((value) => { if (alive) setHealth(value) })
      .catch((cause) => { if (alive) setError(cause) })
    return () => { alive = false }
  }, [api])

  const begin = useCallback(() => {
    setError(null)
    setPhase('intake')
  }, [])

  // 자유문장 → 후보. 원문은 요청에만 쓰고 보관하지 않는다. 실패하면 null.
  const extract = useCallback(async (text) => {
    setPending(true)
    setError(null)
    try {
      const body = await api.extractIntake(text)
      return body.candidates
    } catch (cause) {
      cause.source = 'extract'
      setError(cause)
      return null
    } finally {
      setPending(false)
    }
  }, [api])

  const start = useCallback(async (intake, cache = []) => {
    setPending(true)
    setError(null)
    lastStartRef.current = [intake, cache]
    try {
      const turn = await api.startSession(intake)
      try {
        sessionStorage.setItem(HANDOFF_SESSION_KEY, JSON.stringify(turn.session))
        sessionStorage.setItem(HANDOFF_CACHE_KEY, JSON.stringify(sanitizeCache(cache)))
        sessionStorage.setItem(HANDOFF_ID_KEY, newHandoffId())
      } catch {
        // 저장하지 못하면 의사 화면이 이 상담을 열 수 없다(이전 상담이 열릴 수도 있다) → 완료로 넘기지 않고 알린다.
        for (const key of HANDOFF_KEYS) {
          try { sessionStorage.removeItem(key) } catch { /* 무시 */ }
        }
        setStorageFailed(true)
        return
      }
      lastStartRef.current = null
      setStorageFailed(false)
      setPhase('done')
    } catch (cause) {
      setError(cause)
    } finally {
      setPending(false)
    }
  }, [api])

  const retry = useCallback(() => (lastStartRef.current ? start(...lastStartRef.current) : undefined), [start])

  const reset = useCallback(() => {
    for (const key of HANDOFF_KEYS) {
      try { sessionStorage.removeItem(key) } catch { /* 무시 */ }
    }
    lastStartRef.current = null
    setError(null)
    setStorageFailed(false)
    setPhase('start')
  }, [])

  return { phase, health, error, pending, storageFailed, begin, extract, start, retry, reset, canRetry: Boolean(lastStartRef.current) }
}
