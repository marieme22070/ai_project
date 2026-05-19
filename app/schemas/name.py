from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class NameNormalizeRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=500)
    language_hint: Optional[str] = Field(None, description="fr, ar, hassaniya, pulaar, wolof")

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        cleaned = " ".join(v.split())
        if not cleaned:
            raise ValueError("Name cannot be empty")
        return cleaned


class NameNormalizeResponse(BaseModel):
    input: str
    normalized: str
    arabic_name: str
    confidence: int = Field(..., ge=0, le=100)
    variants: List[str] = []
    official_match: Optional[str] = None
    matched_citizen_id: Optional[UUID] = None
    phonetic_score: Optional[float] = None
    embedding_score: Optional[float] = None
    duplicate_probability: Optional[float] = Field(
        None, description="Probabilité 0-100 que ce nom soit un doublon connu"
    )
    annotation_quality: Optional[float] = Field(
        None, description="Score qualité de l'annotation 0-100"
    )
    linguistic_tags: List[str] = []
    ai_explanation: Optional[str] = None
    near_duplicates: List[Dict[str, Any]] = []
    metadata: Dict[str, Any] = {}


class SpeechToNameResponse(NameNormalizeResponse):
    transcription: str
    audio_duration_seconds: Optional[float] = None


class LiveVoiceNameResponse(SpeechToNameResponse):
    """Reponse micro navigateur (alias de SpeechToNameResponse)."""


class ValidationRequest(BaseModel):
    history_id: UUID
    approved: bool
    corrected_name: Optional[str] = None
    corrected_arabic: Optional[str] = None
    notes: Optional[str] = None


class LearnNameRequest(BaseModel):
    input_name: str = Field(..., min_length=1, max_length=500)
    normalized: str = Field(..., min_length=1, max_length=255)
    arabic_name: Optional[str] = Field(None, max_length=255)
