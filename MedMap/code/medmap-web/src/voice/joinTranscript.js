const TERMINAL_RE = /[.!?。요다죠]$/

// 매퍼는 공백/줄바꿈을 정규화하고 [.!?\n] 또는 [요다죠] 뒤에서 문장을 나눈다.
// 줄바꿈만으로는 서로 다른 발화가 한 문장으로 합쳐져 부정 scope 가 섞일 수 있어
// 필요할 때만 마침표를 보충한다. 기존 입력은 항상 앞에 그대로 남는다(덮어쓰지 않음).
export function joinTranscript(existing, transcript) {
  const trimmedTranscript = (transcript ?? '').trim()
  if (trimmedTranscript === '') return existing

  const trimmedExisting = (existing ?? '').trim()
  if (trimmedExisting === '') return trimmedTranscript

  const existingEnd = (existing ?? '').trimEnd()
  const needsPeriod = !TERMINAL_RE.test(existingEnd)
  return `${existingEnd}${needsPeriod ? '.' : ''}\n${trimmedTranscript}`
}
