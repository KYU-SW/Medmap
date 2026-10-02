import { joinTranscript } from './joinTranscript'

test('transcript 가 비면 existing 을 그대로 돌려준다', () => {
  expect(joinTranscript('기침이 나요', '')).toBe('기침이 나요')
  expect(joinTranscript('기침이 나요', '   ')).toBe('기침이 나요')
})

test('existing 이 비어 있으면(공백 포함) transcript 만 trim 해서 넣는다', () => {
  expect(joinTranscript('', '열이 나요')).toBe('열이 나요')
  expect(joinTranscript('   ', '  열이 나요  ')).toBe('열이 나요')
})

test.each(['요', '다', '죠', '.', '!', '?'])('existing 이 %s 로 끝나면 줄바꿈만 넣는다', (ending) => {
  const existing = `기침이 나요${ending}`
  expect(joinTranscript(existing, '열도 있어요')).toBe(`${existing}\n열도 있어요`)
})

test('existing 이 종결 문자로 끝나지 않으면 마침표를 보충한 뒤 줄바꿈을 넣는다', () => {
  expect(joinTranscript('기침', '열도 있어요')).toBe('기침.\n열도 있어요')
})

test('existing 뒤 공백은 trimEnd 되고 transcript 앞뒤 공백은 trim 된다', () => {
  expect(joinTranscript('기침이 나요   ', '  열도 있어요  ')).toBe('기침이 나요\n열도 있어요')
})

test('existing 을 절대 덮어쓰지 않는다(항상 앞에 남는다)', () => {
  const existing = '기존에 적어둔 내용'
  const result = joinTranscript(existing, '새로 말한 내용')
  expect(result.startsWith('기존에 적어둔 내용')).toBe(true)
})
