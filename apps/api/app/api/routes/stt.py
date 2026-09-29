from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.schemas.stt import TranscriptionResponse


router = APIRouter()

ALLOWED_CONTENT_TYPES = {
    "audio/webm",
    "audio/wav",
    "audio/x-wav",
    "audio/mp4",
    "audio/mpeg",
}


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe(file: UploadFile = File(...)) -> TranscriptionResponse:
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="지원하지 않는 음성 형식입니다.",
        )

    # The Whisper service is intentionally added in the next implementation step.
    # Do not log or persist the uploaded audio while completing this endpoint.
    await file.close()
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="음성 변환 모델을 연결하는 중입니다.",
    )
