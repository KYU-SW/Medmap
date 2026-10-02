import { render, screen } from '@testing-library/react'
import AppHeader from './AppHeader'

test('진행 상태를 n / 3 으로 표시한다', () => {
  render(<AppHeader step={2} total={3} />)
  expect(screen.getByText('MedMap')).toBeInTheDocument()
  expect(screen.getByText('추가 확인')).toBeInTheDocument()
  expect(screen.getByText('2 / 3')).toBeInTheDocument()
})

test('진행 점은 채워진 수만큼 data-filled 를 가진다', () => {
  render(<AppHeader step={2} total={3} />)
  const dots = screen.getAllByTestId('progress-dot')
  expect(dots).toHaveLength(3)
  expect(dots.filter((d) => d.dataset.filled === 'true')).toHaveLength(2)
})
