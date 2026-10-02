import { useState } from 'react'
import { FREQUENT_IDS, initialItem, searchInitial } from '../intake/catalog.js'

export default function InitialPicker({ options = [], exclude = [], onPick }) {
  const [query, setQuery] = useState('')

  if (options.length >= 2) {
    return (
      <section className="panel">
        <h2>이 중 지금 가장 불편한 증상은 무엇인가요?</h2>
        <div className="stack">
          {options.map((item) => (
            <button key={item.evidence_id} type="button" className="button" onClick={() => onPick(item.evidence_id)}>
              {item.label_ko}
            </button>
          ))}
        </div>
      </section>
    )
  }

  const blocked = new Set(exclude)
  const frequent = FREQUENT_IDS.filter((id) => !blocked.has(id)).map(initialItem)
  const results = searchInitial(query, { exclude })

  return (
    <section className="panel">
      <h2>지금 가장 불편한 증상 하나를 골라 주세요</h2>
      <div className="row" data-testid="initial-frequent">
        {frequent.map((item) => (
          <button key={item.evidence_id} type="button" className="button" onClick={() => onPick(item.evidence_id)}>
            {item.label_ko}
          </button>
        ))}
      </div>
      <label className="field">
        <span>증상 찾기</span>
        <input type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="예: 어지러움, 목 아픔" />
      </label>
      {query.trim() && results.length === 0 && <p className="hint">찾는 증상이 없어요. 다른 말로 찾아보세요.</p>}
      <ul className="list" data-testid="initial-results">
        {results.map((item) => (
          <li key={item.evidence_id}>
            <button type="button" className="button" onClick={() => onPick(item.evidence_id)}>{item.label_ko}</button>
            <p className="hint">{item.detail_ko}</p>
          </li>
        ))}
      </ul>
    </section>
  )
}
