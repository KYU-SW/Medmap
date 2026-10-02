import { useState } from 'react'

const OPTIONS = [
  ['POSITIVE', '있음'],
  ['NEGATIVE', '없음'],
  ['REMOVE', '빼기'],
]

// 매퍼 후보를 사용자가 확인한다. 보지 않은 후보는 확인된 것이 아니므로 접지 않고 전부 보여준다.
// 후보를 추가하지는 않는다(빠진 정보는 bootstrap 질문이 채운다).
export default function EvidenceConfirmation({ candidates, onConfirm }) {
  const [decisions, setDecisions] = useState(() => Object.fromEntries(candidates.map((c) => [c.evidence_id, c.status])))

  function confirm() {
    onConfirm(candidates
      .filter((c) => decisions[c.evidence_id] !== 'REMOVE')
      .map((c) => ({ evidence_id: c.evidence_id, status: decisions[c.evidence_id] })))
  }

  return (
    <section className="panel">
      <h2>말씀하신 내용에서 다음 항목을 확인했어요</h2>
      <p className="hint">맞는지 확인해 주세요. 틀린 항목은 바꾸거나 빼 주세요.</p>
      <ul className="list">
        {candidates.map((c) => (
          <li key={c.evidence_id} data-testid="confirm-item">
            <p>{c.label_ko}</p>
            <p className="hint">{`“${c.matched_text}”`}</p>
            <div className="row" role="group" aria-label={c.label_ko}>
              {OPTIONS.map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  className="button"
                  aria-pressed={decisions[c.evidence_id] === value}
                  onClick={() => setDecisions((prev) => ({ ...prev, [c.evidence_id]: value }))}
                >
                  {label}
                </button>
              ))}
            </div>
          </li>
        ))}
      </ul>
      <button type="button" className="button button--primary" onClick={confirm}>다음</button>
    </section>
  )
}
