"""Couche 5 — Clustering Engine : fusion ≥ seuil, sinon séparation."""

from typing import Any, Dict, List

from app.services.duplicate_detector import find_identity_clusters
from app.services.reasoning_pipeline import apply_six_step_pipeline


class ClusteringEngine:
    CLUSTER_THRESHOLD = 88.0

    def cluster_from_entities(
        self,
        entities: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Clusters à partir des formes normalisées."""
        names = [e.get("normalized") or e.get("original", "") for e in entities]
        return find_identity_clusters(names, threshold=self.CLUSTER_THRESHOLD)

    def apply_pipeline_clustering(
        self,
        text: str,
        annotations: List[Dict[str, Any]],
        clusters_raw: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Applique le pipeline 6 étapes avec seuil de fusion."""
        return apply_six_step_pipeline(
            text,
            annotations,
            clusters_raw,
            cluster_threshold=self.CLUSTER_THRESHOLD,
        )
