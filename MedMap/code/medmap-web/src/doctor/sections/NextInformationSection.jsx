import { useLayoutEffect } from 'react'
import QuestionPanel from '../../components/QuestionPanel.jsx'
import { perfMark } from '../../voice/perf.js'
import { COPY } from '../copy.js'

const STOPPED = { BUDGET_REACHED: COPY.budgetReached, NONE_ELIGIBLE: COPY.noneEligible, UNSUPPORTED_SESSION_SHAPE: COPY.unsupported }

// 기존 Internal IG 가 고른 질문 1개. 환자가 intake 에서 이미 말한 답이 있으면 보여주되, 의사가 눌러야만 제출한다.
export default function NextInformationSection({ info, patientSaid, onAnswer, pending = false }) {
  // M5 계측(숫자만): 새 view(후보·다음 질문 또는 한도 도달)가 화면에 그려진 시각. 질문 id·답은 기록하지 않는다
  useLayoutEffect(() => {
    if (info.status !== 'LOCKED') perfMark('doctor_next_render', { questions_used: info.questions_used ?? null })
  }, [info])
  if (info.status === 'LOCKED') return null
  return (
    <section className="sheet doctor-section" aria-labelledby="doctor-next-title" data-testid="doctor-next">
      <h2 id="doctor-next-title">{COPY.nextTitle}</h2>
      {info.max_questions != null && info.questions_used != null && (
        <p className="hint" data-testid="doctor-next-counter">{COPY.nextCounter(info.questions_used, info.max_questions)}</p>
      )}
      {info.status === 'QUESTION' ? (
        <>
          {patientSaid && (
            <div className="doctor-patient-said" data-testid="doctor-patient-said">
              <p>{`${COPY.patientSaid}: ${COPY.patientAnswer[patientSaid.status]}`}</p>
              <button type="button" className="button button--primary" disabled={pending}
                onClick={() => onAnswer({ kind: patientSaid.status, value: null })}>
                {COPY.confirmPatient}
              </button>
            </div>
          )}
          <QuestionPanel question={info.question} onAnswer={onAnswer} pending={pending} />
          {pending && <p className="hint" role="status">{COPY.answering}</p>}
        </>
      ) : (
        <p role="status">{STOPPED[info.status]}</p>
      )}
    </section>
  )
}
