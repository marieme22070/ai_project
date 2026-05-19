"""Couche 2 — Local Entity Engine : fuzzy, phonétique, règles, dictionnaire."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.layers.preprocessing import ExtractedEntity
from app.services.confidence_scorer import compute_annotation_scores
from app.services.entity_extractor import linguistic_hint
from app.services.local_dictionary import normalize_from_local_dictionary
from app.services.phonetic import combined_match_score
from app.services.fallback_rules import apply_fallback_normalization
from app.utils.text import title_case_name


@dataclass
class LocalEntityResult:
    original: str
    normalized: str
    arabic_name: str
    language_detected: str
    confidence: int
    phonetic_score: float
    local_source: Optional[str]
    line_number: int
    segment_id: int
    metadata: Dict[str, Any] = field(default_factory=dict)


class LocalEntityEngine:
    """Normalisation locale sans GPT — RapidFuzz + phonétique + dictionnaire."""

    def normalize_one(self, entity: ExtractedEntity) -> LocalEntityResult:
        original = entity.original
        local = normalize_from_local_dictionary(original)

        if local.get("normalized") and local.get("confidence", 0) >= 75:
            normalized = local["normalized"]
            arabic = local.get("arabic_name") or local.get("arabic", "")
            confidence = int(local["confidence"])
            source = local.get("local_source", "dictionary")
        else:
            fallback = apply_fallback_normalization(original)
            normalized = title_case_name(fallback.get("normalized", original))
            arabic = fallback.get("arabic_name", "")
            confidence = int(fallback.get("confidence", 70))
            source = "rules"

        phonetic = round(combined_match_score(original, normalized), 1)
        lang = linguistic_hint(original)

        scores = compute_annotation_scores(
            ai_confidence=confidence,
            phonetic_score=phonetic,
            local_match=source == "dictionary",
            ai_used=False,
        )

        return LocalEntityResult(
            original=original,
            normalized=normalized,
            arabic_name=arabic,
            language_detected=lang,
            confidence=scores["confidence"],
            phonetic_score=phonetic,
            local_source=source,
            line_number=entity.line_number,
            segment_id=entity.segment_id,
            metadata={
                "annotation_quality": scores.get("annotation_quality"),
                "duplicate_probability": scores.get("duplicate_probability"),
            },
        )

    def process_all(self, entities: List[ExtractedEntity]) -> List[LocalEntityResult]:
        return [self.normalize_one(e) for e in entities]
