import { useEffect, useRef } from 'react'
import { useStreamingStt } from '../voice/useStreamingStt'
import { messageFor } from './VoiceInput'

// 말하는 동안 받아쓰기(PARTIAL)를 입력칸 밖 한 줄에 보여 주고, 확정된 문장(FINAL)만 onTranscript 로 넘긴다.
// PARTIAL 은 화면 표시 전용 — 입력칸·저장소·서버 상태에 들어가지 않는다. 오류 문구는 기존 VoiceInput 과 같다.
export default function StreamingVoiceInput({ onTranscript, disabled = false, onBusyChange = () => {}, onUnsupported, sttOptions }) {
  const stt = useStreamingStt({ onFinal: onTranscript, ...sttOptions })
  const { state, partial, sttState, error, start, stop } = stt

  const onBusyChangeRef = useRef(onBusyChange)
  useEffect(() => { onBusyChangeRef.current = onBusyChange }, [onBusyChange])
  useEffect(() => { onBusyChangeRef.current(state === 'connecting' || state === 'finalizing') }, [state])
  useEffect(() => () => { onBusyChangeRef.current(false) }, [])
  useEffect(() => { if (error === 'unsupported') onUnsupported?.() }, [error, onUnsupported])

  const loading = sttState === 'LOADING' || sttState === 'COLD'
  const hasPartial = Boolean(partial.stable || partial.unstable)

  return (
    <div className="stack">
      {state === 'idle' && (
        <button type="button" className="button" onClick={start} disabled={disabled}>🎙 말하기</button>
      )}
      {state === 'connecting' && <p className="hint" role="status">마이크를 준비하고 있어요.</p>}
      {state === 'listening' && (
        <div className="row">
          <span>● 듣고 있어요</span>
          <button type="button" className="button" onClick={stop}>그만 말하기</button>
        </div>
      )}
      {state === 'finalizing' && <p className="hint" role="status">음성을 글로 바꾸는 중입니다.</p>}
      {state !== 'idle' && loading && <p className="hint">음성 엔진을 준비하고 있어요. 첫 문장은 조금 늦게 나올 수 있습니다.</p>}
      {(state === 'listening' || state === 'finalizing') && (
        <p className="stt-partial" data-testid="stt-partial" aria-live="polite">
          {hasPartial ? (
            <>
              <strong>{partial.stable}</strong>
              <span className="stt-unstable">{partial.unstable}</span>
            </>
          ) : (
            <span className="hint">말씀하시면 여기에 받아 적어요.</span>
          )}
        </p>
      )}
      {error && error !== 'unsupported' && <p className="hint" role="alert">{messageFor(error)}</p>}
    </div>
  )
}
