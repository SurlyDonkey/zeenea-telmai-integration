"""
Factory functions for API clients and runtime settings.
Settings are read from DB first, then fall back to environment variables.
"""
import os
from typing import Dict, Optional

from dotenv import load_dotenv
from sqlmodel import Session, select

load_dotenv()

# ---------------------------------------------------------------------------
# Settings helpers (DB-backed with env-var fallback)
# ---------------------------------------------------------------------------

def get_setting_from_db(session: Session, key: str) -> Optional[str]:
    """Return the value for *key* stored in AppSettings, or None."""
    from database import AppSettings
    row = session.exec(select(AppSettings).where(AppSettings.key == key)).first()
    return row.value if row else None


def save_setting_to_db(session: Session, key: str, value: str) -> None:
    """Upsert a key/value pair into AppSettings."""
    from database import AppSettings
    row = session.exec(select(AppSettings).where(AppSettings.key == key)).first()
    if row:
        row.value = value
    else:
        row = AppSettings(key=key, value=value)
        session.add(row)
    session.commit()


def _get_setting_env(key: str, env_key: str) -> str:
    """Read from env vars only (used when no DB session is available)."""
    return os.getenv(env_key, "")


def get_current_settings() -> Dict[str, str]:
    """
    Return current settings by reading from the DB when possible,
    falling back to environment variables.
    """
    from database import engine
    from sqlmodel import Session as _Session

    with _Session(engine) as session:
        def _get(key: str, env_key: str) -> str:
            db_val = get_setting_from_db(session, key)
            return db_val if db_val else os.getenv(env_key, "")

        return {
            "zeenea_url": _get("zeenea_url", "ZEENEA_URL"),
            "zeenea_api_key": _get("zeenea_api_key", "ZEENEA_API_KEY"),
            "telmai_url": _get("telmai_url", "TELMAI_URL"),
            "telmai_token": _get("telmai_token", "TELMAI_TOKEN"),
        }


def update_settings(updates: Dict[str, str]) -> None:
    """
    Persist non-empty setting values to the DB and keep an in-memory copy
    so that get_zeenea_client() / get_telmai_client() pick them up immediately.
    """
    from database import engine
    from sqlmodel import Session as _Session

    with _Session(engine) as session:
        for key, value in updates.items():
            if value:
                save_setting_to_db(session, key, value)


# ---------------------------------------------------------------------------
# Client factories
# ---------------------------------------------------------------------------

def get_zeenea_client():
    from clients import ZeneaClient
    settings = get_current_settings()
    return ZeneaClient(
        url=settings["zeenea_url"],
        api_key=settings["zeenea_api_key"],
    )


def get_telmai_client():
    from clients import TelmaiClient
    settings = get_current_settings()
    return TelmaiClient(
        base_url=settings["telmai_url"],
        token=settings["telmai_token"],
    )
