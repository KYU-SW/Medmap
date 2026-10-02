import { useCallback, useEffect, useRef, useState } from 'react'

const MIME_CANDIDATES = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4']

function pickMimeType(MediaRecorderImpl) {
  if (!MediaRecorderImpl || typeof MediaRecorderImpl.isTypeSupported !== 'function') return undefined
  return MIME_CANDIDATES.find((type) => {
    try {
      return MediaRecorderImpl.isTypeSupported(type)
    } catch {
      return false
    }
  })
}

function classifyStartError(err) {
  const name = err?.name
  if (name === 'NotAllowedError' || name === 'SecurityError') return 'permission'
  if (name === 'NotFoundError' || name === 'OverconstrainedError') return 'no_mic'
  return 'start_failed'
}

function stopTracks(stream) {
  stream?.getTracks?.().forEach((track) => track.stop())
}

// 녹음(getUserMedia/MediaRecorder)만 담당한다. 서버 전송·transcript 해석은 onRecorded 콜백으로 위임한다.
export function useRecorder({
  maxSeconds = 60,
  getUserMedia,
  MediaRecorderImpl,
  now = () => Date.now(),
  onRecorded,
} = {}) {
  const [state, setState] = useState('idle')
  const [elapsed, setElapsed] = useState(0)
  const [error, setError] = useState(null)

  const recorderRef = useRef(null)
  const streamRef = useRef(null)
  const chunksRef = useRef([])
  const startedAtRef = useRef(0)
  const intervalRef = useRef(null)
  const mimeTypeRef = useRef(undefined)

  const resolvedGetUserMedia = getUserMedia
    ?? (typeof navigator !== 'undefined' ? navigator.mediaDevices?.getUserMedia?.bind(navigator.mediaDevices) : undefined)
  const resolvedMediaRecorder = MediaRecorderImpl === undefined
    ? (typeof window !== 'undefined' ? window.MediaRecorder : undefined)
    : MediaRecorderImpl

  const clearTick = useCallback(() => {
    if (intervalRef.current !== null) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
  }, [])

  const stop = useCallback(() => {
    const recorder = recorderRef.current
    if (!recorder || recorder.state === 'inactive') return
    clearTick()
    try {
      recorder.stop()
    } catch {
      // 가짜 구현에서도 onstop 이 호출되도록 예외는 무시한다
    }
  }, [clearTick])

  const start = useCallback(async () => {
    setError(null)
    if (!resolvedGetUserMedia || !resolvedMediaRecorder) {
      setError('unsupported')
      return
    }

    let stream
    try {
      stream = await resolvedGetUserMedia({ audio: true })
    } catch (err) {
      setError(classifyStartError(err))
      return
    }

    chunksRef.current = []
    const mimeType = pickMimeType(resolvedMediaRecorder)
    mimeTypeRef.current = mimeType

    let recorder
    try {
      recorder = mimeType
        ? new resolvedMediaRecorder(stream, { mimeType, audioBitsPerSecond: 32000 })
        : new resolvedMediaRecorder(stream, { audioBitsPerSecond: 32000 })
    } catch {
      setError('start_failed')
      stopTracks(stream)
      return
    }

    recorder.ondataavailable = (event) => {
      if (event?.data && event.data.size > 0) chunksRef.current.push(event.data)
    }

    recorder.onstop = () => {
      stopTracks(streamRef.current)
      streamRef.current = null

      const blob = new Blob(chunksRef.current, { type: mimeTypeRef.current || 'audio/webm' })
      chunksRef.current = []

      if (blob.size === 0) {
        setElapsed(0)
        setState('idle')
        setError('empty')
        return
      }

      setState('transcribing')
      Promise.resolve()
        .then(() => onRecorded?.(blob))
        .then(() => {
          setElapsed(0)
          setState('idle')
          setError(null)
        })
        .catch((err) => {
          setElapsed(0)
          setState('idle')
          setError(err?.type ?? 'transcribe_failed')
        })
    }

    try {
      recorder.start()
    } catch {
      setError('start_failed')
      stopTracks(stream)
      return
    }

    streamRef.current = stream
    recorderRef.current = recorder
    startedAtRef.current = now()
    setElapsed(0)
    setState('recording')

    clearTick()
    intervalRef.current = setInterval(() => {
      const secs = Math.floor((now() - startedAtRef.current) / 1000)
      setElapsed(secs)
      if (secs >= maxSeconds) stop()
    }, 250)
  }, [resolvedGetUserMedia, resolvedMediaRecorder, now, maxSeconds, onRecorded, stop, clearTick])

  useEffect(
    () => () => {
      clearTick()
      const recorder = recorderRef.current
      if (recorder && recorder.state !== 'inactive') {
        try {
          recorder.stop()
        } catch {
          // ignore on unmount
        }
      }
      stopTracks(streamRef.current)
    },
    [clearTick],
  )

  return { state, elapsed, error, start, stop }
}
