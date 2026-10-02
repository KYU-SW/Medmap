"""Streaming STT API(opt-in `MEDMAP_STT_STREAMING=1`): WebSocket + HTTP chunk fallback + status/prewarm.

- PARTIAL 은 UI 전용: 이 모듈은 매퍼·진단 엔진·세션을 호출하지 않는다.
- 오디오·전사문은 스트림 수명 동안 메모리에만(디스크·로그 금지). 로그에는 해시한 sid·이벤트·ms·코드만.
- 추론은 기존 `speech.get_transcriber()` 싱글톤을 `SttScheduler` 한 줄 큐로 공유한다(기존 /v1/stt/transcribe 와 직렬화).
- audio_ms = 스트림 시작 이후 누적 오디오 길이(ms). 클라이언트도 같은 값을 계산해 T_partial 을 잰다.
- VAD(M2): ct2 worker 가 Silero VAD 를 지원하면 스트림마다 VAD 연결을 열어 발화를 자동으로 나누고 확정한다(reason "vad").
  speech_start 전 오디오는 pre-roll(300 ms)만 발화에 넣고 나머지는 디코드하지 않는다. VAD 가 없거나 실패하면 수동 stop 만.
- Speculative FINAL predecode: 발화 중 침묵이 PREDECODE_MS 이어지면 그 시점 발화(음성 + 짧은 꼬리)로 FINAL 후보를 미리
  디코드한다. 결과는 서버 메모리에만 두고 **endpoint 확정 전에는 어떤 메시지도 보내지 않는다**(FINAL 표시·상태 변경 없음).
  말이 다시 시작되면 후보를 버린다. endpoint(또는 수동 stop) 때 후보가 유효하면 그 결과가 FINAL 이 된다
  (FINAL 오디오 = 후보 스냅샷: 이후 붙은 오디오는 VAD 가 비음성으로 판정한 꼬리뿐).
설계: docs/superpowers/specs/2026-09-30-medmap-realtime-streaming-stt-design.md §6·§9
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
import uuid

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict, Field

from . import speech, stt_turn
from .stt_scheduler import SttInferenceError, SttScheduler
from .stt_stream import LocalAgreement, StreamLimit, StreamSession, end_msg, error_msg, final_msg, partial_msg
from .stt_vad import Endpointer, filter_hallucination, predecode_ms_default

LOG = logging.getLogger("medmap.stt_stream")

STREAMING = os.environ.get("MEDMAP_STT_STREAMING") == "1"
# streaming 추론 엔진: hf = 기존 in-process HF Whisper(기본) · ct2 = 로컬 STT worker(faster-whisper/CT2, Unix socket).
# /v1/stt/transcribe(legacy fallback)는 엔진과 무관하게 항상 기존 HF 경로다.
ENGINE = os.environ.get("MEDMAP_STT_ENGINE", "hf")
MAX_STREAMS = int(os.environ.get("MEDMAP_STT_MAX_STREAMS", "1"))
PARTIAL_TICK_MS = 200          # 최소 partial 간격. 실제 간격 = max(200, 1.2 × 직전 decode ms) (M1: 400 → 200, tick_wait 병목)
IDLE_S = 15.0
MAX_MESSAGE_BYTES = 64 * 1024
SAMPLE_RATE = 16000
VAD_ENABLED = os.environ.get("MEDMAP_STT_VAD", "1") != "0"      # ct2 worker 가 VAD 를 지원할 때만 실제로 켜진다
# STEP A 쉼 전수 기록(측정 전용, 기본 꺼짐): 발화 안 쉼마다 길이·재개 여부·완결 등급(stt_turn)·안정성을 숫자/코드로만 로그
PAUSE_CENSUS = os.environ.get("MEDMAP_STT_PAUSE_CENSUS") == "1"


def enable_census_output() -> None:
    """측정 모드 전용: medmap.stt_stream·stt_turn INFO(숫자·코드만)를 stderr 로 내보낸다. 제품 기본 로깅은 그대로.
    (medmap.* 로거에는 기본 handler 가 없어 INFO 가 버려진다 — 2026-10-01 쉼 기록 0줄로 발견)"""
    for name in ("medmap.stt_stream", "medmap.stt_turn"):
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        if not any(getattr(h, "_medmap_census", False) for h in logger.handlers):
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(asctime)s %(name)s %(message)s"))
            handler._medmap_census = True
            logger.addHandler(handler)


if PAUSE_CENSUS:
    enable_census_output()
VAD_FRAME_BYTES = 512 * 2
VAD_BATCH_BYTES = VAD_FRAME_BYTES * 31                               # ≤ 1 s, worker MAX_VAD_BYTES(2 s) 안
FORMAT = "s16le"
# HTTP 스트림 id 는 경로가 아니라 헤더로 받는다(기존 access log 가 URL 경로를 기록하므로 id 가 로그에 남지 않게).
SID_HEADER = "x-stt-stream"

router = APIRouter()
_override = None               # 테스트 전용 가짜 transcriber
_scheduler: SttScheduler | None = None
_worker = None                 # WorkerClient(ct2)
_worker_state = (0.0, "COLD")  # (확인 시각, 상태) — status 호출마다 ping 하지 않게 1 s 캐시
_worker_vad = False            # 마지막 ping 에서 worker 가 VAD 를 지원했는지
_vad_override = None           # 테스트 전용 가짜 VAD: fn(pcm bytes) -> 프레임별 확률 list
_streams: dict = {}            # sid -> _Stream (WS·HTTP 모두)


def set_transcribe_for_tests(fn) -> None:
    global _override, _scheduler
    _override, _scheduler = fn, None


def worker_client():
    global _worker
    if _worker is None:
        from .stt_worker import WorkerClient
        _worker = WorkerClient()
    return _worker


def set_worker_for_tests(client) -> None:
    global _worker, _worker_state, _scheduler
    _worker, _worker_state, _scheduler = client, (0.0, "COLD"), None


def set_vad_for_tests(fn) -> None:
    global _vad_override
    _vad_override = fn


def vad_mode() -> str:
    """"server"(VAD 자동 발화 확정) · "manual"(수동 stop 만)."""
    if _vad_override is not None:
        return "server"
    if ENGINE == "ct2" and VAD_ENABLED:
        stt_state()                                               # ping 캐시 갱신(1 s)
        return "server" if _worker_vad else "manual"
    return "manual"


def _open_vad():
    """스트림 하나의 VAD: (확률 함수, 닫을 클라이언트). 없으면 (None, None)."""
    if _vad_override is not None:
        return _vad_override, None
    if vad_mode() != "server":
        return None, None
    from .stt_worker import WorkerClient
    client = WorkerClient(timeout_s=1.0)                        # 스트림 전용 연결 = 스트림 전용 VAD 상태
    return client.vad_probs, client


def _transcribe(audio):
    if _override is not None:
        return _override(audio)
    if ENGINE == "ct2":
        return worker_client().transcribe_timed(audio)          # (text, {"worker","ipc"}) — 실패하면 SttWorkerUnavailable
    return speech.get_transcriber().transcribe(audio)


def scheduler() -> SttScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = SttScheduler(_transcribe)
    return _scheduler


def stt_state() -> str:
    """WARM(모델 로드됨) · LOADING(로드 중) · COLD(아직 로드 안 함) · UNAVAILABLE(ct2 worker 응답 없음)."""
    global _worker_state, _worker_vad
    if _override is not None:
        return "WARM"
    if ENGINE == "ct2":
        checked, state = _worker_state
        if time.monotonic() - checked > 1.0:
            try:
                _worker_vad = bool(worker_client().ping().get("vad"))
                state = "WARM"                                    # worker 는 시작 시 로드·prewarm 을 끝낸 뒤 소켓을 연다
            except Exception:
                _worker_vad = False
                state = "UNAVAILABLE"
            _worker_state = (time.monotonic(), state)
        return state
    transcriber = speech.get_transcriber()
    if transcriber._pipeline is not None:
        return "WARM"
    return "LOADING" if transcriber._load_lock.locked() else "COLD"


def _h(sid: str) -> str:
    return hashlib.sha256(sid.encode()).hexdigest()[:8]


def _api_error(status: int, code: str):
    from . import api          # 지연 import: api.py 가 이 모듈을 include 한다
    return api.ApiError(status, code, code)


def expire_idle() -> None:
    """HTTP 스트림만 만료시킨다. WS 스트림은 연결이 끊길 때 정리된다(수신 루프를 밖에서 끊을 수 없으므로)."""
    now = time.monotonic()
    for sid in [s for s, stream in _streams.items()
                if isinstance(stream.emit, _Collector) and now - stream.touched > IDLE_S]:
        _streams.pop(sid).close()
        LOG.info("stt_stream sid=%s event=idle_expired", _h(sid))


class _Stream:
    """한 스트림의 발화 버퍼·LocalAgreement·partial 예약. 메시지는 emit(dict) 로 내보낸다."""

    def __init__(self, sid: str, emit):
        self.sid = sid
        self.session = StreamSession(sid)
        self.agree = LocalAgreement()
        self.emit = emit
        self.touched = time.monotonic()
        self.tick_ms = PARTIAL_TICK_MS
        self.last_partial_at = 0.0
        self.partial_task: asyncio.Task | None = None
        self.inflight: tuple | None = None       # (utt, samples) 로 제출된 partial
        self.recv_at: dict = {}                  # audio_ms → 서버 수신 시각(perf_counter) — 구간 계측용, 숫자만
        self.last_hyp: tuple | None = None       # (utt, samples, text) — 같은 오디오 전체에 대한 마지막 가설
        self.vad, self._vad_client = _open_vad()  # None 이면 수동 stop 만(M1 동작 그대로)
        self.endpointer = Endpointer() if self.vad is not None else None
        self.vad_rest = b""                      # 512-sample 프레임에 못 미친 나머지
        self.vad_pos = 0                         # VAD 가 처리한 스트림 샘플 수
        self.utt_frames = [0, 0]                 # 현재 발화의 (음성 프레임, 전체 프레임) — 환각 가드용
        self.speech_start_ms: int | None = None  # 현재 발화의 VAD 음성 시작(스트림 ms)
        self._gap_start: int | None = None       # 발화 안 진행 중인 비음성 시작 샘플
        self.utt_pauses: list[list[int]] = []    # 현재 발화 안 쉼 [시작, 끝](스트림 ms, ≥ predecode, 말이 이어진 것만) — 채점용 숫자
        self.spec: tuple | None = None           # (utt, 스냅샷 오디오, task) — speculative FINAL 후보(메모리만, 미표시)
        self.spec_discarded = 0                  # 현재 발화에서 말이 이어져 버린 후보 수(숫자만, FINAL 마다 초기화)
        self.predecode_ms = predecode_ms_default(self.endpointer.silence_ms) if self.endpointer is not None else None
        self._pause: dict | None = None          # 쉼 전수 기록: 진행 중인 쉼(시작 샘플·시각·그때 partial 등급)
        self._spec_ready_at: float | None = None
        if PAUSE_CENSUS and self.endpointer is not None:
            stt_turn.warm()                      # Kiwi(~0.7 s)를 첫 쉼이 아니라 스트림 열 때 로드

    @property
    def audio_ms(self) -> int:
        return int(round(self.session.stream_seconds * 1000))

    async def _append(self, pcm: bytes) -> None:
        try:
            self.session.append(pcm)
        except StreamLimit as exc:
            if exc.code != "UTTERANCE_TOO_LONG":
                raise
            await self.finalize("max_duration")
            self.session.append(pcm)

    async def feed(self, pcm: bytes) -> None:
        self.touched = time.monotonic()
        received = time.perf_counter()
        if self.vad is None:
            await self._append(pcm)
        else:
            await self._feed_vad(pcm)
        self.recv_at[self.audio_ms] = received
        if len(self.recv_at) > 1200:                              # 최근 2분치만(메모리 상한)
            for key in sorted(self.recv_at)[:-600]:
                del self.recv_at[key]
        if self.endpointer is not None and (not self.endpointer.in_speech or self.spec is not None):
            return                                                     # VAD: 발화 밖·침묵 중(FINAL 후보 계산 중)은 partial 안 함
        now = time.monotonic() * 1000
        if now - self.last_partial_at >= self.tick_ms and (self.partial_task is None or self.partial_task.done()):
            self.last_partial_at = now
            self.partial_task = asyncio.create_task(self._partial())

    async def _feed_vad(self, pcm: bytes) -> None:
        """발화 중이면 발화에, 아니면 최근 버퍼에만 넣고 VAD 확률로 speech_start(pre-roll 로 발화 시작)·speech_end(자동 확정)."""
        ep = self.endpointer
        if ep.in_speech:
            await self._append(pcm)
        else:
            self.session.hold(pcm)
        data = self.vad_rest + pcm
        cut = len(data) // VAD_FRAME_BYTES * VAD_FRAME_BYTES
        self.vad_rest = data[cut:]
        if not cut:
            return
        held_end = self.vad_pos + len(data) // 2                   # data 끝 = 지금까지 받은 스트림 샘플 수
        try:
            probs = []
            for at in range(0, cut, VAD_BATCH_BYTES):                  # worker 의 한 요청 상한(2 s)보다 큰 청크는 나눠 보낸다
                probs += await asyncio.to_thread(self.vad, data[at:min(cut, at + VAD_BATCH_BYTES)])
        except Exception as exc:                                       # VAD 장애 → 이 스트림은 수동 stop 으로(오디오 손실 없이)
            LOG.info("stt_stream sid=%s event=vad_failed kind=%s", _h(self.sid), type(exc).__name__)
            self._close_vad()
            if not ep.in_speech:
                self.session.open_preroll(self.session.max_utt_samples)
            return
        frame = 512
        for i, prob in enumerate(probs):
            frame_start = self.vad_pos + i * frame
            events = ep.push(prob)
            if "speech_start" in events:
                run_start = frame_start - (ep.start_frames - 1) * frame
                self.speech_start_ms = int(run_start * 1000 / SAMPLE_RATE)
                preroll = ep.preroll_ms * SAMPLE_RATE // 1000
                self.session.open_preroll(held_end - run_start + preroll)
                self.utt_frames = [ep.start_frames, ep.start_frames]
                self._gap_start = None
                continue
            if ep.in_speech:                                           # 발화 안 쉼 경계(채점: 쉼 동안 패킷은 T_partial 에서 뺀다)
                if prob < ep.start_prob:
                    if self._gap_start is None:
                        self._gap_start = frame_start
                elif self._gap_start is not None:
                    if (frame_start - self._gap_start) * 1000 // SAMPLE_RATE >= self.predecode_ms:
                        self.utt_pauses.append([int(self._gap_start * 1000 / SAMPLE_RATE), int(frame_start * 1000 / SAMPLE_RATE)])
                    self._gap_start = None
            if ep.in_speech or "speech_end" in events:
                self.utt_frames[1] += 1
                self.utt_frames[0] += int(prob >= ep.start_prob)
            if PAUSE_CENSUS:
                self._census(ep, prob, events, frame_start, frame)
            if ep.in_speech and prob >= ep.start_prob and self.spec is not None:
                self._drop_spec()                                      # 말이 이어짐 → 후보 폐기(아무것도 내보내지 않았음)
            elif ep.in_speech and self.spec is None and ep.silence_run_ms >= self.predecode_ms:
                self._start_spec()
            if "speech_end" in events:
                end = frame_start - (ep.silence_frames - 1) * frame
                await self.finalize("vad", speech_end_ms=int(end * 1000 / SAMPLE_RATE))
        self.vad_pos += cut // 2

    def _census(self, ep, prob: float, events: list, frame_start: int, frame: int) -> None:
        """발화 안 쉼 하나 = 로그 한 줄. 재개(resumed=1) 또는 endpoint(resumed=0, censored=1 — 실제 길이는 모름)로 끝난다."""
        if self._pause is None:
            if ep.in_speech and prob < ep.start_prob:
                last = self.last_hyp[2] if self.last_hyp is not None and self.last_hyp[0] == self.session.utt else ""
                self._pause = {"start": frame_start, "t": time.perf_counter(), "cls_partial": stt_turn.classify(last),
                               "partial_text": last}
            return
        resumed = ep.in_speech and prob >= ep.start_prob
        if not resumed and "speech_end" not in events:
            return
        pause, self._pause = self._pause, None
        end = frame_start if resumed else frame_start + frame
        cand, ready_ms = None, -1.0
        spec = self.spec
        if spec is not None and spec[2].done() and not spec[2].cancelled() and spec[2].result() is not None:
            cand = spec[2].result()[0]
            ready_ms = round((self._spec_ready_at - pause["t"]) * 1000, 1) if self._spec_ready_at else -1.0
        cls_cand = stt_turn.classify(cand).label if cand is not None else "none"
        stable = -1 if cand is None else int(" ".join(cand.split()) == " ".join(pause["partial_text"].split()))
        LOG.info("stt_stream sid=%s event=pause dur_ms=%d resumed=%d censored=%d silence_ms=%d cls_partial=%s/%s "
                 "cls_cand=%s stable=%d cand_ready_ms=%.1f", _h(self.sid), int((end - pause["start"]) * 1000 / SAMPLE_RATE),
                 int(resumed), int(not resumed), ep.silence_ms, pause["cls_partial"].label, pause["cls_partial"].reason,
                 cls_cand, stable, ready_ms)

    def _start_spec(self) -> None:
        audio = self.session.utterance_pcm()
        try:
            speech.check_speech(audio, audio.size / SAMPLE_RATE)
        except speech.AudioEmpty:
            return
        self.spec = (self.session.utt, audio, asyncio.create_task(self._predecode(audio)))

    async def _predecode(self, audio):
        started = time.perf_counter()
        self._spec_ready_at = None
        try:
            text, ms = await scheduler().submit_final(self.sid, audio)
        except SttInferenceError:
            return None
        self._spec_ready_at = time.perf_counter()
        return text, {**ms, "predecode_total": round((time.perf_counter() - started) * 1000, 1)}

    def _drop_spec(self) -> None:
        if self.spec is not None:
            self.spec[2].cancel()                                      # 아직 큐에 있으면 디코드도 건너뛴다
            self.spec = None
            self.spec_discarded += 1

    def _close_vad(self) -> None:
        self.vad, self.endpointer = None, None
        if self._vad_client is not None:
            self._vad_client.close()
            self._vad_client = None

    async def _partial(self) -> None:
        if scheduler().overloaded:
            return                                                     # 과부하: partial 을 건너뛰고 FINAL 만(spec §9)
        audio = self.session.utterance_pcm()
        try:
            speech.check_speech(audio, audio.size / SAMPLE_RATE)       # 무음·짧은 구간은 디코드하지 않는다(환각 방지)
        except speech.AudioEmpty:
            return
        utt, audio_ms = self.session.utt, self.audio_ms
        recv_ref = self.recv_at.get(audio_ms)
        submitted = time.perf_counter()
        self.inflight = (utt, audio.size)
        try:
            result = await scheduler().submit_partial(self.sid, audio)
        except SttInferenceError:
            return                                                     # partial 실패는 조용히 건너뛴다(FINAL 이 책임)
        finally:
            self.inflight = None
        if result is None:
            return                                                     # 더 새 partial 에 밀려 버려짐
        text, ms = result
        if recv_ref is not None:                                  # 서버 체류: 수신→제출, 수신→방출
            ms = {**ms, "held": round((submitted - recv_ref) * 1000, 1),
                  "since_recv": round((time.perf_counter() - recv_ref) * 1000, 1)}
        self.last_hyp = (utt, audio.size, text)                        # FINAL 재사용 후보(같은 모델·같은 입력 = 같은 결과)
        if utt != self.session.utt or self.session.closed:
            return                                                     # 발화가 이미 끝남
        self.tick_ms = max(PARTIAL_TICK_MS, 1.2 * ms["decode"])
        stable, unstable = self.agree.update(text)
        await self.emit(partial_msg(utt, stable, unstable, audio_ms, ms))

    async def finalize(self, reason: str, *, speech_end_ms: int | None = None) -> None:
        current = self.session.utt
        spec, self.spec = self.spec, None
        if spec is not None and (spec[0] != current or reason == "max_duration"):
            spec[2].cancel()
            spec = None
        audio = spec[1] if spec is not None else self.session.utterance_pcm()
        audio_ms = self.audio_ms
        vad_ms = {}                                                    # VAD 경계(스트림 ms, 숫자만) — e2e 의 T_final(발화 끝 → FINAL)용
        if self.speech_start_ms is not None:
            vad_ms["speech_start_ms"] = self.speech_start_ms
        if speech_end_ms is not None:
            vad_ms["speech_end_ms"] = speech_end_ms
        if self.endpointer is not None:
            vad_ms["spec_discarded"] = self.spec_discarded             # 이 발화에서 말이 이어져 버린 FINAL 후보 수
            vad_ms["pauses_ms"] = self.utt_pauses                      # 발화 안 쉼 구간(숫자만, 채점용)
        self.utt_pauses = []
        self._gap_start = None
        self.spec_discarded = 0
        speech_ratio = self.utt_frames[0] / self.utt_frames[1] if self.endpointer is not None and self.utt_frames[1] else None
        self.utt_frames = [0, 0]
        # 30 s 상한으로 끊겼는데 말이 이어지면 다음 발화는 이 경계에서 시작한 음성이다
        continuing = reason == "max_duration" and self.endpointer is not None and self.endpointer.in_speech
        self.speech_start_ms = audio_ms if continuing else None
        if reason == "manual" and self.endpointer is not None:
            self.endpointer = Endpointer()                             # 수동 stop 뒤 새 발화는 VAD 가 다시 연다
        # 진행 중인 partial 이 이미 발화 전체를 디코드하고 있으면 끝나기를 기다렸다가 그 결과를 쓴다(중복 decode 방지).
        if spec is None and self.inflight == (current, audio.size) and self.partial_task is not None and not self.partial_task.done():
            try:
                await asyncio.shield(self.partial_task)
            except Exception:
                pass
        reusable = self.last_hyp if spec is None and self.last_hyp is not None and self.last_hyp[:2] == (current, audio.size) else None
        utt = self.session.close_utterance(reason)
        self.agree.reset()
        await self.emit(end_msg(utt, reason))
        try:
            speech.check_speech(audio, audio.size / SAMPLE_RATE)
        except speech.AudioEmpty:
            await self.emit(final_msg(utt, "", audio_ms, dict(vad_ms)))
            return
        started = time.perf_counter()
        if reusable is not None:
            await self.emit(final_msg(utt, filter_hallucination(reusable[2], speech_ratio), audio_ms,
                                      {"queue": 0.0, "decode": 0.0, "reused": True, **vad_ms}))
            LOG.info("stt_stream sid=%s event=final audio_ms=%d reused=1 total_ms=%.1f", _h(self.sid), audio_ms,
                     (time.perf_counter() - started) * 1000)
            return
        if spec is not None:
            waited = time.perf_counter()
            try:
                result = await asyncio.shield(spec[2])
            except asyncio.CancelledError:
                result = None
            if result is not None:                                     # 미리 계산한 후보 = FINAL(이제서야 처음 내보낸다)
                text, ms = result
                ms = {**ms, "predecoded": True, "spec_wait": round((time.perf_counter() - waited) * 1000, 1)}
                await self.emit(final_msg(utt, filter_hallucination(text, speech_ratio), audio_ms, {**ms, **vad_ms}))
                LOG.info("stt_stream sid=%s event=final audio_ms=%d predecoded=1 spec_wait_ms=%.1f discarded=%d", _h(self.sid),
                         audio_ms, ms["spec_wait"], vad_ms.get("spec_discarded", 0))
                return
        try:
            text, ms = await scheduler().submit_final(self.sid, audio)
        except SttInferenceError as exc:
            LOG.info("stt_stream sid=%s event=final_failed kind=%s", _h(self.sid), exc.kind)
            await self.emit(error_msg("STT_UNAVAILABLE"))
            return
        await self.emit(final_msg(utt, filter_hallucination(text, speech_ratio), audio_ms, {**ms, **vad_ms}))
        LOG.info("stt_stream sid=%s event=final audio_ms=%d queue_ms=%.1f decode_ms=%.1f total_ms=%.1f",
                 _h(self.sid), audio_ms, ms["queue"], ms["decode"], (time.perf_counter() - started) * 1000)

    def close(self) -> None:
        if self.spec is not None:
            self.spec[2].cancel()
            self.spec = None
        self.session.discard()
        if self.partial_task is not None and not self.partial_task.done():
            self.partial_task.cancel()
        self._close_vad()


def _valid_start(body: dict) -> bool:
    return body.get("sample_rate") == SAMPLE_RATE and body.get("format") == FORMAT


def _origin_ok(headers) -> bool:
    origin = headers.get("origin")
    if origin is None:
        return True            # 브라우저가 아닌 도구. 브라우저는 항상 Origin 을 보낸다
    host = headers.get("host", "")
    return origin.split("://", 1)[-1] == host


# ---------------- status / prewarm ----------------
@router.get("/v1/stt/status")
def stt_status() -> dict:
    body = {"streaming": STREAMING, "stt_state": stt_state(), "vad": vad_mode(), "engine": ENGINE}
    if body["vad"] == "server":                                        # 적용된 endpoint 기준(측정 조건 확인용, 숫자만)
        ep = Endpointer()
        body["vad_silence_ms"] = ep.silence_ms
        body["vad_predecode_ms"] = predecode_ms_default(ep.silence_ms)
    return body


@router.post("/v1/stt/prewarm", status_code=202)
def stt_prewarm() -> dict:
    """멱등. 모델이 아직 없으면 백그라운드 로드만 시작한다(오디오와 무관)."""
    if not STREAMING:
        raise _api_error(404, "STREAMING_DISABLED")         # 플래그 OFF 면 LAN 클라이언트가 GPU 로드를 유발하지 못하게
    state = stt_state()
    if state == "COLD" and ENGINE != "ct2":                       # ct2 worker 는 시작 시 스스로 prewarm 한다
        speech.start_prewarm(speech.get_transcriber())
        state = "LOADING"
    return {"stt_state": state}


# ---------------- WebSocket ----------------
@router.websocket("/v1/stt/stream")
async def stt_stream_ws(ws: WebSocket) -> None:
    if not _origin_ok(ws.headers):
        await ws.close(code=1008)
        return
    await ws.accept()

    async def emit(msg: dict) -> None:
        await ws.send_json(msg)

    stream = None
    sid = uuid.uuid4().hex
    try:
        first = await ws.receive_json()
        if not STREAMING:
            await emit(error_msg("STREAMING_DISABLED"))
            return
        if first.get("type") != "start" or not _valid_start(first):
            await emit(error_msg("AUDIO_INVALID"))
            return
        expire_idle()
        if len(_streams) >= MAX_STREAMS:
            await emit(error_msg("STREAM_BUSY"))
            return
        stream = _Stream(sid, emit)
        _streams[sid] = stream
        LOG.info("stt_stream sid=%s event=open transport=ws", _h(sid))
        await emit({"type": "ready", "stt_state": stt_state(), "vad": "server" if stream.vad is not None else "manual"})
        while True:
            message = await ws.receive()
            if message.get("type") == "websocket.disconnect":
                break
            data = message.get("bytes")
            if data is not None:
                if len(data) > MAX_MESSAGE_BYTES:
                    await emit(error_msg("AUDIO_INVALID"))
                    break
                try:
                    await stream.feed(data)
                except StreamLimit as exc:
                    await emit(error_msg(exc.code))
                    break
                continue
            try:
                control = json.loads(message.get("text") or "{}")
            except ValueError:
                await emit(error_msg("AUDIO_INVALID"))
                break
            if control.get("type") == "stop":
                await stream.finalize("manual")
            elif control.get("type") == "close":
                break
    except WebSocketDisconnect:
        pass
    finally:
        if stream is not None:
            _streams.pop(sid, None)
            stream.close()
            LOG.info("stt_stream sid=%s event=close", _h(sid))
        try:
            await ws.close()
        except Exception:      # 이미 닫힘
            pass


# ---------------- HTTP chunk fallback ----------------
class StreamOpen(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sample_rate: int
    format: str
    run_id: str = Field(max_length=64)


def _http_stream(sid: str) -> _Stream:
    expire_idle()
    stream = _streams.get(sid)
    if stream is None or not isinstance(stream.emit, _Collector):
        raise _api_error(404, "STREAM_NOT_FOUND")
    return stream


class _Collector:
    """HTTP 스트림: 메시지를 모아 두었다가 다음 응답에 담는다."""

    def __init__(self):
        self.messages: list[dict] = []

    async def __call__(self, msg: dict) -> None:
        self.messages.append(msg)

    def drain(self) -> list[dict]:
        out, self.messages = self.messages, []
        return out


@router.post("/v1/stt/stream")
def stt_stream_open(body: StreamOpen) -> dict:
    if not STREAMING:
        raise _api_error(404, "STREAMING_DISABLED")
    if not _valid_start(body.model_dump()):
        raise _api_error(400, "AUDIO_INVALID")
    expire_idle()
    if len(_streams) >= MAX_STREAMS:
        raise _api_error(429, "STREAM_BUSY")
    sid = uuid.uuid4().hex
    stream = _Stream(sid, _Collector())
    _streams[sid] = stream
    LOG.info("stt_stream sid=%s event=open transport=http", _h(sid))
    return {"sid": sid, "stt_state": stt_state(), "vad": "server" if stream.vad is not None else "manual"}


@router.post("/v1/stt/stream/audio")
async def stt_stream_audio(request: Request) -> dict:
    stream = _http_stream(request.headers.get(SID_HEADER, ""))
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_MESSAGE_BYTES * 8:
            raise _api_error(413, "AUDIO_TOO_LARGE")
    try:
        await stream.feed(bytes(body))
    except StreamLimit as exc:
        raise _api_error(400, exc.code) from None
    return {"messages": stream.emit.drain()}


@router.post("/v1/stt/stream/stop")
async def stt_stream_stop(request: Request) -> dict:
    stream = _http_stream(request.headers.get(SID_HEADER, ""))
    stream.touched = time.monotonic()
    await stream.finalize("manual")
    return {"messages": stream.emit.drain()}


@router.post("/v1/stt/stream/close")
def stt_stream_close(request: Request) -> dict:
    sid = request.headers.get(SID_HEADER, "")
    stream = _http_stream(sid)
    _streams.pop(sid, None)
    stream.close()
    LOG.info("stt_stream sid=%s event=close", _h(sid))
    return {"closed": True}
