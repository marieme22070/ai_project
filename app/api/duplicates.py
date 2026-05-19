from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_optional
from app.database.session import get_db
from app.models.user import User
from app.services.name_service import NameService

router = APIRouter()


@router.get("")
async def detect_duplicates(
    threshold: float = Query(85.0, ge=50, le=100),
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional),
) -> dict:
    """Détection de doublons d'identité avec scores et explications IA."""
    service = NameService(db)
    duplicates = service.detect_duplicates(threshold=threshold)
    high_risk = sum(1 for d in duplicates if d.get("duplicate_probability", 0) >= 90)
    return {
        "count": len(duplicates),
        "high_risk_count": high_risk,
        "threshold": threshold,
        "duplicates": duplicates,
    }
