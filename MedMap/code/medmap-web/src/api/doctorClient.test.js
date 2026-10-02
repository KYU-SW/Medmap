import { getDoctorDiagnoses, getDoctorView, submitDoctorAnswer } from './doctorClient.js'

function stubFetch() {
  const calls = []
  vi.stubGlobal('fetch', vi.fn(async (url, init) => {
    calls.push({ url, method: init?.method, body: init?.body ? JSON.parse(init.body) : null })
    return { ok: true, status: 200, json: async () => ({}) }
  }))
  return calls
}

test('doctor client request shapes', async () => {
  const calls = stubFetch()
  await getDoctorDiagnoses()
  await getDoctorView({ session: { s: 1 }, workingDiagnosis: { state: 'PENDING' } })
  await submitDoctorAnswer({ session: { s: 1 }, workingDiagnosis: { state: 'SKIPPED' }, questionId: 'E_1', kind: 'POSITIVE', value: ['x'] })
  await submitDoctorAnswer({ session: { s: 1 }, workingDiagnosis: { state: 'SKIPPED' }, questionId: 'E_2', kind: 'VALUE', value: ['V_1'] })
  expect(calls[0]).toMatchObject({ url: '/v1/doctor/diagnoses', method: 'GET' })
  expect(calls[1]).toMatchObject({ url: '/v1/doctor/view', body: { session: { s: 1 }, working_diagnosis: { state: 'PENDING' } } })
  expect(calls[2].body.submission).toEqual({ question_id: 'E_1', answer: { kind: 'POSITIVE', value: null } })
  expect(calls[3].body.submission).toEqual({ question_id: 'E_2', answer: { kind: 'VALUE', value: ['V_1'] } })
})

test('errors keep the existing ApiError envelope', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 409,
    json: async () => ({ error: { code: 'MEDMAP_WORKING_DIAGNOSIS_PENDING', message: 'm', field: 'working_diagnosis' } }) })))
  await expect(getDoctorView({ session: {}, workingDiagnosis: {} })).rejects.toMatchObject({
    status: 409, code: 'MEDMAP_WORKING_DIAGNOSIS_PENDING', field: 'working_diagnosis' })
})
