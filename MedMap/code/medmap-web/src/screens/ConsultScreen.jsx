import QuestionPanel from '../components/QuestionPanel.jsx'

// 환자 화면: 질문만. 진단 후보·확률은 보이지 않는다(의사 화면 전용 — 2026-10-01 통합 QA P1, 사용자 결정).
export default function ConsultScreen({ turn, onAnswer, pending = false }) {
  return (
    <main className="layout layout--single">
      <QuestionPanel question={turn.next_question} onAnswer={onAnswer} pending={pending} />
    </main>
  )
}
