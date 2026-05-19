"""Couche 7 — Output Layer : JSON strict production."""

from typing import Any, Dict, List, Optional

from app.ai.annotation_prompts import N_ID_TAGLINE, PIPELINE_STEPS


class OutputLayer:
    """Formate la sortie finale auditables pour systèmes administratifs."""

    def format(
        self,
        entities: List[Dict[str, Any]],
        duplicate_clusters: List[Dict[str, Any]],
        document_summary: str,
        overall_quality_score: int,
        metadata: Optional[Dict[str, Any]] = None,
        pipeline_stats: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        meta = {
            "pipeline_steps": PIPELINE_STEPS,
            "tagline": N_ID_TAGLINE,
            "engine": "N-ID Identity Reasoning Engine",
            **(metadata or {}),
        }
        if pipeline_stats:
            meta["pipeline_stats"] = pipeline_stats

        return {
            "entities": entities,
            "duplicate_clusters": duplicate_clusters,
            "document_summary": document_summary,
            "overall_quality_score": min(100, max(0, int(overall_quality_score))),
            "metadata": meta,
        }
