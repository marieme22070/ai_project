import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID

from app.database.db_types import FlexibleJSON
from app.database.session import Base


class Citizen(Base):
    __tablename__ = "citizens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    official_name = Column(String(255), nullable=False, index=True)
    arabic_name = Column(String(255), nullable=True, index=True)
    variants = Column(FlexibleJSON, default=list)
    language = Column(String(50), nullable=True)
    region = Column(String(100), nullable=True)
    embedding = Column(FlexibleJSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
