from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class ZeneaDataset(BaseModel):
    id: str
    name: str
    technical_name: str
    description: Optional[str] = None


class TelmaiDataset(BaseModel):
    id: str
    name: str
    display_name: str
    external_id: Optional[str] = None
    quality_score: Optional[float] = None
    alert_count: int = 0


class MappedAsset(BaseModel):
    zeenea_id: str
    zeenea_name: str
    telmai_id: Optional[str] = None
    telmai_name: Optional[str] = None
    quality_score: Optional[float] = None
    alert_count: int = 0
    last_synced: Optional[datetime] = None
    status: str  # "linked", "unlinked", "syncing", "error"


class SyncLogEntry(BaseModel):
    id: str
    timestamp: datetime
    direction: str  # "push", "pull", "full"
    asset_name: str
    status: str  # "success", "failed", "skipped"
    message: str


class SyncResult(BaseModel):
    synced: int
    failed: int
    skipped: int
    log_entries: List[SyncLogEntry]


class LinkRequest(BaseModel):
    telmai_id: str


class SettingsUpdate(BaseModel):
    zeenea_url: Optional[str] = None
    zeenea_api_key: Optional[str] = None
    telmai_url: Optional[str] = None
    telmai_token: Optional[str] = None


class ConnectionTestResult(BaseModel):
    service: str
    success: bool
    message: str
    dataset_count: Optional[int] = None
