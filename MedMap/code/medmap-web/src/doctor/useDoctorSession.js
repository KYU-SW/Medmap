import { useCallback, useEffect, useRef, useState } from 'react'
import * as defaultApi from '../api/doctorClient.js'
import { sanitizeCache } from '../intake/answerCache.js'
import { perfMark } from '../voice/perf.js'

// 저장 키. Doctor 는 자기 사본(medmap.doctor.*)에만 쓴다. 인계·환자 원본은 읽기만 한다.
export const DOCTOR_SESSION_KEY = 'medmap.doctor.session'
export const DOCTOR_CACHE_KEY = 'medmap.doctor.cache'
export const DOCTOR_WD_KEY = 'medmap.doctor.wd'
export const HANDOFF_SESSION_KEY = 'medmap.handoff.session'
export const HANDOFF_CACHE_KEY = 'medmap.handoff.cache'
export const HANDOFF_ID_KEY = 'medmap.handoff.id'
export const PATIENT_SESSION_KEY = 'medmap.session'
// 사본을 만들 때 보였던 인계·환자 원본(raw 문자열). 원본이 바뀌었으면 새 환자로 보고 사본 대신 새 원본을 연다.
export const DOCTOR_SEEN_KEY = 'medmap.doctor.seen'

const PENDING = { state: 'PENDING' }
const WD_STATES = new Set(['PENDING', 'ENTERED', 'SKIPPED'])

function read(key) {
  try { return JSON.parse(sessionStorage.getItem(key) ?? 'null') } catch { return null }
}

function write(key, value) {
  try { sessionStorage.setItem(key, JSON.stringify(value)) } catch { /* 저장 실패는 무시 — 메모리 상태로 계속 */ }
}

function readRaw(key) {
  try { return sessionStorage.getItem(key) } catch { return null }
}

function parse(raw) {
  try { return JSON.parse(raw ?? 'null') } catch { return null }
}

// 인계는 인계 식별자(없으면 세션 원문)로, 기본 환자 흐름은 세션 원문으로 구분한다.
// 한계: 기본 흐름(medmap.session)은 식별자가 없어 같은 입력을 반복하면 같은 원본으로 보인다(그 hook 은 수정하지 않는다).
function currentOrigins() {
  return { handoff: readRaw(HANDOFF_ID_KEY) ?? readRaw(HANDOFF_SESSION_KEY), patient: readRaw(PATIENT_SESSION_KEY) }
}

function isSession(value) {
  return Boolean(value && typeof value === 'object' && value.schema_version && value.patient_state)
}

// 진입 소스(원본 키에는 쓰지 않는다):
//   1) 사본을 만든 뒤 인계 원본이 새로 생기거나 바뀌었으면 → 새 인계(세션+cache)  (이전 환자 사본을 보여주지 않는다)
//   2) Doctor 사본  3) 인계  4) 기본 환자 흐름 세션(cache 없음). 2)도 기본 흐름 원본이 바뀌었으면 4)로.
export function initialSource() {
  const origins = currentOrigins()
  const handoff = parse(readRaw(HANDOFF_SESSION_KEY))
  const patient = parse(origins.patient)
  const own = read(DOCTOR_SESSION_KEY)
  const seen = read(DOCTOR_SEEN_KEY) ?? {}
  const fromHandoff = { session: handoff, cache: sanitizeCache(read(HANDOFF_CACHE_KEY)), wd: PENDING, origins }
  const fromPatient = { session: patient, cache: [], wd: PENDING, origins }
  if (isSession(own)) {
    if (isSession(handoff) && origins.handoff !== seen.handoff) return fromHandoff
    if (!isSession(handoff) && isSession(patient) && origins.patient !== seen.patient) return fromPatient
    const wd = read(DOCTOR_WD_KEY)
    return { session: own, cache: sanitizeCache(read(DOCTOR_CACHE_KEY)), wd: wd && WD_STATES.has(wd.state) ? wd : PENDING,
      origins: seen }
  }
  if (isSession(handoff)) return fromHandoff
  if (isSession(patient)) return fromPatient
  return null
}

export function useDoctorSession({ api = defaultApi } = {}) {
  const [status, setStatus] = useState('loading')    // loading | load | ready
  const [view, setView] = useState(null)
  const [wd, setWd] = useState(PENDING)
  const [cache, setCache] = useState([])
  const [diagnoses, setDiagnoses] = useState([])
  const [error, setError] = useState(null)
  const [pending, setPending] = useState(false)
  const pendingRef = useRef(false)
  const requestIdRef = useRef(0)       // 새 요청·초기화가 이전 요청의 늦은 응답을 무효화한다
  const lastFailedRef = useRef(null)

  // 반환: true 성공 · false 실패 · undefined 건너뜀(이미 처리 중 또는 무효화됨)
  const run = useCallback(async (action, onSuccess) => {
    if (pendingRef.current) return undefined
    pendingRef.current = true
    setPending(true)
    setError(null)
    const requestId = ++requestIdRef.current
    try {
      const result = await action()
      if (requestIdRef.current !== requestId) return undefined
      onSuccess(result)
      lastFailedRef.current = null
      return true
    } catch (cause) {
      if (requestIdRef.current !== requestId) return undefined
      lastFailedRef.current = { action, onSuccess }
      setError(cause)
      return false
    } finally {
      if (requestIdRef.current === requestId) {
        pendingRef.current = false
        setPending(false)
      }
    }
  }, [])

  const accept = useCallback((next, nextWd, nextCache, origins) => {
    if (origins) write(DOCTOR_SEEN_KEY, origins)
    setView(next)
    setWd(nextWd)
    setCache(nextCache)
    setStatus('ready')
    write(DOCTOR_SESSION_KEY, next.session)
    write(DOCTOR_WD_KEY, nextWd)
    write(DOCTOR_CACHE_KEY, nextCache)
  }, [])

  const open = useCallback((session, nextWd, nextCache, origins) => run(
    () => api.getDoctorView({ session, workingDiagnosis: nextWd }),
    (next) => accept(next, nextWd, nextCache, origins),
  ), [api, run, accept])

  useEffect(() => {
    let alive = true
    api.getDoctorDiagnoses()
      .then((body) => { if (alive) setDiagnoses(body.diagnoses) })
      .catch(() => { /* 검색 목록이 없어도 직접 입력·건너뛰기는 가능 */ })
    const source = initialSource()
    if (!source) {
      setStatus('load')
    } else {
      setStatus('loading')
      // 저장본을 열지 못하면(4xx·네트워크) 오류와 함께 불러오기 화면을 보여준다. 원본 키는 지우지 않는다.
      // StrictMode 이중 effect 에서 두 번째 호출은 건너뛰므로(undefined) 첫 요청 결과로만 판정한다(alive 검사 없음).
      open(source.session, source.wd, source.cache, source.origins).then((ok) => {
        if (ok === false) setStatus('load')
      })
    }
    return () => { alive = false }
  }, [api, open])

  const chooseWorkingDiagnosis = useCallback((nextWd) => {
    if (!view) return undefined
    return run(() => api.getDoctorView({ session: view.session, workingDiagnosis: nextWd }),
      (next) => accept(next, nextWd, cache))
  }, [api, run, accept, view, cache])

  // 의사가 확인한 답만 제출한다(cache 자동 제출 없음). 성공하면 그 질문의 cache 항목을 사본에서만 지운다.
  const answer = useCallback(({ kind, value }) => {
    const question = view?.next_information?.question
    if (!question) return undefined
    const session = view.session
    // M5 계측(숫자만, 동작 무변경): 요청이 실제로 나갈 때 click, 응답 수신 때 response. 렌더는 NextInformationSection 이 기록
    return run(() => {
      perfMark('doctor_answer_click', {})
      return api.submitDoctorAnswer({ session, workingDiagnosis: wd, questionId: question.question_id, kind, value })
    }, (next) => {
      perfMark('doctor_answer_response', {})
      accept(next, wd, cache.filter((e) => e.evidence_id !== question.question_id))
    })
  }, [api, run, accept, view, wd, cache])

  const importSession = useCallback((text) => {
    let parsed
    try { parsed = JSON.parse(text) } catch { parsed = null }
    const session = isSession(parsed) ? parsed : (isSession(parsed?.session) ? parsed.session : null)
    if (!session) return false
    const importedCache = isSession(parsed?.session) ? sanitizeCache(parsed.cache) : []
    run(() => api.getDoctorView({ session, workingDiagnosis: PENDING }),
      (next) => accept(next, PENDING, importedCache, currentOrigins()))
    return true
  }, [api, run, accept])

  const retry = useCallback(() => {
    const failed = lastFailedRef.current
    if (!failed) return undefined
    return run(failed.action, failed.onSuccess)
  }, [run])

  const clear = useCallback(() => {
    requestIdRef.current += 1
    pendingRef.current = false
    setPending(false)
    for (const key of [DOCTOR_SESSION_KEY, DOCTOR_CACHE_KEY, DOCTOR_WD_KEY, DOCTOR_SEEN_KEY]) {
      try { sessionStorage.removeItem(key) } catch { /* 무시 */ }
    }
    setView(null)
    setWd(PENDING)
    setCache([])
    setError(null)
    setStatus('load')
  }, [])

  // 환자 cache 는 binary 답만 담는다 — 기존 cachedAnswerFor 처럼 YES_NO 질문에만 보여준다.
  const patientSaid = view?.next_information?.question?.answer_type === 'YES_NO'
    ? cache.find((e) => e.evidence_id === view.next_information.question.question_id) ?? null
    : null

  return { status, view, wd, cache, patientSaid, diagnoses, error, pending, chooseWorkingDiagnosis, answer,
    importSession, retry, clear }
}
