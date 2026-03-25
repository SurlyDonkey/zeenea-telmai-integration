from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, delete
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field
import uuid

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from auth import verify_api_key
from database import AssetMapping, SyncLogEntry as DBSyncLogEntry, get_session
from models import SyncLogEntry, SyncResult
from clients import ZeneaClient, TelmaiClient
from store import get_zeenea_client, get_telmai_client

router = APIRouter(
    prefix="/api/sync",
    tags=["sync"],
    dependencies=[Depends(verify_api_key)],
)

# Module-level scheduler — started by main.py on startup
scheduler = AsyncIOScheduler()

# Default sync interval in hours (can be changed at runtime)
_sync_interval_hours: float = 4.0


class SchedulerConfigRequest(BaseModel):
    interval_hours: float = Field(ge=0.25, le=168.0, description="Sync interval in hours (0.25–168)")


class SchedulerConfigResponse(BaseModel):
    interval_hours: float
    next_run: Optional[str]
    is_running: bool


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _make_log_entry(
    session: Session,
    direction: str,
    asset_name: str,
    status: str,
    message: str,
) -> SyncLogEntry:
    """Persist a log record to the DB and return the Pydantic response model."""
    entry_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    db_row = DBSyncLogEntry(
        id=entry_id,
        timestamp=now,
        direction=direction,
        asset_name=asset_name,
        status=status,
        message=message,
    )
    session.add(db_row)
    session.commit()
    return SyncLogEntry(
        id=entry_id,
        timestamp=now,
        direction=direction,
        asset_name=asset_name,
        status=status,
        message=message,
    )


async def _push_to_telmai(
    session: Session,
    zeenea: ZeneaClient,
    telmai: TelmaiClient,
) -> tuple[int, int, int, List[SyncLogEntry]]:
    synced = 0
    failed = 0
    skipped = 0
    entries: List[SyncLogEntry] = []

    zeenea_datasets = await zeenea.get_datasets()
    telmai_datasets = await telmai.get_datasets()
    telmai_names = {ds.name for ds in telmai_datasets}

    for zds in zeenea_datasets:
        try:
            if zds.name in telmai_names:
                entry = _make_log_entry(session, "push", zds.name, "skipped", "Dataset already exists in Telmai")
                skipped += 1
            else:
                await telmai.register_dataset(
                    name=zds.technical_name,
                    display_name=zds.name,
                    external_id=zds.id,
                )
                entry = _make_log_entry(session, "push", zds.name, "success", f"Registered '{zds.name}' in Telmai")
                synced += 1
            entries.append(entry)
        except Exception as e:
            entry = _make_log_entry(session, "push", zds.name, "failed", f"Error: {str(e)[:150]}")
            failed += 1
            entries.append(entry)

    return synced, failed, skipped, entries


async def _pull_from_telmai(
    session: Session,
    zeenea: ZeneaClient,
    telmai: TelmaiClient,
) -> tuple[int, int, int, List[SyncLogEntry]]:
    synced = 0
    failed = 0
    skipped = 0
    entries: List[SyncLogEntry] = []

    mappings = session.exec(select(AssetMapping)).all()

    telmai_datasets = await telmai.get_datasets()
    telmai_by_id = {ds.id: ds for ds in telmai_datasets}

    for mapping in mappings:
        tds = telmai_by_id.get(mapping.telmai_id)
        asset_name = mapping.telmai_name or mapping.telmai_id

        if not tds:
            entry = _make_log_entry(
                session, "pull", asset_name, "skipped",
                f"Telmai dataset '{mapping.telmai_id}' not found",
            )
            skipped += 1
            entries.append(entry)
            continue

        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            success = await zeenea.update_quality_properties(
                item_id=mapping.zeenea_id,
                score=tds.quality_score or 0.0,
                alert_count=tds.alert_count,
                last_checked=now_iso,
            )
            if success:
                mapping.last_synced = datetime.now(timezone.utc)
                session.add(mapping)
                session.commit()
                entry = _make_log_entry(
                    session,
                    "pull",
                    asset_name,
                    "success",
                    f"Updated Zeenea with quality score {tds.quality_score:.1f}, {tds.alert_count} alerts",
                )
                synced += 1
            else:
                entry = _make_log_entry(
                    session, "pull", asset_name, "failed", "Zeenea update returned errors"
                )
                failed += 1
            entries.append(entry)
        except Exception as e:
            entry = _make_log_entry(
                session, "pull", asset_name, "failed", f"Error: {str(e)[:150]}"
            )
            failed += 1
            entries.append(entry)

    if not mappings:
        entry = _make_log_entry(
            session,
            "pull",
            "all",
            "skipped",
            "No asset mappings configured — link assets first",
        )
        skipped += 1
        entries.append(entry)

    return synced, failed, skipped, entries


# ---------------------------------------------------------------------------
# Scheduled full-sync (called by APScheduler every 4 hours)
# ---------------------------------------------------------------------------

async def _scheduled_full_sync() -> None:
    """Background task: run a full push+pull sync."""
    from database import engine
    from sqlmodel import Session as _Session

    with _Session(engine) as session:
        zeenea = get_zeenea_client()
        telmai = get_telmai_client()
        await _push_to_telmai(session, zeenea, telmai)
        await _pull_from_telmai(session, zeenea, telmai)


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------

@router.post("/push", response_model=SyncResult)
async def sync_push(session: Session = Depends(get_session)):
    zeenea = get_zeenea_client()
    telmai = get_telmai_client()
    synced, failed, skipped, entries = await _push_to_telmai(session, zeenea, telmai)
    return SyncResult(synced=synced, failed=failed, skipped=skipped, log_entries=entries)


@router.post("/pull", response_model=SyncResult)
async def sync_pull(session: Session = Depends(get_session)):
    zeenea = get_zeenea_client()
    telmai = get_telmai_client()
    synced, failed, skipped, entries = await _pull_from_telmai(session, zeenea, telmai)
    return SyncResult(synced=synced, failed=failed, skipped=skipped, log_entries=entries)


@router.post("/full", response_model=SyncResult)
async def sync_full(session: Session = Depends(get_session)):
    zeenea = get_zeenea_client()
    telmai = get_telmai_client()

    push_synced, push_failed, push_skipped, push_entries = await _push_to_telmai(
        session, zeenea, telmai
    )
    pull_synced, pull_failed, pull_skipped, pull_entries = await _pull_from_telmai(
        session, zeenea, telmai
    )

    return SyncResult(
        synced=push_synced + pull_synced,
        failed=push_failed + pull_failed,
        skipped=push_skipped + pull_skipped,
        log_entries=push_entries + pull_entries,
    )


@router.get("/log", response_model=List[SyncLogEntry])
async def get_sync_log(session: Session = Depends(get_session)):
    rows = session.exec(
        select(DBSyncLogEntry).order_by(DBSyncLogEntry.timestamp.desc()).limit(200)
    ).all()
    return [
        SyncLogEntry(
            id=r.id,
            timestamp=r.timestamp,
            direction=r.direction,
            asset_name=r.asset_name,
            status=r.status,
            message=r.message,
        )
        for r in rows
    ]


@router.delete("/log")
async def clear_sync_log(session: Session = Depends(get_session)):
    session.exec(delete(DBSyncLogEntry))
    session.commit()
    return {"detail": "Sync log cleared"}


@router.get("/scheduler", response_model=SchedulerConfigResponse)
async def get_scheduler_config() -> SchedulerConfigResponse:
    """Return the current auto-sync interval and next scheduled run."""
    job = scheduler.get_job("full_sync")
    next_run = None
    if job and job.next_run_time:
        next_run = job.next_run_time.isoformat()
    return SchedulerConfigResponse(
        interval_hours=_sync_interval_hours,
        next_run=next_run,
        is_running=scheduler.running,
    )


@router.post("/scheduler", response_model=SchedulerConfigResponse)
async def update_scheduler_config(body: SchedulerConfigRequest) -> SchedulerConfigResponse:
    """Update the auto-sync interval. Takes effect immediately."""
    global _sync_interval_hours
    _sync_interval_hours = body.interval_hours

    if scheduler.running:
        scheduler.reschedule_job(
            "full_sync",
            trigger="interval",
            hours=body.interval_hours,
        )

    job = scheduler.get_job("full_sync")
    next_run = job.next_run_time.isoformat() if job and job.next_run_time else None
    return SchedulerConfigResponse(
        interval_hours=_sync_interval_hours,
        next_run=next_run,
        is_running=scheduler.running,
    )


@router.get("/status")
async def get_sync_status(session: Session = Depends(get_session)) -> Dict[str, Any]:
    from sqlmodel import func, col

    total_mappings = len(session.exec(select(AssetMapping)).all())
    total_log = session.exec(select(func.count()).select_from(DBSyncLogEntry)).one()

    # Recent counts (last 200 entries)
    recent = session.exec(
        select(DBSyncLogEntry).order_by(DBSyncLogEntry.timestamp.desc()).limit(200)
    ).all()
    recent_success = sum(1 for r in recent if r.status == "success")
    recent_failed = sum(1 for r in recent if r.status == "failed")

    # Last timestamps per direction
    def _last(direction: str) -> str | None:
        row = session.exec(
            select(DBSyncLogEntry)
            .where(DBSyncLogEntry.direction == direction)
            .order_by(DBSyncLogEntry.timestamp.desc())
            .limit(1)
        ).first()
        return row.timestamp.isoformat() if row else None

    return {
        "last_push": _last("push"),
        "last_pull": _last("pull"),
        "last_full": _last("full"),
        "recent_success": recent_success,
        "recent_failed": recent_failed,
        "mapped_assets": total_mappings,
        "log_entries": total_log,
    }
