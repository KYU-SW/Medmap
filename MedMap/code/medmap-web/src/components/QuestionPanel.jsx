import { useEffect, useState } from 'react'
import ChoiceButton from './ChoiceButton.jsx'
import { evidenceShortLabel } from '../terminology/labels.js'

const VISIBLE_CHOICE_LIMIT = 12

export default function QuestionPanel({ question, onAnswer, pending = false }) {
  const [selected, setSelected] = useState([])
  const [expanded, setExpanded] = useState(false)

  useEffect(() => {
    setSelected([])
    setExpanded(false)
  }, [question.question_id])

  const isMulti = question.answer_type === 'MULTI_CHOICE'
  // 질문 전문이 아직 영문 fallback 이면 한국어 짧은 표시명을 제목으로 함께 보여준다(backlog QUESTION_KO_COMPLETION).
  const shortLabel = question.is_fallback ? evidenceShortLabel(question.question_id) : null
  const choices = expanded ? question.choices : question.choices.slice(0, VISIBLE_CHOICE_LIMIT)

  function answerFromChoice(choice) {
    if (choice.value === null) return { kind: 'UNKNOWN', value: null }
    if (question.answer_type === 'YES_NO') return { kind: choice.value ? 'POSITIVE' : 'NEGATIVE', value: null }
    return { kind: 'VALUE', value: [choice.value] }
  }

  function handleChoice(choice) {
    if (!isMulti) {
      onAnswer(answerFromChoice(choice))
      return
    }
    if (choice.value === null) {
      onAnswer({ kind: 'UNKNOWN', value: null })
      return
    }
    setSelected((prev) => (prev.includes(choice.value) ? prev.filter((v) => v !== choice.value) : [...prev, choice.value]))
  }

  return (
    <section className="sheet question">
      <h2 className="question__kicker">추가로 확인할 정보</h2>
      <div data-testid="question-live" aria-live="polite">
        {shortLabel && <p className="question__label" data-testid="question-short-label">{shortLabel}</p>}
        <p className="question__text">{question.question_ko}</p>
        {question.is_fallback && <p className="question__fallback">영문 원문</p>}
      </div>
      <div className="question__choices">
        {choices.map((choice) => (
          <ChoiceButton
            key={String(choice.value)}
            label={choice.label}
            selected={isMulti && selected.includes(choice.value)}
            onClick={() => handleChoice(choice)}
            disabled={pending}
          />
        ))}
      </div>
      {!expanded && question.choices.length > VISIBLE_CHOICE_LIMIT && (
        <button type="button" className="question__more" onClick={() => setExpanded(true)}>
          전체 보기 ({question.choices.length}개)
        </button>
      )}
      {isMulti && (
        <button
          type="button"
          className="button button--primary question__next"
          disabled={selected.length === 0 || pending}
          onClick={() => onAnswer({ kind: 'VALUE', value: selected })}
        >
          다음
        </button>
      )}
    </section>
  )
}
