import { render, screen, within } from '@testing-library/react'
import PatientSummarySection from './PatientSummarySection.jsx'
import { COPY } from '../copy.js'

// Phase 2a(2026-10-02): 환자가 확인한 소견을 IG 선택과 무관하게 모두 보인다 — 표시만, 모델 입력·cache 의미 불변.
const SUMMARY = {
  age: 45, sex: 'M', chief_complaint: { question_id: 'E_53', label_ko: '통증', question_ko: '통증이 있나요?' },
  confirmed_positive: [{ question_id: 'E_66', question_ko: '숨이 차나요?', answer_ko: '예' }],
  confirmed_negative: [{ question_id: 'E_91', question_ko: '열이 있나요?', answer_ko: '아니요' }],
  confirmed_values: [{ question_id: 'E_56', question_ko: '통증 강도', answer_ko: '7' }],
  not_applicable: [{ question_id: 'E_57', question_ko: '통증이 퍼지나요?', answer_ko: '해당 없음' }],
  unknown: [{ question_id: 'E_204', question_ko: '최근 여행?', answer_ko: '잘 모르겠어요' }],
  answered_questions: [{ question_id: 'E_53' }, { question_id: 'E_66' }, { question_id: 'E_91' }, { question_id: 'E_56' },
    { question_id: 'E_57' }, { question_id: 'E_204' }],
  questions_used: 0,
}

test('모델에 반영된 소견 · 반영되지 않은 확인 소견 · 확인되지 않음을 구분한다', () => {
  render(<PatientSummarySection summary={SUMMARY} cache={[
    { evidence_id: 'E_201', status: 'POSITIVE' }, { evidence_id: 'E_77', status: 'NEGATIVE' }]} />)
  const applied = screen.getByTestId('doctor-findings-applied')
  expect(within(applied).getByText(COPY.appliedTitle)).toBeInTheDocument()
  expect(within(applied).getByText('숨이 차나요?')).toBeInTheDocument()
  expect(within(applied).getByText('열이 있나요?')).toBeInTheDocument()
  expect(within(applied).getByText('통증 강도')).toBeInTheDocument()
  expect(within(applied).getByRole('heading', { name: COPY.notApplicable })).toBeInTheDocument()            // 이전에는 그리지 않던 칸
  expect(within(applied).getByText('통증이 퍼지나요?')).toBeInTheDocument()

  const unapplied = screen.getByTestId('doctor-findings-unapplied')
  expect(within(unapplied).getByText(COPY.unappliedTitle)).toBeInTheDocument()
  expect(within(unapplied).getByText(COPY.unappliedNote)).toBeInTheDocument()
  expect(within(within(unapplied).getByTestId('unapplied-positive')).getByText('기침이 있나요?')).toBeInTheDocument()
  expect(within(within(unapplied).getByTestId('unapplied-negative'))
    .getByText('평소보다 색이 있거나 양이 많은 가래가 나오는 기침을 하나요?')).toBeInTheDocument()

  // UNKNOWN 은 확인 소견 묶음에 섞이지 않는다
  const unknown = screen.getByTestId('doctor-findings-unknown')
  expect(within(unknown).getByText('최근 여행?')).toBeInTheDocument()
  expect(within(applied).queryByText('최근 여행?')).toBeNull()
  expect(within(unapplied).queryByText('최근 여행?')).toBeNull()
})

test('이미 모델에 반영된 질문은 반영되지 않은 목록에 중복 표시하지 않는다', () => {
  render(<PatientSummarySection summary={SUMMARY} cache={[{ evidence_id: 'E_91', status: 'NEGATIVE' }]} />)
  expect(screen.queryByTestId('doctor-findings-unapplied')).toBeNull()
})

test('cache 가 비면 반영되지 않은 묶음을 그리지 않고, 라벨 없는 항목은 내부 ID 를 보이지 않는다', () => {
  const { container } = render(<PatientSummarySection summary={SUMMARY} cache={[{ evidence_id: 'E_99999', status: 'POSITIVE' }]} />)
  expect(screen.queryByTestId('doctor-findings-unapplied')).toBeNull()
  expect(container.textContent).not.toContain('E_99999')
  render(<PatientSummarySection summary={SUMMARY} />)
})
