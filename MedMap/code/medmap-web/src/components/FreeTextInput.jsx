import { useEffect, useState } from 'react'
import VoiceInput from './VoiceInput'
import StreamingVoiceInput from './StreamingVoiceInput'
import { loadSttStreaming } from '../voice/sttAvailability'
import { joinTranscript } from '../voice/joinTranscript'

export const TEXT_MAX = 1000
export const EMPTY_DRAFT = Object.freeze({ age: '', sex: '', text: '' })

// 입력(나이·성별·문장)은 상위(NaturalIntakeScreen)가 소유하는 draft 로만 존재한다(controlled, 이 컴포넌트는 입력 state 없음).
// draft 는 React 메모리에만 있고 저장소·서버에 저장하지 않는다. 문장은 제출 시 onSubmit 으로 extract 요청에만 쓰인다.
// onDraftChange 는 updater 함수를 받는다 — 전사 결과가 늦게 도착해도 그 사이 타이핑한 최신 draft 에 합쳐진다.
// 음성 입력: 서버 streaming 플래그가 켜져 있고 브라우저가 AudioWorklet 을 지원하면 StreamingVoiceInput, 아니면 기존 VoiceInput(그대로).
// 어느 쪽이든 입력칸에는 확정된 문장만 joinTranscript 로 붙는다. streaming FINAL 이 붙은 뒤에만 onVoiceTranscript()(인자 없음)로
// 알린다(M4 후보 준비용). 기존 VoiceInput 경로는 그대로 — [확인하기] 전 extract 없음(STT-1 계약).
// belowText: 입력칸·음성 버튼 아래, [확인하기] 위에 놓을 내용(M4 '확인 대기 중인 증상 후보').
export default function FreeTextInput({ draft = EMPTY_DRAFT, onDraftChange, onSubmit, pending = false, sttAvailability = loadSttStreaming, sttOptions,
  onVoiceTranscript, belowText = null }) {
  const { age, sex, text } = draft
  const [voiceBusy, setVoiceBusy] = useState(false)
  const [streaming, setStreaming] = useState(false)
  useEffect(() => {
    let alive = true
    sttAvailability().then((v) => { if (alive) setStreaming(Boolean(v?.streaming)) }).catch(() => {})
    return () => { alive = false }
  }, [sttAvailability])
  const update = (patch) => onDraftChange((prev) => ({ ...prev, ...patch(prev) }))
  const appendVoice = (t) => update((prev) => ({ text: joinTranscript(prev.text, t) }))
  const appendStreamingFinal = (t) => {
    appendVoice(t)
    onVoiceTranscript?.()
  }
  const ageNumber = Number(age)
  const ready = age !== '' && ageNumber >= 0 && ageNumber <= 130 && (sex === 'M' || sex === 'F') && text.trim().length > 0

  function submit(event) {
    event.preventDefault()
    if (!ready || pending || voiceBusy) return
    onSubmit({ age: ageNumber, sex, text: text.trim() })
  }

  return (
    <form className="panel" onSubmit={submit}>
      <label className="field">
        <span>나이</span>
        <input inputMode="numeric" value={age} onChange={(e) => { const value = e.target.value.replace(/\D/g, '').slice(0, 3); update(() => ({ age: value })) }} />
      </label>
      <fieldset className="field">
        <legend>성별</legend>
        <div className="row">
          {[['M', '남성'], ['F', '여성']].map(([code, label]) => (
            <button key={code} type="button" className="button" aria-pressed={sex === code} onClick={() => update(() => ({ sex: code }))}>
              {label}
            </button>
          ))}
        </div>
      </fieldset>
      <label className="field">
        <span>지금 불편한 점을 편하게 적어 주세요</span>
        <textarea
          rows={4}
          maxLength={TEXT_MAX}
          value={text}
          onChange={(e) => { const value = e.target.value; update(() => ({ text: value })) }}
          placeholder="예: 사흘 전부터 기침이 나고 열이 있어요"
        />
      </label>
      {streaming ? (
        <StreamingVoiceInput onTranscript={appendStreamingFinal} disabled={pending}
          onBusyChange={setVoiceBusy} onUnsupported={() => setStreaming(false)} sttOptions={sttOptions} />
      ) : (
        <VoiceInput onTranscript={appendVoice} disabled={pending} onBusyChange={setVoiceBusy} />
      )}
      {belowText}
      <button type="submit" className="button button--primary" disabled={!ready || pending || voiceBusy}>확인하기</button>
    </form>
  )
}
