import { useCallback, useEffect, useRef, useState } from 'react'
import * as defaultApi from '../api/client.js'
import { cachedAnswerFor, clearCache, loadCache, saveCache, withoutEvidence } from '../intake/answerCache.js'
import { historyQuestionLabel, valueLabel } from '../terminology/labels.js'

const SESSION_KEY = 'medmap.session'

export function useMedmapSession({ api = defaultApi } = {}) {
  const [phase, setPhase] = useState('start')
  const [turn, setTurn] = useState(null)
  const [health, setHealth] = useState({ engine_ready: false, max_questions: 3 })
  const [error, setError] = useState(null)
  const [pending, setPending] = useState(false)
  const [history, setHistory] = useState([])
  const [autoApplied, setAutoApplied] = useState([])
  const [summary, setSummary] = useState(null)
  const [summaryState, setSummaryState] = useState('idle')
  const cacheRef = useRef([])
  // summary 는 세션에 저장하지 않는다(메모리 전용). 이 세션으로 이미 성공한 요청인지만 여기 표시해 중복 호출을 막는다.
  const summarySessionKeyRef = useRef(null)
  const summaryPendingRef = useRef(false)
  const summaryRequestIdRef = useRef(0)   // reset·새 요청이 이전 요청 응답을 무효화한다

  // 마지막으로 실패한 action(메모리 전용, 저장소에 남기지 않음). "다시 시도" = 이 action 을 같은 인자로 재실행.
  const lastFailedRef = useRef(null)
  // 현재 error 가 어디서 왔는지(health/action/extract). canRetry 판정에만 쓴다.
  const errorKindRef = useRef(null)
  // pending 은 state 라 재조회 시 stale 할 수 있어(더블클릭), ref 로도 동시에 보관한다.
  const pendingRef = useRef(false)
  const markPending = useCallback((value) => {
    pendingRef.current = value
    setPending(value)
  }, [])

  useEffect(() => {
    let alive = true
    api.getHealth()
      .then((value) => { if (alive) { errorKindRef.current = null; setHealth(value) } })
      .catch((cause) => { if (alive) { errorKindRef.current = 'health'; setError(cause) } })
    return () => { alive = false }
  }, [api])


  const applyTurn = useCallback((next) => {
    setTurn(next)
    setPhase(next.next_question ? 'consult' : 'summary')
    try { sessionStorage.setItem(SESSION_KEY, JSON.stringify(next.session)) } catch { /* 저장 실패는 무시 */ }
  }, [])

  // "현재까지 확인된 정보" 요약. 같은 세션으로 이미 성공했으면 다시 부르지 않는다(summarySessionKeyRef).
  const runSummary = useCallback(async (session) => {
    if (summaryPendingRef.current) return
    summaryPendingRef.current = true
    const requestId = ++summaryRequestIdRef.current
    const stale = () => summaryRequestIdRef.current !== requestId
    setSummaryState('loading')
    const key = JSON.stringify(session)
    try {
      const result = await api.getSummary(session)
      if (stale()) return          // reset 뒤 늦게 도착한 응답은 버린다(새 화면·새 세션을 덮지 않는다)
      summarySessionKeyRef.current = key
      setSummary(result)
      setSummaryState('ready')
    } catch (cause) {
      if (stale()) return          // 늦게 도착한 4xx 가 새 세션 저장본을 지우지 않도록
      const transient = cause?.code === 'NETWORK_ERROR' || (cause?.status ?? 0) >= 500
      if (transient) {
        // 네트워크·서버 오류: 세션·cache 를 보존하고 다시 시도할 수 있게 둔다.
        setSummaryState('error')
      } else {
        // 4xx(세션 자체가 무효): resume 4xx 와 같은 정책 — 조용히 버리고 시작 화면으로 되돌린다.
        console.error('[medmap] summary failed', cause?.code ?? cause?.message)
        try { sessionStorage.removeItem(SESSION_KEY) } catch { /* 무시 */ }
        clearCache()
        cacheRef.current = []
        summarySessionKeyRef.current = null
        setSummary(null)
        setSummaryState('idle')
        setTurn(null)
        setPhase('start')
      }
    } finally {
      if (!stale()) summaryPendingRef.current = false
    }
  }, [api])

  // phase 가 summary 가 되는 모든 경로(answer/start/settle 종료, resume 로 summary 복원)에서 한 번만 호출한다.
  useEffect(() => {
    if (phase !== 'summary' || !turn?.session) return
    const key = JSON.stringify(turn.session)
    if (summarySessionKeyRef.current === key || summaryPendingRef.current) return
    runSummary(turn.session)
  }, [phase, turn, runSummary])

  const retrySummary = useCallback(() => {
    if (summaryPendingRef.current || !turn?.session) return undefined
    return runSummary(turn.session)
  }, [turn, runSummary])

  // 엔진이 방금 제안한 질문이 확인 cache 에 있을 때만 그 답을 /session/answer 로 제출한다.
  // 제안되지 않은 항목은 미리 제출하지 않고, posterior 는 건드리지 않는다. 적용도 질문 예산 1개를 쓴다.
  const settle = useCallback(async (first) => {
    let next = first
    const applied = []
    try {
      for (;;) {
        const hit = cachedAnswerFor(cacheRef.current, next.next_question)
        if (!hit) break
        const asked = next.next_question
        next = await api.submitAnswer({ session: next.session, questionId: asked.question_id, kind: hit.kind, value: null })
        try { sessionStorage.setItem(SESSION_KEY, JSON.stringify(next.session)) } catch { /* 저장 실패는 무시 */ }
        cacheRef.current = saveCache(withoutEvidence(cacheRef.current, asked.question_id))
        applied.push({ question: historyQuestionLabel(asked), answer: describeAnswer(asked, hit.kind, null) })
      }
      return { next, applied, failure: null }
    } catch (cause) {
      return { next, applied, failure: cause }     // 마지막으로 성공한 턴은 유지한다
    }
  }, [api])

  const finish = useCallback(({ next, applied, failure }) => {
    applyTurn(next)
    if (applied.length) setHistory((prev) => [...prev, ...applied])
    setAutoApplied(applied)
    if (failure) setError(failure)
  }, [applyTurn])

  // 새로고침 복귀: 저장된 세션이 있으면 서버에 복원을 요청한다(세션 source of truth 는 여전히 서버 응답).
  // aliveCheck 는 mount effect 에서 unmount 이후 setState 를 막기 위해서만 쓰고, retry() 재실행에는 필요 없다(항상 true).
  const runResume = useCallback(async (session, aliveCheck = () => true) => {
    markPending(true)
    setError(null)
    try {
      const next = await api.resumeSession(session)
      if (!aliveCheck()) return
      cacheRef.current = loadCache()
      const result = await settle(next)
      if (!aliveCheck()) return
      finish(result)
      lastFailedRef.current = null
      errorKindRef.current = null
    } catch (cause) {
      if (!aliveCheck()) return
      const transient = cause?.code === 'NETWORK_ERROR' || (cause?.status ?? 0) >= 500
      if (transient) {
        // 네트워크·서버 오류: 데이터 손실을 막기 위해 저장된 세션·cache 를 지우지 않는다. 사용자가 다시 시도할 수 있다.
        lastFailedRef.current = { type: 'resume', args: [session] }
        errorKindRef.current = 'action'
        setError(cause)
      } else {
        // 4xx(세션 자체가 무효): 더 이상 이어갈 수 없는 저장본이므로 조용히 버리고 시작 화면에 머문다(오류 문구로 놀래지 않는다).
        console.error('[medmap] resume failed', cause?.code ?? cause?.message)
        try { sessionStorage.removeItem(SESSION_KEY) } catch { /* 무시 */ }
        clearCache()
        cacheRef.current = []
        lastFailedRef.current = null
        errorKindRef.current = null
      }
    } finally {
      if (aliveCheck()) markPending(false)
    }
  }, [api, settle, finish, markPending])

  useEffect(() => {
    let alive = true
    let stored = null
    try { stored = sessionStorage.getItem(SESSION_KEY) } catch { stored = null }
    if (!stored) {
      clearCache()                    // 세션 없이 남은 cache 는 쓸 곳이 없다
      return undefined
    }
    let session
    try { session = JSON.parse(stored) } catch { session = null }
    if (!session) {
      try { sessionStorage.removeItem(SESSION_KEY) } catch { /* 무시 */ }
      clearCache()
      return undefined
    }
    runResume(session, () => alive)
    return () => { alive = false }
  }, [runResume])

  const begin = useCallback(() => {
    setError(null)
    setPhase('intake')
  }, [])

  // 자유문장 → 후보. 원문은 요청에만 쓰고 어디에도 보관하지 않는다. 실패하면 null.
  // extract 실패는 재실행 대상이 아니다(원문을 hook 에 보관하지 않는다) — error.source='extract' 로 표시만 한다.
  const extract = useCallback(async (text) => {
    markPending(true)
    setError(null)
    try {
      const body = await api.extractIntake(text)
      return body.candidates
    } catch (cause) {
      errorKindRef.current = 'extract'
      cause.source = 'extract'
      setError(cause)
      return null
    } finally {
      markPending(false)
    }
  }, [api, markPending])

  const start = useCallback(async (intake, cache = [], intakeHistory = []) => {
    markPending(true)
    setError(null)
    try {
      const next = await api.startSession(intake)
      cacheRef.current = saveCache(cache)          // start 성공 뒤에만 저장
      setHistory(intakeHistory)                    // bootstrap 응답(잘 모르겠어요 포함)을 사용자 응답으로 기록
      finish(await settle(next))
      lastFailedRef.current = null
      errorKindRef.current = null
    } catch (cause) {
      lastFailedRef.current = { type: 'start', args: [intake, cache, intakeHistory] }
      errorKindRef.current = 'action'
      setError(cause)
    } finally {
      markPending(false)
    }
  }, [api, settle, finish, markPending])

  // 실패 당시의 session·question 을 그대로 보관해 재전송한다(stateless API 라 재전송은 안전).
  const runAnswer = useCallback(async ({ session, question, kind, value }) => {
    markPending(true)
    setError(null)
    try {
      const next = await api.submitAnswer({ session, questionId: question.question_id, kind, value })
      setHistory((prev) => [...prev, { question: historyQuestionLabel(question), answer: describeAnswer(question, kind, value) }])
      finish(await settle(next))
      lastFailedRef.current = null
      errorKindRef.current = null
    } catch (cause) {
      lastFailedRef.current = { type: 'answer', args: [{ session, question, kind, value }] }
      errorKindRef.current = 'action'
      setError(cause)
    } finally {
      markPending(false)
    }
  }, [api, settle, finish, markPending])

  const answer = useCallback(({ kind, value }) => {
    if (!turn?.next_question) return Promise.resolve()
    return runAnswer({ session: turn.session, question: turn.next_question, kind, value })
  }, [turn, runAnswer])

  const reset = useCallback(() => {
    setTurn(null)
    setHistory([])
    setAutoApplied([])
    setError(null)
    setPhase('start')
    setSummary(null)
    setSummaryState('idle')
    summarySessionKeyRef.current = null
    summaryPendingRef.current = false
    summaryRequestIdRef.current += 1
    lastFailedRef.current = null
    errorKindRef.current = null
    try { sessionStorage.removeItem(SESSION_KEY) } catch { /* 무시 */ }
    clearCache()
    cacheRef.current = []
  }, [])

  const retryHealth = useCallback(async () => {
    setError(null)
    try {
      setHealth(await api.getHealth())
      errorKindRef.current = null
    } catch (cause) {
      errorKindRef.current = 'health'
      setError(cause)
    }
  }, [api])

  // "다시 시도" = 마지막으로 실패한 action 을 같은 인자로 재실행. 실패한 action 이 없으면 health 재확인.
  // pendingRef 로 확인해 더블클릭으로 같은 요청이 두 번 나가지 않게 한다.
  const retry = useCallback(() => {
    if (pendingRef.current) return undefined
    const failed = lastFailedRef.current
    if (!failed) return retryHealth()
    if (failed.type === 'start') return start(...failed.args)
    if (failed.type === 'answer') return runAnswer(...failed.args)
    if (failed.type === 'resume') return runResume(...failed.args)
    return undefined
  }, [retryHealth, start, runAnswer, runResume])

  const canRetry = lastFailedRef.current !== null || errorKindRef.current === 'health'

  return {
    phase, turn, health, error, pending, history, autoApplied,
    summary, summaryState, retrySummary,
    begin, extract, start, answer, reset, retryHealth, retry, canRetry,
  }
}

export function describeAnswer(question, kind, value) {
  if (kind === 'POSITIVE') return '예'
  if (kind === 'NEGATIVE') return '아니요'
  if (kind === 'UNKNOWN') return '잘 모르겠어요'
  const labels = (value ?? []).map((code) => question.choices.find((c) => c.value === code)?.label ?? valueLabel(code) ?? code)
  return labels.join(', ')
}
