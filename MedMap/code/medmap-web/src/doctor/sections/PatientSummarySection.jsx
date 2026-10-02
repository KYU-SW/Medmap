import { COPY } from '../copy.js'
import { evidenceShortLabel, questionText } from '../../terminology/labels.js'

function Items({ heading, items }) {
  if (!items?.length) return null
  return (
    <div className="doctor-summary__group">
      <h3 className="doctor-summary__heading">{heading}</h3>
      <ul className="list doctor-summary__list">
        {items.map((item) => (
          <li key={item.question_id}>
            <span className="summary__question">{item.question_ko}</span>
            {' — '}
            <span className="summary__answer">{item.answer_ko}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function Labels({ heading, testId, labels }) {
  if (!labels.length) return null
  return (
    <div className="doctor-summary__group" data-testid={testId}>
      <h4 className="doctor-summary__heading">{heading}</h4>
      <ul className="list doctor-summary__list">
        {labels.map(({ id, label }) => <li key={id}>{label}</li>)}
      </ul>
    </div>
  )
}

// 환자가 intake 에서 확인했지만 start(PatientState)에 들어가지 못한 답(cache) — 표시만 한다.
// 모델에 자동 반영하지 않는다(반영은 IG 가 그 질문을 고르고 의사가 확인할 때만, 기존 계약 그대로).
// 이미 PatientState 에 있는 질문은 빼고, 한국어 표시명이 없는 항목은 내부 ID 를 보이지 않도록 생략한다.
function unappliedLabels(cache, summary, status) {
  const applied = new Set((summary.answered_questions ?? []).map((q) => q?.question_id).filter(Boolean))
  return (cache ?? [])
    .filter((entry) => entry.status === status && !applied.has(entry.evidence_id))
    .map((entry) => ({ id: entry.evidence_id, label: questionText(entry.evidence_id) ?? evidenceShortLabel(entry.evidence_id) }))
    .filter((entry) => entry.label)
}

// 환자 요약은 blind 대상이 아니다(환자가 확인한 사실). 진단 후보는 여기 없다.
export default function PatientSummarySection({ summary, cache = [] }) {
  const chief = summary.chief_complaint
  const positive = unappliedLabels(cache, summary, 'POSITIVE')
  const negative = unappliedLabels(cache, summary, 'NEGATIVE')
  return (
    <section className="sheet doctor-section" aria-labelledby="doctor-summary-title">
      <h2 id="doctor-summary-title">{COPY.summaryTitle}</h2>
      <p className="summary__meta">{`${summary.age}세 · ${COPY.sex[summary.sex] ?? summary.sex}`}</p>
      {chief && (
        <div className="doctor-summary__group">
          <h3 className="doctor-summary__heading">{COPY.chiefComplaint}</h3>
          <p>{chief.label_ko ?? chief.question_ko}</p>
        </div>
      )}
      <div data-testid="doctor-findings-applied">
        <h3 className="doctor-summary__heading">{COPY.appliedTitle}</h3>
        <Items heading={COPY.positive} items={summary.confirmed_positive} />
        <Items heading={COPY.negative} items={summary.confirmed_negative} />
        <Items heading={COPY.values} items={summary.confirmed_values} />
        <Items heading={COPY.notApplicable} items={summary.not_applicable} />
      </div>
      {(positive.length > 0 || negative.length > 0) && (
        <div data-testid="doctor-findings-unapplied">
          <h3 className="doctor-summary__heading">{COPY.unappliedTitle}</h3>
          <p className="hint">{COPY.unappliedNote}</p>
          <Labels heading={COPY.unappliedPositive} testId="unapplied-positive" labels={positive} />
          <Labels heading={COPY.unappliedNegative} testId="unapplied-negative" labels={negative} />
        </div>
      )}
      {summary.unknown?.length > 0 && (
        <div data-testid="doctor-findings-unknown">
          <h3 className="doctor-summary__heading">{COPY.unknownTitle}</h3>
          <Items heading={COPY.unknown} items={summary.unknown} />
        </div>
      )}
      <p className="hint">{COPY.answeredCount(summary.answered_questions.length)}</p>
    </section>
  )
}
