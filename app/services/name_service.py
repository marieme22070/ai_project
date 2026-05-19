import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.ai.embeddings import cosine_similarity, get_embedding
from app.ai.normalizer import normalize_with_ai
from app.config import get_settings
from app.models.citizen import Citizen
from app.models.correction_history import CorrectionHistory
from app.services.confidence_scorer import compute_annotation_scores
from app.services.duplicate_detector import duplicate_probability_for_name
from app.services.elasticsearch_service import es_service
from app.services.entity_extractor import linguistic_hint
from app.services.phonetic import combined_match_score, find_best_matches

logger = logging.getLogger(__name__)
settings = get_settings()


class NameService:
    def __init__(self, db: Session):
        self.db = db

    def _load_citizens(self) -> List[Citizen]:
        return self.db.query(Citizen).limit(5000).all()

    def _match_in_database(
        self,
        normalized: str,
        embedding: Optional[List[float]] = None,
    ) -> Optional[Dict[str, Any]]:
        citizens = self._load_citizens()
        if not citizens:
            return None

        best: Optional[Dict[str, Any]] = None
        best_score = 0.0

        all_names: List[tuple[str, Citizen]] = []
        for c in citizens:
            all_names.append((c.official_name, c))
            for v in c.variants or []:
                all_names.append((v, c))

        for name, citizen in all_names:
            score = combined_match_score(normalized, name)
            if embedding and citizen.embedding:
                emb_score = cosine_similarity(embedding, citizen.embedding) * 100
                score = score * 0.6 + emb_score * 0.4

            if score > best_score:
                best_score = score
                best = {
                    "citizen": citizen,
                    "score": score,
                    "matched_name": name,
                }

        if best and best_score >= settings.fuzzy_threshold:
            return best
        return None

    def _search_elasticsearch(self, query: str) -> List[Dict[str, Any]]:
        return es_service.search(query, limit=5)

    async def normalize_name(
        self,
        name: str,
        language_hint: Optional[str] = None,
        source: str = "text",
        save_history: bool = True,
    ) -> Dict[str, Any]:
        ai_result = await normalize_with_ai(name, language_hint)
        normalized = ai_result["normalized"]
        variants = list(dict.fromkeys(ai_result.get("variants", []) + [normalized, name]))

        embedding = get_embedding(normalized)
        db_match = self._match_in_database(normalized, embedding)
        es_hits = self._search_elasticsearch(normalized)

        confidence = ai_result["confidence"]
        official_match = None
        matched_citizen_id = None
        phonetic_score = None
        embedding_score = None

        if db_match:
            official_match = db_match["citizen"].official_name
            matched_citizen_id = db_match["citizen"].id
            phonetic_score = db_match["score"]
            confidence = min(100, int((confidence + db_match["score"]) / 2))
            if db_match["citizen"].arabic_name:
                ai_result["arabic_name"] = db_match["citizen"].arabic_name
        elif es_hits:
            top = es_hits[0]
            official_match = top.get("official_name")
            confidence = min(100, int((confidence + min(top.get("score", 0) / 2, 50)) / 1.2))
            phonetic_score = combined_match_score(normalized, official_match or "")

        if embedding:
            for c in self._load_citizens()[:100]:
                if c.embedding:
                    sim = cosine_similarity(embedding, c.embedding)
                    if sim >= settings.embedding_similarity_threshold:
                        embedding_score = round(sim * 100, 2)
                        break

        candidates = []
        for c in self._load_citizens():
            candidates.append(c.official_name)
            candidates.extend(c.variants or [])
        candidates = list(dict.fromkeys(candidates))

        dup_prob, near_dupes = duplicate_probability_for_name(normalized, candidates)
        scores = compute_annotation_scores(
            ai_confidence=confidence,
            phonetic_score=phonetic_score,
            embedding_score=embedding_score,
            duplicate_probability=dup_prob,
            local_match="local" in (ai_result.get("notes") or "").lower(),
            ai_used=ai_result.get("ai_used", False),
        )

        lang_tags = [linguistic_hint(name)]
        if ai_result.get("language_detected"):
            lang_tags.append(ai_result["language_detected"])

        result = {
            "input": name,
            "normalized": normalized,
            "arabic_name": ai_result.get("arabic_name", ""),
            "confidence": scores["confidence"],
            "annotation_quality": scores["annotation_quality"],
            "duplicate_probability": scores["duplicate_probability"],
            "variants": variants[:8],
            "official_match": official_match,
            "matched_citizen_id": matched_citizen_id,
            "phonetic_score": phonetic_score,
            "embedding_score": embedding_score,
            "linguistic_tags": list(dict.fromkeys(lang_tags)),
            "near_duplicates": near_dupes[:5],
            "ai_explanation": ai_result.get("notes", ""),
            "metadata": {
                "language_detected": ai_result.get("language_detected"),
                "ai_used": ai_result.get("ai_used", False),
                "model": ai_result.get("model"),
                "notes": ai_result.get("notes", ""),
                "source": source,
                "es_results_count": len(es_hits),
            },
        }

        if save_history:
            self._save_history(result, source)

        return result

    def _save_history(self, result: Dict[str, Any], source: str) -> None:
        try:
            history = CorrectionHistory(
                input_name=result["input"],
                normalized_name=result["normalized"],
                arabic_name=result.get("arabic_name"),
                confidence=result.get("confidence"),
                variants=result.get("variants", []),
                source=source,
                matched_citizen_id=result.get("matched_citizen_id"),
                metadata_json=result.get("metadata", {}),
            )
            self.db.add(history)
            self.db.commit()
        except Exception as exc:
            logger.warning("Could not save history: %s", exc)
            self.db.rollback()

    def detect_duplicates(self, threshold: float = 85.0) -> List[Dict[str, Any]]:
        from app.services.duplicate_detector import detect_citizen_duplicates_enhanced

        citizens = self._load_citizens()
        return detect_citizen_duplicates_enhanced(citizens, threshold=threshold)
