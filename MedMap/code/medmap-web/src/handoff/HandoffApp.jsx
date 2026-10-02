import Notice from '../components/Notice.jsx'
import StartScreen from '../screens/StartScreen.jsx'
import NaturalIntakeScreen from '../screens/NaturalIntakeScreen.jsx'
import { userMessage } from '../api/messages.js'
import { useHandoffSession } from './useHandoffSession.js'
import SendToDevice from './SendToDevice.jsx'

export const HANDOFF_DONE_TITLE = '의사에게 전달할 준비가 됐습니다'
export const HANDOFF_STORAGE_FAILED = '이 브라우저에 저장하지 못해 의사 화면으로 전달할 수 없습니다. 브라우저의 사이트 데이터 저장이 허용돼 있는지 확인해 주세요.'
export const HANDOFF_DONE_BODY = '말씀하신 내용과 확인한 답이 이 브라우저에 정리됐습니다. 추가 질문은 의사 화면에서 이어집니다.'

// 의사 인계 흐름(#/handoff): 기존 시작·자유 입력 화면을 그대로 쓰고, start 뒤에는 상담 질문 대신 인계 완료 화면.
export default function HandoffApp({ api, handoffApi }) {
  const session = useHandoffSession(api ? { api } : undefined)
  return (
    <div className="app">
      <header className="app-header">
        <span className="app-header__brand">MedMap</span>
        <span>진료 전 정리</span>
      </header>
      {session.error && (
        <Notice
          message={userMessage(session.error)}
          onRetry={session.error.source !== 'extract' && session.canRetry ? session.retry : undefined}
          onRestart={session.reset}
          pending={session.pending}
        />
      )}
      {session.storageFailed && (
        <div className="notice" role="alert">
          <p className="notice__title">{HANDOFF_STORAGE_FAILED}</p>
        </div>
      )}
      {session.phase === 'start' && (
        <StartScreen ready={session.health.engine_ready} checking={false} onStart={session.begin} />
      )}
      {session.phase === 'intake' && (
        <NaturalIntakeScreen onExtract={session.extract} onStart={session.start} onRestart={session.reset}
          pending={session.pending} />
      )}
      {session.phase === 'done' && (
        <main className="layout layout--single">
          <section className="sheet" data-testid="handoff-done">
            <h1>{HANDOFF_DONE_TITLE}</h1>
            <p>{HANDOFF_DONE_BODY}</p>
            <div className="row">
              <a className="button button--primary" href="#/doctor">의사 화면 열기</a>
              <button type="button" className="button" onClick={session.reset}>처음부터 다시</button>
            </div>
            <SendToDevice {...(handoffApi ? { api: handoffApi } : {})} />
          </section>
        </main>
      )}
    </div>
  )
}
