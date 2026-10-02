import { formatPercent } from '../lib/candidates.js'
import { diseaseLabel } from '../terminology/labels.js'

const SYMBOL = { up: '↑', down: '↓', same: '–' }
const SYMBOL_LABEL = { up: '올라감', down: '내려감', same: '변화 없음' }

export default function CandidatePanel({ rows, note = null }) {
  return (
    <section className="sheet candidates" aria-live="polite">
      <h2 className="candidates__title">현재 확인이 필요한 진단 후보</h2>
      <ul className="candidates__list">
        {rows.map((row) => (
          <li className="candidate" data-testid="candidate-row" key={row.name}>
            <div className="candidate__head">
              <span className="candidate__name">{diseaseLabel(row.name)}</span>
              <span className="candidate__value">{`${formatPercent(row.probability)}%`}</span>
              <span className="candidate__direction" data-direction={row.direction} aria-label={SYMBOL_LABEL[row.direction]}>
                {SYMBOL[row.direction]}
              </span>
            </div>
            {row.previous !== null && row.direction !== 'same' && (
              <span className="candidate__ghost" data-testid={`candidate-ghost-${row.name}`}>
                {`${formatPercent(row.previous)}%`}
              </span>
            )}
            <div className="candidate__track">
              <div className="candidate__bar" style={{ width: `${(row.probability * 100).toFixed(2)}%` }} />
            </div>
          </li>
        ))}
      </ul>
      {note && <p className="candidates__note">{note}</p>}
    </section>
  )
}
