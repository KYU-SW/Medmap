// Doctor Mode API(/v1/doctor/*). 기존 client.js 의 request/post 를 그대로 쓴다.
import { post, request } from './client.js'

export function getDoctorDiagnoses() {
  return request('/v1/doctor/diagnoses', { method: 'GET' })
}

export function getDoctorView({ session, workingDiagnosis }) {
  return post('/v1/doctor/view', { session, working_diagnosis: workingDiagnosis })
}

export function submitDoctorAnswer({ session, workingDiagnosis, questionId, kind, value }) {
  return post('/v1/doctor/answer', {
    session,
    working_diagnosis: workingDiagnosis,
    submission: { question_id: questionId, answer: { kind, value: kind === 'VALUE' ? value : null } },
  })
}
