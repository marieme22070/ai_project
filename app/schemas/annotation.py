from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AnnotateNameRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=500)
    language_hint: Optional[str] = None


class DocumentAnnotateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=500_000)
    language_hint: Optional[str] = None
    max_names: int = Field(100, ge=1, le=500)


class BatchNamesRequest(BaseModel):
    names: List[str] = Field(..., min_length=1, max_length=2000)
    language_hint: Optional[str] = None


class AnnotationItem(BaseModel):
    input: str
    detected_name: Optional[str] = None
    normalized: str = ""
    arabic_name: str = ""
    confidence: int = 0
    annotation_quality: float = 0.0
    duplicate_probability: float = 0.0
    phonetic_score: Optional[float] = None
    linguistic_tags: List[str] = []
    variants: List[str] = []
    near_duplicates: List[Dict[str, Any]] = []
    ai_explanation: str = ""
    metadata: Dict[str, Any] = {}
    line_number: Optional[int] = None


class DocumentAnnotateResponse(BaseModel):
    total_extracted: int
    total_annotated: int
    annotations: List[Dict[str, Any]]
    identity_clusters: List[Dict[str, Any]]
    summary: Dict[str, Any]


class BatchAnnotateResponse(BaseModel):
    total: int
    annotations: List[Dict[str, Any]]
    identity_clusters: List[Dict[str, Any]]
    summary: Dict[str, Any]
    file_metadata: Optional[Dict[str, Any]] = None


class AnnotationEntity(BaseModel):
    original: str
    normalized: str
    language_detected: str = ""
    confidence_score: int = Field(0, ge=0, le=100)
    phonetic_similarity: float = Field(0, ge=0, le=100)
    duplicate_group_id: str = ""
    explanation: str = ""


class DuplicateCluster(BaseModel):
    group_id: str
    members: List[str] = []
    reasoning: str = ""


class StructuredAnnotationResponse(BaseModel):
    """Format JSON obligatoire — moteur d'annotation N-ID production."""

    entities: List[AnnotationEntity] = []
    duplicate_clusters: List[DuplicateCluster] = []
    document_summary: str = ""
    overall_quality_score: int = Field(0, ge=0, le=100)
    metadata: Optional[Dict[str, Any]] = None
