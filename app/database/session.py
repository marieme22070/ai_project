import logging
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

connect_args = {}
if settings.uses_sqlite:
    db_path = settings.database_url.replace("sqlite:///", "")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.database_url,
    pool_pre_ping=not settings.uses_sqlite,
    connect_args=connect_args,
)

if settings.uses_sqlite:

    @event.listens_for(engine, "connect")
    def _sqlite_fk(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app.models import citizen, correction_history, identity_graph, user  # noqa: F401

    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database ready (%s).", "SQLite" if settings.uses_sqlite else "PostgreSQL")
    except Exception as exc:
        logger.warning("Database init skipped: %s", exc)
