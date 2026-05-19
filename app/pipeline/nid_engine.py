"""N-ID Engine — orchestrateur des 7 couches architecturales."""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.ai.annotation_prompts import PIPELINE_STEPS
from app.identity_graph.service import IdentityGraphService
from app.layers.ai_reasoning import AIReasoningLayer
from app.layers.clustering import ClusteringEngine
from app.layers.local_entity_engine import LocalEntityEngine, LocalEntityResult
from app.layers.output_formatter import OutputLayer
from app.layers.preprocessing import PreprocessingLayer
from app.layers.validation import ValidationLayer
from app.services.name_service import NameService

logger = logging.getLogger(__name__)


class NIDEngine:
    """
    AI Identity Reasoning Engine for multilingual administrative data.

    Pipeline :
      1. Preprocessing
      2. Local Entity Engine
      3. AI Reasoning (GPT)
      4. Validation (anti-hallucination)
      5. Clustering
      6. Identity Graph Memory
      7. Output JSON
    """

    def __init__(self, db: Session):
        self.db = db
        self.preprocessing = PreprocessingLayer()
        self.local_engine = LocalEntityEngine()
        self.ai_reasoning = AIReasoningLayer()
        self.validation = ValidationLayer()
        self.clustering = ClusteringEngine()
        self.output = OutputLayer()
        self.identity_graph = IdentityGraphService(db)
        self.name_service = NameService(db)

    async def _enrich_with_openai_normalization(
        self,
        local_entities: List[LocalEntityResult],
        language_hint: Optional[str],
    ) -> List[LocalEntityResult]:
        """Enrichit la normalisation locale via NameService (GPT si disponible)."""
        enriched: List[LocalEntityResult] = []
        for ent in local_entities:
            try:
                result = await self.name_service.normalize_name(
                    ent.original,
                    language_hint=language_hint,
                    source="nid_engine",
                    save_history=False,
                )
                ent.normalized = result.get("normalized", ent.normalized)
                ent.arabic_name = result.get("arabic_name", ent.arabic_name)
                ent.confidence = int(result.get("confidence", ent.confidence))
                ent.metadata["ai_used"] = result.get("metadata", {}).get("ai_used", False)
            except Exception as exc:
                logger.warning("OpenAI enrich failed for %s: %s", ent.original, exc)
            enriched.append(ent)
        return enriched

    async def process_document(
        self,
        text: str,
        language_hint: Optional[str] = None,
        max_names: int = 100,
        persist_graph: bool = True,
        use_ai_reasoning: bool = True,
    ) -> Dict[str, Any]:
        """Exécute le pipeline complet sur un document administratif."""
        stats: Dict[str, Any] = {"layers": []}

        # —— 1. PREPROCESSING ——
        pre = self.preprocessing.run(text, max_names=max_names)
        stats["layers"].append({"layer": "preprocessing", **pre.metadata})
        if not pre.entities:
            return self.output.format(
                entities=[],
                duplicate_clusters=[],
                document_summary="Aucune entité nominative détectée dans le document.",
                overall_quality_score=0,
                metadata={"pipeline_steps": PIPELINE_STEPS},
                pipeline_stats=stats,
            )

        source_originals = [e.original for e in pre.entities]

        # —— 2. LOCAL ENTITY ENGINE ——
        local_entities = self.local_engine.process_all(pre.entities)
        local_entities = await self._enrich_with_openai_normalization(
            local_entities, language_hint
        )
        stats["layers"].append({"layer": "local_entity_engine", "count": len(local_entities)})

        annotations_for_cluster = [
            {
                "input": e.original,
                "normalized": e.normalized,
                "arabic_name": e.arabic_name,
                "confidence": e.confidence,
                "phonetic_score": e.phonetic_score,
                "metadata": {"language_detected": e.language_detected, **e.metadata},
            }
            for e in local_entities
        ]

        # —— 5. CLUSTERING (pré-calcul pour GPT) ——
        clusters_raw = self.clustering.cluster_from_entities(
            [{"original": e.original, "normalized": e.normalized} for e in local_entities]
        )
        stats["layers"].append({"layer": "clustering_precalc", "clusters": len(clusters_raw)})

        # —— 3. AI REASONING ——
        if use_ai_reasoning:
            structured = await self.ai_reasoning.reason(
                pre.cleaned_text, local_entities, clusters_raw
            )
            stats["layers"].append(
                {
                    "layer": "ai_reasoning",
                    "ai_used": structured.get("metadata", {}).get("ai_used", False),
                }
            )
        else:
            structured = self.clustering.apply_pipeline_clustering(
                pre.cleaned_text, annotations_for_cluster, clusters_raw
            )

        # —— 4. VALIDATION ——
        structured = self.validation.validate(structured, source_originals)
        stats["layers"].append({"layer": "validation", **structured.get("metadata", {}).get("validation", {})})

        # —— 5. CLUSTERING final (6 étapes sur entités validées) ——
        if not use_ai_reasoning or not structured.get("entities"):
            structured = self.clustering.apply_pipeline_clustering(
                pre.cleaned_text, annotations_for_cluster, clusters_raw
            )
            structured = self.validation.validate(structured, source_originals)

        entities = structured.get("entities", [])
        duplicate_clusters = structured.get("duplicate_clusters", [])
        summary = structured.get("document_summary", "")
        overall = structured.get("overall_quality_score", 0)

        # —— 6. IDENTITY GRAPH ——
        graph_meta = {}
        if persist_graph and entities:
            try:
                graph_meta = self.identity_graph.ingest_document(
                    entities, duplicate_clusters, pre.document_hash
                )
                stats["layers"].append({"layer": "identity_graph", **graph_meta})
            except Exception as exc:
                logger.warning("Identity graph ingest failed: %s", exc)
                graph_meta = {"error": str(exc)[:200]}

        # —— 7. OUTPUT ——
        meta = structured.get("metadata") or {}
        meta["document_hash"] = pre.document_hash
        meta["document_language"] = pre.document_language
        meta["identity_graph"] = graph_meta
        meta["is_long_context"] = pre.metadata.get("is_long_context", False)

        return self.output.format(
            entities=entities,
            duplicate_clusters=duplicate_clusters,
            document_summary=summary,
            overall_quality_score=overall,
            metadata=meta,
            pipeline_stats=stats,
        )
