import { render, screen, waitFor } from '@testing-library/react'
import App from './App'

beforeEach(() => {
  sessionStorage.clear()
  vi.stubGlobal('fetch', vi.fn(async () => ({
    ok: true, status: 200, json: async () => ({ status: 'ok', engine_ready: true, max_questions: 3 }),
  })))
})

test('앱이 헤더와 시작 화면을 렌더링한다', async () => {
  render(<App />)
  expect(document.querySelector('.app-header__brand')).toHaveTextContent('MedMap')
  await waitFor(() => expect(screen.getByRole('button', { name: '시작하기' })).toBeEnabled())
})
