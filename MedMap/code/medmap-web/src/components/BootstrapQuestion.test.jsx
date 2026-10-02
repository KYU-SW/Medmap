import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import BootstrapQuestion from './BootstrapQuestion'

test('한 번에 한 문항, 있음/없음/잘 모르겠어요', async () => {
  const user = userEvent.setup()
  const onAnswer = vi.fn()
  render(<BootstrapQuestion evidenceId="E_53" remaining={2} onAnswer={onAnswer} />)
  expect(screen.getByTestId('bootstrap-question')).toHaveTextContent('이번에 진료를 받으려는 이유와 관련해서 어딘가 통증이 있나요?')
  expect(screen.getByText('시작 전에 2가지만 더 확인할게요')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: '잘 모르겠어요' }))
  expect(onAnswer).toHaveBeenCalledWith({ question_id: 'E_53', kind: 'UNKNOWN', value: null })
})
