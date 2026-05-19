import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.services.voice_name import process_voice_to_name
from app.api.deps import get_current_user_optional
from app.database.session import get_db
from app.models.user import User
from app.schemas.name import (
    LiveVoiceNameResponse,
    NameNormalizeRequest,
    NameNormalizeResponse,
    SpeechToNameResponse,
)
from app.services.elasticsearch_service import es_service
from app.services.name_service import NameService

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_AUDIO_BASE = {
    "audio/webm",
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/x-wav",
    "audio/ogg",
    "audio/mp4",
    "audio/x-m4a",
}
MAX_AUDIO_SIZE = 25 * 1024 * 1024  # 25 MB


def _is_allowed_audio(content_type: str) -> bool:
    if not content_type:
        return True
    base = content_type.split(";")[0].strip().lower()
    return base in ALLOWED_AUDIO_BASE or base.startswith("audio/")


async def _process_speech_upload(
    file: UploadFile,
    language_hint: Optional[str],
    db: Session,
) -> SpeechToNameResponse:
    content_type = file.content_type or ""
    if content_type and not _is_allowed_audio(content_type):
        logger.warning("Content type non standard accepté: %s", content_type)

    audio_bytes = await file.read()
    if len(audio_bytes) > MAX_AUDIO_SIZE:
        raise HTTPException(status_code=413, detail="Fichier audio trop volumineux (max 25 Mo)")
    if len(audio_bytes) < 100:
        raise HTTPException(status_code=400, detail="Enregistrement audio trop court ou vide")

    filename = file.filename or "recording.webm"
    if "." not in filename:
        ext = "mp4" if "mp4" in content_type else "webm"
        filename = f"{filename}.{ext}"

    try:
        voice_result = await process_voice_to_name(
            audio_bytes, filename, language_hint=language_hint
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Voice name recognition failed")
        raise HTTPException(
            status_code=503,
            detail=f"Reconnaissance vocale impossible: {exc}",
        ) from exc

    transcription = voice_result.get("transcription", "")
    payload = {k: v for k, v in voice_result.items() if k != "transcription"}
    return SpeechToNameResponse(transcription=transcription, **payload)


@router.post("/normalize-name", response_model=NameNormalizeResponse)
async def normalize_name(
    request: NameNormalizeRequest,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional),
) -> NameNormalizeResponse:
    service = NameService(db)
    result = await service.normalize_name(
        request.name,
        language_hint=request.language_hint,
        source="text",
    )
    return NameNormalizeResponse(**result)


@router.post("/speech-to-name", response_model=SpeechToNameResponse)
async def speech_to_name(
    file: UploadFile = File(...),
    language_hint: Optional[str] = None,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional),
) -> SpeechToNameResponse:
    """Micro → Whisper (noms mauritaniens uniquement) → RapidFuzz → dictionnaire local."""
    return await _process_speech_upload(file, language_hint, db)


@router.post("/live-voice-name", response_model=LiveVoiceNameResponse)
async def live_voice_name(
    file: UploadFile = File(...),
    language_hint: Optional[str] = None,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional),
) -> LiveVoiceNameResponse:
    result = await _process_speech_upload(file, language_hint, db)
    return LiveVoiceNameResponse(**result.model_dump())


@router.get("/autocomplete")
async def autocomplete(q: str, limit: int = 8) -> dict:
    suggestions = es_service.autocomplete(q, limit=limit)
    return {"query": q, "suggestions": suggestions}
