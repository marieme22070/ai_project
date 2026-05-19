import logging
from typing import List, Optional

import numpy as np

from app.ai.openai_client import get_openai_client
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def get_embedding(text: str) -> Optional[List[float]]:
    client = get_openai_client()
    if client is None or not text.strip():
        return None
    try:
        response = client.embeddings.create(
            model=settings.openai_model_embedding,
            input=text.strip(),
        )
        return response.data[0].embedding
    except Exception as exc:
        logger.error("Embedding failed: %s", exc)
        return None


def cosine_similarity(a: List[float], b: List[float]) -> float:
    va = np.array(a, dtype=np.float64)
    vb = np.array(b, dtype=np.float64)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)
