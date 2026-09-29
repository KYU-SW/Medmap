from dataclasses import dataclass
from io import BytesIO
import os
from pathlib import Path
from threading import Lock
from time import perf_counter
from typing import Protocol


@dataclass(frozen=True)
class Transcription:
    text: str
    language: str = "ko"
    duration_seconds: float | None = None


class SpeechToTextService(Protocol):
    def transcribe(self, audio: bytes, content_type: str) -> Transcription:
        """Convert audio to text without persisting the audio or transcript."""


class NoSpeechDetectedError(ValueError):
    """Raised when decoding succeeds but no speech is found."""


class SpeechModelUnavailableError(RuntimeError):
    """Raised when the local Whisper model cannot be loaded or executed."""


class FasterWhisperService:
    """Lazy-loaded, local-only Korean speech recognition service."""

    def __init__(
        self,
        model_name: str = "turbo",
        device: str = "cpu",
        compute_type: str = "int8",
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self._model = None
        self._model_lock = Lock()

    def _get_model(self):
        if self._model is not None:
            return self._model

        with self._model_lock:
            if self._model is None:
                try:
                    project_root = Path(__file__).resolve().parents[4]
                    cache_root = Path(
                        os.getenv("MEDMAP_CACHE_DIR", project_root / "local-cache")
                    ).resolve()
                    os.environ.setdefault("HF_HOME", str(cache_root / "huggingface"))
                    from faster_whisper import WhisperModel

                    self._model = WhisperModel(
                        self.model_name,
                        device=self.device,
                        compute_type=self.compute_type,
                    )
                except Exception as exc:
                    raise SpeechModelUnavailableError(
                        "Whisper 모델을 불러오지 못했습니다. 실행 환경을 확인해 주세요."
                    ) from exc
        return self._model

    def transcribe(self, audio: bytes, content_type: str) -> Transcription:
        del content_type  # PyAV detects the container from the in-memory audio stream.
        if not audio:
            raise NoSpeechDetectedError("음성 데이터가 비어 있습니다.")

        model = self._get_model()
        started_at = perf_counter()
        try:
            segments, info = model.transcribe(
                BytesIO(audio),
                language="ko",
                task="transcribe",
                beam_size=5,
                vad_filter=True,
                condition_on_previous_text=False,
            )
            text = " ".join(
                segment.text.strip() for segment in segments if segment.text.strip()
            ).strip()
        except NoSpeechDetectedError:
            raise
        except Exception as exc:
            raise SpeechModelUnavailableError(
                "음성을 변환하지 못했습니다. 잠시 후 다시 시도해 주세요."
            ) from exc

        if not text:
            raise NoSpeechDetectedError("말소리를 찾지 못했습니다. 다시 녹음해 주세요.")

        duration = getattr(info, "duration", None)
        _elapsed_seconds = perf_counter() - started_at
        # Do not log audio or transcript. Timing metrics can be added separately.
        return Transcription(
            text=text,
            language=getattr(info, "language", "ko") or "ko",
            duration_seconds=float(duration) if duration is not None else None,
        )


_service: FasterWhisperService | None = None


def get_stt_service() -> FasterWhisperService:
    global _service
    if _service is None:
        device = os.getenv("MEDMAP_STT_DEVICE", "cpu")
        default_compute_type = "float16" if device == "cuda" else "int8"
        _service = FasterWhisperService(
            model_name=os.getenv("MEDMAP_STT_MODEL", "turbo"),
            device=device,
            compute_type=os.getenv("MEDMAP_STT_COMPUTE_TYPE", default_compute_type),
        )
    return _service
