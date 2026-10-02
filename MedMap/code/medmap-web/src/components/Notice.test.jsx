import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Notice from './Notice'

test('재시도 버튼을 보여준다', async () => {
  const onRetry = vi.fn()
  render(<Notice message={{ title: '연결하지 못했습니다.', body: '잠시 후 다시 시도해 주세요.', action: 'retry' }} onRetry={onRetry} />)
  expect(screen.getByRole('alert')).toHaveTextContent('연결하지 못했습니다.')
  await userEvent.click(screen.getByRole('button', { name: '다시 시도' }))
  expect(onRetry).toHaveBeenCalled()
})

test('다시 시작 액션이면 처음부터 다시 버튼을 보여준다', () => {
  render(<Notice message={{ title: 'x', body: 'y', action: 'restart' }} onRestart={() => {}} />)
  expect(screen.getByRole('button', { name: '처음부터 다시' })).toBeInTheDocument()
})

test('pending 이면 다시 시도 버튼이 비활성화된다', () => {
  render(<Notice message={{ title: '연결하지 못했습니다.', action: 'retry' }} onRetry={() => {}} pending />)
  expect(screen.getByRole('button', { name: '다시 시도' })).toBeDisabled()
})
