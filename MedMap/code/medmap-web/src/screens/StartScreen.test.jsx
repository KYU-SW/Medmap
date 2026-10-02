import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import StartScreen from './StartScreen'

test('서비스 설명과 시작 버튼을 보여준다', () => {
  render(<StartScreen ready onStart={() => {}} />)
  expect(screen.getByText('증상을 한 번에 판단하지 않습니다. 확인이 필요한 정보를 하나씩 좁혀갑니다.')).toBeInTheDocument()
  expect(screen.getByText('의료 행위가 아니며 진료를 대신하지 않습니다.')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '시작하기' })).toBeEnabled()
})

test('서버가 준비되지 않으면 시작 버튼이 비활성이고 안내가 보인다', () => {
  render(<StartScreen ready={false} checking={false} onStart={() => {}} />)
  expect(screen.getByRole('button', { name: '시작하기' })).toBeDisabled()
  expect(screen.getByText('준비 중입니다. 잠시 후 다시 시도해 주세요.')).toBeInTheDocument()
})

test('시작 버튼을 누르면 onStart 가 호출된다', async () => {
  const onStart = vi.fn()
  render(<StartScreen ready onStart={onStart} />)
  await userEvent.click(screen.getByRole('button', { name: '시작하기' }))
  expect(onStart).toHaveBeenCalledTimes(1)
})
