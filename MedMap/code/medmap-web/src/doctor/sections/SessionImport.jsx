import { useState } from 'react'
import { COPY } from '../copy.js'

// 시연·개발용: 상담 기록(medmap-session-v1 JSON, 또는 {session, cache})을 붙여 넣거나 파일로 불러온다.
export default function SessionImport({ onImport, pending = false }) {
  const [text, setText] = useState('')
  const [invalid, setInvalid] = useState(false)

  const submit = (value) => setInvalid(!onImport(value))

  const readFile = async (event) => {
    const file = event.target.files?.[0]
    if (!file) return
    submit(await file.text())
    event.target.value = ''
  }

  return (
    <section className="sheet doctor-section" aria-labelledby="doctor-load-title">
      <h2 id="doctor-load-title">{COPY.loadTitle}</h2>
      <p className="hint">{COPY.loadBody}</p>
      <label className="field">
        <span>{COPY.loadPasteLabel}</span>
        <textarea rows={6} value={text} onChange={(e) => setText(e.target.value)} disabled={pending} />
      </label>
      <button type="button" className="button button--primary" disabled={pending || !text.trim()} onClick={() => submit(text)}>
        {COPY.loadPasteSubmit}
      </button>
      <label className="field doctor-load__file">
        <span>{COPY.loadFileLabel}</span>
        <input type="file" accept="application/json,.json" onChange={readFile} disabled={pending} />
      </label>
      {invalid && <p role="alert">{COPY.loadInvalid}</p>}
    </section>
  )
}
