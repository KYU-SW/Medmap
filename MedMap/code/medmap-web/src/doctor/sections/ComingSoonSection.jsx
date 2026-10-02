import { COPY } from '../copy.js'

// 확장 영역: 서버가 NOT_AVAILABLE 로 준 항목만 "준비 중"으로 보여준다. 가짜 결과를 그리지 않는다.
export default function ComingSoonSection({ extensions }) {
  const items = Object.entries(COPY.comingSoon).filter(([key]) => extensions?.[key]?.status === 'NOT_AVAILABLE')
  if (!items.length) return null
  return (
    <section className="sheet doctor-section doctor-coming" aria-labelledby="doctor-coming-title">
      <h2 id="doctor-coming-title">{COPY.comingSoonTitle}</h2>
      <ul className="list">
        {items.map(([key, label]) => (
          <li key={key}><span>{label}</span> <span className="hint">{COPY.comingSoonReason}</span></li>
        ))}
      </ul>
    </section>
  )
}
