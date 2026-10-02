from fastapi import APIRouter

from app.schemas.intake import IntakeExtractionRequest, IntakeExtractionResponse
from app.services.intake_extractor import extract_intake


router = APIRouter()


@router.post("/extract", response_model=IntakeExtractionResponse)
def extract(request: IntakeExtractionRequest) -> IntakeExtractionResponse:
    return extract_intake(request.transcript)

