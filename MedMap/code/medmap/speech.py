"""STT(speech → text)만 담당한다. evidence 추출·진단·PatientState·세션과 무관.

`decode_audio`/`check_speech`/`WhisperTranscriber`는 순수 오디오 처리다. `medmap.intake`를 import하지
않는다(책임 분리, docs/superpowers/plans/2026-09-26-medmap-stt.md). 디스크·임시파일을 쓰지 않는다
(입력 바이트는 메모리에서만 처리한다).
"""
from __future__ import annotations

import io
import logging
import os
import threading
import time

import av
import numpy as np

LOG = logging.getLogger("medmap.speech")

SR = 16000
MAX_BYTES = 2 * 1024 * 1024
MAX_SECONDS = 60.0
# 디코드는 60.5s까지 허용한 뒤 즉시 중단한다(경계 근처 인코더 오차 흡수, 60.0s 자체를 거부하지 않기 위함).
DECODE_MAX_SECONDS = 60.5
MIN_SECONDS = 0.3
SILENCE_RMS = 1e-3
# PyAV가 정수 포맷을 fltp로 잘못 스케일한 경우를 잡는 가드. 정상 float 오디오는 |x|<=1.0이어야 한다.
PEAK_GUARD = 1.5

# 테스트에서 PyAV encode→decode 라운드트립이 실제로 확인된 형식만 남긴다.
# 이 박스(av 18.1.0)에서 확인: wav/pcm_s16le, webm/libopus, ogg/libopus, mp4/aac, mp3/libmp3lame 전부 통과.
ALLOWED_MIME = frozenset({
    "audio/webm",
    "audio/ogg",
    "audio/wav",
    "audio/x-wav",   # audio/wav 와 동일하게 취급(브라우저·구형 클라이언트 별칭)
    "audio/mp4",
    "audio/mpeg",
})


class AudioTooLarge(Exception):
    """바이트 상한(MAX_BYTES) 초과. 엔드포인트가 스트리밍 중 먼저 잡는 것이 정상 경로이며,
    이 클래스는 decode 경로에서도 동일 계약을 표현하기 위해 존재한다."""


class AudioTooLong(Exception):
    """디코드된 오디오 길이가 DECODE_MAX_SECONDS를 넘는 즉시 발생."""


class AudioDecodeError(Exception):
    """컨테이너/코덱 디코드 실패, 오디오 스트림 없음, 진폭 이상(정수 스케일 오염 등)."""


class AudioEmpty(Exception):
    """너무 짧거나(< MIN_SECONDS) 무음(RMS < SILENCE_RMS)."""


class UnsupportedAudioType(Exception):
    """allowlist에 없는 MIME. (엔드포인트에서 415로 먼저 걸러지므로 여기서는 방어적으로만 쓰인다.)"""


class TranscriberUnavailable(Exception):
    """모델 로드 실패(디스크/네트워크/CUDA OOM 등) 또는 추론 실패."""


def normalize_mime(content_type: str | None) -> str:
    """`;` 앞 base MIME만, 소문자, 앞뒤 공백 제거. `None`/빈 문자열은 빈 문자열."""
    if not content_type:
        return ""
    return content_type.split(";", 1)[0].strip().lower()


def decode_audio(data: bytes) -> tuple[np.ndarray, float]:
    """원시 오디오 바이트 → (mono float32 PCM @ SR Hz, duration_seconds). 디스크에 쓰지 않는다.

    누적 디코드 샘플이 DECODE_MAX_SECONDS를 넘는 즉시 중단하고 `AudioTooLong`을 낸다(전체를
    다 디코드한 뒤 자르지 않는다). 디코드 자체 실패, 오디오 스트림 부재, 진폭 이상은
    `AudioDecodeError`.
    """
    try:
        container = av.open(io.BytesIO(data))
    except Exception as exc:
        raise AudioDecodeError("failed to open audio container") from exc

    try:
        try:
            stream = container.streams.audio[0]
        except IndexError as exc:
            raise AudioDecodeError("no audio stream in container") from exc

        resampler = av.AudioResampler(format="fltp", layout="mono", rate=SR)
        chunks: list[np.ndarray] = []
        total_samples = 0
        max_samples = int(DECODE_MAX_SECONDS * SR)

        def _consume(frame) -> None:
            nonlocal total_samples
            for rframe in resampler.resample(frame):
                arr = rframe.to_ndarray().reshape(-1).astype(np.float32)
                if arr.size == 0:
                    continue
                chunks.append(arr)
                total_samples += arr.shape[0]
                if total_samples > max_samples:
                    raise AudioTooLong("decoded audio exceeds max duration")

        try:
            for packet in container.demux(stream):
                for frame in packet.decode():
                    _consume(frame)
            _consume(None)          # flush resampler
        except AudioTooLong:
            raise
        except Exception as exc:
            raise AudioDecodeError("failed to decode audio") from exc
    finally:
        container.close()

    if not chunks:
        raise AudioDecodeError("decoded zero samples")

    x = np.concatenate(chunks)
    peak = float(np.abs(x).max())
    if peak > PEAK_GUARD:
        raise AudioDecodeError("decoded amplitude out of range")
    duration = x.shape[0] / SR
    return x, duration


def check_speech(x: np.ndarray, duration: float) -> None:
    """너무 짧거나 무음이면 `AudioEmpty`."""
    if duration < MIN_SECONDS:
        raise AudioEmpty("audio shorter than minimum duration")
    rms = float(np.sqrt(np.mean(np.square(x)))) if x.size else 0.0
    if rms < SILENCE_RMS:
        raise AudioEmpty("audio is silent")


class WhisperTranscriber:
    """Whisper pipeline을 최초 `transcribe` 호출 때만 로드한다(lifespan에서 로드 금지).

    `loader`는 인자 없이 호출되어 추론 가능한 객체(예: transformers pipeline)를 반환해야 한다.
    로드는 double-checked locking으로 한 번만 일어나고, 추론은 별도 lock으로 직렬화한다(동시
    요청이 같은 pipeline 인스턴스를 동시에 호출하지 않도록).
    """

    def __init__(self, loader=None, device: str | None = None):
        self._loader = loader if loader is not None else self._default_loader
        self._device = device
        self._pipeline = None
        self._load_lock = threading.Lock()
        self._infer_lock = threading.Lock()

    def _resolve_device(self) -> str:
        forced = os.environ.get("MEDMAP_STT_DEVICE")
        if forced in ("cuda", "cpu"):
            return forced
        if self._device in ("cuda", "cpu"):
            return self._device
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"

    def _default_loader(self):
        import torch
        from transformers import pipeline

        device = self._resolve_device()
        dtype = torch.float16 if device == "cuda" else torch.float32
        return pipeline("automatic-speech-recognition", model="openai/whisper-large-v3-turbo",
                        device=device, dtype=dtype)

    def _ensure_loaded(self) -> None:
        if self._pipeline is not None:
            return
        with self._load_lock:
            if self._pipeline is not None:
                return
            try:
                self._pipeline = self._loader()
            except Exception as exc:
                raise TranscriberUnavailable("failed to load transcriber") from exc

    def transcribe(self, x: np.ndarray) -> str:
        self._ensure_loaded()
        with self._infer_lock:
            try:
                result = self._pipeline({"raw": x, "sampling_rate": SR}, generate_kwargs={"language": "ko", "task": "transcribe"},
                                        chunk_length_s=30)
            except Exception as exc:
                raise TranscriberUnavailable("transcription failed") from exc
        text = result.get("text", "") if isinstance(result, dict) else str(result)
        return text.strip()


_TRANSCRIBER: WhisperTranscriber | None = None
_TRANSCRIBER_LOCK = threading.Lock()


def get_transcriber() -> WhisperTranscriber:
    """모듈 싱글톤. 최초 호출 시 `WhisperTranscriber` 인스턴스를 만들지만 모델 자체는 아직 로드하지 않는다."""
    global _TRANSCRIBER
    if _TRANSCRIBER is None:
        with _TRANSCRIBER_LOCK:
            if _TRANSCRIBER is None:
                _TRANSCRIBER = WhisperTranscriber()
    return _TRANSCRIBER


def start_prewarm(transcriber: WhisperTranscriber | None = None) -> threading.Thread:
    """opt-in(MEDMAP_STT_PREWARM=1): Whisper 로드를 백그라운드 daemon thread 로 미리 시작한다.

    서버 시작·health 를 막지 않는다. 실패는 로그(예외 종류만)로 남기고 삼킨다 — 첫 STT 요청 때
    기존 lazy load(`_ensure_loaded`)가 다시 시도한다. 오디오·전사문과 무관하다.
    """
    target = transcriber if transcriber is not None else get_transcriber()

    def run() -> None:
        started = time.perf_counter()
        try:
            target._ensure_loaded()
        except TranscriberUnavailable as exc:
            LOG.warning("stt prewarm failed cause=%s ms=%.1f", type(exc.__cause__).__name__,
                        (time.perf_counter() - started) * 1000)
            return
        LOG.info("stt prewarm loaded ms=%.1f", (time.perf_counter() - started) * 1000)

    thread = threading.Thread(target=run, name="medmap-stt-prewarm", daemon=True)
    thread.start()
    return thread
