from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class IntakeExtractionRequest(BaseModel):
    transcript: str = Field(min_length=1, max_length=5000)
    # The patient's local date; relative onsets such as "어제부터" become dates from it.
    reference_date: date | None = None


class SymptomObservation(BaseModel):
    name: str
    status: Literal["present", "absent", "uncertain"]
    body_site: str | None = None
    onset: str | None = None
    onset_date: str | None = None
    severity: str | None = None
    frequency: str | None = None
    trend: Literal["improving", "worsening", "unchanged"] | None = None
    source_text: str


class OtherPersonSymptom(BaseModel):
    person: str
    symptom: str
    source_text: str


class PatientProfileHints(BaseModel):
    """Basic information the patient said about themself; the web app saves it after review."""

    age: int | None = None
    sex: Literal["female", "male"] | None = None
    pregnancy: Literal["yes", "no", "unknown"] | None = None
    smoking: Literal["current", "former", "never"] | None = None
    drinking: Literal["yes", "no"] | None = None


class IntakeExtractionResponse(BaseModel):
    symptoms: list[SymptomObservation]
    medications: list[str]
    allergies: list[str]
    medical_history: list[str] = Field(default_factory=list)
    others_symptoms: list[OtherPersonSymptom] = Field(default_factory=list)
    profile: PatientProfileHints = Field(default_factory=PatientProfileHints)
    unrecognized_fragments: list[str] = Field(default_factory=list)
    needs_user_confirmation: bool = True
