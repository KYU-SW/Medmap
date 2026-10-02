import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import EvidenceConfirmation from './EvidenceConfirmation'

const candidates = [
  { evidence_id: 'E_201', status: 'POSITIVE', label_ko: '기침이 있나요?', matched_text: '기침', initial_eligible: true },
  { evidence_id: 'E_91', status: 'NEGATIVE', label_ko: '열이 있나요? (느낌으로든 체온계로 잰 것이든)', matched_text: '열은 없어요', initial_eligible: false },
  { evidence_id: 'E_77', status: 'POSITIVE', label_ko: '가래?', matched_text: '가래도 누렇', initial_eligible: true },
]

test('매퍼 상태가 기본 선택이고, 확인한 것만 넘긴다(빼기 제외, 변경 반영)', async () => {
  const user = userEvent.setup()
  const onConfirm = vi.fn()
  render(<EvidenceConfirmation candidates={candidates} onConfirm={onConfirm} />)
  expect(screen.getByText('말씀하신 내용에서 다음 항목을 확인했어요')).toBeInTheDocument()
  const items = screen.getAllByTestId('confirm-item')
  expect(items).toHaveLength(3)
  expect(within(items[0]).getByRole('button', { name: '있음' })).toHaveAttribute('aria-pressed', 'true')
  expect(within(items[1]).getByRole('button', { name: '없음' })).toHaveAttribute('aria-pressed', 'true')
  await user.click(within(items[0]).getByRole('button', { name: '없음' }))
  await user.click(within(items[2]).getByRole('button', { name: '빼기' }))
  await user.click(screen.getByRole('button', { name: '다음' }))
  expect(onConfirm).toHaveBeenCalledWith([
    { evidence_id: 'E_201', status: 'NEGATIVE' },
    { evidence_id: 'E_91', status: 'NEGATIVE' },
  ])
})

test('신뢰도·내부 코드는 보이지 않는다', () => {
  render(<EvidenceConfirmation candidates={candidates} onConfirm={() => {}} />)
  expect(document.body.textContent).not.toMatch(/HIGH|confidence|E_\d+|MEDMAP_/)
})
