import AppHeader from './components/AppHeader.jsx'
import StartScreen from './screens/StartScreen.jsx'
import NaturalIntakeScreen from './screens/NaturalIntakeScreen.jsx'
import ConsultScreen from './screens/ConsultScreen.jsx'
import SummaryScreen from './screens/SummaryScreen.jsx'
import Notice from './components/Notice.jsx'
import { userMessage } from './api/messages.js'
import { useMedmapSession } from './session/useMedmapSession.js'

export default function App() {
  const session = useMedmapSession()
  const step = session.turn?.questions_asked_in_session ?? 0
  const total = session.turn?.max_questions ?? session.health.max_questions ?? 3

  return (
    <div className="app">
      <AppHeader step={step} total={total} />
      {session.error && (
        <Notice
          message={userMessage(session.error)}
          onRetry={session.error.source !== 'extract' && session.canRetry ? session.retry : undefined}
          onRestart={session.reset}
          pending={session.pending}
        />
      )}
      {session.autoApplied.length > 0 && session.phase !== 'intake' && (
        <p className="applied" role="status">
          {`앞서 말씀하신 내용을 반영했어요: ${session.autoApplied.map((a) => `${a.question} — ${a.answer}`).join(', ')}`}
        </p>
      )}
      {session.phase === 'start' && (
        <StartScreen ready={session.health.engine_ready} checking={false} onStart={session.begin} />
      )}
      {session.phase === 'intake' && (
        <NaturalIntakeScreen
          onExtract={session.extract}
          onStart={session.start}
          onRestart={session.reset}
          pending={session.pending}
        />
      )}
      {session.phase === 'consult' && (
        <ConsultScreen turn={session.turn} onAnswer={session.answer} pending={session.pending} />
      )}
      {session.phase === 'summary' && (
        <SummaryScreen
          turn={session.turn}
          summary={session.summary}
          summaryState={session.summaryState}
          onRetrySummary={session.retrySummary}
          onRestart={session.reset}
        />
      )}
    </div>
  )
}
