"""Couche 4 — Validation anti-hallucination."""

import logging
from typing import Any, Dict, List, Set

from app.services.phonetic import combined_match_score

logger = logging.getLogger(__name__)

MIN_CONFIDENCE = 35


class ValidationLayer:
    """Compare sortie IA avec entités source — supprime inventions, applique seuils."""

    def __init__(self, min_confidence: int = MIN_CONFIDENCE):
        self.min_confidence = min_confidence

    def _known_originals(self, source_originals: List[str]) -> Set[str]:
        return {o.lower().strip() for o in source_originals if o.strip()}

    def _is_grounded(self, original: str, known: Set[str]) -> bool:
        key = original.lower().strip()
        if key in known:
            return True
        for k in known:
            if combined_match_score(original, k) >= 88:
                return True
        return False

    def validate(
        self,
        structured: Dict[str, Any],
        source_originals: List[str],
    ) -> Dict[str, Any]:
        known = self._known_originals(source_originals)
        entities = structured.get("entities", [])
        valid_entities: List[Dict[str, Any]] = []
        rejected = 0

        for ent in entities:
            orig = (ent.get("original") or "").strip()
            if not orig or not self._is_grounded(orig, known):
                rejected += 1
                continue
            conf = int(ent.get("confidence_score", 0))
            if conf < self.min_confidence:
                ent = {**ent, "confidence_score": self.min_confidence}
            valid_entities.append(ent)

        # Filtrer clusters : membres doivent exister
        valid_clusters = []
        for cluster in structured.get("duplicate_clusters", []):
            members = [
                m
                for m in (cluster.get("members") or [])
                if self._is_grounded(m, known)
            ]
            if len(members) >= 2:
                valid_clusters.append({**cluster, "members": members})

        meta = structured.get("metadata") or {}
        meta["validation"] = {
            "entities_accepted": len(valid_entities),
            "entities_rejected": rejected,
            "min_confidence": self.min_confidence,
        }

        return {
            **structured,
            "entities": valid_entities,
            "duplicate_clusters": valid_clusters,
            "metadata": meta,
        }
