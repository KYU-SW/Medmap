from pydantic import BaseModel, Field


class TranscriptionResponse(BaseModel):
    transcript: str = Field(description="사용자가 수정할 수 있는 한국어 변환 결과")
    language: str = Field(default="ko")
    duration_seconds: float | None = Field(default=None, ge=0)
