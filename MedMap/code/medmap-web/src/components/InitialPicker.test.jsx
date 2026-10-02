import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import InitialPicker from './InitialPicker'
import { initialItem } from '../intake/catalog.js'

test('여러 POSITIVE 중 가장 불편한 것 하나를 고른다', async () => {
  const user = userEvent.setup()
  const onPick = vi.fn()
  render(<InitialPicker options={['E_201', 'E_91'].map(initialItem)} onPick={onPick} />)
  expect(screen.getByText('이 중 지금 가장 불편한 증상은 무엇인가요?')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: '열' }))
  expect(onPick).toHaveBeenCalledWith('E_91')
})

test('후보가 없으면 자주 쓰는 8개 + 검색, 96개를 전부 펼치지 않는다', async () => {
  const user = userEvent.setup()
  const onPick = vi.fn()
  render(<InitialPicker options={[]} exclude={[]} onPick={onPick} />)
  expect(within(screen.getByTestId('initial-frequent')).getAllByRole('button')).toHaveLength(8)
  expect(screen.getAllByRole('button').length).toBeLessThan(20)
  await user.type(screen.getByLabelText('증상 찾기'), '목 아픔')
  await user.click(within(screen.getByTestId('initial-results')).getByRole('button', { name: '목 아픔' }))
  expect(onPick).toHaveBeenCalledWith('E_97')
})

test('확인된 항목(NEGATIVE 포함)은 선택지에서 빠진다', async () => {
  const user = userEvent.setup()
  render(<InitialPicker options={[]} exclude={['E_91']} onPick={() => {}} />)
  expect(within(screen.getByTestId('initial-frequent')).queryByRole('button', { name: '열' })).toBeNull()
  await user.type(screen.getByLabelText('증상 찾기'), '열')
  expect(within(screen.getByTestId('initial-results')).queryByRole('button', { name: '열' })).toBeNull()
})

test('검색 결과가 없으면 안내만 하고 종료하지 않는다', async () => {
  const user = userEvent.setup()
  render(<InitialPicker options={[]} exclude={[]} onPick={() => {}} />)
  await user.type(screen.getByLabelText('증상 찾기'), '존재하지않는증상')
  expect(screen.getByText('찾는 증상이 없어요. 다른 말로 찾아보세요.')).toBeInTheDocument()
  expect(document.body.textContent).not.toMatch(/범위 밖|지원하지 않/)
})
