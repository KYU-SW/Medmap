import { render, screen } from '@testing-library/react'
import ConsultScreen from './screens/ConsultScreen'
import AppHeader from './components/AppHeader'
import turnStart from './test/fixtures/turn.start.json'

test('질문 영역은 스크린리더에 변경을 알린다', () => {
  render(<ConsultScreen turn={turnStart} onAnswer={() => {}} />)
  const live = screen.getByTestId('question-live')
  expect(live).toHaveAttribute('aria-live', 'polite')
  expect(live).toHaveTextContent(turnStart.next_question.question_ko)
})

test('진행 표시는 접근 가능한 이름을 가진다', () => {
  render(<AppHeader step={1} total={3} />)
  expect(screen.getByLabelText('추가 확인 1 / 3')).toBeInTheDocument()
})

test('선택 버튼은 공통 버튼 클래스를 쓴다(최소 44px 높이)', () => {
  const { container } = render(<ConsultScreen turn={turnStart} onAnswer={() => {}} />)
  const buttons = container.querySelectorAll('.choice')
  expect(buttons.length).toBeGreaterThan(0)
  buttons.forEach((b) => expect(b.className).toContain('button'))
})
