"""Couche 3 — AI Reasoning (OpenAI GPT) : raisonnement 6 étapes uniquement."""

import logging
from typing import Any, Dict, List, Optional

from app.layers.local_entity_engine import LocalEntityResult
from app.services.structured_annotation import annotate_document_structured

logger = logging.getLogger(__name__)


class AIReasoningLayer:
    """
    GPT comme moteur de raisonnement — enrichit les entités locales.
    N'invente pas d'entités : la validation couche 4 filtre la sortie.
    """

    async def reason(
        self,
        text: str,
        local_entities: List[LocalEntityResult],
        clusters_raw: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        annotations = [
            {
                "input": e.original,
                "normalized": e.normalized,
                "arabic_name": e.arabic_name,
                "confidence": e.confidence,
                "phonetic_score": e.phonetic_score,
                "metadata": {
                    "language_detected": e.language_detected,
                    "local_source": e.local_source,
                },
            }
            for e in local_entities
        ]

        return await annotate_document_structured(
            text=text,
            annotations=annotations,
            clusters_raw=clusters_raw or [],
            icl_sample_name=local_entities[0].original if local_entities else None,
        )
