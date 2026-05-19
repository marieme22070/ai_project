"""API d'annotation automatique — long contexte, batch, documents."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_optional
from app.database.session import get_db
from app.models.user import User
from app.schemas.annotation import (
    AnnotateNameRequest,
    BatchAnnotateResponse,
    BatchNamesRequest,
    DocumentAnnotateRequest,
    DocumentAnnotateResponse,
    StructuredAnnotationResponse,
)
from app.schemas.name import NameNormalizeResponse
from app.services.annotation_pipeline import AnnotationPipeline
from app.services.batch_processor import MAX_BATCH_ROWS, parse_upload_content

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_UPLOAD = 15 * 1024 * 1024


@router.post("/annotate", response_model=NameNormalizeResponse, tags=["AI Annotation"])
async def annotate_name(
    body: AnnotateNameRequest,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional),
):
    """Annotation IA enrichie d'un nom (scores, doublons, explication)."""
    pipeline = AnnotationPipeline(db)
    result = await pipeline.annotate_single(body.name.strip(), body.language_hint)
    return NameNormalizeResponse(**{k: v for k, v in result.items() if k in NameNormalizeResponse.model_fields})


@router.post("/annotate/full", tags=["AI Annotation"])
async def annotate_name_full(
    body: AnnotateNameRequest,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional),
):
    """Réponse complète avec doublons, tags linguistiques et explication IA."""
    pipeline = AnnotationPipeline(db)
    return await pipeline.annotate_single(body.name.strip(), body.language_hint)


@router.post("/annotate/document", response_model=DocumentAnnotateResponse, tags=["AI Annotation"])
async def annotate_document(
    body: DocumentAnnotateRequest,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional),
):
    """Analyse d'un document administratif long (listes, registres)."""
    pipeline = AnnotationPipeline(db)
    result = await pipeline.annotate_document(
        body.text,
        language_hint=body.language_hint,
        max_names=body.max_names,
    )
    return DocumentAnnotateResponse(**result)


@router.post(
    "/annotate/document/structured",
    response_model=StructuredAnnotationResponse,
    tags=["AI Annotation"],
)
async def annotate_document_structured(
    body: DocumentAnnotateRequest,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Annotation intelligente complète — format JSON production :
    entities, duplicate_clusters, document_summary, overall_quality_score.
    """
    pipeline = AnnotationPipeline(db)
    result = await pipeline.annotate_document_structured(
        body.text,
        language_hint=body.language_hint,
        max_names=body.max_names,
    )
    return StructuredAnnotationResponse(
        entities=result.get("entities", []),
        duplicate_clusters=result.get("duplicate_clusters", []),
        document_summary=result.get("document_summary", ""),
        overall_quality_score=result.get("overall_quality_score", 0),
        metadata={
            **(result.get("metadata") or {}),
            "pipeline": result.get("pipeline"),
        },
    )


@router.post("/annotate/batch", response_model=BatchAnnotateResponse, tags=["AI Annotation"])
async def annotate_batch_names(
    body: BatchNamesRequest,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional),
):
    """Annotation en lot d'une liste de noms."""
    if len(body.names) > MAX_BATCH_ROWS:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {MAX_BATCH_ROWS} noms par requête",
        )
    pipeline = AnnotationPipeline(db)
    result = await pipeline.annotate_batch_names(body.names, body.language_hint)
    return BatchAnnotateResponse(**result)


@router.post("/annotate/upload", response_model=BatchAnnotateResponse, tags=["AI Annotation"])
async def annotate_upload_file(
    file: UploadFile = File(...),
    language_hint: Optional[str] = None,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional),
):
    """Import CSV / Excel / texte → annotation automatique massive."""
    raw = await file.read()
    if len(raw) > MAX_UPLOAD:
        raise HTTPException(status_code=413, detail="Fichier trop volumineux (max 15 Mo)")
    if len(raw) < 2:
        raise HTTPException(status_code=400, detail="Fichier vide")

    try:
        names, file_meta = parse_upload_content(raw, file.filename or "upload.csv")
    except Exception as exc:
        logger.exception("Batch file parse failed")
        raise HTTPException(status_code=400, detail=f"Impossible de lire le fichier: {exc}") from exc

    if not names:
        raise HTTPException(status_code=400, detail="Aucun nom détecté dans le fichier")

    pipeline = AnnotationPipeline(db)
    result = await pipeline.annotate_batch_names(names, language_hint)
    result["file_metadata"] = file_meta
    return BatchAnnotateResponse(**result)
