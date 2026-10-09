import { useEffect, useRef, useState } from "react";
import QRCode from "qrcode";
import {
  deleteIntakeRecord,
  listIntakeRecords,
  saveIntakeRecord,
  saveIntakeRecords,
  type StoredIntakeRecord,
} from "./recordStorage";
import { createBackup, parseBackup } from "./backup";
import {
  detailedSite,
  followUpQuestions,
  formatOnset,
  localDateString,
  addMedicineDetail,
  medicinesWithoutDose,
  nameMedicine,
  parseList,
  SUPPORTED_SYMPTOMS,
  tracksFrequency,
  type FollowUpQuestion,
  unnamedMedicines,
  URGENT_NOTICE,
  severeNotice,
  severeSymptoms,
  urgentSymptoms,
} from "./symptomOptions";
import { buildSymptomHistories, buildTimeline, type SymptomHistoryPoint } from "./timeline";
import { dayKey, monthGrid } from "./calendar";
import { API_BASE, DeviceStt, deviceSttReady, pcm16Base64, usesPhoneStt, Whisper } from "./phoneStt";
import { describeChanges, factChanges, spokenNumbersToDigits, type FactChange } from "./transcriptCheck";
import type { PluginListenerHandle } from "@capacitor/core";
import { hasSpeech, joinChunks, tidyCaption, trimSilence } from "./speechAudio";
import { buildSymptomEpisodes } from "./symptomEpisodes";
import { buildVisitSummary, episodePeriod, profileText, visitSummaryText, wasUrgent } from "./visitSummary";
import {
  createRecordGroup,
  deleteRecordGroup,
  getCurrentRecordGroupId,
  LEGACY_RECORD_GROUP_ID,
  mergeRecordGroups,
  prepareRecordGroups,
  setCurrentRecordGroupId,
  updateRecordGroupProfile,
  type PatientProfile,
  type RecordGroup,
} from "./recordGroups";

type View = "home" | "record" | "review" | "summary" | "history" | "trends" | "profile";
const VIEWS: View[] = ["home", "record", "review", "summary", "history", "trends", "profile"];

// One task per screen; the hash keeps the phone back button working.
function readView(): View {
  const name = window.location.hash.replace(/^#\/?/, "");
  return VIEWS.includes(name as View) ? (name as View) : "home";
}

function go(view: View) {
  window.location.hash = view === "home" ? "" : `/${view}`;
}

const STATUS_LABEL = { present: "있음", absent: "없음", uncertain: "확실하지 않음" } as const;
const TREND_BADGE = {
  improving: { tone: "better", label: "↓ 호전 중" },
  worsening: { tone: "worse", label: "↑ 악화 중" },
  unchanged: { tone: "same", label: "= 변화 없음" },
} as const;
const TONE_MARK = { new: "+", worse: "↑", better: "↓", same: "=", unknown: "?" } as const;
const TONE_LABEL = { new: "새 증상", worse: "악화", better: "호전", same: "비슷함", unknown: "확실하지 않음" } as const;

const pointDate = new Intl.DateTimeFormat("ko-KR", { month: "long", day: "numeric", hour: "2-digit", minute: "2-digit" });
const shortDate = new Intl.DateTimeFormat("ko-KR", { month: "long", day: "numeric" });

// Still there at its latest known record (not "없음" since then).
function isOngoing(history: { points: SymptomHistoryPoint[] }): boolean {
  const known = history.points.filter((point) => point.status !== "uncertain");
  return known[known.length - 1]?.status === "present";
}

// One record of a symptom in words: "5회 · 심함", "없음".
function pointValue(point: SymptomHistoryPoint): string {
  if (point.status !== "present") return STATUS_LABEL[point.status];
  return [point.frequency, point.severity].filter(Boolean).join(" · ") || "있음";
}

// Plain words for the arrow-style changes on screen; the stored wording stays the same.
const CHANGE_LABEL: Record<string, string> = { "있음 → 없음": "사라짐", "없음 → 있음": "다시 생김" };

// One labelled group of short items in the visit summary (medicines, allergies, history ...).
function ChipBlock({ title, items, kind }: { title: string; items: string[]; kind: string }) {
  return (
    <section className={`info-block info-block--${kind}${items.length === 0 ? " info-block--empty" : ""}`}>
      <h3>{title}</h3>
      {items.length > 0 ? (
        <ul className="chips">
          {items.map((item) => <li key={item}>{item}</li>)}
        </ul>
      ) : (
        <p className="info-block__empty">확인되지 않음</p>
      )}
    </section>
  );
}

const ACTION_ICONS = {
  copy: <><rect x="9" y="9" width="12" height="12" rx="2" /><path d="M5 15V5a2 2 0 0 1 2-2h10" /></>,
  pdf: <><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" /><path d="M14 3v5h5" /><path d="M9 14h6M9 17h4" /></>,
  qr: <><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><path d="M14 14h3v3h-3zM21 14v3M14 21h3M20 21h1" /></>,
};

function ActionIcon({ name }: { name: keyof typeof ACTION_ICONS }) {
  return (
    <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {ACTION_ICONS[name]}
    </svg>
  );
}

type Status = "idle" | "recording" | "transcribing" | "done" | "error";

type SymptomObservation = {
  name: string;
  status: "present" | "absent" | "uncertain";
  body_site: string | null;
  onset: string | null;
  onset_date?: string | null;
  severity: string | null;
  frequency: string | null;
  trend: "improving" | "worsening" | "unchanged" | null;
  source_text: string;
};

type IntakeResult = {
  symptoms: SymptomObservation[];
  medications: string[];
  allergies: string[];
  medical_history: string[];
  others_symptoms: OtherPersonSymptom[];
  // Basic information said in this transcript; saved to the record group after review.
  profile: PatientProfile;
  unrecognized_fragments: string[];
  needs_user_confirmation: boolean;
};

type OtherPersonSymptom = {
  person: string;
  symptom: string;
  source_text: string;
};

type ListDrafts = {
  medications: string;
  allergies: string;
  medical_history: string;
};

const EMPTY_LIST_DRAFTS: ListDrafts = { medications: "", allergies: "", medical_history: "" };

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
  const [listDrafts, setListDrafts] = useState<ListDrafts>(EMPTY_LIST_DRAFTS);
  const [backupMessage, setBackupMessage] = useState("");
  const [view, setView] = useState<View>(readView);

  useEffect(() => {
    const onHashChange = () => {
      setView(readView());
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);
  const [skippedQuestions, setSkippedQuestions] = useState<Set<string>>(new Set());
  const [answerDrafts, setAnswerDrafts] = useState<Record<string, string>>({});
  const [extracting, setExtracting] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [records, setRecords] = useState<StoredIntakeRecord[]>([]);
  const [recordGroups, setRecordGroups] = useState<RecordGroup[]>([]);
  const [currentRecordGroupId, setCurrentGroupId] = useState("");
  const [savingRecord, setSavingRecord] = useState(false);
  const [recordMessage, setRecordMessage] = useState("");
  const [summaryMessage, setSummaryMessage] = useState("");
  const [summaryQrCode, setSummaryQrCode] = useState("");
  const [calendarMonth, setCalendarMonth] = useState<Date | null>(null);
  const [selectedDay, setSelectedDay] = useState<string | null>(null);
  const [selectedHistory, setSelectedHistory] = useState<string | null>(null);
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
  // On the phone: the running caption request (small model), awaited before the final transcription.
  const phoneCaptionRef = useRef<Promise<void> | null>(null);
  // On the phone with an on-device Korean recognizer: its caption listener while a recording is live, and the
  // turbo check of the transcript it produced (compared when the patient asks to organize the symptoms).
  const deviceSessionRef = useRef<PluginListenerHandle | null>(null);
  const turboCheckRef = useRef<{ deviceText: string; turbo: Promise<string | null>; done: boolean } | null>(null);
  const [verification, setVerification] = useState<{ quickText: string; turboText: string; changes: FactChange<SymptomObservation>[] } | null>(null);
  const verificationRef = useRef<HTMLDivElement | null>(null);
  // The review screen opens on the on-device transcript; saving waits until turbo has checked it.
  const [turboChecking, setTurboChecking] = useState(false);
  const transcriptRef = useRef<HTMLTextAreaElement | null>(null);
  const savingRecordRef = useRef(false);

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
  }, [records, recordGroups, currentRecordGroupId]);

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
      const chunk = new Float32Array(event.inputBuffer.getChannelData(0));
      liveSamplesRef.current.push(chunk);
      // The on-device recognizer hears the same audio that turbo will check.
      if (deviceSessionRef.current) void DeviceStt.push({ pcm16: pcm16Base64([chunk]) });
    };
    source.connect(processor);
    processor.connect(silentGain);
    silentGain.connect(context.destination);
    audioContextRef.current = context;
    audioSourceRef.current = source;
    audioProcessorRef.current = processor;
    silentGainRef.current = silentGain;
    // The on-device recognizer captions by itself. Otherwise on the phone a small quick model captions and
    // turbo transcribes once at the end; in the browser the server re-transcribes as the patient speaks.
    if (deviceSessionRef.current) return;
    liveIntervalRef.current = window.setInterval(
      () => void (usesPhoneStt ? requestPhoneCaption() : requestLiveTranscript()),
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
      recorder.onstop = () => void (usesPhoneStt ? transcribeOnPhone() : sendRecording(recorder.mimeType || "audio/webm"));
      turboCheckRef.current = null;
      setVerification(null);
      setTurboChecking(false);
      if (usesPhoneStt && await deviceSttReady()) {
        try {
          await DeviceStt.start();
          deviceSessionRef.current = await DeviceStt.addListener("caption", (event) => {
            // Captions are only shown while recording; they are never saved as the record.
            if (deviceSessionRef.current) setTranscript(event.text);
          });
        } catch {
          deviceSessionRef.current = null; // fall back to the small model and turbo
        }
      }
      recorder.start();
      await startLiveCapture(stream);
      setStatus("recording");
      setMessage(deviceSessionRef.current
        ? "듣고 있습니다. 말하는 대로 글자가 나옵니다."
        : usesPhoneStt
          ? "듣고 있습니다. 미리보기 자막은 대략적이고, 녹음 종료를 누르면 정확하게 다시 바꿉니다."
          : "듣고 있습니다. 말하는 동안 변환 문장이 표시됩니다.");
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
    turboCheckRef.current = null; // typed text is the patient's own; nothing to check against
    setVerification(null);
    setTurboChecking(false);
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

  // The 16 kHz samples captured for live preview go to whisper.cpp on the phone; nothing is uploaded.
  function requestPhoneCaption() {
    if (phoneCaptionRef.current || liveSampleRateRef.current !== 16_000) return;
    const samples = joinChunks(liveSamplesRef.current);
    if (!hasSpeech(samples)) return;
    phoneCaptionRef.current = Whisper.preview({ pcm16: pcm16Base64([samples]) })
      .then((result) => {
        // A caption that finishes after "녹음 종료" must not overwrite the final transcript.
        if (liveIntervalRef.current !== null && result.transcript) setTranscript(tidyCaption(result.transcript));
      })
      .catch(() => {
        // No caption model on this phone: keep recording without captions.
        if (liveIntervalRef.current !== null) window.clearInterval(liveIntervalRef.current);
        liveIntervalRef.current = null;
      })
      .finally(() => {
        phoneCaptionRef.current = null;
      });
  }

  async function transcribeOnPhone() {
    chunksRef.current = [];
    const recording = joinChunks(liveSamplesRef.current);
    liveSamplesRef.current = [];
    const session = deviceSessionRef.current;
    deviceSessionRef.current = null;
    void session?.remove();
    if (liveSampleRateRef.current !== 16_000 || !hasSpeech(recording)) {
      if (session) void DeviceStt.stop().catch(() => undefined);
      setStatus("error");
      setMessage("녹음된 말소리가 없습니다. 다시 시도해 주세요.");
      return;
    }
    const stoppedAt = performance.now();
    if (session) {
      try {
        const { transcript: deviceText } = await DeviceStt.stop();
        if (deviceText) {
          setTranscript(deviceText);
          setIntake(null);
          setConfirmed(false);
          setStatus("done");
          setMessage(
            `변환 결과를 확인하고 틀린 부분을 직접 수정해 주세요. 녹음 종료 후 ${((performance.now() - stoppedAt) / 1000).toFixed(1)}초.`
              + " 정밀 인식으로 한 번 더 확인하고 있습니다.",
          );
          // turbo checks the same audio while the patient reads; the result is compared in extractMedicalInformation.
          turboCheckRef.current = {
            deviceText,
            done: false,
            turbo: Whisper.transcribe({ pcm16: pcm16Base64([trimSilence(recording)]) })
              .then((result) => spokenNumbersToDigits(result.transcript))
              .catch(() => null),
          };
          return;
        }
      } catch {
        // The on-device recognizer failed: turbo below transcribes the recording as before.
      }
    }
    setMessage("말씀하신 내용을 정확하게 다시 확인하고 있습니다. 잠시만 기다려 주세요.");
    try {
      await phoneCaptionRef.current;
      const result = await Whisper.transcribe({ pcm16: pcm16Base64([trimSilence(recording)]) });
      setTranscript(spokenNumbersToDigits(result.transcript));
      setIntake(null);
      setConfirmed(false);
      setStatus("done");
      setMessage(
        `변환 결과를 확인하고 틀린 부분을 직접 수정해 주세요. 녹음 종료 후 ${((performance.now() - stoppedAt) / 1000).toFixed(1)}초`
          + ` (녹음 ${result.audio_seconds.toFixed(1)}초${result.load_seconds > 0.5 ? `, 모델 불러오기 ${result.load_seconds.toFixed(1)}초` : ""}).`,
      );
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "음성 변환에 실패했습니다.");
    }
  }

  async function fetchIntake(text: string): Promise<IntakeResult> {
    const response = await fetch(`${API_BASE}/v1/intake/extract`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ transcript: text, reference_date: localDateString() }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "의료정보를 정리하지 못했습니다.");
    return {
      ...data,
      medical_history: data.medical_history ?? [],
      others_symptoms: data.others_symptoms ?? [],
      profile: data.profile ?? {},
    };
  }

  // Runs in the background after the review screen opens on the on-device transcript. When turbo hears the medical
  // facts differently, each difference is offered above the save button to apply or ignore, so the patient's own
  // edits on the review screen stay. A transcript the patient has edited is theirs and is not checked.
  async function checkAgainstTurbo(text: string) {
    const check = turboCheckRef.current;
    if (!check || check.done) return;
    if (text !== check.deviceText) {
      turboCheckRef.current = null;
      return;
    }
    check.done = true;
    setTurboChecking(true);
    try {
      const turboText = await check.turbo;
      if (!turboText) return;
      const changes = turboText === check.deviceText
        ? []
        : factChanges(...await Promise.all([fetchIntake(check.deviceText), fetchIntake(turboText)]));
      // A new recording or typed text started while turbo ran: this result no longer applies.
      if (turboCheckRef.current !== check) return;
      // Kept even without changes, so the patient can read what turbo heard.
      setVerification({ quickText: check.deviceText, turboText, changes });
    } catch {
      // The check is a second opinion; without the API the on-device transcript stands.
    } finally {
      if (turboCheckRef.current === check) setTurboChecking(false);
    }
  }

  // "모두 반영" adds or changes only what turbo heard differently, so details the patient set stay.
  function resolveVerification(apply: boolean) {
    const changes = apply ? verification?.changes ?? [] : [];
    setVerification((current) => current && { ...current, changes: [] });
    if (changes.length === 0) return;
    setIntake((current) => {
      if (!current) return current;
      let symptoms = current.symptoms;
      for (const change of changes) {
        if (change.kind !== "symptom") continue;
        const turboSymptom = change.symptom;
        const index = symptoms.findIndex((symptom) => symptom.name === change.name);
        symptoms = !turboSymptom
          ? symptoms.filter((_, itemIndex) => itemIndex !== index)
          : index < 0
            ? [...symptoms, turboSymptom]
            : symptoms.map((symptom, itemIndex) => itemIndex === index
              ? {
                ...symptom,
                status: turboSymptom.status,
                onset: turboSymptom.onset,
                onset_date: turboSymptom.onset_date,
                severity: turboSymptom.severity ?? symptom.severity,
                frequency: turboSymptom.frequency ?? symptom.frequency,
                trend: turboSymptom.trend ?? symptom.trend,
              }
              : symptom);
      }
      return { ...current, symptoms };
    });
    setListDrafts((current) => {
      const next = { ...current };
      for (const change of changes) {
        if (change.kind === "symptom") continue;
        const items = parseList(next[change.kind]);
        next[change.kind] = [...new Set(change.add ? [...items, change.value] : items.filter((item) => item !== change.value))]
          .join(", ");
      }
      return next;
    });
    setConfirmed(false);
  }

  async function extractMedicalInformation(text = transcript) {
    if (!text.trim()) return;
    setExtracting(true);
    setConfirmed(false);
    try {
      const result = await fetchIntake(text);
      setIntake(result);
      setSkippedQuestions(new Set());
      setAnswerDrafts({});
      setListDrafts({
        medications: result.medications.join(", "),
        allergies: result.allergies.join(", "),
        medical_history: result.medical_history.join(", "),
      });
      go("review");
      void checkAgainstTurbo(text);
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "의료정보를 정리하지 못했습니다.");
    } finally {
      setExtracting(false);
    }
  }

  async function answerFollowUp(question: FollowUpQuestion, answer: string) {
    const value = answer.trim();
    const index = intake?.symptoms.findIndex((symptom) => symptom.name === question.symptom) ?? -1;
    if (!value || !intake || index < 0) return;
    if (question.field !== "onset") {
      updateSymptom(index, { [question.field]: value });
      return;
    }
    // Reuse the extractor so "어제부터" gets the same wording and date as a spoken onset.
    let onset: Pick<SymptomObservation, "onset" | "onset_date"> = { onset: value, onset_date: null };
    try {
      const response = await fetch(`${API_BASE}/v1/intake/extract`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          transcript: `${value} ${intake.symptoms[index].source_text}`,
          reference_date: localDateString(),
        }),
      });
      const data = await response.json();
      const found = response.ok
        ? (data.symptoms as SymptomObservation[]).find((symptom) => symptom.name === question.symptom && symptom.onset)
        : undefined;
      if (found) onset = { onset: found.onset, onset_date: found.onset_date ?? null };
    } catch {
      // Keep the words as typed; the date stays empty.
    }
    updateSymptom(index, onset);
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

  function addSymptom() {
    setIntake((current) => current && ({
      ...current,
      symptoms: [...current.symptoms, {
        name: "",
        status: "present",
        body_site: null,
        onset: null,
        onset_date: null,
        severity: null,
        frequency: null,
        trend: null,
        source_text: "사용자가 직접 추가",
      }],
    }));
    setConfirmed(false);
  }

  function removeSymptom(index: number) {
    setIntake((current) => current && ({
      ...current,
      symptoms: current.symptoms.filter((_, itemIndex) => itemIndex !== index),
    }));
    setConfirmed(false);
  }

  function moveOtherToPatient(index: number) {
    setIntake((current) => {
      if (!current) return current;
      const item = current.others_symptoms[index];
      return {
        ...current,
        others_symptoms: current.others_symptoms.filter((_, itemIndex) => itemIndex !== index),
        symptoms: [...current.symptoms, {
          name: item.symptom,
          status: "present",
          body_site: null,
          onset: null,
        onset_date: null,
          severity: null,
          frequency: null,
          trend: null,
          source_text: item.source_text,
        }],
      };
    });
    setConfirmed(false);
  }

  function removeOther(index: number) {
    setIntake((current) => current && ({
      ...current,
      others_symptoms: current.others_symptoms.filter((_, itemIndex) => itemIndex !== index),
    }));
    setConfirmed(false);
  }

  // Questions about the medicine list: a pill taken without a name, a medicine named without how much.
  const medicineQuestions = [
    ...unnamedMedicines(listDrafts.medications).map((line) => ({
      key: `medicine:${line}`,
      question: `먹은 약 이름이 뭔가요? (${line.replace("이름 모르는 약", "").trim() || "약"})`,
      placeholder: "예: 타이레놀",
      choices: undefined,
      apply: (answer: string) => answer.trim()
        && updateListDraft("medications", nameMedicine(listDrafts.medications, line, answer.trim())),
    })),
    ...medicinesWithoutDose(listDrafts.medications).map((line) => ({
      key: `dose:${line}`,
      question: `${line}: 한 번에 얼마나 먹었나요?`,
      placeholder: "예: 500mg, 자기 전 한 알",
      choices: ["반 알", "한 알", "두 알"],
      apply: (answer: string) => answer.trim()
        && updateListDraft("medications", addMedicineDetail(listDrafts.medications, line, answer.trim())),
    })),
  ].filter((question) => !skippedQuestions.has(question.key));

  function updateListDraft(key: keyof ListDrafts, value: string) {
    setListDrafts((current) => ({ ...current, [key]: value }));
    setConfirmed(false);
  }

  async function confirmAndSave() {
    if (!intake || !transcript.trim() || savingRecordRef.current || confirmed || turboChecking) return;
    if (verification?.changes.length) {
      verificationRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }
    if (!currentRecordGroupId) {
      setRecordMessage("증상 기록 묶음을 불러오는 중입니다. 잠시 후 다시 저장해 주세요.");
      return;
    }
    if (intake.symptoms.some((symptom) => !symptom.name.trim())) {
      setRecordMessage("이름이 비어 있는 증상이 있습니다. 증상 이름을 입력하거나 삭제해 주세요.");
      return;
    }
    savingRecordRef.current = true;
    setSavingRecord(true);
    setRecordMessage("");
    const record: StoredIntakeRecord = {
      id: crypto.randomUUID(),
      recordGroupId: currentRecordGroupId,
      createdAt: new Date().toISOString(),
      transcript: transcript.trim(),
      intake: {
        ...intake,
        symptoms: intake.symptoms.map((symptom) => ({
          ...symptom,
          name: symptom.name.trim(),
          frequency: tracksFrequency(symptom.name.trim()) ? symptom.frequency : null,
        })),
        medications: parseList(listDrafts.medications),
        allergies: parseList(listDrafts.allergies),
        medical_history: parseList(listDrafts.medical_history),
      },
    };
    try {
      await saveIntakeRecord(record);
      setRecords((current) => [record, ...current]);
      setConfirmed(true);
      const said = Object.fromEntries(
        Object.entries(intake.profile).filter(([, value]) => value !== null && value !== undefined),
      ) as PatientProfile;
      if (Object.keys(said).length > 0) updateProfile(said);
      go("summary");
      setRecordMessage("이 브라우저에 기록을 저장했습니다.");
    } catch {
      setConfirmed(false);
      setRecordMessage("기록을 저장하지 못했습니다. 브라우저 저장 권한을 확인해 주세요.");
    } finally {
      savingRecordRef.current = false;
      setSavingRecord(false);
    }
  }

  async function removeRecord(id: string) {
    try {
      await deleteIntakeRecord(id);
      setRecords((current) => current.filter((record) => record.id !== id));
      setRecordMessage("기록을 삭제했습니다.");
      setBackupMessage("");
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
  const turboTextLink = verification && (
    <details className="turbo-text">
      <summary>정밀 인식 문장 보기</summary>
      <p>{verification.turboText}</p>
    </details>
  );
  const verificationBox = verification && (verification.changes.length === 0 ? (
    <div className="verification-done">정밀 인식으로 확인했어요 {turboTextLink}</div>
  ) : (
    <div className="review-warning verification" role="status" ref={verificationRef}>
      <div className="verification__row">
        <strong>정밀 인식이 {verification.changes.length}가지를 다르게 들었어요</strong>
        <button type="button" onClick={() => resolveVerification(true)}>모두 반영</button>
        <button className="button--secondary" type="button" onClick={() => resolveVerification(false)}>무시</button>
      </div>
      <details>
        <summary>무엇이 다른지 보기</summary>
        <p>처음 들은 말 → 다시 확인한 말</p>
        <ul>
          {describeChanges(verification.quickText, verification.turboText, verification.changes)
            .map((line) => <li key={line}>{line}</li>)}
        </ul>
      </details>
      {turboTextLink}
    </div>
  ));
  const visibleRecords = records.filter(
    (record) => (record.recordGroupId || LEGACY_RECORD_GROUP_ID) === currentRecordGroupId,
  );
  const timeline = buildTimeline(visibleRecords);
  const symptomEpisodes = buildSymptomEpisodes(visibleRecords);
  // The calendar opens on the latest recorded day until the user picks another.
  const latestEntry = timeline[timeline.length - 1];
  const shownDay = selectedDay ?? (latestEntry ? dayKey(latestEntry.createdAt) : null);
  const shownMonth = calendarMonth ?? (shownDay ? new Date(`${shownDay}T00:00:00`) : new Date());
  const calendarCells = monthGrid(shownMonth.getFullYear(), shownMonth.getMonth(), timeline, symptomEpisodes);
  const shownDayEntries = timeline.filter((entry) => dayKey(entry.createdAt) === shownDay);
  const todayKey = dayKey(new Date());
  const activeEpisodes = symptomEpisodes.filter((episode) => episode.status === "active");
  const moveMonth = (offset: number) =>
    setCalendarMonth(new Date(shownMonth.getFullYear(), shownMonth.getMonth() + offset, 1));
  const profile = recordGroups.find((group) => group.id === currentRecordGroupId)?.profile ?? {};
  const visitSummary = buildVisitSummary(visibleRecords, symptomEpisodes, profile);
  const step = view === "record" ? 1 : view === "review" ? 2 : view === "summary" ? 3 : 0;
  const symptomHistories = buildSymptomHistories(timeline);
  const shownHistory = symptomHistories.find((history) => history.name === selectedHistory) ?? symptomHistories[0];
  const shownKnown = shownHistory?.points.filter((point) => point.status !== "uncertain") ?? [];
  // Two pages, not tabs: each has its own address, so the phone's back button returns to the other.
  const historySwitch = (
    <nav className="view-switch" aria-label="지난 기록 보는 방식">
      <a href="#/history" aria-current={view === "history" ? "page" : undefined}>날짜별</a>
      <a href="#/trends" aria-current={view === "trends" ? "page" : undefined}>증상별</a>
    </nav>
  );

  function startNewEntry() {
    setTranscript("");
    setIntake(null);
    setConfirmed(false);
    setRecordMessage("");
    go("record");
  }
  const currentGroupName = recordGroups.find((group) => group.id === currentRecordGroupId)?.name;

  function updateProfile(changes: Partial<PatientProfile>) {
    if (!currentRecordGroupId) return;
    setRecordGroups(updateRecordGroupProfile(currentRecordGroupId, { ...profile, ...changes }));
  }

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

  function exportBackup() {
    if (records.length === 0) {
      setBackupMessage("내보낼 기록이 없습니다.");
      return;
    }
    const backup = createBackup(recordGroups, records);
    const url = URL.createObjectURL(new Blob([JSON.stringify(backup, null, 2)], { type: "application/json" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `medmap-backup-${backup.exportedAt.slice(0, 10)}.json`;
    link.click();
    URL.revokeObjectURL(url);
    setBackupMessage(`기록 ${records.length}개를 백업 파일로 내보냈습니다. 파일에 건강 정보가 들어 있으니 안전하게 보관해 주세요.`);
  }

  async function importBackup(file: File) {
    setRecordMessage("");
    try {
      const backup = parseBackup(await file.text());
      const knownIds = new Set(records.map((record) => record.id));
      const newRecords = backup.records.filter((record) => !knownIds.has(record.id));
      await saveIntakeRecords(newRecords);
      const allRecords = [...records, ...newRecords].sort(
        (left, right) => right.createdAt.localeCompare(left.createdAt),
      );
      mergeRecordGroups(backup.groups);
      setRecords(allRecords);
      setRecordGroups(prepareRecordGroups(allRecords));
      const skipped = backup.records.length - newRecords.length;
      setBackupMessage(
        `기록 ${newRecords.length}개를 가져왔습니다.`
          + (skipped > 0 ? ` 이미 있는 기록 ${skipped}개는 건너뛰었습니다.` : ""),
      );
    } catch (error) {
      setBackupMessage(error instanceof Error ? error.message : "백업 파일을 가져오지 못했습니다.");
    }
  }

  return (
    <main className="page">
      <section className="card" aria-live="polite">
        {view === "home" ? (
          <>
            <p className="eyebrow">MedMap 진료 전 기록</p>
            <h1>증상을 기록하고 진료 때 보여 주세요</h1>
          </>
        ) : (
          <button className="back-link" type="button" onClick={() => go("home")}>← 처음 화면</button>
        )}
        {step > 0 && (
        <ol className="steps" aria-label="사용 순서">
          {["증상 말하기", "정리된 내용 확인", "진료 전 요약 보여 주기"].map((label, index) => (
            <li
              key={label}
              className={index + 1 === step ? "steps__item steps__item--current" : "steps__item"}
              aria-current={index + 1 === step ? "step" : undefined}
            >
              <span>{index + 1}</span>{label}
            </li>
          ))}
        </ol>
        )}
        {view === "home" && (
        <details className="record-group-picker">
          <summary>기록 묶음: {currentGroupName ?? "불러오는 중"}</summary>
          <label htmlFor="record-group">기록 묶음 바꾸기</label>
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
          <p>아픈 기간마다 기록 묶음을 나누면, 요약·타임라인·PDF·QR이 그 묶음 안에서만 만들어집니다.</p>
        </details>
        )}
        {view === "home" && latestEntry && (
          <section className="home-status" aria-label="지금 기록 상태">
            <h2>진행 중인 증상</h2>
            {activeEpisodes.length > 0 ? (
              <ul className="chips">
                {activeEpisodes.map((episode) => (
                  <li key={episode.id}>{episode.name} · {episodePeriod(episode)}</li>
                ))}
              </ul>
            ) : (
              <p>진행 중인 증상이 없습니다.</p>
            )}
            <p className="home-status__last">
              마지막 기록: {new Intl.DateTimeFormat("ko-KR", { month: "long", day: "numeric", weekday: "short" }).format(new Date(latestEntry.createdAt))}
            </p>
          </section>
        )}
        {view === "home" && (
          <div className="home-menu">
            <button className="home-menu__primary" type="button" onClick={startNewEntry}>새 증상 기록하기</button>
            <button className="button--secondary" type="button" onClick={() => go("summary")} disabled={!visitSummary}>
              진료 전 요약 보기
            </button>
            <button className="button--secondary" type="button" onClick={() => go("history")}>
              지난 기록 보기 ({visibleRecords.length}개)
            </button>
            <button className="button--secondary" type="button" onClick={() => go("profile")}>
              기본 정보 {profileText(profile) ? `(${profileText(profile)})` : "입력"}
            </button>
          </div>
        )}
        {view === "profile" && (
        <section className="patient-profile">
          <h2 className="step-title">기본 정보 (선택)</h2>
          <p>진료 전 요약에 함께 적힙니다. 이 브라우저에만 저장됩니다.</p>
          <label>
            나이
            <input
              type="number"
              min={0}
              max={130}
              value={profile.age ?? ""}
              onChange={(event) => updateProfile({
                age: event.target.value === "" ? null : Math.min(130, Math.max(0, Math.floor(Number(event.target.value)))),
              })}
            />
          </label>
          <label>
            성별
            <select
              value={profile.sex ?? ""}
              onChange={(event) => updateProfile({ sex: (event.target.value || null) as PatientProfile["sex"] })}
            >
              <option value="">선택 안 함</option>
              <option value="female">여성</option>
              <option value="male">남성</option>
            </select>
          </label>
          {profile.sex === "female" && (
            <label>
              임신 가능성
              <select
                value={profile.pregnancy ?? ""}
                onChange={(event) => updateProfile({ pregnancy: (event.target.value || null) as PatientProfile["pregnancy"] })}
              >
                <option value="">선택 안 함</option>
                <option value="yes">임신 중이거나 가능성 있음</option>
                <option value="no">임신 아님</option>
                <option value="unknown">모름</option>
              </select>
            </label>
          )}
          <label>
            흡연
            <select
              value={profile.smoking ?? ""}
              onChange={(event) => updateProfile({ smoking: (event.target.value || null) as PatientProfile["smoking"] })}
            >
              <option value="">선택 안 함</option>
              <option value="current">흡연</option>
              <option value="former">과거 흡연</option>
              <option value="never">비흡연</option>
            </select>
          </label>
          <label>
            음주
            <select
              value={profile.drinking ?? ""}
              onChange={(event) => updateProfile({ drinking: (event.target.value || null) as PatientProfile["drinking"] })}
            >
              <option value="">선택 안 함</option>
              <option value="yes">음주</option>
              <option value="no">음주 안 함</option>
            </select>
          </label>
          <button type="button" onClick={() => go("home")}>완료</button>
        </section>
        )}
        {view === "record" && (
        <>
        <h2 className="step-title">1. 증상을 말하거나 적어 주세요</h2>
        <p className={`status status--${status}`}>{message}</p>
        {status === "transcribing" && <progress className="stt-progress" aria-label="음성 변환 중" />}

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
          type="button"
          onClick={() => void extractMedicalInformation()}
          disabled={!transcript.trim() || extracting || busy}
        >
          {extracting ? "정리 중…" : "다음: 증상 정리하기"}
        </button>
        </>
        )}

        {view === "review" && !intake && (
          <div className="empty-step">
            <p className="empty-result">정리된 내용이 없습니다. 먼저 증상을 말하거나 적어 주세요.</p>
            <button type="button" onClick={() => go("record")}>증상 말하기로 가기</button>
          </div>
        )}
        {view === "review" && intake && (
          <section className="intake" aria-label="정리된 의료정보">
            <h2 className="step-title">2. 정리된 내용을 확인해 주세요</h2>
            {urgentSymptoms(intake.symptoms).length > 0 && (
              <div className="urgent-notice" role="alert">
                <strong>{urgentSymptoms(intake.symptoms).join(", ")}</strong>
                <p>{URGENT_NOTICE}</p>
              </div>
            )}
            {severeSymptoms(intake.symptoms).length > 0 && (
              <p className="severe-notice" role="status">{severeNotice(severeSymptoms(intake.symptoms))}</p>
            )}
            {intake.unrecognized_fragments.length > 0 && (
              <div className="review-warning" role="alert">
                <strong>자동으로 정리하지 못한 표현</strong>
                {intake.unrecognized_fragments.map((fragment, index) => (
                  <p key={`${fragment}-${index}`}>“{fragment}”</p>
                ))}
                <p>원문을 확인하고 필요하면 아래 ‘증상 직접 추가’로 넣어 주세요.</p>
              </div>
            )}
            {followUpQuestions(intake.symptoms).filter((question) => !skippedQuestions.has(question.key)).length
              + medicineQuestions.length > 0 && (
              <div className="follow-up">
                <strong>추가로 알려 주세요</strong>
                {followUpQuestions(intake.symptoms)
                  .filter((question) => !skippedQuestions.has(question.key))
                  .map((question) => (
                    <div className="follow-up-item" key={question.key}>
                      <p>{question.question}</p>
                      {question.choices && (
                        <div className="follow-up-choices">
                          {question.choices.map((choice) => (
                            <button
                              className="button--secondary"
                              type="button"
                              key={choice}
                              onClick={() => void answerFollowUp(question, choice)}
                            >
                              {choice}
                            </button>
                          ))}
                        </div>
                      )}
                      <div className="follow-up-answer">
                        <input
                          value={answerDrafts[question.key] ?? ""}
                          placeholder={question.field === "onset" ? "예: 어제부터, 3일 전부터" : "직접 입력"}
                          aria-label={question.question}
                          onChange={(event) => setAnswerDrafts((current) => ({ ...current, [question.key]: event.target.value }))}
                        />
                        <button
                          className="button--secondary"
                          type="button"
                          onClick={() => void answerFollowUp(question, answerDrafts[question.key] ?? "")}
                        >
                          입력
                        </button>
                        <button
                          className="button--secondary"
                          type="button"
                          onClick={() => setSkippedQuestions((current) => new Set(current).add(question.key))}
                        >
                          건너뛰기
                        </button>
                      </div>
                    </div>
                  ))}
                {medicineQuestions.map(({ key, question, placeholder, choices, apply }) => (
                  <div className="follow-up-item" key={key}>
                    <p>{question}</p>
                    {choices && (
                      <div className="follow-up-choices">
                        {choices.map((choice) => (
                          <button className="button--secondary" type="button" key={choice} onClick={() => apply(choice)}>
                            {choice}
                          </button>
                        ))}
                      </div>
                    )}
                    <div className="follow-up-answer">
                      <input
                        value={answerDrafts[key] ?? ""}
                        placeholder={placeholder}
                        aria-label={question}
                        onChange={(event) => setAnswerDrafts((current) => ({ ...current, [key]: event.target.value }))}
                      />
                      <button className="button--secondary" type="button" onClick={() => apply(answerDrafts[key] ?? "")}>
                        입력
                      </button>
                      <button
                        className="button--secondary"
                        type="button"
                        onClick={() => setSkippedQuestions((current) => new Set(current).add(key))}
                      >
                        건너뛰기
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
            <p>잘못 정리된 내용은 직접 고친 뒤 확인해 주세요.</p>
            {intake.symptoms.length === 0 ? (
              <p className="empty-result">현재 규칙에서 찾은 증상이 없습니다.</p>
            ) : intake.symptoms.map((symptom, index) => (
              <div
                className={urgentSymptoms([symptom]).length > 0 ? "observation observation--urgent" : "observation"}
                key={index}
              >
                <div className="observation-header">
                  <strong className="observation-name">{symptom.name || "새 증상"}</strong>
                  <span className={`badge badge--${symptom.status}`}>{STATUS_LABEL[symptom.status]}</span>
                  {detailedSite(symptom.body_site) && <span className="badge badge--site">{symptom.body_site}</span>}
                  {symptom.status === "present" && symptom.trend && (
                    <span className={`trend trend--${TREND_BADGE[symptom.trend].tone}`}>{TREND_BADGE[symptom.trend].label}</span>
                  )}
                </div>
                {symptom.status === "present" && (
                  <dl className="facts">
                    <div><dt>시작</dt><dd>{formatOnset(symptom.onset, symptom.onset_date) || "확인되지 않음"}</dd></div>
                    <div><dt>정도</dt><dd>{symptom.severity || "확인되지 않음"}</dd></div>
                    {tracksFrequency(symptom.name) && <div><dt>횟수</dt><dd>{symptom.frequency || "확인되지 않음"}</dd></div>}
                  </dl>
                )}
                <p className="source-text">원문 근거: “{symptom.source_text}”</p>
                {/* Details stay folded until the patient wants to correct them; a hand-added symptom opens ready to fill. */}
                <details className="observation-edit" open={symptom.source_text === "사용자가 직접 추가" || undefined}>
                <summary>고치기</summary>
                <div className="observation-fields">
                <label>
                  증상
                  <input
                    value={symptom.name}
                    list="supported-symptoms"
                    placeholder="증상 이름"
                    onChange={(event) => updateSymptom(index, { name: event.target.value })}
                  />
                </label>
                <label>
                  부위
                  <input
                    value={symptom.body_site ?? ""}
                    placeholder="확인되지 않음"
                    onChange={(event) => updateSymptom(index, { body_site: event.target.value || null })}
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
                    <option value="uncertain">확실하지 않음</option>
                  </select>
                </label>
                <label>
                  시작 시점
                  <input
                    value={symptom.onset ?? ""}
                    placeholder="확인되지 않음"
                    onChange={(event) => updateSymptom(index, { onset: event.target.value || null, onset_date: null })}
                  />
                  {symptom.onset_date && (
                    <span className="onset-date">{formatOnset(symptom.onset, symptom.onset_date)}</span>
                  )}
                </label>
                <label>
                  정도
                  <input
                    value={symptom.severity ?? ""}
                    placeholder="확인되지 않음"
                    onChange={(event) => updateSymptom(index, { severity: event.target.value || null })}
                  />
                </label>
                {tracksFrequency(symptom.name) && (
                  <label>
                    횟수
                    <input
                      value={symptom.frequency ?? ""}
                      placeholder="확인되지 않음"
                      onChange={(event) => updateSymptom(index, { frequency: event.target.value || null })}
                    />
                  </label>
                )}
                {symptom.status === "present" && (
                  <label>
                    이전보다 변화
                    <select
                      value={symptom.trend ?? ""}
                      onChange={(event) => updateSymptom(index, {
                        trend: (event.target.value || null) as SymptomObservation["trend"],
                      })}
                    >
                      <option value="">확인되지 않음</option>
                      <option value="improving">호전 중</option>
                      <option value="worsening">악화 중</option>
                      <option value="unchanged">변화 없음</option>
                    </select>
                  </label>
                )}
                <button className="button--delete" type="button" onClick={() => removeSymptom(index)}>
                  이 증상 삭제
                </button>
                </div>
                </details>
              </div>
            ))}
            <datalist id="supported-symptoms">
              {SUPPORTED_SYMPTOMS.map((name) => <option key={name} value={name} />)}
            </datalist>
            <button className="button--secondary" type="button" onClick={addSymptom}>
              증상 직접 추가
            </button>
            <div className="intake-lists">
              <label>
                복용약
                <input
                  value={listDrafts.medications}
                  placeholder="확인되지 않음 (쉼표로 구분)"
                  onChange={(event) => updateListDraft("medications", event.target.value)}
                />
              </label>
              <label>
                알레르기
                <input
                  value={listDrafts.allergies}
                  placeholder="확인되지 않음 (쉼표로 구분)"
                  onChange={(event) => updateListDraft("allergies", event.target.value)}
                />
              </label>
              <label>
                과거력 (앓고 있는 병, 수술)
                <input
                  value={listDrafts.medical_history}
                  placeholder="확인되지 않음 (쉼표로 구분)"
                  onChange={(event) => updateListDraft("medical_history", event.target.value)}
                />
              </label>
            </div>
            {profileText(intake.profile) && (
              <div className="others-review">
                <strong>말에서 찾은 기본 정보</strong>
                <p>{profileText(intake.profile)}</p>
                <p>저장하면 기본 정보 칸에 반영됩니다.</p>
                <button
                  className="button--secondary"
                  type="button"
                  onClick={() => setIntake((current) => current && { ...current, profile: {} })}
                >
                  반영하지 않기
                </button>
              </div>
            )}
            {intake.others_symptoms.length > 0 && (
              <div className="others-review">
                <strong>다른 사람에 대한 내용으로 보이는 표현</strong>
                <p>환자 본인의 증상이 아니어서 따로 모았습니다. 본인 증상이면 옮겨 주세요.</p>
                {intake.others_symptoms.map((item, index) => (
                  <div className="others-item" key={`${item.person}-${item.symptom}-${index}`}>
                    <span>{item.person}: {item.symptom} (“{item.source_text}”)</span>
                    <button className="button--secondary" type="button" onClick={() => moveOtherToPatient(index)}>
                      본인 증상으로 옮기기
                    </button>
                    <button className="button--delete" type="button" onClick={() => removeOther(index)}>
                      삭제
                    </button>
                  </div>
                ))}
              </div>
            )}
            {verificationBox}
            <button type="button" onClick={() => void confirmAndSave()} disabled={savingRecord || confirmed || !currentRecordGroupId || turboChecking}>
              {savingRecord ? "저장 중…" : turboChecking ? "정밀 인식 확인 중…" : verification?.changes.length ? "위 정밀 인식 결과를 먼저 확인해 주세요" : "확인하고 기록 저장"}
            </button>
            {turboChecking && <p className="record-message">말씀하신 내용을 정밀 인식으로 한 번 더 확인하고 있습니다. 그동안 내용을 확인하고 고칠 수 있습니다.</p>}
            {confirmed && <p className="confirmed">확인한 내용을 현재 브라우저에 저장했습니다.</p>}
          </section>
        )}
        {recordMessage && <p className="record-message">{recordMessage}</p>}
        {view === "summary" && (
        <>
        <section className="visit-summary" aria-label="진료 전 요약">
          <h2 className="step-title">3. 진료 전 요약</h2>
          <p>병원에서 보여줄 수 있도록 확인한 기록을 짧게 정리합니다.</p>
          {!visitSummary ? (
            <p className="empty-result">요약할 기록이 없습니다.</p>
          ) : (
            <div className="visit-summary-card">
              <p className="summary-meta">
                <span className="summary-meta__label">기록 기간</span>
                <span>
                  {new Intl.DateTimeFormat("ko-KR", {
                    dateStyle: "medium",
                    timeStyle: "short",
                  }).format(new Date(visitSummary.firstRecordedAt))}
                  {" ~ "}
                  {new Intl.DateTimeFormat("ko-KR", {
                    dateStyle: "medium",
                    timeStyle: "short",
                  }).format(new Date(visitSummary.lastRecordedAt))}
                </span>
              </p>
              {visitSummary.profile && (
                <ChipBlock title="기본 정보" kind="profile" items={visitSummary.profile.split(" / ")} />
              )}
              {visitSummary.urgentSymptoms.length > 0 && (
                <div className="urgent-notice" role="alert">
                  <strong>{visitSummary.urgentSymptoms.join(", ")}</strong>
                  <p>{URGENT_NOTICE}</p>
                </div>
              )}
              {visitSummary.severeSymptoms.length > 0 && (
                <p className="severe-notice" role="status">{severeNotice(visitSummary.severeSymptoms)}</p>
              )}
              <div className="visit-summary-symptoms">
                <strong>지금 있는 증상</strong>
                {visitSummary.symptoms.every((symptom) => symptom.status !== "active") && (
                  <p className="empty-result">지금 있는 증상이 없습니다.</p>
                )}
                <ul className="symptom-list">
                  {visitSummary.symptoms.filter((symptom) => symptom.status === "active").map((symptom) => (
                    <li key={`summary-${symptom.id}`} className="symptom-row">
                      <div className="symptom-row__head">
                        <strong>{symptom.name}</strong>
                        {symptom.latestTrend && (
                          <span className={`trend trend--${TREND_BADGE[symptom.latestTrend].tone}`}>
                            {TREND_BADGE[symptom.latestTrend].label}
                          </span>
                        )}
                      </div>
                      <dl className="facts">
                        {symptom.bodySite && <div><dt>부위</dt><dd>{symptom.bodySite}</dd></div>}
                        <div><dt>시작</dt><dd>{formatOnset(symptom.statedOnset, symptom.statedOnsetDate) || "확인되지 않음"}</dd></div>
                        <div><dt>가장 심한 정도</dt><dd>{symptom.peakSeverity || "확인되지 않음"}</dd></div>
                        {tracksFrequency(symptom.name) && symptom.frequencies.length > 0 && (
                          <div><dt>횟수</dt><dd>{symptom.frequencies.join(", ")}</dd></div>
                        )}
                        <div><dt>기록</dt><dd>{symptom.recordCount}회</dd></div>
                      </dl>
                    </li>
                  ))}
                </ul>
                {visitSummary.symptoms.some((symptom) => symptom.status === "resolved") && (
                  <>
                    <strong className="resolved-title">사라진 증상</strong>
                    <ul className="resolved-list">
                      {visitSummary.symptoms.filter((symptom) => symptom.status === "resolved").map((symptom) => (
                        <li key={`resolved-${symptom.id}`} className={wasUrgent(symptom) ? "resolved-list__urgent" : undefined}>
                          <span className="resolved-list__name">{symptom.name}</span>
                          {wasUrgent(symptom) && <span className="badge badge--urgent">위험 증상</span>}
                          <span>
                            {episodePeriod(symptom)}
                            {symptom.peakSeverity && ` · 최고 ${symptom.peakSeverity}`}
                            {tracksFrequency(symptom.name) && symptom.frequencies.length > 0 && ` · ${symptom.frequencies.join(", ")}`}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </div>
              <div className="info-grid">
                <ChipBlock title="알레르기" kind="allergy" items={visitSummary.allergies} />
                <ChipBlock title="기록 기간 중 복용약" kind="medication" items={visitSummary.medications} />
                <ChipBlock title="과거력" kind="history" items={visitSummary.medicalHistory} />
                {visitSummary.uncertainSymptoms.length > 0 && (
                  <ChipBlock title="있는지 확실하지 않다고 한 증상" kind="uncertain" items={visitSummary.uncertainSymptoms} />
                )}
                {visitSummary.othersSymptoms.length > 0 && (
                  <ChipBlock title="주변 사람에 대해 말한 내용" kind="others" items={visitSummary.othersSymptoms} />
                )}
              </div>
              <p className="summary-notice">사용자가 확인한 기록의 요약이며 진단 결과가 아닙니다.</p>
              <div className="summary-actions" aria-label="요약 보내기">
                <button className="button--secondary action-tile" type="button" onClick={() => void copyVisitSummary()}>
                  <ActionIcon name="copy" />
                  <span className="action-tile__label">요약 복사</span>
                  <span className="action-tile__hint">문자·메모에 붙여넣기</span>
                </button>
                <button className="button--secondary action-tile" type="button" onClick={printVisitSummary}>
                  <ActionIcon name="pdf" />
                  <span className="action-tile__label">PDF로 저장</span>
                  <span className="action-tile__hint">파일·인쇄</span>
                </button>
                <button className="button--secondary action-tile" type="button" onClick={() => void toggleVisitSummaryQr()}>
                  <ActionIcon name="qr" />
                  <span className="action-tile__label">{summaryQrCode ? "QR 숨기기" : "QR 만들기"}</span>
                  <span className="action-tile__hint">의사 카메라로 읽기</span>
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
        <div className="next-actions">
          <button type="button" onClick={startNewEntry}>새 증상 기록하기</button>
          <button className="button--secondary" type="button" onClick={() => go("history")}>지난 기록 보기</button>
        </div>
        </>
        )}
        {view === "trends" && (
        <>
        <h2 className="step-title">지난 기록</h2>
        {historySwitch}
        {!shownHistory ? (
          <p className="empty-result">아직 저장된 기록이 없습니다.</p>
        ) : (
          <>
            {/* One line however many symptoms pile up; the phone's own list opens on tap. */}
            <div className="symptom-picker">
              <label htmlFor="symptom-history">볼 증상</label>
              <select
                id="symptom-history"
                value={shownHistory.name}
                onChange={(event) => setSelectedHistory(event.target.value)}
              >
                {([["지금 있는 증상", true], ["사라진 증상", false]] as const).map(([label, ongoing]) => {
                  const histories = symptomHistories.filter((history) => isOngoing(history) === ongoing);
                  return histories.length > 0 && (
                    <optgroup key={label} label={label}>
                      {histories.map((history) => (
                        <option key={history.name} value={history.name}>{history.name}</option>
                      ))}
                    </optgroup>
                  );
                })}
              </select>
            </div>
            <section className="symptom-history" aria-label={`${shownHistory.name} 기록 변화`}>
              <div className="symptom-history__head">
                <h3>{shownHistory.name}</h3>
                {shownHistory.overall && (
                  <span className={`trend trend--${shownHistory.overall.tone}`}>
                    {TONE_MARK[shownHistory.overall.tone]} {shownHistory.overall.label}
                  </span>
                )}
              </div>
              {shownHistory.overall ? (
                <div className="then-now">
                  <div>
                    <span>처음 · {shortDate.format(new Date(shownKnown[0].createdAt))}</span>
                    <strong>{pointValue(shownKnown[0])}</strong>
                  </div>
                  <span className="then-now__arrow" aria-hidden="true">→</span>
                  <div>
                    <span>최근 · {shortDate.format(new Date(shownKnown[shownKnown.length - 1].createdAt))}</span>
                    <strong>{pointValue(shownKnown[shownKnown.length - 1])}</strong>
                  </div>
                </div>
              ) : (
                <p className="empty-result">기록이 한 번뿐이라 아직 비교할 수 없어요. 다음에 또 기록하면 여기서 변화를 볼 수 있어요.</p>
              )}
              <ol className="history-points" aria-label="기록한 순서">
                {shownHistory.points.map((point, index) => (
                  <li key={`${point.createdAt}-${index}`}>
                    <time dateTime={point.createdAt}>{pointDate.format(new Date(point.createdAt))}</time>
                    <span className={`trend trend--${point.tone}`}>
                      {TONE_MARK[point.tone]} {CHANGE_LABEL[point.change] ?? point.change}
                    </span>
                    <strong className="history-points__value">{pointValue(point)}</strong>
                    {point.level !== null && (
                      <span className="history-points__bar" aria-hidden="true">
                        <i style={{ width: `${Math.max(4, Math.round(point.level * 100))}%` }} />
                      </span>
                    )}
                  </li>
                ))}
              </ol>
            </section>
          </>
        )}
        </>
        )}

        {view === "history" && (
        <>
        <h2 className="step-title">지난 기록</h2>
        {historySwitch}
        <section className="calendar" aria-label="증상 기록 달력">
          <div className="calendar__head">
            <button className="button--secondary" type="button" onClick={() => moveMonth(-1)} aria-label="이전 달">‹</button>
            <h2>{shownMonth.getFullYear()}년 {shownMonth.getMonth() + 1}월</h2>
            <button className="button--secondary" type="button" onClick={() => moveMonth(1)} aria-label="다음 달">›</button>
          </div>
          <div className="calendar__grid">
            {["일", "월", "화", "수", "목", "금", "토"].map((weekday) => (
              <span className="calendar__weekday" key={weekday}>{weekday}</span>
            ))}
            {calendarCells.map((cell, index) => cell ? (
              <button
                key={cell.key}
                type="button"
                className={`calendar__day${cell.inEpisode ? " calendar__day--episode" : ""}${cell.key === shownDay ? " calendar__day--selected" : ""}${cell.key === todayKey ? " calendar__day--today" : ""}`}
                aria-current={cell.key === todayKey ? "date" : undefined}
                onClick={() => setSelectedDay(cell.key)}
                aria-pressed={cell.key === shownDay}
                aria-label={`${cell.day}일${cell.tone ? `, 기록 있음 (${TONE_LABEL[cell.tone]})` : ""}`}
              >
                {cell.day}
                {cell.tone && <span className={`calendar__dot calendar__dot--${cell.tone}`} />}
              </button>
            ) : <span key={`pad-${index}`} />)}
          </div>
          <p className="calendar__legend">
            <span><i className="calendar__dot calendar__dot--worse" />악화</span>
            <span><i className="calendar__dot calendar__dot--new" />새 증상</span>
            <span><i className="calendar__dot calendar__dot--same" />비슷함</span>
            <span><i className="calendar__dot calendar__dot--better" />호전</span>
            <span><i className="calendar__swatch" />증상 기간</span>
          </p>
          {symptomEpisodes.length > 0 && (
            <ul className="episode-lines">
              {symptomEpisodes.map((episode) => (
                <li key={episode.id}>
                  <strong>{episode.name}</strong>
                  <span className={`episode-status episode-status--${episode.status}`}>
                    {episode.status === "active" ? "진행 중" : "종료됨"}
                  </span>
                  <span>
                    {episodePeriod(episode)}
                    {episode.peakSeverity && ` · 최고 ${episode.peakSeverity}`}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section className="timeline" aria-label="선택한 날의 기록">
          <h2>{shownDay ? `${Number(shownDay.slice(5, 7))}월 ${Number(shownDay.slice(8))}일 기록` : "기록"}</h2>
          {shownDayEntries.length === 0 ? (
            <p className="empty-result">
              {timeline.length === 0 ? "아직 저장된 기록이 없습니다." : "이 날은 기록이 없습니다. 점이 찍힌 날을 눌러 보세요."}
            </p>
          ) : shownDayEntries.map((entry) => (
            <article className="timeline-entry" key={entry.id}>
              <time dateTime={entry.createdAt}>
                {new Intl.DateTimeFormat("ko-KR", { timeStyle: "short" }).format(new Date(entry.createdAt))}
              </time>
              {entry.symptoms.length === 0 ? (
                <p>확인된 증상이 없습니다.</p>
              ) : (
                <ul className="symptom-list">
                  {entry.symptoms.map((symptom, index) => (
                    <li key={`${entry.id}-${symptom.name}-${index}`} className="symptom-row">
                      <div className="symptom-row__head">
                        <strong>{symptom.name}</strong>
                        <span className={`trend trend--${symptom.tone}`}>
                          {TONE_MARK[symptom.tone]} {CHANGE_LABEL[symptom.change] ?? symptom.change}
                        </span>
                      </div>
                      {symptom.status === "present" && (
                        <dl className="facts">
                          {detailedSite(symptom.body_site) && <div><dt>부위</dt><dd>{symptom.body_site}</dd></div>}
                          <div><dt>시작</dt><dd>{formatOnset(symptom.onset, symptom.onset_date) || "확인되지 않음"}</dd></div>
                          <div><dt>정도</dt><dd>{symptom.severity || "확인되지 않음"}</dd></div>
                          {tracksFrequency(symptom.name) && symptom.frequency && <div><dt>횟수</dt><dd>{symptom.frequency}</dd></div>}
                        </dl>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </article>
          ))}
        </section>
        <details className="history">
          <summary>저장된 기록 관리·백업 ({visibleRecords.length}개)</summary>
          <p>이 기기의 현재 브라우저에만 보관됩니다.</p>
          <div className="backup-actions">
            <button className="button--secondary" type="button" onClick={exportBackup}>
              전체 기록 백업 파일로 내보내기
            </button>
            <label className="button--secondary backup-import">
              백업 파일 가져오기
              <input
                type="file"
                accept="application/json,.json"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  event.target.value = "";
                  if (file) void importBackup(file);
                }}
              />
            </label>
          </div>
          <p className="backup-note">다른 브라우저나 기기로 옮길 때 사용하세요. 백업 파일은 서버로 전송되지 않습니다.</p>
          {backupMessage && <p className="record-message">{backupMessage}</p>}
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
                        {` · ${symptom.status === "present" ? "있음" : symptom.status === "absent" ? "없음" : "확실하지 않음"}`}
                        {detailedSite(symptom.body_site) && ` · 부위: ${symptom.body_site}`}
                        {symptom.status === "present" && ` · 시작: ${formatOnset(symptom.onset, symptom.onset_date) || "확인되지 않음"}`}
                        {symptom.status === "present" && ` · 정도: ${symptom.severity || "확인되지 않음"}`}
                        {symptom.status === "present" && symptom.trend && ` · 변화: ${symptom.trend === "improving" ? "호전 중" : symptom.trend === "worsening" ? "악화 중" : "변화 없음"}`}
                        {tracksFrequency(symptom.name) && symptom.status === "present" && symptom.frequency && ` · 횟수: ${symptom.frequency}`}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <p><strong>복용약:</strong> {record.intake.medications.join(", ") || "확인되지 않음"}</p>
              <p><strong>알레르기:</strong> {record.intake.allergies.join(", ") || "확인되지 않음"}</p>
              <p><strong>과거력:</strong> {record.intake.medical_history?.join(", ") || "확인되지 않음"}</p>
              {(record.intake.others_symptoms?.length ?? 0) > 0 && (
                <p>
                  <strong>주변 사람:</strong>{" "}
                  {record.intake.others_symptoms!.map((item) => `${item.person} ${item.symptom}`).join(", ")}
                </p>
              )}
              <button className="button--delete" type="button" onClick={() => void removeRecord(record.id)}>
                이 기록 삭제
              </button>
            </article>
          ))}
        </details>
        </>
        )}
        <p className="privacy-note">
          음성은 글자로 바꾸는 동안만 사용합니다. 확인한 기록은 이 브라우저 안에만
          저장되며 서버에는 보관하지 않습니다.
        </p>
      </section>
    </main>
  );
}
