from fastapi import APIRouter
from typing import List, Dict, Any
from datetime import datetime, timezone
import uuid

from models import SyncLogEntry, SyncResult
from clients import ZeneaClient, TelmaiClient
from store import mappings_store, sync_log, sync_status, get_zeenea_client, get_telmai_client

router = APIRouter(prefix="/api/sync", tags=["sync"])


def _make_log_entry(direction: str, asset_name: str, status: str, message: str) -> SyncLogEntry:
    entry = SyncLogEntry(
        id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc),
        direction=direction,
        asset_name=asset_name,
        status=status,
        message=message,
    )
    sync_log.insert(0, entry)
    # Keep log bounded to 500 entries
    if len(sync_log) > 500:
        sync_log.pop()
    return entry


async def _push_to_telmai(zeenea: ZeneaClient, telmai: TelmaiClient) -> tuple[int, int, int, List[SyncLogEntry]]:
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
                entry = _make_log_entry("push", zds.name, "skipped", "Dataset already exists in Telmai")
                skipped += 1
            else:
                await telmai.register_dataset(
                    name=zds.technical_name,
                    display_name=zds.name,
                    external_id=zds.id,
                )
                entry = _make_log_entry("push", zds.name, "success", f"Registered '{zds.name}' in Telmai")
                synced += 1
            entries.append(entry)
        except Exception as e:
            entry = _make_log_entry("push", zds.name, "failed", f"Error: {str(e)[:150]}")
            failed += 1
            entries.append(entry)

    return synced, failed, skipped, entries


async def _pull_from_telmai(zeenea: ZeneaClient, telmai: TelmaiClient) -> tuple[int, int, int, List[SyncLogEntry]]:
    synced = 0
    failed = 0
    skipped = 0
    entries: List[SyncLogEntry] = []

    telmai_datasets = await telmai.get_datasets()
    telmai_by_id = {ds.id: ds for ds in telmai_datasets}

    for zeenea_id, mapping in mappings_store.items():
        telmai_id = mapping["telmai_id"]
        tds = telmai_by_id.get(telmai_id)
        asset_name = mapping.get("telmai_name", telmai_id)

        if not tds:
            entry = _make_log_entry("pull", asset_name, "skipped", f"Telmai dataset '{telmai_id}' not found")
            skipped += 1
            entries.append(entry)
            continue

        try:
            now = datetime.now(timezone.utc).isoformat()
            success = await zeenea.update_quality_property(
                item_id=zeenea_id,
                score=tds.quality_score or 0.0,
                alert_count=tds.alert_count,
                last_checked=now,
            )
            if success:
                mapping["last_synced"] = datetime.now(timezone.utc)
                entry = _make_log_entry(
                    "pull",
                    asset_name,
                    "success",
                    f"Updated Zeenea with quality score {tds.quality_score:.1f}, {tds.alert_count} alerts",
                )
                synced += 1
            else:
                entry = _make_log_entry("pull", asset_name, "failed", "Zeenea update returned errors")
                failed += 1
            entries.append(entry)
        except Exception as e:
            entry = _make_log_entry("pull", asset_name, "failed", f"Error: {str(e)[:150]}")
            failed += 1
            entries.append(entry)

    if not mappings_store:
        entry = _make_log_entry("pull", "all", "skipped", "No asset mappings configured — link assets first")
        skipped += 1
        entries.append(entry)

    return synced, failed, skipped, entries


@router.post("/push", response_model=SyncResult)
async def sync_push():
    zeenea = get_zeenea_client()
    telmai = get_telmai_client()
    synced, failed, skipped, entries = await _push_to_telmai(zeenea, telmai)
    sync_status["last_push"] = datetime.now(timezone.utc).isoformat()
    sync_status["push_synced"] = synced
    sync_status["push_failed"] = failed
    return SyncResult(synced=synced, failed=failed, skipped=skipped, log_entries=entries)


@router.post("/pull", response_model=SyncResult)
async def sync_pull():
    zeenea = get_zeenea_client()
    telmai = get_telmai_client()
    synced, failed, skipped, entries = await _pull_from_telmai(zeenea, telmai)
    sync_status["last_pull"] = datetime.now(timezone.utc).isoformat()
    sync_status["pull_synced"] = synced
    sync_status["pull_failed"] = failed
    return SyncResult(synced=synced, failed=failed, skipped=skipped, log_entries=entries)


@router.post("/full", response_model=SyncResult)
async def sync_full():
    zeenea = get_zeenea_client()
    telmai = get_telmai_client()

    push_synced, push_failed, push_skipped, push_entries = await _push_to_telmai(zeenea, telmai)
    pull_synced, pull_failed, pull_skipped, pull_entries = await _pull_from_telmai(zeenea, telmai)

    now = datetime.now(timezone.utc).isoformat()
    sync_status["last_push"] = now
    sync_status["last_pull"] = now
    sync_status["last_full"] = now

    return SyncResult(
        synced=push_synced + pull_synced,
        failed=push_failed + pull_failed,
        skipped=push_skipped + pull_skipped,
        log_entries=push_entries + pull_entries,
    )


@router.get("/log", response_model=List[SyncLogEntry])
async def get_sync_log():
    return sync_log


@router.delete("/log")
async def clear_sync_log():
    sync_log.clear()
    return {"detail": "Sync log cleared"}


@router.get("/status")
async def get_sync_status() -> Dict[str, Any]:
    return {
        **sync_status,
        "mapped_assets": len(mappings_store),
        "log_entries": len(sync_log),
    }
