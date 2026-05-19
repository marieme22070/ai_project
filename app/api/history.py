from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.session import get_db
from app.models.correction_history import CorrectionHistory
from app.models.user import User
from app.schemas.name import ValidationRequest
from app.services.name_knowledge import normalize_lookup_key, save_learned_name

router = APIRouter()


@router.get("")
def list_history(
    skip: int = 0,
    limit: int = 50,
    validated: Optional[int] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[dict]:
    query = db.query(CorrectionHistory).order_by(CorrectionHistory.created_at.desc())
    if validated is not None:
        query = query.filter(CorrectionHistory.validated == validated)
    records = query.offset(skip).limit(limit).all()
    return [
        {
            "id": str(r.id),
            "input_name": r.input_name,
            "normalized_name": r.normalized_name,
            "arabic_name": r.arabic_name,
            "confidence": r.confidence,
            "variants": r.variants,
            "source": r.source,
            "validated": r.validated,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in records
    ]


@router.post("/validate")
def validate_correction(
    body: ValidationRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    record = db.query(CorrectionHistory).filter(CorrectionHistory.id == body.history_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="History record not found")

    record.validated = 1 if body.approved else -1
    record.validated_by = user.username

    if body.corrected_name:
        record.normalized_name = body.corrected_name
    if body.corrected_arabic:
        record.arabic_name = body.corrected_arabic

    learned_entry = None
    if body.approved:
        final_normalized = (body.corrected_name or record.normalized_name or "").strip()
        final_arabic = (body.corrected_arabic or record.arabic_name or "").strip()
        if final_normalized:
            try:
                learned_entry = save_learned_name(
                    input_key=normalize_lookup_key(record.input_name),
                    normalized=final_normalized,
                    arabic=final_arabic,
                    learned_by=user.username,
                )
            except Exception as exc:
                raise HTTPException(
                    status_code=500,
                    detail=f"Validation OK mais sauvegarde learned_names echouee: {exc}",
                ) from exc

    if body.notes:
        meta = record.metadata_json or {}
        meta["validation_notes"] = body.notes
        record.metadata_json = meta

    db.commit()

    response = {
        "status": "validated",
        "id": str(record.id),
        "approved": body.approved,
        "learned": learned_entry is not None,
    }
    if learned_entry:
        response["learned_entry"] = learned_entry
        response["message"] = (
            f"Correction apprise et sauvegardee dans learned_names.py "
            f"({learned_entry['key']} → {learned_entry['normalized']})"
        )
    return response
