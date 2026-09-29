from dataclasses import dataclass

from fastapi.testclient import TestClient

from app.main import app
from app.api.routes import stt


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_rejects_unsupported_audio_type() -> None:
    response = client.post(
        "/v1/stt/transcribe",
        files={"file": ("note.txt", b"not audio", "text/plain")},
    )
    assert response.status_code == 415


def test_rejects_empty_audio() -> None:
    response = client.post(
        "/v1/stt/transcribe",
        files={"file": ("empty.webm", b"", "audio/webm")},
    )
    assert response.status_code == 422


def test_accepts_webm_type_with_codec_parameter(monkeypatch) -> None:
    @dataclass(frozen=True)
    class Result:
        text: str = "머리가 아파요."
        language: str = "ko"
        duration_seconds: float = 1.0

    class FakeService:
        def transcribe(self, audio: bytes, content_type: str) -> Result:
            assert content_type == "audio/webm"
            return Result()

    monkeypatch.setattr(stt, "get_stt_service", lambda: FakeService())
    response = client.post(
        "/v1/stt/transcribe",
        files={"file": ("sample.webm", b"fake audio", "audio/webm;codecs=opus")},
    )

    assert response.status_code == 200


def test_returns_transcript_from_service(monkeypatch) -> None:
    @dataclass(frozen=True)
    class Result:
        text: str = "어제부터 머리가 아파요."
        language: str = "ko"
        duration_seconds: float = 2.5

    class FakeService:
        def transcribe(self, audio: bytes, content_type: str) -> Result:
            assert audio == b"fake audio"
            assert content_type == "audio/webm"
            return Result()

    monkeypatch.setattr(stt, "get_stt_service", lambda: FakeService())
    response = client.post(
        "/v1/stt/transcribe",
        files={"file": ("sample.webm", b"fake audio", "audio/webm")},
    )

    assert response.status_code == 200
    assert response.json() == {
        "transcript": "어제부터 머리가 아파요.",
        "language": "ko",
        "duration_seconds": 2.5,
    }
