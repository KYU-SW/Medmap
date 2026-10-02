import { render, screen } from '@testing-library/react'
import CandidatePanel from './CandidatePanel'

const rows = [
  { name: '만성 부비동염', probability: 0.2435, previous: 0.0802, direction: 'up' },
  { name: '기관지염', probability: 0.2415, previous: 0.2513, direction: 'down' },
  { name: '급성 부비동염', probability: 0.2388, previous: 0.2388, direction: 'same' },
]

test('후보 3개를 순위 표기 없이 보여준다', () => {
  render(<CandidatePanel rows={rows} />)
  expect(screen.getByText('현재 확인이 필요한 진단 후보')).toBeInTheDocument()
  expect(screen.getByText('만성 부비동염')).toBeInTheDocument()
  // 0.2435 는 IEEE754 에서 24.349999…% 이므로 소수 한 자리 표기는 24.3% 다(formatPercent 테스트 참고).
  expect(screen.getByText('24.3%')).toBeInTheDocument()
  expect(screen.queryByText('1위')).not.toBeInTheDocument()
})

test('변화 방향을 기호로 표시하고 막대는 확률에 비례한다', () => {
  render(<CandidatePanel rows={rows} />)
  const items = screen.getAllByTestId('candidate-row')
  expect(items[0].querySelector('[data-direction]').dataset.direction).toBe('up')
  expect(items[0].querySelector('.candidate__bar').style.width).toBe('24.35%')
})

test('선 그래프나 canvas 를 쓰지 않는다', () => {
  const { container } = render(<CandidatePanel rows={rows} />)
  expect(container.querySelector('svg')).toBeNull()
  expect(container.querySelector('canvas')).toBeNull()
})

test('이전 값 잔상을 한 번 보여준다', () => {
  render(<CandidatePanel rows={rows} />)
  const ghost = screen.getByTestId('candidate-ghost-만성 부비동염')
  expect(ghost).toHaveTextContent('8.0%')
  expect(ghost.className).toContain('candidate__ghost')
})

test('모델 질환 이름은 한국어 표시명으로 보이고 내부 이름은 key/testid 로만 남는다', () => {
  const modelRows = [
    { name: 'Pneumonia', probability: 0.5, previous: 0.3, direction: 'up' },
    { name: 'Pulmonary neoplasm', probability: 0.2, previous: null, direction: 'same' },
  ]
  render(<CandidatePanel rows={modelRows} />)
  expect(screen.getByText('폐렴')).toBeInTheDocument()
  expect(screen.queryByText('Pneumonia')).not.toBeInTheDocument()
  expect(screen.getByTestId('candidate-ghost-Pneumonia')).toHaveTextContent('30.0%')
  expect(screen.getByText('폐 종양')).toBeInTheDocument()                 // 2026-09-27 직역 확정(이전 review_needed)
  expect(screen.queryByText('Pulmonary neoplasm')).not.toBeInTheDocument()
})
