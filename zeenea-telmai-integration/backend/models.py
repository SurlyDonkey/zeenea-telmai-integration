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


class TelmaiWebhookPayload(BaseModel):
    """
    Payload sent by Telmai when a data scan completes.
    Used to immediately pull fresh alerts and update Zeenea.

    source_id: Telmai source/asset identifier
    job_id:    Upload/scan job identifier — passed to Check for Alerts API
    event:     Event type (e.g. "scan_complete", "alert_triggered")
    tenant:    Optional — overrides the configured tenant for this request
    """
    source_id: str
    job_id: str
    event: str = "scan_complete"
    tenant: Optional[str] = None


class WebhookResult(BaseModel):
    source_id: str
    job_id: str
    alerts_found: int
    zeenea_updated: bool
    quality_score: Optional[float] = None
    message: str


class LinkRequest(BaseModel):
    telmai_id: str


class SettingsUpdate(BaseModel):
    zeenea_url: Optional[str] = None
    zeenea_api_key: Optional[str] = None
    telmai_endpoint: Optional[str] = None
    telmai_tenant: Optional[str] = None
    telmai_username: Optional[str] = None
    telmai_password: Optional[str] = None
    telmai_client_id: Optional[str] = None
    telmai_auth_endpoint: Optional[str] = None


class ConnectionTestResult(BaseModel):
    service: str
    success: bool
    message: str
    dataset_count: Optional[int] = None
