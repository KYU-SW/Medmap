const BASE = import.meta.env?.VITE_MEDMAP_API ?? ''
export const MODEL_CONTEXT = 'k3'

export class ApiError extends Error {
  constructor(status, code, message, field = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.field = field
  }
}

export async function request(path, options) {
  let response
  try {
    response = await fetch(`${BASE}${path}`, options)
  } catch (cause) {
    throw new ApiError(0, 'NETWORK_ERROR', String(cause))
  }
  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    const error = payload?.error ?? {}
    throw new ApiError(response.status, error.code ?? 'UNKNOWN_ERROR', error.message ?? 'request failed', error.field ?? null)
  }
  return payload
}

export function post(path, body) {
  return request(path, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export function getHealth() {
  return request('/health', { method: 'GET' })
}

export function startSession({ age, sex, initialEvidence, answers }) {
  return post('/v1/session/start', {
    age,
    sex,
    model_context: MODEL_CONTEXT,
    initial_evidence: initialEvidence,
    answers,
  })
}

export function submitAnswer({ session, questionId, kind, value }) {
  return post('/v1/session/answer', {
    session,
    submission: { question_id: questionId, answer: { kind, value: kind === 'VALUE' ? value : null } },
  })
}

export function resumeSession(session) {
  return post('/v1/session/resume', { session })
}

export function getSummary(session) {
  return post('/v1/session/summary', { session })
}

export function extractIntake(text) {
  return post('/v1/intake/extract', { text })
}

export function transcribeAudio(blob) {
  return request('/v1/stt/transcribe', {
    method: 'POST',
    headers: { 'content-type': blob.type || 'audio/webm' },
    body: blob,
  })
}

// Streaming STT(opt-in 서버 플래그). 실패하면 호출자가 streaming 을 끈 것으로 본다.
export function getSttStatus() {
  return request('/v1/stt/status', { method: 'GET' })
}

// Whisper 로드만 미리 시작(멱등). 오디오와 무관.
export function prewarmStt() {
  return post('/v1/stt/prewarm', {})
}
