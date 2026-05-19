from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CitizenCreate(BaseModel):
    official_name: str = Field(..., min_length=1, max_length=255)
    arabic_name: Optional[str] = None
    variants: List[str] = []
    language: Optional[str] = None
    region: Optional[str] = None


class CitizenResponse(BaseModel):
    id: UUID
    official_name: str
    arabic_name: Optional[str]
    variants: List[str]
    language: Optional[str]
    region: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class CitizenSearchResult(BaseModel):
    id: UUID
    official_name: str
    arabic_name: Optional[str]
    score: float
    match_type: str
