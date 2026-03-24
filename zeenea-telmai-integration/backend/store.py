"""
In-memory store for mappings, sync log, and runtime config.
Also provides factory functions for API clients.
"""
import os
from typing import Dict, Any, List
from dotenv import load_dotenv

load_dotenv()

# Mapping: zeenea_id -> {telmai_id, telmai_name, last_synced}
mappings_store: Dict[str, Any] = {}

# Sync log entries (most recent first)
sync_log: List[Any] = []

# Sync status counters / timestamps
sync_status: Dict[str, Any] = {
    "last_push": None,
    "last_pull": None,
    "last_full": None,
    "push_synced": 0,
    "push_failed": 0,
    "pull_synced": 0,
    "pull_failed": 0,
}

# Runtime settings (can be overridden via /api/settings)
_runtime_settings: Dict[str, str] = {}


def get_setting(key: str, env_key: str) -> str:
    return _runtime_settings.get(key) or os.getenv(env_key, "")


def update_settings(updates: Dict[str, str]) -> None:
    _runtime_settings.update({k: v for k, v in updates.items() if v})


def get_current_settings() -> Dict[str, str]:
    return {
        "zeenea_url": get_setting("zeenea_url", "ZEENEA_URL"),
        "zeenea_api_key": get_setting("zeenea_api_key", "ZEENEA_API_KEY"),
        "telmai_url": get_setting("telmai_url", "TELMAI_URL"),
        "telmai_token": get_setting("telmai_token", "TELMAI_TOKEN"),
    }


def get_zeenea_client():
    from clients import ZeneaClient
    return ZeneaClient(
        url=get_setting("zeenea_url", "ZEENEA_URL"),
        api_key=get_setting("zeenea_api_key", "ZEENEA_API_KEY"),
    )


def get_telmai_client():
    from clients import TelmaiClient
    return TelmaiClient(
        base_url=get_setting("telmai_url", "TELMAI_URL"),
        token=get_setting("telmai_token", "TELMAI_TOKEN"),
    )


def _seed_demo_mappings():
    """Pre-populate mappings so the dashboard shows data out of the box."""
    from datetime import datetime, timezone
    demo = [
        ("zee-001", "tel-001", "Customer Orders"),
        ("zee-002", "tel-002", "Product Catalog"),
        ("zee-003", "tel-003", "User Events Stream"),
        ("zee-004", "tel-004", "Inventory Levels"),
        ("zee-005", "tel-005", "Revenue Metrics"),
    ]
    for zeenea_id, telmai_id, telmai_name in demo:
        mappings_store[zeenea_id] = {
            "telmai_id": telmai_id,
            "telmai_name": telmai_name,
            "last_synced": datetime.now(timezone.utc),
        }


_seed_demo_mappings()
