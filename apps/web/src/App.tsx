import { useEffect, useRef, useState } from "react";

type Status = "idle" | "recording" | "transcribing" | "done" | "error";

const MAX_RECORDING_MS = 60_000;

export default function App() {
  const [status, setStatus] = useState<Status>("idle");
  const [transcript, setTranscript] = useState("");
  const [message, setMessage] = useState("버튼을 누르고 증상을 말해 주세요.");
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timeoutRef = useRef<number | null>(null);

  useEffect(() => {
    return () => stopMediaTracks();
  }, []);

  function stopMediaTracks() {
    if (timeoutRef.current !== null) {
      window.clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }

  async function startRecording() {
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      setStatus("error");
      setMessage("이 브라우저에서는 음성 녹음을 지원하지 않습니다.");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const preferredType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : undefined;
      const recorder = new MediaRecorder(
        stream,
        preferredType ? { mimeType: preferredType } : undefined,
      );

      streamRef.current = stream;
      recorderRef.current = recorder;
      chunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };
      recorder.onstop = () => void sendRecording(recorder.mimeType || "audio/webm");
      recorder.start();
      setStatus("recording");
      setMessage("녹음 중입니다. 말이 끝나면 녹음 종료를 눌러 주세요.");
      timeoutRef.current = window.setTimeout(() => stopRecording(), MAX_RECORDING_MS);
    } catch {
      stopMediaTracks();
      setStatus("error");
      setMessage("마이크를 사용할 수 없습니다. 브라우저 권한을 확인해 주세요.");
    }
  }

  function stopRecording() {
    if (recorderRef.current?.state === "recording") {
      recorderRef.current.stop();
      setStatus("transcribing");
      setMessage("음성을 글자로 바꾸고 있습니다. 첫 실행은 시간이 더 걸릴 수 있습니다.");
    }
    stopMediaTracks();
  }

  async function sendRecording(contentType: string) {
    const audio = new Blob(chunksRef.current, { type: contentType });
    chunksRef.current = [];

    if (audio.size === 0) {
      setStatus("error");
      setMessage("녹음된 음성이 없습니다. 다시 시도해 주세요.");
      return;
    }

    const form = new FormData();
    form.append("file", audio, "recording.webm");

    try {
      const response = await fetch("/v1/stt/transcribe", { method: "POST", body: form });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "음성 변환에 실패했습니다.");

      setTranscript(data.transcript);
      setStatus("done");
      const processingTime = Number(data.processing_seconds);
      const timing = Number.isFinite(processingTime)
        ? ` 변환 시간은 ${processingTime.toFixed(2)}초입니다.`
        : "";
      setMessage(`변환 결과를 확인하고 틀린 부분을 직접 수정해 주세요.${timing}`);
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "음성 변환에 실패했습니다.");
    }
  }

  const busy = status === "recording" || status === "transcribing";

  return (
    <main className="page">
      <section className="card" aria-live="polite">
        <p className="eyebrow">MedMap 음성 입력</p>
        <h1>증상을 말로 기록해 보세요</h1>
        <p className={`status status--${status}`}>{message}</p>

        <div className="controls">
          {status !== "recording" ? (
            <button type="button" onClick={startRecording} disabled={busy}>
              {status === "transcribing" ? "변환 중…" : "녹음 시작"}
            </button>
          ) : (
            <button className="button--stop" type="button" onClick={stopRecording}>
              녹음 종료
            </button>
          )}
        </div>

        <label htmlFor="transcript">변환된 문장</label>
        <textarea
          id="transcript"
          value={transcript}
          onChange={(event) => setTranscript(event.target.value)}
          placeholder="음성 변환 결과가 여기에 표시됩니다."
          rows={6}
          disabled={status === "transcribing"}
        />
        <p className="privacy-note">
          음성은 글자로 바꾸는 동안만 사용합니다. 결과는 사용자가 확인하기 전까지 환자
          기록에 반영하지 않습니다.
        </p>
      </section>
    </main>
  );
}
