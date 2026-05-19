"""Identity Graph — mémoire persistante des identités (nodes + variantes + liens)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database.db_types import FlexibleJSON
from app.database.session import Base


class IdentityNode(Base):
    """Nœud = identité canonique (personne)."""

    __tablename__ = "identity_nodes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    canonical_normalized = Column(String(255), nullable=False, index=True)
    canonical_arabic = Column(String(255), nullable=True)
    primary_language = Column(String(32), default="mixed")
    occurrence_count = Column(Integer, default=1)
    avg_confidence = Column(Float, default=0.0)
    metadata_json = Column(FlexibleJSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    variants = relationship("IdentityVariant", back_populates="node", cascade="all, delete-orphan")
    outgoing_edges = relationship(
        "IdentityEdge",
        foreign_keys="IdentityEdge.source_node_id",
        back_populates="source_node",
        cascade="all, delete-orphan",
    )


class IdentityVariant(Base):
    """Variante textuelle liée à un nœud."""

    __tablename__ = "identity_variants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    node_id = Column(
        UUID(as_uuid=True),
        ForeignKey("identity_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    original_form = Column(String(500), nullable=False, index=True)
    normalized_form = Column(String(255), nullable=False)
    language_detected = Column(String(32), default="fr")
    phonetic_similarity = Column(Float, default=0.0)
    confidence_score = Column(Integer, default=0)
    document_hash = Column(String(32), nullable=True, index=True)
    line_number = Column(Integer, nullable=True)
    duplicate_group_id = Column(String(16), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    node = relationship("IdentityNode", back_populates="variants")


class IdentityEdge(Base):
    """Lien entre deux nœuds (probable même personne)."""

    __tablename__ = "identity_edges"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_node_id = Column(
        UUID(as_uuid=True),
        ForeignKey("identity_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_node_id = Column(
        UUID(as_uuid=True),
        ForeignKey("identity_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relation_type = Column(String(32), default="probable_duplicate")
    similarity_score = Column(Float, default=0.0)
    reasoning = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    source_node = relationship(
        "IdentityNode",
        foreign_keys=[source_node_id],
        back_populates="outgoing_edges",
    )
