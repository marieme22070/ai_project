import logging
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Racine du projet : hack/
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ENV_FILE = PROJECT_ROOT / ".env.example"


def _load_env_example_only() -> None:
    """Charge UNIQUEMENT hack/.env.example (pas de .env ni autre fichier)."""
    if not ENV_FILE.is_file():
        logger.warning(
            "Fichier %s introuvable. Creez-le avec OPENAI_API_KEY=...",
            ENV_FILE,
        )
        return
    load_dotenv(ENV_FILE, override=True, encoding="utf-8")
    logger.info("Configuration chargee depuis %s", ENV_FILE)


def _load_settings() -> "Settings":
    _load_env_example_only()
    return Settings()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    app_name: str = "N-ID — Annotation d'identités · long contexte (Afrique multilingue)"
    app_version: str = "2.0.0"
    debug: bool = False

    api_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    secret_key: str = "change-me-in-production-use-openssl-rand-hex-32"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    openai_api_key: str = ""
    openai_model_correction: str = "gpt-4.1-mini"
    openai_model_complex: str = "gpt-4.1"
    openai_model_whisper: str = "whisper-1"
    whisper_temperature: float = 0.0
    voice_auto_correct_threshold: int = 85
    openai_model_embedding: str = "text-embedding-3-large"

    database_url: str = "sqlite:///./data/mauritania_names.db"

    elasticsearch_enabled: bool = False
    elasticsearch_url: str = "http://localhost:9200"
    elasticsearch_index: str = "citizens_index"

    fuzzy_threshold: int = 75
    embedding_similarity_threshold: float = 0.85

    cluster_threshold: float = 88.0
    min_confidence_score: int = 35
    long_context_batch_lines: int = 80

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def uses_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def env_file_path(self) -> Optional[Path]:
        return ENV_FILE if ENV_FILE.is_file() else None


@lru_cache
def get_settings() -> Settings:
    return _load_settings()
