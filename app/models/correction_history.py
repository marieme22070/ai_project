import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID

from app.database.db_types import FlexibleJSON
from app.database.session import Base


class CorrectionHistory(Base):
    __tablename__ = "correction_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    input_name = Column(String(255), nullable=False)
    normalized_name = Column(String(255), nullable=True)
    arabic_name = Column(String(255), nullable=True)
    confidence = Column(Integer, nullable=True)
    variants = Column(FlexibleJSON, default=list)
    source = Column(String(50), default="text")  # text | audio
    matched_citizen_id = Column(UUID(as_uuid=True), nullable=True)
    validated = Column(Integer, default=0)  # 0=pending, 1=approved, -1=rejected
    validated_by = Column(String(100), nullable=True)
    metadata_json = Column(FlexibleJSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
