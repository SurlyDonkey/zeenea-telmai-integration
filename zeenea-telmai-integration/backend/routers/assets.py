from fastapi import APIRouter, HTTPException
from typing import List
from datetime import datetime, timezone

from models import MappedAsset, LinkRequest
from clients import ZeneaClient, TelmaiClient
from store import mappings_store, get_zeenea_client, get_telmai_client

router = APIRouter(prefix="/api/assets", tags=["assets"])


@router.get("", response_model=List[MappedAsset])
async def get_assets():
    zeenea: ZeneaClient = get_zeenea_client()
    telmai: TelmaiClient = get_telmai_client()

    zeenea_datasets = await zeenea.get_datasets()
    telmai_datasets = await telmai.get_datasets()

    telmai_by_id = {ds.id: ds for ds in telmai_datasets}

    result = []
    for zds in zeenea_datasets:
        mapping = mappings_store.get(zds.id)
        if mapping:
            telmai_id = mapping["telmai_id"]
            tds = telmai_by_id.get(telmai_id)
            result.append(
                MappedAsset(
                    zeenea_id=zds.id,
                    zeenea_name=zds.name,
                    telmai_id=telmai_id,
                    telmai_name=tds.display_name if tds else mapping.get("telmai_name"),
                    quality_score=tds.quality_score if tds else None,
                    alert_count=tds.alert_count if tds else 0,
                    last_synced=mapping.get("last_synced"),
                    status="linked",
                )
            )
        else:
            result.append(
                MappedAsset(
                    zeenea_id=zds.id,
                    zeenea_name=zds.name,
                    telmai_id=None,
                    telmai_name=None,
                    quality_score=None,
                    alert_count=0,
                    last_synced=None,
                    status="unlinked",
                )
            )

    return result


@router.post("/{zeenea_id}/link", response_model=MappedAsset)
async def link_asset(zeenea_id: str, body: LinkRequest):
    zeenea: ZeneaClient = get_zeenea_client()
    telmai: TelmaiClient = get_telmai_client()

    zeenea_datasets = await zeenea.get_datasets()
    zeenea_dataset = next((ds for ds in zeenea_datasets if ds.id == zeenea_id), None)
    if not zeenea_dataset:
        raise HTTPException(status_code=404, detail=f"Zeenea dataset '{zeenea_id}' not found")

    telmai_datasets = await telmai.get_datasets()
    telmai_dataset = next((ds for ds in telmai_datasets if ds.id == body.telmai_id), None)
    if not telmai_dataset:
        raise HTTPException(status_code=404, detail=f"Telmai dataset '{body.telmai_id}' not found")

    mappings_store[zeenea_id] = {
        "telmai_id": body.telmai_id,
        "telmai_name": telmai_dataset.display_name,
        "last_synced": datetime.now(timezone.utc),
    }

    return MappedAsset(
        zeenea_id=zeenea_id,
        zeenea_name=zeenea_dataset.name,
        telmai_id=body.telmai_id,
        telmai_name=telmai_dataset.display_name,
        quality_score=telmai_dataset.quality_score,
        alert_count=telmai_dataset.alert_count,
        last_synced=mappings_store[zeenea_id]["last_synced"],
        status="linked",
    )


@router.delete("/{zeenea_id}/link")
async def unlink_asset(zeenea_id: str):
    if zeenea_id not in mappings_store:
        raise HTTPException(status_code=404, detail=f"No mapping found for Zeenea dataset '{zeenea_id}'")

    del mappings_store[zeenea_id]
    return {"detail": f"Mapping for '{zeenea_id}' removed successfully"}
