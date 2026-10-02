import { act, render, screen } from '@testing-library/react'
import { Root, routeOf } from './main.jsx'

beforeEach(() => {
  sessionStorage.clear()
  vi.stubGlobal('fetch', vi.fn(async (url) => ({ ok: true, status: 200,
    json: async () => (url === '/health' ? { status: 'ok', engine_ready: true, max_questions: 3 } : { diagnoses: [] }) })))
})
afterEach(() => { window.location.hash = '' })

test('routeOf: only exact hashes switch the entry point', () => {
  expect(routeOf('')).toBe('patient')
  expect(routeOf('#/doctor')).toBe('doctor')
  expect(routeOf('#/handoff')).toBe('handoff')
  expect(routeOf('#/doctor/x')).toBe('patient')
})

test('no hash renders the existing patient app; hashchange remounts the doctor or handoff app', async () => {
  window.location.hash = ''
  render(<Root />)
  expect(await screen.findByText(/추가 확인/)).toBeInTheDocument()      // 기존 AppHeader
  await act(async () => { window.location.hash = '#/doctor'; window.dispatchEvent(new HashChangeEvent('hashchange')) })
  expect(await screen.findByText('의사 화면')).toBeInTheDocument()
  expect(screen.queryByText(/추가 확인 0/)).toBeNull()
  await act(async () => { window.location.hash = '#/handoff'; window.dispatchEvent(new HashChangeEvent('hashchange')) })
  expect(await screen.findByText('진료 전 정리')).toBeInTheDocument()
})
