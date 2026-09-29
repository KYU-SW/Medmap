from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Transcription:
    text: str
    language: str = "ko"
    duration_seconds: float | None = None


class SpeechToTextService(Protocol):
    async def transcribe(self, audio: bytes, content_type: str) -> Transcription:
        """Convert audio to text without persisting the audio or transcript."""
