import { useEffect, useRef, useState } from "react";
import {
  deleteIntakeRecord,
  listIntakeRecords,
  saveIntakeRecord,
  type StoredIntakeRecord,
} from "./recordStorage";

type Status = "idle" | "recording" | "transcribing" | "done" | "error";

type SymptomObservation = {
  name: string;
  status: "present" | "absent";
  body_site: string | null;
  onset: string | null;
  severity: string | null;
  source_text: string;
};

type IntakeResult = {
  symptoms: SymptomObservation[];
  medications: string[];
  allergies: string[];
  unrecognized_fragments: string[];
  needs_user_confirmation: boolean;
};

const MAX_RECORDING_MS = 60_000;
const LIVE_TRANSCRIPTION_INTERVAL_MS = 1_500;

function encodeMonoWav(chunks: Float32Array[], sampleRate: number): Blob {
  const sampleCount = chunks.reduce((total, chunk) => total + chunk.length, 0);
  const buffer = new ArrayBuffer(44 + sampleCount * 2);
  const view = new DataView(buffer);
  const writeText = (offset: number, value: string) => {
    for (let index = 0; index < value.length; index += 1) {
      view.setUint8(offset + index, value.charCodeAt(index));
    }
  };

  writeText(0, "RIFF");
  view.setUint32(4, 36 + sampleCount * 2, true);
  writeText(8, "WAVE");
  writeText(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeText(36, "data");
  view.setUint32(40, sampleCount * 2, true);

  let offset = 44;
  for (const chunk of chunks) {
    for (const sample of chunk) {
      const clipped = Math.max(-1, Math.min(1, sample));
      view.setInt16(offset, clipped < 0 ? clipped * 0x8000 : clipped * 0x7fff, true);
      offset += 2;
    }
  }
  return new Blob([buffer], { type: "audio/wav" });
}

export default function App() {
  const [status, setStatus] = useState<Status>("idle");
  const [transcript, setTranscript] = useState("");
  const [message, setMessage] = useState("버튼을 누르고 증상을 말해 주세요.");
  const [intake, setIntake] = useState<IntakeResult | null>(null);
  const [extracting, setExtracting] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [records, setRecords] = useState<StoredIntakeRecord[]>([]);
  const [savingRecord, setSavingRecord] = useState(false);
  const [recordMessage, setRecordMessage] = useState("");
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timeoutRef = useRef<number | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const audioSourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const audioProcessorRef = useRef<ScriptProcessorNode | null>(null);
  const silentGainRef = useRef<GainNode | null>(null);
  const liveSamplesRef = useRef<Float32Array[]>([]);
  const liveSampleRateRef = useRef(16_000);
  const liveIntervalRef = useRef<number | null>(null);
  const liveRequestRef = useRef<AbortController | null>(null);
  const liveRequestRunningRef = useRef(false);

  useEffect(() => {
    void listIntakeRecords()
      .then(setRecords)
      .catch(() => setRecordMessage("저장된 기록을 불러오지 못했습니다."));
    return () => {
      stopLiveCapture();
      stopMediaTracks();
    };
  }, []);

  function stopLiveCapture() {
    if (liveIntervalRef.current !== null) {
      window.clearInterval(liveIntervalRef.current);
      liveIntervalRef.current = null;
    }
    liveRequestRef.current?.abort();
    liveRequestRef.current = null;
    liveRequestRunningRef.current = false;
    audioProcessorRef.current?.disconnect();
    audioSourceRef.current?.disconnect();
    silentGainRef.current?.disconnect();
    audioProcessorRef.current = null;
    audioSourceRef.current = null;
    silentGainRef.current = null;
    void audioContextRef.current?.close();
    audioContextRef.current = null;
  }

  async function requestLiveTranscript() {
    if (liveRequestRunningRef.current) return;
    const sampleCount = liveSamplesRef.current.reduce(
      (total, chunk) => total + chunk.length,
      0,
    );
    if (sampleCount < liveSampleRateRef.current * 0.6) return;

    liveRequestRunningRef.current = true;
    const controller = new AbortController();
    liveRequestRef.current = controller;
    const form = new FormData();
    form.append(
      "file",
      encodeMonoWav([...liveSamplesRef.current], liveSampleRateRef.current),
      "live.wav",
    );

    try {
      const response = await fetch("/v1/stt/transcribe", {
        method: "POST",
        body: form,
        signal: controller.signal,
      });
      const data = await response.json();
      if (response.ok && typeof data.transcript === "string" && data.transcript.trim()) {
        setTranscript(data.transcript);
        setMessage("듣고 있습니다. 말하는 동안 문장이 계속 수정될 수 있습니다.");
      }
    } catch (error) {
      if (!(error instanceof DOMException && error.name === "AbortError")) {
        console.error("Live transcription failed", error);
      }
    } finally {
      if (liveRequestRef.current === controller) liveRequestRef.current = null;
      liveRequestRunningRef.current = false;
    }
  }

  async function startLiveCapture(stream: MediaStream) {
    const context = new AudioContext({ sampleRate: 16_000 });
    await context.resume();
    const source = context.createMediaStreamSource(stream);
    const processor = context.createScriptProcessor(4096, 1, 1);
    const silentGain = context.createGain();
    silentGain.gain.value = 0;
    liveSamplesRef.current = [];
    liveSampleRateRef.current = context.sampleRate;
    processor.onaudioprocess = (event) => {
      liveSamplesRef.current.push(new Float32Array(event.inputBuffer.getChannelData(0)));
    };
    source.connect(processor);
    processor.connect(silentGain);
    silentGain.connect(context.destination);
    audioContextRef.current = context;
    audioSourceRef.current = source;
    audioProcessorRef.current = processor;
    silentGainRef.current = silentGain;
    liveIntervalRef.current = window.setInterval(
      () => void requestLiveTranscript(),
      LIVE_TRANSCRIPTION_INTERVAL_MS,
    );
  }

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
      await startLiveCapture(stream);
      setStatus("recording");
      setMessage("듣고 있습니다. 말하는 동안 변환 문장이 표시됩니다.");
      timeoutRef.current = window.setTimeout(() => stopRecording(), MAX_RECORDING_MS);
    } catch {
      stopMediaTracks();
      setStatus("error");
      setMessage("마이크를 사용할 수 없습니다. 브라우저 권한을 확인해 주세요.");
    }
  }

  function stopRecording() {
    if (recorderRef.current?.state === "recording") {
      stopLiveCapture();
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
      setIntake(null);
      setConfirmed(false);
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

  async function extractMedicalInformation() {
    if (!transcript.trim()) return;
    setExtracting(true);
    setConfirmed(false);
    try {
      const response = await fetch("/v1/intake/extract", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ transcript }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "의료정보를 정리하지 못했습니다.");
      setIntake(data);
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "의료정보를 정리하지 못했습니다.");
    } finally {
      setExtracting(false);
    }
  }

  function updateSymptom(index: number, changes: Partial<SymptomObservation>) {
    setIntake((current) => current && ({
      ...current,
      symptoms: current.symptoms.map((item, itemIndex) =>
        itemIndex === index ? { ...item, ...changes } : item,
      ),
    }));
    setConfirmed(false);
  }

  async function confirmAndSave() {
    if (!intake || !transcript.trim()) return;
    setSavingRecord(true);
    setRecordMessage("");
    const record: StoredIntakeRecord = {
      id: crypto.randomUUID(),
      createdAt: new Date().toISOString(),
      transcript: transcript.trim(),
      intake,
    };
    try {
      await saveIntakeRecord(record);
      setRecords((current) => [record, ...current]);
      setConfirmed(true);
      setRecordMessage("이 브라우저에 기록을 저장했습니다.");
    } catch {
      setConfirmed(false);
      setRecordMessage("기록을 저장하지 못했습니다. 브라우저 저장 권한을 확인해 주세요.");
    } finally {
      setSavingRecord(false);
    }
  }

  async function removeRecord(id: string) {
    try {
      await deleteIntakeRecord(id);
      setRecords((current) => current.filter((record) => record.id !== id));
      setRecordMessage("선택한 테스트 기록을 삭제했습니다.");
    } catch {
      setRecordMessage("기록을 삭제하지 못했습니다.");
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
          onChange={(event) => {
            setTranscript(event.target.value);
            setIntake(null);
            setConfirmed(false);
          }}
          placeholder="음성 변환 결과가 여기에 표시됩니다."
          rows={6}
          disabled={status === "transcribing"}
        />

        <button
          className="button--secondary"
          type="button"
          onClick={extractMedicalInformation}
          disabled={!transcript.trim() || extracting || busy}
        >
          {extracting ? "정리 중…" : "증상 정보 정리"}
        </button>

        {intake && (
          <section className="intake" aria-label="정리된 의료정보">
            <h2>확인이 필요한 정보</h2>
            <p>잘못 정리된 내용은 직접 고친 뒤 확인해 주세요.</p>
            {intake.symptoms.length === 0 ? (
              <p className="empty-result">현재 규칙에서 찾은 증상이 없습니다.</p>
            ) : intake.symptoms.map((symptom, index) => (
              <div className="observation" key={`${symptom.name}-${index}`}>
                <label>
                  증상
                  <input
                    value={symptom.name}
                    onChange={(event) => updateSymptom(index, { name: event.target.value })}
                  />
                </label>
                <label>
                  상태
                  <select
                    value={symptom.status}
                    onChange={(event) => updateSymptom(index, {
                      status: event.target.value as SymptomObservation["status"],
                    })}
                  >
                    <option value="present">있음</option>
                    <option value="absent">없음</option>
                  </select>
                </label>
                <label>
                  시작 시점
                  <input
                    value={symptom.onset ?? ""}
                    placeholder="확인되지 않음"
                    onChange={(event) => updateSymptom(index, { onset: event.target.value || null })}
                  />
                </label>
                <label>
                  정도
                  <input
                    value={symptom.severity ?? ""}
                    placeholder="확인되지 않음"
                    onChange={(event) => updateSymptom(index, { severity: event.target.value || null })}
                  />
                </label>
                <p className="source-text">원문 근거: “{symptom.source_text}”</p>
              </div>
            ))}
            <p><strong>복용약:</strong> {intake.medications.join(", ") || "확인되지 않음"}</p>
            <p><strong>알레르기:</strong> {intake.allergies.join(", ") || "확인되지 않음"}</p>
            {intake.unrecognized_fragments.length > 0 && (
              <div className="review-warning" role="alert">
                <strong>자동으로 정리하지 못한 표현</strong>
                {intake.unrecognized_fragments.map((fragment, index) => (
                  <p key={`${fragment}-${index}`}>“{fragment}”</p>
                ))}
                <p>원문을 확인하고 필요한 내용을 직접 추가해 주세요.</p>
              </div>
            )}
            <button type="button" onClick={() => void confirmAndSave()} disabled={savingRecord}>
              {savingRecord ? "저장 중…" : "확인하고 기록 저장"}
            </button>
            {confirmed && <p className="confirmed">확인한 내용을 현재 브라우저에 저장했습니다.</p>}
          </section>
        )}
        {recordMessage && <p className="record-message">{recordMessage}</p>}
        <section className="records" aria-label="저장된 증상 기록">
          <h2>저장된 증상 기록</h2>
          <p>이 기기의 현재 브라우저에만 보관됩니다.</p>
          {records.length === 0 ? (
            <p className="empty-result">아직 저장된 기록이 없습니다.</p>
          ) : records.map((record) => (
            <article className="record" key={record.id}>
              <time dateTime={record.createdAt}>
                {new Intl.DateTimeFormat("ko-KR", {
                  dateStyle: "medium",
                  timeStyle: "short",
                }).format(new Date(record.createdAt))}
              </time>
              <p>{record.transcript}</p>
              <p>
                <strong>증상:</strong>{" "}
                {record.intake.symptoms.map((symptom) => (
                  `${symptom.name}(${symptom.status === "present" ? "있음" : "없음"})`
                )).join(", ") || "확인되지 않음"}
              </p>
              <p><strong>복용약:</strong> {record.intake.medications.join(", ") || "확인되지 않음"}</p>
              <p><strong>알레르기:</strong> {record.intake.allergies.join(", ") || "확인되지 않음"}</p>
              <button className="button--delete" type="button" onClick={() => void removeRecord(record.id)}>
                이 기록 삭제
              </button>
            </article>
          ))}
        </section>
        <p className="privacy-note">
          음성은 글자로 바꾸는 동안만 사용합니다. 확인한 기록은 이 브라우저 안에만
          저장되며 서버에는 보관하지 않습니다.
        </p>
      </section>
    </main>
  );
}
