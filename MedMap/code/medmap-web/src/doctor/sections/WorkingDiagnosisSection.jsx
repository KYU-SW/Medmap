import { useState } from 'react'
import { COPY } from '../copy.js'

const SEARCH_LIMIT = 8

// 현재 생각하는 진단: 49개 검색 선택 · 목록 밖 직접 입력 · 건너뛰기. 입력 전에는 후보·질문이 서버에서 잠겨 있다(blind).
export default function WorkingDiagnosisSection({ wd, diagnoses, onChoose, pending = false }) {
  const [editing, setEditing] = useState(wd.state === 'PENDING')
  const [query, setQuery] = useState('')
  const [free, setFree] = useState('')

  const choose = async (next) => {
    await onChoose(next)
    setEditing(false)
    setQuery('')
    setFree('')
  }

  if (!editing && wd.state !== 'PENDING') {
    const value = wd.value
    return (
      <section className="sheet doctor-section" aria-labelledby="doctor-wd-title">
        <h2 id="doctor-wd-title">{COPY.wdTitle}</h2>
        <p className="doctor-wd__value" data-testid="doctor-wd-value">{value ? value.label : COPY.wdSkipped}</p>
        {value?.kind === 'OUT_OF_SCOPE' && <p className="hint">{COPY.wdOutOfScope}</p>}
        <button type="button" className="button" onClick={() => setEditing(true)} disabled={pending}>{COPY.wdChange}</button>
      </section>
    )
  }

  const needle = query.trim()
  const matches = needle ? diagnoses.filter((d) => d.label_ko.includes(needle)).slice(0, SEARCH_LIMIT) : []
  const freeLabel = free.trim()

  return (
    <section className="sheet doctor-section" aria-labelledby="doctor-wd-title">
      <h2 id="doctor-wd-title">{COPY.wdTitle}</h2>
      {wd.state === 'PENDING' && <p className="hint">{COPY.wdHint}</p>}
      <label className="field">
        <span>{COPY.wdSearchLabel}</span>
        <input type="search" value={query} onChange={(e) => setQuery(e.target.value)} disabled={pending} />
      </label>
      {matches.length > 0 && (
        <ul className="list doctor-wd__matches">
          {matches.map((d) => (
            <li key={d.code}>
              <button type="button" className="button" disabled={pending}
                onClick={() => choose({ state: 'ENTERED', value: { kind: 'CATALOG', code: d.code } })}>
                {d.label_ko}
              </button>
            </li>
          ))}
        </ul>
      )}
      {needle && matches.length === 0 && <p className="hint">{COPY.wdNoMatch}</p>}
      <label className="field">
        <span>{COPY.wdFreeLabel}</span>
        <input type="text" maxLength={80} value={free} onChange={(e) => setFree(e.target.value)} disabled={pending} />
      </label>
      <div className="row">
        <button type="button" className="button" disabled={pending || !freeLabel}
          onClick={() => choose({ state: 'ENTERED', value: { kind: 'OUT_OF_SCOPE', label: freeLabel } })}>
          {COPY.wdFreeSubmit}
        </button>
        {wd.state === 'PENDING' && (
          <button type="button" className="button" disabled={pending} onClick={() => choose({ state: 'SKIPPED' })}>
            {COPY.wdSkip}
          </button>
        )}
      </div>
    </section>
  )
}
