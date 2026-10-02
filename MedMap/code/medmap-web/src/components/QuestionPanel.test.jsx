import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import QuestionPanel from './QuestionPanel'

const yesNo = {
  question_id: 'E_155', question_ko: '심장이 빠르게 뛰나요?', question_original: 'Do you feel palpitations?',
  answer_type: 'YES_NO', information_gain: 0.6547, is_fallback: false, explanation: null,
  choices: [
    { value: true, label: '예', original_label: null, is_fallback: false },
    { value: false, label: '아니요', original_label: null, is_fallback: false },
    { value: null, label: '잘 모르겠어요', original_label: null, is_fallback: false },
  ],
}

const multi = {
  question_id: 'E_54', question_ko: '통증이 어떤 느낌인가요?', question_original: 'Characterize your pain:',
  answer_type: 'MULTI_CHOICE', information_gain: 1.6559, is_fallback: false, explanation: null,
  choices: [
    { value: 'V_181', label: '타는 듯한', original_label: 'burning', is_fallback: false },
    { value: 'V_183', label: '묵직한', original_label: 'heavy', is_fallback: false },
    { value: null, label: '잘 모르겠어요', original_label: null, is_fallback: false },
  ],
}

test('질문과 선택지를 보여주고 정보이득은 감춘다', () => {
  render(<QuestionPanel question={yesNo} onAnswer={() => {}} />)
  expect(screen.getByText('추가로 확인할 정보')).toBeInTheDocument()
  expect(screen.getByText('심장이 빠르게 뛰나요?')).toBeInTheDocument()
  expect(screen.queryByText(/bits/)).not.toBeInTheDocument()
  expect(screen.queryByText(/0\.65/)).not.toBeInTheDocument()
})

test('예/아니요는 즉시 제출된다', async () => {
  const onAnswer = vi.fn()
  render(<QuestionPanel question={yesNo} onAnswer={onAnswer} />)
  await userEvent.click(screen.getByRole('button', { name: '아니요' }))
  expect(onAnswer).toHaveBeenCalledWith({ kind: 'NEGATIVE', value: null })
})

test('잘 모르겠어요는 UNKNOWN 으로 제출된다', async () => {
  const onAnswer = vi.fn()
  render(<QuestionPanel question={yesNo} onAnswer={onAnswer} />)
  await userEvent.click(screen.getByRole('button', { name: '잘 모르겠어요' }))
  expect(onAnswer).toHaveBeenCalledWith({ kind: 'UNKNOWN', value: null })
})

test('다중 선택은 여러 개를 고른 뒤 다음으로 제출한다', async () => {
  const user = userEvent.setup()
  const onAnswer = vi.fn()
  render(<QuestionPanel question={multi} onAnswer={onAnswer} />)
  await user.click(screen.getByRole('button', { name: '타는 듯한' }))
  await user.click(screen.getByRole('button', { name: '묵직한' }))
  await user.click(screen.getByRole('button', { name: '다음' }))
  expect(onAnswer).toHaveBeenCalledWith({ kind: 'VALUE', value: ['V_181', 'V_183'] })
})

test('한국어 미매핑 질문은 원문과 안내 라벨을 함께 보여준다', () => {
  render(<QuestionPanel question={{ ...yesNo, question_ko: 'Do you have a cough?', is_fallback: true }} onAnswer={() => {}} />)
  expect(screen.getByText('Do you have a cough?')).toBeInTheDocument()
  expect(screen.getByText('영문 원문')).toBeInTheDocument()
})

test('영문 fallback 질문이면 한국어 짧은 표시명을 제목으로 함께 보여준다', () => {
  const fallback = {
    question_id: 'E_204', question_ko: 'Have you traveled out of the country in the last 4 weeks?',
    question_original: 'Have you traveled out of the country in the last 4 weeks?',
    answer_type: 'SINGLE_CHOICE', information_gain: 0.1, is_fallback: true, explanation: null,
    choices: [
      { value: 'V_7', label: '동남아시아', original_label: 'South East Asia', is_fallback: false },
      { value: null, label: '잘 모르겠어요', original_label: null, is_fallback: false },
    ],
  }
  render(<QuestionPanel question={fallback} onAnswer={() => {}} />)
  expect(screen.getByTestId('question-short-label')).toHaveTextContent('4주 내 해외여행')
})

test('한국어 질문에는 짧은 표시명 제목을 추가하지 않는다', () => {
  render(<QuestionPanel question={yesNo} onAnswer={() => {}} />)
  expect(screen.queryByTestId('question-short-label')).not.toBeInTheDocument()
})
