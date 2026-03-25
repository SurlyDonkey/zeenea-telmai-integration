"""
SQLite persistence layer using SQLModel.
Defines tables and exports engine, session dependency, and create_db_and_tables().
"""
from datetime import datetime
from typing import Optional

from sqlmodel import Field, Session, SQLModel, create_engine

DATABASE_URL = "sqlite:///zeenea_telmai.db"

engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})


# ---------------------------------------------------------------------------
# Table definitions
# ---------------------------------------------------------------------------

class AssetMapping(SQLModel, table=True):
    """Persists zeenea_id ↔ telmai_id linkages."""

    __tablename__ = "asset_mapping"

    id: Optional[int] = Field(default=None, primary_key=True)
    zeenea_id: str = Field(unique=True, index=True)
    telmai_id: str
    telmai_name: str
    last_synced: Optional[datetime] = Field(default=None)


class SyncLogEntry(SQLModel, table=True):
    """Persistent sync log records."""

    __tablename__ = "sync_log_entry"

    id: str = Field(primary_key=True)
    timestamp: datetime
    direction: str  # "push" | "pull" | "full"
    asset_name: str
    status: str  # "success" | "failed" | "skipped"
    message: str


class AppSettings(SQLModel, table=True):
    """Key/value store for runtime configuration."""

    __tablename__ = "app_settings"

    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(unique=True, index=True)
    value: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def create_db_and_tables() -> None:
    """Create all tables if they do not already exist."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """FastAPI dependency that yields a database session."""
    with Session(engine) as session:
        yield session
