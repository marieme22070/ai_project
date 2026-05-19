"""Fallback when OpenAI is unavailable — délègue au dictionnaire local."""

from typing import Any, Dict

from app.services.local_dictionary import normalize_from_local_dictionary


def apply_fallback_normalization(name: str) -> Dict[str, Any]:
    return normalize_from_local_dictionary(name)
