"""API Identity Graph — mémoire persistante des identités."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_optional
from app.database.session import get_db
from app.identity_graph.service import IdentityGraphService
from app.models.user import User

router = APIRouter()


@router.get("/stats")
def graph_stats(
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional),
) -> dict:
    """Statistiques du graphe d'identités."""
    return IdentityGraphService(db).get_stats()


@router.get("/nodes/{node_id}")
def get_node(
    node_id: UUID,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional),
) -> dict:
    """Détail d'un nœud et ses variantes."""
    data = IdentityGraphService(db).get_node_with_variants(node_id)
    if not data:
        raise HTTPException(status_code=404, detail="Nœud introuvable")
    return data
