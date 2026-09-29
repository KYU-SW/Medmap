from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool

from app.schemas.stt import TranscriptionResponse
from app.services.stt_service import (
    NoSpeechDetectedError,
    SpeechModelUnavailableError,
    get_stt_service,
)


router = APIRouter()

ALLOWED_CONTENT_TYPES = {
    "audio/mp4",
    "audio/ogg",
    "audio/webm",
    "audio/wav",
    "audio/x-wav",
    "audio/mpeg",
    "video/webm",
}
MAX_AUDIO_BYTES = 25 * 1024 * 1024


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe(file: UploadFile = File(...)) -> TranscriptionResponse:
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="지원하지 않는 음성 형식입니다.",
        )

    audio = await file.read(MAX_AUDIO_BYTES + 1)
    await file.close()

    if not audio:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="음성 파일이 비어 있습니다.",
        )
    if len(audio) > MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="음성 파일은 25MB 이하여야 합니다.",
        )

    try:
        result = await run_in_threadpool(
            get_stt_service().transcribe,
            audio,
            file.content_type,
        )
    except NoSpeechDetectedError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except SpeechModelUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return TranscriptionResponse(
        transcript=result.text,
        language=result.language,
        duration_seconds=result.duration_seconds,
    )
