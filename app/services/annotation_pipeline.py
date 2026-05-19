"""Pipeline d'annotation IA : extraction → GPT/ICL → phonétique → doublons → scores."""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.services.confidence_scorer import compute_annotation_scores
from app.services.duplicate_detector import (
    duplicate_probability_for_name,
    find_identity_clusters,
)
from app.services.entity_extractor import extract_names_from_text, linguistic_hint
from app.services.icl_selector import select_icl_examples
from app.services.name_service import NameService
from app.services.phonetic import combined_match_score

logger = logging.getLogger(__name__)


class AnnotationPipeline:
    """Orchestrateur du flux IA N-ID pour annotation long-contexte."""

    def __init__(self, db: Session):
        self.db = db
        self.name_service = NameService(db)

    def _candidate_names(self) -> List[str]:
        citizens = self.name_service._load_citizens()
        names: List[str] = []
        for c in citizens:
            names.append(c.official_name)
            names.extend(c.variants or [])
        return list(dict.fromkeys(names))

    async def annotate_single(
        self,
        name: str,
        language_hint: Optional[str] = None,
        save_history: bool = True,
    ) -> Dict[str, Any]:
        """Annoter un nom unique avec scores enrichis."""
        icl_examples = select_icl_examples(name)
        result = await self.name_service.normalize_name(
            name,
            language_hint=language_hint,
            source="annotation",
            save_history=save_history,
        )

        candidates = self._candidate_names()
        dup_prob, near_dupes = duplicate_probability_for_name(
            result["normalized"],
            candidates + [result["input"]],
        )

        scores = compute_annotation_scores(
            ai_confidence=result.get("confidence", 0),
            phonetic_score=result.get("phonetic_score"),
            embedding_score=result.get("embedding_score"),
            duplicate_probability=dup_prob,
            local_match=bool(result.get("metadata", {}).get("notes", "").find("local")),
            ai_used=result.get("metadata", {}).get("ai_used", False),
        )

        meta = result.get("metadata") or {}
        meta["icl_examples_used"] = len(icl_examples)
        meta["linguistic_tags"] = [linguistic_hint(name)]
        if meta.get("language_detected"):
            meta["linguistic_tags"].append(meta["language_detected"])

        ai_explanation = _build_explanation(result, scores, near_dupes, icl_examples)

        return {
            **result,
            **scores,
            "detected_name": name,
            "linguistic_tags": list(dict.fromkeys(meta.get("linguistic_tags", []))),
            "near_duplicates": near_dupes[:5],
            "ai_explanation": ai_explanation,
            "metadata": meta,
        }

    async def annotate_document(
        self,
        text: str,
        language_hint: Optional[str] = None,
        max_names: int = 100,
    ) -> Dict[str, Any]:
        """Analyser un document long : extraire et annoter les noms."""
        extracted = extract_names_from_text(text, max_names=max_names)
        if not extracted:
            return {
                "total_extracted": 0,
                "annotations": [],
                "identity_clusters": [],
                "summary": {"message": "Aucun nom détecté dans le document."},
            }

        annotations: List[Dict[str, Any]] = []
        raw_names = [n for n, _ in extracted]

        for name, line_no in extracted[:max_names]:
            try:
                ann = await self.annotate_single(name, language_hint, save_history=False)
                ann["line_number"] = line_no
                annotations.append(ann)
            except Exception as exc:
                logger.warning("Annotation failed for %s: %s", name, exc)
                annotations.append(
                    {
                        "input": name,
                        "detected_name": name,
                        "line_number": line_no,
                        "error": str(exc),
                        "confidence": 0,
                    }
                )

        clusters = find_identity_clusters(
            [a.get("normalized") or a.get("input", "") for a in annotations if "error" not in a],
            threshold=88.0,
        )

        avg_conf = (
            sum(a.get("confidence", 0) for a in annotations if "error" not in a)
            / max(1, len([a for a in annotations if "error" not in a]))
        )

        high_dup = sum(1 for a in annotations if a.get("duplicate_probability", 0) >= 75)

        return {
            "total_extracted": len(extracted),
            "total_annotated": len(annotations),
            "annotations": annotations,
            "identity_clusters": clusters,
            "summary": {
                "average_confidence": round(avg_conf, 1),
                "duplicate_alerts": high_dup,
                "cluster_count": len(clusters),
                "languages_detected": list(
                    dict.fromkeys(
                        tag
                        for a in annotations
                        for tag in (a.get("linguistic_tags") or [])
                    )
                )[:10],
            },
        }

    async def annotate_document_structured(
        self,
        text: str,
        language_hint: Optional[str] = None,
        max_names: int = 100,
    ) -> Dict[str, Any]:
        """Document long → pipeline N-ID 7 couches → JSON structuré production."""
        from app.pipeline.nid_engine import NIDEngine

        engine = NIDEngine(self.db)
        result = await engine.process_document(
            text,
            language_hint=language_hint,
            max_names=max_names,
            persist_graph=True,
            use_ai_reasoning=True,
        )
        pre_count = result.get("metadata", {}).get("pipeline_stats", {}).get("layers", [{}])
        extracted = 0
        for layer in pre_count:
            if layer.get("layer") == "preprocessing":
                extracted = layer.get("entity_count", 0)
                break
        result["pipeline"] = {
            "total_extracted": extracted,
            "total_annotated": len(result.get("entities", [])),
            "architecture": "7-layer",
        }
        return result

    async def annotate_batch_names(
        self,
        names: List[str],
        language_hint: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Annoter une liste de noms (CSV parsé côté batch_processor)."""
        annotations = []
        for name in names:
            ann = await self.annotate_single(name, language_hint, save_history=False)
            annotations.append(ann)

        clusters = find_identity_clusters(
            [a.get("normalized", "") for a in annotations],
            threshold=88.0,
        )

        return {
            "total": len(annotations),
            "annotations": annotations,
            "identity_clusters": clusters,
            "summary": {
                "average_confidence": round(
                    sum(a.get("confidence", 0) for a in annotations) / max(1, len(annotations)),
                    1,
                ),
                "duplicate_alerts": sum(
                    1 for a in annotations if a.get("duplicate_probability", 0) >= 75
                ),
            },
        }


def _build_explanation(
    result: Dict[str, Any],
    scores: Dict[str, Any],
    near_dupes: List[Dict[str, Any]],
    icl_examples: List[Dict[str, Any]],
) -> str:
    parts = []
    inp = result.get("input", "")
    norm = result.get("normalized", "")

    if inp.lower() != norm.lower():
        parts.append(f"Normalisation : « {inp} » → « {norm} ».")
    else:
        parts.append(f"Nom déjà conforme ou très proche de la forme standard : « {norm} ».")

    conf = scores.get("confidence", 0)
    parts.append(f"Confiance globale : {conf}%.")

    meta = result.get("metadata") or {}
    if meta.get("ai_used"):
        parts.append("Raisonnement OpenAI appliqué avec contexte ICL.")
    if meta.get("notes"):
        parts.append(str(meta["notes"]))

    if icl_examples:
        parts.append(f"{len(icl_examples)} exemple(s) few-shot du dictionnaire local utilisé(s).")

    if near_dupes and near_dupes[0].get("likely_duplicate"):
        parts.append(
            f"Alerte doublon : similarité {near_dupes[0]['similarity_score']:.0f}% "
            f"avec « {near_dupes[0]['name']} »."
        )

    return " ".join(parts)
