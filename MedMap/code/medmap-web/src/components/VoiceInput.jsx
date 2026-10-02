import { useEffect, useRef } from 'react'
import { useRecorder } from '../voice/useRecorder'
import { transcribeAudio } from '../api/client'

const PERMISSION_MESSAGE = '마이크를 사용할 수 없습니다. 직접 입력해서 계속할 수 있어요.'
const EMPTY_MESSAGE = '음성이 감지되지 않았어요. 다시 말하거나 직접 입력해 주세요.'
const FAILED_MESSAGE = '음성을 글로 바꾸지 못했어요. 직접 입력해서 계속할 수 있어요.'

// permission/no_mic/unsupported/start_failed 는 마이크 자체를 못 쓴 경우, empty 는 서버·클라이언트
// 모두 "말은 했지만 소리가 없다"는 뜻으로 같은 문구를 쓴다. 내부 오류 코드는 절대 노출하지 않는다.
const ERROR_MESSAGES = {
  permission: PERMISSION_MESSAGE,
  no_mic: PERMISSION_MESSAGE,
  unsupported: PERMISSION_MESSAGE,
  start_failed: PERMISSION_MESSAGE,
  empty: EMPTY_MESSAGE,
  AUDIO_EMPTY: EMPTY_MESSAGE,
  transcribe_failed: FAILED_MESSAGE,
}

export function messageFor(errorCode) {
  return ERROR_MESSAGES[errorCode] ?? FAILED_MESSAGE
}

function formatElapsed(totalSeconds) {
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
}

// 이 탭에서 전사가 한 번이라도 성공하면 "처음 한 번은 오래 걸릴 수 있다" 안내를 더 이상 보여주지 않는다.
// 모듈 수준 in-memory flag(저장소 사용 안 함). 테스트에서만 __resetVoiceInputTranscribeHintForTests 로 초기화한다.
let hasTranscribedOnce = false
export function __resetVoiceInputTranscribeHintForTests() {
  hasTranscribedOnce = false
}

export default function VoiceInput({
  onTranscript,
  transcribe = transcribeAudio,
  disabled = false,
  getUserMedia,
  MediaRecorderImpl,
  onBusyChange = () => {},
}) {
  async function onRecorded(blob) {
    let response
    try {
      response = await transcribe(blob)
    } catch (err) {
      throw Object.assign(new Error('transcribe_failed'), { type: err?.code === 'AUDIO_EMPTY' ? 'AUDIO_EMPTY' : 'transcribe_failed' })
    }
    hasTranscribedOnce = true
    onTranscript(response.transcript)
  }

  const { state, elapsed, error, start, stop } = useRecorder({
    getUserMedia,
    MediaRecorderImpl,
    onRecorded,
  })

  // busy 는 transcribing 상태 변화가 있을 때만 부모에 알린다. unmount 시에는 항상 false 로 정리한다.
  const onBusyChangeRef = useRef(onBusyChange)
  useEffect(() => { onBusyChangeRef.current = onBusyChange }, [onBusyChange])
  useEffect(() => {
    onBusyChangeRef.current(state === 'transcribing')
  }, [state])
  useEffect(() => () => { onBusyChangeRef.current(false) }, [])

  const message = error ? messageFor(error) : null

  return (
    <div className="stack">
      {state === 'idle' && (
        <button type="button" className="button" onClick={start} disabled={disabled}>
          🎙 말하기
        </button>
      )}
      {state === 'recording' && (
        <div className="row">
          <span>● 듣고 있어요 {formatElapsed(elapsed)}</span>
          <button type="button" className="button" onClick={stop}>그만 말하기</button>
        </div>
      )}
      {state === 'transcribing' && (
        <>
          <p className="hint" role="status">음성을 글로 바꾸는 중입니다.</p>
          {!hasTranscribedOnce && <p className="hint">처음 한 번은 약 10초 정도 걸릴 수 있습니다.</p>}
        </>
      )}
      {message && <p className="hint" role="alert">{message}</p>}
    </div>
  )
}
