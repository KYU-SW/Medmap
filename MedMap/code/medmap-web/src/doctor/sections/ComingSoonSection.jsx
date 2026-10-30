import { COPY } from '../copy.js'

// 확장 영역: 서버가 NOT_AVAILABLE 로 준 항목만 "준비 중"으로 보여준다. 가짜 결과를 그리지 않는다.
export default function ComingSoonSection({ extensions }) {
  const items = Object.entries(COPY.comingSoon).filter(([key]) => extensions?.[key]?.status === 'NOT_AVAILABLE')
  if (!items.length) return null
  // 축약 표시: 실제 기능 카드처럼 보이지 않게 한 줄 목록으로. 받아쓰기 항목은 표시만(버튼·마이크 없음).
  return (
    <section className="doctor-coming" aria-labelledby="doctor-coming-title">
      <h2 id="doctor-coming-title" className="doctor-coming__title">{COPY.comingSoonTitle}</h2>
      <ul className="doctor-coming__list">
        {items.map(([key, label]) => <li key={key}>{label}</li>)}
        <li>{COPY.futureStt}</li>
      </ul>
      <p className="hint">{COPY.comingSoonReason}</p>
    </section>
  )
}
