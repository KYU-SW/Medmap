import { render, screen } from '@testing-library/react'
import ConsultScreen from './ConsultScreen'
import turnStart from '../test/fixtures/turn.start.json'

test('환자 화면: 질문만 보이고 진단 후보·확률은 보이지 않는다(진단 후보는 의사 화면 전용)', () => {
  const { container } = render(<ConsultScreen turn={turnStart} onAnswer={() => {}} />)
  expect(screen.getByText('추가로 확인할 정보')).toBeInTheDocument()
  expect(screen.queryByText('현재 확인이 필요한 진단 후보')).not.toBeInTheDocument()
  expect(screen.queryAllByTestId('candidate-row')).toHaveLength(0)
  expect(container.textContent).not.toMatch(/\d+(\.\d+)?\s*%/)
})
