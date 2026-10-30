import { useState } from 'react'
import { COPY } from '../copy.js'
import { evidenceShortLabel, questionText } from '../../terminology/labels.js'

function Items({ heading, items }) {
  if (!items?.length) return null
  return (
    <div className="doctor-summary__group">
      <h4 className="doctor-summary__heading doctor-record__group">{heading}</h4>
      <ul className="doctor-record__list">
        {items.map((item) => (
          <li key={item.question_id} className="doctor-record__row">
            <span className="summary__question">{item.question_ko}</span>
            <span className="visually-hidden">{' — '}</span>
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
      <ul className="doctor-tags doctor-tags--neutral">
        {labels.map(({ id, label }) => <li key={id} className="doctor-tag">{label}</li>)}
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

// 위쪽 한눈 요약: PatientState 에 반영된 답을 짧은 표시명 태그로 다시 보여준다(표시만, 아래 "확인한 내용"과 같은 데이터).
// 짧은 표시명이 없는 항목은 태그로 만들지 않는다(아래 기록에는 그대로 남는다).
function shortTags(items, exclude) {
  return (items ?? [])
    .filter((item) => item.question_id !== exclude)
    .map((item) => ({ id: item.question_id, label: evidenceShortLabel(item.question_id), answer: item.answer_ko }))
    .filter((item) => item.label)
}

const RECORD_COLLAPSED = 6

// 환자 요약은 blind 대상이 아니다(환자가 확인한 사실). 진단 후보는 여기 없다.
export default function PatientSummarySection({ summary, cache = [] }) {
  const [recordOpen, setRecordOpen] = useState(false)
  const chief = summary.chief_complaint
  const positive = unappliedLabels(cache, summary, 'POSITIVE')
  const negative = unappliedLabels(cache, summary, 'NEGATIVE')
  const positiveTags = shortTags(summary.confirmed_positive, chief?.question_id)
  const negativeTags = shortTags(summary.confirmed_negative)
  const valueTags = shortTags(summary.confirmed_values)
  const recordCount = ['confirmed_positive', 'confirmed_negative', 'confirmed_values', 'not_applicable']
    .reduce((n, key) => n + (summary[key]?.length ?? 0), 0)
  const collapsible = recordCount > RECORD_COLLAPSED
  return (
    <section className="sheet doctor-section doctor-summary" aria-labelledby="doctor-summary-title">
      <div className="doctor-section__head">
        <h2 id="doctor-summary-title">{COPY.summaryTitle}</h2>
        <p className="summary__meta doctor-summary__meta">{`${summary.age}세 · ${COPY.sex[summary.sex] ?? summary.sex}`}</p>
      </div>
      {(chief || positiveTags.length > 0) && (
        <div className="doctor-summary__group doctor-summary__main">
          <h3 className="doctor-summary__heading">{COPY.summaryMain}</h3>
          <ul className="doctor-symptoms">
            {chief && (
              <li className="doctor-symptom doctor-symptom--chief">
                <span className="doctor-symptom__label">{chief.label_ko ?? chief.question_ko}</span>
                <span className="doctor-symptom__note">{COPY.chiefComplaint}</span>
              </li>
            )}
            {positiveTags.map((tag) => (
              <li key={tag.id} className="doctor-symptom">
                <span className="doctor-symptom__label">{tag.label}</span>
                <span className="doctor-symptom__note">{COPY.unappliedPositive}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {valueTags.length > 0 && (
        <div className="doctor-summary__group">
          <h3 className="doctor-summary__heading">{COPY.summaryValueTags}</h3>
          <ul className="doctor-tags">
            {valueTags.map((tag) => (
              <li key={tag.id} className="doctor-tag doctor-tag--value">
                <span className="doctor-tag__key">{tag.label}</span> {tag.answer}
              </li>
            ))}
          </ul>
        </div>
      )}
      {negativeTags.length > 0 && (
        <div className="doctor-summary__group">
          <h3 className="doctor-summary__heading">{COPY.summaryNegativeTags}</h3>
          <ul className="doctor-tags doctor-tags--negative">
            {negativeTags.map((tag) => <li key={tag.id} className="doctor-tag">{`${tag.label} 없음`}</li>)}
          </ul>
        </div>
      )}
      <div className="doctor-record" data-testid="doctor-findings-applied"
        data-collapsed={collapsible && !recordOpen ? 'true' : 'false'}>
        <div className="doctor-record__head">
          <h3 className="doctor-summary__heading doctor-record__title">{COPY.recordTitle}</h3>
          <p className="hint">{COPY.appliedTitle}</p>
        </div>
        <div className="doctor-record__body" id="doctor-record-body">
          <Items heading={COPY.positive} items={summary.confirmed_positive} />
          <Items heading={COPY.negative} items={summary.confirmed_negative} />
          <Items heading={COPY.values} items={summary.confirmed_values} />
          <Items heading={COPY.notApplicable} items={summary.not_applicable} />
        </div>
        {collapsible && (
          <button type="button" className="question__more doctor-more" aria-expanded={recordOpen}
            aria-controls="doctor-record-body" onClick={() => setRecordOpen((v) => !v)}>
            {recordOpen ? COPY.recordLess : COPY.recordMore(recordCount)}
          </button>
        )}
      </div>
      {(positive.length > 0 || negative.length > 0) && (
        <div className="doctor-aside" data-testid="doctor-findings-unapplied">
          <h3 className="doctor-summary__heading">{COPY.unappliedTitle}</h3>
          <p className="hint">{COPY.unappliedNote}</p>
          <Labels heading={COPY.unappliedPositive} testId="unapplied-positive" labels={positive} />
          <Labels heading={COPY.unappliedNegative} testId="unapplied-negative" labels={negative} />
        </div>
      )}
      {summary.unknown?.length > 0 && (
        <div className="doctor-aside" data-testid="doctor-findings-unknown">
          <h3 className="doctor-summary__heading">{COPY.unknownTitle}</h3>
          <Items heading={COPY.unknown} items={summary.unknown} />
        </div>
      )}
      <p className="hint">{COPY.answeredCount(summary.answered_questions.length)}</p>
    </section>
  )
}
