import { useState } from 'react'
import { COPY } from '../copy.js'

export const DEFAULT_VISIBLE = 5

// 순서만 보여준다: 번호·확률·점수·순위 호칭 없음. 표시 개수는 IG 선택과 무관하다(서버가 전체 상태로 질문을 고른다).
export default function CandidatesSection({ assessment }) {
  const [expanded, setExpanded] = useState(false)
  if (assessment.status !== 'AVAILABLE') return null
  const all = assessment.candidates
  const shown = expanded ? all : all.slice(0, DEFAULT_VISIBLE)
  return (
    <section className="sheet doctor-section" aria-labelledby="doctor-candidates-title" data-testid="doctor-candidates">
      <h2 id="doctor-candidates-title">{COPY.candidatesTitle}</h2>
      <ul className="doctor-candidates__list">
        {shown.map((c) => <li key={c.code}>{c.label_ko}</li>)}
      </ul>
      {all.length > DEFAULT_VISIBLE && (
        <button type="button" className="question__more" aria-expanded={expanded} onClick={() => setExpanded((v) => !v)}>
          {expanded ? COPY.less : COPY.more}
        </button>
      )}
      <p className="hint">{assessment.scope_ko}</p>
      <p className="hint">{COPY.candidatesNotExcluded}</p>
      <p className="hint">{COPY.candidatesNoCompare}</p>
    </section>
  )
}
