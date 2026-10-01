import { useEffect, useRef, useState } from "react";
import QRCode from "qrcode";
import {
  deleteIntakeRecord,
  listIntakeRecords,
  saveIntakeRecord,
  type StoredIntakeRecord,
} from "./recordStorage";
import { buildTimeline } from "./timeline";
import { buildSymptomEpisodes } from "./symptomEpisodes";
import { buildVisitSummary, visitSummaryText } from "./visitSummary";
import {
  createRecordGroup,
  deleteRecordGroup,
  getCurrentRecordGroupId,
  LEGACY_RECORD_GROUP_ID,
  prepareRecordGroups,
  setCurrentRecordGroupId,
  type RecordGroup,
} from "./recordGroups";

type Status = "idle" | "recording" | "transcribing" | "done" | "error";

type SymptomObservation = {
  name: string;
  status: "present" | "absent";
  body_site: string | null;
  onset: string | null;
  severity: string | null;
  frequency: string | null;
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
  const [recordGroups, setRecordGroups] = useState<RecordGroup[]>([]);
  const [currentRecordGroupId, setCurrentGroupId] = useState("");
  const [savingRecord, setSavingRecord] = useState(false);
  const [recordMessage, setRecordMessage] = useState("");
  const [summaryMessage, setSummaryMessage] = useState("");
  const [summaryQrCode, setSummaryQrCode] = useState("");
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
  const transcriptRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    void listIntakeRecords()
      .then((loadedRecords) => {
        setRecords(loadedRecords);
        const groups = prepareRecordGroups(loadedRecords);
        setRecordGroups(groups);
        setCurrentGroupId(getCurrentRecordGroupId(groups));
      })
      .catch(() => setRecordMessage("저장된 기록을 불러오지 못했습니다."));
    return () => {
      stopLiveCapture();
      stopMediaTracks();
    };
  }, []);

  useEffect(() => {
    setSummaryQrCode("");
    setSummaryMessage("");
  }, [records]);

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

  function startTextEntry() {
    setStatus("idle");
    setIntake(null);
    setConfirmed(false);
    setMessage("증상을 직접 입력한 뒤 증상 정보 정리를 눌러 주세요.");
    window.requestAnimationFrame(() => transcriptRef.current?.focus());
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
      recordGroupId: currentRecordGroupId,
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

  function selectRecordGroup(id: string) {
    setCurrentRecordGroupId(id);
    setCurrentGroupId(id);
    setTranscript("");
    setIntake(null);
    setConfirmed(false);
    setRecordMessage("");
  }

  function startNewRecordGroup() {
    const group = createRecordGroup();
    setRecordGroups((current) => [group, ...current]);
    selectRecordGroup(group.id);
    setMessage("새 증상 기록을 시작했습니다. 증상을 말하거나 입력해 주세요.");
  }

  async function removeCurrentRecordGroup() {
    if (!currentRecordGroupId) return;
    try {
      await Promise.all(visibleRecords.map((record) => deleteIntakeRecord(record.id)));
      setRecords((current) => current.filter(
        (record) => (record.recordGroupId || LEGACY_RECORD_GROUP_ID) !== currentRecordGroupId,
      ));
      let remaining = deleteRecordGroup(currentRecordGroupId);
      if (remaining.length === 0) {
        const replacement = createRecordGroup();
        remaining = [replacement];
      }
      setRecordGroups(remaining);
      selectRecordGroup(remaining[0].id);
      setRecordMessage("선택한 증상 기록 묶음을 삭제했습니다.");
    } catch {
      setRecordMessage("증상 기록 묶음을 삭제하지 못했습니다.");
    }
  }

  const busy = status === "recording" || status === "transcribing";
  const visibleRecords = records.filter(
    (record) => (record.recordGroupId || LEGACY_RECORD_GROUP_ID) === currentRecordGroupId,
  );
  const timeline = buildTimeline(visibleRecords);
  const symptomEpisodes = buildSymptomEpisodes(visibleRecords);
  const visitSummary = buildVisitSummary(visibleRecords, symptomEpisodes);

  async function copyVisitSummary() {
    if (!visitSummary) return;
    try {
      await navigator.clipboard.writeText(visitSummaryText(visitSummary));
      setSummaryMessage("진료 전 요약을 복사했습니다.");
    } catch {
      setSummaryMessage("요약을 복사하지 못했습니다. 브라우저의 클립보드 권한을 확인해 주세요.");
    }
  }

  async function toggleVisitSummaryQr() {
    if (summaryQrCode) {
      setSummaryQrCode("");
      setSummaryMessage("");
      return;
    }
    if (!visitSummary) return;
    try {
      const dataUrl = await QRCode.toDataURL(visitSummaryText(visitSummary), {
        errorCorrectionLevel: "M",
        margin: 2,
        width: 360,
      });
      setSummaryQrCode(dataUrl);
      setSummaryMessage("QR을 만들었습니다. 환자 정보가 서버로 전송되지는 않습니다.");
    } catch {
      setSummaryMessage("기록이 너무 길어 QR을 만들지 못했습니다. PDF 저장을 이용해 주세요.");
    }
  }

  function printVisitSummary() {
    setSummaryMessage("인쇄 화면에서 대상을 PDF로 저장으로 선택해 주세요.");
    window.print();
  }

  return (
    <main className="page">
      <section className="card" aria-live="polite">
        <p className="eyebrow">MedMap 음성 입력</p>
        <h1>증상을 말로 기록해 보세요</h1>
        <section className="record-group-picker" aria-label="증상 기록 묶음 선택">
          <label htmlFor="record-group">현재 증상 기록</label>
          <select
            id="record-group"
            value={currentRecordGroupId}
            onChange={(event) => selectRecordGroup(event.target.value)}
          >
            {recordGroups.map((group) => (
              <option key={group.id} value={group.id}>{group.name}</option>
            ))}
          </select>
          <button className="button--secondary" type="button" onClick={startNewRecordGroup}>
            새 증상 기록 시작
          </button>
          <button className="button--delete" type="button" onClick={() => void removeCurrentRecordGroup()}>
            현재 증상 기록 묶음 삭제
          </button>
          <p>현재 선택한 기록 안에서만 타임라인, PDF, QR을 만듭니다.</p>
        </section>
        <p className={`status status--${status}`}>{message}</p>

        <div className="controls">
          {status === "recording" ? (
            <button className="button--stop" type="button" onClick={stopRecording}>
              녹음 종료
            </button>
          ) : (
            <>
              <button type="button" onClick={startRecording} disabled={busy}>
                {status === "transcribing" ? "변환 중…" : "음성으로 기록"}
              </button>
              <button
                className="button--secondary"
                type="button"
                onClick={startTextEntry}
                disabled={busy}
              >
                텍스트로 기록
              </button>
            </>
          )}
        </div>

        <label htmlFor="transcript">변환된 문장</label>
        <textarea
          ref={transcriptRef}
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
                <label>
                  횟수
                  <input
                    value={symptom.frequency ?? ""}
                    placeholder="확인되지 않음"
                    onChange={(event) => updateSymptom(index, { frequency: event.target.value || null })}
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
        <section className="visit-summary" aria-label="진료 전 요약">
          <h2>진료 전 요약</h2>
          <p>병원에서 보여줄 수 있도록 확인한 기록을 짧게 정리합니다.</p>
          {!visitSummary ? (
            <p className="empty-result">요약할 기록이 없습니다.</p>
          ) : (
            <div className="visit-summary-card">
              <p>
                <strong>기록 기간</strong><br />
                {new Intl.DateTimeFormat("ko-KR", {
                  dateStyle: "medium",
                  timeStyle: "short",
                }).format(new Date(visitSummary.firstRecordedAt))}
                {" ~ "}
                {new Intl.DateTimeFormat("ko-KR", {
                  dateStyle: "medium",
                  timeStyle: "short",
                }).format(new Date(visitSummary.lastRecordedAt))}
              </p>
              <div className="visit-summary-symptoms">
                <strong>증상 변화</strong>
                <ul>
                  {visitSummary.symptoms.map((symptom) => (
                    <li key={`summary-${symptom.id}`}>
                      <strong>{symptom.name}</strong>
                      {` · ${symptom.status === "active" ? "현재 있음" : "사라짐"}`}
                      {` · 시작: ${symptom.statedOnset || "확인되지 않음"}`}
                      {` · 가장 심한 정도: ${symptom.peakSeverity || "확인되지 않음"}`}
                      {symptom.frequencies.length > 0 && ` · 횟수: ${symptom.frequencies.join(", ")}`}
                      {` · ${symptom.recordCount}회 기록`}
                    </li>
                  ))}
                </ul>
              </div>
              <p><strong>기록 기간 중 복용약:</strong> {visitSummary.medications.join(", ") || "확인되지 않음"}</p>
              <p><strong>기록된 알레르기:</strong> {visitSummary.allergies.join(", ") || "확인되지 않음"}</p>
              <p className="summary-notice">사용자가 확인한 기록의 요약이며 진단 결과가 아닙니다.</p>
              <div className="summary-actions">
                <button className="button--secondary" type="button" onClick={() => void copyVisitSummary()}>
                  요약 복사
                </button>
                <button className="button--secondary" type="button" onClick={printVisitSummary}>
                  PDF로 저장
                </button>
                <button className="button--secondary" type="button" onClick={() => void toggleVisitSummaryQr()}>
                  {summaryQrCode ? "QR 숨기기" : "QR 만들기"}
                </button>
              </div>
              {summaryQrCode && (
                <div className="summary-qr">
                  <img src={summaryQrCode} alt="진료 전 증상 요약 QR 코드" />
                  <p>의사의 카메라로 읽으면 요약 글자가 표시됩니다.</p>
                  <p>QR을 촬영한 사람은 내용을 읽을 수 있으므로 진료할 때만 보여주세요.</p>
                </div>
              )}
              {summaryMessage && <p className="confirmed summary-feedback">{summaryMessage}</p>}
            </div>
          )}
        </section>
        <section className="episodes" aria-label="증상 발생 기간">
          <h2>증상 발생 기간</h2>
          <p>같은 증상이 나타난 때부터 사라진 때까지를 하나로 묶습니다.</p>
          {symptomEpisodes.length === 0 ? (
            <p className="empty-result">묶어서 표시할 증상 기록이 없습니다.</p>
          ) : (
            <div className="episode-list">
              {symptomEpisodes.map((episode) => (
                <article className="episode" key={episode.id}>
                  <div className="episode-heading">
                    <strong>{episode.name}</strong>
                    <span className={`episode-status episode-status--${episode.status}`}>
                      {episode.status === "active" ? "진행 중" : "종료됨"}
                    </span>
                  </div>
                  <p>
                    첫 기록: {new Intl.DateTimeFormat("ko-KR", {
                      dateStyle: "medium",
                      timeStyle: "short",
                    }).format(new Date(episode.startedAt))}
                  </p>
                  {episode.endedAt && (
                    <p>
                      사라짐 기록: {new Intl.DateTimeFormat("ko-KR", {
                        dateStyle: "medium",
                        timeStyle: "short",
                      }).format(new Date(episode.endedAt))}
                    </p>
                  )}
                  <p>말한 시작 시점: {episode.statedOnset || "확인되지 않음"}</p>
                  <p>가장 심한 정도: {episode.peakSeverity || "확인되지 않음"}</p>
                  <p>기록된 횟수: {episode.frequencies.join(", ") || "확인되지 않음"}</p>
                  <p>연결된 기록: {episode.recordCount}개</p>
                </article>
              ))}
            </div>
          )}
        </section>
        <section className="timeline" aria-label="증상 변화 타임라인">
          <h2>증상 변화 타임라인</h2>
          <p>확인하고 저장한 기록만 시간순으로 연결합니다.</p>
          {timeline.length === 0 ? (
            <p className="empty-result">타임라인에 표시할 기록이 없습니다.</p>
          ) : timeline.map((entry) => (
            <article className="timeline-entry" key={entry.id}>
              <time dateTime={entry.createdAt}>
                {new Intl.DateTimeFormat("ko-KR", {
                  dateStyle: "medium",
                  timeStyle: "short",
                }).format(new Date(entry.createdAt))}
              </time>
              {entry.symptoms.length === 0 ? (
                <p>확인된 증상이 없습니다.</p>
              ) : (
                <ul>
                  {entry.symptoms.map((symptom, index) => (
                    <li key={`${entry.id}-${symptom.name}-${index}`}>
                      <strong>{symptom.name}</strong>
                      {` · ${symptom.change}`}
                      {symptom.status === "present" && ` · 시작: ${symptom.onset || "확인되지 않음"}`}
                      {symptom.status === "present" && ` · 정도: ${symptom.severity || "확인되지 않음"}`}
                      {symptom.status === "present" && symptom.frequency && ` · 횟수: ${symptom.frequency}`}
                    </li>
                  ))}
                </ul>
              )}
            </article>
          ))}
        </section>
        <section className="records" aria-label="저장된 증상 기록">
          <h2>저장된 증상 기록</h2>
          <p>이 기기의 현재 브라우저에만 보관됩니다.</p>
          {visibleRecords.length === 0 ? (
            <p className="empty-result">아직 저장된 기록이 없습니다.</p>
          ) : visibleRecords.map((record) => (
            <article className="record" key={record.id}>
              <time dateTime={record.createdAt}>
                {new Intl.DateTimeFormat("ko-KR", {
                  dateStyle: "medium",
                  timeStyle: "short",
                }).format(new Date(record.createdAt))}
              </time>
              <p>{record.transcript}</p>
              <div className="record-symptoms">
                <strong>증상</strong>
                {record.intake.symptoms.length === 0 ? (
                  <p>확인되지 않음</p>
                ) : (
                  <ul>
                    {record.intake.symptoms.map((symptom, index) => (
                      <li key={`${record.id}-${symptom.name}-${index}`}>
                        <strong>{symptom.name}</strong>
                        {` · ${symptom.status === "present" ? "있음" : "없음"}`}
                        {symptom.status === "present" && ` · 시작: ${symptom.onset || "확인되지 않음"}`}
                        {symptom.status === "present" && ` · 정도: ${symptom.severity || "확인되지 않음"}`}
                        {symptom.status === "present" && symptom.frequency && ` · 횟수: ${symptom.frequency}`}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
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
