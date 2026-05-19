"""Couche 1 — Preprocessing : nettoyage, langue, segmentation, extraction."""

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.services.entity_extractor import extract_names_from_text, linguistic_hint
from app.utils.arabic import is_arabic
from app.utils.text import normalize_unicode

try:
    import langdetect

    HAS_LANGDETECT = True
except ImportError:
    HAS_LANGDETECT = False


@dataclass
class ExtractedEntity:
    original: str
    line_number: int
    segment_id: int = 0


@dataclass
class PreprocessingResult:
    cleaned_text: str
    document_hash: str
    document_language: str
    segments: List[str]
    entities: List[ExtractedEntity]
    metadata: Dict[str, Any] = field(default_factory=dict)


class PreprocessingLayer:
    """Nettoyage, détection langue, segmentation long contexte, extraction noms."""

    BATCH_LINE_SIZE = 80
    MAX_ENTITIES = 500

    def clean_text(self, text: str) -> str:
        text = normalize_unicode(text)
        text = re.sub(r"\r\n?", "\n", text)
        text = re.sub(r"\n{4,}", "\n\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        return text.strip()

    def document_hash(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    def detect_language(self, text: str) -> str:
        if is_arabic(text[:500]):
            return "ar"
        if HAS_LANGDETECT:
            try:
                code = langdetect.detect(text[:2000])
                mapping = {"fr": "fr", "ar": "ar", "en": "fr"}
                return mapping.get(code, "mixed")
            except Exception:
                pass
        return "mixed"

    def segment_document(self, text: str) -> List[str]:
        """Découpe un long document en segments pour analyse progressive."""
        lines = text.splitlines()
        if len(lines) <= self.BATCH_LINE_SIZE:
            return [text]

        segments: List[str] = []
        for i in range(0, len(lines), self.BATCH_LINE_SIZE):
            chunk = "\n".join(lines[i : i + self.BATCH_LINE_SIZE])
            if chunk.strip():
                segments.append(chunk)
        return segments or [text]

    def extract_entities(
        self,
        text: str,
        max_names: int = 100,
    ) -> List[ExtractedEntity]:
        """Extraction initiale — toutes les occurrences (pas de déduplication)."""
        raw = extract_names_from_text(text, max_names=min(max_names, self.MAX_ENTITIES))
        return [
            ExtractedEntity(original=name, line_number=line_no, segment_id=0)
            for name, line_no in raw
        ]

    def run(self, text: str, max_names: int = 100) -> PreprocessingResult:
        cleaned = self.clean_text(text)
        doc_lang = self.detect_language(cleaned)
        segments = self.segment_document(cleaned)

        all_entities: List[ExtractedEntity] = []
        for seg_id, segment in enumerate(segments):
            for ent in self.extract_entities(segment, max_names=max_names):
                ent.segment_id = seg_id
                all_entities.append(ent)
            if len(all_entities) >= max_names:
                break

        all_entities = all_entities[:max_names]

        return PreprocessingResult(
            cleaned_text=cleaned,
            document_hash=self.document_hash(cleaned),
            document_language=doc_lang,
            segments=segments,
            entities=all_entities,
            metadata={
                "segment_count": len(segments),
                "entity_count": len(all_entities),
                "is_long_context": len(segments) > 1,
            },
        )
