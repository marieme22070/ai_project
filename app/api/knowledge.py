from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, get_current_user_optional
from app.models.user import User
from app.schemas.name import LearnNameRequest
from app.services.name_knowledge import (
    get_all_names,
    get_knowledge_stats,
    get_learned_names,
    normalize_lookup_key,
    reload_learned_names,
    save_learned_name,
)

router = APIRouter()


@router.post("/learn")
def learn_name(
    body: LearnNameRequest,
    user: Optional[User] = Depends(get_current_user_optional),
) -> Dict[str, Any]:
    """Valider une correction et l'enregistrer dans learned_names.py."""
    learned_by = user.username if user else "public"
    entry = save_learned_name(
        input_key=normalize_lookup_key(body.input_name),
        normalized=body.normalized.strip(),
        arabic=(body.arabic_name or "").strip(),
        learned_by=learned_by,
    )
    return {
        "status": "learned",
        "message": f"Correction enregistree: {entry['key']} → {entry['normalized']}",
        "learned_entry": entry,
        "total_names": len(get_all_names()),
    }


@router.get("/stats")
def knowledge_stats(user: User = Depends(get_current_user_optional)) -> Dict[str, Any]:
    stats = get_knowledge_stats()
    return {
        **stats,
        "merged": "LOCAL_NAMES + LEARNED_NAMES",
    }


@router.get("/learned")
def list_learned(user: User = Depends(get_current_user)) -> Dict[str, Any]:
    learned = get_learned_names()
    return {"count": len(learned), "learned_names": learned}


@router.post("/reload")
def reload_knowledge(user: Optional[User] = Depends(get_current_user_optional)) -> Dict[str, Any]:
    learned = reload_learned_names()
    return {
        "status": "reloaded",
        "learned_count": len(learned),
        "total_count": len(get_all_names()),
    }
