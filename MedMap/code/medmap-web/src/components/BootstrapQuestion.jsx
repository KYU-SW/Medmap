import { BOOTSTRAP_QUESTIONS_KO } from '../intake/startPlan.js'

const CHOICES = [
  ['POSITIVE', '있음'],
  ['NEGATIVE', '없음'],
  ['UNKNOWN', '잘 모르겠어요'],
]

// remaining = 시작에 더 필요한 known 답 수. "잘 모르겠어요"는 이 수를 줄이지 않는다.
// note 가 있으면(답변 다시 확인하기) remaining 안내 대신 note 를 보여준다. 어느 경우든 기본 선택값은 없다.
export default function BootstrapQuestion({ evidenceId, remaining, note, onAnswer, pending = false }) {
  return (
    <section className="panel">
      <p className="hint">{note ?? `시작 전에 ${remaining}가지만 더 확인할게요`}</p>
      <h2 data-testid="bootstrap-question">{BOOTSTRAP_QUESTIONS_KO[evidenceId]}</h2>
      <div className="stack">
        {CHOICES.map(([kind, label]) => (
          <button
            key={kind}
            type="button"
            className="button choice"
            disabled={pending}
            onClick={() => onAnswer({ question_id: evidenceId, kind, value: null })}
          >
            {label}
          </button>
        ))}
      </div>
    </section>
  )
}
