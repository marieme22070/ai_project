"""Seed national citizen database with test names."""

import logging

from sqlalchemy.orm import Session

from app.ai.embeddings import get_embedding
from app.models.citizen import Citizen
from app.services.elasticsearch_service import es_service

logger = logging.getLogger(__name__)

SEED_CITIZENS = [
    ("Mohamed Baba", "محمد بابا", ["Mohamedou Baba", "Mohaned Baba"], "fr", "Nouakchott"),
    ("Ramata Ding", "راماتا دينغ", ["Ramata Dink", "Ramata ding"], "fr", "Nouakchott"),
    ("Mamadou Diallo", "مامادو ديالو", ["MAMADOU DIALLO", "Diallo Jallo"], "pulaar", "Nouakchott"),
    ("Kreybiche", "كريبيش", ["Khreybiche", "Kreybiche"], "hassaniya", "Nouadhibou"),
    ("Moussa Ndiaye", "موسى اندياي", ["N'DIAYE", "Ndiaye"], "wolof", "Rosso"),
    ("Khalidou Barro", "خليدو بارو", ["KHALIDOU", "BARROU"], "fr", "Kaédi"),
    ("Hapsatou Sall", "حفصة سال", ["Hapsatou", "SALL"], "fr", "Nouakchott"),
    ("Alassane Traoré", "الحسن تراوري", ["Alassane", "TRAORE"], "fr", "Sélibaby"),
    ("Ablaye Diakité", "أبلاي دياكيتي", ["Ablaiye", "Diakite"], "fr", "Boghe"),
    ("Roukaya El Bekaye", "رقية البكاي", ["Roukaya", "EL BEKAYE"], "ar", "Nouakchott"),
    ("Abderraouf Sidibé", "عبد الرؤوف سيديبي", ["Abderraouf", "SIDIBE"], "fr", "Nouakchott"),
    ("Kadiata Coulibaly", "كادياتا كوليبالي", ["Kadiata", "Colibaly", "Coulibaly"], "fr", "Néma"),
    ("Sokhna Diagne", "سخنة دياغن", ["Sokhena", "DIAGANA"], "wolof", "Rosso"),
    ("Meguèye Ball", "ميغي بال", ["Megueye", "BALL"], "fr", "Aleg"),
    ("Houleymatou Ba", "حليمة با", ["Houley", "Ba", "Bah"], "hassaniya", "Nouakchott"),
]


def seed_citizens(db: Session) -> int:
    existing = db.query(Citizen).count()
    if existing > 0:
        logger.info("Citizens already seeded (%d records).", existing)
        return existing

    count = 0
    for official, arabic, variants, lang, region in SEED_CITIZENS:
        embedding = get_embedding(official)
        citizen = Citizen(
            official_name=official,
            arabic_name=arabic,
            variants=variants,
            language=lang,
            region=region,
            embedding=embedding,
        )
        db.add(citizen)
        count += 1

    db.commit()

    if es_service.available:
        citizens = db.query(Citizen).all()
        for c in citizens:
            es_service.index_citizen(
                {
                    "id": str(c.id),
                    "official_name": c.official_name,
                    "arabic_name": c.arabic_name or "",
                    "variants": c.variants or [],
                    "language": c.language,
                    "region": c.region,
                }
            )

    logger.info("Seeded %d citizens.", count)
    return count


def seed_admin_user(db: Session) -> None:
    from app.models.user import User
    from app.utils.security import get_password_hash

    if db.query(User).filter(User.username == "admin").first():
        return
    admin = User(
        username="admin",
        email="admin@gov.mr",
        hashed_password=get_password_hash("Admin@2024!"),
        full_name="Administrateur Système",
        role="admin",
    )
    db.add(admin)
    db.commit()
    logger.info("Default admin user created (username: admin).")
