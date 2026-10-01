from typing import Literal

from pydantic import BaseModel, Field


class IntakeExtractionRequest(BaseModel):
    transcript: str = Field(min_length=1, max_length=5000)


class SymptomObservation(BaseModel):
    name: str
    status: Literal["present", "absent", "uncertain"]
    body_site: str | None = None
    onset: str | None = None
    severity: str | None = None
    frequency: str | None = None
    trend: Literal["improving", "worsening", "unchanged"] | None = None
    source_text: str


class OtherPersonSymptom(BaseModel):
    person: str
    symptom: str
    source_text: str


class IntakeExtractionResponse(BaseModel):
    symptoms: list[SymptomObservation]
    medications: list[str]
    allergies: list[str]
    medical_history: list[str] = Field(default_factory=list)
    others_symptoms: list[OtherPersonSymptom] = Field(default_factory=list)
    unrecognized_fragments: list[str] = Field(default_factory=list)
    needs_user_confirmation: bool = True
