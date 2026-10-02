import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import NaturalIntakeScreen, { NO_CANDIDATE_MESSAGE, PRESTART_NOTICE, START_INCOMPLETE_MESSAGE, STILL_INCOMPLETE_MESSAGE } from './NaturalIntakeScreen'

const c = (evidence_id, status, label_ko, matched_text, initial_eligible = status === 'POSITIVE') =>
  ({ evidence_id, status, label_ko, matched_text, initial_eligible })

async function describe(user, text) {
  await user.type(screen.getByLabelText('나이'), '45')
  await user.click(screen.getByRole('button', { name: '남성' }))
  await user.type(screen.getByLabelText('지금 불편한 점을 편하게 적어 주세요'), text)
  await user.click(screen.getByRole('button', { name: '확인하기' }))
}

const answerBoot = async (user, label) => user.click(screen.getByRole('button', { name: label }))

test('POSITIVE 1개면 자동 initial, 확인된 NEGATIVE 는 walk 가 도달하면 재사용되고 다시 묻지 않는다(rev3)', async () => {
  const user = userEvent.setup()
  const onStart = vi.fn()
  const onExtract = vi.fn(async () => [c('E_201', 'POSITIVE', '기침이 있나요?', '기침'), c('E_91', 'NEGATIVE', '열이 있나요?', '열은 없어요')])
  render(<NaturalIntakeScreen onExtract={onExtract} onStart={onStart} onRestart={() => {}} />)
  await describe(user, '기침은 나는데 열은 없어요')
  expect(onExtract).toHaveBeenCalledWith('기침은 나는데 열은 없어요')
  expect(screen.queryByLabelText('지금 불편한 점을 편하게 적어 주세요')).toBeNull()   // 입력칸(원문) 사라짐
  await user.click(screen.getByRole('button', { name: '다음' }))
  expect(screen.queryByText('이 중 지금 가장 불편한 증상은 무엇인가요?')).toBeNull()
  expect(screen.getByTestId('bootstrap-question')).toHaveTextContent('통증이 있나요?')     // E_91 은 확인된 NEGATIVE 로 재사용 → E_53 부터 물음
  await answerBoot(user, '없음')      // E_53
  await answerBoot(user, '없음')      // E_66
  const [request, cached, intakeHistory] = onStart.mock.calls[0]
  expect(request).toEqual({
    age: 45, sex: 'M', initialEvidence: 'E_201',
    answers: [
      { question_id: 'E_91', kind: 'NEGATIVE', value: null },
      { question_id: 'E_53', kind: 'NEGATIVE', value: null },
      { question_id: 'E_66', kind: 'NEGATIVE', value: null },
    ],
  })
  expect(cached).toEqual([])
  expect(intakeHistory).toHaveLength(2)
  expect(intakeHistory.map((h) => h.answer)).toEqual(['없음', '없음'])
})

test('후보 0개: 안내 문구 → 검색으로 initial → bootstrap 3', async () => {
  const user = userEvent.setup()
  const onStart = vi.fn()
  render(<NaturalIntakeScreen onExtract={vi.fn(async () => [])} onStart={onStart} onRestart={() => {}} />)
  await describe(user, '그냥 몸이 좀 이상해요')
  expect(screen.getByText(NO_CANDIDATE_MESSAGE)).toBeInTheDocument()
  expect(document.body.textContent).not.toMatch(/증상이 없/)
  await user.click(screen.getByRole('button', { name: '가장 불편한 증상 고르기' }))
  await user.type(screen.getByLabelText('증상 찾기'), '기침')
  await user.click(within(screen.getByTestId('initial-results')).getByRole('button', { name: '기침' }))
  for (const expected of ['열이 있나요?', '통증이 있나요?', '숨이 차거나']) {
    expect(screen.getByTestId('bootstrap-question')).toHaveTextContent(expected)
    await answerBoot(user, '없음')
  }
  const [request, cached] = onStart.mock.calls[0]
  expect(request.initialEvidence).toBe('E_201')
  expect(request.answers.map((a) => a.question_id)).toEqual(['E_91', 'E_53', 'E_66'])
  expect(cached).toEqual([])
})

test('잘 모르겠어요는 개수에 넣지 않고 기록만 한 뒤 예비 질문으로 넘어간다', async () => {
  const user = userEvent.setup()
  const onStart = vi.fn()
  render(<NaturalIntakeScreen onExtract={vi.fn(async () => [])} onStart={onStart} onRestart={() => {}} />)
  await describe(user, '몸이 이상해요')
  await user.click(screen.getByRole('button', { name: '가장 불편한 증상 고르기' }))
  await user.click(within(screen.getByTestId('initial-frequent')).getByRole('button', { name: '기침' }))
  await answerBoot(user, '잘 모르겠어요')                       // E_91
  expect(screen.getByText('시작 전에 3가지만 더 확인할게요')).toBeInTheDocument()
  await answerBoot(user, '없음')                                // E_53
  await answerBoot(user, '없음')                                // E_66
  expect(screen.getByTestId('bootstrap-question')).toHaveTextContent('새로 생긴 피로감')   // E_175(예비)
  await answerBoot(user, '있음')
  const [request, , intakeHistory] = onStart.mock.calls[0]
  expect(request.answers).toEqual([
    { question_id: 'E_53', kind: 'NEGATIVE', value: null },
    { question_id: 'E_66', kind: 'NEGATIVE', value: null },
    { question_id: 'E_175', kind: 'POSITIVE', value: null },
  ])
  expect(intakeHistory[0]).toEqual({ question: '열이 있나요? (느낌으로든 체온계로 잰 것이든)', answer: '잘 모르겠어요' })
})

test('예비까지 써도 채울 수 없으면 START_INCOMPLETE — start 를 부르지 않고, 오류가 아닌 안내를 보여준다', async () => {
  const user = userEvent.setup()
  const onStart = vi.fn()
  const onRestart = vi.fn()
  render(<NaturalIntakeScreen onExtract={vi.fn(async () => [])} onStart={onStart} onRestart={onRestart} />)
  await describe(user, '몸이 이상해요')
  await user.click(screen.getByRole('button', { name: '가장 불편한 증상 고르기' }))
  await user.click(within(screen.getByTestId('initial-frequent')).getByRole('button', { name: '기침' }))
  for (let i = 0; i < 3; i += 1) await answerBoot(user, '잘 모르겠어요')   // E_91·E_53·E_66 → 남은 2개로 3개 불가
  expect(screen.getByText(START_INCOMPLETE_MESSAGE)).toBeInTheDocument()
  expect(screen.queryByRole('alert')).toBeNull()
  expect(screen.queryByTestId('bootstrap-question')).toBeNull()
  expect(onStart).not.toHaveBeenCalled()
  expect(onRestart).not.toHaveBeenCalled()
  await user.click(screen.getByRole('button', { name: '처음부터 다시' }))
  expect(onRestart).toHaveBeenCalledTimes(1)
})

const TYPED = '사흘 전부터 기침이 나요'

// 기침(E_201, 자동 initial) + 확인된 NEGATIVE 가래(E_77, frozen 목록 밖) → E_91·E_53·E_66 모두 잘 모르겠어요 → START_INCOMPLETE
async function reachIncompleteWithCandidates(user, { onStart = vi.fn(), onRestart = vi.fn() } = {}) {
  const found = [c('E_201', 'POSITIVE', '기침이 있나요?', '기침이 나요'), c('E_77', 'NEGATIVE', '가래가 있나요?', '가래는 없고', false)]
  const view = render(<NaturalIntakeScreen onExtract={vi.fn(async () => found)} onStart={onStart} onRestart={onRestart} />)
  await describe(user, TYPED)
  await user.click(screen.getByRole('button', { name: '다음' }))
  for (let i = 0; i < 3; i += 1) await answerBoot(user, '잘 모르겠어요')
  expect(screen.getByText(START_INCOMPLETE_MESSAGE)).toBeInTheDocument()
  return { onStart, onRestart, view }
}

test('START_INCOMPLETE 후 나이·성별·문장·확인 항목·선택 증상·답(잘 모르겠어요 포함)이 화면에 그대로 남는다', async () => {
  const user = userEvent.setup()
  await reachIncompleteWithCandidates(user)
  const recap = screen.getByTestId('intake-recap')
  expect(recap).toHaveTextContent('45세')
  expect(recap).toHaveTextContent('남성')
  expect(recap).toHaveTextContent(TYPED)
  expect(within(recap).getByTestId('recap-confirmed')).toHaveTextContent('기침이 있나요? — 있음')
  expect(within(recap).getByTestId('recap-confirmed')).toHaveTextContent('가래가 있나요? — 없음')
  expect(within(recap).getByTestId('recap-initial')).toHaveTextContent('기침')
  const answers = within(recap).getAllByTestId('recap-answer').map((li) => li.textContent)
  expect(answers).toHaveLength(3)
  expect(answers[0]).toContain('열이 있나요?')
  expect(answers.every((a) => a.includes('잘 모르겠어요'))).toBe(true)
  expect(recap).not.toHaveTextContent('가래는 없고')          // matched_text 는 확인 화면에서만
})

test('START_INCOMPLETE 후 known bootstrap 답도 유지된다', async () => {
  const user = userEvent.setup()
  render(<NaturalIntakeScreen onExtract={vi.fn(async () => [])} onStart={vi.fn()} onRestart={() => {}} />)
  await describe(user, '몸이 이상해요')
  await user.click(screen.getByRole('button', { name: '가장 불편한 증상 고르기' }))
  await user.click(within(screen.getByTestId('initial-frequent')).getByRole('button', { name: '기침' }))
  await answerBoot(user, '없음')             // E_91
  for (let i = 0; i < 3; i += 1) await answerBoot(user, '잘 모르겠어요')   // E_53·E_66·E_175 → E_88 하나로 불가
  const answers = screen.getAllByTestId('recap-answer').map((li) => li.textContent)
  expect(answers).toHaveLength(4)
  expect(answers[0]).toContain('열이 있나요?')
  expect(answers[0]).toContain('없음')
})

test('답변 다시 확인하기: 잘 모르겠어요만 원래 순서로 다시 보여주고, 기본 선택이 없으며, 그대로 두면 끝까지 시작하지 않는다', async () => {
  const user = userEvent.setup()
  const { onStart } = await reachIncompleteWithCandidates(user)
  await user.click(screen.getByRole('button', { name: '답변 다시 확인하기' }))
  const seen = []
  for (let i = 0; i < 3; i += 1) {
    seen.push(screen.getByTestId('bootstrap-question').textContent)
    expect(screen.getByText(/이전 답: 잘 모르겠어요/)).toHaveTextContent(`(${i + 1} / 3)`)
    // 기본 선택 없음: 선택지 3개는 모두 같은 상태의 일반 버튼이고, 누르기 전에는 아무 답도 바뀌지 않는다
    expect(['있음', '없음', '잘 모르겠어요'].map((name) => screen.getByRole('button', { name }).getAttribute('aria-pressed'))).toEqual([null, null, null])
    expect(onStart).not.toHaveBeenCalled()
    await answerBoot(user, '잘 모르겠어요')
  }
  expect(seen[0]).toContain('열이 있나요?')
  expect(seen[1]).toContain('통증이 있나요?')
  expect(seen[2]).toContain('숨이 차거나')
  expect(screen.getByText(STILL_INCOMPLETE_MESSAGE)).toBeInTheDocument()
  expect(onStart).not.toHaveBeenCalled()
  expect(screen.getByTestId('intake-recap')).toHaveTextContent(TYPED)     // 입력은 그대로
  expect(screen.getAllByTestId('recap-answer')).toHaveLength(3)
})

test('답변 다시 확인하기: 사용자가 바꾼 답만 교체되고, 남은 frozen 예비 질문으로 이어서 exact-k3 가 되면 start 1회(UNKNOWN 미포함)', async () => {
  const user = userEvent.setup()
  const { onStart } = await reachIncompleteWithCandidates(user)
  await user.click(screen.getByRole('button', { name: '답변 다시 확인하기' }))
  await answerBoot(user, '없음')             // E_91: 잘 모르겠어요 → 없음
  await answerBoot(user, '잘 모르겠어요')    // E_53: 그대로
  await answerBoot(user, '있음')             // E_66: 잘 모르겠어요 → 있음
  expect(onStart).not.toHaveBeenCalled()
  expect(screen.getByTestId('bootstrap-question')).toHaveTextContent('새로 생긴 피로감')   // E_175(frozen 예비)
  await answerBoot(user, '있음')
  expect(onStart).toHaveBeenCalledTimes(1)
  const [request, cached, intakeHistory] = onStart.mock.calls[0]
  expect(request).toEqual({
    age: 45, sex: 'M', initialEvidence: 'E_201',
    answers: [
      { question_id: 'E_91', kind: 'NEGATIVE', value: null },
      { question_id: 'E_66', kind: 'POSITIVE', value: null },
      { question_id: 'E_175', kind: 'POSITIVE', value: null },
    ],
  })
  expect(JSON.stringify(request)).not.toContain('UNKNOWN')
  expect(cached).toEqual([{ evidence_id: 'E_77', status: 'NEGATIVE' }])
  expect(intakeHistory.map((h) => h.answer)).toEqual(['없음', '잘 모르겠어요', '있음', '있음'])
})

test('답변 다시 확인하기: 바꾼 답으로 exact-k3 가 채워지면 남은 질문 없이 바로 start 1회', async () => {
  const user = userEvent.setup()
  const onStart = vi.fn()
  render(<NaturalIntakeScreen onExtract={vi.fn(async () => [])} onStart={onStart} onRestart={() => {}} />)
  await describe(user, '몸이 이상해요')
  await user.click(screen.getByRole('button', { name: '가장 불편한 증상 고르기' }))
  await user.click(within(screen.getByTestId('initial-frequent')).getByRole('button', { name: '기침' }))
  await answerBoot(user, '없음')             // E_91
  for (let i = 0; i < 3; i += 1) await answerBoot(user, '잘 모르겠어요')   // E_53·E_66·E_175
  await user.click(screen.getByRole('button', { name: '답변 다시 확인하기' }))
  expect(screen.getByTestId('bootstrap-question')).toHaveTextContent('통증이 있나요?')   // E_91 은 known 이라 다시 묻지 않음
  await answerBoot(user, '있음')             // E_53
  expect(onStart).not.toHaveBeenCalled()
  await answerBoot(user, '없음')             // E_66 → E_91·E_53·E_66 로 3개
  expect(onStart).toHaveBeenCalledTimes(1)
  const [request] = onStart.mock.calls[0]
  expect(request.answers.map((a) => [a.question_id, a.kind])).toEqual([['E_91', 'NEGATIVE'], ['E_53', 'POSITIVE'], ['E_66', 'NEGATIVE']])
  expect(request.answers.every((a) => ['E_91', 'E_53', 'E_66', 'E_201', 'E_175', 'E_88'].includes(a.question_id))).toBe(true)
})

test('시작 전 안내 문구는 intake 모든 단계에 작게 보인다(modal 아님)', async () => {
  const user = userEvent.setup()
  render(<NaturalIntakeScreen onExtract={vi.fn(async () => [])} onStart={vi.fn()} onRestart={() => {}} />)
  for (const line of PRESTART_NOTICE.split('\n')) expect(screen.getByTestId('prestart-notice')).toHaveTextContent(line)
  expect(screen.queryByRole('dialog')).toBeNull()
  await describe(user, '몸이 이상해요')
  expect(screen.getByTestId('prestart-notice')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: '가장 불편한 증상 고르기' }))
  await user.click(within(screen.getByTestId('initial-frequent')).getByRole('button', { name: '기침' }))
  expect(screen.getByTestId('bootstrap-question')).toBeInTheDocument()
  expect(screen.getByTestId('prestart-notice')).toBeInTheDocument()
})

const unloadPrevented = () => {
  const event = new Event('beforeunload', { cancelable: true })
  window.dispatchEvent(event)
  return event.defaultPrevented
}

test('beforeunload: 입력 전에는 등록하지 않고, 입력이 생기면 등록, unmount 하면 제거', async () => {
  const user = userEvent.setup()
  const { unmount } = render(<NaturalIntakeScreen onExtract={vi.fn(async () => [])} onStart={vi.fn()} onRestart={() => {}} />)
  expect(unloadPrevented()).toBe(false)
  await user.type(screen.getByLabelText('지금 불편한 점을 편하게 적어 주세요'), '기')
  expect(unloadPrevented()).toBe(true)
  await user.clear(screen.getByLabelText('지금 불편한 점을 편하게 적어 주세요'))
  expect(unloadPrevented()).toBe(false)
  await user.type(screen.getByLabelText('나이'), '4')
  expect(unloadPrevented()).toBe(true)
  unmount()
  expect(unloadPrevented()).toBe(false)
})

test('beforeunload: describe 이후(START_INCOMPLETE 포함) 단계는 계속 등록되어 있다', async () => {
  const user = userEvent.setup()
  const { view } = await reachIncompleteWithCandidates(user)
  expect(unloadPrevented()).toBe(true)
  view.unmount()
  expect(unloadPrevented()).toBe(false)
})

test('POSITIVE 여러 개 → 가장 불편한 것 선택, 4개 이상 → 앞 3개 + cache, bootstrap 없음', async () => {
  const user = userEvent.setup()
  const onStart = vi.fn()
  const found = [c('E_201', 'POSITIVE', '기침?', '기침'), c('E_91', 'POSITIVE', '열?', '열'), c('E_66', 'POSITIVE', '숨?', '숨이 차'),
    c('E_77', 'POSITIVE', '가래?', '가래도 누렇'), c('E_50', 'POSITIVE', '땀?', '식은땀'), c('E_212', 'POSITIVE', '목소리?', '목소리도 쉬었')]
  render(<NaturalIntakeScreen onExtract={vi.fn(async () => found)} onStart={onStart} onRestart={() => {}} />)
  await describe(user, '여러 증상')
  await user.click(screen.getByRole('button', { name: '다음' }))
  await user.click(screen.getByRole('button', { name: '숨이 참' }))
  expect(screen.queryByTestId('bootstrap-question')).toBeNull()
  const [request, cached] = onStart.mock.calls[0]
  expect(request.initialEvidence).toBe('E_66')
  expect(request.answers.map((a) => a.question_id)).toEqual(['E_201', 'E_91', 'E_77'])
  expect(cached).toEqual([{ evidence_id: 'E_50', status: 'POSITIVE' }, { evidence_id: 'E_212', status: 'POSITIVE' }])
})

test('시작 실패 후 다시 시도는 마지막 request·cached·intakeHistory 그대로 onStart 를 다시 부른다', async () => {
  const user = userEvent.setup()
  const onStart = vi.fn()
  render(<NaturalIntakeScreen onExtract={vi.fn(async () => [])} onStart={onStart} onRestart={() => {}} pending={false} />)
  await describe(user, '몸이 이상해요')
  await user.click(screen.getByRole('button', { name: '가장 불편한 증상 고르기' }))
  await user.click(within(screen.getByTestId('initial-frequent')).getByRole('button', { name: '기침' }))
  await answerBoot(user, '없음')   // E_91
  await answerBoot(user, '없음')   // E_53
  await answerBoot(user, '없음')   // E_66
  expect(onStart).toHaveBeenCalledTimes(1)
  const [firstRequest, firstCached, firstHistory] = onStart.mock.calls[0]
  expect(screen.getByText('시작하지 못했어요.')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: '다시 시도' }))
  expect(onStart).toHaveBeenCalledTimes(2)
  expect(onStart.mock.calls[1]).toEqual([firstRequest, firstCached, firstHistory])
})

test('추출 실패(null)면 입력 화면에 머문다', async () => {
  const user = userEvent.setup()
  render(<NaturalIntakeScreen onExtract={vi.fn(async () => null)} onStart={vi.fn()} onRestart={() => {}} />)
  await describe(user, '기침')
  expect(screen.getByLabelText('지금 불편한 점을 편하게 적어 주세요')).toHaveValue('기침')
})

test('다시 확인에서 답을 바꿨는데 예비 질문 후 다시 부족하면, "바꾼 답 없음" 문구가 아니라 처음 안내를 보여준다', async () => {
  const user = userEvent.setup()
  const { onStart } = await reachIncompleteWithCandidates(user)
  await user.click(screen.getByRole('button', { name: '답변 다시 확인하기' }))
  await answerBoot(user, '없음')             // E_91 → 없음 (바꿈)
  await answerBoot(user, '잘 모르겠어요')    // E_53
  await answerBoot(user, '잘 모르겠어요')    // E_66 → known 1, 남은 E_175·E_88 로 가능 → E_175
  expect(screen.getByTestId('bootstrap-question')).toHaveTextContent('새로 생긴 피로감')
  await answerBoot(user, '잘 모르겠어요')    // E_175 → E_88 하나로 불가
  expect(screen.getByText(START_INCOMPLETE_MESSAGE)).toBeInTheDocument()
  expect(screen.queryByText(STILL_INCOMPLETE_MESSAGE)).toBeNull()
  expect(screen.getAllByTestId('recap-answer').map((li) => li.textContent)[0]).toContain('없음')
  expect(onStart).not.toHaveBeenCalled()
})

// ---- M4: FINAL → 매퍼 후보 미리 준비('확인 대기') ----
import { act as actM4 } from '@testing-library/react'

function voiceFakes() {
  const ctl = {}
  const capture = async ({ onPacket }) => { ctl.onPacket = onPacket; return { stop: () => [] } }
  const connect = async ({ onMessage }) => {
    ctl.onMessage = onMessage
    return { kind: 'ws', sttState: 'WARM', send: () => {}, stop: async () => {}, close: () => {} }
  }
  return { ctl, sttOptions: { capture, connect, raf: (fn) => fn(), transcribeLegacy: async () => ({ transcript: '' }) } }
}

async function speakFinal(user, ctl, text, utt = 1) {
  if (!screen.queryByText('● 듣고 있어요')) {
    await user.click(screen.getByRole('button', { name: '🎙 말하기' }))
    await screen.findByText('● 듣고 있어요')
  }
  await actM4(async () => ctl.onMessage({ type: 'final', utt, text, audio_ms: 900 * utt, srv_ms: {} }))
}

function renderM4({ prepareExtract, onExtract = vi.fn(async () => []), onStart = vi.fn() } = {}) {
  const { ctl, sttOptions } = voiceFakes()
  render(<NaturalIntakeScreen onExtract={onExtract} onStart={onStart} onRestart={() => {}} prepareExtract={prepareExtract}
    sttAvailability={async () => ({ streaming: true })} sttOptions={sttOptions} />)
  return { ctl, onExtract, onStart }
}

test('M4 voice FINAL → candidates prepared and listed (labels only); 확인하기 uses them with no extra extract', async () => {
  const user = userEvent.setup()
  const setItem = vi.spyOn(Storage.prototype, 'setItem')
  const prepareExtract = vi.fn(async () => [c('E_201', 'POSITIVE', '기침이 있나요?', '기침'), c('E_91', 'NEGATIVE', '열이 있나요?', '열은 없어요')])
  const { ctl, onExtract, onStart } = renderM4({ prepareExtract })
  await actM4(async () => {})
  await user.type(screen.getByLabelText('나이'), '45')
  await user.click(screen.getByRole('button', { name: '남성' }))
  await speakFinal(user, ctl, '기침은 나는데 열은 없어요')
  expect(prepareExtract).toHaveBeenCalledWith('기침은 나는데 열은 없어요')
  const list = await screen.findByTestId('prepared-candidates')
  expect(list).toHaveTextContent('확인 대기 중인 증상 후보')
  expect(list).toHaveTextContent('기침이 있나요?')
  expect(list).toHaveTextContent('열이 있나요?')
  expect(list).not.toHaveTextContent('열은 없어요')                    // 원문·matched_text 는 보이지 않음
  expect(within(list).queryAllByRole('button')).toHaveLength(0)       // 버튼·체크 없음(확인은 다음 단계에서)
  expect(onStart).not.toHaveBeenCalled()
  await user.click(screen.getByRole('button', { name: '그만 말하기' }))
  await user.click(screen.getByRole('button', { name: '확인하기' }))
  expect(onExtract).not.toHaveBeenCalled()
  expect(prepareExtract).toHaveBeenCalledTimes(1)
  expect(screen.getAllByTestId('confirm-item')).toHaveLength(2)
  expect(setItem).not.toHaveBeenCalled()
  setItem.mockRestore()
})

test('M4 typing after the FINAL hides the prepared list; 확인하기 extracts the new text once', async () => {
  const user = userEvent.setup()
  const prepareExtract = vi.fn(async () => [c('E_201', 'POSITIVE', '기침이 있나요?', '기침')])
  const onExtract = vi.fn(async () => [c('E_91', 'POSITIVE', '열이 있나요?', '열')])
  const { ctl } = renderM4({ prepareExtract, onExtract })
  await actM4(async () => {})
  await user.type(screen.getByLabelText('나이'), '45')
  await user.click(screen.getByRole('button', { name: '남성' }))
  await speakFinal(user, ctl, '기침이 나요')
  await screen.findByTestId('prepared-candidates')
  await user.click(screen.getByRole('button', { name: '그만 말하기' }))
  await user.type(screen.getByLabelText('지금 불편한 점을 편하게 적어 주세요'), ' 열도')
  expect(screen.queryByTestId('prepared-candidates')).toBeNull()
  await user.click(screen.getByRole('button', { name: '확인하기' }))
  expect(onExtract).toHaveBeenCalledTimes(1)
  expect(onExtract).toHaveBeenCalledWith('기침이 나요 열도')
})

test('M4 two FINALs: the late response for the first text is discarded, the list shows the second', async () => {
  const user = userEvent.setup()
  let releaseFirst
  const prepareExtract = vi.fn()
    .mockImplementationOnce(() => new Promise((r) => { releaseFirst = () => r([c('E_201', 'POSITIVE', '기침이 있나요?', '기침')]) }))
    .mockImplementationOnce(async () => [c('E_91', 'POSITIVE', '열이 있나요?', '열')])
  const { ctl } = renderM4({ prepareExtract })
  await actM4(async () => {})
  await speakFinal(user, ctl, '기침이 나요', 1)
  await speakFinal(user, ctl, '열도 나요', 2)
  await screen.findByText('열이 있나요?')
  await actM4(async () => releaseFirst())
  expect(screen.getByTestId('prepared-candidates')).not.toHaveTextContent('기침이 있나요?')
  expect(prepareExtract).toHaveBeenLastCalledWith('기침이 나요\n열도 나요')                 // '요' 로 끝나 마침표 보충 없음
})

test('M4 prepare failure is silent and 확인하기 extracts normally', async () => {
  const user = userEvent.setup()
  const prepareExtract = vi.fn(async () => { throw new Error('down') })
  const onExtract = vi.fn(async () => [c('E_201', 'POSITIVE', '기침이 있나요?', '기침')])
  const { ctl } = renderM4({ prepareExtract, onExtract })
  await actM4(async () => {})
  await user.type(screen.getByLabelText('나이'), '45')
  await user.click(screen.getByRole('button', { name: '남성' }))
  await speakFinal(user, ctl, '기침이 나요')
  await user.click(screen.getByRole('button', { name: '그만 말하기' }))
  expect(screen.queryByTestId('prepared-candidates')).toBeNull()
  expect(screen.queryByRole('alert')).toBeNull()
  await user.click(screen.getByRole('button', { name: '확인하기' }))
  expect(onExtract).toHaveBeenCalledTimes(1)
})

test('M4 typed text alone never triggers a prepare request', async () => {
  const user = userEvent.setup()
  const prepareExtract = vi.fn(async () => [])
  renderM4({ prepareExtract })
  await actM4(async () => {})
  await user.type(screen.getByLabelText('지금 불편한 점을 편하게 적어 주세요'), '기침이 나요')
  expect(prepareExtract).not.toHaveBeenCalled()
})

