from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.ai.embeddings import get_embedding
from app.api.deps import get_current_admin, get_current_user
from app.database.session import get_db
from app.models.citizen import Citizen
from app.models.user import User
from app.schemas.citizen import CitizenCreate, CitizenResponse, CitizenSearchResult
from app.services.elasticsearch_service import es_service
from app.services.phonetic import combined_match_score, fuzzy_search_in_list

router = APIRouter()


@router.post("", response_model=CitizenResponse, status_code=201)
def create_citizen(
    data: CitizenCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_admin),
) -> Citizen:
    embedding = get_embedding(data.official_name)
    citizen = Citizen(
        official_name=data.official_name,
        arabic_name=data.arabic_name,
        variants=data.variants,
        language=data.language,
        region=data.region,
        embedding=embedding,
    )
    db.add(citizen)
    db.commit()
    db.refresh(citizen)

    es_service.index_citizen(
        {
            "id": str(citizen.id),
            "official_name": citizen.official_name,
            "arabic_name": citizen.arabic_name or "",
            "variants": citizen.variants or [],
            "language": citizen.language,
            "region": citizen.region,
        }
    )
    return citizen


@router.get("", response_model=List[CitizenResponse])
def list_citizens(
    skip: int = 0,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[Citizen]:
    return db.query(Citizen).offset(skip).limit(limit).all()


@router.get("/search", response_model=List[CitizenSearchResult])
def search_citizens(
    q: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[CitizenSearchResult]:
    es_hits = es_service.search(q, limit=10)
    if es_hits:
        return [
            CitizenSearchResult(
                id=UUID(h["id"]) if isinstance(h.get("id"), str) else h["id"],
                official_name=h["official_name"],
                arabic_name=h.get("arabic_name"),
                score=float(h.get("score", 0)),
                match_type="elasticsearch",
            )
            for h in es_hits
        ]

    citizens = db.query(Citizen).limit(500).all()
    items = [
        {
            "id": c.id,
            "official_name": c.official_name,
            "arabic_name": c.arabic_name,
        }
        for c in citizens
    ]
    fuzzy = fuzzy_search_in_list(q, items)
    return [
        CitizenSearchResult(
            id=item["id"],
            official_name=item["official_name"],
            arabic_name=item.get("arabic_name"),
            score=item["score"],
            match_type="postgresql_fuzzy",
        )
        for item in fuzzy
    ]


@router.get("/{citizen_id}", response_model=CitizenResponse)
def get_citizen(
    citizen_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Citizen:
    citizen = db.query(Citizen).filter(Citizen.id == citizen_id).first()
    if not citizen:
        raise HTTPException(status_code=404, detail="Citizen not found")
    return citizen


@router.delete("/{citizen_id}", status_code=204)
def delete_citizen(
    citizen_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_admin),
) -> None:
    citizen = db.query(Citizen).filter(Citizen.id == citizen_id).first()
    if not citizen:
        raise HTTPException(status_code=404, detail="Citizen not found")
    es_service.delete_citizen(citizen_id)
    db.delete(citizen)
    db.commit()
