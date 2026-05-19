"""Identity Graph Service — persistance et apprentissage progressif."""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.identity_graph import IdentityEdge, IdentityNode, IdentityVariant
from app.services.phonetic import combined_match_score

logger = logging.getLogger(__name__)

MERGE_NODE_THRESHOLD = 90.0


class IdentityGraphService:
    """Graphe d'identités : nodes=personnes, edges=relations, variants=occurrences."""

    def __init__(self, db: Session):
        self.db = db

    def _find_node_by_canonical(self, normalized: str) -> Optional[IdentityNode]:
        key = normalized.lower().strip()
        nodes = self.db.query(IdentityNode).all()
        best: Optional[IdentityNode] = None
        best_score = 0.0
        for node in nodes:
            score = combined_match_score(normalized, node.canonical_normalized)
            if score > best_score:
                best_score = score
                best = node
        if best and best_score >= MERGE_NODE_THRESHOLD:
            return best
        return self.db.query(IdentityNode).filter(
            IdentityNode.canonical_normalized.ilike(normalized)
        ).first()

    def upsert_node(
        self,
        normalized: str,
        arabic: str = "",
        language: str = "fr",
        confidence: int = 0,
    ) -> IdentityNode:
        node = self._find_node_by_canonical(normalized)
        if node:
            node.occurrence_count = (node.occurrence_count or 0) + 1
            n = node.occurrence_count
            node.avg_confidence = ((node.avg_confidence or 0) * (n - 1) + confidence) / n
            if arabic and not node.canonical_arabic:
                node.canonical_arabic = arabic
            self.db.commit()
            self.db.refresh(node)
            return node

        node = IdentityNode(
            canonical_normalized=normalized,
            canonical_arabic=arabic or None,
            primary_language=language,
            occurrence_count=1,
            avg_confidence=float(confidence),
        )
        self.db.add(node)
        self.db.commit()
        self.db.refresh(node)
        return node

    def add_variant(
        self,
        node: IdentityNode,
        original: str,
        normalized: str,
        language: str,
        phonetic: float,
        confidence: int,
        document_hash: str,
        line_number: Optional[int] = None,
        group_id: str = "",
    ) -> IdentityVariant:
        variant = IdentityVariant(
            node_id=node.id,
            original_form=original,
            normalized_form=normalized,
            language_detected=language,
            phonetic_similarity=phonetic,
            confidence_score=confidence,
            document_hash=document_hash,
            line_number=line_number,
            duplicate_group_id=group_id or None,
        )
        self.db.add(variant)
        self.db.commit()
        self.db.refresh(variant)
        return variant

    def link_nodes(
        self,
        node_a: IdentityNode,
        node_b: IdentityNode,
        similarity: float,
        reasoning: str,
    ) -> IdentityEdge:
        edge = IdentityEdge(
            source_node_id=node_a.id,
            target_node_id=node_b.id,
            relation_type="probable_duplicate",
            similarity_score=similarity,
            reasoning=reasoning,
        )
        self.db.add(edge)
        self.db.commit()
        return edge

    def ingest_document(
        self,
        entities: List[Dict[str, Any]],
        duplicate_clusters: List[Dict[str, Any]],
        document_hash: str,
    ) -> Dict[str, Any]:
        """Persiste les entités annotées dans le graphe."""
        node_by_group: Dict[str, IdentityNode] = {}
        nodes_created = 0
        variants_created = 0

        for ent in entities:
            normalized = ent.get("normalized") or ent.get("original", "")
            node = self.upsert_node(
                normalized=normalized,
                arabic=ent.get("arabic_name", ""),
                language=ent.get("language_detected", "fr"),
                confidence=int(ent.get("confidence_score", 0)),
            )
            if node.occurrence_count == 1:
                nodes_created += 1

            gid = ent.get("duplicate_group_id") or ""
            if gid:
                node_by_group.setdefault(gid, node)

            self.add_variant(
                node=node,
                original=ent.get("original", ""),
                normalized=normalized,
                language=ent.get("language_detected", "fr"),
                phonetic=float(ent.get("phonetic_similarity", 0)),
                confidence=int(ent.get("confidence_score", 0)),
                document_hash=document_hash,
                group_id=gid,
            )
            variants_created += 1

        edges_created = 0
        for cluster in duplicate_clusters:
            gid = cluster.get("group_id", "")
            members = cluster.get("members") or []
            if len(members) < 2:
                continue
            primary = node_by_group.get(gid)
            if not primary:
                primary = self.upsert_node(normalized=members[0])
            for member in members[1:]:
                other = self._find_node_by_canonical(member)
                if other and other.id != primary.id:
                    self.link_nodes(
                        primary,
                        other,
                        float(cluster.get("avg_similarity", 88)),
                        cluster.get("reasoning", ""),
                    )
                    edges_created += 1

        return {
            "nodes_touched": self.db.query(IdentityNode).count(),
            "variants_added": variants_created,
            "edges_added": edges_created,
            "document_hash": document_hash,
        }

    def get_stats(self) -> Dict[str, Any]:
        return {
            "nodes": self.db.query(IdentityNode).count(),
            "variants": self.db.query(IdentityVariant).count(),
            "edges": self.db.query(IdentityEdge).count(),
        }

    def get_node_with_variants(self, node_id: UUID) -> Optional[Dict[str, Any]]:
        node = self.db.query(IdentityNode).filter(IdentityNode.id == node_id).first()
        if not node:
            return None
        return {
            "id": str(node.id),
            "canonical_normalized": node.canonical_normalized,
            "canonical_arabic": node.canonical_arabic,
            "occurrence_count": node.occurrence_count,
            "avg_confidence": node.avg_confidence,
            "variants": [
                {
                    "original": v.original_form,
                    "normalized": v.normalized_form,
                    "language": v.language_detected,
                    "confidence": v.confidence_score,
                }
                for v in node.variants
            ],
        }
