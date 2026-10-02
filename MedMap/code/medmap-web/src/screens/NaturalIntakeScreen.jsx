import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import FreeTextInput, { EMPTY_DRAFT } from '../components/FreeTextInput.jsx'
import EvidenceConfirmation from '../components/EvidenceConfirmation.jsx'
import InitialPicker from '../components/InitialPicker.jsx'
import BootstrapQuestion from '../components/BootstrapQuestion.jsx'
import { initialItem } from '../intake/catalog.js'
import { BOOTSTRAP_QUESTIONS_KO, START_INCOMPLETE, bootstrapStep, buildStartRequest, initialOptions } from '../intake/startPlan.js'
import { usePreparedCandidates } from '../intake/usePreparedCandidates.js'
import { perfMark } from '../voice/perf.js'

export const NO_CANDIDATE_MESSAGE = '말씀하신 내용에서 확실하게 확인할 수 있는 항목을 찾지 못했어요.'
// START_INCOMPLETE 는 오류가 아니다: frozen bootstrap/backup 으로 exact-k3 에 필요한 known 답을 아직 확보하지 못한 상태.
export const START_INCOMPLETE_MESSAGE = '진료 질문을 시작하려면 몇 가지 정보를 더 확인해야 합니다.'
export const START_INCOMPLETE_HINT = '‘잘 모르겠어요’도 괜찮은 답입니다. 기억나는 답이 있을 때만 바꿔 주세요.'
export const STILL_INCOMPLETE_MESSAGE = '현재 확인된 정보만으로는 다음 상담 질문을 시작하기 어렵습니다.'
export const STILL_INCOMPLETE_HINT = '입력하신 내용은 그대로 남아 있어요. 처음부터 다시 하려면 아래 버튼을 눌러 주세요.'
export const PREPARED_TITLE = '확인 대기 중인 증상 후보'
export const PREPARED_HINT = '아래 [확인하기]를 누르면 하나씩 확인합니다.'
export const PRESTART_NOTICE = '아직 저장된 상담이 아닙니다.\n이 단계에서 새로고침하면 입력한 내용이 사라질 수 있습니다.'
const ANSWER_LABEL = { POSITIVE: '있음', NEGATIVE: '없음', UNKNOWN: '잘 모르겠어요' }
const SEX_LABEL = { M: '남성', F: '여성' }

// 자유 입력 → 확인 → initial → bootstrap → start.
// 입력(draft)·후보·확인·initial·bootstrap 답은 이 화면이 살아 있는 동안 React 메모리에만 있다(저장소·서버에 저장하지 않음).
// start 성공(→상담)이나 명시적 [처음부터 다시](→시작 화면)로 이 화면이 unmount 되면 함께 사라진다.
// M4: 음성 FINAL 이 입력칸에 붙으면 prepareExtract(상태 없는 추출 요청)로 후보를 미리 계산해 '확인 대기'로만 보여준다.
// 확인·PatientState·세션은 그대로 [확인하기] 이후 단계가 맡는다. 입력칸 텍스트가 준비 때와 다르면 목록을 숨기고 평소처럼 onExtract.
export default function NaturalIntakeScreen({ onExtract, onStart, onRestart, pending = false, prepareExtract, sttAvailability, sttOptions }) {
  const [step, setStep] = useState('describe')
  const [draft, setDraft] = useState(EMPTY_DRAFT)
  const [profile, setProfile] = useState(null)
  const [candidates, setCandidates] = useState([])
  const [confirmed, setConfirmed] = useState([])
  const [initialId, setInitialId] = useState(null)
  const [responses, setResponses] = useState([])
  const [asking, setAsking] = useState(null)
  const [review, setReview] = useState(null)       // 답변 다시 확인하기: { positions: UNKNOWN 응답 index[], cursor, changed }
  const [reviewedUnchanged, setReviewedUnchanged] = useState(false)   // 마지막 다시 확인에서 바꾼 답이 없었는지
  const [extracting, setExtracting] = useState(false)
  const lastStartArgsRef = useRef(null)
  const prep = usePreparedCandidates(prepareExtract ? { extract: prepareExtract } : undefined)
  const [voiceTick, setVoiceTick] = useState(0)
  const { prepare } = prep
  useEffect(() => {
    if (voiceTick > 0) prepare(draft.text)             // FINAL 이 붙은 직후의 전체 입력칸 텍스트
  }, [voiceTick])                                       // eslint-disable-line react-hooks/exhaustive-deps
  const preparedNow = prep.prepared && prep.prepared.text === draft.text.trim() && prep.prepared.candidates.length > 0
    ? prep.prepared.candidates : null

  // 시작 전(서버 세션 없음)에 잃을 입력이 있을 때만 새로고침·닫기 시 브라우저 기본 확인창을 띄운다(custom 문구 없음).
  // start 성공·reset 으로 이 화면이 unmount 되거나 입력이 비면 제거된다. SPA 내부 화면 전환에는 관여하지 않는다.
  const dirty = step !== 'describe' || draft.age !== '' || draft.sex !== '' || draft.text.trim() !== ''
  useEffect(() => {
    if (!dirty) return undefined
    const warn = (event) => {
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])

  async function describe({ age, sex, text }) {
    const ready = prep.takeIfSame(text)
    if (ready) {                                        // 미리 준비한 후보(같은 텍스트) — extract 요청 없이 확인 단계로
      setProfile({ age, sex })
      setCandidates(ready)
      setStep(ready.length ? 'confirm' : 'none')
      return
    }
    setExtracting(true)
    try {
      const found = await onExtract(text)
      if (found === null) return
      setProfile({ age, sex })
      setCandidates(found)
      setStep(found.length ? 'confirm' : 'none')
    } finally {
      setExtracting(false)
    }
  }

  function finish(id, list, answered) {
    const { request, cached } = buildStartRequest({ ...profile, initialId: id, confirmed: list, bootstrapResponses: answered })
    const intakeHistory = answered.map((r) => ({ question: BOOTSTRAP_QUESTIONS_KO[r.question_id], answer: ANSWER_LABEL[r.kind] }))
    lastStartArgsRef.current = [request, cached, intakeHistory]
    setStep('starting')
    onStart(request, cached, intakeHistory)
  }

  function retryStart() {
    if (!lastStartArgsRef.current) return
    onStart(...lastStartArgsRef.current)
  }

  function advance(id, list, answered) {
    const next = bootstrapStep({ initialId: id, confirmed: list, responses: answered })
    if (next.status === 'READY') finish(id, list, answered)
    else if (next.status === START_INCOMPLETE) setStep('incomplete')
    else {
      setAsking(next)
      setStep('bootstrap')
    }
  }

  function chooseInitial(id, list = confirmed) {
    setInitialId(id)
    setResponses([])
    advance(id, list, [])
  }

  function afterConfirm(list) {
    setConfirmed(list)
    const options = initialOptions(list)
    if (options.length === 1) chooseInitial(options[0].evidence_id, list)
    else setStep('initial')
  }

  function answerBootstrap(answer) {
    const answered = [...responses, answer]
    setResponses(answered)
    advance(initialId, confirmed, answered)
  }

  // 답변 다시 확인하기: '잘 모르겠어요'로 답한 질문만 원래 순서로 한 번씩 다시 보여준다(새 질문·순서 변경 없음).
  function startReview() {
    const positions = responses.flatMap((r, index) => (r.kind === 'UNKNOWN' ? [index] : []))
    if (!positions.length) return
    setReview({ positions, cursor: 0, changed: false })
    setStep('review')
  }

  // 교체된 응답 중 walk 가 READY 가 되는 가장 짧은 앞부분. 없으면 null.
  function readyPrefix(answered) {
    for (let n = 0; n <= answered.length; n += 1) {
      const prefix = answered.slice(0, n)
      if (bootstrapStep({ initialId, confirmed, responses: prefix }).status === 'READY') return prefix
    }
    return null
  }

  // 사용자가 있음/없음을 누른 경우만 그 답을 교체한다. '잘 모르겠어요'는 기존 답을 그대로 둔다.
  function answerReview(answer) {
    const position = review.positions[review.cursor]
    const changed = answer.kind !== 'UNKNOWN'
    const revised = changed ? responses.map((r, index) => (index === position ? answer : r)) : responses
    if (changed) {
      setResponses(revised)
      const prefix = readyPrefix(revised)
      if (prefix) {
        setReview(null)
        setResponses(prefix)
        finish(initialId, confirmed, prefix)
        return
      }
    }
    const cursor = review.cursor + 1
    const anyChanged = review.changed || changed
    if (cursor < review.positions.length) {
      setReview({ ...review, cursor, changed: anyChanged })
      return
    }
    setReview(null)
    setReviewedUnchanged(!anyChanged)
    advance(initialId, confirmed, revised)       // 남은 frozen 예비 질문이 있으면 이어서, 없으면 incomplete 유지
  }

  const options = initialOptions(confirmed).map((c) => initialItem(c.evidence_id))
  const reviewId = review ? responses[review.positions[review.cursor]]?.question_id : null

  return (
    <main className="page">
      <p className="hint" data-testid="prestart-notice">
        {PRESTART_NOTICE.split('\n').map((line, index) => (
          // eslint-disable-next-line react/no-array-index-key
          <span key={index}>{line}{index === 0 && <br />}</span>
        ))}
      </p>
      {step === 'describe' && (
        <FreeTextInput draft={draft} onDraftChange={setDraft} onSubmit={describe} pending={extracting || pending}
          onVoiceTranscript={() => setVoiceTick((n) => n + 1)}
          belowText={preparedNow ? <PreparedCandidates candidates={preparedNow} /> : null}
          {...(sttAvailability ? { sttAvailability } : {})} {...(sttOptions ? { sttOptions } : {})} />
      )}
      {step === 'confirm' && <EvidenceConfirmation candidates={candidates} onConfirm={afterConfirm} />}
      {step === 'none' && (
        <section className="panel">
          <p role="status">{NO_CANDIDATE_MESSAGE}</p>
          <button type="button" className="button button--primary" onClick={() => setStep('initial')}>
            가장 불편한 증상 고르기
          </button>
        </section>
      )}
      {step === 'initial' && (
        <InitialPicker options={options} exclude={confirmed.map((c) => c.evidence_id)} onPick={(id) => chooseInitial(id)} />
      )}
      {step === 'bootstrap' && asking && (
        <BootstrapQuestion
          key={asking.questionId}
          evidenceId={asking.questionId}
          remaining={asking.remaining}
          onAnswer={answerBootstrap}
          pending={pending}
        />
      )}
      {step === 'review' && reviewId && (
        <BootstrapQuestion
          key={`review-${reviewId}`}
          evidenceId={reviewId}
          note={`이전 답: 잘 모르겠어요 (${review.cursor + 1} / ${review.positions.length}) · 바꿀 답이 없으면 그대로 ‘잘 모르겠어요’를 눌러 주세요.`}
          onAnswer={answerReview}
          pending={pending}
        />
      )}
      {step === 'incomplete' && (
        <section className="panel">
          <p role="status">{reviewedUnchanged ? STILL_INCOMPLETE_MESSAGE : START_INCOMPLETE_MESSAGE}</p>
          <p className="hint">{reviewedUnchanged ? STILL_INCOMPLETE_HINT : START_INCOMPLETE_HINT}</p>
          <IntakeRecap profile={profile} draft={draft} candidates={candidates} confirmed={confirmed} initialId={initialId} responses={responses} />
          {responses.some((r) => r.kind === 'UNKNOWN') && (
            <button type="button" className="button button--primary" onClick={startReview}>답변 다시 확인하기</button>
          )}
          <button type="button" className="button" onClick={onRestart}>처음부터 다시</button>
        </section>
      )}
      {step === 'starting' && (
        <section className="panel">
          <p role="status">{pending ? '진단을 시작하고 있어요' : '시작하지 못했어요.'}</p>
          {!pending && (
            <>
              <button type="button" className="button button--primary" onClick={retryStart}>다시 시도</button>
              <button type="button" className="button" onClick={onRestart}>처음부터 다시</button>
            </>
          )}
        </section>
      )}
    </main>
  )
}

// '확인 대기' 후보: 한국어 라벨만(원문·matched_text·있음/없음 표시 없음, 버튼 없음). 확인은 [확인하기] 다음 단계에서.
function PreparedCandidates({ candidates }) {
  useLayoutEffect(() => { perfMark('prep_render', { n: candidates.length }) }, [candidates])
  return (
    <section className="stack" data-testid="prepared-candidates" aria-live="polite">
      <h3>{PREPARED_TITLE}</h3>
      <ul className="list">
        {candidates.map((c) => <li key={c.evidence_id}>{c.label_ko}</li>)}
      </ul>
      <p className="hint">{PREPARED_HINT}</p>
    </section>
  )
}

// START_INCOMPLETE 화면에서 지금까지 입력·확인한 내용을 그대로 보여준다(메모리의 값, matched_text 는 표시하지 않음).
function IntakeRecap({ profile, draft, candidates, confirmed, initialId, responses }) {
  const labelOf = (id) => candidates.find((c) => c.evidence_id === id)?.label_ko ?? id
  return (
    <div data-testid="intake-recap">
      <h3>지금까지 입력한 내용</h3>
      {profile && <p>{`${profile.age}세 · ${SEX_LABEL[profile.sex] ?? ''}`}</p>}
      {draft.text.trim() && <p>{draft.text.trim()}</p>}
      {confirmed.length > 0 && (
        <ul className="list" data-testid="recap-confirmed">
          {confirmed.map((c) => <li key={c.evidence_id}>{`${labelOf(c.evidence_id)} — ${ANSWER_LABEL[c.status]}`}</li>)}
        </ul>
      )}
      {initialId && <p data-testid="recap-initial">{`가장 불편한 증상: ${initialItem(initialId)?.label_ko ?? initialId}`}</p>}
      {responses.length > 0 && (
        <ul className="list">
          {responses.map((r) => (
            <li key={r.question_id} data-testid="recap-answer">{`${BOOTSTRAP_QUESTIONS_KO[r.question_id]} — ${ANSWER_LABEL[r.kind]}`}</li>
          ))}
        </ul>
      )}
    </div>
  )
}
