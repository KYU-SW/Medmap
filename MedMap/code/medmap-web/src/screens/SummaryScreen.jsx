function ageSexLabel(turn) {
  return `${turn.session.patient_state.age}세 · ${turn.session.patient_state.sex === 'M' ? '남성' : '여성'}`
}

function AnswerList({ heading, items }) {
  if (!items || items.length === 0) return null
  return (
    <>
      <h2 className="summary__heading">{heading}</h2>
      <ul className="summary__history">
        {items.map((item) => (
          <li key={item.question_id}>
            <span className="summary__question">{item.question_ko}</span>
            {' — '}
            <span className="summary__answer">{item.answer_ko}</span>
          </li>
        ))}
      </ul>
    </>
  )
}

function Disclaimer({ text }) {
  const lines = text.split('\n')
  return (
    <p className="summary__disclaimer">
      {lines.map((line, index) => (
        // eslint-disable-next-line react/no-array-index-key
        <span key={index}>
          {line}
          {index < lines.length - 1 && <br />}
        </span>
      ))}
    </p>
  )
}

export default function SummaryScreen({ turn, summary, summaryState, onRetrySummary, onRestart }) {
  const ready = summaryState === 'ready' && summary != null

  return (
    <main className="layout layout--single">
      <section className="sheet summary">
        <h1 className="summary__title">현재까지 확인된 정보</h1>
        <p className="summary__meta">{ageSexLabel(turn)}</p>

        {summaryState === 'loading' && <p role="status">요약을 불러오는 중입니다.</p>}

        {summaryState === 'error' && (
          <div role="alert">
            <p>요약 정보를 불러오지 못했습니다.</p>
            <button type="button" className="button" onClick={onRetrySummary}>다시 시도</button>
          </div>
        )}

        {ready && (
          <>
            {summary.chief_complaint && (
              <>
                <h2 className="summary__heading">주 증상</h2>
                <p className="summary__question">
                  {summary.chief_complaint.label_ko ?? summary.chief_complaint.question_ko}
                </p>
              </>
            )}
            <AnswerList heading="있다고 확인한 증상" items={summary.confirmed_positive} />
            <AnswerList heading="없다고 확인한 증상" items={summary.confirmed_negative} />
            <AnswerList heading="선택한 값" items={summary.confirmed_values} />
            <AnswerList heading="해당 없음" items={summary.not_applicable} />
            <AnswerList heading="잘 모르겠다고 답한 질문" items={summary.unknown} />
            <p className="summary__progress">
              {`답한 질문 ${summary.answered_questions.length}개${summary.chief_complaint ? '(주 증상 포함)' : ''} · 추가 확인 ${summary.questions_used} / ${turn.max_questions}`}
            </p>
          </>
        )}

        {/* 진단 후보·확률은 환자 화면에 보이지 않는다(의사 화면 전용 — 2026-10-01 통합 QA P1, 사용자 결정) */}

        {ready && <Disclaimer text={summary.disclaimer} />}

        <button type="button" className="button button--primary" onClick={onRestart}>처음부터 다시</button>
      </section>
    </main>
  )
}
