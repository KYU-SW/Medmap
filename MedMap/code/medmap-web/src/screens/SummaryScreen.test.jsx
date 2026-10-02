import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SummaryScreen from './SummaryScreen'
import turnStart from '../test/fixtures/turn.start.json'
import summaryFixture from '../test/fixtures/summary.v1.json'

const turn = { ...turnStart, next_question: null, stop_reason: 'MAX_QUESTIONS', questions_asked_in_session: 3 }

test('최종 진단이라고 말하지 않고 현재까지 확인된 정보로 정리한다', () => {
  render(<SummaryScreen turn={turn} summary={summaryFixture} summaryState="ready" onRetrySummary={() => {}} onRestart={() => {}} />)
  expect(screen.getByText('현재까지 확인된 정보')).toBeInTheDocument()
  expect(screen.queryByText(/최종 진단/)).not.toBeInTheDocument()
  expect(screen.queryByText(/확정 진단/)).not.toBeInTheDocument()
  expect(screen.getByText('열이 있나요? (느낌으로든 체온계로 잰 것이든)')).toBeInTheDocument()
  expect(screen.getByText('없음')).toBeInTheDocument()
  expect(screen.getByText(`답한 질문 ${summaryFixture.answered_questions.length}개(주 증상 포함) · 추가 확인 3 / 3`)).toBeInTheDocument()
})

test('P3: 목록의 질문과 답 사이에 구분자가 있어 붙어 읽히지 않는다', () => {
  render(<SummaryScreen turn={turn} summary={summaryFixture} summaryState="ready" onRetrySummary={() => {}} onRestart={() => {}} />)
  const item = summaryFixture.confirmed_negative[0]
  const li = screen.getByText(item.question_ko).closest('li')
  expect(li.textContent).toBe(`${item.question_ko} — ${item.answer_ko}`)
  expect(document.body.textContent).not.toContain(`${item.question_ko}${item.answer_ko}`)
})

test('처음부터 다시 버튼이 동작한다', async () => {
  const onRestart = vi.fn()
  render(<SummaryScreen turn={turn} summary={summaryFixture} summaryState="ready" onRetrySummary={() => {}} onRestart={onRestart} />)
  await userEvent.click(screen.getByRole('button', { name: '처음부터 다시' }))
  expect(onRestart).toHaveBeenCalled()
})

test('로딩 중에는 안내 문구와 처음부터 다시만 보이고 진단 후보는 없다', () => {
  render(<SummaryScreen turn={turn} summary={null} summaryState="loading" onRetrySummary={() => {}} onRestart={() => {}} />)
  expect(screen.getByRole('status')).toHaveTextContent('요약을 불러오는 중입니다.')
  expect(screen.queryAllByTestId('candidate-row')).toHaveLength(0)
  expect(screen.getByRole('button', { name: '처음부터 다시' })).toBeInTheDocument()
})

test('오류 시 다시 시도 버튼과 처음부터 다시가 보이고 진단 후보는 없다', async () => {
  const onRetrySummary = vi.fn()
  render(<SummaryScreen turn={turn} summary={null} summaryState="error" onRetrySummary={onRetrySummary} onRestart={() => {}} />)
  const alert = screen.getByRole('alert')
  expect(alert).toHaveTextContent('요약 정보를 불러오지 못했습니다.')
  expect(screen.queryAllByTestId('candidate-row')).toHaveLength(0)
  expect(screen.getByRole('button', { name: '처음부터 다시' })).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: '다시 시도' }))
  expect(onRetrySummary).toHaveBeenCalled()
})

test('빈 섹션은 숨긴다', () => {
  const summary = { ...summaryFixture, confirmed_positive: [], not_applicable: [], unknown: [] }
  render(<SummaryScreen turn={turn} summary={summary} summaryState="ready" onRetrySummary={() => {}} onRestart={() => {}} />)
  expect(screen.queryByText('있다고 확인한 증상')).not.toBeInTheDocument()
  expect(screen.queryByText('해당 없음')).not.toBeInTheDocument()
  expect(screen.queryByText('잘 모르겠다고 답한 질문')).not.toBeInTheDocument()
  expect(screen.getByText('없다고 확인한 증상')).toBeInTheDocument()
})

test('질문 문구는 서버 요약 그대로 렌더하고, 질환명은 환자 화면에 보이지 않는다', () => {
  render(<SummaryScreen turn={turn} summary={summaryFixture} summaryState="ready" onRetrySummary={() => {}} onRestart={() => {}} />)
  expect(screen.getByText('Do you have a rare peripheral tingling sensation?')).toBeInTheDocument()   // fixture 의 서버 문구 그대로
  expect(screen.queryByText('빈혈')).not.toBeInTheDocument()                                          // 진단 후보는 의사 화면 전용
  expect(screen.queryByText('Anemia')).not.toBeInTheDocument()
})

test('안내 문구를 줄바꿈과 함께 보여준다', () => {
  render(<SummaryScreen turn={turn} summary={summaryFixture} summaryState="ready" onRetrySummary={() => {}} onRestart={() => {}} />)
  expect(screen.getByText(/진단 결과가 아니며/)).toBeInTheDocument()
  expect(screen.getByText(/진료 전 참고용으로 정리한 것입니다/)).toBeInTheDocument()
})

test('환자 요약에는 진단 후보 제목·확률이 없다(진단 후보는 의사 화면 전용)', () => {
  const { container } = render(<SummaryScreen turn={turn} summary={summaryFixture} summaryState="ready" onRetrySummary={() => {}} onRestart={() => {}} />)
  expect(screen.queryByText('현재 확인이 필요한 진단 후보')).not.toBeInTheDocument()
  expect(screen.queryAllByTestId('candidate-row')).toHaveLength(0)
  expect(container.textContent).not.toMatch(/\d+(\.\d+)?\s*%/)
})

test('P3: 주 증상이 없는 요약에는 "(주 증상 포함)"을 붙이지 않는다', () => {
  const summary = { ...summaryFixture, chief_complaint: null }
  render(<SummaryScreen turn={turn} summary={summary} summaryState="ready" onRetrySummary={() => {}} onRestart={() => {}} />)
  expect(screen.getByText(`답한 질문 ${summaryFixture.answered_questions.length}개 · 추가 확인 3 / 3`)).toBeInTheDocument()
})
