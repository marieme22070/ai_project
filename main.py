import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from sqlalchemy.orm import Session

from app.api import api_router
from app.api.names import live_voice_name, normalize_name, speech_to_name
from app.config import get_settings
from app.database.seed import seed_admin_user, seed_citizens
from app.database.session import SessionLocal, get_db, init_db
from app.schemas.name import (
    LiveVoiceNameResponse,
    NameNormalizeRequest,
    NameNormalizeResponse,
    SpeechToNameResponse,
)
from app.services.elasticsearch_service import es_service
from app.services.name_knowledge import get_knowledge_stats, reload_learned_names
from app.utils.logging_config import setup_logging

settings = get_settings()
setup_logging(settings.debug)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    reload_learned_names()
    es_service.connect()
    try:
        db = SessionLocal()
        try:
            seed_admin_user(db)
            seed_citizens(db)
        finally:
            db.close()
    except Exception as exc:
        logger.warning("Database seed skipped: %s", exc)
    logger.info("%s v%s started.", settings.app_name, settings.app_version)
    yield
    logger.info("Application shutdown.")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "N-ID — Mauritania AI Identity Standardization System. "
        "AI Identity Reasoning Engine : 7 couches (preprocessing → local → GPT → validation → "
        "clustering → identity graph → JSON). Afrique multilingue, long contexte. "
        "Langues: arabe, français, hassaniya, pulaar, wolof."
    ),
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_prefix)


@app.post("/normalize-name", response_model=NameNormalizeResponse, tags=["Name Standardization"])
async def normalize_name_root(
    request: NameNormalizeRequest,
    db: Session = Depends(get_db),
):
    return await normalize_name(request, db)


@app.post("/speech-to-name", response_model=SpeechToNameResponse, tags=["Name Standardization"])
async def speech_to_name_root(
    file: UploadFile = File(...),
    language_hint: str | None = None,
    db: Session = Depends(get_db),
):
    return await speech_to_name(file=file, language_hint=language_hint, db=db)


@app.post("/live-voice-name", response_model=LiveVoiceNameResponse, tags=["Name Standardization"])
async def live_voice_name_root(
    file: UploadFile = File(...),
    language_hint: str | None = None,
    db: Session = Depends(get_db),
):
    return await live_voice_name(file=file, language_hint=language_hint, db=db)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": settings.app_version,
        "database": "sqlite" if settings.uses_sqlite else "postgresql",
        "elasticsearch": es_service.available,
        "elasticsearch_enabled": settings.elasticsearch_enabled,
        "openai_configured": bool(settings.openai_api_key),
        "config_file": str(settings.env_file_path) if settings.env_file_path else None,
        "knowledge": get_knowledge_stats(),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=settings.debug)
