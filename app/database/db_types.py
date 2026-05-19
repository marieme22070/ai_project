from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

# Compatible PostgreSQL (JSONB) et SQLite (JSON)
FlexibleJSON = JSON().with_variant(JSONB(), "postgresql")
