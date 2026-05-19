import logging
from functools import lru_cache
from typing import Optional

from openai import OpenAI

from app.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def get_openai_client() -> Optional[OpenAI]:
    settings = get_settings()
    # Cle chargee uniquement depuis hack/.env.example via app.config
    key = settings.openai_api_key.strip()
    if not key:
        logger.warning("OPENAI_API_KEY not set — AI features will use fallback rules.")
        return None
    return OpenAI(api_key=key)
